from __future__ import annotations

from typing import Any


ALLOWED_ACTIONS = {"BUY_NOW", "BUY_ON_BREAKOUT", "BUY_ON_PULLBACK", "WATCH", "AVOID"}
ALLOWED_RECOMMENDATIONS = {"ACTIONABLE", "SPECULATIVE_REVIEW", "HIGH_PRIORITY_WATCH", "WATCH", "AVOID"}
ALLOWED_CONVICTIONS = {"HIGH", "MEDIUM", "LOW", "VERY_LOW"}
MIN_ACTIONABLE_SETUP = 40.0
MIN_ACTIONABLE_ACTIONABILITY = 60.0
HIGH_QUALITY_SETUP = 60.0


def _number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if number == number else None
    except (TypeError, ValueError):
        return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _unique(values: list[Any]) -> list[Any]:
    result = []
    for value in values:
        if value is not None and value not in result:
            result.append(value)
    return result


def _upper(value: Any) -> str:
    return str(value or "").upper()


def _classify(candidate: dict) -> tuple[str, Any, str | None, Any, list[str]]:
    momentum = candidate.get("momentum", {})
    consolidation = candidate.get("consolidation", {})
    current = candidate.get("current_data", {})
    stage = _upper(momentum.get("stage")) or "UNKNOWN"
    extension = _upper(momentum.get("extension_risk"))
    range_state = _upper(consolidation.get("range_state"))
    position = _number(consolidation.get("position_percent"))
    breakout = momentum.get("breakout_level")
    activation = momentum.get("activation_condition")
    invalidation = momentum.get("invalidation_condition") or candidate.get("evidence", {}).get("invalidation_condition")

    if _upper(current.get("freshness")) not in {"", "FRESH"}:
        return "AVOID", None, None, invalidation, ["STALE_DATA"]
    if stage == "FAILED_BREAKOUT":
        return "AVOID", None, None, invalidation, ["FAILED_BREAKOUT"]
    if stage == "EXTENDED_MOVE" and extension == "HIGH":
        return "AVOID", None, None, invalidation, ["EXTENDED_MOVE"]
    if consolidation.get("range_validity") is False and range_state in {"RANGE_INVALIDATED", "BREAKDOWN_CONFIRMED"}:
        return "AVOID", None, None, invalidation, ["INVALIDATED_SETUP"]
    if stage == "BREAKOUT_CONFIRMED":
        return "BUY_NOW", breakout, "CONFIRMED_BREAKOUT", invalidation, ["BREAKOUT_CONFIRMED"]
    if stage in {"BREAKOUT_DEVELOPING", "EARLY_MOMENTUM"}:
        return "BUY_ON_BREAKOUT", breakout or activation, "BREAKOUT_CONFIRMATION", invalidation, [stage]
    if consolidation.get("range_validity") is True and position is not None and position <= 35:
        return "BUY_ON_PULLBACK", consolidation.get("range_low"), "RANGE_SUPPORT", invalidation, ["LOWER_RANGE_ENTRY_ZONE"]
    return "WATCH", activation or breakout or consolidation.get("range_low"), "CONDITIONAL_WATCH", invalidation, ["SETUP_NOT_YET_ACTIONABLE"]


def _warnings(candidate: dict, avoid_reasons: list[str]) -> list[str]:
    decision = candidate.get("decision_metrics", {})
    rotation = candidate.get("rotation", {})
    validation = candidate.get("validation", {})
    confidence = _number(decision.get("evidence_confidence_score"))
    warnings: list[str] = []
    if _upper(rotation.get("edge_validation_status")) == "UNVALIDATED":
        warnings.append("UNVALIDATED_EDGE")
    if confidence is None or confidence < 50 or _upper(decision.get("confidence_band")) == "LOW":
        warnings.append("LOW_CONFIDENCE")
    sample = _number(validation.get("historical_sample_size"))
    if _upper(validation.get("validation_grade")) in {"INSUFFICIENT", "INSUFFICIENT_SAMPLE"} or sample is None or sample < 10:
        warnings.append("INSUFFICIENT_SAMPLE")
    edge = _number(rotation.get("net_edge_after_costs"))
    if edge is not None and edge < 0:
        warnings.append("NEGATIVE_NET_EDGE_AFTER_COSTS")
    warnings.extend(avoid_reasons)
    return _unique(warnings)


