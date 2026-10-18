from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd

from consolidation_range_engine import MIN_WINDOW, completed_4h_bars
from range_fixed_5_v2_clock import ClockSafetyGuard
from range_fixed_5_v2_universe_scanner import (
    INTRADAY_DIR, discover_public_universe, load_local_ohlcv, run_scan,
)
from weekly_consolidation_common import atomic_write, get_json
from weekly_intraday_market_backfill import KRAKEN_OHLC_URL, parse_kraken_ohlc


MIN_COMPLETED_4H_BARS = MIN_WINDOW + 14
MIN_THEORETICAL_1H_ROWS = MIN_COMPLETED_4H_BARS * 4
FRESH_HOURS = 8.0
MAX_BACKFILL_REQUESTS = 10
REPORT_VERSION = "RANGE_FIXED_5_V2_DATA_COVERAGE_1.0.0"


def utc(value: Any = None) -> pd.Timestamp:
    return pd.to_datetime(pd.Timestamp.now(tz="UTC") if value is None else value, utc=True)


def _empty_metrics(asset: str, pair: str, path: Path, cause: str, requirement: str) -> dict[str, Any]:
    return {
        "asset": asset, "pair": pair, "status": "NOT_ELIGIBLE_DATA_INCOMPLETE",
        "source_path": str(path), "source_timeframe": "1H", "first_timestamp": None,
        "last_timestamp": None, "rows": 0, "expected_minimum_1h_rows": MIN_THEORETICAL_1H_ROWS,
        "expected_minimum_completed_4h_bars": MIN_COMPLETED_4H_BARS, "usable_completed_4h_bars": 0,
        "exact_missing_requirement": requirement, "latest_completed_candle": None,
        "data_age_hours": None, "missing_expected_1h_bars": None, "recent_gap_hours": None,
        "duplicate_timestamps": 0, "malformed_rows": 0, "non_monotonic_timestamps": False,
        "root_cause": cause,
    }


