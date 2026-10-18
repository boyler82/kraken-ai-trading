from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import research_regime_engine as regime  # noqa: E402
import research_score_engine as scores  # noqa: E402


class MarketRegimeReportingTest(unittest.TestCase):
    def test_crypto_regime_does_not_require_asset_class_column(self) -> None:
        crypto = pd.DataFrame(
            [{"market_bias": "BEAR"}, {"market_bias": "BEAR_HIGH_VOL"}, {"market_bias": "BULL"}]
        )
        self.assertEqual(regime._majority_crypto(crypto), "BEAR")

    def test_opportunity_regime_uses_existing_ranking_labels(self) -> None:
        crypto = pd.DataFrame(
            [
                {"asset": "BTC", "bucket": "ACTIVE_OPPORTUNITY"},
                {"asset": "ETH", "bucket": "WATCHLIST"},
                {"asset": "LTC", "bucket": "HISTORICAL_WATCHLIST"},
            ]
        )
        universal = pd.DataFrame(
            [
                {
                    "asset": "SOL",
                    "recommendation": "WATCHLIST",
                    "data_freshness_status": "FRESH",
                },
                {
                    "asset": "XRP",
                    "recommendation": "WATCHLIST",
                    "data_freshness_status": "STALE",
                },
            ]
        )
        self.assertEqual(regime._current_opportunity_count(crypto, universal), 3)
        self.assertEqual(regime._opportunity_regime(crypto, universal), "ACTIVE")

    def test_opportunity_ranking_reuses_source_scores(self) -> None:
        crypto = pd.DataFrame(
            [
                {
                    "asset": "BTC",
                    "opportunity_score": 80,
                    "confidence_score": 70,
                    "recommendation": "DAY1_OBSERVE_ONLY",
                }
            ]
        )
        universal = pd.DataFrame(
            [
                {
                    "asset": "ETH",
                    "opportunity_score": 90,
                    "confidence_score": 60,
                    "recommendation": "WATCHLIST",
                }
            ]
        )
        research = pd.DataFrame(
            [{"asset": "BTC", "research_score": 75}, {"asset": "ETH", "research_score": 65}]
        )
        result = regime._rank_opportunities(crypto, universal, research)
        self.assertEqual(result["asset"].tolist(), ["ETH", "BTC"])
        self.assertEqual(result["opportunity_score"].tolist(), [90, 80])

    def test_candidate_status_prevents_old_signal_from_becoming_current(self) -> None:
        crypto = pd.DataFrame(
            [
                {
                    "asset": "LINK",
                    "bucket": "ACTIVE_OPPORTUNITY",
                    "opportunity_score": 85,
                    "recommendation": "DAY1_OBSERVE_ONLY",
                }
            ]
        )
        candidates = pd.DataFrame(
            [
                {
                    "asset": "LINK",
                    "current_setup_status": "NO_SETUP",
                    "opportunity_score": 5,
                    "recommendation": "NO_ACTION",
                }
            ]
        )
        empty = pd.DataFrame()
        self.assertEqual(
            regime._current_opportunity_count(crypto, empty, candidates), 0
        )
        self.assertTrue(
            regime._rank_opportunities(crypto, empty, empty, candidates).empty
        )


class ResearchScoreBreakdownTest(unittest.TestCase):
    def test_contributions_sum_to_unchanged_research_score(self) -> None:
        opportunity = pd.DataFrame(
            [
                {
                    "asset": "BTC",
                    "expected_value_pct": 2.0,
                    "profit_factor": 2.0,
                    "win_rate_pct": 60,
                    "opportunity_score": 80,
                    "confidence_score": 70,
                    "market_bias": "BULL",
                    "atr_pct": 3,
                    "current_phase": "NO_OVERSOLD",
                    "recommendation": "HISTORICALLY_STRONG_NO_SIGNAL",
                    "bucket": "HISTORICAL_WATCHLIST",
                }
            ]
        )
        universal = pd.DataFrame([{"asset": "BTC"}])
        with patch.object(scores, "load_inputs", return_value=(opportunity, universal)):
            result = scores.build_research_score()

        contribution_columns = [
            column for column in result.columns if column.endswith("_contribution")
        ]
        self.assertAlmostEqual(
            float(result.loc[0, contribution_columns].sum()),
            float(result.loc[0, "research_score"]),
            places=2,
        )
        markdown = scores.render_markdown(result)
        self.assertIn("## Research Score Breakdown", markdown)
        self.assertIn("EV 25.0 + PF 20.0", markdown)


if __name__ == "__main__":
    unittest.main()