def _range_quality_points(candidate: dict) -> float:
    consolidation = candidate.get("consolidation", {})
    valid = consolidation.get("range_validity")
    state = _upper(consolidation.get("range_state"))
    position = _number(consolidation.get("position_percent"))
    points = 5.0 if valid is True else -10.0 if valid is False else 0.0
    if state in {"RANGE_INVALIDATED", "BREAKDOWN_CONFIRMED"}:
        points -= 6.0
    if position is not None:
        points += 5.0 if 0 <= position <= 35 else 3.0 if position <= 70 else 0.0 if position <= 110 else -4.0
    quality = _number(consolidation.get("range_quality"))
    if quality is not None:
        points += _clamp((quality - 50.0) * 0.08, -4.0, 4.0)
    return _clamp(points, -16.0, 12.0)


def _evidence_points(candidate: dict, warnings: list[str]) -> tuple[float, float]:
    decision = candidate.get("decision_metrics", {})
    validation = candidate.get("validation", {})
    confidence = _number(decision.get("evidence_confidence_score"))
    confidence_points = -3.0 if confidence is None else _clamp((confidence - 50.0) * 0.16, -8.0, 8.0)
    sample = _number(validation.get("historical_sample_size"))
    insufficient = "INSUFFICIENT_SAMPLE" in warnings
    unvalidated = "UNVALIDATED_EDGE" in warnings
    if insufficient and unvalidated:
        validation_points = -8.0
    elif insufficient:
        validation_points = -6.0
    elif unvalidated:
        validation_points = -5.0
    elif sample is not None:
        validation_points = 2.0 if sample < 30 else 5.0 if sample < 100 else 8.0
    else:
        validation_points = 0.0
    return confidence_points, validation_points


def _setup_quality(candidate: dict, warnings: list[str]) -> tuple[float, dict]:
    momentum = candidate.get("momentum", {})
    relative = candidate.get("relative_strength", {})
    rotation = candidate.get("rotation", {})
    evidence = candidate.get("evidence", {})
    stage = _upper(momentum.get("stage")) or "UNKNOWN"
    extension = _upper(momentum.get("extension_risk"))
    momentum_points = {
        "BREAKOUT_CONFIRMED": 12.0, "BREAKOUT_DEVELOPING": 9.0, "EARLY_MOMENTUM": 6.0,
        "NO_MOMENTUM": 2.0, "UNKNOWN": 0.0, "EXTENDED_MOVE": -4.0, "FAILED_BREAKOUT": -6.0,
    }.get(stage, 0.0)
    percentile = _number(relative.get("percentile_rank"))
    relative_points = 0.0 if percentile is None else _clamp((percentile - 50.0) * 0.12, -6.0, 6.0)
    range_points = _range_quality_points(candidate)
    advantage = _number(rotation.get("score_advantage"))
    rotation_points = 0.0 if advantage is None else _clamp(advantage * 0.45, -7.0, 7.0)
    edge = _number(rotation.get("net_edge_after_costs"))
    edge_points = 0.0 if edge is None else _clamp(edge, -7.0, 7.0)
    confidence_points, validation_points = _evidence_points(candidate, warnings)
    supporting = set(evidence.get("supporting_modules") or [])
    opposing = set(evidence.get("opposing_modules") or [])
    flow_points = (3.0 if "capital_flow" in supporting else 0.0) - (4.0 if "capital_flow" in opposing else 0.0)
    extension_points = -22.0 if extension == "HIGH" else -7.0 if extension == "MEDIUM" else 0.0
    failed_points = -20.0 if stage == "FAILED_BREAKOUT" else 0.0
    stale_points = -25.0 if "STALE_DATA" in warnings else 0.0
    components = {
        "base": 50.0, "momentum_quality": momentum_points, "relative_strength": relative_points,
        "consolidation_range": range_points, "rotation_advantage": rotation_points,
        "net_edge_after_costs": edge_points, "evidence_confidence": confidence_points,
        "validation": validation_points, "capital_flow_alignment": flow_points,
        "extension_risk": extension_points, "failed_breakout_risk": failed_points,
        "freshness": stale_points,
    }
    # Preserve relative information inside AVOID instead of flattening weak
    # setups to zero. The small positive floor still means unacceptable.
    return round(_clamp(sum(components.values()), 0.01, 100.0), 2), {k: round(v, 4) for k, v in components.items()}


