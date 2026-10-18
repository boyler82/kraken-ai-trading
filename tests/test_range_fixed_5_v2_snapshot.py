from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import range_fixed_5_v2_snapshot as snapshot
import range_fixed_5_v2_storage as storage


def setup_db(path: Path):
    cfg = storage.load_config(ROOT / "config/range_fixed_5_forward_v2.json")
    foundation = storage.build_manifest(cfg, "2026-08-31T22:00:00+00:00")
    storage.initialize_database(path, cfg, foundation)
    storage.install_phase4_extension(path, cfg, storage.load_phase4_config(), "2026-08-31T22:30:00+00:00")
    storage.install_clock_safety_extension(
        path, cfg, storage.json.loads(storage.CLOCK_CONFIG_PATH.read_text()), "2026-08-31T22:40:00+00:00"
    )
    active = storage.append_activation_manifest(
        path, cfg, "2026-09-01T00:00:00+00:00", "2026-08-31T23:00:00+00:00"
    )
    return cfg, active


def feature(**changes):
    base = {
        "asset": "TEST", "pair": "TESTUSD", "market_data_cutoff": "2026-09-01T12:00:00Z",
        "source_candle_open_timestamp": "2026-09-01T08:00:00Z",
        "source_candle_completion_timestamp": "2026-09-01T12:00:00Z",
        "source_data_observed_at": "2026-09-01T12:00:01Z",
        "feature_calculation_started_at": "2026-09-01T12:00:02Z",
        "feature_calculation_completed_at": "2026-09-01T12:00:03Z",
        "decision_timestamp": "2026-09-01T12:00:04Z",
        "reference_close": 102.0, "atr14": 1.0, "range_low": 100.0, "range_high": 110.0,
        "range_midpoint": 105.0, "range_position_pct": 20.0, "range_valid": True,
        "range_state": "VALID_RANGE", "rqi_score": 70.0, "rqi_classification": "GOOD_RANGE",
        "rqi_position_zone": "LOWER_ZONE", "freshness_status": "FRESH",
        "liquidity_eligible": True, "spread_eligible": True, "universe_eligibility": True,
        "market_regime": "BEAR", "btc_market_state": "BELOW_EMA20",
        "source_hashes": {"ohlcv": "a" * 64},
        "component_cutoffs": {name: "2026-09-01T12:00:00Z" for name in ("price", "range", "rqi", "liquidity", "spread", "universe")},
        "feature_availability_timestamps": {"ohlcv": "2026-09-01T12:00:01Z", "range": "2026-09-01T12:00:03Z", "rqi": "2026-09-01T12:00:03Z"},
    }
    base.update(changes)
    return base


def build(tmp_path: Path, **changes):
    cfg, manifest = setup_db(tmp_path / "v2.sqlite")
    return snapshot.build_decision_snapshot(feature(**changes), cfg, manifest), cfg, manifest


def test_completed_candle_unavailable_before_completion(tmp_path):
    result, _, _ = build(tmp_path, source_data_observed_at="2026-09-01T11:59:59Z")
    assert result["eligibility_status"] == "NOT_ELIGIBLE_TIMESTAMP_ILLEGAL"


def test_candle_open_cannot_be_decision_time(tmp_path):
    result, _, _ = build(tmp_path, decision_timestamp="2026-09-01T08:00:00Z")
    assert result["eligibility_status"] == "NOT_ELIGIBLE_TIMESTAMP_ILLEGAL"


def test_future_feature_timestamp_fails_closed(tmp_path):
    result, _, _ = build(tmp_path, feature_availability_timestamps={"rqi": "2026-09-01T12:00:05Z"})
    assert result["eligible_for_future_signal"] is False
    assert "NOT_ELIGIBLE_TIMESTAMP_ILLEGAL" in result["eligibility_reasons"]


def test_mixed_market_cutoffs_fail_closed(tmp_path):
    cutoffs = feature()["component_cutoffs"]
    cutoffs["liquidity"] = "2026-09-01T11:00:00Z"
    result, _, _ = build(tmp_path, component_cutoffs=cutoffs)
    assert result["eligibility_status"] == "NOT_ELIGIBLE_TIMESTAMP_ILLEGAL"


def test_hashes_are_deterministic_and_sensitive(tmp_path):
    cfg, manifest = setup_db(tmp_path / "v2.sqlite")
    first = snapshot.build_decision_snapshot(feature(), cfg, manifest)
    second_data = feature(feature_calculation_started_at="2026-09-01T12:00:02.5Z", decision_timestamp="2026-09-01T12:00:04.5Z")
    second = snapshot.build_decision_snapshot(second_data, cfg, manifest)
    changed = snapshot.build_decision_snapshot(feature(source_hashes={"ohlcv": "b" * 64}), cfg, manifest)
    assert first["canonical_input_hash"] == second["canonical_input_hash"]
    assert first["feature_snapshot_hash"] == second["feature_snapshot_hash"]
    assert first["canonical_input_hash"] != changed["canonical_input_hash"]
    assert first["feature_snapshot_hash"] != changed["feature_snapshot_hash"]


def test_changed_deterministic_feature_changes_only_feature_hash(tmp_path):
    cfg, manifest = setup_db(tmp_path / "v2.sqlite")
    first = snapshot.build_decision_snapshot(feature(), cfg, manifest)
    changed = snapshot.build_decision_snapshot(feature(rqi_score=71.0), cfg, manifest)
    assert first["canonical_input_hash"] == changed["canonical_input_hash"]
    assert first["feature_snapshot_hash"] != changed["feature_snapshot_hash"]


