from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import range_fixed_5_v2_clock as clock_safety
import range_fixed_5_v2_entry as entry
import range_fixed_5_v2_snapshot as snapshot
import range_fixed_5_v2_storage as storage
from test_range_fixed_5_v2_phase4 import Times, create_ready_signal, phase3_feature, setup_db, ticker


class Values:
    def __init__(self, *values):
        self.values = iter(values)

    def __call__(self):
        return next(self.values)


def utc(seconds: float) -> datetime:
    return datetime(2026, 9, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)


def test_process_audit_times_do_not_change_economic_or_feature_hash(tmp_path):
    path = tmp_path / "v2.sqlite"
    cfg, active, _, _ = setup_db(path)
    first = snapshot.build_decision_snapshot(phase3_feature(), cfg, active)
    later = snapshot.build_decision_snapshot(phase3_feature(
        feature_calculation_started_at="2026-09-01T12:10:02Z",
        feature_calculation_completed_at="2026-09-01T12:10:03Z",
        decision_timestamp="2026-09-01T12:10:04Z",
        feature_availability_timestamps={
            "ohlcv": "2026-09-01T12:00:01Z",
            "range": "2026-09-01T12:10:03Z",
            "rqi": "2026-09-01T12:10:03Z",
        },
    ), cfg, active)
    assert first["canonical_input_hash"] == later["canonical_input_hash"]
    assert first["feature_snapshot_hash"] == later["feature_snapshot_hash"]


def test_changed_ohlcv_identity_changes_canonical_hash(tmp_path):
    path = tmp_path / "v2.sqlite"
    cfg, active, _, _ = setup_db(path)
    first = snapshot.build_decision_snapshot(phase3_feature(), cfg, active)
    changed = snapshot.build_decision_snapshot(phase3_feature(source_hashes={"ohlcv": "b" * 64}), cfg, active)
    assert first["canonical_input_hash"] != changed["canonical_input_hash"]


def test_changed_feature_result_changes_feature_hash_not_market_identity(tmp_path):
    path = tmp_path / "v2.sqlite"
    cfg, active, _, _ = setup_db(path)
    first = snapshot.build_decision_snapshot(phase3_feature(), cfg, active)
    changed = snapshot.build_decision_snapshot(phase3_feature(rqi_score=71.0), cfg, active)
    assert first["canonical_input_hash"] == changed["canonical_input_hash"]
    assert first["feature_snapshot_hash"] != changed["feature_snapshot_hash"]


def test_clock_guard_normal_and_small_drift_pass():
    guard = clock_safety.ClockSafetyGuard(Values(utc(0), utc(1.5)), Values(10.0, 11.0), 2.0)
    result = guard.check()
    assert result.status == "PASS" and result.drift_seconds == pytest.approx(0.5)


def test_clock_guard_backward_wall_fails_closed():
    guard = clock_safety.ClockSafetyGuard(Values(utc(10), utc(9)), Values(10.0, 11.0), 2.0)
    with pytest.raises(clock_safety.ClockSafetyError, match="CLOCK_CHRONOLOGY_ERROR"):
        guard.check()


def test_clock_guard_forward_jump_fails_closed():
    guard = clock_safety.ClockSafetyGuard(Values(utc(0), utc(10)), Values(10.0, 11.0), 2.0)
    with pytest.raises(clock_safety.ClockSafetyError, match="CLOCK_DRIFT_DETECTED"):
        guard.check()


def test_persistent_backward_quote_clock_persists_no_invalid_attempt(tmp_path):
    path = tmp_path / "v2.sqlite"
    _, signal = create_ready_signal(path)
    result = entry.observe_entry(
        path, signal["signal_id"], lambda *_: (ticker(), "2026-09-01T12:00:04Z"),
        Times("2026-09-01T12:00:06Z", "2026-09-01T12:00:05Z"), lambda _: None,
    )
    assert result["status"] == "CLOCK_CHRONOLOGY_ERROR"
    db = sqlite3.connect(path)
    assert db.execute("SELECT count(*) FROM v2_quote_attempts").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM v2_entry_observations").fetchone()[0] == 0
    db.close()


def test_signal_not_created_when_clock_guard_fails(tmp_path):
    path = tmp_path / "v2.sqlite"
    _, _, _, decision = setup_db(path)
    guard = clock_safety.ClockSafetyGuard(Values(utc(0), utc(10)), Values(0.0, 1.0), 2.0)
    with pytest.raises(clock_safety.ClockSafetyError, match="CLOCK_DRIFT_DETECTED"):
        entry.create_signal(path, decision["snapshot_id"], "2026-09-01T12:00:05Z", clock_guard=guard)
    db = sqlite3.connect(path)
    assert db.execute("SELECT count(*) FROM v2_signals").fetchone()[0] == 0
    db.close()


def test_entry_not_accepted_when_clock_guard_fails(tmp_path):
    path = tmp_path / "v2.sqlite"
    _, signal = create_ready_signal(path)
    guard = clock_safety.ClockSafetyGuard(
        Values(utc(0), utc(0), utc(10)), Values(0.0, 0.0, 1.0), 2.0
    )
    called = []
    result = entry.observe_entry(
        path, signal["signal_id"], lambda *_: called.append(1),
        Times("2026-09-01T12:00:06Z"), lambda _: None, clock_guard=guard,
    )
    assert result["status"] == "CLOCK_DRIFT_DETECTED" and called == []
    db = sqlite3.connect(path)
    assert db.execute("SELECT count(*) FROM v2_quote_attempts").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM v2_entry_observations").fetchone()[0] == 0
    db.close()


def test_clock_preflight_is_local_and_disclaims_external_sync():
    result = clock_safety.clock_safety_preflight(Values(utc(0), utc(0.1)), Values(1.0, 1.1))
    assert result["status"] == "SAFE"
    assert result["external_sync"] == "HOST_CLOCK_EXTERNAL_SYNC_UNVERIFIED"
    assert result["tolerance_seconds"] == 2.0


def test_activation_requires_immutable_clock_extension(tmp_path):
    path = tmp_path / "v2.sqlite"
    cfg = storage.load_config()
    foundation = storage.build_manifest(cfg, "2026-08-31T22:00:00+00:00")
    storage.initialize_database(path, cfg, foundation)
    storage.install_phase4_extension(path, cfg, storage.load_phase4_config(), "2026-08-31T22:30:00+00:00")
    with pytest.raises(ValueError, match="clock-safety extension"):
        storage.append_activation_manifest(path, cfg, "2026-09-01T00:00:00Z", "2026-08-31T23:00:00Z")