def _actionability(candidate: dict) -> tuple[float, dict]:
    momentum = candidate.get("momentum", {})
    consolidation = candidate.get("consolidation", {})
    current = candidate.get("current_data", {})
    stage = _upper(momentum.get("stage")) or "UNKNOWN"
    extension = _upper(momentum.get("extension_risk"))
    stage_points = {
        "BREAKOUT_CONFIRMED": 38.0, "BREAKOUT_DEVELOPING": 30.0, "EARLY_MOMENTUM": 24.0,
        "NO_MOMENTUM": -8.0, "UNKNOWN": -10.0, "EXTENDED_MOVE": -22.0, "FAILED_BREAKOUT": -32.0,
    }.get(stage, -5.0)
    distance = _number(momentum.get("distance_to_breakout_pct"))
    distance_points = 0.0 if distance is None else 12.0 if abs(distance) <= 1 else 8.0 if abs(distance) <= 3 else 3.0 if abs(distance) <= 7 else -5.0
    closes = _number(momentum.get("confirmation_closes"))
    confirmation_points = 0.0 if closes is None else 10.0 if closes >= 3 else 6.0 if closes >= 1 else -2.0
    activation_points = 6.0 if momentum.get("activation_condition") or momentum.get("breakout_level") is not None else -3.0
    stop_points = 8.0 if momentum.get("invalidation_reference_level") is not None or consolidation.get("range_low") is not None else -5.0
    freshness = _upper(current.get("freshness"))
    freshness_points = 5.0 if freshness == "FRESH" else 0.0 if not freshness else -30.0
    extension_points = -25.0 if extension == "HIGH" else -7.0 if extension == "MEDIUM" else 0.0
    position = _number(consolidation.get("position_percent"))
    range_position_points = 0.0 if position is None else 10.0 if 0 <= position <= 35 else 5.0 if position <= 70 else 1.0 if position <= 110 else -5.0
    components = {
        "base": 20.0, "momentum_stage": stage_points, "distance_to_breakout": distance_points,
        "confirmation_closes": confirmation_points, "activation_condition": activation_points,
        "invalidation_stop_available": stop_points, "freshness": freshness_points,
        "extension_risk": extension_points, "range_position": range_position_points,
    }
    return round(_clamp(sum(components.values()), 0.0, 100.0), 2), {k: round(v, 4) for k, v in components.items()}


def _signed(value: Any, scale: float, limit: float) -> float:
    number = _number(value)
    return 0.0 if number is None else _clamp(number * scale, -limit, limit)


def _daily_score(candidate: dict, setup: float, actionability: float) -> tuple[float, dict]:
    momentum = candidate.get("momentum", {})
    relative = candidate.get("relative_strength", {})
    stage = _upper(momentum.get("stage"))
    stage_points = {"BREAKOUT_CONFIRMED": 10.0, "BREAKOUT_DEVELOPING": 8.0, "EARLY_MOMENTUM": 6.0,
                    "NO_MOMENTUM": 0.0, "EXTENDED_MOVE": -8.0, "FAILED_BREAKOUT": -10.0}.get(stage, 0.0)
    acceleration = _signed(momentum.get("acceleration"), 1.0, 4.0)
    performance = _signed(momentum.get("return_24h_pct"), 0.35, 2.5) + _signed(momentum.get("return_48h_pct"), 0.2, 2.0)
    volume = _signed(momentum.get("volume_z_score"), 1.2, 3.0)
    expansion = _number(momentum.get("volatility_expansion"))
    expansion_points = 0.0 if expansion is None else _clamp((expansion - 1.0) * 3.0, -2.0, 3.0)
    short_rs = _signed(relative.get("return_vs_btc_24h_pct"), 0.8, 4.0)
    components = {"actionability": actionability * 0.45, "setup_quality": setup * 0.25,
                  "momentum_stage": stage_points, "acceleration": acceleration,
                  "performance_24h_48h": performance, "volume_z_score": volume,
                  "volatility_expansion": expansion_points, "short_term_relative_strength": short_rs}
    return round(_clamp(sum(components.values()), 0.0, 100.0), 2), {k: round(v, 4) for k, v in components.items()}


