from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import morning_brief as brief  # noqa: E402


class MorningBriefDashboardRegressionTest(unittest.TestCase):
    def test_unified_dashboard_contains_every_research_section(self) -> None:
        regime = pd.DataFrame(
            [
                {"metric": "crypto_regime", "value": "BEAR"},
                {"metric": "equity_regime", "value": "MIXED"},
                {"metric": "volatility_regime", "value": "NORMAL"},
                {"metric": "opportunity_regime", "value": "EMPTY"},
                {"metric": "environment_score", "value": 30},
                {"metric": "environment_status", "value": "DEFENSIVE"},
            ]
        )
        ranking = pd.DataFrame(
            [
                {
                    "asset": "BTC",
                    "bucket": "HISTORICAL_WATCHLIST",
                    "opportunity_score": 35,
                    "confidence_score": 90,
                    "recommendation": "HISTORICALLY_STRONG_NO_SIGNAL",
                }
            ]
        )
        candidates = pd.DataFrame(
            [{"asset": "BTC", "current_setup_status": "HISTORICAL_ONLY"}]
        )
        regime_before = regime.copy(deep=True)
        ranking_before = ranking.copy(deep=True)
        candidates_before = candidates.copy(deep=True)
        score_md = """## Research Score Breakdown

- #1 BTC | total 74.25 = EV 17.5 + PF 20
"""
        radar_md = """## Fastest Improving Assets

No improving assets.

## Fastest Deteriorating Assets

- ETH | change -2

## Newly Emerging Candidates

None

## Disappearing Candidates

- LINK | change 0

## Research Score Trend — Last 7 Days

- BTC | day1=70 → day7=74

## Readiness Trend — Last 7 Days

- BTC | day1=0 → day7=0

## Market Rotation Observations

- Score breadth: 0 improving, 1 deteriorating.
"""
        output = brief.render_research_dashboard(
            regime, ranking, candidates, score_md, radar_md
        )
        for heading in (
            "UNIFIED RESEARCH DASHBOARD",
            "MARKET REGIME ENGINE",
            "OPPORTUNITY RANKING — RESEARCH OUTPUT, NOT CURRENT SIGNALS",
            "RESEARCH SCORE BREAKDOWN",
            "CRYPTO RESEARCH RADAR — FASTEST IMPROVING ASSETS",
            "CRYPTO RESEARCH RADAR — FASTEST DETERIORATING ASSETS",
            "CRYPTO RESEARCH RADAR — NEWLY EMERGING CANDIDATES",
            "CRYPTO RESEARCH RADAR — DISAPPEARING CANDIDATES",
            "CRYPTO RESEARCH RADAR — RESEARCH SCORE TREND — LAST 7 DAYS",
            "CRYPTO RESEARCH RADAR — READINESS TREND — LAST 7 DAYS",
            "CRYPTO RESEARCH RADAR — MARKET ROTATION OBSERVATIONS",
        ):
            self.assertIn(heading, output)
        self.assertIn("current setup HISTORICAL_ONLY", output)
        self.assertIn("total 74.25", output)
        pd.testing.assert_frame_equal(regime, regime_before)
        pd.testing.assert_frame_equal(ranking, ranking_before)
        pd.testing.assert_frame_equal(candidates, candidates_before)

    def test_decision_precedence_is_unchanged(self) -> None:
        self.assertEqual(
            brief._decision_from_current_research(["BTC"], ["ETH"], ["SOL"])[0],
            "BUY_REVIEW",
        )
        self.assertEqual(
            brief._decision_from_current_research([], ["ETH"], ["SOL"])[0],
            "WAIT_AND_WATCH",
        )
        self.assertEqual(
            brief._decision_from_current_research([], [], ["SOL"])[0],
            "WAIT_AND_WATCH",
        )
        self.assertEqual(
            brief._decision_from_current_research([], [], []),
            ("WAIT", "No current setup or watchlist conditions."),
        )

    def test_missing_additive_reports_do_not_break_dashboard(self) -> None:
        output = brief.render_research_dashboard(
            pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "", ""
        )
        self.assertIn("Market regime report unavailable.", output)
        self.assertIn("Research Score breakdown unavailable.", output)
        self.assertIn("Crypto Research Radar section unavailable.", output)


if __name__ == "__main__":
    unittest.main()
