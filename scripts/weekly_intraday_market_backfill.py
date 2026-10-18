from __future__ import annotations

import argparse
import io
from pathlib import Path
from typing import Any

import pandas as pd

from consolidation_range_engine import BTC_OPERATIONAL_PATH, completed_4h_bars, _read_operational_15m
from weekly_consolidation_common import (
    CHECKPOINT_DIR, DEFAULTS, INTRADAY_DIR, UNIVERSE_DIR, WEEKLY_REPORT_DIR,
    atomic_write, get_json, utc_timestamp, validate_hourly, write_json,
    freshness,
)

KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"


def parse_kraken_ohlc(payload: Any) -> pd.DataFrame:
    if not isinstance(payload, dict) or payload.get("error") or not isinstance(payload.get("result"), dict):
        raise ValueError("malformed Kraken OHLC response")
    keys = [k for k in payload["result"] if k != "last"]
    if len(keys) != 1 or not isinstance(payload["result"][keys[0]], list):
        raise ValueError("malformed Kraken OHLC rows")
    rows = payload["result"][keys[0]]
    frame = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "vwap", "volume", "trades"])
    frame["timestamp"] = pd.to_datetime(pd.to_numeric(frame["timestamp"], errors="coerce"), unit="s", utc=True)
    return frame


def merge_incremental(existing: pd.DataFrame, incoming: pd.DataFrame, as_of: Any) -> tuple[pd.DataFrame, dict[str, Any]]:
    if incoming.empty:
        combined = existing.copy()
    elif existing.empty:
        combined = incoming.copy()
    else:
        combined = pd.concat([existing, incoming], ignore_index=True)
    clean, quality = validate_hourly(combined, as_of)
    if clean.empty or quality["ohlc_anomalies"] or quality["negative_volume_rows"]:
        raise ValueError("FAIL_SAFE_NO_OVERWRITE: downloaded OHLC failed validation")
    return clean, quality


def update_pair(pair: str, as_of: Any, no_network: bool = False) -> tuple[pd.DataFrame, dict[str, Any]]:
    path = INTRADAY_DIR / f"{pair}_1H.csv"
    existing = pd.read_csv(path) if path.exists() else pd.DataFrame()
    since = None
    if not existing.empty:
        since = int(utc_timestamp(existing.iloc[-1]["timestamp"]).timestamp())
    if no_network:
        if existing.empty: raise FileNotFoundError(f"no cached intraday data for {pair}")
        incoming = pd.DataFrame(columns=existing.columns)
    else:
        payload = get_json(KRAKEN_OHLC_URL, {"pair": pair, "interval": 60, **({"since": since} if since else {})})
        incoming = parse_kraken_ohlc(payload)
    clean, quality = merge_incremental(existing, incoming, as_of)
    atomic_write(path, clean.to_csv(index=False, date_format="%Y-%m-%dT%H:%M:%SZ"))
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(CHECKPOINT_DIR / f"{pair}.json", {"pair": pair, "last_completed_timestamp": clean.iloc[-1]["timestamp"].isoformat(), "rows": len(clean)})
    return clean, quality


def quality_row(asset: str, pair: str, path: Path, source: str, timeframe: str, raw: pd.DataFrame, quality: dict[str, Any], as_of: Any) -> dict[str, Any]:
    derived = completed_4h_bars(raw, as_of, source_timeframe=timeframe)
    raw_buckets = pd.to_datetime(raw["timestamp"], utc=True).dt.floor("4h").nunique()
    return {"asset": asset, "source_path": str(path), "source": source, "pair": pair,
            "source_timeframe": timeframe, "first_timestamp": raw.iloc[0]["timestamp"].isoformat() if len(raw) else None,
            "last_timestamp": raw.iloc[-1]["timestamp"].isoformat() if len(raw) else None, "row_count": len(raw),
            **quality, "derived_complete_4h_bars": len(derived),
            "incomplete_4h_buckets_rejected": max(0, int(raw_buckets) - len(derived)),
            "usable_for_consolidation_scan": (len(raw) >= DEFAULTS["min_1h_candles"] if timeframe == "1H" else len(derived) >= 44) and quality["freshness_status"] in {"FRESH", "DELAYED"}}


def write_quality(rows: list[dict[str, Any]], date_text: str) -> None:
    WEEKLY_REPORT_DIR.mkdir(parents=True, exist_ok=True); base = WEEKLY_REPORT_DIR / f"{date_text}_intraday_quality"
    atomic_write(base.with_suffix(".csv"), pd.DataFrame(rows).to_csv(index=False)); write_json(base.with_suffix(".json"), {"assets": rows})
    lines = ["# Weekly Intraday Quality", ""] + [f"- {r['asset']} | {r['freshness_status']} | rows {r['row_count']} | 4H {r['derived_complete_4h_bars']} | usable {r['usable_for_consolidation_scan']}" for r in rows]
    atomic_write(base.with_suffix(".md"), "\n".join(lines) + "\n")


def backfill_universe(as_of: Any = None, no_network: bool = False) -> list[dict[str, Any]]:
    cutoff = utc_timestamp(as_of); universe_path = UNIVERSE_DIR / "weekly_consolidation_universe.csv"
    if not universe_path.exists(): raise FileNotFoundError("weekly universe unavailable")
    universe = pd.read_csv(universe_path); rows = []
    for _, item in universe[universe["inclusion_status"] == "INCLUDED"].iterrows():
        asset, pair = str(item["symbol"]), str(item["selected_kraken_pair"])
        try:
            if asset == "BTC":
                raw = _read_operational_15m(BTC_OPERATIONAL_PATH); clean = raw.copy()
                btc_age, btc_freshness = freshness(raw.iloc[-1]["timestamp"], cutoff)
                quality = {"duplicate_count": int(raw["timestamp"].duplicated().sum()), "missing_expected_1h_bars": None, "longest_gap_hours": None, "incomplete_bars_rejected": 0, "ohlc_anomalies": 0, "negative_volume_rows": int((raw["volume"] < 0).sum()), "freshness_age_hours": btc_age, "freshness_status": btc_freshness}
                rows.append(quality_row(asset, pair, BTC_OPERATIONAL_PATH, "BTC_OPERATIONAL_READ_ONLY", "15m", clean, quality, cutoff))
            else:
                clean, quality = update_pair(pair, cutoff, no_network=no_network)
                rows.append(quality_row(asset, pair, INTRADAY_DIR / f"{pair}_1H.csv", "KRAKEN_PUBLIC_OHLC", "1H", clean, quality, cutoff))
        except Exception as exc:
            rows.append({"asset": asset, "pair": pair, "source_path": str(INTRADAY_DIR / f"{pair}_1H.csv"), "source": "KRAKEN_PUBLIC_OHLC", "source_timeframe": "1H", "row_count": 0, "derived_complete_4h_bars": 0, "freshness_status": "UNAVAILABLE", "usable_for_consolidation_scan": False, "error": str(exc)})
    write_quality(rows, cutoff.strftime("%Y-%m-%d")); return rows


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--as-of"); parser.add_argument("--no-network", action="store_true")
    args=parser.parse_args(); rows=backfill_universe(args.as_of, args.no_network); print(f"Quality rows: {len(rows)}; usable: {sum(bool(r.get('usable_for_consolidation_scan')) for r in rows)}")


if __name__ == "__main__": main()
