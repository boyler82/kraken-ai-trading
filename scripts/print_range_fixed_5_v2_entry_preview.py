from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from range_fixed_5_v2_storage import DB_PATH


def render(snapshot: dict[str, Any], signal: dict[str, Any], entry: dict[str, Any], synthetic: bool = False) -> str:
    label = "SYNTHETIC TEST PREVIEW — NOT PRODUCTION DATA" if synthetic else "OFFICIAL FORWARD RESEARCH RECORD"
    return f"""RANGE_FIXED_5 V2 — ENTRY OBSERVATION

{label}

Asset: {snapshot['asset']}
Status: RESEARCH ENTRY OBSERVED

Why detected:
- valid range
- accepted RQI: {snapshot.get('rqi_classification')}
- lower half of range: {snapshot.get('range_position_pct')}%
- synchronized legal snapshot

Signal time: {signal['signal_timestamp']}
Kraken quote observed: {entry['response_received_at']}
Best ask reference: {entry['entry_reference_price']}
Target +5%: {entry['target_price']}
Stop -2%: {entry['stop_price']}
Expiry: {entry['expiry_timestamp']}

IMPORTANT:
This is a research observation.
No order was placed.
No position exists on Kraken.
"""


def load_official(db_path: Path, signal_id: str) -> tuple[dict, dict, dict]:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        signal = db.execute("SELECT * FROM v2_signals WHERE signal_id=?", (signal_id,)).fetchone()
        if not signal:
            raise ValueError("signal not found")
        snapshot = db.execute("SELECT * FROM v2_decision_snapshots WHERE snapshot_id=?", (signal["snapshot_id"],)).fetchone()
        entry = db.execute("SELECT * FROM v2_entry_observations WHERE signal_id=?", (signal_id,)).fetchone()
        if not entry:
            raise ValueError("entry not observed")
        return dict(snapshot), dict(signal), dict(entry)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--signal-id")
    parser.add_argument("--synthetic-json", type=Path,
                        help="Render an explicitly labeled synthetic fixture instead of production DB data.")
    args = parser.parse_args()
    if args.synthetic_json:
        payload = json.loads(args.synthetic_json.read_text())
        print(render(payload["snapshot"], payload["signal"], payload["entry"], synthetic=True), end="")
        return
    if not args.signal_id:
        raise SystemExit("--signal-id is required unless --synthetic-json is used")
    print(render(*load_official(args.db, args.signal_id)), end="")


if __name__ == "__main__":
    main()
