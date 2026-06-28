from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.edge_metrics import calculate_quality_score

EDGE_DB = "BACKTESTS/rsi2_edge_database.csv"
OUT = "BACKTESTS/rsi2_best_edge.csv"

MIN_TRADES = 50
MIN_PROFIT_FACTOR = 1.2

df = pd.read_csv(EDGE_DB)

filtered = df[
    (df["trades"] >= MIN_TRADES)
    & (df["profit_factor"] >= MIN_PROFIT_FACTOR)
    & (df["expected_value_pct"] > 0)
].copy()

filtered["quality_score"] = filtered.apply(
    lambda row: calculate_quality_score(
        expected_value_pct=row["expected_value_pct"],
        profit_factor=row["profit_factor"],
        win_rate_pct=row["win_rate_pct"],
        median_return_pct=row["median_return_pct"],
    ),
    axis=1,
)

best = (
    filtered.sort_values(
        ["asset", "quality_score"],
        ascending=[True, False],
    )
    .groupby("asset")
    .head(1)
    .reset_index(drop=True)
)

columns = [
    "asset",
    "entry_day",
    "hold_days",
    "trades",
    "win_rate_pct",
    "avg_return_pct",
    "median_return_pct",
    "avg_win_pct",
    "avg_loss_pct",
    "profit_factor",
    "expected_value_pct",
    "worst_return_pct",
    "best_return_pct",
    "quality_score",
]

best[columns].to_csv(OUT, index=False)

print("\nRSI2 BEST EDGE SUMMARY\n")
print(best[columns].sort_values("quality_score", ascending=False).to_string(index=False))
print(f"\nSaved: {OUT}")
