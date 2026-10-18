from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from consolidation_range_engine import atr14, completed_4h_bars, detect_range
from range_fixed_5_v2_storage import (
    DB_PATH, ROOT, STRATEGY_ID, active_manifest, canonical_json, initialize_foundation,
    load_config, sha256_json,
)
from range_quality_index import calculate_rqi


CODE_VERSION = "RANGE_FIXED_5_V2_SNAPSHOT_1.1.0"
MIN_QUOTE_VOLUME_24H = 250_000.0
MAX_BID_ASK_SPREAD_PCT = 0.75
REQUIRED_FEATURES = (
    "asset", "pair", "market_data_cutoff", "source_candle_open_timestamp",
    "source_candle_completion_timestamp", "source_data_observed_at",
    "feature_calculation_started_at", "feature_calculation_completed_at", "decision_timestamp",
    "reference_close", "atr14", "range_low", "range_high", "range_midpoint",
    "range_position_pct", "range_valid", "range_state", "rqi_score", "rqi_classification",
    "rqi_position_zone", "freshness_status", "liquidity_eligible", "spread_eligible",
    "universe_eligibility", "source_hashes", "component_cutoffs",
)
ECONOMIC_INPUT_FIELDS = (
    "asset", "pair", "market_data_cutoff", "source_candle_open_timestamp",
    "source_candle_completion_timestamp", "source_data_observed_at", "source_hashes",
    "component_cutoffs", "quote_volume_24h", "bid_ask_spread_pct", "universe_eligibility",
    "market_regime", "btc_market_state",
)


def utc(value: Any) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return stamp.tz_convert("UTC")


def iso(value: Any) -> str:
    return utc(value).isoformat()


def frame_hash(frame: pd.DataFrame) -> str:
    rows = []
    for record in frame.copy().to_dict("records"):
        rows.append({key: (iso(value) if key == "timestamp" and value is not None else value) for key, value in record.items()})
    return sha256_json(rows)


def timestamp_legality(feature: dict[str, Any]) -> tuple[bool, list[str]]:
    names = (
        "source_candle_open_timestamp", "source_candle_completion_timestamp", "source_data_observed_at",
        "feature_calculation_started_at", "feature_calculation_completed_at", "decision_timestamp",
        "market_data_cutoff",
    )
    try:
        stamps = {name: utc(feature[name]) for name in names}
        availability = [utc(value) for value in feature.get("feature_availability_timestamps", {}).values()]
        cutoffs = [utc(value) for value in feature.get("component_cutoffs", {}).values()]
    except (KeyError, TypeError, ValueError):
        return False, ["NOT_ELIGIBLE_TIMESTAMP_ILLEGAL"]
    reasons = []
    if not stamps["source_candle_open_timestamp"] < stamps["source_candle_completion_timestamp"]:
        reasons.append("NOT_ELIGIBLE_TIMESTAMP_ILLEGAL")
    if stamps["source_data_observed_at"] < stamps["source_candle_completion_timestamp"]:
        reasons.append("NOT_ELIGIBLE_TIMESTAMP_ILLEGAL")
    if stamps["market_data_cutoff"] < stamps["source_candle_completion_timestamp"]:
        reasons.append("NOT_ELIGIBLE_TIMESTAMP_ILLEGAL")
    if stamps["feature_calculation_completed_at"] < stamps["feature_calculation_started_at"]:
        reasons.append("NOT_ELIGIBLE_TIMESTAMP_ILLEGAL")
    if stamps["decision_timestamp"] < max(stamps["source_data_observed_at"], stamps["feature_calculation_completed_at"]):
        reasons.append("NOT_ELIGIBLE_TIMESTAMP_ILLEGAL")
    if stamps["decision_timestamp"] == stamps["source_candle_open_timestamp"]:
        reasons.append("NOT_ELIGIBLE_TIMESTAMP_ILLEGAL")
    if any(value > stamps["decision_timestamp"] for value in availability):
        reasons.append("NOT_ELIGIBLE_TIMESTAMP_ILLEGAL")
    if not cutoffs or any(value != stamps["market_data_cutoff"] for value in cutoffs):
        reasons.append("NOT_ELIGIBLE_TIMESTAMP_ILLEGAL")
    return not reasons, sorted(set(reasons))


