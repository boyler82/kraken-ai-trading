from __future__ import annotations

"""Forward-only outcome resolution for RANGE_FIXED_5_FORWARD_V2.

The pure ``monitor_observation`` boundary is deliberately injectable: production
collection can use public Kraken data while tests use an isolated synthetic DB.
There is no account, order, position, or private-API capability in this module.
"""

import argparse
import hashlib
import json
import sqlite3
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd

from consolidation_range_engine import atr14, breakout_events
from range_fixed_5_v2_storage import DB_PATH, canonical_json, load_config


PUBLIC_TRADES_ENDPOINT = "https://api.kraken.com/0/public/Trades"
TERMINAL_TYPES = {"TARGET_HIT", "STOP_HIT", "STRUCTURE_INVALIDATION", "TIME_EXIT"}


def utc(value: Any) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def iso(value: Any) -> str:
    return utc(value).isoformat()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


@dataclass(frozen=True)
class Candidate:
    outcome: str
    timestamp: datetime
    exit_price: float
    payload: dict[str, Any]
    sequence: int = 0


def fetch_public_kraken_trades(pair: str, since: int, endpoint: str = PUBLIC_TRADES_ENDPOINT,
                               timeout_seconds: float = 15.0) -> dict[str, Any]:
    """Read the unauthenticated public Trades endpoint; ``since`` is Kraken nanoseconds."""
    url = endpoint + "?" + urllib.parse.urlencode({"pair": pair, "since": int(since)})
    request = urllib.request.Request(url, headers={"User-Agent": "kraken-ai-trading-v2-monitor/1.0"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_kraken_trades(response: dict[str, Any], pair: str) -> list[dict[str, Any]]:
    if not isinstance(response, dict) or response.get("error"):
        raise ValueError("invalid Kraken Trades response")
    result = response.get("result") or {}
    key = next((key for key in result if key != "last"), None)
    if key is None or not isinstance(result.get(key), list):
        raise ValueError("Kraken Trades response has no trade list")
    trades = []
    for sequence, row in enumerate(result[key]):
        if not isinstance(row, list) or len(row) < 3:
            raise ValueError("malformed Kraken trade")
        price, stamp = float(row[0]), datetime.fromtimestamp(float(row[2]), timezone.utc)
        if price <= 0:
            raise ValueError("non-positive Kraken trade")
        trades.append({"timestamp": stamp.isoformat(), "price": price, "sequence": sequence, "pair": pair})
    return trades


def trade_candidate(entry: sqlite3.Row, trades: Iterable[dict[str, Any]]) -> Optional[Candidate]:
    start, expiry = utc(entry["entry_timestamp"]), utc(entry["expiry_timestamp"])
    ordered = sorted(trades, key=lambda row: (utc(row["timestamp"]), int(row.get("sequence", 0))))
    for row in ordered:
        stamp, price = utc(row["timestamp"]), float(row["price"])
        if stamp < start or stamp > expiry:
            continue
        if price >= float(entry["target_price"]):
            return Candidate("TARGET_HIT", stamp, price, {"source": "KRAKEN_PUBLIC_TRADES", "trade": row,
                "resolution_policy": "EXACT_PUBLIC_TRADE_SEQUENCE"}, int(row.get("sequence", 0)))
        if price <= float(entry["stop_price"]):
            return Candidate("STOP_HIT", stamp, price, {"source": "KRAKEN_PUBLIC_TRADES", "trade": row,
                "resolution_policy": "EXACT_PUBLIC_TRADE_SEQUENCE"}, int(row.get("sequence", 0)))
    return None


def bar_candidate(entry: sqlite3.Row, bars: Iterable[dict[str, Any]]) -> Optional[Candidate]:
    """Resolve complete bars. Bars overlapping entry are excluded in their entirety."""
    start, expiry = utc(entry["entry_timestamp"]), utc(entry["expiry_timestamp"])
    found = []
    for row in bars:
        opened, closed = utc(row["open_timestamp"]), utc(row["close_timestamp"])
        if opened < start or closed <= opened or closed > expiry:
            continue
        hit_target = float(row["high"]) >= float(entry["target_price"])
        hit_stop = float(row["low"]) <= float(entry["stop_price"])
        evidence = {"source": "COMPLETED_PUBLIC_KRAKEN_BAR", "bar": row,
                    "raw_evidence_sha256": digest(row)}
        if hit_target and hit_stop:
            evidence.update(ambiguity_flag="INTRABAR_ORDER_UNKNOWN",
                            resolution_policy="CONSERVATIVE_STOP_FIRST")
            found.append(Candidate("STOP_HIT", closed, float(entry["stop_price"]), evidence))
        elif hit_stop:
            evidence["resolution_policy"] = "BAR_SINGLE_BOUNDARY_TOUCH"
            found.append(Candidate("STOP_HIT", closed, float(entry["stop_price"]), evidence))
        elif hit_target:
            evidence["resolution_policy"] = "BAR_SINGLE_BOUNDARY_TOUCH"
            found.append(Candidate("TARGET_HIT", closed, float(entry["target_price"]), evidence))
    return min(found, key=lambda item: item.timestamp) if found else None


def structure_candidate(entry: sqlite3.Row, completed_4h: Iterable[dict[str, Any]]) -> Optional[Candidate]:
    """Apply the authoritative consolidation breakout classifier to completed 4H bars."""
    start, expiry = utc(entry["entry_timestamp"]), utc(entry["expiry_timestamp"])
    rows = list(completed_4h)
    if len(rows) < 14:
        return None
    frame = pd.DataFrame(rows)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.sort_values("timestamp").drop_duplicates("timestamp", keep="last").reset_index(drop=True)
    numeric = ("open", "high", "low", "close")
    for name in numeric:
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
    frame = frame.dropna(subset=["timestamp", *numeric]).reset_index(drop=True)
    tolerance = 0.25 * atr14(frame)
    events = breakout_events(frame, float(entry["range_low"]), float(entry["range_high"]), tolerance)
    candidates = []
    for event in events["events"]:
        if event["classification"] not in {"BREAKOUT_CONFIRMED", "BREAKDOWN_CONFIRMED"}:
            continue
        index = int(event["confirmation_index"])
        actionable = frame.loc[index, "timestamp"].to_pydatetime() + timedelta(hours=4)
        if actionable < start or actionable > expiry:
            continue
        payload = {"source": "AUTHORITATIVE_V2_CONSOLIDATION_LOGIC", "event": event,
                   "confirming_bar_completed_at": actionable.isoformat(),
                   "completed_4h_evidence_sha256": digest(rows),
                   "resolution_policy": "TWO_COMPLETED_4H_CLOSES_WITH_ATR_TOLERANCE"}
        candidates.append(Candidate("STRUCTURE_INVALIDATION", actionable,
                                    float(frame.loc[index, "close"]), payload))
    return min(candidates, key=lambda item: item.timestamp) if candidates else None


def time_candidate(entry: sqlite3.Row, bids: Iterable[dict[str, Any]]) -> Optional[Candidate]:
    expiry = utc(entry["expiry_timestamp"])
    valid = [(utc(row["timestamp"]), float(row["best_bid"]), row) for row in bids
             if utc(row["timestamp"]) >= expiry and float(row["best_bid"]) > 0]
    if not valid:
        return None
    stamp, price, row = min(valid, key=lambda item: item[0])
    return Candidate("TIME_EXIT", stamp, price, {"source": "KRAKEN_PUBLIC_BEST_BID", "quote": row,
        "resolution_policy": "FIRST_VALID_BEST_BID_AT_OR_AFTER_EXPIRY"})


def _append_event(db: sqlite3.Connection, signal_id: str, event_type: str, stamp: datetime,
                  payload: dict[str, Any], created_at: datetime) -> tuple[str, bool]:
    encoded, source_hash = canonical_json(payload), digest(payload)
    payload_hash = hashlib.sha256(encoded.encode()).hexdigest()
    event_id = hashlib.sha256(f"{signal_id}|{event_type}|{stamp.isoformat()}|{payload_hash}".encode()).hexdigest()[:32]
    previous = db.execute("SELECT event_id FROM v2_monitor_events WHERE signal_id=? ORDER BY event_timestamp DESC,event_id DESC LIMIT 1",
                          (signal_id,)).fetchone()
    before = db.total_changes
    db.execute("""INSERT OR IGNORE INTO v2_monitor_events(event_id,signal_id,event_type,event_timestamp,
               previous_event_id,source_data_sha256,canonical_payload_json,payload_sha256,created_at_utc)
               VALUES(?,?,?,?,?,?,?,?,?)""", (event_id, signal_id, event_type, stamp.isoformat(),
               previous[0] if previous else None, source_hash, encoded, payload_hash, created_at.isoformat()))
    return event_id, db.total_changes > before


def monitor_observation(db_path: Path, signal_id: str, *, trades: Iterable[dict[str, Any]] = (),
                        bars: Iterable[dict[str, Any]] = (), completed_4h: Iterable[dict[str, Any]] = (),
                        bids: Iterable[dict[str, Any]] = (), coverage_complete: bool = True,
                        data_gap: Optional[str] = None, entry_slippage_pct: float = 0.0,
                        exit_slippage_pct: float = 0.0, observed_at: Any = None) -> dict[str, Any]:
    now = utc(observed_at or datetime.now(timezone.utc))
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        existing = db.execute("SELECT * FROM v2_completed_outcomes WHERE signal_id=?", (signal_id,)).fetchone()
        if existing:
            return {"status": "ALREADY_COMPLETED", "outcome": dict(existing), "idempotent": True}
        entry = db.execute("""SELECT o.*,d.range_low,d.range_high FROM v2_open_observations o
                              JOIN v2_decision_snapshots d ON d.snapshot_id=o.snapshot_id
                              WHERE o.signal_id=?""", (signal_id,)).fetchone()
        if not entry:
            raise ValueError("open V2 observation not found")
        candidates = [candidate for candidate in (
            trade_candidate(entry, trades), bar_candidate(entry, bars), structure_candidate(entry, completed_4h),
            time_candidate(entry, bids)) if candidate is not None]
        # Stop wins only unresolved same-bar equality; exact trades retain sequence order.
        priority = {"STOP_HIT": 0, "TARGET_HIT": 1, "STRUCTURE_INVALIDATION": 2, "TIME_EXIT": 3}
        winner = min(candidates, key=lambda item: (item.timestamp, priority[item.outcome])) if candidates else None
        if winner and winner.outcome == "TIME_EXIT" and not coverage_complete:
            winner = None
        if winner is None:
            gap = data_gap or ("MONITORING_COVERAGE_INCOMPLETE" if not coverage_complete else "NO_TERMINAL_EVENT")
            event_id, inserted = _append_event(db, signal_id, "DATA_GAP" if gap != "NO_TERMINAL_EVENT" else "MONITOR_CHECK",
                                               now, {"state": gap, "terminal_exit_fabricated": False}, now)
            db.commit()
            return {"status": "OPEN_DATA_GAP" if gap != "NO_TERMINAL_EVENT" else "OPEN",
                    "event_id": event_id, "event_inserted": inserted, "idempotent": not inserted}
        event_id, _ = _append_event(db, signal_id, winner.outcome, winner.timestamp, winner.payload, now)
        config = load_config()
        entry_fee = float(config["cost_model"]["entry_fee_pct"])
        exit_fee = float(config["cost_model"]["exit_fee_pct"])
        total_fee = entry_fee + exit_fee
        total_slippage = float(entry_slippage_pct) + float(exit_slippage_pct)
        if min(entry_slippage_pct, exit_slippage_pct) < 0:
            raise ValueError("slippage estimates cannot be negative")
        gross = (winner.exit_price / float(entry["entry_reference_price"]) - 1.0) * 100.0
        total_cost = total_fee + total_slippage
        outcome_payload = {"signal_id": signal_id, "terminal_event_id": event_id, "terminal_outcome": winner.outcome,
            "entry_timestamp": iso(entry["entry_timestamp"]), "exit_timestamp": winner.timestamp.isoformat(),
            "entry_reference_price": float(entry["entry_reference_price"]), "exit_reference_price": winner.exit_price,
            "gross_return_pct": gross, "entry_fee_pct": entry_fee, "exit_fee_pct": exit_fee,
            "entry_slippage_pct": float(entry_slippage_pct), "exit_slippage_pct": float(exit_slippage_pct),
            "total_fee_pct": total_fee, "total_slippage_pct": total_slippage,
            "total_transaction_cost_pct": total_cost, "net_return_pct": gross - total_cost}
        outcome_hash, outcome_id = digest(outcome_payload), hashlib.sha256(f"{signal_id}|OUTCOME".encode()).hexdigest()[:32]
        columns = tuple(outcome_payload) + ("outcome_id", "outcome_sha256", "created_at_utc")
        values = tuple(outcome_payload.values()) + (outcome_id, outcome_hash, now.isoformat())
        db.execute(f"INSERT INTO v2_completed_outcomes({','.join(columns)}) VALUES({','.join('?' for _ in columns)})", values)
        db.commit()
        return {"status": "COMPLETED", "outcome": {**outcome_payload, "outcome_id": outcome_id}, "idempotent": False}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve one V2 observation from caller-supplied public evidence.")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--signal-id", required=True)
    parser.add_argument("--evidence", type=Path, required=True,
                        help="JSON with trades/bars/completed_4h/bids and explicit coverage_complete.")
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text())
    print(canonical_json(monitor_observation(args.db, args.signal_id, **evidence)))


if __name__ == "__main__":
    main()
