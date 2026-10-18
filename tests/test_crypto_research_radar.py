from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import crypto_research_radar as radar  # noqa: E402


class CryptoResearchRadarTest(unittest.TestCase):
    def test_historical_comparison_and_rank_order(self) -> None:
        previous = pd.DataFrame(
            [
                {"asset": "BTC", "research_score": 50, "readiness_pct": 10, "current_setup_status": "NO_SETUP"},
                {"asset": "ETH", "research_score": 70, "readiness_pct": 40, "current_setup_status": "DEVELOPING"},
                {"asset": "SOL", "research_score": 60, "readiness_pct": 0, "current_setup_status": "NO_SETUP"},
            ]
        )
        today = pd.DataFrame(
            [
                {"asset": "BTC", "research_score": 65, "readiness_pct": 30, "current_setup_status": "DEVELOPING"},
                {"asset": "ETH", "research_score": 55, "readiness_pct": 0, "current_setup_status": "NO_SETUP"},
                {"asset": "SOL", "research_score": 63, "readiness_pct": 0, "current_setup_status": "NO_SETUP"},
            ]
        )
        result = radar.compare_snapshots(today, previous)
        self.assertEqual(result["asset"].tolist(), ["BTC", "SOL", "ETH"])
        btc = result[result["asset"] == "BTC"].iloc[0]
        eth = result[result["asset"] == "ETH"].iloc[0]
        self.assertEqual(btc["research_score_delta"], 15)
        self.assertEqual(btc["readiness_delta"], 20)
        self.assertTrue(bool(btc["newly_emerging"]))
        self.assertTrue(bool(eth["disappearing"]))

    def test_missing_history_is_graceful(self) -> None:
        today = pd.DataFrame(
            [
                {"asset": "BTC", "research_score": 65, "readiness_pct": 0, "current_setup_status": "NO_SETUP"}
            ]
        )
        result = radar.compare_snapshots(today, pd.DataFrame())
        self.assertEqual(result["asset"].tolist(), ["BTC"])
        self.assertTrue(pd.isna(result.iloc[0]["research_score_delta"]))
        self.assertFalse(bool(result.iloc[0]["newly_emerging"]))

    def test_seven_day_history_uses_calendar_window_and_missing_days(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for date_text, score in (
                ("2026-07-18", 40),
                ("2026-07-20", 50),
                ("2026-07-26", 70),
            ):
                pd.DataFrame(
                    [{"asset": "BTC", "research_score": score}]
                ).to_csv(directory / f"{date_text}_research_score.csv", index=False)
            history = radar.seven_day_history(
                directory, pd.Timestamp("2026-07-26")
            )
            self.assertEqual(
                history["snapshot_date"].unique().tolist(),
                ["2026-07-20", "2026-07-26"],
            )
            self.assertEqual(history["research_score"].tolist(), [50, 70])

    def test_rotation_observations_rank_leader_and_laggard(self) -> None:
        comparison = pd.DataFrame(
            [
                {"asset": "BTC", "research_score_delta": 8, "newly_emerging": False, "disappearing": False},
                {"asset": "ETH", "research_score_delta": -5, "newly_emerging": False, "disappearing": True},
            ]
        )
        observations = radar.market_rotation_observations(comparison)
        self.assertIn("Rotation leader: BTC (+8.00 Research Score).", observations)
        self.assertIn("Rotation laggard: ETH (-5.00 Research Score).", observations)

    def test_rotation_does_not_call_unchanged_asset_a_leader(self) -> None:
        comparison = pd.DataFrame(
            [
                {"asset": "BTC", "research_score_delta": 0, "newly_emerging": False, "disappearing": False},
                {"asset": "ETH", "research_score_delta": -2, "newly_emerging": False, "disappearing": False},
            ]
        )
        observations = radar.market_rotation_observations(comparison)
        self.assertIn(
            "No asset recorded positive Research Score rotation.", observations
        )


if __name__ == "__main__":
    unittest.main()
