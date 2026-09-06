from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from weekly_consolidation_common import ROOT, atomic_write, utc_timestamp


DATASET_DIR = ROOT / "DATASETS/TACTICAL_OUTCOMES"
SUMMARY_DIR = ROOT / "DAILY_REPORTS/TACTICAL_OUTCOMES"
SNAPSHOTS = "tactical_candidate_snapshots.jsonl"
EVENTS = "tactical_outcome_events.jsonl"
SUMMARY = "latest_tactical_outcome_summary.json"
HORIZONS = (4, 12, 24, 48, 72, 96)
MIN_EDGE_SAMPLE = 20
BUY_ACTIONS = {"BUY_NOW", "BUY_ON_BREAKOUT", "BUY_ON_PULLBACK"}
INVALIDATION_WARNINGS = {"FAILED_BREAKOUT", "EXTENDED_MOVE", "INVALIDATED_SETUP", "STALE_DATA"}


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except (ValueError, TypeError):
            continue
    return rows


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(_clean(row), sort_keys=True, separators=(",", ":")) + "\n")


def _id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


def _utc(value: Any) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _candidate_pairs(packet: dict) -> dict[str, str]:
    return {
        str(row.get("asset")): str(row.get("identity", {}).get("kraken_pair"))
        for row in packet.get("candidates", [])
        if row.get("asset") and row.get("identity", {}).get("kraken_pair")
    }


def _unique_opportunities(packet: dict) -> list[dict]:
    found: dict[str, dict] = {}
    for bucket in ("daily", "weekly", "avoid"):
        for row in packet.get("tactical_opportunities", {}).get(bucket, []):
            asset = str(row.get("asset") or "")
            if asset and asset not in found:
                found[asset] = row
    return list(found.values())


def build_snapshots(packet: dict) -> list[dict]:
    generated = _utc(packet.get("generated_at_utc") or utc_timestamp()).isoformat()
    pairs = _candidate_pairs(packet)
    rows = []
    for item in _unique_opportunities(packet):
        asset = str(item["asset"])
        plan = item.get("trade_plan") or {}
        warnings = list(dict.fromkeys((item.get("warnings") or []) + (plan.get("warnings") or [])))
        snapshot_id = _id("tos", generated, asset)
        rows.append({
            "snapshot_id": snapshot_id,
            "timestamp": generated,
            "asset": asset,
            "kraken_pair": pairs.get(asset),
            "objective": packet.get("objective"),
            "recommendation": item.get("recommendation"),
            "conviction": item.get("conviction"),
            "technical_action": item.get("technical_action") or item.get("action"),
            "setup_quality_score": item.get("setup_quality_score"),
            "actionability_score": item.get("actionability_score"),
            "daily_score": item.get("daily_score"),
            "weekly_score": item.get("weekly_score"),
            "current_price": item.get("current_price"),
            "preferred_entry": plan.get("preferred_entry"),
            "entry_method": plan.get("entry_method"),
            "stop_loss": plan.get("stop_loss"),
            "stop_distance_pct": plan.get("stop_distance_pct"),
            "planned_trade_family": plan.get("planned_trade_family"),
            "exit_method": plan.get("exit_method"),
            "btc_relative_edge": item.get("net_edge_after_costs"),
            "rotation_advantage": item.get("rotation_score_advantage"),
            "warnings": warnings,
        })
    return rows


