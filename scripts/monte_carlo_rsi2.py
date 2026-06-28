from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.monte_carlo import run_monte_carlo, summarize_monte_carlo

INPUT_FILE = Path("BACKTESTS/rsi2_oversold_episodes.csv")
OUTPUT_FILE = Path("BACKTESTS/rsi2_monte_carlo_summary.csv")

ENTRY_COLUMNS = {
    "DAY1": "ret_day1_hold3_pct",
    "DAY2": "ret_day2_hold3_pct",
    "DAY3": "ret_day3_hold3_pct",
}


def main() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE)
    rows = []

    for asset, group in df.groupby("asset"):
        for entry_day, column in ENTRY_COLUMNS.items():
            returns = pd.to_numeric(group[column], errors="coerce").dropna().tolist()

            results = run_monte_carlo(
                returns,
                simulations=5000,
                starting_capital=10000,
                position_size_pct=5,
                seed=42,
            )
            summary = summarize_monte_carlo(results)

            rows.append(
                {
                    "asset": asset,
                    "entry_day": entry_day,
                    "trades": len(returns),
                    "median_return_pct": summary["median_return_pct"],
                    "p5_return_pct": summary["p5_return_pct"],
                    "p95_return_pct": summary["p95_return_pct"],
                    "probability_loss_pct": summary["probability_loss_pct"],
                    "median_max_drawdown_pct": summary["median_max_drawdown_pct"],
                    "p95_max_drawdown_pct": summary["p95_max_drawdown_pct"],
                    "worst_max_drawdown_pct": summary["worst_max_drawdown_pct"],
                }
            )

    output = pd.DataFrame(rows).sort_values(["asset", "entry_day"]).reset_index(drop=True)

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    output.to_csv(OUTPUT_FILE, index=False)

    print(output.to_string(index=False))
    print(f"\nSaved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
