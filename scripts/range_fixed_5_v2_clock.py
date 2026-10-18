from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
CLOCK_CONFIG_PATH = ROOT / "config/range_fixed_5_forward_v2_clock_safety.json"

WallClock = Callable[[], datetime]
MonotonicClock = Callable[[], float]


def utc_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("CLOCK_TIMESTAMP_NOT_TIMEZONE_AWARE")
    return parsed.astimezone(timezone.utc)


def load_clock_config(path: Path = CLOCK_CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(path.read_text())
    validate_clock_config(config)
    return config


def validate_clock_config(config: dict[str, Any]) -> None:
    expected = {
        "base_strategy_id": "RANGE_FIXED_5_FORWARD_V2",
        "extension_id": "RANGE_FIXED_5_FORWARD_V2_CLOCK_SAFETY_V1",
        "extension_version": "1.0.0",
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"invalid clock-safety setting: {key}")
    if config.get("clock_policy") != {
        "external_sync_claim": "HOST_CLOCK_EXTERNAL_SYNC_UNVERIFIED",
        "fail_closed": True,
        "monotonic_required": True,
        "tolerance_seconds": 2.0,
        "utc_wall_clock_authoritative": True,
    }:
        raise ValueError("invalid frozen V2 clock-safety policy")


@dataclass(frozen=True)
class ClockCheck:
    wall_utc: datetime
    monotonic_value: float
    wall_elapsed_seconds: float
    monotonic_elapsed_seconds: float
    drift_seconds: float
    status: str


class ClockSafetyError(RuntimeError):
    pass


class ClockSafetyGuard:
    def __init__(
        self,
        wall_clock: WallClock = lambda: datetime.now(timezone.utc),
        monotonic_clock: MonotonicClock = time.monotonic,
        tolerance_seconds: float | None = None,
    ) -> None:
        config = load_clock_config()
        self.wall_clock = wall_clock
        self.monotonic_clock = monotonic_clock
        self.tolerance_seconds = float(
            config["clock_policy"]["tolerance_seconds"] if tolerance_seconds is None else tolerance_seconds
        )
        if self.tolerance_seconds < 0:
            raise ValueError("clock tolerance must be non-negative")
        self.wall_start_utc = utc_datetime(self.wall_clock())
        self.monotonic_start = float(self.monotonic_clock())
        self._last_wall_utc = self.wall_start_utc
        self._last_monotonic = self.monotonic_start

    def check(self) -> ClockCheck:
        wall = utc_datetime(self.wall_clock())
        monotonic_value = float(self.monotonic_clock())
        wall_elapsed = (wall - self.wall_start_utc).total_seconds()
        monotonic_elapsed = monotonic_value - self.monotonic_start
        drift = abs(wall_elapsed - monotonic_elapsed)
        if wall < self._last_wall_utc or wall_elapsed < 0:
            raise ClockSafetyError("CLOCK_CHRONOLOGY_ERROR")
        if monotonic_value < self._last_monotonic or monotonic_elapsed < 0:
            raise ClockSafetyError("MONOTONIC_CHRONOLOGY_ERROR")
        if drift > self.tolerance_seconds:
            raise ClockSafetyError("CLOCK_DRIFT_DETECTED")
        self._last_wall_utc = wall
        self._last_monotonic = monotonic_value
        return ClockCheck(wall, monotonic_value, wall_elapsed, monotonic_elapsed, drift, "PASS")


def clock_safety_preflight(
    wall_clock: WallClock = lambda: datetime.now(timezone.utc),
    monotonic_clock: MonotonicClock = time.monotonic,
) -> dict[str, Any]:
    config = load_clock_config()
    try:
        guard = ClockSafetyGuard(wall_clock, monotonic_clock)
        check = guard.check()
        return {
            "utc_wall_time": check.wall_utc.isoformat(),
            "monotonic_clock": "AVAILABLE",
            "chronology": "PASS",
            "drift_guard": "PASS",
            "drift_seconds": check.drift_seconds,
            "tolerance_seconds": guard.tolerance_seconds,
            "external_sync": config["clock_policy"]["external_sync_claim"],
            "status": "SAFE",
        }
    except Exception as exc:
        return {
            "utc_wall_time": None,
            "monotonic_clock": "AVAILABLE",
            "chronology": "FAIL",
            "drift_guard": "FAIL",
            "tolerance_seconds": config["clock_policy"]["tolerance_seconds"],
            "external_sync": config["clock_policy"]["external_sync_claim"],
            "status": "UNSAFE",
            "error": str(exc),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only RANGE_FIXED_5 V2 local clock-safety preflight.")
    parser.parse_args()
    result = clock_safety_preflight()
    print("V2 CLOCK SAFETY")
    print(f"UTC wall time: {result['utc_wall_time']}")
    print(f"Monotonic clock: {result['monotonic_clock']}")
    print(f"Chronology: {result['chronology']}")
    print(f"Drift guard: {result['drift_guard']}")
    print(f"Tolerance: {result['tolerance_seconds']} seconds")
    print(f"External synchronization: {result['external_sync']}")
    print(f"Status: {result['status']}")


if __name__ == "__main__":
    main()