def _weekly_score(candidate: dict, setup: float, actionability: float) -> tuple[float, dict]:
    relative = candidate.get("relative_strength", {})
    rotation = candidate.get("rotation", {})
    decision = candidate.get("decision_metrics", {})
    long_rs = _signed(relative.get("return_vs_btc_7d_pct"), 0.6, 5.0) + _signed(relative.get("return_vs_btc_14d_pct"), 0.35, 3.0)
    range_context = _clamp(_range_quality_points(candidate) * 0.5, -8.0, 6.0)
    advantage = _number(rotation.get("score_advantage"))
    edge = _number(rotation.get("net_edge_after_costs"))
    rotation_context = (0.0 if advantage is None else _clamp(advantage * 0.25, -4.0, 4.0)) + (0.0 if edge is None else _clamp(edge * 0.4, -3.0, 3.0))
    age_status = _upper(decision.get("opportunity_age_status"))
    age_points = -3.0 if age_status in {"STALE", "EXPIRED", "DETERIORATING"} else 2.0 if age_status in {"NEW", "FRESH", "PERSISTENT"} else 0.0
    components = {"setup_quality": setup * 0.65, "actionability": actionability * 0.10,
                  "relative_strength_7d_14d": long_rs, "consolidation_context": range_context,
                  "rotation_edge_context": rotation_context, "opportunity_age": age_points}
    return round(_clamp(sum(components.values()), 0.0, 100.0), 2), {k: round(v, 4) for k, v in components.items()}


def _why_not_buy_now(action: str, candidate: dict, warnings: list[str], reasons: list[str]) -> list[str]:
    momentum = candidate.get("momentum", {})
    result: list[str] = []
    if action != "BUY_NOW":
        stage = _upper(momentum.get("stage"))
        if stage in {"BREAKOUT_DEVELOPING", "EARLY_MOMENTUM"}:
            result.append("BREAKOUT_NOT_CONFIRMED")
        elif stage in {"NO_MOMENTUM", "UNKNOWN", ""}:
            result.append("NO_ACTIVE_MOMENTUM")
        result.extend(x for x in reasons if x in {"FAILED_BREAKOUT", "EXTENDED_MOVE", "INVALIDATED_SETUP", "STALE_DATA"})
        result.extend(x for x in warnings if x in {"LOW_CONFIDENCE", "UNVALIDATED_EDGE", "NEGATIVE_NET_EDGE_AFTER_COSTS", "INSUFFICIENT_SAMPLE"})
        if momentum.get("invalidation_reference_level") is None and candidate.get("consolidation", {}).get("range_low") is None:
            result.append("NO_INVALIDATION_REFERENCE")
    return _unique(result)


