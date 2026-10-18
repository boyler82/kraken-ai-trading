from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import range_fixed_5_v2_storage as storage


def config() -> dict:
    return storage.load_config(ROOT / "config/range_fixed_5_forward_v2.json")


def initialize(path: Path):
    cfg = config()
    manifest = storage.build_manifest(cfg, "2026-08-27T00:00:00+00:00")
    storage.initialize_database(path, cfg, manifest)
    return cfg, manifest


def activate(path: Path):
    cfg, foundation = initialize(path)
    storage.install_phase4_extension(path, cfg, storage.load_phase4_config(), "2026-08-31T22:30:00+00:00")
    storage.install_clock_safety_extension(
        path, cfg, storage.json.loads(storage.CLOCK_CONFIG_PATH.read_text()), "2026-08-31T22:40:00+00:00"
    )
    active = storage.append_activation_manifest(
        path, cfg, "2026-09-01T00:00:00+00:00", "2026-08-31T23:00:00+00:00"
    )
    return cfg, foundation, active


def test_deterministic_config_hash_and_manifest_consistency():
    cfg = config()
    reordered = dict(reversed(list(cfg.items())))
    assert storage.sha256_json(cfg) == storage.sha256_json(reordered)
    manifest = storage.build_manifest(cfg, "2026-08-27T00:00:00+00:00")
    assert manifest["config_sha256"] == storage.sha256_json(cfg)
    assert manifest["official_cohort_start_timestamp"] is None
    assert manifest["official_cohort_active"] is False
    assert manifest["manifest_status"] == "FOUNDATION_ONLY"


def test_database_schema_and_empty_official_cohort(tmp_path):
    db_path = tmp_path / "v2.sqlite"
    initialize(db_path)
    db = sqlite3.connect(db_path)
    names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert set(storage.IMMUTABLE_TABLES) <= names
    assert db.execute("SELECT count(*) FROM v2_strategy_manifest").fetchone()[0] == 1
    for table in storage.IMMUTABLE_TABLES[1:]:
        assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM v2_open_observations").fetchone()[0] == 0
    db.close()


def test_manifest_is_append_only_and_conflicting_reinitialization_fails(tmp_path):
    db_path = tmp_path / "v2.sqlite"
    cfg, manifest = initialize(db_path)
    db = sqlite3.connect(db_path)
    with pytest.raises(sqlite3.IntegrityError, match="APPEND_ONLY"):
        db.execute("UPDATE v2_strategy_manifest SET hypothesis_version='changed'")
    with pytest.raises(sqlite3.IntegrityError, match="APPEND_ONLY"):
        db.execute("DELETE FROM v2_strategy_manifest")
    db.close()
    changed = dict(manifest, notes="different immutable content")
    with pytest.raises(ValueError, match="differs"):
        storage.initialize_database(db_path, cfg, changed)


def test_decision_duplicate_protection_and_overwrite_rejection(tmp_path):
    db_path = tmp_path / "v2.sqlite"
    _, _, manifest = activate(db_path)
    db = sqlite3.connect(db_path)
    row = ("snap", manifest["manifest_id"], "OFFICIAL_FORWARD", "BTC", "BTCUSD", "2026-09-01T12:00:00Z", "2026-09-01T12:00:01Z", "ELIGIBLE", "{}", "a" * 64, "2026-09-01T12:00:01Z")
    columns = "snapshot_id,manifest_id,cohort_type,asset,kraken_pair,market_data_cutoff,decision_timestamp,eligibility_status,canonical_payload_json,payload_sha256,created_at_utc"
    db.execute(f"INSERT INTO v2_decision_snapshots({columns}) VALUES(?,?,?,?,?,?,?,?,?,?,?)", row)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(f"INSERT INTO v2_decision_snapshots({columns}) VALUES(?,?,?,?,?,?,?,?,?,?,?)", row)
    with pytest.raises(sqlite3.IntegrityError, match="APPEND_ONLY"):
        db.execute("UPDATE v2_decision_snapshots SET eligibility_status='CHANGED' WHERE snapshot_id='snap'")
    db.close()


def test_official_signals_rejected_until_cohort_activation(tmp_path):
    db_path = tmp_path / "v2.sqlite"
    _, manifest = initialize(db_path)
    db = sqlite3.connect(db_path)
    signal = ("sig", "snap", manifest["manifest_id"], "OFFICIAL_FORWARD", "BTC", "BTCUSD", "batch", "2026-09-01T12:00:01Z", 1, 0, "b" * 64, "2026-09-01T12:00:01Z")
    with pytest.raises(sqlite3.IntegrityError, match="OFFICIAL_COHORT_NOT_ACTIVATED"):
        db.execute("INSERT INTO v2_signals VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", signal)
    assert db.execute("SELECT count(*) FROM v2_signals").fetchone()[0] == 0
    db.close()


