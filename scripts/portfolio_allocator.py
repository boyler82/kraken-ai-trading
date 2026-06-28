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
)

from lib.portfolio_engine import (
    build_portfolio_allocation,
    get_allocation_columns,
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
    """Compute portfolio allocation fields for the input ranking."""

    return build_portfolio_allocation(df)

def write_report(df: pd.DataFrame) -> None:
    """Write CSV and markdown allocation reports."""

    columns = get_allocation_columns()

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
