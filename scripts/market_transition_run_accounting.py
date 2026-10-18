from __future__ import annotations

"""Operational run ledger for the market-transition launchd job.

This ledger is deliberately separate from immutable predictions.  Gap records are
diagnostics only and never imply that a prediction existed at a missed slot.
"""

import argparse
import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

from weekly_consolidation_common import ROOT, atomic_write, utc_timestamp

MEMORY = ROOT / "RESEARCH_MEMORY" / "market_transition"
RUNS = MEMORY / "operational_runs"
GAPS = MEMORY / "operational_gaps"
INTERVAL_SECONDS = 5400
VALID = {
    "SUCCESS_NEW_OBSERVATION", "NO_NEW_MARKET_DATA", "STALE_MARKET_DATA",
    "MARKET_DATA_REFRESH_FAILED", "MONITOR_FAILED", "MAC_SLEEP_OR_OFFLINE_GAP",
    "UNKNOWN_MISSED_RUN",
}


def _load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def latest_attempt_before(now: Any) -> dict[str, Any] | None:
    current = utc_timestamp(now)
    candidates = []
    for path in RUNS.glob("*.json") if RUNS.exists() else []:
        row = _load(path)
        try:
            if utc_timestamp(row["started_at"]) < current:
                candidates.append(row)
        except (KeyError, TypeError, ValueError):
            pass
    return max(candidates, key=lambda row: utc_timestamp(row["started_at"]), default=None)


def record_gaps(now: Any, previous: dict[str, Any] | None, reason: str = "MAC_SLEEP_OR_OFFLINE_GAP") -> list[Path]:
    if not previous:
        return []
    if reason not in {"MAC_SLEEP_OR_OFFLINE_GAP", "UNKNOWN_MISSED_RUN"}:
        raise ValueError(reason)
    current = utc_timestamp(now)
    expected = utc_timestamp(previous["started_at"]) + timedelta(seconds=INTERVAL_SECONDS)
    # Allow runtime and launchd jitter. The current invocation accounts for the
    # newest slot; only whole intervening slots are recorded as gaps.
    cutoff = current - timedelta(seconds=INTERVAL_SECONDS / 2)
    made = []
    GAPS.mkdir(parents=True, exist_ok=True)
    while expected < cutoff:
        path = GAPS / f"{expected.strftime('%Y%m%dT%H%M%S%fZ')}.json"
        payload = {"expected_at": expected.isoformat(), "recorded_at": current.isoformat(),
                   "status": reason, "prediction_created": False,
                   "forward_validation_eligible": False}
        try:
            with path.open("x") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True); handle.write("\n")
            made.append(path)
        except FileExistsError:
            pass
        expected += timedelta(seconds=INTERVAL_SECONDS)
    return made


def start(run_id: str, now: Any, trigger: str) -> Path:
    timestamp = utc_timestamp(now)
    previous = latest_attempt_before(timestamp)
    # launchd cannot replay StartInterval firings missed during sleep. A new
    # launchd invocation after a long wall-clock gap is therefore recorded as a
    # sleep/offline gap; manually invoked runs use the more conservative UNKNOWN.
    record_gaps(timestamp, previous, "MAC_SLEEP_OR_OFFLINE_GAP" if trigger == "launchd" else "UNKNOWN_MISSED_RUN")
    RUNS.mkdir(parents=True, exist_ok=True)
    path = RUNS / f"{run_id}.json"
    payload = {"run_id": run_id, "started_at": timestamp.isoformat(), "finished_at": None,
               "status": "STARTED", "trigger": trigger, "pid": os.getppid(),
               "prediction_created": False}
    with path.open("x") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True); handle.write("\n")
    return path


def finish(run_id: str, now: Any, status: str, exit_status: int, result_file: str | None) -> None:
    if status not in VALID:
        raise ValueError(status)
    path = RUNS / f"{run_id}.json"
    row = _load(path)
    result = _load(Path(result_file)) if result_file else {}
    row.update(result)
    row.update({"run_id": run_id, "finished_at": utc_timestamp(now).isoformat(),
                "status": status, "exit_status": exit_status,
                "prediction_created": status == "SUCCESS_NEW_OBSERVATION"})
    atomic_write(path, json.dumps(row, indent=2, sort_keys=True, allow_nan=False) + "\n", backup=False)
    atomic_write(MEMORY / "automation_last_run.json", json.dumps(row, indent=2, sort_keys=True, allow_nan=False) + "\n", backup=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    begin = sub.add_parser("start"); begin.add_argument("run_id"); begin.add_argument("--at", required=True); begin.add_argument("--trigger", choices=("launchd", "manual"), default="launchd")
    end = sub.add_parser("finish"); end.add_argument("run_id"); end.add_argument("--at", required=True); end.add_argument("--status", choices=sorted(VALID), required=True); end.add_argument("--exit-status", type=int, required=True); end.add_argument("--result-file")
    args = parser.parse_args()
    if args.command == "start":
        start(args.run_id, args.at, args.trigger)
    else:
        finish(args.run_id, args.at, args.status, args.exit_status, args.result_file)


if __name__ == "__main__":
    main()
