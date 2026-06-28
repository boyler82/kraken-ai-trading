from __future__ import annotations

from typing import Iterable, Mapping, Sequence

import pandas as pd

MAX_TOTAL_ALLOCATION = 30
MAX_SINGLE_POSITION = 10
MAX_POSITIONS = 3
MIN_CONFIDENCE = 70
MIN_OPPORTUNITY = 75


def clean(value: float | int | None) -> float | None:
    """Round numeric values to two decimals and normalize missing values to None."""

    if value is None or pd.isna(value):
        return None
    return float(round(float(value), 2))


def _safe_float(value: object) -> float | None:
    """Convert a value to float if possible."""

    if value is None or pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def calculate_confidence_multiplier(confidence_score: float | None) -> float | None:
    """Return a confidence multiplier for position sizing."""

    confidence = _safe_float(confidence_score)
    if confidence is None or confidence < MIN_CONFIDENCE:
        return None

    return 0.75 + ((confidence - MIN_CONFIDENCE) / 30.0) * 0.75


def calculate_edge_multiplier(
    opportunity_score: float | None,
    profit_factor: float | None,
    expected_value_pct: float | None,
) -> float | None:
    """Return an edge multiplier derived from ranking and edge statistics."""

    opp = _safe_float(opportunity_score)
    pf = _safe_float(profit_factor)
    ev = _safe_float(expected_value_pct)

    if opp is None or opp < MIN_OPPORTUNITY:
        return None

    multiplier = (opp / 100.0) * 0.8 + 0.2

    if pf is not None:
        multiplier *= max(0.5, min(pf / 1.5, 1.5))

    if ev is not None:
        multiplier *= max(0.5, min(1.0 + (ev / 10.0), 1.5))

    return multiplier


def calculate_volatility_multiplier(
    atr_pct: float | None = None,
    volatility: str | None = None,
) -> float | None:
    """Return a volatility multiplier using ATR percent or volatility labels."""

    atr_value = _safe_float(atr_pct)
    if atr_value is not None:
        if atr_value <= 3:
            return 1.1
        if atr_value <= 5:
            return 1.0
        if atr_value <= 7:
            return 0.9
        return 0.8

    if volatility is None or pd.isna(volatility):
        return None

    normalized = str(volatility).upper()
    if normalized == "LOW":
        return 1.1
    if normalized == "MEDIUM":
        return 1.0
    if normalized == "HIGH":
        return 0.85
    return None


def calculate_drawdown_multiplier(
    worst_return_pct: float | None,
    median_return_pct: float | None = None,
) -> float | None:
    """Return a drawdown penalty multiplier from the worst observed return."""

    worst = _safe_float(worst_return_pct)
    median = _safe_float(median_return_pct)

    if worst is None:
        return None

    penalty = 1.0
    if worst <= -20:
        penalty *= 0.7
    elif worst <= -10:
        penalty *= 0.85
    elif worst <= -5:
        penalty *= 0.92

    if median is not None and median < 0:
        penalty *= 0.95

    return penalty


def calculate_position_score(row: Mapping[str, object]) -> float | None:
    """Combine ranking and risk signals into a raw allocation score."""

    rec = row.get("recommendation")
    if rec in {
        "DAY1_OBSERVE_ONLY",
        "WATCH_CLOSELY",
        "HISTORICALLY_STRONG_NO_SIGNAL",
    }:
        return None

    opportunity = _safe_float(row.get("opportunity_score"))
    confidence = _safe_float(row.get("confidence_score"))
    profit_factor = _safe_float(row.get("profit_factor"))
    expected_value = _safe_float(row.get("expected_value_pct"))
    atr_pct = _safe_float(row.get("atr_pct"))
    volatility = row.get("volatility")
    worst_return = _safe_float(row.get("worst_return_pct"))
    median_return = _safe_float(row.get("median_return_pct"))

    if opportunity is None or opportunity < MIN_OPPORTUNITY:
        return None

    if confidence is None or confidence < MIN_CONFIDENCE:
        return None

    if rec == "MANUAL_REVIEW" and confidence < 75:
        return None

    conf_mult = calculate_confidence_multiplier(confidence)
    edge_mult = calculate_edge_multiplier(opportunity, profit_factor, expected_value)
    vol_mult = calculate_volatility_multiplier(atr_pct=atr_pct, volatility=volatility)
    dd_mult = calculate_drawdown_multiplier(worst_return, median_return)

    if any(value is None for value in [conf_mult, edge_mult, vol_mult, dd_mult]):
        return None

    raw_score = opportunity * conf_mult * edge_mult * vol_mult * dd_mult

    if rec == "MANUAL_REVIEW":
        raw_score *= 0.5

    return clean(raw_score)


def normalize_allocations(
    position_scores: Sequence[float | None],
    *,
    max_total_allocation: float = MAX_TOTAL_ALLOCATION,
    max_single_position: float = MAX_SINGLE_POSITION,
    max_positions: int = MAX_POSITIONS,
) -> list[float]:
    """Normalize raw scores to allocation percentages under portfolio limits."""

    valid_scores = [float(score) for score in position_scores if score is not None and score > 0]
    if not valid_scores:
        return [0.0 for _ in position_scores]

    top_scores = sorted(valid_scores, reverse=True)[:max_positions]
    total_score = sum(top_scores)
    if total_score <= 0:
        return [0.0 for _ in position_scores]

    scaled_top = [min(max_single_position, (score / total_score) * max_total_allocation) for score in top_scores]
    total_alloc = sum(scaled_top)

    if total_alloc > max_total_allocation and total_alloc > 0:
        scale = max_total_allocation / total_alloc
        scaled_top = [score * scale for score in scaled_top]

    normalized = [0.0 for _ in position_scores]
    top_index = sorted(
        [(idx, float(score)) for idx, score in enumerate(position_scores) if score is not None and score > 0],
        key=lambda item: item[1],
        reverse=True,
    )[:max_positions]

    for (idx, _), allocation in zip(top_index, scaled_top):
        normalized[idx] = clean(allocation) or 0.0

    return normalized


def calculate_position_size(
    position_score: float | None,
    *,
    max_total_allocation: float = MAX_TOTAL_ALLOCATION,
    max_single_position: float = MAX_SINGLE_POSITION,
    max_positions: int = MAX_POSITIONS,
    active_position_count: int = 0,
) -> float:
    """Convert a position score into a capped position size."""

    score = _safe_float(position_score)
    if score is None or score <= 0:
        return 0.0

    if active_position_count >= max_positions:
        return 0.0

    base = min(max_single_position, (score / 100.0) * max_single_position)
    remaining = max_total_allocation / max(1, max_positions)
    return clean(min(base, remaining)) or 0.0