def diagnose_dataset(asset: str, pair: str, cutoff: Any, directory: Path = INTRADAY_DIR) -> dict[str, Any]:
    path = directory / f"{pair}_1H.csv"
    if not path.exists():
        return _empty_metrics(asset, pair, path, "NO_LOCAL_DATA", "local hourly OHLCV dataset is absent")
    try:
        raw = pd.read_csv(path)
    except Exception as exc:
        return _empty_metrics(asset, pair, path, "INVALID_ROWS", f"CSV unreadable: {exc}")
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if not required.issubset(raw.columns):
        return _empty_metrics(asset, pair, path, "TIMEFRAME_PROBLEM",
                              f"missing required columns: {sorted(required - set(raw.columns))}")
    timestamps = pd.to_datetime(raw["timestamp"], utc=True, errors="coerce")
    numeric = raw[["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce")
    malformed = timestamps.isna() | numeric.isna().any(axis=1)
    malformed |= (numeric[["open", "high", "low", "close"]] <= 0).any(axis=1) | (numeric["volume"] < 0)
    malformed |= numeric["high"] < numeric[["open", "close", "low"]].max(axis=1)
    malformed |= numeric["low"] > numeric[["open", "close", "high"]].min(axis=1)
    valid = raw.loc[~malformed].copy()
    valid["timestamp"] = timestamps.loc[~malformed]
    for column in ("open", "high", "low", "close", "volume"):
        valid[column] = numeric.loc[~malformed, column]
    non_monotonic = not timestamps.dropna().is_monotonic_increasing
    duplicates = int(valid["timestamp"].duplicated().sum())
    valid = valid.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    completed_source = valid[valid["timestamp"] + pd.Timedelta(hours=1) <= utc(cutoff)]
    diffs = completed_source["timestamp"].diff().dropna().dt.total_seconds().div(3600)
    missing_hours = int(sum(max(0, round(gap) - 1) for gap in diffs))
    recent_gap = float(diffs.iloc[-1] - 1) if len(diffs) and diffs.iloc[-1] > 1 else 0.0
    derived = completed_4h_bars(completed_source, cutoff, "1H")
    latest_open = None if derived.empty else utc(derived.iloc[-1]["timestamp"])
    latest_completion = None if latest_open is None else latest_open + pd.Timedelta(hours=4)
    age = None if latest_completion is None else max(0.0, (utc(cutoff) - latest_completion).total_seconds() / 3600)
    requirements = []
    causes = []
    if int(malformed.sum()):
        requirements.append(f"remove or replace {int(malformed.sum())} invalid OHLCV rows")
        causes.append("INVALID_ROWS")
    if duplicates:
        requirements.append(f"deduplicate {duplicates} timestamps")
        causes.append("DUPLICATE_TIMESTAMPS")
    if non_monotonic:
        requirements.append("sort timestamps chronologically")
        causes.append("OTHER")
    if len(derived) < MIN_COMPLETED_4H_BARS:
        requirements.append(f"need {MIN_COMPLETED_4H_BARS} completed 4H bars; have {len(derived)}")
        causes.append("INSUFFICIENT_HISTORY")
    if age is None or age > FRESH_HOURS:
        requirements.append(f"latest completed 4H candle must be no older than {FRESH_HOURS}h")
        causes.append("STALE_HISTORY")
    if missing_hours:
        requirements.append(f"{missing_hours} hourly observations absent inside local coverage")
        causes.append("RECENT_GAP" if recent_gap else "INTERNAL_GAPS")
    priority = ("NO_LOCAL_DATA", "TIMEFRAME_PROBLEM", "INVALID_ROWS", "DUPLICATE_TIMESTAMPS",
                "INSUFFICIENT_HISTORY", "STALE_HISTORY", "RECENT_GAP", "INTERNAL_GAPS", "OTHER")
    root = next((value for value in priority if value in causes), "OTHER")
    return {
        "asset": asset, "pair": pair, "status": "DATASET_VALID" if not requirements else "DATASET_DEFICIENT",
        "source_path": str(path), "source_timeframe": "1H",
        "first_timestamp": None if completed_source.empty else utc(completed_source.iloc[0]["timestamp"]).isoformat(),
        "last_timestamp": None if completed_source.empty else utc(completed_source.iloc[-1]["timestamp"]).isoformat(),
        "rows": int(len(raw)), "valid_completed_1h_rows": int(len(completed_source)),
        "expected_minimum_1h_rows": MIN_THEORETICAL_1H_ROWS,
        "expected_minimum_completed_4h_bars": MIN_COMPLETED_4H_BARS,
        "usable_completed_4h_bars": int(len(derived)),
        "exact_missing_requirement": "; ".join(requirements) if requirements else "NONE",
        "latest_completed_candle": None if latest_completion is None else latest_completion.isoformat(),
        "data_age_hours": age, "missing_expected_1h_bars": missing_hours,
        "recent_gap_hours": recent_gap, "duplicate_timestamps": duplicates,
        "malformed_rows": int(malformed.sum()), "non_monotonic_timestamps": non_monotonic,
        "root_cause": root,
    }


def audit_incomplete(scan: dict[str, Any], cutoff: Any, directory: Path = INTRADAY_DIR) -> list[dict[str, Any]]:
    rows = []
    for decision in scan.get("snapshots", []):
        if decision.get("eligibility_status") != "NOT_ELIGIBLE_DATA_INCOMPLETE":
            continue
        diagnostic = diagnose_dataset(decision["asset"], decision["pair"], cutoff, directory)
        missing_features = [name for name in (
            "reference_close", "atr14", "range_low", "range_high", "range_position_pct",
            "rqi_score", "rqi_classification", "freshness_status",
        ) if decision.get(name) is None]
        diagnostic["missing_v2_features"] = missing_features
        diagnostic["v2_data_quality_error"] = decision.get("data_quality_error") or decision.get("preview_data_error")
        if diagnostic["status"] == "DATASET_VALID":
            diagnostic["status"] = "NON_DATA_FEATURE_INCOMPLETE"
            diagnostic["root_cause"] = "OTHER"
            diagnostic["exact_missing_requirement"] = (
                "dataset satisfies coverage; V2 feature is not applicable: " + ", ".join(missing_features)
            )
        rows.append(diagnostic)
    return sorted(rows, key=lambda row: row["asset"])


def _clean_ohlcv(frame: pd.DataFrame, cutoff: Any) -> pd.DataFrame:
    required = ["timestamp", "open", "high", "low", "close", "volume"]
    if not set(required).issubset(frame.columns):
        return pd.DataFrame(columns=list(frame.columns) or required)
    work = frame.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], utc=True, errors="coerce")
    for column in ("open", "high", "low", "close", "volume", "vwap", "trades"):
        if column in work:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    valid = work[required].notna().all(axis=1)
    valid &= (work[["open", "high", "low", "close"]] > 0).all(axis=1) & (work["volume"] >= 0)
    valid &= work["high"] >= work[["open", "close", "low"]].max(axis=1)
    valid &= work["low"] <= work[["open", "close", "high"]].min(axis=1)
    valid &= work["timestamp"] + pd.Timedelta(hours=1) <= utc(cutoff)
    return work.loc[valid].sort_values("timestamp").drop_duplicates("timestamp", keep="last").reset_index(drop=True)


