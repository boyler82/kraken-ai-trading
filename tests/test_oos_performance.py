from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import analyze_oos_performance as oos
import build_ai_research_memory_packet as memory_packet
import run_complete_daily_research as daily
from lib import research_memory as rm


def row(episode: str, value: float, role: str, variant: str = "V1", hour: int = 0, regime: str = "BEAR") -> dict:
    return {
        "setup_episode_id": episode, "strategy_family": "MOMENTUM", "strategy_variant": variant,
        "sample_role": role, "net_return_pct": value, "mfe_pct": max(value, 0),
        "mae_pct": min(value, 0), "holding_hours": 4, "entry_timestamp": f"2026-01-01T{hour % 24:02d}:00:00Z",
        "market_regime": regime, "relative_strength_percentile_at_entry": 70,
        "range_position_pct_at_entry": 25, "volume_z_score_at_entry": .5,
        "universe_above_ema20_pct": 30,
    }


class OOSPerformanceUnitTests(unittest.TestCase):
    def test_bootstrap_reproducibility_and_intervals(self):
        values = [2, 1, -1, 3, -2] * 6
        first = oos.bootstrap_intervals(values)
        second = oos.bootstrap_intervals(values)
        self.assertEqual(first, second)
        self.assertLessEqual(first["ev_ci_lower_pct"], sum(values) / len(values))
        self.assertGreaterEqual(first["ev_ci_upper_pct"], sum(values) / len(values))
        self.assertLessEqual(first["wr_ci_lower_pct"], 60)
        self.assertGreaterEqual(first["wr_ci_upper_pct"], 60)

    def test_bootstrap_small_n_rejected(self):
        result = oos.bootstrap_intervals([1] * 9)
        self.assertEqual(result["bootstrap_status"], "BOOTSTRAP_INSUFFICIENT_SAMPLE")
        self.assertIsNone(result["ev_ci_lower_pct"])

    def test_negative_expectancy_labels(self):
        self.assertEqual(oos.negative_expectancy_status(29, -1, -0.1), "INSUFFICIENT_SAMPLE")
        self.assertEqual(oos.negative_expectancy_status(30, -1, .1), "NEGATIVE_POINT_ESTIMATE_ONLY")
        self.assertEqual(oos.negative_expectancy_status(30, -1, -.1), "LIKELY_NEGATIVE")
        self.assertEqual(oos.negative_expectancy_status(100, -1, -.1), "HIGHER_CONFIDENCE_NEGATIVE")

    def test_unique_episode_and_variant_correlation(self):
        rows = [row("same", 1, "DEVELOPMENT", "A"), row("same", 99, "DEVELOPMENT", "B")]
        result = oos.sample_metrics(rows)
        self.assertEqual(result["unique_episode_count"], 1)
        self.assertEqual(result["variant_trade_count"], 2)
        self.assertEqual(result["expected_value_pct"], 1)

    def test_degradation_and_status(self):
        dev = rm.metrics([row(str(i), 1, "DEVELOPMENT") for i in range(20)])
        forward = rm.metrics([row(str(i), -1, "FORWARD_OOS") for i in range(20)])
        self.assertEqual(oos.degradation(dev, forward)["ev_delta_oos_minus_dev"], -2)
        self.assertEqual(oos.oos_status(dev, forward), "OOS_NEGATIVE")

    def test_conditional_is_development_defined_and_not_ranked(self):
        rows = [row(f"d{i}", 1, "DEVELOPMENT", regime="BEAR") for i in range(20)]
        rows += [row(f"o{i}", 1, "FORWARD_OOS", regime="BEAR") for i in range(20)]
        rows += [row("o-new", 99, "FORWARD_OOS", regime="BULL")]
        result = oos.conditional_validation(rows)
        regime_cells = [x for x in result if x["dimension"] == "market_regime"]
        self.assertEqual({x["value"] for x in regime_cells}, {"BEAR"})
        self.assertEqual(regime_cells[0]["oos_confirmation_status"], "SUPPORTED_OOS_UNVALIDATED")
        self.assertNotIn("rank", json.dumps(result).lower())

    def test_rolling_metrics_and_stability(self):
        positive = [row(str(i), 1 if i % 4 else -1, "DEVELOPMENT", hour=i) for i in range(100)]
        rolling = oos.rolling_metrics(positive)
        self.assertAlmostEqual(rolling["20"]["rolling_ev"], .6)
        self.assertEqual(rolling["20"]["rolling_pf"], 4)
        self.assertEqual(oos.stability_status(100, rolling), "STABLE_POSITIVE_UNVALIDATED")
        self.assertEqual(oos.stability_status(49, rolling), "INSUFFICIENT_SAMPLE")


class OOSIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "memory.sqlite"
        self.db = rm.connect(self.path)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def insert(self, episode: str, value: float, role: str, variant: str = "V1") -> None:
        values = (f"id-{episode}-{variant}", episode, None, "BTC", "MOMENTUM", variant,
                  "2026-01-01T00:00:00Z", "2026-01-01T04:00:00Z", 100, 101, "WIN" if value > 0 else "LOSS", "TEST",
                  value, value, max(value, 0), min(value, 0), 4, 3, 2, "BEAR", 70, 25, .5, "EARLY", role)
        self.db.execute("INSERT INTO research_setup_outcomes VALUES(" + ",".join("?" for _ in values) + ")", values)

    def test_development_oos_separation_without_contamination(self):
        for i in range(30): self.insert(f"d{i}", 1, "DEVELOPMENT")
        for i in range(20): self.insert(f"o{i}", -1, "FORWARD_OOS")
        self.db.commit()
        result = oos.analyze(self.db)["strategies"][0]
        self.assertEqual(result["DEVELOPMENT"]["unique_episode_count"], 30)
        self.assertEqual(result["DEVELOPMENT"]["expected_value_pct"], 1)
        self.assertEqual(result["FORWARD_OOS"]["unique_episode_count"], 20)
        self.assertEqual(result["FORWARD_OOS"]["expected_value_pct"], -1)

    def test_chief_compact_oos_integration(self):
        packet = {"status": "AVAILABLE", "market_memory_summary": {}, "oos_summary": [{"strategy": str(i), "blob": "x" * 1000} for i in range(8)], "research_memory_statistical_warnings": ["DATA_SNOOPING_RISK"]}
        compact = memory_packet.compact_for_chief(packet)
        self.assertEqual(len(compact["oos_summary"]), 5)
        self.assertIn("research_memory_statistical_warnings", compact)
        self.assertLessEqual(len(json.dumps(compact).encode()), 15000)

    @patch.object(daily, "run_tactical_outcome_tracker", return_value=(None, {}))
    @patch.object(daily, "generate_decision_brief", return_value=(None, {}))
    @patch.object(daily, "generate_chief", side_effect=[("x", "chief"), ("x", "chief")])
    @patch.object(daily, "generate_observations", return_value=("x", "observations"))
    @patch.object(daily, "generate", return_value=({"run_status": {"x": "OK"}}, "latest", "full"))
    @patch.object(daily, "run_modular", return_value={"errors": {}, "succeeded": 1, "total": 1})
    @patch.object(daily, "call")
    def test_oos_failure_is_fail_soft(self, call, *_):
        call.side_effect = lambda args: (False, "boom") if "scripts/analyze_oos_performance.py" in args else (True, "ok")
        result = daily.run(reuse=True)
        self.assertTrue(result["success"])
        self.assertTrue(any(x.startswith("OOS_VALIDATION_UNAVAILABLE") for x in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
