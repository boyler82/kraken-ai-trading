from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

STEPS = [
    "scripts/rsi2_edge_database.py",
    "scripts/build_edge_summary.py",
    "scripts/cross_asset_rsi2_research.py",
    "scripts/cross_asset_rsi2_regime_analysis.py",
    "scripts/monte_carlo_rsi2.py",
    "scripts/opportunity_ranking.py",
    "scripts/portfolio_allocator.py",
    "scripts/daily_research_summary.py",
]


def main() -> None:
    """Run the full research pipeline sequentially."""

    started = time.perf_counter()

    for idx, step in enumerate(STEPS, start=1):
        print(f"[{idx}/{len(STEPS)}] Running {step}")
        subprocess.run([sys.executable, str(ROOT / step)], check=True)

    elapsed = time.perf_counter() - started

    print("\nSUCCESS")
    print(f"Completed {len(STEPS)} steps in {elapsed:.2f}s")
    print("Pipeline: research modules combined successfully")


if __name__ == "__main__":
    main()