def _recommendation(technical_action: str, candidate: dict, setup: float, actionability: float,
                    warnings: list[str], reasons: list[str], objective: str) -> tuple[str, str, list[str], list[str], list[str]]:
    momentum = candidate.get("momentum", {})
    rotation = candidate.get("rotation", {})
    btc_objective = _upper(objective) in {"BTC", "BTC_ACCUMULATION"}
    edge = _number(rotation.get("net_edge_after_costs"))
    advantage = _number(rotation.get("score_advantage"))
    technical_buy = technical_action in {"BUY_NOW", "BUY_ON_BREAKOUT", "BUY_ON_PULLBACK"}
    trigger = momentum.get("activation_condition") or momentum.get("breakout_level")
    why: list[str] = []
    why_not: list[str] = []
    activation: list[str] = []

    if technical_action == "AVOID":
        recommendation = "AVOID"
        why.extend(reasons)
        why_not.extend(reasons)
        return recommendation, "VERY_LOW", _unique(why), _unique(why_not), []
    elif technical_buy:
        why.append("TECHNICAL_TRIGGER_PRESENT")
        if setup >= MIN_ACTIONABLE_SETUP:
            why.append("SETUP_QUALITY_SUFFICIENT")
        else:
            why_not.append("SETUP_QUALITY_BELOW_ACTIONABLE")
        if actionability >= MIN_ACTIONABLE_ACTIONABILITY:
            why.append("ACTIONABILITY_SUFFICIENT")
        else:
            why_not.append("ACTIONABILITY_BELOW_ACTIONABLE")
        if btc_objective:
            if edge is None:
                why_not.append("BTC_RELATIVE_EDGE_UNAVAILABLE")
            elif edge < 0:
                why_not.append("NEGATIVE_NET_EDGE_AFTER_COSTS")
                activation.append("POSITIVE_BTC_RELATIVE_EDGE_REQUIRED")
            else:
                why.append("NON_NEGATIVE_BTC_RELATIVE_EDGE")
            if advantage is None:
                why_not.append("ROTATION_ADVANTAGE_UNAVAILABLE")
            elif advantage < 0:
                why_not.append("NEGATIVE_ROTATION_ADVANTAGE")
            else:
                why.append("NON_NEGATIVE_ROTATION_ADVANTAGE")
        economics_pass = not btc_objective or (edge is not None and edge >= 0 and advantage is not None and advantage >= 0)
        recommendation = "ACTIONABLE" if setup >= MIN_ACTIONABLE_SETUP and actionability >= MIN_ACTIONABLE_ACTIONABILITY and economics_pass else "SPECULATIVE_REVIEW"
    elif setup >= HIGH_QUALITY_SETUP and actionability < MIN_ACTIONABLE_ACTIONABILITY and trigger:
        recommendation = "HIGH_PRIORITY_WATCH"
        why.extend(["HIGH_SETUP_QUALITY", "CONCRETE_ACTIVATION_CONDITION"])
        why_not.append("ACTIONABILITY_BELOW_ACTIONABLE")
    else:
        recommendation = "WATCH"
        why.append("RESEARCH_INTEREST_ONLY")
        if setup < MIN_ACTIONABLE_SETUP:
            why_not.append("SETUP_QUALITY_BELOW_ACTIONABLE")
        if actionability < MIN_ACTIONABLE_ACTIONABILITY:
            why_not.append("ACTIONABILITY_BELOW_ACTIONABLE")

    stage = _upper(momentum.get("stage"))
    if technical_action == "BUY_ON_BREAKOUT":
        activation.append("BREAKOUT_CONFIRMATION_REQUIRED")
    if stage in {"NO_MOMENTUM", "UNKNOWN", ""}:
        activation.append("MOMENTUM_ACTIVATION_REQUIRED")
    if isinstance(momentum.get("activation_condition"), str):
        activation.insert(0, momentum["activation_condition"])
    elif technical_action in {"BUY_ON_BREAKOUT", "WATCH"} and momentum.get("breakout_level") is not None:
        activation.insert(0, "CLOSE_ABOVE_BREAKOUT_LEVEL")
    if "LOW_CONFIDENCE" in warnings:
        why_not.append("LOW_CONFIDENCE")
        activation.append("CONFIDENCE_IMPROVEMENT")
    if "UNVALIDATED_EDGE" in warnings:
        why_not.append("UNVALIDATED_EDGE")
    if "INSUFFICIENT_SAMPLE" in warnings:
        why_not.append("INSUFFICIENT_SAMPLE")
        activation.append("VALIDATION_REQUIRED")

    evidence_gap = "LOW_CONFIDENCE" in warnings or "UNVALIDATED_EDGE" in warnings or "INSUFFICIENT_SAMPLE" in warnings
    if recommendation == "AVOID":
        conviction = "VERY_LOW"
    elif edge is not None and edge < 0 and "LOW_CONFIDENCE" in warnings and evidence_gap:
        conviction = "VERY_LOW"
    elif evidence_gap:
        conviction = "LOW"
    elif setup >= 70 and actionability >= 75:
        conviction = "HIGH"
    elif setup >= MIN_ACTIONABLE_SETUP or actionability >= MIN_ACTIONABLE_ACTIONABILITY:
        conviction = "MEDIUM"
    else:
        conviction = "LOW"
    return recommendation, conviction, _unique(why), _unique(why_not), _unique(activation)


def _strategy_support(planned_family: str, research_memory: dict | None) -> dict:
    memory = research_memory or {}
    strategies = memory.get("strategy_memory") or memory.get("strategy_context") or []
    preferred = "MOMENTUM_STRUCTURE_EXIT" if planned_family == "MOMENTUM_BREAKOUT" else "RANGE_HIGH"
    matches = [row for row in strategies if _upper(row.get("strategy_family") or row.get("strategy")) == planned_family]
    supported = [row for row in matches if (_number(row.get("unique_episode_count") or row.get("unique_setup_episode_count")) or 0) >= 20]
    selected = next((row for row in supported if _upper(row.get("strategy_variant") or row.get("variant")) == preferred), None)
    if selected is None and supported:
        selected = max(supported, key=lambda row: _number(row.get("unique_episode_count") or row.get("unique_setup_episode_count")) or 0)
    selected = selected or {}
    oos_rows = memory.get("oos_summary") or []
    variant = selected.get("strategy_variant") or selected.get("variant") or preferred
    oos = next((row for row in oos_rows if _upper(row.get("strategy")) == _upper(variant)), {})
    return {"family": planned_family, "variant": variant, "statistics": selected, "oos": oos, "available": bool(selected)}


