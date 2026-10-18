from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.portfolio_positions import active_positions, open_position_assets, open_position_count, open_position_summary  # noqa: E402


class PortfolioPositionsTest(unittest.TestCase):
    def assert_portfolio(self, rows: list[dict], count: int, assets: list[str], summary: str) -> None:
        frame = pd.DataFrame(rows)
        self.assertEqual(len(active_positions(frame)), count)
        self.assertEqual(open_position_assets(frame), assets)
        self.assertEqual(open_position_count(frame), len(assets))
        self.assertEqual(open_position_summary(frame), summary)

    def test_empty(self) -> None:
        self.assert_portfolio([], 0, [], "No open positions")

    def test_only_closed(self) -> None:
        self.assert_portfolio([{"asset": "BTC", "status": "CLOSED"}], 0, [], "No open positions")

    def test_one_open(self) -> None:
        self.assert_portfolio([{"asset": "BTC", "status": "OPEN"}], 1, ["BTC"], "Open positions (1): BTC")

    def test_mixed_open_closed(self) -> None:
        self.assert_portfolio(
            [{"asset": "ETH", "status": "CLOSED"}, {"asset": "BTC", "status": "open"}],
            1, ["BTC"], "Open positions (1): BTC",
        )

    def test_nan_and_blank_statuses(self) -> None:
        self.assert_portfolio(
            [{"asset": "BTC", "status": None}, {"asset": "ETH", "status": ""}, {"asset": "SOL", "status": pd.NA}],
            0, [], "No open positions",
        )


if __name__ == "__main__":
    unittest.main()