def _completed_candles(snapshot: dict, as_of: pd.Timestamp, market_dir: Path) -> pd.DataFrame:
    pair = snapshot.get("kraken_pair")
    path = market_dir / f"{pair}_1H.csv" if pair else None
    if not path or not path.exists():
        return pd.DataFrame()
    try:
        frame = pd.read_csv(path)
        required = {"timestamp", "open", "high", "low", "close"}
        if not required.issubset(frame.columns):
            return pd.DataFrame()
        frame["candle_start"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
        frame["completed_at"] = frame["candle_start"] + timedelta(hours=1)
        for name in ("open", "high", "low", "close"):
            frame[name] = pd.to_numeric(frame[name], errors="coerce")
        # A candle must both start after the snapshot and be completed by as_of.
        start = _utc(snapshot["timestamp"])
        return frame[(frame["candle_start"] >= start) & (frame["completed_at"] <= as_of)].dropna(
            subset=["candle_start", "completed_at", "high", "low", "close"]
        ).sort_values("candle_start")
    except Exception:
        return pd.DataFrame()


def _event(snapshot: dict, kind: str, **fields: Any) -> dict:
    discriminator = fields.get("horizon_hours") or fields.get("activated_snapshot_id") or "once"
    return {"event_id": _id("toe", snapshot["snapshot_id"], kind, discriminator),
            "snapshot_id": snapshot["snapshot_id"], "asset": snapshot["asset"],
            "event_type": kind, **fields}


def _find_trigger(snapshot: dict, candles: pd.DataFrame) -> dict | None:
    action = snapshot.get("technical_action")
    entry = snapshot.get("preferred_entry")
    if action == "BUY_NOW" and snapshot.get("current_price") is not None:
        return _event(snapshot, "TRIGGERED", trigger_timestamp=snapshot["timestamp"],
                      trigger_price=float(entry or snapshot["current_price"]), trigger_candle_start=None)
    if entry is None or candles.empty:
        return None
    entry = float(entry)
    if action == "BUY_ON_BREAKOUT":
        hits = candles[candles["close"] >= entry]
        if len(hits):
            row = hits.iloc[0]
            return _event(snapshot, "TRIGGERED", trigger_timestamp=row["completed_at"].isoformat(),
                          trigger_price=float(row["close"]), trigger_candle_start=row["candle_start"].isoformat())
    elif action == "BUY_ON_PULLBACK":
        hits = candles[(candles["low"] <= entry) & (candles["high"] >= entry)]
        if len(hits):
            row = hits.iloc[0]
            return _event(snapshot, "TRIGGERED", trigger_timestamp=row["completed_at"].isoformat(),
                          trigger_price=entry, trigger_candle_start=row["candle_start"].isoformat())
    return None


def _horizon_events(snapshot: dict, trigger: dict, candles: pd.DataFrame) -> list[dict]:
    if candles.empty:
        return []
    trigger_time = _utc(trigger["trigger_timestamp"])
    trigger_price = float(trigger["trigger_price"])
    post = candles[candles["completed_at"] > trigger_time]
    rows = []
    for horizon in HORIZONS:
        due = trigger_time + timedelta(hours=horizon)
        eligible = post[post["completed_at"] >= due]
        if eligible.empty:
            continue
        outcome = eligible.iloc[0]
        window = post[post["completed_at"] <= outcome["completed_at"]]
        if window.empty:
            continue
        max_pos = window["high"].idxmax(); min_pos = window["low"].idxmin()
        mfe = (float(window.loc[max_pos, "high"]) / trigger_price - 1) * 100
        mae = (float(window.loc[min_pos, "low"]) / trigger_price - 1) * 100
        stop = snapshot.get("stop_loss")
        rows.append(_event(
            snapshot, "HORIZON_OUTCOME", horizon_hours=horizon,
            measured_at=outcome["completed_at"].isoformat(),
            return_pct=(float(outcome["close"]) / trigger_price - 1) * 100,
            mfe_pct=mfe, mae_pct=mae,
            mfe_timestamp=window.loc[max_pos, "completed_at"].isoformat(),
            mae_timestamp=window.loc[min_pos, "completed_at"].isoformat(),
            stop_breached=bool(stop is not None and (window["low"] <= float(stop)).any()),
            time_to_mfe_hours=(window.loc[max_pos, "completed_at"] - trigger_time).total_seconds() / 3600,
            time_to_mae_hours=(window.loc[min_pos, "completed_at"] - trigger_time).total_seconds() / 3600,
        ))
    return rows


def _observation_horizon_events(snapshot: dict, candles: pd.DataFrame, market_dir: Path, as_of: pd.Timestamp) -> list[dict]:
    price=snapshot.get("current_price")
    if price in (None,0) or candles.empty:return []
    synthetic={"trigger_timestamp":snapshot["timestamp"],"trigger_price":float(price)}
    rows=_horizon_events(snapshot,synthetic,candles)
    btc=_completed_candles({**snapshot,"kraken_pair":"BTCUSD"},as_of,market_dir)
    btc_price=None
    btc_path=market_dir/"BTCUSD_1H.csv"
    if btc_path.exists():
        try:
            f=pd.read_csv(btc_path);f["timestamp"]=pd.to_datetime(f["timestamp"],utc=True,errors="coerce");prior=f[f["timestamp"]<=_utc(snapshot["timestamp"])]
            if len(prior):btc_price=float(prior.iloc[-1]["close"])
        except Exception:btc_price=None
    for row in rows:
        due=_utc(row["measured_at"]);match=btc[btc["completed_at"]>=due]
        btc_return=None if btc_price in (None,0) or match.empty else (float(match.iloc[0]["close"])/btc_price-1)*100
        window=candles[candles["completed_at"]<=due];scenario=snapshot.get("technical_scenario") or {}
        activation=scenario.get("activation_level");invalidation=scenario.get("technical_invalidation_level")
        references=scenario.get("reference_levels") or []
        row.update(observation_basis="NO_ASSUMED_EXECUTION",btc_return_pct=btc_return,
                   relative_return_vs_btc_pct=None if btc_return is None else row["return_pct"]-btc_return,
                   activation_occurred=bool(activation is not None and len(window) and (window["high"]>=float(activation)).any()),
                   technical_invalidation_occurred=bool(invalidation is not None and len(window) and (window["low"]<=float(invalidation)).any()),
                   reference_touches=[{"price":x.get("price"),"touched":bool(x.get("price") is not None and len(window) and (window["high"]>=float(x["price"])).any())} for x in references])
    return rows


def _watch_event(snapshot: dict, snapshots: list[dict]) -> dict | None:
    later = [row for row in snapshots if row.get("asset") == snapshot.get("asset")
             and _utc(row["timestamp"]) > _utc(snapshot["timestamp"])]
    for row in sorted(later, key=lambda x: _utc(x["timestamp"])):
        elapsed = (_utc(row["timestamp"]) - _utc(snapshot["timestamp"])).total_seconds() / 3600
        if row.get("technical_action") in BUY_ACTIONS:
            return _event(snapshot, "WATCH_ACTIVATED", activated_snapshot_id=row["snapshot_id"],
                          activation_timestamp=row["timestamp"], time_to_activation_hours=elapsed,
                          activated_action=row.get("technical_action"))
        if row.get("technical_action") == "AVOID" or INVALIDATION_WARNINGS.intersection(row.get("warnings") or []):
            return _event(snapshot, "WATCH_INVALIDATED", activated_snapshot_id=row["snapshot_id"],
                          invalidation_timestamp=row["timestamp"], time_to_invalidation_hours=elapsed)
    return None


def update_events(snapshots: list[dict], events: list[dict], as_of: pd.Timestamp, market_dir: Path) -> list[dict]:
    existing = {row.get("event_id") for row in events}
    by_snapshot: dict[str, list[dict]] = {}
    for row in events:
        by_snapshot.setdefault(row.get("snapshot_id"), []).append(row)
    new = []
    for snapshot in snapshots:
        if snapshot.get("methodology_version") == "OPPORTUNITY_DISCOVERY_V1":
            candles = _completed_candles(snapshot, as_of, market_dir)
            for event in _observation_horizon_events(snapshot,candles,market_dir,as_of):
                if event["event_id"] not in existing:new.append(event);existing.add(event["event_id"])
            continue
        action = snapshot.get("technical_action")
        if action == "AVOID" or snapshot.get("recommendation") == "AVOID":
            continue
        if action == "WATCH" or snapshot.get("recommendation") == "HIGH_PRIORITY_WATCH":
            event = _watch_event(snapshot, snapshots)
            if event and event["event_id"] not in existing:
                new.append(event); existing.add(event["event_id"])
            continue
        candles = _completed_candles(snapshot, as_of, market_dir)
        trigger = next((e for e in by_snapshot.get(snapshot["snapshot_id"], []) if e.get("event_type") == "TRIGGERED"), None)
        if trigger is None:
            trigger = _find_trigger(snapshot, candles)
            if trigger and trigger["event_id"] not in existing:
                new.append(trigger); existing.add(trigger["event_id"])
        if trigger:
            for event in _horizon_events(snapshot, trigger, candles):
                if event["event_id"] not in existing:
                    new.append(event); existing.add(event["event_id"])
    return new


def _bucket(value: Any) -> str:
    if value is None:
        return "MISSING"
    number = max(0.0, min(100.0, float(value)))
    if number >= 80: return "80-100"
    lower = int(number // 20) * 20
    return f"{lower}-{lower + 20}"


def _group_summary(rows: list[dict], event_map: dict[str, list[dict]], field: str) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        key = _bucket(row.get(field)) if field.endswith("_score") else str(row.get(field) or "MISSING")
        groups.setdefault(key, []).append(row)
    output = []
    for key in sorted(groups):
        members = groups[key]
        counterfactual = all(r.get("recommendation") == "AVOID" or r.get("technical_action") == "AVOID" for r in members)
        outcomes = [e for r in members for e in event_map.get(r["snapshot_id"], []) if e.get("event_type") == "HORIZON_OUTCOME"]
        result = {"group": key, "snapshot_count": len(members), "counterfactual_only": counterfactual,
                  "triggered_count": sum(any(e.get("event_type") == "TRIGGERED" for e in event_map.get(r["snapshot_id"], [])) for r in members)}
        for horizon in HORIZONS:
            sample = [float(e["return_pct"]) for e in outcomes if e.get("horizon_hours") == horizon]
            result[f"return_{horizon}h"] = {
                "sample_size": len(sample),
                "status": "COUNTERFACTUAL_EXCLUDED" if counterfactual else "INSUFFICIENT_SAMPLE" if len(sample) < MIN_EDGE_SAMPLE else "FORWARD_SAMPLE_AVAILABLE",
                "mean_return_pct": None if counterfactual or len(sample) < MIN_EDGE_SAMPLE else sum(sample) / len(sample),
                "positive_rate_pct": None if counterfactual or len(sample) < MIN_EDGE_SAMPLE else 100 * sum(x > 0 for x in sample) / len(sample),
            }
        output.append(result)
    return output


def build_summary(snapshots: list[dict], events: list[dict], generated_at: str) -> dict:
    event_map: dict[str, list[dict]] = {}
    for event in events:
        event_map.setdefault(event.get("snapshot_id"), []).append(event)
    statuses = []
    for row in snapshots:
        own = event_map.get(row["snapshot_id"], [])
        types = {e.get("event_type") for e in own}
        if row.get("technical_action") == "AVOID" or row.get("recommendation") == "AVOID": status = "AVOID_COUNTERFACTUAL"
        elif "WATCH_ACTIVATED" in types: status = "ACTIVATED"
        elif "WATCH_INVALIDATED" in types: status = "INVALIDATED_BEFORE_ACTIVATION"
        elif row.get("technical_action") == "WATCH" or row.get("recommendation") == "HIGH_PRIORITY_WATCH": status = "WATCHING"
        elif "TRIGGERED" in types: status = "TRIGGERED"
        else: status = "NOT_TRIGGERED"
        statuses.append({"snapshot_id": row["snapshot_id"], "asset": row["asset"], "status": status})
    dimensions = {
        "by_opportunity_family": "opportunity_family",
        "by_recommendation": "recommendation", "by_technical_action": "technical_action",
        "by_setup_quality_bucket": "setup_quality_score", "by_actionability_bucket": "actionability_score",
        "by_daily_score_bucket": "daily_score", "by_weekly_score_bucket": "weekly_score",
        "by_planned_trade_family": "planned_trade_family",
    }
    return {
        "generated_at_utc": generated_at, "purpose": "FORWARD_VALIDATION_ONLY",
        "look_ahead_policy": "ONLY_CANDLES_STARTING_AFTER_SNAPSHOT_AND_COMPLETED_BY_AS_OF",
        "minimum_sample_for_published_edge": MIN_EDGE_SAMPLE,
        "totals": {"snapshots": len(snapshots), "events": len(events)},
        "current_snapshot_status": statuses,
        "unresolved_observations":sum(s["status"] in {"WATCHING","NOT_TRIGGERED"} for s in statuses),
        "results": {name: _group_summary(snapshots, event_map, field) for name, field in dimensions.items()},
        "controls": ["OUTCOMES_DO_NOT_CHANGE_SCORING", "SNAPSHOTS_AND_EVENTS_ARE_APPEND_ONLY", "AVOID_IS_COUNTERFACTUAL_ONLY"],
    }


def run(packet: dict, as_of: Any = None, dataset_dir: Path = DATASET_DIR,
        summary_dir: Path = SUMMARY_DIR, market_dir: Path | None = None) -> tuple[Path, dict]:
    dataset_dir = Path(dataset_dir); summary_dir = Path(summary_dir)
    market_dir = Path(market_dir or ROOT / "DATASETS/market_intraday_weekly")
    as_of_ts = _utc(as_of or utc_timestamp())
    snapshot_path = dataset_dir / SNAPSHOTS; event_path = dataset_dir / EVENTS
    dataset_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path.touch(exist_ok=True); event_path.touch(exist_ok=True)
    existing_snapshots = _read_jsonl(snapshot_path)
    known = {row.get("snapshot_id") for row in existing_snapshots}
    added = [row for row in build_snapshots(packet) if row["snapshot_id"] not in known]
    _append_jsonl(snapshot_path, added)
    snapshots = existing_snapshots + added
    events = _read_jsonl(event_path)
    new_events = update_events(snapshots, events, as_of_ts, market_dir)
    _append_jsonl(event_path, new_events)
    summary = build_summary(snapshots, events + new_events, as_of_ts.isoformat())
    output = summary_dir / SUMMARY
    atomic_write(output, json.dumps(_clean(summary), indent=2, sort_keys=True))
    return output, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Append-only tactical forward outcome tracker")
    parser.add_argument("--packet", default=str(ROOT / "DAILY_REPORTS/CHATGPT_EXPORT/latest_ai_chief_strategist_packet.json"))
    parser.add_argument("--as-of")
    args = parser.parse_args()
    packet = json.loads(Path(args.packet).read_text())
    path, summary = run(packet, args.as_of)
    print(f"Tactical outcome summary: {path}")
    print(f"Snapshots: {summary['totals']['snapshots']} | Events: {summary['totals']['events']}")


if __name__ == "__main__":
    main()
