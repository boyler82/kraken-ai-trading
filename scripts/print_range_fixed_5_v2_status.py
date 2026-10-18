from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from range_fixed_5_v2_clock import clock_safety_preflight
from range_fixed_5_v2_storage import DB_PATH, STRATEGY_ID


def read_status(db_path: Path, now: datetime | None = None) -> dict[str, object]:
    """Read the permanent V2 state without creating SQLite journals or sidecars."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    db = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro&immutable=1", uri=True)
    try:
        active = db.execute(
            """SELECT official_cohort_start_timestamp
               FROM v2_strategy_manifest
               WHERE strategy_id=? AND manifest_status='OFFICIAL_COHORT_ACTIVE'
               ORDER BY created_at_utc, manifest_id""",
            (STRATEGY_ID,),
        ).fetchall()
        if len(active) != 1:
            raise RuntimeError(f"expected exactly one activation manifest; found {len(active)}")
        start_text = active[0][0]
        start = datetime.fromisoformat(start_text.replace("Z", "+00:00")).astimezone(timezone.utc)
        tables = {
            "decisions": "v2_decision_snapshots",
            "signals": "v2_signals",
            "quote_attempts": "v2_quote_attempts",
            "accepted_entries": "v2_entry_observations",
            "open_observations": "v2_open_observations",
            "completed_outcomes": "v2_completed_outcomes",
        }
        counts = {name: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                  for name, table in tables.items()}
    finally:
        db.close()
    return {
        "cohort_start": start.isoformat().replace("+00:00", "Z"),
        "collection_state": "PRE_COHORT" if current < start else "COLLECTING",
        **counts,
    }


def render(
    db_path: Path = DB_PATH,
    now: datetime | None = None,
    preflight: Callable[[], dict[str, object]] = clock_safety_preflight,
) -> str:
    status = read_status(db_path, now)
    clock = preflight()
    return "\n".join([
        STRATEGY_ID,
        "",
        "Activation: ACTIVATED",
        f"Official cohort start: {status['cohort_start']}",
        "Collection state:",
        f"  {status['collection_state']}",
        "",
        f"Decisions: {status['decisions']}",
        f"Signals: {status['signals']}",
        f"Quote attempts: {status['quote_attempts']}",
        f"Accepted entries: {status['accepted_entries']}",
        f"Open observations: {status['open_observations']}",
        f"Completed outcomes: {status['completed_outcomes']}",
        "",
        "Data coverage: FROZEN REVIEW 100.00% (65/65)",
        f"Clock safety: {clock['status']}",
        "Trading capability: DISABLED",
    ]) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only RANGE_FIXED_5 V2 production status.")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    print(render(args.db), end="")


if __name__ == "__main__":
    main()
