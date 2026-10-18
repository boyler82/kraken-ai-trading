from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from range_fixed_5_v2_clock import clock_safety_preflight, load_clock_config
from range_fixed_5_v2_storage import (
    DB_PATH, append_activation_manifest, install_clock_safety_extension, load_config,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Permanently activate the RANGE_FIXED_5_FORWARD_V2 official cohort.")
    parser.add_argument("--start", required=True, help="Explicit UTC ISO-8601 cohort start; must not be in the past.")
    parser.add_argument("--yes", action="store_true", help="Confirm the permanent append-only activation non-interactively.")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    proposed = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
    print(f"Proposed permanent V2 cohort start: {proposed.isoformat()}")
    print("This cannot be overwritten or moved backward. Historical backfill remains prohibited.")
    if not args.yes:
        answer = input("Type ACTIVATE to confirm: ").strip()
        if answer != "ACTIVATE":
            raise SystemExit("Activation cancelled; no manifest was appended.")
    preflight = clock_safety_preflight()
    if preflight["status"] != "SAFE":
        raise SystemExit(f"Activation blocked: {preflight.get('error', 'CLOCK_UNSAFE')}")
    config = load_config()
    install_clock_safety_extension(args.db, config, load_clock_config())
    manifest = append_activation_manifest(args.db, config, args.start)
    destination = args.db.parent / f"strategy_manifest_activation_{manifest['manifest_id']}.json"
    destination.write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(f"Official cohort activated: {manifest['official_cohort_start_timestamp']}")
    print(f"Activation manifest: {destination}")


if __name__ == "__main__":
    main()