def test_snapshot_immutable_and_duplicate_idempotent(tmp_path):
    result, _, _ = build(tmp_path)
    db_path = tmp_path / "v2.sqlite"
    assert snapshot.persist_snapshot(db_path, result)[1] is True
    assert snapshot.persist_snapshot(db_path, result)[1] is False
    db = sqlite3.connect(db_path)
    assert db.execute("SELECT count(*) FROM v2_decision_snapshots").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError, match="APPEND_ONLY"):
        db.execute("UPDATE v2_decision_snapshots SET range_position_pct=49")
    assert db.execute("SELECT count(*) FROM v2_signals").fetchone()[0] == 0
    db.close()


@pytest.mark.parametrize("position", [0.0, 49.999])
def test_lower_half_boundaries_qualify(tmp_path, position):
    result, _, _ = build(tmp_path, range_position_pct=position, reference_close=100 + position / 10)
    assert result["eligible_for_future_signal"] is True


def test_exactly_fifty_is_rejected(tmp_path):
    result, _, _ = build(tmp_path, range_position_pct=50.0, reference_close=105.0)
    assert "NOT_ELIGIBLE_UPPER_HALF" in result["eligibility_reasons"]


def test_outside_range_is_rejected(tmp_path):
    result, _, _ = build(tmp_path, range_position_pct=-10.0, reference_close=99.0)
    assert "NOT_ELIGIBLE_PRICE_OUTSIDE_RANGE" in result["eligibility_reasons"]


@pytest.mark.parametrize("classification", ["ACCEPTABLE_RANGE", "GOOD_RANGE", "EXCELLENT_RANGE"])
def test_accepted_rqi_classifications(tmp_path, classification):
    result, _, _ = build(tmp_path, rqi_classification=classification)
    assert result["eligible_for_future_signal"] is True


def test_rejected_rqi_classification(tmp_path):
    result, _, _ = build(tmp_path, rqi_classification="WEAK_RANGE")
    assert "NOT_ELIGIBLE_RQI" in result["eligibility_reasons"]


@pytest.mark.parametrize("field,reason", [
    ("freshness_status", "NOT_ELIGIBLE_STALE_DATA"),
    ("liquidity_eligible", "NOT_ELIGIBLE_LIQUIDITY"),
    ("spread_eligible", "NOT_ELIGIBLE_SPREAD"),
])
def test_quality_failures_are_rejected(tmp_path, field, reason):
    value = "STALE" if field == "freshness_status" else False
    result, _, _ = build(tmp_path, **{field: value})
    assert reason in result["eligibility_reasons"]


def test_liquidity_and_spread_thresholds_are_frozen():
    assert snapshot.MIN_QUOTE_VOLUME_24H == 250_000.0
    assert snapshot.MAX_BID_ASK_SPREAD_PCT == 0.75


def test_regime_is_metadata_only(tmp_path):
    bear, _, _ = build(tmp_path, market_regime="BEAR")
    bull = snapshot.build_decision_snapshot({**feature(), "market_regime": "BULL"}, storage.load_config(),
                                             {"manifest_id": bear["manifest_id"], "config_sha256": bear["configuration_hash"]})
    assert bear["eligible_for_future_signal"] is True
    assert bull["eligible_for_future_signal"] is True


def test_missing_required_data_is_incomplete(tmp_path):
    result, _, _ = build(tmp_path, atr14=None)
    assert result["eligibility_status"] == "NOT_ELIGIBLE_DATA_INCOMPLETE"
    assert result["range_low"] == 100.0


def test_complete_data_invalid_range_with_nonapplicable_rqi_is_range_invalid(tmp_path):
    result, _, _ = build(
        tmp_path, range_valid=False, range_state="RANGE_INVALIDATED",
        rqi_score=None, rqi_classification="NOT_APPLICABLE",
    )
    assert result["eligibility_status"] == "NOT_ELIGIBLE_RANGE_INVALID"
    assert result["eligibility_reasons"] == ["NOT_ELIGIBLE_RANGE_INVALID"]
    assert result["rqi_score"] is None


def test_valid_range_with_unexpected_null_rqi_is_data_incomplete(tmp_path):
    result, _, _ = build(tmp_path, range_valid=True, rqi_score=None, rqi_classification="NOT_APPLICABLE")
    assert result["eligibility_status"] == "NOT_ELIGIBLE_DATA_INCOMPLETE"


def test_missing_ohlcv_fields_remain_data_incomplete_even_when_range_invalid(tmp_path):
    result, _, _ = build(
        tmp_path, source_candle_open_timestamp=None, range_valid=False,
        range_state="RANGE_INVALIDATED", rqi_score=None, rqi_classification="NOT_APPLICABLE",
    )
    assert result["eligibility_status"] == "NOT_ELIGIBLE_DATA_INCOMPLETE"


def test_no_private_api_or_order_dependency():
    for filename in ("range_fixed_5_v2_snapshot.py", "activate_range_fixed_5_v2_cohort.py",
                     "print_range_fixed_5_v2_snapshot_summary.py"):
        source = (ROOT / "scripts" / filename).read_text()
        tree = ast.parse(source)
        imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        imports |= {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        assert not any(token in name.lower() for name in imports for token in ("order", "position", "paper", "ccxt", "krakenex"))
        lowered = source.lower()
        assert "/private/" not in lowered and "addorder" not in lowered and "api_secret" not in lowered