def _planned_trade_family(technical_action: str, recommendation: str, candidate: dict,
                          preferred_entry: float | None) -> str:
    momentum = candidate.get("momentum", {})
    consolidation = candidate.get("consolidation", {})
    range_high = _number(consolidation.get("range_high"))
    stage = _upper(momentum.get("stage"))
    if technical_action == "BUY_ON_BREAKOUT" or (preferred_entry is not None and range_high is not None and preferred_entry > range_high):
        return "MOMENTUM_BREAKOUT"
    if technical_action == "BUY_ON_PULLBACK":
        return "CONSOLIDATION_RANGE"
    if recommendation == "HIGH_PRIORITY_WATCH" and momentum.get("breakout_level") is not None:
        return "MOMENTUM_BREAKOUT"
    if technical_action == "BUY_NOW" and stage in {"BREAKOUT_CONFIRMED", "BREAKOUT_DEVELOPING", "EARLY_MOMENTUM"}:
        return "MOMENTUM_BREAKOUT"
    if consolidation.get("range_validity") is True:
        return "CONSOLIDATION_RANGE"
    return "MOMENTUM_BREAKOUT"


def _trade_plan(candidate: dict, record: dict, research_memory: dict | None) -> dict | None:
    recommendation = record["recommendation"]
    if recommendation not in {"ACTIONABLE", "SPECULATIVE_REVIEW", "HIGH_PRIORITY_WATCH"}:
        return None
    momentum = candidate.get("momentum", {})
    consolidation = candidate.get("consolidation", {})
    technical_action = record["technical_action"]
    breakout = _number(momentum.get("breakout_level"))
    current = _number(candidate.get("current_data", {}).get("current_price"))
    range_low = _number(consolidation.get("range_low"))

    if technical_action == "BUY_ON_BREAKOUT" or recommendation == "HIGH_PRIORITY_WATCH":
        entry_low = entry_high = preferred_entry = breakout
        entry_method = "BREAKOUT_LEVEL_WITH_CONFIRMATION"
    elif technical_action == "BUY_ON_PULLBACK":
        entry_low = entry_high = preferred_entry = range_low
        entry_method = "RANGE_SUPPORT_PULLBACK"
    elif technical_action == "BUY_NOW":
        preferred_entry = current
        entry_low = breakout if breakout is not None and current is not None and breakout <= current else current
        entry_high = current
        entry_method = "CONFIRMED_BREAKOUT"
    else:
        entry_low = entry_high = preferred_entry = breakout
        entry_method = "WAIT_FOR_MOMENTUM_ACTIVATION"

    stop = _number(momentum.get("invalidation_reference_level"))
    stop_source = "momentum.invalidation_reference_level" if stop is not None else None
    if stop is None and consolidation.get("range_validity") is True and range_low is not None:
        stop, stop_source = range_low, "consolidation.range_low"
    stop_distance = None
    if preferred_entry is not None and stop is not None and preferred_entry > 0 and stop < preferred_entry:
        stop_distance = round((preferred_entry - stop) / preferred_entry * 100.0, 4)

    targets: list[tuple[float, str]] = []
    if consolidation.get("range_validity") is True and preferred_entry is not None:
        for field in ("midpoint", "range_high"):
            level = _number(consolidation.get(field))
            if level is not None and level > preferred_entry and all(level != existing[0] for existing in targets):
                targets.append((level, f"consolidation.{field}"))
    targets.sort(key=lambda item: item[0])
    target_1, source_1 = targets[0] if targets else (None, None)
    target_2, source_2 = targets[1] if len(targets) > 1 else (None, None)

    def rr(target: float | None) -> float | None:
        if target is None or preferred_entry is None or stop is None or stop >= preferred_entry or target <= preferred_entry:
            return None
        return round((target - preferred_entry) / (preferred_entry - stop), 4)

    planned_family = _planned_trade_family(technical_action, recommendation, candidate, preferred_entry)
    support = _strategy_support(planned_family, research_memory)
    stats, oos = support["statistics"], support["oos"]
    sample = _number(stats.get("unique_episode_count") or stats.get("unique_setup_episode_count"))
    holding = _number(stats.get("median_holding_hours"))
    exit_family = support["family"] if support["available"] else None
    exit_method = None if not support["available"] else "RANGE_STRUCTURE_EXIT" if exit_family == "CONSOLIDATION_RANGE" else support["variant"]
    validation = candidate.get("validation", {})
    current_sample = _number(validation.get("historical_sample_size"))
    current_validated = current_sample is not None and current_sample >= 20 and _upper(validation.get("validation_grade")) not in {"INSUFFICIENT", "INSUFFICIENT_SAMPLE"}
    exit_support_level = "CURRENT_SETUP_VALIDATED" if support["available"] and current_validated else "FAMILY_LEVEL_ONLY" if support["available"] else "NO_COMPATIBLE_SUPPORT"
    stop_width_band = None if stop_distance is None else "NORMAL" if stop_distance <= 5 else "WIDE" if stop_distance <= 8 else "VERY_WIDE"
    warnings: list[str] = []
    if target_1 is None and target_2 is None:
        warnings.extend(["TARGET_NOT_VALIDATED", "RISK_REWARD_NOT_ESTIMABLE"])
        if stop_distance is not None and stop_distance > 8:
            warnings.append("WIDE_STOP_WITHOUT_VALIDATED_TARGET")
    if stop is None:
        warnings.append("STOP_UNAVAILABLE")
    if preferred_entry is None:
        warnings.append("ENTRY_LEVEL_UNAVAILABLE")
    if recommendation == "SPECULATIVE_REVIEW":
        warnings.append("SPECULATIVE_REVIEW_ONLY")
    if not support["available"]:
        warnings.append("MATCHED_EXIT_STRATEGY_NOT_AVAILABLE")
        sample = holding = None
    if support["available"] and _upper(oos.get("oos_status")) == "OOS_POSITIVE_UNVALIDATED":
        warnings.extend(["OOS_POSITIVE_UNVALIDATED", "OOS_NOT_FOR_OPTIMIZATION"])
    if "INSUFFICIENT_SAMPLE" in record.get("warnings", []):
        warnings.append("CURRENT_SETUP_INSUFFICIENT_SAMPLE")
    if target_1 is None and target_2 is None:
        target_confidence = "VERY_LOW" if recommendation == "SPECULATIVE_REVIEW" else "LOW"
    elif sample is not None and sample >= 50:
        target_confidence = "LOW" if "INSUFFICIENT_SAMPLE" in record.get("warnings", []) else "MEDIUM"
    else:
        target_confidence = "VERY_LOW"
    status = {"ACTIONABLE": "READY_FOR_MANUAL_REVIEW", "SPECULATIVE_REVIEW": "SPECULATIVE_REVIEW_ONLY",
              "HIGH_PRIORITY_WATCH": "WAITING_FOR_TRIGGER"}[recommendation]
    return {
        "status": status, "entry_zone_low": entry_low, "entry_zone_high": entry_high,
        "preferred_entry": preferred_entry, "entry_method": entry_method,
        "stop_loss": stop, "stop_source": stop_source, "stop_distance_pct": stop_distance,
        "target_1": target_1, "target_2": target_2,
        "target_1_source": source_1, "target_2_source": source_2,
        "risk_reward_tp1": rr(target_1), "risk_reward_tp2": rr(target_2),
        "expected_holding_hours": holding, "exit_method": exit_method,
        "planned_trade_family": planned_family, "exit_family": exit_family,
        "exit_support_level": exit_support_level, "stop_width_band": stop_width_band,
        "target_confidence": target_confidence,
        "supporting_sample_size": None if sample is None else int(sample),
        "warnings": _unique(warnings),
    }


