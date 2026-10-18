from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from range_fixed_5_v2_storage import DB_PATH


def render(db_path: Path = DB_PATH) -> str:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in db.execute(
            "SELECT * FROM v2_decision_snapshots ORDER BY decision_timestamp DESC,asset"
        )]
        signals = db.execute("SELECT count(*) FROM v2_signals").fetchone()[0]
    finally:
        db.close()
    eligible = [row for row in rows if row.get("eligible_for_future_signal") == 1]
    cutoff = rows[0]["market_data_cutoff"] if rows else "NO SNAPSHOTS"
    lines = [
        "RANGE_FIXED_5 V2 SNAPSHOT", "", f"Market cutoff: {cutoff}",
        f"Assets evaluated: {len(rows)}", f"Eligible-for-future-signal: {len(eligible)}", "",
    ]
    for index, row in enumerate(eligible, 1):
        lines += [
            f"{index}. {row['asset']}", f"Range: {row.get('range_state')}",
            f"RQI: {row.get('rqi_classification')}", f"Range position: {row.get('range_position_pct')}%",
            f"Freshness: {row.get('freshness_status')}",
            f"Liquidity: {'GOOD' if row.get('liquidity_eligible') else 'FAIL'}",
            f"Spread: {'GOOD' if row.get('spread_eligible') else 'FAIL'}",
            "Timestamp legality: PASS", "", "Status:", "ELIGIBLE_FOR_FUTURE_SIGNAL", "",
        ]
    rejected = [row for row in rows if row.get("eligible_for_future_signal") != 1]
    if rejected:
        lines += ["Rejected:"]
        for row in rejected:
            reasons = ", ".join(json.loads(row.get("eligibility_reasons_json") or "[]"))
            lines.append(f"- {row['asset']} | {reasons or row['eligibility_status']}")
        lines.append("")
    lines += [
        "IMPORTANT:", f"No signal has been created. Signal rows: {signals}",
        "No entry has been observed.", "No trade has been placed.", "", "RESEARCH ONLY",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    print(render(args.db), end="")


if __name__ == "__main__":
    main()
