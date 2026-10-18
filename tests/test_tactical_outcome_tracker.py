from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from tactical_outcome_tracker import EVENTS, SNAPSHOTS, build_summary, run
import run_complete_daily_research as daily


def opportunity(asset="TEST", action="BUY_ON_BREAKOUT", recommendation="SPECULATIVE_REVIEW"):
    plan = None if action == "AVOID" else {
        "preferred_entry": 105.0, "entry_method": "BREAKOUT_LEVEL_WITH_CONFIRMATION",
        "stop_loss": 95.0, "stop_distance_pct": 9.52,
        "planned_trade_family": "MOMENTUM_BREAKOUT", "exit_method": "MOMENTUM_STRUCTURE_EXIT",
        "warnings": ["RISK_REWARD_NOT_ESTIMABLE"],
    }
    return {
        "asset": asset, "action": action, "technical_action": action,
        "recommendation": recommendation, "conviction": "LOW",
        "setup_quality_score": 55, "actionability_score": 70,
        "daily_score": 68, "weekly_score": 52, "current_price": 100,
        "net_edge_after_costs": -1, "rotation_score_advantage": -2,
        "warnings": ["UNVALIDATED_EDGE"], "trade_plan": plan,
    }


def packet(timestamp="2026-01-01T00:30:00Z", row=None):
    row = row or opportunity()
    return {
        "generated_at_utc": timestamp, "objective": "BTC_ACCUMULATION",
        "candidates": [{"asset": row["asset"], "identity": {"kraken_pair": f"{row['asset']}USD"}}],
        "tactical_opportunities": {"daily": [row], "weekly": [row], "avoid": []},
    }


def candles(path: Path, rows: list[tuple]):
    pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"]).to_csv(path, index=False)


class TacticalOutcomeTrackerTests(unittest.TestCase):
    def test_production_orchestrator_keeps_packet_and_output_path_distinct(self):
        expected=packet();output=Path('/tmp/chief.json')
        with patch.object(daily,'generate_chief',return_value=(expected,output)):
            actual_packet,actual_path=daily.generate_chief_artifacts('btc','BTC',None,False,False)
        self.assertIs(actual_packet,expected);self.assertIsInstance(actual_packet,dict);self.assertIs(actual_path,output)
    def test_snapshot_is_unique_immutable_and_input_is_not_mutated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); data = root / "data"; reports = root / "reports"; market = root / "market"; market.mkdir()
            source = packet(); before = json.dumps(source, sort_keys=True)
            run(source, "2026-01-01T01:00:00Z", data, reports, market)
            first = (data / SNAPSHOTS).read_text()
            run(source, "2026-01-01T02:00:00Z", data, reports, market)
            self.assertEqual(first, (data / SNAPSHOTS).read_text())
            self.assertEqual(1, len(first.splitlines()))
            self.assertEqual(before, json.dumps(source, sort_keys=True))

    def test_candle_overlapping_snapshot_is_never_used(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); data = root / "data"; reports = root / "reports"; market = root / "market"; market.mkdir()
            candles(market / "TESTUSD_1H.csv", [
                ("2026-01-01T00:00:00Z", 100, 120, 99, 110, 1),  # started before snapshot
                ("2026-01-01T01:00:00Z", 100, 120, 99, 110, 1),
            ])
            _, early = run(packet(), "2026-01-01T01:30:00Z", data, reports, market)
            self.assertEqual("NOT_TRIGGERED", early["current_snapshot_status"][0]["status"])
            self.assertEqual("", (data / EVENTS).read_text())
            _, complete = run(packet(), "2026-01-01T02:00:00Z", data, reports, market)
            self.assertEqual("TRIGGERED", complete["current_snapshot_status"][0]["status"])
            event = json.loads((data / EVENTS).read_text().splitlines()[0])
            self.assertEqual("2026-01-01T02:00:00+00:00", event["trigger_timestamp"])

    def test_horizon_outcome_is_not_emitted_before_due_time(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); data = root / "data"; reports = root / "reports"; market = root / "market"; market.mkdir()
            rows = [(f"2026-01-01T{hour:02d}:00:00Z", 106, 108 + hour, 100, 106 + hour, 1) for hour in range(1, 8)]
            candles(market / "TESTUSD_1H.csv", rows)
            run(packet(), "2026-01-01T05:59:00Z", data, reports, market)
            events = [json.loads(x) for x in (data / EVENTS).read_text().splitlines()]
            self.assertEqual(["TRIGGERED"], [x["event_type"] for x in events])
            run(packet(), "2026-01-01T06:00:00Z", data, reports, market)
            events = [json.loads(x) for x in (data / EVENTS).read_text().splitlines()]
            horizon = [x for x in events if x["event_type"] == "HORIZON_OUTCOME"]
            self.assertEqual([4], [x["horizon_hours"] for x in horizon])

    def test_watch_transition_uses_only_later_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); data = root / "data"; reports = root / "reports"; market = root / "market"; market.mkdir()
            watch = opportunity(action="WATCH", recommendation="HIGH_PRIORITY_WATCH")
            run(packet("2026-01-01T00:00:00Z", watch), "2026-01-01T00:00:00Z", data, reports, market)
            run(packet("2026-01-01T12:00:00Z", opportunity()), "2026-01-01T12:00:00Z", data, reports, market)
            events = [json.loads(x) for x in (data / EVENTS).read_text().splitlines()]
            activated = [x for x in events if x["event_type"] == "WATCH_ACTIVATED"]
            self.assertEqual(12, activated[0]["time_to_activation_hours"])

    def test_avoid_is_counterfactual_and_small_samples_publish_no_edge(self):
        avoid = opportunity("BAD", "AVOID", "AVOID")
        source = packet(row=avoid)
        source["tactical_opportunities"] = {"daily": [], "weekly": [], "avoid": [avoid]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); market = root / "market"; market.mkdir()
            _, summary = run(source, "2026-01-02T00:00:00Z", root / "data", root / "reports", market)
            group = summary["results"]["by_recommendation"][0]
            self.assertTrue(group["counterfactual_only"])
            self.assertEqual("COUNTERFACTUAL_EXCLUDED", group["return_24h"]["status"])
            self.assertIsNone(group["return_24h"]["mean_return_pct"])
        normal = build_summary([{
            "snapshot_id": "one", "asset": "A", "recommendation": "ACTIONABLE",
            "technical_action": "BUY_NOW", "setup_quality_score": 80, "actionability_score": 80,
            "daily_score": 80, "weekly_score": 80, "planned_trade_family": "MOMENTUM_BREAKOUT",
        }], [{"snapshot_id": "one", "event_type": "HORIZON_OUTCOME", "horizon_hours": 24, "return_pct": 9}], "now")
        group = normal["results"]["by_recommendation"][0]
        self.assertEqual("INSUFFICIENT_SAMPLE", group["return_24h"]["status"])
        self.assertIsNone(group["return_24h"]["mean_return_pct"])


if __name__ == "__main__":
    unittest.main()
