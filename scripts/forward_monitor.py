from __future__ import annotations

"""Safe operational dispatcher for already-active frozen forward experiments."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from forward_validation_board import REGISTRY, refresh as refresh_forward_board
from range_fixed_5_v2_storage import DB_PATH, STRATEGY_ID
from resolve_range_fixed_5_v2_expired import execute as execute_v2
from resolve_range_fixed_5_v2_expired import open_entries, verify_frozen


ACTIVE_STATES = {"FROZEN_FORWARD", "COLLECTING"}
SUPPORTED = {STRATEGY_ID}


def _load_registry(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
        raise RuntimeError("INCONSISTENT_EXPERIMENT_STATE: invalid Forward Validation Registry")
    if payload.get("trading_capability") != "DISABLED":
        raise RuntimeError("INCONSISTENT_EXPERIMENT_STATE: trading capability is not disabled")
    return payload


def active_experiments(registry_path: Path = REGISTRY) -> list[dict[str, Any]]:
    entries = _load_registry(registry_path)["entries"]
    active = [entry for entry in entries if entry.get("governance_state") in ACTIVE_STATES]
    for entry in active:
        if not entry.get("frozen_strategy_spec_hash") or not entry.get("activated_at"):
            raise RuntimeError("INCONSISTENT_EXPERIMENT_STATE: active experiment is not frozen and activated")
        if entry.get("trading_capability") != "DISABLED":
            raise RuntimeError("INCONSISTENT_EXPERIMENT_STATE: experiment trading capability is not disabled")
    return active


def run(
    registry_path: Path = REGISTRY,
    db_path: Path = DB_PATH,
    *,
    execute: Callable[..., dict[str, Any]] = execute_v2,
    refresh: Callable[..., dict[str, Any]] = refresh_forward_board,
) -> str:
    active = active_experiments(registry_path)
    if not active:
        return "No active frozen forward experiments.\naction: NONE\nstatus: SAFE\n"

    names = [entry.get("forward_experiment_name") for entry in active]
    unsupported = [name or entry.get("strategy_name", "UNKNOWN") for name, entry in zip(names, active)
                   if name not in SUPPORTED]
    if unsupported:
        raise RuntimeError("UNSUPPORTED_ACTIVE_EXPERIMENT: " + ", ".join(map(str, unsupported)))

    if len(names) != len(set(names)):
        raise RuntimeError("INCONSISTENT_EXPERIMENT_STATE: duplicate active experiment")

    lines: list[str] = []
    for entry in active:
        name = entry["forward_experiment_name"]
        frozen = verify_frozen(db_path)  # mandatory before every possible mutation
        if frozen["base_config_sha256"] != entry["frozen_strategy_spec_hash"]:
            raise RuntimeError("FROZEN_HASH_MISMATCH: registry and official manifest disagree")
        opens = open_entries(db_path)
        if int(entry.get("open_outcomes", -1)) != len(opens):
            raise RuntimeError("INCONSISTENT_EXPERIMENT_STATE: registry and official store open counts disagree")
        lines += [name, f"open observations: {len(opens)}"]
        if not opens:
            lines += ["action: NONE", "status: SAFE"]
            continue
        result = execute(db_path=db_path)
        if result.get("status") != "OFFICIAL_MONITOR_COMPLETE" or result.get("trading_capability") != "DISABLED":
            raise RuntimeError("OFFICIAL_MONITOR_FAILED_CLOSED")
        refresh(current=datetime.now(timezone.utc))
        remaining = len(open_entries(db_path))
        lines += [f"resolved observations: {len(opens) - remaining}", f"open observations after: {remaining}",
                  "action: OFFICIAL_MONITOR_UPDATE", "status: SAFE"]
    return "\n".join(lines) + "\n"


def main() -> None:
    try:
        print(run(), end="")
    except Exception as exc:
        print(f"forward-monitor: ABORTED\nreason: {exc}\nstatus: UNSAFE", flush=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
