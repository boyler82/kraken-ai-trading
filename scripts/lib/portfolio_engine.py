from __future__ import annotations

import pandas as pd

from lib.risk_engine import (
    MAX_POSITIONS,
    MAX_SINGLE_POSITION,
    MAX_TOTAL_ALLOCATION,
    calculate_position_score,
    normalize_allocations,
)


def get_allocation_columns() -> list[str]:
    return [
        "asset",
        "recommendation",
        "bucket",
        "opportunity_score",
        "confidence_score",
        "current_phase",
        "rsi2",
        "entry_day",
        "hold_days",
        "expected_value_pct",
        "profit_factor",
        "win_rate_pct",
        "raw_weight_score",
        "proposed_weight_pct",
        "allocation_status",
        "allocation_reason",
    ]


def build_portfolio_allocation(df: pd.DataFrame) -> pd.DataFrame:
    report = df.copy()

    report["raw_weight_score"] = report.apply(calculate_position_score, axis=1)

    report["proposed_weight_pct"] = normalize_allocations(
        report["raw_weight_score"].tolist(),
        max_total_allocation=MAX_TOTAL_ALLOCATION,
        max_single_position=MAX_SINGLE_POSITION,
        max_positions=MAX_POSITIONS,
    )

    report["allocation_status"] = report["proposed_weight_pct"].apply(
        lambda value: "ALLOCATE_REVIEW" if value > 0 else "NO_ALLOCATION"
    )

    report["allocation_reason"] = report["raw_weight_score"].apply(
        lambda value: "eligible for allocation"
        if pd.notna(value) and value > 0
        else "not eligible under risk rules"
    )

    report["raw_weight_score"] = report["raw_weight_score"].apply(
        lambda value: round(float(value), 2) if pd.notna(value) else None
    )

    report["proposed_weight_pct"] = report["proposed_weight_pct"].apply(
        lambda value: round(float(value), 2) if pd.notna(value) else 0.0
    )

    return report


def summarize_allocation(df: pd.DataFrame) -> dict:
    allocated = df[df["proposed_weight_pct"] > 0]

    return {
        "allocated_positions": int(len(allocated)),
        "total_allocation_pct": float(round(allocated["proposed_weight_pct"].sum(), 2)),
        "cash_pct": float(round(100 - allocated["proposed_weight_pct"].sum(), 2)),
        "max_position_pct": float(round(allocated["proposed_weight_pct"].max(), 2))
        if not allocated.empty
        else 0.0,
    }