def test_activated_cohort_rejects_historical_official_backfill(tmp_path):
    db_path = tmp_path / "v2.sqlite"
    cfg, foundation = initialize(db_path)
    db = sqlite3.connect(db_path)
    activated = storage.build_manifest(cfg, "2026-09-01T00:00:00+00:00")
    activated.update({
        "manifest_id": "active-manifest",
        "manifest_status": "OFFICIAL_COHORT_ACTIVE",
        "official_cohort_active": True,
        "official_cohort_start_timestamp": "2026-09-01T00:00:00+00:00",
        "supersedes_manifest_id": foundation["manifest_id"],
    })
    db.execute(
        "INSERT INTO v2_strategy_manifest VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (activated["manifest_id"], activated["strategy_id"], activated["hypothesis_version"],
         activated["schema_version"], activated["manifest_status"], activated["official_cohort_start_timestamp"],
         activated["config_sha256"], storage.canonical_json(cfg), storage.canonical_json(activated),
         activated["created_at_utc"], activated["supersedes_manifest_id"]),
    )
    columns = "snapshot_id,manifest_id,cohort_type,asset,kraken_pair,market_data_cutoff,decision_timestamp,eligibility_status,canonical_payload_json,payload_sha256,created_at_utc"
    db.execute(f"INSERT INTO v2_decision_snapshots({columns}) VALUES(?,?,?,?,?,?,?,?,?,?,?)", ("old-snap", activated["manifest_id"], "OFFICIAL_FORWARD", "BTC", "BTCUSD", "2026-08-31T12:00:00Z", "2026-09-01T00:00:01Z", "ELIGIBLE", "{}", "a" * 64, "2026-09-01T00:00:01Z"))
    old_signal = ("old-sig", "old-snap", activated["manifest_id"], "OFFICIAL_FORWARD", "BTC", "BTCUSD", "batch", "2026-08-31T12:00:01Z", 1, 0, "b" * 64, "2026-09-01T00:00:01Z")
    with pytest.raises(sqlite3.IntegrityError, match="HISTORICAL_BACKFILL_PROHIBITED"):
        db.execute("INSERT INTO v2_signals VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", old_signal)
    assert db.execute("SELECT count(*) FROM v2_signals").fetchone()[0] == 0
    db.close()


def test_activation_is_append_only_utc_and_permanent(tmp_path):
    db_path = tmp_path / "v2.sqlite"
    cfg, foundation, active = activate(db_path)
    assert active["supersedes_manifest_id"] == foundation["manifest_id"]
    assert active["official_cohort_start_timestamp"] == "2026-09-01T00:00:00+00:00"
    with pytest.raises(ValueError, match="already permanently activated"):
        storage.append_activation_manifest(db_path, cfg, "2026-09-02T00:00:00Z", "2026-09-01T12:00:00Z")
    with pytest.raises(ValueError, match="cannot precede"):
        storage.append_activation_manifest(tmp_path / "other.sqlite", cfg, "2026-08-30T00:00:00Z", "2026-08-31T00:00:00Z")


def test_config_has_no_combined_v1_cost():
    cfg = config()
    costs = cfg["cost_model"]
    assert costs == {
        "combined_v1_cost_allowed": False,
        "entry_fee_pct": 0.2,
        "entry_slippage_stored_separately": True,
        "exit_fee_pct": 0.2,
        "exit_slippage_stored_separately": True,
        "reference_notional_usd": 10000.0,
    }
    assert "estimated_round_trip_cost_pct" not in json.dumps(cfg)


def test_foundation_has_no_network_private_api_or_execution_dependencies():
    path = ROOT / "scripts/range_fixed_5_v2_storage.py"
    source = path.read_text()
    tree = ast.parse(source)
    imports = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    } | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert not imports & {"requests", "urllib", "httpx", "socket"}
    forbidden_import_fragments = {"order", "position_manager", "paper_position_tracker", "trading", "krakenex", "ccxt"}
    assert not any(fragment in name.lower() for name in imports for fragment in forbidden_import_fragments)
    lowered = source.lower()
    assert "/private/" not in lowered
    assert "addorder" not in lowered
    assert "api_key" not in lowered
    assert "api_secret" not in lowered


@pytest.mark.archive
def test_production_manifest_matches_config():
    cfg = config()
    manifest = json.loads((ROOT / "FORWARD_RESEARCH/RANGE_FIXED_5_FORWARD_V2/strategy_manifest.json").read_text())
    assert manifest["config_sha256"] == storage.sha256_json(cfg)
    assert manifest["strategy_id"] == cfg["strategy_id"]
    assert manifest["hypothesis_version"] == cfg["hypothesis_version"]
    assert manifest["schema_version"] == cfg["schema_version"]
