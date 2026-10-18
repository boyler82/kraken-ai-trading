from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import daily_consolidation_watchlist_monitor as daily
import morning_brief


class SimpleZoneTests(unittest.TestCase):
    def assert_zone(self, position, color, zone, fresh="FRESH", valid=True, breakdown=False):
        result = daily.simple_position_zone(position, fresh, valid, breakdown)
        self.assertEqual((result["simple_color"], result["simple_zone"]), (color, zone))

    def test_exact_boundaries(self):
        self.assert_zone(0, "GREEN", "LOWER_RANGE")
        self.assert_zone(30, "GREEN", "LOWER_RANGE")
        self.assert_zone(50, "YELLOW", "OBSERVE")
        self.assert_zone(100, "RED", "UPPER_RANGE")

    def test_outside_range(self):
        self.assert_zone(-.01, "RED", "BELOW_RANGE")
        self.assert_zone(100.01, "RED", "ABOVE_RANGE")

    def test_stale_and_invalid_are_forced_red(self):
        self.assert_zone(10, "RED", "LOWER_RANGE", fresh="STALE")
        self.assert_zone(10, "RED", "LOWER_RANGE", valid=False)
        self.assert_zone(10, "RED", "LOWER_RANGE", breakdown=True)
        self.assertEqual(
            daily.simple_position_zone(101, "FRESH", False, False)["simple_zone"],
            "ABOVE_RANGE",
        )

    @staticmethod
    def frame():
        base = {
            "range_low": .01765, "range_high": .019351, "midpoint": .0185005,
            "current_price": .01792, "estimated_net_movement_to_midpoint_pct": 2.64,
            "estimated_net_movement_to_high_pct": 7.34, "average_cycle_hours": 34.6667,
            "freshness_status": "FRESH", "range_still_valid": True,
            "simple_zone": "LOWER_RANGE",
            "simple_display": daily.ZONE_DISPLAY["LOWER_RANGE"],
        }
        return pd.DataFrame([
            {**base, "asset": "B", "simple_color": "GREEN", "position_pct": 20, "range_quality": 90},
            {**base, "asset": "A", "simple_color": "GREEN", "position_pct": 10, "range_quality": 70},
            {**base, "asset": "C", "simple_color": "YELLOW", "position_pct": 40, "range_quality": 99,
             "simple_zone": "OBSERVE", "simple_display": daily.ZONE_DISPLAY["OBSERVE"]},
        ])

    def test_deterministic_ranking_and_rendering(self):
        first = morning_brief._weekly_consolidation_rows(self.frame())
        second = morning_brief._weekly_consolidation_rows(self.frame().sample(frac=1, random_state=4))
        self.assertEqual(first, second)
        self.assertTrue(first[0].startswith("🟢 A | DÓŁ KONSOLIDACJI"))
        self.assertIn("current 0.017920", first[0])
        self.assertIn("range 0.017650–0.019351", first[0])
        self.assertIn("position 10.0%", first[0])
        self.assertNotIn("FALSE_BREAKOUT", "\n".join(first))

    def test_adaptive_price_formatting(self):
        self.assertEqual(morning_brief._fmt_num(1200), "1,200.00")
        self.assertEqual(morning_brief._fmt_num(4.524), "4.5240")
        self.assertEqual(morning_brief._fmt_num(.01765), "0.017650")
        self.assertEqual(morning_brief._fmt_num(.001765), "0.00176500")

    def test_helpers_do_not_mutate_sqlite_or_strategies(self):
        protected = list((ROOT / "journal").glob("*.sqlite")) + list((ROOT / "STRATEGIES").rglob("*.py"))
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
        daily.simple_position_zone(20, "FRESH", True, False)
        morning_brief._weekly_consolidation_rows(self.frame())
        after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
