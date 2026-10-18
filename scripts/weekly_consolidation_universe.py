from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from weekly_consolidation_common import (
    DEFAULTS, QUOTE_ORDER, UNIVERSE_DIR, WEEKLY_REPORT_DIR, atomic_write,
    exclusion_reason, get_json, normalize_symbol, utc_timestamp, write_json,
)

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
KRAKEN_PAIRS_URL = "https://api.kraken.com/0/public/AssetPairs"
KRAKEN_TICKER_URL = "https://api.kraken.com/0/public/Ticker"


def parse_coingecko(payload: Any, limit: int) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("malformed CoinGecko response: expected list")
    required = {"id", "symbol", "name", "market_cap_rank"}
    rows = [coin for coin in payload if isinstance(coin, dict) and required.issubset(coin)]
    return sorted(rows, key=lambda c: (c.get("market_cap_rank") or 10**9, c["id"]))[:limit]


def parse_kraken_pairs(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or payload.get("error") or not isinstance(payload.get("result"), dict):
        raise ValueError("malformed Kraken AssetPairs response")
    rows = []
    for pair_id, info in payload["result"].items():
        wsname = str(info.get("wsname", ""))
        if "/" not in wsname:
            continue
        base, quote = wsname.split("/", 1)
        rows.append({"pair_id": pair_id, "altname": info.get("altname", pair_id),
                     "base": normalize_symbol(base), "quote": normalize_symbol(quote),
                     "status": info.get("status", "online")})
    return rows


def map_pair(symbol: str, pairs: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = [p for p in pairs if p["base"] == normalize_symbol(symbol) and p["quote"] in QUOTE_ORDER and p["status"] in {"online", "active"}]
    return min(matches, key=lambda p: (QUOTE_ORDER[p["quote"]], p["pair_id"])) if matches else None


def build_universe(coins: list[dict[str, Any]], pairs: list[dict[str, Any]], tickers: dict[str, Any], generated_at: str) -> list[dict[str, Any]]:
    rows = []
    for coin in coins:
        reason = exclusion_reason(coin)
        pair = None if reason else map_pair(coin["symbol"], pairs)
        if not reason and pair is None:
            reason = "NO_ACTIVE_KRAKEN_SPOT_PAIR"
        ticker = (tickers.get(pair["pair_id"]) or tickers.get(pair["altname"]) or {}) if pair else {}
        last = float(ticker.get("c", [0])[0] or 0) if ticker else 0
        base_volume = float(ticker.get("v", [0, 0])[1] or 0) if ticker else 0
        quote_volume = last * base_volume
        ask = float(ticker.get("a", [0])[0] or 0) if ticker else 0
        bid = float(ticker.get("b", [0])[0] or 0) if ticker else 0
        spread = ((ask - bid) / ((ask + bid) / 2) * 100) if ask > 0 and bid > 0 else None
        liquidity_pass = quote_volume >= DEFAULTS["min_quote_volume"]
        spread_pass = spread is None or spread <= DEFAULTS["max_spread_pct"]
        ticker_available = bool(ticker)
        if not reason and not ticker_available: reason = "TICKER_UNAVAILABLE"
        if not reason and not liquidity_pass: reason = "INSUFFICIENT_KRAKEN_LIQUIDITY"
        if not reason and not spread_pass: reason = "EXCESSIVE_BID_ASK_SPREAD"
        rows.append({
            "coingecko_id": coin["id"], "symbol": str(coin["symbol"]).upper(), "name": coin["name"],
            "market_cap_rank": coin.get("market_cap_rank"), "market_cap": coin.get("market_cap"),
            "coingecko_24h_volume": coin.get("total_volume"), "selected_kraken_pair": pair["altname"] if pair else None,
            "kraken_pair_id": pair["pair_id"] if pair else None, "kraken_base_asset": pair["base"] if pair else None,
            "kraken_quote_asset": pair["quote"] if pair else None, "kraken_pair_status": pair["status"] if pair else None,
            "kraken_24h_quote_volume": quote_volume if ticker_available else None, "bid_ask_spread_pct": spread,
            "volume_comparability": "UNCERTAIN_NO_USD_CONVERSION" if pair and pair["quote"] == "EUR" else "USD_OR_USDT_QUOTE",
            "mapping_uncertain": bool(pair and pair["quote"] == "EUR"),
            "liquidity_pass": liquidity_pass, "spread_pass": spread_pass,
            "inclusion_status": "INCLUDED" if reason is None else "EXCLUDED", "exclusion_reason": reason,
            "coingecko_source_timestamp": generated_at, "kraken_source_timestamp": generated_at,
        })
    return rows


def write_universe(rows: list[dict[str, Any]], date_text: str, generated_at: str) -> list[Path]:
    UNIVERSE_DIR.mkdir(parents=True, exist_ok=True); WEEKLY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    csv_text = frame.to_csv(index=False)
    atomic_write(UNIVERSE_DIR / "weekly_consolidation_universe.csv", csv_text)
    write_json(UNIVERSE_DIR / "weekly_consolidation_universe.json", {"generated_at_utc": generated_at, "assets": rows})
    base = WEEKLY_REPORT_DIR / f"{date_text}_universe_report"
    atomic_write(base.with_suffix(".csv"), csv_text)
    write_json(base.with_suffix(".json"), {"generated_at_utc": generated_at, "assets": rows})
    included = [r for r in rows if r["inclusion_status"] == "INCLUDED"]
    lines = ["# Weekly Consolidation Universe", "", f"Generated: {generated_at}", f"Requested/returned: {len(rows)}", f"Included: {len(included)}", "", "## Included", ""]
    lines += [f"- {r['symbol']} | {r['selected_kraken_pair']} | rank {r['market_cap_rank']} | quote volume {r['kraken_24h_quote_volume']:.2f}" for r in included]
    lines += ["", "## Excluded", ""] + [f"- {r['symbol']}: {r['exclusion_reason']}" for r in rows if r["inclusion_status"] == "EXCLUDED"]
    atomic_write(base.with_suffix(".md"), "\n".join(lines) + "\n")
    return [base.with_suffix(ext) for ext in (".csv", ".json", ".md")]


def refresh_universe(size: int = 150, as_of: str | None = None) -> list[dict[str, Any]]:
    generated = utc_timestamp(as_of).isoformat()
    coins = parse_coingecko(get_json(COINGECKO_URL, {"vs_currency": "usd", "order": "market_cap_desc", "per_page": size, "page": 1, "sparkline": "false"}), size)
    pairs = parse_kraken_pairs(get_json(KRAKEN_PAIRS_URL))
    pair_ids = sorted({mapped["pair_id"] for coin in coins if exclusion_reason(coin) is None
                       for mapped in [map_pair(coin["symbol"], pairs)] if mapped is not None})
    ticker_payload = get_json(KRAKEN_TICKER_URL, {"pair": ",".join(pair_ids)})
    if ticker_payload.get("error") or not isinstance(ticker_payload.get("result"), dict):
        raise ValueError("malformed Kraken Ticker response")
    rows = build_universe(coins, pairs, ticker_payload["result"], generated)
    write_universe(rows, generated[:10], generated)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--universe-size", type=int, default=150); parser.add_argument("--as-of")
    args = parser.parse_args(); rows = refresh_universe(min(150, max(1, args.universe_size)), args.as_of)
    print(f"Universe assets: {len(rows)}; included: {sum(r['inclusion_status'] == 'INCLUDED' for r in rows)}")


if __name__ == "__main__": main()
