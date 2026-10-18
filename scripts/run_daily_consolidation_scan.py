from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import pandas as pd

from consolidation_range_engine import BTC_OPERATIONAL_PATH, _read_operational_15m, completed_4h_bars, detect_range
from daily_consolidation_watchlist_monitor import simple_position_zone
from weekly_consolidation_common import (
    DEFAULTS, INTRADAY_DIR, LABELS, ROOT, UNIVERSE_DIR, WATCHLIST_DIR,
    atomic_write, opportunity_metrics, opportunity_score, risk_flags, sha256,
    freshness, utc_timestamp, validate_hourly, write_json,
)
from weekly_consolidation_scanner import flatten_scan, weekly_status
from weekly_consolidation_universe import refresh_universe
from weekly_intraday_market_backfill import backfill_universe

DAILY_REPORT_DIR = ROOT / "DAILY_REPORTS" / "DAILY_CONSOLIDATION"
CRITICAL_FLAGS = {"STALE_DATA", "LOW_LIQUIDITY", "WIDE_SPREAD", "DATA_GAPS", "CONFIRMED_BREAKOUT", "CONFIRMED_BREAKDOWN"}


def _git_commit() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def cached_universe_is_current(path: Path, cutoff: pd.Timestamp) -> bool:
    json_path = path.with_suffix(".json")
    if not path.exists() or not json_path.exists():
        return False
    try:
        generated = utc_timestamp(json.loads(json_path.read_text())["generated_at_utc"])
        return (cutoff - generated).total_seconds() <= 24 * 3600
    except Exception:
        return False


