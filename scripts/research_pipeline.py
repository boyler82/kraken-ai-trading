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
    "scripts/universal_market_scanner.py",
    "scripts/monte_carlo_rsi2.py",
    "scripts/opportunity_ranking.py",
    "scripts/opportunity_tracker.py",
    "scripts/research_score_engine.py",
    "scripts/trade_candidate_dashboard.py",
    "scripts/research_explainability_engine.py",
    "scripts/research_evolution_engine.py",
    "scripts/research_timeline_engine.py",
    "scripts/research_regime_engine.py",
    "scripts/portfolio_allocator.py",
    "scripts/position_manager.py",
    "scripts/realized_trade_manager.py",
    "scripts/exit_planner.py",
    "scripts/signal_outcome_engine.py",
    "scripts/signal_exit_calendar.py",
    "scripts/daily_research_summary.py",
    "scripts/daily_decision_dashboard.py",
    "scripts/research_consensus_engine.py",
    "scripts/research_feedback_engine.py",
    "scripts/research_validation_engine.py",
    "scripts/research_performance_dashboard.py",
    "scripts/project_health_check.py",
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
