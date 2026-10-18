from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from range_fixed_5_v2_snapshot import timestamp_legality
from range_fixed_5_v2_clock import ClockSafetyError, ClockSafetyGuard
from range_fixed_5_v2_storage import (
    DB_PATH, STRATEGY_ID, active_manifest, canonical_json, load_config, load_phase4_config, sha256_json,
    validate_phase4_config,
)


Clock = Callable[[], datetime]
Fetcher = Callable[[str, str], Any]


def _utc_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _iso(value: Any) -> str:
    return _utc_datetime(value).isoformat()


def fetch_public_kraken_ticker(pair: str, endpoint: str, timeout_seconds: float = 10.0) -> dict[str, Any]:
    """Fetch one unauthenticated public Ticker response. No private API capability exists here."""
    url = endpoint + "?" + urllib.parse.urlencode({"pair": pair})
    request = urllib.request.Request(url, headers={"User-Agent": "kraken-ai-trading-v2-research/1.0"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def create_signal(
    db_path: Path, snapshot_id: str, signal_created_at: Any = None,
    simultaneous_signal_count: int = 1, same_asset_active_episode: bool = False,
    clock_guard: Optional[ClockSafetyGuard] = None,
) -> tuple[dict[str, Any], bool]:
    config = load_config()
    guard = clock_guard or ClockSafetyGuard()
    guard.check()
    created = _utc_datetime(signal_created_at or datetime.now(timezone.utc))
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        existing = db.execute("SELECT * FROM v2_signals WHERE snapshot_id=?", (snapshot_id,)).fetchone()
        if existing:
            return dict(existing), False
        manifest = active_manifest(db)
        if not manifest:
            raise ValueError("OFFICIAL_COHORT_NOT_ACTIVATED")
        extension = db.execute(
            "SELECT * FROM v2_strategy_extensions WHERE extension_id='RANGE_FIXED_5_FORWARD_V2_PHASE4_ENTRY_V1'"
        ).fetchone()
        if not extension:
            raise ValueError("PHASE4_POLICY_NOT_INSTALLED")
        if extension["extension_config_sha256"] != sha256_json(load_phase4_config()):
            raise ValueError("PHASE4_POLICY_HASH_MISMATCH")
        clock_extension = db.execute(
            "SELECT * FROM v2_strategy_extensions WHERE extension_id='RANGE_FIXED_5_FORWARD_V2_CLOCK_SAFETY_V1'"
        ).fetchone()
        if not clock_extension:
            raise ValueError("CLOCK_SAFETY_POLICY_NOT_INSTALLED")
        snapshot = db.execute("SELECT * FROM v2_decision_snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
        if not snapshot:
            raise ValueError("SNAPSHOT_NOT_PERSISTED")
        if snapshot["manifest_id"] != manifest["manifest_id"]:
            raise ValueError("SNAPSHOT_MANIFEST_MISMATCH")
        if snapshot["eligible_for_future_signal"] != 1 or snapshot["eligibility_status"] != "ELIGIBLE_FOR_FUTURE_SIGNAL":
            raise ValueError("SNAPSHOT_NOT_ELIGIBLE")
        if snapshot["strategy_id"] != STRATEGY_ID:
            raise ValueError("SNAPSHOT_STRATEGY_MISMATCH")
        if snapshot["configuration_hash"] != manifest["config_sha256"] or snapshot["configuration_hash"] != sha256_json(config):
            raise ValueError("SNAPSHOT_CONFIG_MISMATCH")
        if snapshot["hypothesis_version"] != manifest["hypothesis_version"]:
            raise ValueError("SNAPSHOT_HYPOTHESIS_MISMATCH")
        payload = json.loads(snapshot["canonical_payload_json"])
        legal, _ = timestamp_legality(payload)
        if not legal:
            raise ValueError("SNAPSHOT_TIMESTAMP_ILLEGAL")
        decision = _utc_datetime(snapshot["decision_timestamp"])
        cohort_start = _utc_datetime(manifest["official_cohort_start_timestamp"])
        if decision < cohort_start:
            raise ValueError("PRE_COHORT_SNAPSHOT")
        if created < decision or created < cohort_start:
            raise ValueError("SIGNAL_BEFORE_DECISION_OR_COHORT")
        signal_payload = {
            "manifest_id": manifest["manifest_id"], "snapshot_id": snapshot_id,
            "asset": snapshot["asset"], "pair": snapshot["kraken_pair"],
            "signal_timestamp": created.isoformat(), "strategy_id": STRATEGY_ID,
            "hypothesis_version": manifest["hypothesis_version"],
            "configuration_hash": manifest["config_sha256"],
            "phase4_extension_config_sha256": extension["extension_config_sha256"],
        }
        signal_id = hashlib.sha256(f"{STRATEGY_ID}|{snapshot_id}".encode()).hexdigest()[:32]
        batch_id = hashlib.sha256(f"{manifest['manifest_id']}|{snapshot['decision_timestamp']}".encode()).hexdigest()[:24]
        signal_hash = sha256_json(signal_payload)
        db.execute(
            """INSERT INTO v2_signals(signal_id,snapshot_id,manifest_id,cohort_type,asset,kraken_pair,
               signal_batch_id,signal_timestamp,simultaneous_signal_count,same_asset_active_episode,
               signal_sha256,created_at_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (signal_id, snapshot_id, manifest["manifest_id"], "OFFICIAL_FORWARD", snapshot["asset"],
             snapshot["kraken_pair"], batch_id, created.isoformat(), simultaneous_signal_count,
             int(same_asset_active_episode), signal_hash, created.isoformat()),
        )
        db.commit()
        return dict(db.execute("SELECT * FROM v2_signals WHERE signal_id=?", (signal_id,)).fetchone()), True
    finally:
        db.close()


def _parse_quote(payload: Any, pair: str, maximum_spread_pct: float) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("MALFORMED_RESPONSE")
    if payload.get("error"):
        raise ValueError("KRAKEN_ERROR_RESPONSE")
    result = payload.get("result")
    if not isinstance(result, dict) or len(result) != 1:
        raise ValueError("UNSUPPORTED_OR_MALFORMED_PAIR")
    quote = next(iter(result.values()))
    if not isinstance(quote, dict):
        raise ValueError("MALFORMED_RESPONSE")
    status = str(quote.get("status") or "STATUS_NOT_PROVIDED").upper()
    if status not in {"STATUS_NOT_PROVIDED", "ONLINE", "ACTIVE"}:
        raise ValueError("PAIR_INACTIVE")
    try:
        bid = float(quote["b"][0])
        ask = float(quote["a"][0])
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError("MISSING_OR_INVALID_BID_ASK")
    if bid <= 0 or ask <= 0:
        raise ValueError("NON_POSITIVE_BID_ASK")
    if ask < bid:
        raise ValueError("ASK_BELOW_BID")
    spread = (ask - bid) / ((ask + bid) / 2) * 100
    if spread > maximum_spread_pct:
        raise ValueError("EXCESSIVE_SPREAD")
    return {"pair": pair, "best_bid": bid, "best_ask": ask, "spread_pct": spread, "pair_status": status}


def validate_public_ticker_quote(payload: Any, pair: str, maximum_spread_pct: float) -> dict[str, Any]:
    """Public, side-effect-free access to the frozen Phase-4 quote validation."""
    return _parse_quote(payload, pair, maximum_spread_pct)


def observe_entry(
    db_path: Path, signal_id: str, fetcher: Fetcher = fetch_public_kraken_ticker,
    clock: Clock = lambda: datetime.now(timezone.utc), sleeper: Callable[[float], None] = time.sleep,
    phase4_config: Optional[dict[str, Any]] = None,
    clock_guard: Optional[ClockSafetyGuard] = None,
) -> dict[str, Any]:
    policy_config = phase4_config or load_phase4_config()
    validate_phase4_config(policy_config)
    policy = policy_config["quote_attempt_policy"]
    entry_rule = policy_config["entry_observation"]
    guard = clock_guard or ClockSafetyGuard()
    try:
        guard.check()
    except ClockSafetyError as exc:
        return {"status": str(exc), "entry": None, "attempts_recorded": 0, "idempotent": False}
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        accepted = db.execute("SELECT * FROM v2_entry_observations WHERE signal_id=?", (signal_id,)).fetchone()
        if accepted:
            return {"status": "ENTRY_OBSERVED", "entry": dict(accepted), "attempts_recorded": 0, "idempotent": True}
        signal = db.execute("SELECT * FROM v2_signals WHERE signal_id=?", (signal_id,)).fetchone()
        if not signal:
            raise ValueError("SIGNAL_NOT_FOUND")
        signal_time = _utc_datetime(signal["signal_timestamp"])
        previous = db.execute("SELECT count(*) FROM v2_quote_attempts WHERE signal_id=?", (signal_id,)).fetchone()[0]
        attempts_recorded = 0
        for attempt_number in range(previous + 1, int(policy["maximum_attempts"]) + 1):
            try:
                guard.check()
            except ClockSafetyError as exc:
                return {"status": str(exc), "entry": None,
                        "attempts_recorded": attempts_recorded, "idempotent": False}
            request_started = _utc_datetime(clock())
            if request_started < signal_time:
                raise ValueError("QUOTE_REQUEST_BEFORE_SIGNAL")
            payload = None
            received = None
            raw_hash = None
            quote = None
            error_code = None
            try:
                fetched = fetcher(signal["kraken_pair"], entry_rule["public_endpoint"])
                if isinstance(fetched, tuple) and len(fetched) == 2:
                    payload, received_value = fetched
                    received = _utc_datetime(received_value)
                else:
                    payload = fetched
                    received = _utc_datetime(clock())
                try:
                    guard.check()
                except ClockSafetyError as exc:
                    return {"status": str(exc), "entry": None,
                            "attempts_recorded": attempts_recorded, "idempotent": False}
                raw_hash = sha256_json(payload)
                if received < request_started:
                    raise ValueError("QUOTE_RECEIVED_BEFORE_REQUEST")
                quote = _parse_quote(payload, signal["kraken_pair"], float(entry_rule["maximum_spread_pct"]))
                quote_status = "VALID_QUOTE"
            except Exception as exc:
                received = _utc_datetime(clock()) if received is None or received < request_started else received
                if received < request_started:
                    return {"status": "CLOCK_CHRONOLOGY_ERROR", "entry": None,
                            "attempts_recorded": attempts_recorded, "idempotent": False}
                error_code = str(exc) or exc.__class__.__name__
                quote_status = "QUOTE_REJECTED"
            attempt_payload = {
                "signal_id": signal_id, "attempt_number": attempt_number, "pair": signal["kraken_pair"],
                "request_started_at": request_started.isoformat(), "response_received_at": received.isoformat(),
                "quote_status": quote_status, "best_bid": quote.get("best_bid") if quote else None,
                "best_ask": quote.get("best_ask") if quote else None,
                "spread_pct": quote.get("spread_pct") if quote else None,
                "raw_response_sha256": raw_hash, "error_code": error_code,
            }
            attempt_id = hashlib.sha256(f"{signal_id}|QUOTE_ATTEMPT|{attempt_number}".encode()).hexdigest()[:32]
            encoded = canonical_json(attempt_payload)
            db.execute(
                "INSERT INTO v2_quote_attempts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (attempt_id, signal_id, attempt_number, signal["kraken_pair"], request_started.isoformat(),
                 received.isoformat(), quote_status, attempt_payload["best_bid"], attempt_payload["best_ask"],
                 attempt_payload["spread_pct"], raw_hash, error_code, encoded,
                 hashlib.sha256(encoded.encode()).hexdigest(), received.isoformat()),
            )
            attempts_recorded += 1
            if quote:
                entry_price = quote["best_ask"]
                target = entry_price * 1.05
                stop = entry_price * 0.98
                expiry = received + timedelta(hours=120)
                entry_payload = {
                    "signal_id": signal_id, "pair": signal["kraken_pair"], "accepted_attempt_id": attempt_id,
                    "request_started_at": request_started.isoformat(), "response_received_at": received.isoformat(),
                    "best_bid": quote["best_bid"], "best_ask": entry_price, "spread_pct": quote["spread_pct"],
                    "entry_reference_price": entry_price, "entry_timestamp": received.isoformat(),
                    "target_price": target, "stop_price": stop, "expiry_timestamp": expiry.isoformat(),
                    "gross_reward_pct": 5.0, "gross_risk_pct": -2.0, "gross_reward_risk_ratio": 2.5,
                    "quote_status": "ENTRY_OBSERVED", "raw_response_sha256": raw_hash,
                }
                entry_id = hashlib.sha256(f"{signal_id}|ENTRY|{attempt_id}".encode()).hexdigest()[:32]
                entry_encoded = canonical_json(entry_payload)
                db.execute(
                    """INSERT INTO v2_entry_observations(entry_observation_id,signal_id,request_started_at,
                       observed_at,best_bid,best_ask,entry_reference_price,target_price,stop_price,
                       expiry_timestamp,raw_response_sha256,canonical_payload_json,created_at_utc,pair,
                       response_received_at,spread_pct,quote_status,accepted_attempt_id,gross_reward_pct,
                       gross_risk_pct,gross_reward_risk_ratio) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (entry_id, signal_id, request_started.isoformat(), received.isoformat(), quote["best_bid"],
                     entry_price, entry_price, target, stop, expiry.isoformat(), raw_hash, entry_encoded,
                     received.isoformat(), signal["kraken_pair"], received.isoformat(), quote["spread_pct"],
                     "ENTRY_OBSERVED", attempt_id, 5.0, -2.0, 2.5),
                )
                db.commit()
                return {"status": "ENTRY_OBSERVED", "entry": entry_payload,
                        "attempts_recorded": attempts_recorded, "idempotent": False}
            db.commit()
            if attempt_number < int(policy["maximum_attempts"]):
                sleeper(float(policy["delay_between_attempts_seconds"]))
        return {"status": "ENTRY_NOT_OBSERVED", "entry": None,
                "attempts_recorded": attempts_recorded, "idempotent": False}
    finally:
        db.close()
