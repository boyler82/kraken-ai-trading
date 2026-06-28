from pathlib import Path
import glob
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.risk_engine import (
    MAX_POSITIONS,
    MAX_SINGLE_POSITION,
    MAX_TOTAL_ALLOCATION,
    calculate_position_score,
    normalize_allocations,
)

TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")

RANKING = f"DAILY_REPORTS/{TODAY}_crypto_opportunity_ranking.csv"
OUT_CSV = f"DAILY_REPORTS/{TODAY}_portfolio_allocation.csv"
OUT_MD = f"DAILY_REPORTS/{TODAY}_portfolio_allocation.md"


def latest_ranking() -> str:
    """Return the latest crypto opportunity ranking file."""

    if Path(RANKING).exists():
        return RANKING

    files = sorted(glob.glob("DAILY_REPORTS/*_crypto_opportunity_ranking.csv"))
    if not files:
        raise FileNotFoundError("No crypto opportunity ranking files found.")

    return files[-1]


def build_allocation_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Compute risk-engine-driven allocation fields for the input ranking."""

    df = df.copy()
    df["raw_weight_score"] = df.apply(calculate_position_score, axis=1)

    allocations = normalize_allocations(
        df["raw_weight_score"].tolist(),
        max_total_allocation=MAX_TOTAL_ALLOCATION,
        max_single_position=MAX_SINGLE_POSITION,
        max_positions=MAX_POSITIONS,
    )
    df["proposed_weight_pct"] = allocations

    df["allocation_status"] = df["proposed_weight_pct"].apply(
        lambda value: "ALLOCATE_REVIEW" if value > 0 else "NO_ALLOCATION"
    )
    df["allocation_reason"] = df["raw_weight_score"].apply(
        lambda value: "eligible for allocation" if value and value > 0 else "not eligible under risk rules"
    )

    df["raw_weight_score"] = df["raw_weight_score"].apply(
        lambda value: round(float(value), 2) if pd.notna(value) else None
    )
    df["proposed_weight_pct"] = df["proposed_weight_pct"].apply(
        lambda value: round(float(value), 2) if pd.notna(value) else None
    )

    return df


def write_report(df: pd.DataFrame) -> None:
    """Write CSV and markdown allocation reports."""

    columns = [
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

    df[columns].to_csv(OUT_CSV, index=False)

    lines = [
        "# Portfolio Allocation",
        "",
        f"Date: {TODAY}",
        "",
        "Research support only. Not an automatic trade instruction.",
        "",
        f"Max total allocation: {MAX_TOTAL_ALLOCATION}%",
        f"Max single position: {MAX_SINGLE_POSITION}%",
        f"Max positions: {MAX_POSITIONS}",
        "",
    ]

    allocated = df[df["proposed_weight_pct"] > 0]
    if allocated.empty:
        lines.extend(
            [
                "## Allocation Decision",
                "",
                "100% CASH / NO ALLOCATION",
                "",
                "Reason: no setup reached allocation threshold.",
            ]
        )
    else:
        lines.extend(["## Allocation Candidates", ""])
        for _, row in allocated.iterrows():
            lines.append(
                f"- {row['asset']}: {row['proposed_weight_pct']:.2f}% | "
                f"{row['recommendation']} | raw {row['raw_weight_score']:.2f} | "
                f"score {row['opportunity_score']} | confidence {row['confidence_score']} | "
                f"{row['allocation_reason']}"
            )

    Path(OUT_MD).write_text("\n".join(lines))

    print("\nPORTFOLIO ALLOCATION\n")
    print(df[columns].to_string(index=False))
    print(f"\nSaved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")


def main() -> None:
    """Entry point for the portfolio allocator."""

    ranking = pd.read_csv(latest_ranking())
    report = build_allocation_frame(ranking)
    write_report(report)


if __name__ == "__main__":
    main()
