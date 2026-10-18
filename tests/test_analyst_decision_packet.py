from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import pytest
from pathlib import Path

ROOT_PATH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_PATH / "scripts"))

from scripts.analyst_decision_packet import ROOT, build, confirmations, consolidations, momentum_candidates, render_markdown, rotation, validate
from scripts.morning_brief import render_analyst_packet_brief


DATE = "2026-08-03"
NOW = "2026-08-03T18:00:00Z"


@pytest.mark.archive
class AnalystDecisionPacketTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = build(DATE, NOW)

    def test_schema_modules_limits_and_markdown(self):
        packet = self.packet
        validate(packet, [ROOT / x["path"] for x in packet["source_manifest"]])
        for key in ("run_status", "market_context", "rsi2", "top_consolidations", "top_momentum", "rotation", "active_position_context", "validation_feedback", "donchian"):
            self.assertIn(key, packet)
        self.assertLessEqual(len(packet["top_consolidations"]), 4)
        self.assertLessEqual(len(packet["top_momentum"]), 5)
        self.assertLessEqual(len(packet["validation_feedback"]), 5)
        markdown = render_markdown(packet)
        self.assertTrue(80 <= len(markdown.splitlines()) <= 150)

    def test_duplicates_nan_determinism_and_unknowns(self):
        for key in ("top_consolidations", "top_momentum"):
            assets = [x["asset"] for x in self.packet[key]]
            self.assertEqual(len(assets), len(set(assets)))
        encoded = json.dumps(self.packet, allow_nan=False)
        self.assertNotIn("NaN", encoded); self.assertNotIn("Infinity", encoded)
        self.assertEqual(build(DATE, NOW), self.packet)
        self.assertIn("PROBABILITY_UNAVAILABLE", self.packet["unknowns"])

    def test_missing_position_cross_module_and_risk_ranking(self):
        self.assertTrue(self.packet["active_position_context"]["position_data_missing_for_TAO"])
        self.assertTrue(self.packet["cross_module_confirmations"])
        order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        levels = [order[x["severity"]] for x in self.packet["risk_summary"]]
        self.assertEqual(levels, sorted(levels))

    def test_consolidation_rr_rotation_rejection_and_conflict(self):
        source = {"candidates": [{"asset": "X", "latest_available_market_price": 100, "range_low": 90, "midpoint": 110, "range_high": 120, "estimated_total_friction_pct": 1, "range_still_valid": True, "freshness_status": "FRESH", "position_pct": 20}]}
        row = consolidations(source)[0]
        self.assertAlmostEqual(row["risk_reward_to_midpoint"], 1)
        self.assertAlmostEqual(row["risk_reward_to_high"], 2)
        rejected = rotation({"top_candidates": [{"asset": "X", "net_relative_upside_after_costs": -0.1}]})
        self.assertEqual(rejected["alternatives"], [])
        mom = momentum_candidates({"candidates": [{"asset": "X", "momentum_stage": "BREAKOUT_DEVELOPING", "overextension_risk": "HIGH", "relative_strength_vs_btc_24h_pct": 2, "momentum_breakout_score": 70}]})
        _, conflicts = confirmations([{"asset": "X", "range_valid": True, "position_pct": 20}], mom, {"alternatives": []})
        self.assertEqual(conflicts[0]["conflict"], ["OVEREXTENSION"])

    def test_morning_brief_and_no_order_generation(self):
        text = render_analyst_packet_brief(self.packet)
        for heading in ("MARKET CONTEXT", "STRONGEST HYPOTHESIS", "TOP 3 CANDIDATES", "ROTATION RESULT", "ACTIVE-POSITION ALERTS", "TOP 5 RISKS", "NEXT CONDITIONS"):
            self.assertIn(heading, text)
        encoded = json.dumps(self.packet).lower()
        self.assertNotIn("buy_command", encoded); self.assertNotIn("sell_command", encoded)

    def test_packet_generation_does_not_mutate_protected_artifacts(self):
        protected = list((ROOT / "journal").glob("*.sqlite")) + [p for p in (ROOT / "STRATEGIES").rglob("*") if p.is_file()]
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        before = {p: digest(p) for p in protected}
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run([sys.executable, str(ROOT / "scripts/analyst_decision_packet.py"), "--date", DATE, "--generated-at", NOW, "--output-dir", directory], check=True, capture_output=True)
        self.assertEqual(before, {p: digest(p) for p in protected})


if __name__ == "__main__":
    unittest.main()