def eligibility(feature: dict[str, Any], config: dict[str, Any]) -> tuple[bool, list[str], str]:
    missing = [name for name in REQUIRED_FEATURES if feature.get(name) is None]
    rqi_not_applicable_for_invalid_range = (
        feature.get("range_valid") is False
        and feature.get("rqi_score") is None
        and feature.get("rqi_classification") == "NOT_APPLICABLE"
    )
    if rqi_not_applicable_for_invalid_range:
        missing = [name for name in missing if name != "rqi_score"]
    if missing:
        return False, ["NOT_ELIGIBLE_DATA_INCOMPLETE"], "NOT_ELIGIBLE_DATA_INCOMPLETE"
    legal, timestamp_reasons = timestamp_legality(feature)
    if not legal:
        return False, timestamp_reasons, "NOT_ELIGIBLE_TIMESTAMP_ILLEGAL"
    reasons = []
    low, high, price = float(feature["range_low"]), float(feature["range_high"]), float(feature["reference_close"])
    position = float(feature["range_position_pct"])
    if not bool(feature["range_valid"]):
        reasons.append("NOT_ELIGIBLE_RANGE_INVALID")
    if high <= low or price < low or price > high or position < 0 or position > 100:
        reasons.append("NOT_ELIGIBLE_PRICE_OUTSIDE_RANGE")
    elif position >= float(config["range_position"]["upper_exclusive_pct"]):
        reasons.append("NOT_ELIGIBLE_UPPER_HALF")
    if bool(feature["range_valid"]) and feature["rqi_classification"] not in config["accepted_rqi_classifications"]:
        reasons.append("NOT_ELIGIBLE_RQI")
    if str(feature["freshness_status"]).upper() != "FRESH":
        reasons.append("NOT_ELIGIBLE_STALE_DATA")
    if not bool(feature["liquidity_eligible"]):
        reasons.append("NOT_ELIGIBLE_LIQUIDITY")
    if not bool(feature["spread_eligible"]):
        reasons.append("NOT_ELIGIBLE_SPREAD")
    if not bool(feature["universe_eligibility"]):
        reasons.append("NOT_ELIGIBLE_UNIVERSE")
    reasons = sorted(set(reasons))
    if not reasons:
        status = "ELIGIBLE_FOR_FUTURE_SIGNAL"
    elif "NOT_ELIGIBLE_RANGE_INVALID" in reasons:
        status = "NOT_ELIGIBLE_RANGE_INVALID"
    else:
        status = reasons[0]
    return not reasons, reasons, status


