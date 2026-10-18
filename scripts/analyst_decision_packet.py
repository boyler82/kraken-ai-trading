#!/usr/bin/env python3
"""Build the compact, machine-oriented Analyst Decision Packet.

This module is deliberately read-only with respect to research inputs, journals,
SQLite databases, strategies, and orders.  Its only writes are packet artifacts.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "DAILY_REPORTS"
OUT = REPORTS / "ANALYST_PACKET"
VERSION = "1.0.0"
NULL = None


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


def num(value: Any) -> float | int | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
        if not math.isfinite(result):
            return None
        return int(result) if result.is_integer() else result
    except (TypeError, ValueError):
        return None


def boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if str(value).lower() in {"true", "1", "yes"}:
        return True
    if str(value).lower() in {"false", "0", "no"}:
        return False
    return None


def utc(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def pct_change(target: Any, current: Any) -> float | None:
    t, c = num(target), num(current)
    return None if t is None or c in (None, 0) else (t / c - 1) * 100


def ratio(reward: Any, risk: Any) -> float | None:
    a, b = num(reward), num(risk)
    return None if a is None or b in (None, 0) else a / abs(b)


def split_flags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value if x not in (None, "")]
    if value in (None, "", "[]", "NONE"):
        return []
    return [x.strip() for x in re.split(r"[|,;]", str(value).strip("[]")) if x.strip()]


def latest_date_path(directory: Path, suffix: str, report_date: str) -> Path:
    dated = directory / f"{report_date}_{suffix}"
    latest = directory / f"latest_{suffix}"
    return dated if dated.exists() else latest


def regime_context(report_date: str, momentum: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    path = REPORTS / f"{report_date}_research_regime.csv"
    rows = read_csv(path)
    lookup = {r.get("metric"): r.get("value") for r in rows}
    candidates = momentum.get("candidates", [])
    btc = next((x for x in candidates if x.get("asset") == "BTC"), {})
    improving = sum(num(x.get("acceleration_24h_pct")) > 0 for x in candidates if num(x.get("acceleration_24h_pct")) is not None)
    deteriorating = sum(num(x.get("acceleration_24h_pct")) < 0 for x in candidates if num(x.get("acceleration_24h_pct")) is not None)
    return {
        "crypto_regime": lookup.get("crypto_regime", "UNKNOWN"),
        "volatility_regime": lookup.get("volatility_regime", "UNKNOWN"),
        "opportunity_regime": lookup.get("opportunity_regime", "UNKNOWN"),
        "environment_score": num(lookup.get("environment_score")),
        "environment_status": lookup.get("environment_status", "UNKNOWN"),
        "btc_price": num(btc.get("current_price")),
        "btc_return_24h_pct": num(btc.get("change_24h_pct")),
        "btc_return_48h_pct": num(btc.get("change_48h_pct")),
        "btc_atr_pct": num(btc.get("atr14_pct")),
        "btc_trend_state": ("UP" if num(btc.get("ema20_slope_pct")) is not None and num(btc.get("ema20_slope_pct")) > 0 else "DOWN" if num(btc.get("ema20_slope_pct")) is not None else "UNKNOWN"),
        "breadth": {"improving_count": improving, "deteriorating_count": deteriorating, "unchanged_count": len(candidates) - improving - deteriorating},
        "data_timestamp": utc(btc.get("latest_completed_candle_timestamp") or momentum.get("generated_at_utc")),
        "freshness": btc.get("freshness_status", "UNKNOWN"),
    }, path


def consolidations(source: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for x in source.get("candidates", []):
        price, low, mid, high = (num(x.get(k)) for k in ("latest_available_market_price", "range_low", "midpoint", "range_high"))
        friction = num(x.get("estimated_total_friction_pct"))
        gross_mid, gross_high = pct_change(mid, price), pct_change(high, price)
        downside_low = pct_change(low, price)
        false_count = (num(x.get("false_breakouts_above")) or 0) + (num(x.get("false_breakdowns_below")) or 0)
        valid = boolean(x.get("range_still_valid"))
        row = {
            "asset": x.get("asset"), "pair": x.get("kraken_pair"), "current_price": price,
            "source_timestamp": utc(x.get("latest_available_market_timestamp") or x.get("latest_completed_candle_timestamp")),
            "freshness": x.get("freshness_status", "UNKNOWN"), "range_low": low, "midpoint": mid, "range_high": high,
            "position_pct": num(x.get("position_pct")), "gross_return_to_midpoint_pct": gross_mid,
            "net_return_to_midpoint_pct": None if gross_mid is None or friction is None else gross_mid - friction,
            "gross_return_to_high_pct": gross_high, "net_return_to_high_pct": None if gross_high is None or friction is None else gross_high - friction,
            "downside_to_range_low_pct": downside_low, "downside_to_invalidation_pct": downside_low,
            "risk_reward_to_midpoint": ratio(gross_mid, downside_low), "risk_reward_to_high": ratio(gross_high, downside_low),
            "average_cycle_hours": num(x.get("average_full_cycle_hours")), "cycles_per_30d": num(x.get("estimated_cycles_per_30d")),
            "lower_tests": num(x.get("lower_boundary_tests")), "upper_tests": num(x.get("upper_boundary_tests")),
            "false_break_count": false_count, "range_quality": num(x.get("range_quality")),
            "opportunity_score": num(x.get("daily_range_opportunity_score")), "breakout_risk": x.get("breakout_risk", "UNKNOWN"),
            "range_valid": valid, "primary_risk": (split_flags(x.get("risk_flags")) or ["NONE"])[0],
            "invalidation_condition": None if low is None else f"CLOSE_BELOW_RANGE_LOW:{low}",
        }
        pos = row["position_pct"]
        row["_rank"] = (valid is not True, row["freshness"] != "FRESH", not (pos is not None and 0 <= pos <= 30), -(row["risk_reward_to_midpoint"] or -999), -(row["range_quality"] or -999), row["average_cycle_hours"] or math.inf, false_count, str(row["asset"]))
        out.append(row)
    out.sort(key=lambda r: r.pop("_rank"))
    return out[:4]


def momentum_candidates(source: dict[str, Any]) -> list[dict[str, Any]]:
    stage_order = {"EARLY_MOMENTUM": 0, "BREAKOUT_DEVELOPING": 1, "BREAKOUT_CONFIRMED": 2, "EXTENDED_MOVE": 3}
    rows = []
    for x in source.get("candidates", []):
        stage = x.get("momentum_stage", "NO_MOMENTUM")
        if stage == "NO_MOMENTUM":
            continue
        flags = []
        if x.get("overextension_risk") not in (None, "LOW", "NONE"):
            flags.append("OVEREXTENSION")
        if boolean(x.get("failed_breakout")):
            flags.append("FAILED_BREAKOUT")
        breakout = num(x.get("breakout_level")); price = num(x.get("current_price"))
        row = {
            "asset": x.get("asset"), "pair": x.get("kraken_pair"), "stage": stage, "current_price": price,
            "source_timestamp": utc(x.get("latest_completed_candle_timestamp")), "freshness": x.get("freshness_status", "UNKNOWN"),
            "return_4h_pct": num(x.get("change_4h_pct")), "return_12h_pct": num(x.get("change_12h_pct")),
            "return_24h_pct": num(x.get("change_24h_pct")), "return_48h_pct": num(x.get("change_48h_pct")),
            "relative_return_vs_btc_24h_pct": num(x.get("relative_strength_vs_btc_24h_pct")),
            "relative_return_vs_btc_48h_pct": num(x.get("relative_strength_vs_btc_48h_pct")),
            "acceleration": num(x.get("acceleration_24h_pct")), "volume_zscore": num(x.get("volume_z_score")),
            "volume_ratio": num(x.get("volume_ratio")), "volatility_expansion": num(x.get("volatility_expansion_ratio")),
            "breakout_level": breakout, "distance_to_breakout_pct": pct_change(breakout, price),
            "confirmation_closes": num(x.get("number_completed_closes_above_breakout")),
            "consolidation_to_breakout_transition": x.get("consolidation_transition"),
            "EMA20_distance_ATR": num(x.get("distance_above_ema20_atr")), "extension_risk": x.get("overextension_risk", "UNKNOWN"),
            "momentum_score": num(x.get("momentum_breakout_score")), "primary_risk": (flags or ["NONE"])[0],
            "invalidation_condition": None if breakout is None else f"CLOSE_BELOW_BREAKOUT_LEVEL:{breakout}",
        }
        row["_rank"] = (stage_order.get(stage, 9), row["freshness"] != "FRESH", -(row["momentum_score"] or -999), str(row["asset"]))
        rows.append(row)
    rows.sort(key=lambda r: r.pop("_rank"))
    primary = [r for r in rows if r["stage"] != "EXTENDED_MOVE"]
    return (primary or rows)[:5]


def rotation(source: dict[str, Any]) -> dict[str, Any]:
    all_candidates = source.get("top_candidates", [])
    positive = [x for x in all_candidates if (num(x.get("net_relative_upside_after_costs")) or 0) > 0]
    rejected = [x for x in all_candidates if x not in positive]
    def candidate(x: dict[str, Any]) -> dict[str, Any]:
        return {
            "asset": x.get("asset"), "score": num(x.get("alt_rotation_score")), "BTC_score": num(x.get("btc_hold_score")),
            "score_advantage": num(x.get("score_advantage")), "relative_return_24h_pct": num(x.get("relative_return_24h_pct")),
            "relative_return_48h_pct": num(x.get("relative_return_48h_pct")), "relative_return_7d_pct": num(x.get("relative_return_7d_pct")),
            "theoretical_net_relative_edge_pct": num(x.get("net_relative_upside_after_costs")),
            "theoretical_relative_downside_pct": num(x.get("theoretical_relative_downside_to_invalidation_pct")),
            "relative_risk_reward": num(x.get("relative_risk_reward")), "holding_window": x.get("expected_holding_window"),
            "overextension_risk": x.get("overextension_risk", "UNKNOWN"), "liquidity_status": "PASS" if x.get("liquidity_pass") is True else "FAIL",
            "historical_sample_size": num(x.get("historical_sample_size")), "historical_win_rate": num(x.get("historical_win_rate")),
            "expected_value": num(x.get("expected_value")), "invalidation_condition": x.get("invalidation_condition"),
            "risk_flags": split_flags(x.get("risk_flags")),
        }
    best = positive[0] if positive else None
    return {
        "objective": source.get("objective", "BTC_ACCUMULATION"), "current_holding": source.get("current_holding", "UNKNOWN"),
        "BTC_hold_score": num(source.get("btc_hold_score")), "preferred_state": source.get("preferred_state", "UNKNOWN"),
        "cost_guard": source.get("rotation_cost_guard", "UNKNOWN"), "cooldown_status": source.get("rotation_cooldown_status", "UNKNOWN"),
        "minimum_required_edge_pct": num(best.get("break_even_outperformance_vs_btc")) if best else None,
        "confidence": source.get("confidence", "UNKNOWN"), "best_candidate": best.get("asset") if best else None,
        "best_candidate_score": num(best.get("alt_rotation_score")) if best else None, "BTC_score": num(source.get("btc_hold_score")),
        "score_advantage": num(best.get("score_advantage")) if best else None,
        "relative_return_24h_pct": num(best.get("relative_return_24h_pct")) if best else None,
        "relative_return_48h_pct": num(best.get("relative_return_48h_pct")) if best else None,
        "relative_return_7d_pct": num(best.get("relative_return_7d_pct")) if best else None,
        "theoretical_net_relative_edge_pct": num(best.get("net_relative_upside_after_costs")) if best else None,
        "theoretical_relative_downside_pct": num(best.get("theoretical_relative_downside_to_invalidation_pct")) if best else None,
        "relative_risk_reward": num(best.get("relative_risk_reward")) if best else None,
        "holding_window": best.get("expected_holding_window") if best else None,
        "overextension_risk": best.get("overextension_risk", "UNKNOWN") if best else "UNKNOWN",
        "liquidity_status": ("PASS" if best.get("liquidity_pass") is True else "FAIL") if best else "UNKNOWN",
        "historical_sample_size": num(best.get("historical_sample_size")) if best else None,
        "historical_win_rate": num(best.get("historical_win_rate")) if best else None, "expected_value": num(best.get("expected_value")) if best else None,
        "invalidation_condition": best.get("invalidation_condition") if best else source.get("main_invalidation_condition"),
        "risk_flags": split_flags(best.get("risk_flags")) if best else ["NO_POSITIVE_AFTER_COST_ALTERNATIVE"],
        "preferred_candidate": candidate(best) if best else None,
        "alternatives": [candidate(x) for x in positive[1:3]],
        "rejected_candidates": [{"asset": x.get("asset"), "rejection_reason": "NON_POSITIVE_EDGE_AFTER_COSTS"} for x in rejected],
    }


def rsi2(report_date: str) -> tuple[dict[str, Any], Path]:
    path = REPORTS / f"{report_date}_trade_candidate_dashboard.csv"
    rows = read_csv(path)
    actionable = [r.get("asset") for r in rows if r.get("current_setup_status") == "ACTIONABLE"]
    developing = [r.get("asset") for r in rows if r.get("current_setup_status") == "DEVELOPING"]
    current = "ACTIONABLE" if actionable else "DEVELOPING" if developing else "WAIT"
    relevant = [r for r in rows if r.get("asset") in actionable + developing][:5]
    ready = max((num(r.get("readiness_pct")) or 0 for r in relevant), default=None)
    limitation = "NO_CURRENT_RSI2_EPISODE" if not relevant else None
    assets = [{"asset": r.get("asset"), "readiness": num(r.get("readiness_pct")), "research_score": num(r.get("research_score")), "reason_for_no_signal": r.get("missing_conditions")} for r in relevant]
    return {"current_state": current, "actionable_assets": actionable[:5], "developing_assets": developing[:5], "relevant_assets": assets,
            "highest_readiness": ready, "next_trigger": "NEW_OVERSOLD_EPISODE" if current == "WAIT" else "ENTRY_CONDITIONS_COMPLETE",
            "sample_quality": "UNKNOWN" if not rows else "AVAILABLE", "main_limitation": limitation}, path


def donchian(report_date: str) -> tuple[dict[str, Any], list[Path]]:
    base = REPORTS / "BTC_4H_DONCHIAN_V1"
    dashboard = latest_date_path(base, "forward_dashboard.csv", report_date)
    signals = latest_date_path(base, "paper_signals.csv", report_date)
    lookup = {r.get("section"): r.get("value") for r in read_csv(dashboard)}
    trades = read_csv(signals)
    timestamps = [num(r.get("actual_exit_timestamp") or r.get("actual_entry_timestamp")) for r in trades]
    latest = max((x for x in timestamps if x is not None), default=None)
    latest_iso = datetime.fromtimestamp(latest, timezone.utc).isoformat() if latest else None
    return {"current_signal": lookup.get("Current signal status", "UNKNOWN"), "open_positions": num(lookup.get("Open paper positions")),
            "pending_entries": num(lookup.get("Pending entries")), "closed_trade_count": sum(r.get("status") == "CLOSED" for r in trades),
            "observation_progress": lookup.get("Observation progress"), "latest_data_timestamp": latest_iso,
            "main_limitation": "PAPER_SAMPLE_ONLY" if len(trades) < 30 else None}, [dashboard, signals]


def active_positions(consolidation_rows: list[dict[str, Any]], momentum_rows: list[dict[str, Any]], generated: datetime) -> tuple[dict[str, Any], Path]:
    path = ROOT / "journal" / "portfolio_positions.csv"
    rows = read_csv(path); by_range = {x["asset"]: x for x in consolidation_rows}; by_mom = {x["asset"]: x for x in momentum_rows}
    positions = []
    for x in rows:
        asset = x.get("asset"); qty = num(x.get("quantity")); entry = num(x.get("entry_price")); c = by_range.get(asset); m = by_mom.get(asset)
        price = c.get("current_price") if c else m.get("current_price") if m else None
        gross = pct_change(price, entry); friction = 0.6
        invalid = c.get("range_low") if c else m.get("breakout_level") if m else None
        target = c.get("midpoint") if c else m.get("breakout_level") if m else None
        entered = utc(x.get("entry_timestamp") or x.get("entry_date")); holding = None
        if entered:
            holding = (generated - datetime.fromisoformat(entered)).total_seconds() / 3600
        target_upside = pct_change(target, price); invalid_downside = pct_change(invalid, price)
        positions.append({"asset": asset, "entry_timestamp": entered, "entry_price": entry, "quantity": qty, "invested_value": num(x.get("cost_basis")) or (entry * qty if entry is not None and qty is not None else None), "fees": num(x.get("fees")),
            "current_price": price, "gross_pnl_pct": gross, "estimated_net_pnl_pct": None if gross is None else gross - friction,
            "strategy_hypothesis": "CONSOLIDATION" if c else "MOMENTUM" if m else "UNKNOWN",
            "relevant_range_low": c.get("range_low") if c else None, "relevant_midpoint": c.get("midpoint") if c else None,
            "relevant_range_high": c.get("range_high") if c else None, "invalidation_level": invalid,
            "downside_to_invalidation_pct": invalid_downside, "first_target": target,
            "upside_to_first_target_pct": target_upside, "risk_reward": ratio(target_upside, invalid_downside),
            "current_hypothesis_status": ("VALID" if c and c.get("range_valid") else "ACTIVE" if m else "UNKNOWN"),
            "holding_time": None if holding is None else {"hours": holding},
            "current_risk_flags": ([] if price is not None else ["CURRENT_PRICE_UNAVAILABLE"]) + ([] if invalid is not None else ["INVALIDATION_UNAVAILABLE"])})
    return {"open_positions": positions, "position_data_missing_for_TAO": not any(x.get("asset") == "TAO" for x in rows)}, path


def confirmations(con: list[dict[str, Any]], mom: list[dict[str, Any]], rot: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rotation_candidates = ([rot["preferred_candidate"]] if rot.get("preferred_candidate") else []) + rot.get("alternatives", [])
    assets = sorted({x["asset"] for x in con + mom} | {x["asset"] for x in rotation_candidates})
    agrees, conflicts = [], []
    for asset in assets:
        support, conflict = [], []
        c = next((x for x in con if x["asset"] == asset), None); m = next((x for x in mom if x["asset"] == asset), None)
        if c and c["range_valid"]: support.append("VALID_CONSOLIDATION")
        if c and c["position_pct"] is not None and 0 <= c["position_pct"] <= 30: support.append("LOWER_30_PERCENT")
        if m: support.append(m["stage"])
        if m and (m["relative_return_vs_btc_24h_pct"] or 0) > 0: support.append("POSITIVE_RELATIVE_STRENGTH")
        if any(x["asset"] == asset for x in rotation_candidates): support.append("POSITIVE_ROTATION_EDGE")
        if m and m["extension_risk"] in {"HIGH", "EXTREME"}: conflict.append("OVEREXTENSION")
        if c and c["range_valid"] is False: conflict.append("RANGE_INVALID")
        if len(support) >= 2: agrees.append({"asset": asset, "agreement": support, "support_count": len(support)})
        if support and conflict: conflicts.append({"asset": asset, "support": support, "conflict": conflict, "interpretation_required": True})
    return agrees, conflicts


def risks(context: dict[str, Any], con: list[dict[str, Any]], mom: list[dict[str, Any]], rot: dict[str, Any], manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    severity = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}; out = []
    def add(level: str, asset: str, code: str, evidence: Any, hypothesis: str) -> None:
        out.append({"severity": level, "asset": asset, "code": code, "evidence": evidence, "affected_hypothesis": hypothesis})
    if context["crypto_regime"] == "BEAR": add("HIGH", "MARKET", "BEAR_MARKET_REGIME", "crypto_regime=BEAR", "ALL")
    for x in con:
        if x["false_break_count"] >= 3: add("HIGH", x["asset"], "EXCESSIVE_FALSE_BREAKS", x["false_break_count"], "CONSOLIDATION")
        if x["freshness"] != "FRESH": add("HIGH", x["asset"], "STALE_DATA", x["freshness"], "CONSOLIDATION")
    for x in mom:
        if x["extension_risk"] in {"HIGH", "EXTREME"}: add("HIGH", x["asset"], "OVEREXTENSION", x["extension_risk"], "MOMENTUM")
    if not rot["preferred_candidate"]: add("MEDIUM", "MARKET", "COSTS_EXCEED_EDGE", rot["cost_guard"], "ROTATION")
    for x in manifest:
        if x["freshness"] not in {"FRESH", "UNKNOWN"}: add("HIGH", "MARKET", "STALE_DATA", x["path"], "ALL")
    return sorted(out, key=lambda x: (severity[x["severity"]], x["asset"], x["code"]))[:10]


def run_status() -> tuple[dict[str, Any], Path]:
    path = ROOT / "logs" / "latest_research_run.json"
    source = read_json(path)
    return {
        "pipeline_status": source.get("pipeline_status", "UNKNOWN"),
        "completed_modules": source.get("completed_modules", []),
        "failed_modules": source.get("failed_modules", []),
        "warnings_count": num(source.get("warnings_count")),
        "source_timestamps": {"pipeline": utc(source.get("generated_at_utc"))},
        "overall_freshness": "FRESH" if source.get("pipeline_status") == "SUCCESS" else "UNKNOWN",
    }, path


def validation_feedback(report_date: str, relevant_assets: set[str]) -> tuple[list[dict[str, Any]], list[Path]]:
    feedback_path = REPORTS / f"{report_date}_research_feedback.csv"
    validation_path = REPORTS / f"{report_date}_research_validation.csv"
    rows = [r for r in read_csv(feedback_path) if r.get("asset") in relevant_assets][:5]
    records = [{
        "asset": r.get("asset"), "historical_sample_size": num(r.get("paper_trades")),
        "realized_win_rate_pct": num(r.get("paper_win_rate_pct")), "realized_average_return_pct": num(r.get("paper_avg_return_pct")),
        "expected_value_pct": num(r.get("historical_expected_value_pct")), "EV_gap_pct": num(r.get("ev_gap")),
        "validation_grade": r.get("feedback_grade", "UNKNOWN"),
        "confidence_implication": "LOW" if (num(r.get("paper_trades")) or 0) < 10 else "MEDIUM",
    } for r in rows]
    return records, [feedback_path, validation_path]


def analyst_questions(con: list[dict[str, Any]], mom: list[dict[str, Any]], rot: dict[str, Any], positions: dict[str, Any]) -> list[str]:
    questions = []
    for position in positions.get("open_positions", [])[:1]:
        questions.append(f"DOES_{position['asset']}_RISK_REWARD_REMAIN_POSITIVE_AFTER_ACTUAL_ENTRY_AND_COSTS")
    if con:
        questions.append(f"DO_FALSE_BREAKS_INVALIDATE_{con[0]['asset']}_CONSOLIDATION_QUALITY")
        questions.append(f"DOES_{con[0]['asset']}_JUSTIFY_CYCLE_TIME")
    if mom:
        questions.append(f"IS_{mom[0]['asset']}_BREAKOUT_TOO_EXTENDED_RELATIVE_TO_ATR")
    questions.append("IS_BTC_ROTATION_EDGE_SUFFICIENT_AFTER_COSTS")
    return questions[:5]


def validate(packet: dict[str, Any], sources: list[Path]) -> None:
    required = ["packet_version", "generated_at_utc", "report_date", "objective", "current_holding", "run_status", "market_context", "decision_summary", "active_position_context", "top_consolidations", "top_momentum", "rotation", "rsi2", "donchian", "validation_feedback", "cross_module_confirmations", "cross_module_conflicts", "risk_summary", "unknowns", "analyst_questions", "data_quality", "source_manifest"]
    assert list(packet) == required, "canonical top-level schema mismatch"
    assert utc(packet["generated_at_utc"]), "generated_at_utc must be UTC timestamp"
    assert len(packet["top_consolidations"]) <= 4 and len(packet["top_momentum"]) <= 5
    for key in ("top_consolidations", "top_momentum"):
        assets = [x["asset"] for x in packet[key]]; assert len(assets) == len(set(assets)), f"duplicate candidate in {key}"
        for row in packet[key]:
            assert row["freshness"] is not None, "freshness must be explicit"
            if row["source_timestamp"] is not None:
                assert utc(row["source_timestamp"]), "candidate timestamp must be UTC"
    for row in packet["top_consolidations"]:
        for key in ("risk_reward_to_midpoint", "risk_reward_to_high"):
            assert key in row, "risk/reward input must be present or null"
        for key in ("range_quality", "opportunity_score"):
            value = row[key]
            assert value is None or 0 <= value <= 100, f"{key} outside 0..100"
    for row in packet["top_momentum"]:
        value = row["momentum_score"]
        assert value is None or 0 <= value <= 100, "momentum_score outside 0..100"
    assert all(path.exists() for path in sources), "source paths must exist"
    def walk(x: Any) -> None:
        if isinstance(x, float): assert math.isfinite(x), "non-finite number"
        elif isinstance(x, dict):
            assert len(x) == len(set(x)), "duplicate field"
            for value in x.values(): walk(value)
        elif isinstance(x, list):
            for value in x: walk(value)
    walk(packet)
    json.dumps(packet, allow_nan=False)


def render_markdown(packet: dict[str, Any]) -> str:
    lines = [f"packet_version: {packet['packet_version']}", f"generated_at_utc: {packet['generated_at_utc']}", f"report_date: {packet['report_date']}", f"objective: {packet['objective']} | current_holding: {packet['current_holding']}"]
    for key in list(packet)[5:]:
        lines.append(f"## {key}")
        value = packet[key]
        if isinstance(value, dict):
            for field, field_value in value.items():
                lines.append(f"{field}: {json.dumps(field_value, sort_keys=True, separators=(',', ':'), allow_nan=False)}")
        elif isinstance(value, list):
            lines.extend(f"- {json.dumps(item, sort_keys=True, separators=(',', ':'), allow_nan=False)}" for item in value)
        else:
            lines.append(json.dumps(value, allow_nan=False))
    # Keep this human index within its established 80–150 line information budget.
    return "\n".join(lines[:150]) + "\n"


def build(report_date: str, generated_at: str | None = None) -> dict[str, Any]:
    generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00")).astimezone(timezone.utc) if generated_at else datetime.now(timezone.utc)
    con_path = latest_date_path(REPORTS / "DAILY_CONSOLIDATION", "daily_consolidation_scan.json", report_date)
    mom_path = latest_date_path(REPORTS / "MOMENTUM_BREAKOUT", "momentum_breakout_radar.json", report_date)
    rot_path = REPORTS / "BTC_ROTATION" / "latest_btc_rotation_dashboard.json"
    con_source, mom_source, rot_source = read_json(con_path), read_json(mom_path), read_json(rot_path)
    context, regime_path = regime_context(report_date, mom_source); con = consolidations(con_source); mom = momentum_candidates(mom_source); rot = rotation(rot_source)
    rsi, rsi_path = rsi2(report_date); don, don_paths = donchian(report_date); positions, portfolio_path = active_positions(con, mom, generated)
    status, status_path = run_status()
    agrees, conflicts = confirmations(con, mom, rot)
    rotation_relevant = ([rot["preferred_candidate"]] if rot.get("preferred_candidate") else []) + rot.get("alternatives", [])
    relevant_assets = {x["asset"] for x in con + mom + rotation_relevant + positions.get("open_positions", [])}
    feedback, feedback_paths = validation_feedback(report_date, relevant_assets)
    sources = [con_path, mom_path, rot_path, regime_path, rsi_path, portfolio_path, *don_paths, *feedback_paths]
    if status_path.exists():
        sources.append(status_path)
    manifest = [{"path": str(p.relative_to(ROOT)), "source_timestamp": utc(read_json(p).get("generated_at_utc")) if p.suffix == ".json" else datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(), "freshness": "FRESH" if p.exists() else "MISSING"} for p in sources]
    risk = risks(context, con, mom, rot, manifest)
    hypotheses = [("CONSOLIDATION", con[0]) if con else None, ("MOMENTUM", mom[0]) if mom else None, ("ROTATION", rot["preferred_candidate"]) if rot["preferred_candidate"] else None]
    hypotheses = [x for x in hypotheses if x]; strongest = hypotheses[0] if hypotheses else None
    unknowns = []
    if rot["historical_sample_size"] in (None, 0): unknowns += ["PROBABILITY_UNAVAILABLE", "INSUFFICIENT_SAMPLE"]
    unknowns += ["MISSING_ORDER_BOOK_DEPTH", "UNCERTAIN_SLIPPAGE", "UNAVAILABLE_ON_CHAIN_DATA", "UNAVAILABLE_DERIVATIVES_DATA"]
    if context["crypto_regime"] in {"MIXED", "UNKNOWN"}: unknowns.append("REGIME_INSTABILITY")
    if not positions["open_positions"] and positions["position_data_missing_for_TAO"]: unknowns.append("MISSING_POSITION_RECORD_FOR_TAO")
    state = "ACTIVE_RESEARCH_EVIDENCE" if con or mom or rot["preferred_candidate"] else "WAIT"
    packet = {
        "packet_version": VERSION, "generated_at_utc": generated.isoformat(), "report_date": report_date,
        "objective": rot["objective"], "current_holding": rot["current_holding"], "run_status": status, "market_context": context,
        "decision_summary": {"rsi2_state": rsi["current_state"], "consolidation_state": "ACTIVE" if con else "NONE", "momentum_state": "ACTIVE" if mom else "NONE", "rotation_state": rot["preferred_state"], "donchian_state": don["current_signal"], "overall_research_state": state, "strongest_current_hypothesis": strongest[0] if strongest else None, "strongest_candidate": strongest[1].get("asset") if strongest else None, "strongest_candidate_type": strongest[0] if strongest else None, "strongest_reason": ("VALID_FRESH_RANKED_CANDIDATE" if strongest else None), "primary_invalidation": strongest[1].get("invalidation_condition") if strongest else None, "immediate_action_requirement": "MANUAL_REVIEW" if strongest else "NONE", "confidence": rot["confidence"], "evidence_count": len(agrees), "conflict_count": len(conflicts)},
        "active_position_context": positions, "top_consolidations": con, "top_momentum": mom, "rotation": {**rot, "broad_regime": context["crypto_regime"]}, "rsi2": rsi, "donchian": don,
        "validation_feedback": feedback, "cross_module_confirmations": agrees[:10], "cross_module_conflicts": conflicts[:10], "risk_summary": risk, "unknowns": list(dict.fromkeys(unknowns)),
        "analyst_questions": analyst_questions(con, mom, rot, positions),
        "data_quality": {"status": "PASS" if all(p.exists() for p in sources) else "FAIL", "source_count": len(sources), "missing_source_count": sum(not p.exists() for p in sources), "validation_errors": []},
        "source_manifest": manifest,
    }
    validate(packet, sources)
    return packet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=datetime.now().astimezone().date().isoformat())
    parser.add_argument("--generated-at", help="UTC ISO timestamp; useful for deterministic replay")
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args(); packet = build(args.date, args.generated_at); markdown = render_markdown(packet)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(packet, indent=2, sort_keys=False, allow_nan=False) + "\n"
    for name, content in ((f"{args.date}_analyst_decision_packet.json", json_text), ("latest_analyst_decision_packet.json", json_text), (f"{args.date}_analyst_decision_packet.md", markdown), ("latest_analyst_decision_packet.md", markdown)):
        (args.output_dir / name).write_text(content)
    print(args.output_dir / f"{args.date}_analyst_decision_packet.json")


if __name__ == "__main__":
    main()
