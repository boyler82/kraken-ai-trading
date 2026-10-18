from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config/range_fixed_5_forward_v2.json"
V2_DIR = ROOT / "FORWARD_RESEARCH/RANGE_FIXED_5_FORWARD_V2"
MANIFEST_PATH = V2_DIR / "strategy_manifest.json"
DB_PATH = V2_DIR / "range_fixed_5_forward_v2.sqlite"
PHASE4_CONFIG_PATH = ROOT / "config/range_fixed_5_forward_v2_phase4.json"
PHASE4_MANIFEST_PATH = V2_DIR / "phase4_manifest.json"
CLOCK_CONFIG_PATH = ROOT / "config/range_fixed_5_forward_v2_clock_safety.json"
CLOCK_MANIFEST_PATH = V2_DIR / "clock_safety_manifest.json"

STRATEGY_ID = "RANGE_FIXED_5_FORWARD_V2"
OFFICIAL_COHORT = "OFFICIAL_FORWARD"


def canonical_json(value: Any) -> str:
    """Return the sole canonical representation used by V2 hashes."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(path.read_text())
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    expected = {
        "strategy_id": STRATEGY_ID,
        "accepted_rqi_classifications": ["ACCEPTABLE_RANGE", "GOOD_RANGE", "EXCELLENT_RANGE"],
        "target_pct": 5.0,
        "stop_pct": 2.0,
        "max_holding_hours": 120,
        "market_regime_is_entry_filter": False,
        "order_placement": "PROHIBITED",
        "historical_backfill_official_cohort": "PROHIBITED",
        "entry_convention": "FIRST_VALID_KRAKEN_BEST_ASK_AFTER_SIGNAL_CREATION",
        "same_bar_ambiguous_tp_sl": "CONSERVATIVE_STOP_FIRST",
        "official_cohort_start_timestamp": None,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"invalid frozen V2 setting: {key}")
    if config.get("range_position") != {"lower_inclusive_pct": 0.0, "upper_exclusive_pct": 50.0}:
        raise ValueError("invalid frozen V2 range position")
    costs = config.get("cost_model", {})
    if costs.get("reference_notional_usd") != 10000.0 or costs.get("entry_fee_pct") != 0.2 or costs.get("exit_fee_pct") != 0.2:
        raise ValueError("invalid frozen V2 cost model")
    if costs.get("combined_v1_cost_allowed") is not False:
        raise ValueError("V1 combined cost is prohibited in V2")
    if not config.get("hypothesis_version") or not config.get("schema_version"):
        raise ValueError("V2 hypothesis_version and schema_version are required")


def build_manifest(config: dict[str, Any], created_at_utc: str | None = None) -> dict[str, Any]:
    validate_config(config)
    created = created_at_utc or datetime.now(timezone.utc).isoformat()
    return {
        "manifest_id": hashlib.sha256(f"{STRATEGY_ID}|FOUNDATION|{sha256_json(config)}".encode()).hexdigest()[:32],
        "strategy_id": STRATEGY_ID,
        "hypothesis_version": config["hypothesis_version"],
        "schema_version": config["schema_version"],
        "manifest_status": "FOUNDATION_ONLY",
        "official_cohort_start_timestamp": None,
        "official_cohort_active": False,
        "historical_backfill_official_cohort": "PROHIBITED",
        "order_placement": "PROHIBITED",
        "config_path": "config/range_fixed_5_forward_v2.json",
        "config_sha256": sha256_json(config),
        "canonicalization": "UTF8_JSON_SORTED_KEYS_COMPACT_NO_NAN_V1",
        "created_at_utc": created,
        "supersedes_manifest_id": None,
        "notes": "Phases 1-2 foundation only. No signals may be created until an activation manifest is appended.",
    }


SCHEMA = """
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS v2_strategy_manifest(
  manifest_id TEXT PRIMARY KEY,
  strategy_id TEXT NOT NULL CHECK(strategy_id='RANGE_FIXED_5_FORWARD_V2'),
  hypothesis_version TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  manifest_status TEXT NOT NULL CHECK(manifest_status IN ('FOUNDATION_ONLY','OFFICIAL_COHORT_ACTIVE')),
  official_cohort_start_timestamp TEXT,
  config_sha256 TEXT NOT NULL CHECK(length(config_sha256)=64),
  config_json TEXT NOT NULL,
  manifest_json TEXT NOT NULL,
  created_at_utc TEXT NOT NULL,
  supersedes_manifest_id TEXT REFERENCES v2_strategy_manifest(manifest_id),
  CHECK((manifest_status='FOUNDATION_ONLY' AND official_cohort_start_timestamp IS NULL) OR
        (manifest_status='OFFICIAL_COHORT_ACTIVE' AND official_cohort_start_timestamp IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS v2_strategy_extensions(
  extension_manifest_id TEXT PRIMARY KEY,
  extension_id TEXT NOT NULL UNIQUE,
  extension_version TEXT NOT NULL,
  base_strategy_id TEXT NOT NULL CHECK(base_strategy_id='RANGE_FIXED_5_FORWARD_V2'),
  base_config_sha256 TEXT NOT NULL CHECK(length(base_config_sha256)=64),
  extension_config_sha256 TEXT NOT NULL CHECK(length(extension_config_sha256)=64),
  extension_config_json TEXT NOT NULL,
  extension_manifest_json TEXT NOT NULL,
  created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v2_decision_snapshots(
  snapshot_id TEXT PRIMARY KEY,
  manifest_id TEXT NOT NULL REFERENCES v2_strategy_manifest(manifest_id),
  cohort_type TEXT NOT NULL CHECK(cohort_type='OFFICIAL_FORWARD'),
  asset TEXT NOT NULL,
  kraken_pair TEXT NOT NULL,
  market_data_cutoff TEXT NOT NULL,
  decision_timestamp TEXT NOT NULL,
  eligibility_status TEXT NOT NULL,
  canonical_payload_json TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL CHECK(length(payload_sha256)=64),
  created_at_utc TEXT NOT NULL,
  strategy_id TEXT,
  pair TEXT,
  source_candle_open_timestamp TEXT,
  source_candle_completion_timestamp TEXT,
  source_data_observed_at TEXT,
  feature_calculation_started_at TEXT,
  feature_calculation_completed_at TEXT,
  reference_close REAL,
  atr14 REAL,
  range_low REAL,
  range_high REAL,
  range_midpoint REAL,
  range_position_pct REAL,
  range_valid INTEGER,
  range_state TEXT,
  rqi_score REAL,
  rqi_classification TEXT,
  rqi_position_zone TEXT,
  freshness_status TEXT,
  liquidity_eligible INTEGER,
  spread_eligible INTEGER,
  universe_eligibility INTEGER,
  market_regime TEXT,
  btc_market_state TEXT,
  eligible_for_future_signal INTEGER,
  eligibility_reasons_json TEXT,
  source_hashes_json TEXT,
  canonical_input_hash TEXT,
  feature_snapshot_hash TEXT,
  code_version TEXT,
  configuration_hash TEXT,
  UNIQUE(manifest_id, asset, decision_timestamp, payload_sha256)
);

CREATE TABLE IF NOT EXISTS v2_signals(
  signal_id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL UNIQUE REFERENCES v2_decision_snapshots(snapshot_id),
  manifest_id TEXT NOT NULL REFERENCES v2_strategy_manifest(manifest_id),
  cohort_type TEXT NOT NULL CHECK(cohort_type='OFFICIAL_FORWARD'),
  asset TEXT NOT NULL,
  kraken_pair TEXT NOT NULL,
  signal_batch_id TEXT NOT NULL,
  signal_timestamp TEXT NOT NULL,
  simultaneous_signal_count INTEGER NOT NULL CHECK(simultaneous_signal_count>=1),
  same_asset_active_episode INTEGER NOT NULL CHECK(same_asset_active_episode IN (0,1)),
  signal_sha256 TEXT NOT NULL CHECK(length(signal_sha256)=64),
  created_at_utc TEXT NOT NULL,
  UNIQUE(manifest_id, asset, signal_timestamp, snapshot_id)
);

CREATE TABLE IF NOT EXISTS v2_entry_observations(
  entry_observation_id TEXT PRIMARY KEY,
  signal_id TEXT NOT NULL UNIQUE REFERENCES v2_signals(signal_id),
  request_started_at TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  best_bid REAL NOT NULL CHECK(best_bid>0),
  best_ask REAL NOT NULL CHECK(best_ask>=best_bid),
  entry_reference_price REAL NOT NULL CHECK(entry_reference_price=best_ask),
  target_price REAL NOT NULL CHECK(target_price>entry_reference_price),
  stop_price REAL NOT NULL CHECK(stop_price<entry_reference_price),
  expiry_timestamp TEXT NOT NULL,
  raw_response_sha256 TEXT NOT NULL CHECK(length(raw_response_sha256)=64),
  canonical_payload_json TEXT NOT NULL,
  created_at_utc TEXT NOT NULL,
  pair TEXT,
  response_received_at TEXT,
  spread_pct REAL,
  quote_status TEXT,
  accepted_attempt_id TEXT,
  gross_reward_pct REAL,
  gross_risk_pct REAL,
  gross_reward_risk_ratio REAL,
  CHECK(julianday(observed_at)>=julianday(request_started_at))
);

CREATE TABLE IF NOT EXISTS v2_quote_attempts(
  attempt_id TEXT PRIMARY KEY,
  signal_id TEXT NOT NULL REFERENCES v2_signals(signal_id),
  attempt_number INTEGER NOT NULL CHECK(attempt_number BETWEEN 1 AND 3),
  pair TEXT NOT NULL,
  request_started_at TEXT NOT NULL,
  response_received_at TEXT NOT NULL,
  quote_status TEXT NOT NULL,
  best_bid REAL,
  best_ask REAL,
  spread_pct REAL,
  raw_response_sha256 TEXT,
  error_code TEXT,
  canonical_payload_json TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL CHECK(length(payload_sha256)=64),
  created_at_utc TEXT NOT NULL,
  UNIQUE(signal_id,attempt_number),
  CHECK(julianday(response_received_at)>=julianday(request_started_at))
);

CREATE TABLE IF NOT EXISTS v2_monitor_events(
  event_id TEXT PRIMARY KEY,
  signal_id TEXT NOT NULL REFERENCES v2_signals(signal_id),
  event_type TEXT NOT NULL,
  event_timestamp TEXT NOT NULL,
  previous_event_id TEXT REFERENCES v2_monitor_events(event_id),
  source_data_sha256 TEXT CHECK(source_data_sha256 IS NULL OR length(source_data_sha256)=64),
  canonical_payload_json TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL CHECK(length(payload_sha256)=64),
  created_at_utc TEXT NOT NULL,
  UNIQUE(signal_id, event_type, event_timestamp, payload_sha256)
);

CREATE TABLE IF NOT EXISTS v2_completed_outcomes(
  outcome_id TEXT PRIMARY KEY,
  signal_id TEXT NOT NULL UNIQUE REFERENCES v2_signals(signal_id),
  terminal_event_id TEXT NOT NULL UNIQUE REFERENCES v2_monitor_events(event_id),
  terminal_outcome TEXT NOT NULL CHECK(terminal_outcome IN ('TARGET_HIT','STOP_HIT','STRUCTURE_INVALIDATION','TIME_EXIT')),
  entry_timestamp TEXT NOT NULL,
  exit_timestamp TEXT NOT NULL,
  entry_reference_price REAL NOT NULL CHECK(entry_reference_price>0),
  exit_reference_price REAL NOT NULL CHECK(exit_reference_price>0),
  gross_return_pct REAL NOT NULL,
  entry_fee_pct REAL NOT NULL CHECK(entry_fee_pct>=0),
  exit_fee_pct REAL NOT NULL CHECK(exit_fee_pct>=0),
  entry_slippage_pct REAL NOT NULL CHECK(entry_slippage_pct>=0),
  exit_slippage_pct REAL NOT NULL CHECK(exit_slippage_pct>=0),
  total_fee_pct REAL NOT NULL CHECK(total_fee_pct>=0),
  total_slippage_pct REAL NOT NULL CHECK(total_slippage_pct>=0),
  total_transaction_cost_pct REAL NOT NULL CHECK(total_transaction_cost_pct>=0),
  net_return_pct REAL NOT NULL,
  outcome_sha256 TEXT NOT NULL CHECK(length(outcome_sha256)=64),
  created_at_utc TEXT NOT NULL,
  CHECK(julianday(exit_timestamp)>=julianday(entry_timestamp))
);

CREATE TABLE IF NOT EXISTS v2_validation_snapshots(
  validation_snapshot_id TEXT PRIMARY KEY,
  manifest_id TEXT NOT NULL REFERENCES v2_strategy_manifest(manifest_id),
  cohort_cutoff_timestamp TEXT NOT NULL,
  completed_outcome_count INTEGER NOT NULL CHECK(completed_outcome_count>=0),
  distinct_signal_batch_count INTEGER NOT NULL CHECK(distinct_signal_batch_count>=0),
  methodology_version TEXT NOT NULL,
  canonical_payload_json TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL CHECK(length(payload_sha256)=64),
  created_at_utc TEXT NOT NULL,
  UNIQUE(manifest_id, cohort_cutoff_timestamp, methodology_version)
);

CREATE VIEW IF NOT EXISTS v2_open_observations AS
SELECT s.signal_id, s.snapshot_id, s.asset, s.kraken_pair, s.signal_batch_id,
       s.signal_timestamp, e.observed_at AS entry_timestamp,
       e.entry_reference_price, e.target_price, e.stop_price, e.expiry_timestamp
FROM v2_signals s
JOIN v2_entry_observations e USING(signal_id)
LEFT JOIN v2_completed_outcomes o USING(signal_id)
WHERE o.signal_id IS NULL;

CREATE TRIGGER IF NOT EXISTS v2_signals_require_activated_cohort
BEFORE INSERT ON v2_signals
BEGIN
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM v2_strategy_manifest m
    WHERE m.manifest_id=NEW.manifest_id
      AND m.manifest_status='OFFICIAL_COHORT_ACTIVE'
      AND m.official_cohort_start_timestamp IS NOT NULL
  ) THEN RAISE(ABORT,'OFFICIAL_COHORT_NOT_ACTIVATED') END;
  SELECT CASE WHEN julianday(NEW.signal_timestamp) IS NULL
    THEN RAISE(ABORT,'INVALID_SIGNAL_TIMESTAMP') END;
  SELECT CASE WHEN (SELECT manifest_id FROM v2_decision_snapshots WHERE snapshot_id=NEW.snapshot_id) != NEW.manifest_id
    THEN RAISE(ABORT,'SIGNAL_SNAPSHOT_MANIFEST_MISMATCH') END;
  SELECT CASE WHEN julianday(NEW.signal_timestamp) < julianday((
    SELECT official_cohort_start_timestamp FROM v2_strategy_manifest WHERE manifest_id=NEW.manifest_id
  )) THEN RAISE(ABORT,'HISTORICAL_BACKFILL_PROHIBITED') END;
  SELECT CASE WHEN julianday(NEW.signal_timestamp) < julianday((
    SELECT decision_timestamp FROM v2_decision_snapshots WHERE snapshot_id=NEW.snapshot_id
  )) THEN RAISE(ABORT,'SIGNAL_BEFORE_DECISION_PROHIBITED') END;
END;

CREATE TRIGGER IF NOT EXISTS v2_decisions_require_activated_cohort
BEFORE INSERT ON v2_decision_snapshots
BEGIN
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM v2_strategy_manifest m
    WHERE m.manifest_id=NEW.manifest_id
      AND m.manifest_status='OFFICIAL_COHORT_ACTIVE'
      AND m.official_cohort_start_timestamp IS NOT NULL
  ) THEN RAISE(ABORT,'OFFICIAL_COHORT_NOT_ACTIVATED') END;
  SELECT CASE WHEN julianday(NEW.decision_timestamp) IS NULL
    THEN RAISE(ABORT,'INVALID_DECISION_TIMESTAMP') END;
  SELECT CASE WHEN julianday(NEW.decision_timestamp) < julianday((
    SELECT official_cohort_start_timestamp FROM v2_strategy_manifest WHERE manifest_id=NEW.manifest_id
  )) THEN RAISE(ABORT,'HISTORICAL_BACKFILL_PROHIBITED') END;
END;
"""

IMMUTABLE_TABLES = (
    "v2_strategy_manifest", "v2_strategy_extensions", "v2_decision_snapshots", "v2_signals", "v2_entry_observations", "v2_quote_attempts",
    "v2_monitor_events", "v2_completed_outcomes", "v2_validation_snapshots",
)

SNAPSHOT_COLUMNS = {
    "strategy_id": "TEXT", "pair": "TEXT", "source_candle_open_timestamp": "TEXT",
    "source_candle_completion_timestamp": "TEXT", "source_data_observed_at": "TEXT",
    "feature_calculation_started_at": "TEXT", "feature_calculation_completed_at": "TEXT",
    "reference_close": "REAL", "atr14": "REAL", "range_low": "REAL", "range_high": "REAL",
    "range_midpoint": "REAL", "range_position_pct": "REAL", "range_valid": "INTEGER",
    "range_state": "TEXT", "rqi_score": "REAL", "rqi_classification": "TEXT",
    "rqi_position_zone": "TEXT", "freshness_status": "TEXT", "liquidity_eligible": "INTEGER",
    "spread_eligible": "INTEGER", "universe_eligibility": "INTEGER", "market_regime": "TEXT",
    "btc_market_state": "TEXT", "eligible_for_future_signal": "INTEGER",
    "eligibility_reasons_json": "TEXT", "source_hashes_json": "TEXT",
    "canonical_input_hash": "TEXT", "feature_snapshot_hash": "TEXT", "code_version": "TEXT",
    "configuration_hash": "TEXT", "hypothesis_version": "TEXT",
}

ENTRY_COLUMNS = {
    "pair": "TEXT", "response_received_at": "TEXT", "spread_pct": "REAL", "quote_status": "TEXT",
    "accepted_attempt_id": "TEXT", "gross_reward_pct": "REAL", "gross_risk_pct": "REAL",
    "gross_reward_risk_ratio": "REAL",
}

OUTCOME_COLUMNS = {
    "total_fee_pct": "REAL CHECK(total_fee_pct>=0)",
    "total_slippage_pct": "REAL CHECK(total_slippage_pct>=0)",
}


def _immutability_schema() -> str:
    statements = []
    for table in IMMUTABLE_TABLES:
        for operation in ("UPDATE", "DELETE"):
            statements.append(
                f"CREATE TRIGGER IF NOT EXISTS {table}_reject_{operation.lower()} "
                f"BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'APPEND_ONLY:{table}'); END;"
            )
    return "\n".join(statements)


def initialize_database(db_path: Path, config: dict[str, Any], manifest: dict[str, Any]) -> None:
    validate_config(config)
    if manifest.get("config_sha256") != sha256_json(config):
        raise ValueError("manifest/config hash mismatch")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path)
    try:
        db.executescript(SCHEMA + "\n" + _immutability_schema())
        existing_columns = {row[1] for row in db.execute("PRAGMA table_info(v2_decision_snapshots)")}
        for name, column_type in SNAPSHOT_COLUMNS.items():
            if name not in existing_columns:
                db.execute(f"ALTER TABLE v2_decision_snapshots ADD COLUMN {name} {column_type}")
        entry_columns = {row[1] for row in db.execute("PRAGMA table_info(v2_entry_observations)")}
        for name, column_type in ENTRY_COLUMNS.items():
            if name not in entry_columns:
                db.execute(f"ALTER TABLE v2_entry_observations ADD COLUMN {name} {column_type}")
        outcome_columns = {row[1] for row in db.execute("PRAGMA table_info(v2_completed_outcomes)")}
        for name, column_type in OUTCOME_COLUMNS.items():
            if name not in outcome_columns:
                db.execute(f"ALTER TABLE v2_completed_outcomes ADD COLUMN {name} {column_type}")
        db.execute(
            """INSERT OR IGNORE INTO v2_strategy_manifest
               (manifest_id,strategy_id,hypothesis_version,schema_version,manifest_status,
                official_cohort_start_timestamp,config_sha256,config_json,manifest_json,
                created_at_utc,supersedes_manifest_id)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                manifest["manifest_id"], manifest["strategy_id"], manifest["hypothesis_version"],
                manifest["schema_version"], manifest["manifest_status"],
                manifest["official_cohort_start_timestamp"], manifest["config_sha256"],
                canonical_json(config), canonical_json(manifest), manifest["created_at_utc"],
                manifest["supersedes_manifest_id"],
            ),
        )
        stored = db.execute("SELECT config_sha256,manifest_json FROM v2_strategy_manifest WHERE manifest_id=?", (manifest["manifest_id"],)).fetchone()
        if stored != (manifest["config_sha256"], canonical_json(manifest)):
            raise ValueError("existing immutable manifest differs from requested manifest")
        db.commit()
    finally:
        db.close()


