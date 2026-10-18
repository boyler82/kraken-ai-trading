from __future__ import annotations

import ast
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import range_fixed_5_v2_entry as entry
import range_fixed_5_v2_snapshot as snapshot
import range_fixed_5_v2_storage as storage
from print_range_fixed_5_v2_entry_preview import render


def phase3_feature(**changes):
    value = {
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
    value.update(changes)
    return value


def setup_db(path: Path, activate: bool = True, feature_changes: dict | None = None):
    cfg = storage.load_config()
    foundation = storage.build_manifest(cfg, "2026-08-31T22:00:00+00:00")
    storage.initialize_database(path, cfg, foundation)
    extension = storage.install_phase4_extension(path, cfg, storage.load_phase4_config(), "2026-08-31T22:30:00+00:00")
    storage.install_clock_safety_extension(
        path, cfg, storage.json.loads(storage.CLOCK_CONFIG_PATH.read_text()), "2026-08-31T22:40:00+00:00"
    )
    if not activate:
        return cfg, foundation, extension, None
    active = storage.append_activation_manifest(path, cfg, "2026-09-01T00:00:00Z", "2026-08-31T23:00:00Z")
    decision = snapshot.build_decision_snapshot(phase3_feature(**(feature_changes or {})), cfg, active)
    snapshot.persist_snapshot(path, decision)
    return cfg, active, extension, decision


def create_ready_signal(path: Path):
    _, _, _, decision = setup_db(path)
    signal, created = entry.create_signal(path, decision["snapshot_id"], "2026-09-01T12:00:05Z")
    assert created
    return decision, signal


def ticker(bid="99.90", ask="100.00", status=None):
    quote = {"b": [bid, "1", "1"], "a": [ask, "1", "1"]}
    if status is not None:
        quote["status"] = status
    return {"error": [], "result": {"TESTUSD": quote}}


class Times:
    def __init__(self, *values): self.values = iter(values)
    def __call__(self): return datetime.fromisoformat(next(self.values).replace("Z", "+00:00"))


def test_inactive_cohort_blocks_signal(tmp_path):
    path = tmp_path / "v2.sqlite"
    setup_db(path, activate=False)
    with pytest.raises(ValueError, match="OFFICIAL_COHORT_NOT_ACTIVATED"):
        entry.create_signal(path, "missing", "2026-09-01T12:00:05Z")


def test_precohort_snapshot_is_blocked_before_signal(tmp_path):
    path = tmp_path / "v2.sqlite"
    cfg, active, _, _ = setup_db(path)
    old = snapshot.build_decision_snapshot(phase3_feature(decision_timestamp="2026-08-31T12:00:04Z"), cfg, active)
    with pytest.raises(sqlite3.IntegrityError, match="HISTORICAL_BACKFILL_PROHIBITED"):
        snapshot.persist_snapshot(path, old)


def test_ineligible_snapshot_blocks_signal(tmp_path):
    path = tmp_path / "v2.sqlite"
    _, _, _, decision = setup_db(path, feature_changes={"range_position_pct": 50.0, "reference_close": 105.0})
    with pytest.raises(ValueError, match="SNAPSHOT_NOT_ELIGIBLE"):
        entry.create_signal(path, decision["snapshot_id"], "2026-09-01T12:00:05Z")


def test_config_mismatch_blocks_signal(tmp_path):
    path = tmp_path / "v2.sqlite"
    cfg, active, _, _ = setup_db(path)
    decision = snapshot.build_decision_snapshot(phase3_feature(asset="MISMATCH"), cfg, active)
    decision["configuration_hash"] = "f" * 64
    snapshot.persist_snapshot(path, decision)
    with pytest.raises(ValueError, match="SNAPSHOT_CONFIG_MISMATCH"):
        entry.create_signal(path, decision["snapshot_id"], "2026-09-01T12:00:05Z")


def test_signal_cannot_precede_decision(tmp_path):
    path = tmp_path / "v2.sqlite"
    _, _, _, decision = setup_db(path)
    with pytest.raises(ValueError, match="SIGNAL_BEFORE_DECISION"):
        entry.create_signal(path, decision["snapshot_id"], "2026-09-01T12:00:03Z")


def test_duplicate_signal_is_idempotent(tmp_path):
    path = tmp_path / "v2.sqlite"
    _, signal = create_ready_signal(path)
    replay, created = entry.create_signal(path, signal["snapshot_id"], "2026-09-01T12:01:00Z")
    assert not created and replay["signal_id"] == signal["signal_id"]
    db = sqlite3.connect(path)
    assert db.execute("SELECT count(*) FROM v2_signals").fetchone()[0] == 1
    db.close()


def test_quote_request_cannot_precede_signal(tmp_path):
    path = tmp_path / "v2.sqlite"; _, signal = create_ready_signal(path)
    called = []
    with pytest.raises(ValueError, match="QUOTE_REQUEST_BEFORE_SIGNAL"):
        entry.observe_entry(path, signal["signal_id"], lambda *_: called.append(1), Times("2026-09-01T12:00:04Z"), lambda _: None)
    assert called == []


def test_quote_received_before_request_fails_closed(tmp_path):
    path = tmp_path / "v2.sqlite"; _, signal = create_ready_signal(path)
    times = Times("2026-09-01T12:00:06Z", "2026-09-01T12:00:08Z",
                  "2026-09-01T12:00:09Z", "2026-09-01T12:00:10Z",
                  "2026-09-01T12:00:11Z", "2026-09-01T12:00:12Z")
    responses = iter([
        (ticker(), "2026-09-01T12:00:04Z"),
        (ticker(), "2026-09-01T12:00:04Z"),
        (ticker(), "2026-09-01T12:00:04Z"),
    ])
    result = entry.observe_entry(path, signal["signal_id"], lambda *_: next(responses), times, lambda _: None)
    assert result["status"] == "ENTRY_NOT_OBSERVED"
    db = sqlite3.connect(path)
    assert db.execute("SELECT count(*) FROM v2_entry_observations").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM v2_quote_attempts").fetchone()[0] == 3
    db.close()


def test_valid_best_ask_entry_economics_and_single_entry(tmp_path):
    path = tmp_path / "v2.sqlite"; decision, signal = create_ready_signal(path)
    fetch = lambda *_: (ticker(), "2026-09-01T12:00:07Z")
    result = entry.observe_entry(path, signal["signal_id"], fetch, Times("2026-09-01T12:00:06Z"), lambda _: None)
    observed = result["entry"]
    assert result["status"] == "ENTRY_OBSERVED" and observed["entry_reference_price"] == 100
    assert observed["target_price"] == 105 and observed["stop_price"] == 98
    assert observed["expiry_timestamp"] == "2026-09-06T12:00:07+00:00"
    assert observed["gross_reward_pct"] == 5 and observed["gross_risk_pct"] == -2
    assert observed["gross_reward_risk_ratio"] == 2.5
    replay = entry.observe_entry(path, signal["signal_id"], lambda *_: pytest.fail("must not fetch"))
    assert replay["idempotent"] is True
    db = sqlite3.connect(path)
    assert db.execute("SELECT count(*) FROM v2_entry_observations").fetchone()[0] == 1
    assert db.execute("SELECT count(*) FROM v2_monitor_events").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM v2_completed_outcomes").fetchone()[0] == 0
    db.close()
    preview = render(decision, signal, observed, synthetic=True)
    assert "SYNTHETIC TEST PREVIEW" in preview and "No order was placed" in preview


@pytest.mark.parametrize("payload", [
    None,
    {"error": ["bad"], "result": {}},
    {"error": [], "result": {"TESTUSD": {"a": ["100"]}}},
    ticker("0", "100"), ticker("100", "0"), ticker("101", "100"),
    ticker("99", "100"), ticker(status="cancel_only"),
])
def test_invalid_quotes_fail_closed(tmp_path, payload):
    path = tmp_path / "v2.sqlite"; _, signal = create_ready_signal(path)
    times = Times("2026-09-01T12:00:06Z", "2026-09-01T12:00:07Z",
                  "2026-09-01T12:00:08Z", "2026-09-01T12:00:09Z",
                  "2026-09-01T12:00:10Z", "2026-09-01T12:00:11Z")
    result = entry.observe_entry(path, signal["signal_id"], lambda *_: payload, times, lambda _: None)
    assert result["status"] == "ENTRY_NOT_OBSERVED"
    db = sqlite3.connect(path)
    assert db.execute("SELECT count(*) FROM v2_quote_attempts").fetchone()[0] == 3
    assert db.execute("SELECT count(*) FROM v2_entry_observations").fetchone()[0] == 0
    db.close()


def test_network_failures_bounded_and_every_attempt_accounted(tmp_path):
    path = tmp_path / "v2.sqlite"; _, signal = create_ready_signal(path)
    calls, delays = [], []
    def fail(*_): calls.append(1); raise TimeoutError("timeout")
    times = Times("2026-09-01T12:00:06Z", "2026-09-01T12:00:07Z",
                  "2026-09-01T12:00:08Z", "2026-09-01T12:00:09Z",
                  "2026-09-01T12:00:10Z", "2026-09-01T12:00:11Z")
    result = entry.observe_entry(path, signal["signal_id"], fail, times, delays.append)
    assert result["status"] == "ENTRY_NOT_OBSERVED"
    assert len(calls) == 3 and delays == [1.0, 1.0]
    db = sqlite3.connect(path)
    assert db.execute("SELECT count(*) FROM v2_quote_attempts").fetchone()[0] == 3
    assert db.execute("SELECT count(*) FROM v2_entry_observations").fetchone()[0] == 0
    db.close()


def test_phase4_has_no_private_or_order_dependency():
    source = (ROOT / "scripts/range_fixed_5_v2_entry.py").read_text()
    tree = ast.parse(source)
    imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imports |= {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(token in name.lower() for name in imports for token in ("order", "position", "paper", "ccxt", "krakenex"))
    lowered = source.lower()
    assert "/private/" not in lowered and "addorder" not in lowered
    assert "api_key" not in lowered and "api_secret" not in lowered and "cancelorder" not in lowered
    policy = storage.load_phase4_config()
    assert policy["entry_observation"]["public_endpoint"] == "https://api.kraken.com/0/public/Ticker"
    assert "/private/" not in storage.canonical_json(policy).lower()


def test_phase4_extension_preserves_base_hash_and_is_deterministic(tmp_path):
    path = tmp_path / "v2.sqlite"
    cfg, foundation, extension, _ = setup_db(path, activate=False)
    policy = storage.load_phase4_config()
    assert extension["base_config_sha256"] == foundation["config_sha256"] == storage.sha256_json(cfg)
    assert extension["extension_config_sha256"] == storage.sha256_json(policy)
    assert storage.install_phase4_extension(path, cfg, policy, extension["created_at_utc"])["extension_manifest_id"] == extension["extension_manifest_id"]
