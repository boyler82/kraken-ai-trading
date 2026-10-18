"""Additive, public-only Kraken display quotes for frozen research reports."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable

PUBLIC_TICKER_ENDPOINT = "https://api.kraken.com/0/public/Ticker"
LIVE_PRICE_FRESHNESS_SECONDS = float(os.environ.get("LIVE_PRICE_FRESHNESS_SECONDS", "60"))
LIVE_REFERENCE_SEMANTICS = "MIDPOINT_OF_KRAKEN_BEST_BID_AND_BEST_ASK"

def _canonical_pair(value: str) -> str:
    pair = str(value).upper()
    if pair.endswith("ZUSD"): pair = pair[:-4] + "USD"
    if pair.startswith("X") and pair not in {"XBTUSD"}: pair = pair[1:]
    return pair

def _utc(value: Any = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)

def fetch_public_mid_prices(pairs: list[str], opener: Callable[..., Any] = urllib.request.urlopen,
                            clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> dict[str, dict[str, Any]]:
    """Fetch public Ticker; timestamp is local UTC response receipt (Ticker has none)."""
    requested = sorted({str(pair) for pair in pairs if pair})
    if not requested:
        return {}
    url = PUBLIC_TICKER_ENDPOINT + "?" + urllib.parse.urlencode({"pair": ",".join(requested)})
    request = urllib.request.Request(url, headers={"User-Agent": "kraken-ai-trading-live-reference/1.0"})
    with opener(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    received = _utc(clock()).isoformat()
    if not isinstance(payload, dict) or payload.get("error") or not isinstance(payload.get("result"), dict):
        raise ValueError("malformed Kraken public Ticker response")
    result = payload["result"];quotes = {}
    for pair in requested:
        row = result.get(pair) or next((value for key, value in result.items() if _canonical_pair(key) == _canonical_pair(pair)), None)
        if row is None and len(requested) == 1 and len(result) == 1:
            row = next(iter(result.values()))
        if not isinstance(row, dict):
            continue
        bid = float(row["b"][0]);ask = float(row["a"][0])
        if bid > 0 and ask >= bid:
            quotes[pair] = {"price": (bid + ask) / 2.0, "timestamp": received, "bid": bid, "ask": ask}
    return quotes

def unavailable_fields(status: str = "LIVE_PRICE_UNAVAILABLE") -> dict[str, Any]:
    return {"live_reference_price": None, "live_reference_timestamp": None,
            "live_price_age_seconds": None, "price_drift_pct": None,
            "live_price_status": status, "live_reference_semantics": LIVE_REFERENCE_SEMANTICS}

def reference_fields(analysis_price: Any, quote: dict[str, Any] | None, now: Any,
                     freshness_seconds: float = LIVE_PRICE_FRESHNESS_SECONDS) -> dict[str, Any]:
    if not quote:
        return unavailable_fields()
    try:
        observed = _utc(quote["timestamp"]);age = max(0.0, (_utc(now) - observed).total_seconds())
        price = float(quote["price"]);analysis = float(analysis_price)
        if price <= 0 or analysis <= 0: raise ValueError("prices must be positive")
    except (KeyError, TypeError, ValueError):
        return unavailable_fields()
    if age > freshness_seconds:
        fields = unavailable_fields("LIVE_PRICE_STALE")
        fields.update({"live_reference_timestamp": observed.isoformat(), "live_price_age_seconds": age})
        return fields
    return {"live_reference_price": price, "live_reference_timestamp": observed.isoformat(),
            "live_price_age_seconds": age, "price_drift_pct": (price / analysis - 1.0) * 100.0,
            "live_price_status": "LIVE_PRICE_AVAILABLE", "live_reference_semantics": LIVE_REFERENCE_SEMANTICS}

def attach_live_references(packet: dict[str, Any], fetcher=fetch_public_mid_prices, now: Any = None,
                           freshness_seconds: float = LIVE_PRICE_FRESHNESS_SECONDS) -> dict[str, Any]:
    """Attach display-only values after every deterministic research calculation."""
    observed_now = _utc(now);candidates = packet.get("candidates", [])
    pairs = [row.get("identity", {}).get("kraken_pair") for row in candidates]
    try: quotes = fetcher(pairs)
    except Exception: quotes = {}
    by_asset = {}
    for row in candidates:
        current = row.setdefault("current_data", {});pair = row.get("identity", {}).get("kraken_pair")
        fields = reference_fields(current.get("analysis_price"), quotes.get(pair), observed_now, freshness_seconds)
        current.update(fields);by_asset[str(row.get("asset"))] = fields
    for bucket in ("daily", "weekly", "avoid"):
        for row in packet.get("tactical_opportunities", {}).get(bucket, []):
            row.update(by_asset.get(str(row.get("asset")), unavailable_fields()))
    packet["live_price_policy"] = {"source": PUBLIC_TICKER_ENDPOINT,
        "authentication": "NONE_PUBLIC_MARKET_DATA_ONLY", "reference_semantics": LIVE_REFERENCE_SEMANTICS,
        "timestamp_semantics": "LOCAL_UTC_RESPONSE_RECEIPT_TIME", "freshness_threshold_seconds": freshness_seconds,
        "research_effect": "DISPLAY_ONLY_NO_RECOMPUTATION"}
    return packet