def backfill_pair(
    pair: str, cutoff: Any, directory: Path = INTRADAY_DIR,
    getter: Callable[..., Any] = get_json, max_requests: int = MAX_BACKFILL_REQUESTS,
) -> dict[str, Any]:
    path = directory / f"{pair}_1H.csv"
    existing = pd.read_csv(path) if path.exists() else pd.DataFrame()
    clean = _clean_ohlcv(existing, cutoff)
    before_rows = len(clean)
    since = None if clean.empty else int(utc(clean.iloc[-1]["timestamp"]).timestamp())
    requests = 0
    last_seen = None
    error = None
    for _ in range(max_requests):
        requests += 1
        try:
            payload = getter(KRAKEN_OHLC_URL, {"pair": pair, "interval": 60, **({"since": since} if since is not None else {})})
            incoming = parse_kraken_ohlc(payload)
        except Exception as exc:
            error = str(exc)
            break
        combined = incoming.copy() if clean.empty else pd.concat([clean, incoming], ignore_index=True)
        merged = _clean_ohlcv(combined, cutoff)
        newest = None if merged.empty else int(utc(merged.iloc[-1]["timestamp"]).timestamp())
        clean = merged
        response_last = payload.get("result", {}).get("last")
        next_since = int(response_last) if response_last is not None else newest
        if newest is None or newest == last_seen or next_since is None or (since is not None and next_since <= since):
            break
        last_seen, since = newest, next_since
        if utc(clean.iloc[-1]["timestamp"]) + pd.Timedelta(hours=1) >= utc(cutoff).floor("1h"):
            break
    if clean.empty:
        return {"pair": pair, "status": "UNRECOVERABLE", "requests": requests,
                "before_rows": before_rows, "after_rows": 0, "error": error or "no valid public OHLCV"}
    directory.mkdir(parents=True, exist_ok=True)
    columns = [column for column in ("timestamp", "open", "high", "low", "close", "vwap", "volume", "trades") if column in clean]
    atomic_write(path, clean[columns].to_csv(index=False, date_format="%Y-%m-%dT%H:%M:%SZ"))
    return {"pair": pair, "status": "BACKFILLED", "requests": requests,
            "before_rows": before_rows, "after_rows": len(clean), "error": error}


