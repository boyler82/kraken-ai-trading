from __future__ import annotations

"""Official Phase-4.5 collection runner for RANGE_FIXED_5_FORWARD_V2.

This module is deliberately only an observation orchestrator.  It persists the
Phase-3 decision made from one synchronized cutoff and, for eligible decisions,
uses the Phase-4 public best-ask observer.  It has no order or private-API
capability.
"""

import argparse
import json
import sqlite3
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd

from range_fixed_5_v2_clock import ClockSafetyError, ClockSafetyGuard
from range_fixed_5_v2_entry import create_signal, fetch_public_kraken_ticker, observe_entry
from range_fixed_5_v2_snapshot import calculate_from_ohlcv, current_active_manifest, persist_snapshot
from range_fixed_5_v2_storage import DB_PATH, load_config
from range_fixed_5_v2_universe_scanner import (
    deduplicate_universe,
    discover_public_universe,
    load_local_ohlcv,
    load_local_universe,
)


CODE_VERSION = "RANGE_FIXED_5_V2_OFFICIAL_RUNNER_1.0.0"
Clock = Callable[[], datetime]


def utc(value: Any = None) -> datetime:
    parsed = datetime.now(timezone.utc) if value is None else (
        value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _active_episode(db_path: Path, asset: str, excluded_snapshot_id: str) -> bool:
    """Return whether an earlier, unresolved signal exists for this asset."""
    db = sqlite3.connect(db_path)
    try:
        row = db.execute(
            """SELECT 1 FROM v2_signals s
               LEFT JOIN v2_completed_outcomes o ON o.signal_id=s.signal_id
               WHERE s.asset=? AND s.snapshot_id<>? AND o.signal_id IS NULL LIMIT 1""",
            (asset, excluded_snapshot_id),
        ).fetchone()
        return row is not None
    finally:
        db.close()


def _counts(db_path: Path) -> dict[str, int]:
    db = sqlite3.connect(db_path)
    try:
        return {
            name: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for name, table in {
                "decisions": "v2_decision_snapshots",
                "signals": "v2_signals",
                "quote_attempts": "v2_quote_attempts",
                "entries": "v2_entry_observations",
            }.items()
        }
    finally:
        db.close()


def run_official(
    universe_rows: list[dict[str, Any]],
    universe_metadata: dict[str, Any],
    ohlcv_loader: Callable[[str], tuple[Any, str]] = load_local_ohlcv,
    quote_fetcher: Callable[[str, str], Any] = fetch_public_kraken_ticker,
    wall_clock: Clock = lambda: datetime.now(timezone.utc),
    sleeper: Callable[[float], None] = time.sleep,
    guard: Optional[ClockSafetyGuard] = None,
    db_path: Path = DB_PATH,
) -> dict[str, Any]:
    """Run one official, synchronized, forward-only observation cycle.

    Universe staleness, inactive/pre-start cohorts and unsafe clocks are checked
    before the first official row is written.  A rejected decision is still an
    official forward decision; only eligible decisions produce signals.
    """
    run_guard = guard or ClockSafetyGuard()
    before = _counts(db_path)
    try:
        run_guard.check()
        manifest = current_active_manifest(db_path)
        cutoff = utc(wall_clock())
        cohort_start = utc(manifest["official_cohort_start_timestamp"])
        if cutoff < cohort_start:
            raise RuntimeError("OFFICIAL_COHORT_NOT_STARTED")
        if not universe_metadata.get("fresh"):
            raise RuntimeError("UNIVERSE_METADATA_STALE")
        observed_at = utc(universe_metadata.get("observed_at"))
        if observed_at > cutoff:
            raise RuntimeError("UNIVERSE_OBSERVED_AFTER_CUTOFF")
        run_guard.check()
    except (ClockSafetyError, RuntimeError, ValueError) as exc:
        return {
            "status": str(exc), "code_version": CODE_VERSION, "cutoff": None,
            "decisions": [], "signals": [], "entries": [], "errors": [],
            "writes": {key: 0 for key in before}, "orders_placed": 0,
        }

    config = load_config()
    rows, conflicts = deduplicate_universe(universe_rows)
    exclusions: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    component_cutoffs = {
        name: cutoff.isoformat()
        for name in ("price", "range", "rqi", "liquidity", "spread", "universe")
    }

    # Calculate and persist the complete batch before creating any signal.  This
    # makes simultaneous_signal_count a property of the decision batch.
    for row in rows:
        asset = str(row.get("symbol") or "").upper()
        pair = str(row.get("selected_kraken_pair") or "").upper()
        if row.get("inclusion_status") != "INCLUDED" or not pair:
            exclusions.append({
                "asset": asset, "pair": pair or None,
                "reason": row.get("exclusion_reason") or "NOT_ELIGIBLE_UNIVERSE",
            })
            continue
        try:
            run_guard.check()
            try:
                raw, source_path = ohlcv_loader(pair)
                source_error = None
            except Exception as exc:
                # Missing/bad source data is itself an official forward
                # observation.  Feed an empty frame through the frozen snapshot
                # engine so it is stored as DATA_INCOMPLETE rather than omitted.
                raw = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
                source_path, source_error = None, str(exc)
            decision = calculate_from_ohlcv(
                raw, asset, pair, "1H", cutoff, observed_at,
                float(row.get("kraken_24h_quote_volume") or 0.0),
                float(row.get("bid_ask_spread_pct") if row.get("bid_ask_spread_pct") is not None else 999.0),
                True, manifest, config, market_regime="UNKNOWN", btc_market_state="UNKNOWN",
                component_cutoffs=component_cutoffs,
            )
            decision["source_path"] = source_path
            if source_error:
                decision["source_data_error"] = source_error
            _, inserted = persist_snapshot(db_path, decision)
            decisions.append({"snapshot": decision, "persisted": inserted})
            run_guard.check()
        except ClockSafetyError as exc:
            errors.append({"asset": asset, "pair": pair, "stage": "DECISION", "error": str(exc)})
            break
        except Exception as exc:
            # No signal can be inferred when an official decision cannot be built
            # and persisted.  Continue so one bad local file does not hide the rest.
            errors.append({"asset": asset, "pair": pair, "stage": "DECISION", "error": str(exc)})

    clock_failed = bool(errors and errors[-1]["error"] in {
        "CLOCK_CHRONOLOGY_ERROR", "MONOTONIC_CHRONOLOGY_ERROR", "CLOCK_DRIFT_DETECTED"
    })
    eligible = [item for item in decisions if item["snapshot"].get("eligible_for_future_signal")]
    signals: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    if not clock_failed:
        simultaneous = max(1, len(eligible))
        for item in eligible:
            decision = item["snapshot"]
            try:
                run_guard.check()
                signal_time = utc(wall_clock())
                signal, created = create_signal(
                    db_path, decision["snapshot_id"], signal_time, simultaneous,
                    _active_episode(db_path, decision["asset"], decision["snapshot_id"]), run_guard,
                )
                signals.append({"signal": signal, "created": created})
                observed = observe_entry(
                    db_path, signal["signal_id"], quote_fetcher, wall_clock, sleeper,
                    clock_guard=run_guard,
                )
                entries.append({"signal_id": signal["signal_id"], **observed})
                if observed["status"] in {
                    "CLOCK_CHRONOLOGY_ERROR", "MONOTONIC_CHRONOLOGY_ERROR", "CLOCK_DRIFT_DETECTED"
                }:
                    errors.append({"asset": decision["asset"], "pair": decision["pair"],
                                   "stage": "ENTRY", "error": observed["status"]})
                    break
            except Exception as exc:
                errors.append({"asset": decision["asset"], "pair": decision["pair"],
                               "stage": "SIGNAL_OR_ENTRY", "error": str(exc)})

    after = _counts(db_path)
    rejection_counts = Counter(
        reason for item in decisions if not item["snapshot"].get("eligible_for_future_signal")
        for reason in item["snapshot"].get("eligibility_reasons", [])
    )
    rejection_counts.update(item["reason"] for item in exclusions)
    return {
        "status": "OFFICIAL_RUN_COMPLETE" if not errors else "OFFICIAL_RUN_COMPLETED_WITH_ERRORS",
        "code_version": CODE_VERSION, "cutoff": cutoff.isoformat(),
        "universe_source": universe_metadata, "assets_discovered": len(universe_rows),
        "assets_evaluated": len(decisions), "eligible_decisions": len(eligible),
        "decisions": decisions, "signals": signals, "entries": entries,
        "exclusions": exclusions, "mapping_conflicts": conflicts, "errors": errors,
        "rejection_reason_distribution": dict(sorted(rejection_counts.items())),
        "writes": {key: after[key] - before[key] for key in before},
        "orders_placed": 0, "clock_guard_identity": id(run_guard),
    }


def render_summary(result: dict[str, Any]) -> str:
    lines = ["RANGE_FIXED_5_FORWARD_V2 — OFFICIAL RUN", "", f"Status: {result['status']}"]
    if result.get("cutoff"):
        lines += [f"Synchronized cutoff: {result['cutoff']}",
                  f"Assets evaluated: {result['assets_evaluated']}",
                  f"Eligible decisions: {result['eligible_decisions']}",
                  f"Signals in batch: {len(result['signals'])}",
                  f"Entries observed: {sum(item['status'] == 'ENTRY_OBSERVED' for item in result['entries'])}"]
    if result.get("errors"):
        lines += ["", "Errors:"] + [
            f"- {item['asset']} ({item['pair']}), {item['stage']}: {item['error']}"
            for item in result["errors"]
        ]
    lines += ["", "RESEARCH OBSERVATION ONLY", "NO ORDERS PLACED"]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one official RANGE_FIXED_5 V2 forward observation cycle.")
    parser.add_argument("--public-refresh", action="store_true",
                        help="Refresh the public dynamic universe in memory for this run.")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--json", action="store_true", help="Print the machine-readable result.")
    args = parser.parse_args()
    if args.public_refresh:
        rows, metadata = discover_public_universe()
    else:
        rows, metadata = load_local_universe()
    result = run_official(rows, metadata, db_path=args.db)
    print(json.dumps(result, indent=2, sort_keys=True, default=str) if args.json else render_summary(result), end="" if args.json else "")
    if result["status"] != "OFFICIAL_RUN_COMPLETE":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