def prepare_market_data(as_of: Any = None, universe_size: int = 150, no_network: bool = False,
                        reuse_existing_data: bool = False, refresh_universe_cache: bool = False,
                        dry_run: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cutoff = utc_timestamp(as_of)
    universe_path = UNIVERSE_DIR / "weekly_consolidation_universe.csv"
    should_refresh = refresh_universe_cache or not cached_universe_is_current(universe_path, cutoff)
    if should_refresh and not (no_network or reuse_existing_data or dry_run):
        universe = refresh_universe(min(150, max(1, universe_size)), cutoff.isoformat())
    elif universe_path.exists():
        universe = pd.read_csv(universe_path).head(universe_size).to_dict("records")
    else:
        raise FileNotFoundError("cached universe unavailable; run without --no-network")
    if no_network or reuse_existing_data or dry_run:
        quality = cached_quality(universe, cutoff)
    else:
        quality = backfill_universe(cutoff, no_network=False)
    return universe, quality


def cached_quality(universe: list[dict[str, Any]], cutoff: Any) -> list[dict[str, Any]]:
    rows=[]
    for item in universe:
        if item.get("inclusion_status") != "INCLUDED": continue
        asset,pair=str(item["symbol"]),str(item["selected_kraken_pair"])
        try:
            if asset == "BTC":
                raw=_read_operational_15m(BTC_OPERATIONAL_PATH); age,status=freshness(raw.iloc[-1]["timestamp"],cutoff)
                count=len(raw); latest=pd.Timestamp(raw.iloc[-1]["timestamp"]).isoformat()
            else:
                clean,q=validate_hourly(pd.read_csv(INTRADAY_DIR/f"{pair}_1H.csv"),cutoff)
                age,status=q["freshness_age_hours"],q["freshness_status"]; count=len(clean); latest=clean.iloc[-1]["timestamp"].isoformat()
            rows.append({"asset":asset,"pair":pair,"freshness_age_hours":age,"freshness_status":status,"row_count":count,"latest_completed_candle_timestamp":latest,"usable_for_consolidation_scan":count>=DEFAULTS["min_1h_candles"] and status in {"FRESH","DELAYED"},"refresh_status":"REUSED_CACHE","source":"LOCAL_CACHE"})
        except Exception as exc:
            rows.append({"asset":asset,"pair":pair,"freshness_status":"UNAVAILABLE","usable_for_consolidation_scan":False,"refresh_status":"REFRESH_FAILED_STALE","error":str(exc)})
    return rows


def evaluate_universe(universe: list[dict[str, Any]], quality: list[dict[str, Any]], as_of: Any) -> list[dict[str, Any]]:
    cutoff = utc_timestamp(as_of)
    quality_map = {str(row.get("asset")): row for row in quality}
    rows: list[dict[str, Any]] = []
    for item in universe:
        if item.get("inclusion_status") != "INCLUDED":
            continue
        asset, pair = str(item["symbol"]), str(item["selected_kraken_pair"])
        q = quality_map.get(asset, {})
        try:
            if asset == "BTC":
                raw = _read_operational_15m(BTC_OPERATIONAL_PATH)
                bars = completed_4h_bars(raw, cutoff, "15m")
                latest_1h = bars.iloc[-1]["timestamp"]
                native_rows = len(raw)
            else:
                clean, local_quality = validate_hourly(pd.read_csv(INTRADAY_DIR / f"{pair}_1H.csv"), cutoff)
                bars = completed_4h_bars(clean, cutoff, "1H")
                latest_1h = clean.iloc[-1]["timestamp"]
                native_rows = len(clean)
                q = {**local_quality, **q}
            row = detect_range(bars, asset)
            row.update({
                "kraken_pair": pair, "market_cap_rank": item.get("market_cap_rank"),
                "kraken_24h_quote_volume": float(item.get("kraken_24h_quote_volume") or 0),
                "bid_ask_spread_pct": item.get("bid_ask_spread_pct"),
                "liquidity_pass": bool(item.get("liquidity_pass", False)),
                "spread_pass": bool(item.get("spread_pass", False)),
                "mapping_uncertain": bool(item.get("mapping_uncertain", False)),
                "freshness_status": q.get("freshness_status", "UNAVAILABLE"),
                "freshness_age_hours": q.get("freshness_age_hours"),
                "latest_completed_candle_timestamp": pd.Timestamp(latest_1h).isoformat(),
                "retrieval_timestamp": cutoff.isoformat(),
                "refresh_status": q.get("refresh_status", "REFRESH_SUCCEEDED"),
                "api_failure_reason": q.get("error"), "native_intraday_rows": native_rows,
                "sufficient_native_intraday_history": native_rows >= DEFAULTS["min_1h_candles"],
                "data_quality_status": "OK" if q.get("usable_for_consolidation_scan", q.get("freshness_status") in {"FRESH", "DELAYED"}) else "DATA_INCONSISTENT",
            })
            row.update(opportunity_metrics(row))
            row["risk_flags"] = risk_flags(row, row["liquidity_pass"], row["spread_pass"])
            score, components = opportunity_score(row)
            row["daily_range_opportunity_score"] = score
            row["daily_score_components"] = components
            row["weekly_range_opportunity_score"] = score
            row["weekly_score_components"] = components
            row["daily_status"] = weekly_status(row)
            row["range_still_valid"] = bool(row.get("range_valid", row.get("is_valid_horizontal_consolidation"))) and row.get("status") not in {"BELOW_RANGE_PENDING_RECOVERY", "RANGE_INVALIDATED", "BREAKOUT_CONFIRMED", "BREAKDOWN_CONFIRMED", "DATA_INCONSISTENT"}
            row.update(simple_position_zone(row.get("position_pct"), row["freshness_status"], row["range_still_valid"], bool(row.get("confirmed_breakdowns", 0))))
            rows.append(row)
        except Exception:
            continue
    return rank_daily(rows)


def rank_daily(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(row: dict[str, Any]):
        position = float(row.get("position_pct", 999))
        lower = 0 <= position <= 30
        cycle = row.get("average_full_cycle_hours")
        breakout_risk = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}.get(str(row.get("breakout_risk")).upper(), 3)
        return (
            not bool(row.get("range_still_valid")), not lower,
            -float(row.get("estimated_net_range_return_pct", 0)),
            float(cycle) if cycle is not None else float("inf"),
            -float(row.get("range_quality", 0)), -float(row.get("kraken_24h_quote_volume", 0)),
            breakout_risk, float(row.get("freshness_age_hours") or 0), str(row.get("asset")),
        )
    ordered = sorted(rows, key=key)
    for rank, row in enumerate(ordered, 1):
        row["daily_rank"] = rank
    return ordered


def eligible(row: dict[str, Any]) -> bool:
    traversals = int(row["low_to_high"]["count"]) + int(row["high_to_low"]["count"])
    flags = set(row.get("risk_flags", []))
    return (
        row.get("freshness_status") == "FRESH" and bool(row.get("range_still_valid"))
        and bool(row.get("is_valid_horizontal_consolidation"))
        and row.get("data_quality_status") == "OK"
        and not row.get("confirmed_breakouts", 0) and not row.get("confirmed_breakdowns", 0)
        and not (flags & CRITICAL_FLAGS) and bool(row.get("liquidity_pass"))
        and float(row.get("range_quality", 0)) >= 60
        and float(row.get("estimated_net_range_return_pct", 0)) >= 1.5
        and int(row.get("lower_boundary_tests", 0)) >= 2
        and int(row.get("upper_boundary_tests", 0)) >= 2 and traversals >= 2
        and bool(row.get("sufficient_native_intraday_history"))
    )


def select_daily(rows: list[dict[str, Any]], size: int = 4) -> list[dict[str, Any]]:
    return [row for row in rows if eligible(row)][:max(1, min(4, size))]


def _watch_row(row: dict[str, Any], date_text: str) -> dict[str, Any]:
    friction = float(row.get("estimated_total_friction_pct", .6))
    price = float(row["latest_available_market_price"])
    return {
        **flatten_scan(row), "daily_selection_date": date_text, "rank": row["daily_rank"],
        "current_price": price, "average_cycle_hours": row.get("average_full_cycle_hours"),
        "cycles_per_30d": row.get("estimated_cycles_per_30d"),
        "opportunity_score": row["daily_range_opportunity_score"],
        "estimated_net_movement_to_midpoint_pct": (float(row["midpoint"]) / price - 1) * 100 - friction,
        "estimated_net_movement_to_high_pct": (float(row["range_high"]) / price - 1) * 100 - friction,
        "risk_flags": "|".join(row.get("risk_flags", [])),
    }


def write_outputs(rows: list[dict[str, Any]], selected: list[dict[str, Any]], cutoff: pd.Timestamp) -> None:
    date_text = cutoff.strftime("%Y-%m-%d")
    DAILY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    base = DAILY_REPORT_DIR / f"{date_text}_daily_consolidation_scan"
    flat = pd.DataFrame([flatten_scan(row) for row in rows])
    atomic_write(base.with_suffix(".csv"), flat.to_csv(index=False))
    write_json(base.with_suffix(".json"), {"generated_at_utc": cutoff.isoformat(), "labels": LABELS, "candidates": rows})
    lines = ["# Daily Consolidation Scan", "", *LABELS, "", "## Top Daily Candidates", ""]
    lines += [f"- #{r['daily_rank']} {r['asset']} | {r['simple_color']} {r['simple_zone']} | score {r['daily_range_opportunity_score']:.2f} | quality {r['range_quality']:.2f}" for r in selected] or ["- None"]
    atomic_write(base.with_suffix(".md"), "\n".join(lines) + "\n")
    for ext in (".csv", ".json", ".md"):
        atomic_write(DAILY_REPORT_DIR / f"latest_daily_consolidation_scan{ext}", base.with_suffix(ext).read_text(), backup=False)
    watch = [_watch_row(row, date_text) for row in selected]
    frame = pd.DataFrame(watch)
    atomic_write(WATCHLIST_DIR / "consolidation_daily_watchlist.csv", frame.to_csv(index=False))
    write_json(WATCHLIST_DIR / "consolidation_daily_watchlist.json", {"generated_at_utc": cutoff.isoformat(), "labels": LABELS, "watchlist": watch})
    atomic_write(WATCHLIST_DIR / "consolidation_daily_watchlist.md", "# Daily Consolidation Watchlist\n\n" + "\n".join(f"- #{r['rank']} {r['asset']} | {r['simple_color']} {r['simple_zone']}" for r in watch) + "\n")


def run(as_of: Any = None, universe_size: int = 150, selection_size: int = 4,
        no_network: bool = False, reuse_existing_data: bool = False,
        refresh_universe_cache: bool = False, dry_run: bool = False,
        prepared: tuple[list[dict[str, Any]], list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    cutoff = utc_timestamp(as_of)
    universe, quality = prepared or prepare_market_data(cutoff, universe_size, no_network, reuse_existing_data, refresh_universe_cache, dry_run)
    rows = evaluate_universe(universe, quality, cutoff)
    selected = select_daily(rows, selection_size)
    if not dry_run:
        write_outputs(rows, selected, cutoff)
    manifest = {
        "generated_at_utc": cutoff.isoformat(), "git_commit": _git_commit(),
        "universe_size_requested": universe_size, "universe_size_returned": len(universe),
        "kraken_mapped_assets": sum(r.get("inclusion_status") == "INCLUDED" for r in universe),
        "fresh_data_assets": sum(r.get("freshness_status") == "FRESH" for r in quality),
        "candidates_evaluated": len(rows), "watchlist_assets": [r["asset"] for r in selected],
        "execution_duration_seconds": time.perf_counter() - started,
        "input_hashes": {str(p): sha256(p) for p in INTRADAY_DIR.glob("*_1H.csv")},
        "checkpoint_resume": bool(reuse_existing_data or no_network or dry_run),
    }
    if not dry_run:
        write_json(DAILY_REPORT_DIR / f"{cutoff:%Y-%m-%d}_daily_consolidation_manifest.json", manifest)
    return {**manifest, "rows": rows, "selected": selected, "universe": universe, "quality": quality}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of"); parser.add_argument("--universe-size", type=int, default=150)
    parser.add_argument("--selection-size", type=int, default=4); parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--reuse-existing-data", action="store_true"); parser.add_argument("--refresh-universe", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run(args.as_of, args.universe_size, args.selection_size, args.no_network, args.reuse_existing_data, args.refresh_universe, args.dry_run)
    print(f"Daily consolidation scan complete | universe {result['universe_size_returned']} | mapped {result['kraken_mapped_assets']} | candidates {result['candidates_evaluated']} | watchlist {len(result['watchlist_assets'])}")


if __name__ == "__main__":
    main()