def coverage_summary(scan: dict[str, Any], diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = int(scan["eligible_kraken_pairs"])
    v2_incomplete = int(sum(row.get("eligibility_status") == "NOT_ELIGIBLE_DATA_INCOMPLETE" for row in scan["snapshots"]))
    data_deficient = sum(row.get("status") != "NON_DATA_FEATURE_INCOMPLETE" for row in diagnostics)
    analyzable = pairs - data_deficient
    pct = 0.0 if not pairs else analyzable / pairs * 100
    gate = "GREEN" if pct >= 90 else "YELLOW" if pct >= 80 else "RED"
    roots = Counter(row["root_cause"] for row in diagnostics)
    return {
        "evaluated_kraken_pairs": pairs, "fully_analyzable_assets": analyzable,
        "incomplete_assets": data_deficient, "v2_data_incomplete_status_count": v2_incomplete,
        "non_data_feature_incomplete_count": v2_incomplete - data_deficient,
        "coverage_pct": round(pct, 2), "gate": gate,
        "stale_assets": roots["STALE_HISTORY"],
        "assets_with_internal_gaps": roots["INTERNAL_GAPS"] + roots["RECENT_GAP"],
        "assets_with_insufficient_lookback": roots["INSUFFICIENT_HISTORY"],
        "assets_with_no_local_dataset": roots["NO_LOCAL_DATA"],
        "root_causes": dict(sorted(roots.items())),
        "eligible_preview_count": int(scan["eligible_opportunities"]),
        "rejection_distribution": scan["rejection_reason_distribution"],
    }


def render_report(report: dict[str, Any]) -> str:
    before, after = report["before"]["summary"], report["after"]["summary"]
    lines = ["# RANGE_FIXED_5_FORWARD_V2 — PRE-ACTIVATION DATA COVERAGE GATE", "",
             f"Generated: {report['generated_at_utc']}", "", "## Before/after", "",
             "| Metric | Before | After |", "|---|---:|---:|",
             f"| Evaluated pairs | {before['evaluated_kraken_pairs']} | {after['evaluated_kraken_pairs']} |",
             f"| Fully analyzable | {before['fully_analyzable_assets']} | {after['fully_analyzable_assets']} |",
             f"| True data deficient | {before['incomplete_assets']} | {after['incomplete_assets']} |",
             f"| V2 DATA_INCOMPLETE label | {before['v2_data_incomplete_status_count']} | {after['v2_data_incomplete_status_count']} |",
             f"| Coverage | {before['coverage_pct']}% | {after['coverage_pct']}% |",
             f"| Eligible previews | {before['eligible_preview_count']} | {after['eligible_preview_count']} |",
             "", "## Pre-repair incomplete assets", "",
             "| Asset | Pair | Status | Rows | Usable 4H | Last candle | Root cause |",
             "|---|---|---|---:|---:|---|---|"]
    for row in report["before"]["diagnostics"]:
        lines.append(f"| {row['asset']} | {row['pair']} | {row['status']} | {row['rows']} | "
                     f"{row['usable_completed_4h_bars']} | {row['latest_completed_candle']} | {row['root_cause']} |")
    lines += ["", "## Gate", "", f"**{after['gate']} — {after['coverage_pct']}% fully analyzable**", "",
              "No cohort activation, signals, entries, monitor events, outcomes, or orders were created."]
    return "\n".join(lines) + "\n"


def execute(
    universe_rows: list[dict[str, Any]], universe_metadata: dict[str, Any], repair: bool,
    getter: Callable[..., Any] = get_json, directory: Path = INTRADAY_DIR,
    wall_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    guard = ClockSafetyGuard()
    guard.check()
    cutoff = utc(wall_clock())
    loader = lambda pair: load_local_ohlcv(pair, directory)
    before_scan = run_scan(universe_rows, universe_metadata, ohlcv_loader=loader, wall_clock=wall_clock, guard=guard)
    before_diagnostics = audit_incomplete(before_scan, cutoff, directory)
    repairs = []
    repairable = {"NO_LOCAL_DATA", "INSUFFICIENT_HISTORY", "STALE_HISTORY", "RECENT_GAP",
                  "INTERNAL_GAPS", "INVALID_ROWS", "DUPLICATE_TIMESTAMPS", "TIMEFRAME_PROBLEM"}
    if repair:
        for row in before_diagnostics:
            if row["root_cause"] in repairable:
                guard.check()
                repairs.append(backfill_pair(row["pair"], utc(wall_clock()), directory, getter))
                guard.check()
    after_cutoff = utc(wall_clock())
    after_scan = run_scan(universe_rows, universe_metadata, ohlcv_loader=loader, wall_clock=wall_clock, guard=guard)
    after_diagnostics = audit_incomplete(after_scan, after_cutoff, directory)
    return {
        "version": REPORT_VERSION, "generated_at_utc": utc(wall_clock()).isoformat(),
        "before": {"summary": coverage_summary(before_scan, before_diagnostics), "diagnostics": before_diagnostics},
        "repairs": repairs,
        "after": {"summary": coverage_summary(after_scan, after_diagnostics), "diagnostics": after_diagnostics},
        "safety": {"official_forward_records_created": 0, "orders": 0, "private_endpoints": 0},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Public-data-only RANGE_FIXED_5 V2 coverage audit/repair.")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    universe, metadata = discover_public_universe()
    # execute owns the one lifecycle guard for audit/repair; discovery precedes its data cutoff.
    report = execute(universe, metadata, args.repair)
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "range_fixed_5_v2_data_coverage.json").write_text(
            json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        )
        (args.output_dir / "range_fixed_5_v2_data_coverage.md").write_text(render_report(report))
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) if args.json else render_report(report))


if __name__ == "__main__":
    main()