def build_decision_snapshot(feature: dict[str, Any], config: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    eligible, reasons, status = eligibility(feature, config)
    source_hashes = feature.get("source_hashes") or {}
    # Economic identity excludes process-local audit clocks. Market availability is
    # represented by the deterministic source observation/completion timestamps and
    # synchronized component cutoffs already present below.
    canonical_inputs = {key: feature.get(key) for key in ECONOMIC_INPUT_FIELDS}
    canonical_inputs["configuration_hash"] = manifest["config_sha256"]
    canonical_input_hash = sha256_json(canonical_inputs)
    feature_values = {
        key: feature.get(key) for key in (
            "asset", "pair", "market_data_cutoff", "reference_close", "atr14", "range_low", "range_high",
            "range_midpoint", "range_position_pct", "range_valid", "range_state", "rqi_score",
            "rqi_classification", "rqi_position_zone", "freshness_status", "liquidity_eligible",
            "spread_eligible", "universe_eligibility", "market_regime", "btc_market_state",
        )
    }
    feature_values.update(eligible_for_future_signal=eligible, eligibility_reasons=reasons,
                          canonical_input_hash=canonical_input_hash, configuration_hash=manifest["config_sha256"],
                          code_version=CODE_VERSION)
    feature_snapshot_hash = sha256_json(feature_values)
    snapshot_id = hashlib.sha256(
        f"{manifest['manifest_id']}|{feature.get('asset')}|{canonical_input_hash}".encode()
    ).hexdigest()[:32]
    return {
        **feature,
        "snapshot_id": snapshot_id,
        "manifest_id": manifest["manifest_id"],
        "strategy_id": STRATEGY_ID,
        "cohort_type": "OFFICIAL_FORWARD",
        "eligibility_status": status,
        "eligible_for_future_signal": eligible,
        "eligibility_reasons": reasons,
        "source_hashes": source_hashes,
        "canonical_input_hash": canonical_input_hash,
        "feature_snapshot_hash": feature_snapshot_hash,
        "code_version": CODE_VERSION,
        "configuration_hash": manifest["config_sha256"],
        "hypothesis_version": manifest.get("hypothesis_version", config["hypothesis_version"]),
    }


def persist_snapshot(db_path: Path, snapshot: dict[str, Any]) -> tuple[str, bool]:
    columns = (
        "snapshot_id", "manifest_id", "cohort_type", "asset", "kraken_pair", "market_data_cutoff",
        "decision_timestamp", "eligibility_status", "canonical_payload_json", "payload_sha256", "created_at_utc",
        "strategy_id", "pair", "source_candle_open_timestamp", "source_candle_completion_timestamp",
        "source_data_observed_at", "feature_calculation_started_at", "feature_calculation_completed_at",
        "reference_close", "atr14", "range_low", "range_high", "range_midpoint", "range_position_pct",
        "range_valid", "range_state", "rqi_score", "rqi_classification", "rqi_position_zone",
        "freshness_status", "liquidity_eligible", "spread_eligible", "universe_eligibility",
        "market_regime", "btc_market_state", "eligible_for_future_signal", "eligibility_reasons_json",
        "source_hashes_json", "canonical_input_hash", "feature_snapshot_hash", "code_version", "configuration_hash", "hypothesis_version",
    )
    payload = canonical_json(snapshot)
    values = {
        **snapshot, "kraken_pair": snapshot.get("pair"), "canonical_payload_json": payload,
        "payload_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "created_at_utc": snapshot["decision_timestamp"],
        "range_valid": int(bool(snapshot.get("range_valid"))),
        "liquidity_eligible": int(bool(snapshot.get("liquidity_eligible"))),
        "spread_eligible": int(bool(snapshot.get("spread_eligible"))),
        "universe_eligibility": int(bool(snapshot.get("universe_eligibility"))),
        "eligible_for_future_signal": int(bool(snapshot.get("eligible_for_future_signal"))),
        "eligibility_reasons_json": canonical_json(snapshot.get("eligibility_reasons", [])),
        "source_hashes_json": canonical_json(snapshot.get("source_hashes", {})),
    }
    db = sqlite3.connect(db_path)
    try:
        before = db.total_changes
        db.execute(
            f"INSERT OR IGNORE INTO v2_decision_snapshots({','.join(columns)}) VALUES({','.join('?' for _ in columns)})",
            tuple(values.get(column) for column in columns),
        )
        inserted = db.total_changes > before
        existing = db.execute(
            "SELECT canonical_input_hash,feature_snapshot_hash FROM v2_decision_snapshots WHERE snapshot_id=?",
            (snapshot["snapshot_id"],),
        ).fetchone()
        if existing != (snapshot["canonical_input_hash"], snapshot["feature_snapshot_hash"]):
            raise ValueError("snapshot ID collision with different immutable content")
        db.commit()
        return snapshot["snapshot_id"], inserted
    finally:
        db.close()


def calculate_from_ohlcv(
    raw: pd.DataFrame, asset: str, pair: str, source_timeframe: str, market_data_cutoff: Any,
    source_data_observed_at: Any, quote_volume_24h: float, bid_ask_spread_pct: float,
    universe_eligibility: bool, manifest: dict[str, Any], config: dict[str, Any],
    market_regime: Optional[str] = None, btc_market_state: Optional[str] = None,
    component_cutoffs: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    cutoff = utc(market_data_cutoff)
    source_hours = {"15m": 0.25, "1H": 1.0, "4H": 4.0}[source_timeframe]
    clean = raw.copy()
    clean["timestamp"] = pd.to_datetime(clean["timestamp"], utc=True, errors="coerce")
    clean = clean[clean["timestamp"] + pd.to_timedelta(source_hours, unit="h") <= cutoff]
    source_hashes = {"completed_source_ohlcv_sha256": frame_hash(clean)}
    liquidity_eligible = float(quote_volume_24h) >= MIN_QUOTE_VOLUME_24H
    spread_eligible = 0 <= float(bid_ask_spread_pct) <= MAX_BID_ASK_SPREAD_PCT
    source_hashes["synchronized_eligibility_inputs_sha256"] = sha256_json({
        "market_data_cutoff": cutoff.isoformat(), "quote_volume_24h": float(quote_volume_24h),
        "bid_ask_spread_pct": float(bid_ask_spread_pct), "universe_eligibility": bool(universe_eligibility),
    })
    feature: dict[str, Any] = {
        "asset": asset, "pair": pair, "market_data_cutoff": cutoff.isoformat(),
        "source_data_observed_at": iso(source_data_observed_at),
        "feature_calculation_started_at": started.isoformat(),
        "liquidity_eligible": liquidity_eligible, "spread_eligible": spread_eligible,
        "quote_volume_24h": float(quote_volume_24h), "bid_ask_spread_pct": float(bid_ask_spread_pct),
        "universe_eligibility": universe_eligibility, "market_regime": market_regime or "UNKNOWN",
        "btc_market_state": btc_market_state or "UNKNOWN", "source_hashes": source_hashes,
        "component_cutoffs": component_cutoffs or {name: cutoff.isoformat() for name in ("price", "range", "rqi", "liquidity", "spread", "universe")},
    }
    try:
        bars = completed_4h_bars(clean, cutoff, source_timeframe)
        result = detect_range(bars, asset)
        latest = bars.iloc[-1]
        completion = utc(latest["timestamp"]) + pd.Timedelta(hours=4)
        age_hours = max(0.0, (cutoff - completion).total_seconds() / 3600)
        freshness = "FRESH" if age_hours <= 8 else "DELAYED" if age_hours <= 24 else "STALE"
        result.update(freshness_status=freshness, freshness_age_hours=age_hours, kraken_pair=pair,
                      liquidity_pass=liquidity_eligible, spread_pass=spread_eligible,
                      latest_completed_candle_timestamp=utc(latest["timestamp"]).isoformat())
        rqi = calculate_rqi(result, historical={})
        feature.update({
            "source_candle_open_timestamp": utc(latest["timestamp"]).isoformat(),
            "source_candle_completion_timestamp": completion.isoformat(),
            "reference_close": float(latest["close"]), "atr14": float(atr14(bars).iloc[-1]),
            "range_low": result["range_low"], "range_high": result["range_high"],
            "range_midpoint": result["midpoint"], "range_position_pct": result["position_pct"],
            "range_valid": result["range_valid"], "range_state": result["range_state"],
            "rqi_score": rqi.get("rqi_score"), "rqi_classification": rqi.get("rqi_classification"),
            "rqi_position_zone": rqi.get("position_zone"), "freshness_status": freshness,
        })
    except Exception as exc:
        feature.update({name: None for name in REQUIRED_FEATURES if name not in feature})
        feature["data_quality_error"] = str(exc)
    completed = datetime.now(timezone.utc)
    feature["feature_calculation_completed_at"] = completed.isoformat()
    feature["decision_timestamp"] = completed.isoformat()
    feature["feature_availability_timestamps"] = {
        "ohlcv": iso(source_data_observed_at), "range": completed.isoformat(), "rqi": completed.isoformat()
    }
    return build_decision_snapshot(feature, config, manifest)


def current_active_manifest(db_path: Path) -> dict[str, Any]:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        row = active_manifest(db)
        if not row:
            raise RuntimeError("official cohort is inactive; snapshots cannot be persisted")
        return json.loads(row["manifest_json"])
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate Phase-3 V2 snapshots from synchronized local OHLCV only.")
    parser.add_argument("--asset", required=True)
    parser.add_argument("--pair", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-timeframe", choices=("15m", "1H", "4H"), required=True)
    parser.add_argument("--cutoff", required=True, help="Explicit synchronized UTC market-data cutoff.")
    parser.add_argument("--source-observed-at", required=True)
    parser.add_argument("--quote-volume-24h", type=float, required=True)
    parser.add_argument("--bid-ask-spread-pct", type=float, required=True)
    parser.add_argument("--universe-eligible", action="store_true")
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    if args.persist:
        initialize_foundation()
        manifest = current_active_manifest(args.db)
    else:
        config = load_config()
        manifest = {"manifest_id": "DRY_RUN", "config_sha256": sha256_json(config)}
    config = load_config()
    snapshot = calculate_from_ohlcv(pd.read_csv(args.source), args.asset.upper(), args.pair,
                                    args.source_timeframe, args.cutoff, args.source_observed_at,
                                    args.quote_volume_24h, args.bid_ask_spread_pct, args.universe_eligible,
                                    manifest, config)
    inserted = False
    if args.persist:
        _, inserted = persist_snapshot(args.db, snapshot)
    print(json.dumps({"snapshot_id": snapshot["snapshot_id"], "asset": snapshot["asset"],
                      "status": snapshot["eligibility_status"], "eligible_for_future_signal": snapshot["eligible_for_future_signal"],
                      "persisted": inserted, "signals_created": 0}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