def _record(candidate: dict, objective: str = "BTC_ACCUMULATION", research_memory: dict | None = None) -> dict:
    decision = candidate.get("decision_metrics", {})
    momentum = candidate.get("momentum", {})
    consolidation = candidate.get("consolidation", {})
    rotation = candidate.get("rotation", {})
    relative = candidate.get("relative_strength", {})
    validation = candidate.get("validation", {})
    evidence = candidate.get("evidence", {})
    action, trigger, entry_type, invalidation, reasons = _classify(candidate)
    warnings = _warnings(candidate, reasons if action == "AVOID" else [])
    setup, setup_breakdown = _setup_quality(candidate, warnings)
    actionability, action_breakdown = _actionability(candidate)
    daily, daily_breakdown = _daily_score(candidate, setup, actionability)
    weekly, weekly_breakdown = _weekly_score(candidate, setup, actionability)
    recommendation, conviction, why_recommended, why_not_actionable, activation_requirements = _recommendation(
        action, candidate, setup, actionability, warnings, reasons, objective
    )

    stop_reference = momentum.get("invalidation_reference_level")
    stop_source = "momentum.invalidation_reference_level" if stop_reference is not None else None
    if stop_reference is None and consolidation.get("range_validity") is True:
        stop_reference = consolidation.get("range_low")
        stop_source = "consolidation.range_low" if stop_reference is not None else None
    confidence = _number(decision.get("evidence_confidence_score"))
    record = {
        "rank": None, "asset": candidate.get("asset"), "action": action,
        "technical_action": action, "recommendation": recommendation, "conviction": conviction,
        "setup_quality_score": setup, "actionability_score": actionability,
        "daily_score": daily, "weekly_score": weekly,
        "tactical_score": daily if action != "AVOID" else setup,
        "analysis_price": candidate.get("current_data", {}).get("analysis_price", candidate.get("current_data", {}).get("current_price")),
        "analysis_price_timestamp": candidate.get("current_data", {}).get("analysis_price_timestamp", candidate.get("current_data", {}).get("source_timestamp")),
        "current_price": candidate.get("current_data", {}).get("current_price"),
        "current_price_semantics": "DEPRECATED_ALIAS_OF_ANALYSIS_PRICE",
        "entry_trigger": trigger, "entry_type": entry_type,
        "stop_reference": stop_reference, "stop_source": stop_source,
        "setup": decision.get("current_primary_hypothesis"), "horizon": None,
        "relative_strength": {k: relative.get(k) for k in ("relative_trend", "percentile_rank", "return_vs_btc_24h_pct", "return_vs_btc_7d_pct", "return_vs_btc_14d_pct")},
        "rotation_score_advantage": rotation.get("score_advantage"),
        "net_edge_after_costs": rotation.get("net_edge_after_costs"),
        "evidence_confidence": {"score": confidence, "band": decision.get("confidence_band")},
        "validation": {k: validation.get(k) for k in ("validation_grade", "historical_sample_size", "historical_win_rate", "expected_value", "profit_factor", "maximum_drawdown")},
        "invalidation_condition": invalidation,
        "reasons": _unique(reasons + list(evidence.get("supporting_modules") or [])),
        "warnings": warnings, "why_not_buy_now": _why_not_buy_now(action, candidate, warnings, reasons),
        "why_recommended": why_recommended, "why_not_actionable": why_not_actionable,
        "activation_requirements": activation_requirements,
        "score_breakdown": {"setup_quality": setup_breakdown, "actionability": action_breakdown,
                            "daily": daily_breakdown, "weekly": weekly_breakdown},
    }
    record["trade_plan"] = _trade_plan(candidate, record, research_memory)
    return record


def build(candidates: list[dict], objective: str = "BTC_ACCUMULATION", research_memory: dict | None = None) -> dict[str, list[dict]]:
    """Build independent, portfolio-free daily, weekly, and avoid rankings."""
    records = [_record(candidate, objective, research_memory) for candidate in candidates]
    active = [row for row in records if row["action"] != "AVOID"]
    avoid = [row for row in records if row["action"] == "AVOID"]
    daily = sorted(active, key=lambda row: (-row["daily_score"], -row["actionability_score"], str(row.get("asset"))))
    weekly = sorted(active, key=lambda row: (-row["weekly_score"], -row["setup_quality_score"], str(row.get("asset"))))
    avoid.sort(key=lambda row: (-row["setup_quality_score"], str(row.get("asset"))))
    result = {"daily": [dict(row, horizon="DAILY", tactical_score=row["daily_score"]) for row in daily],
              "weekly": [dict(row, horizon="WEEKLY", tactical_score=row["weekly_score"]) for row in weekly],
              "avoid": [dict(row, horizon="AVOID", tactical_score=row["setup_quality_score"]) for row in avoid]}
    for rows in result.values():
        for rank, row in enumerate(rows, 1):
            row["rank"] = rank
    return result