def active_manifest(db: sqlite3.Connection) -> Optional[sqlite3.Row]:
    db.row_factory = sqlite3.Row
    return db.execute(
        "SELECT * FROM v2_strategy_manifest WHERE manifest_status='OFFICIAL_COHORT_ACTIVE' ORDER BY created_at_utc,manifest_id LIMIT 1"
    ).fetchone()


def append_activation_manifest(
    db_path: Path, config: dict[str, Any], start_timestamp: str,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Append the one permanent cohort activation; never update a prior manifest."""
    validate_config(config)
    start = datetime.fromisoformat(start_timestamp.replace("Z", "+00:00"))
    if start.tzinfo is None or start.utcoffset() is None:
        raise ValueError("cohort start must be timezone-aware UTC")
    if start.utcoffset().total_seconds() != 0:
        raise ValueError("cohort start must use UTC")
    created = datetime.fromisoformat((created_at_utc or datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00"))
    if created.tzinfo is None or created.utcoffset() is None or created.utcoffset().total_seconds() != 0:
        raise ValueError("activation creation time must be timezone-aware UTC")
    if start < created:
        raise ValueError("official cohort start cannot precede activation creation time")
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        if active_manifest(db):
            raise ValueError("official cohort is already permanently activated")
        foundation = db.execute(
            "SELECT * FROM v2_strategy_manifest ORDER BY created_at_utc,manifest_id LIMIT 1"
        ).fetchone()
        if not foundation or foundation["config_sha256"] != sha256_json(config):
            raise ValueError("foundation manifest/config hash mismatch")
        extension = db.execute(
            "SELECT * FROM v2_strategy_extensions WHERE extension_id='RANGE_FIXED_5_FORWARD_V2_PHASE4_ENTRY_V1'"
        ).fetchone()
        if not extension:
            raise ValueError("Phase-4 policy extension must be installed before cohort activation")
        clock_extension = db.execute(
            "SELECT * FROM v2_strategy_extensions WHERE extension_id='RANGE_FIXED_5_FORWARD_V2_CLOCK_SAFETY_V1'"
        ).fetchone()
        if not clock_extension:
            raise ValueError("clock-safety extension must be installed before cohort activation")
        start_text = start.astimezone(timezone.utc).isoformat()
        created_text = created.astimezone(timezone.utc).isoformat()
        manifest = {
            "manifest_id": hashlib.sha256(
                f"{STRATEGY_ID}|ACTIVATION|{start_text}|{foundation['manifest_id']}|{sha256_json(config)}".encode()
            ).hexdigest()[:32],
            "strategy_id": STRATEGY_ID,
            "hypothesis_version": config["hypothesis_version"],
            "schema_version": config["schema_version"],
            "manifest_status": "OFFICIAL_COHORT_ACTIVE",
            "official_cohort_start_timestamp": start_text,
            "official_cohort_active": True,
            "historical_backfill_official_cohort": "PROHIBITED",
            "order_placement": "PROHIBITED",
            "config_path": "config/range_fixed_5_forward_v2.json",
            "config_sha256": sha256_json(config),
            "phase4_extension_manifest_id": extension["extension_manifest_id"],
            "phase4_extension_config_sha256": extension["extension_config_sha256"],
            "clock_safety_extension_manifest_id": clock_extension["extension_manifest_id"],
            "clock_safety_extension_config_sha256": clock_extension["extension_config_sha256"],
            "canonicalization": "UTF8_JSON_SORTED_KEYS_COMPACT_NO_NAN_V1",
            "created_at_utc": created_text,
            "supersedes_manifest_id": foundation["manifest_id"],
            "notes": "Permanent append-only official forward cohort activation.",
        }
        db.execute(
            "INSERT INTO v2_strategy_manifest VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (manifest["manifest_id"], manifest["strategy_id"], manifest["hypothesis_version"],
             manifest["schema_version"], manifest["manifest_status"], start_text,
             manifest["config_sha256"], canonical_json(config), canonical_json(manifest),
             created_text, manifest["supersedes_manifest_id"]),
        )
        db.commit()
        return manifest
    finally:
        db.close()


def load_phase4_config(path: Path = PHASE4_CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(path.read_text())
    validate_phase4_config(config)
    return config


def validate_phase4_config(config: dict[str, Any]) -> None:
    policy = config.get("quote_attempt_policy", {})
    entry = config.get("entry_observation", {})
    if config.get("base_strategy_id") != STRATEGY_ID:
        raise ValueError("invalid Phase-4 base strategy")
    if policy != {"delay_between_attempts_seconds": 1.0, "maximum_attempts": 3,
                  "same_scanner_execution": True, "unbounded_retries": False}:
        raise ValueError("invalid frozen Phase-4 quote attempt policy")
    if entry.get("entry_side") != "BEST_ASK" or entry.get("maximum_spread_pct") != 0.75:
        raise ValueError("invalid frozen Phase-4 entry observation")
    if entry.get("public_endpoint") != "https://api.kraken.com/0/public/Ticker":
        raise ValueError("only the public Kraken Ticker endpoint is allowed")


def install_phase4_extension(
    db_path: Path, base_config: dict[str, Any], phase4_config: dict[str, Any],
    created_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    validate_phase4_config(phase4_config)
    extension_hash = sha256_json(phase4_config)
    existing_db = sqlite3.connect(db_path)
    existing_db.row_factory = sqlite3.Row
    try:
        existing = existing_db.execute(
            "SELECT * FROM v2_strategy_extensions WHERE extension_id=?", (phase4_config["extension_id"],)
        ).fetchone()
        if existing:
            if existing["base_config_sha256"] != sha256_json(base_config) or existing["extension_config_sha256"] != extension_hash:
                raise ValueError("existing immutable Phase-4 extension differs")
            return json.loads(existing["extension_manifest_json"])
    finally:
        existing_db.close()
    created = created_at_utc or datetime.now(timezone.utc).isoformat()
    manifest = {
        "extension_manifest_id": hashlib.sha256(
            f"{phase4_config['extension_id']}|{extension_hash}|{sha256_json(base_config)}".encode()
        ).hexdigest()[:32],
        "extension_id": phase4_config["extension_id"],
        "extension_version": phase4_config["extension_version"],
        "base_strategy_id": STRATEGY_ID,
        "base_config_sha256": sha256_json(base_config),
        "extension_config_sha256": extension_hash,
        "created_at_utc": created,
        "cohort_status": "INACTIVE",
        "notes": "Append-only pre-cohort Phase-4 entry observation policy; no activation and no signals.",
    }
    db = sqlite3.connect(db_path)
    try:
        db.execute(
            "INSERT OR IGNORE INTO v2_strategy_extensions VALUES(?,?,?,?,?,?,?,?,?)",
            (manifest["extension_manifest_id"], manifest["extension_id"], manifest["extension_version"],
             STRATEGY_ID, manifest["base_config_sha256"], extension_hash, canonical_json(phase4_config),
             canonical_json(manifest), created),
        )
        stored = db.execute(
            "SELECT extension_config_sha256,extension_manifest_json FROM v2_strategy_extensions WHERE extension_manifest_id=?",
            (manifest["extension_manifest_id"],),
        ).fetchone()
        if stored != (extension_hash, canonical_json(manifest)):
            raise ValueError("existing immutable Phase-4 extension differs")
        db.commit()
        return manifest
    finally:
        db.close()


def install_clock_safety_extension(
    db_path: Path, base_config: dict[str, Any], clock_config: dict[str, Any],
    created_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    from range_fixed_5_v2_clock import validate_clock_config

    validate_clock_config(clock_config)
    extension_hash = sha256_json(clock_config)
    extension_id = clock_config["extension_id"]
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        existing = db.execute("SELECT * FROM v2_strategy_extensions WHERE extension_id=?", (extension_id,)).fetchone()
        if existing:
            if existing["base_config_sha256"] != sha256_json(base_config) or existing["extension_config_sha256"] != extension_hash:
                raise ValueError("existing immutable clock-safety extension differs")
            return json.loads(existing["extension_manifest_json"])
        created = created_at_utc or datetime.now(timezone.utc).isoformat()
        manifest = {
            "extension_manifest_id": hashlib.sha256(
                f"{extension_id}|{extension_hash}|{sha256_json(base_config)}".encode()
            ).hexdigest()[:32],
            "extension_id": extension_id,
            "extension_version": clock_config["extension_version"],
            "base_strategy_id": STRATEGY_ID,
            "base_config_sha256": sha256_json(base_config),
            "extension_config_sha256": extension_hash,
            "created_at_utc": created,
            "cohort_status": "INACTIVE",
            "notes": "Append-only pre-cohort operational clock-safety policy; not a strategy parameter.",
        }
        db.execute(
            "INSERT INTO v2_strategy_extensions VALUES(?,?,?,?,?,?,?,?,?)",
            (manifest["extension_manifest_id"], extension_id, manifest["extension_version"], STRATEGY_ID,
             manifest["base_config_sha256"], extension_hash, canonical_json(clock_config),
             canonical_json(manifest), created),
        )
        db.commit()
        return manifest
    finally:
        db.close()


def initialize_foundation(root: Path = ROOT) -> tuple[Path, Path]:
    config_path = root / "config/range_fixed_5_forward_v2.json"
    output_dir = root / "FORWARD_RESEARCH/RANGE_FIXED_5_FORWARD_V2"
    manifest_path = output_dir / "strategy_manifest.json"
    db_path = output_dir / "range_fixed_5_forward_v2.sqlite"
    config = load_config(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        manifest = build_manifest(config)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n")
    initialize_database(db_path, config, manifest)
    phase4_path = root / "config/range_fixed_5_forward_v2_phase4.json"
    if phase4_path.exists():
        phase4_config = json.loads(phase4_path.read_text())
        extension = install_phase4_extension(db_path, config, phase4_config)
        extension_path = output_dir / "phase4_manifest.json"
        encoded = json.dumps(extension, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if extension_path.exists() and extension_path.read_text() != encoded:
            raise ValueError("existing immutable Phase-4 manifest file differs")
        if not extension_path.exists():
            extension_path.write_text(encoded)
    clock_config_path = root / "config/range_fixed_5_forward_v2_clock_safety.json"
    clock_manifest_path = output_dir / "clock_safety_manifest.json"
    if clock_config_path.exists():
        clock_config = json.loads(clock_config_path.read_text())
        clock_extension = install_clock_safety_extension(db_path, config, clock_config)
        clock_encoded = json.dumps(clock_extension, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if clock_manifest_path.exists() and clock_manifest_path.read_text() != clock_encoded:
            raise ValueError("existing immutable clock-safety manifest file differs")
        if not clock_manifest_path.exists():
            clock_manifest_path.write_text(clock_encoded)
    return manifest_path, db_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the RANGE_FIXED_5_FORWARD_V2 storage foundation only.")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    manifest, database = initialize_foundation(args.root)
    print(f"V2 foundation initialized: {manifest} | {database}")
    print("Official cohort inactive; signals are prohibited.")


if __name__ == "__main__":
    main()
