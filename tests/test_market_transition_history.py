import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import print_market_transition_history as history


NOW = datetime(2026, 8, 23, 18, 0, tzinfo=timezone.utc)


def snapshot(timestamp, state="CONSOLIDATION", identity="hash-1", market_timestamp=None):
    row = {
        "timestamp": timestamp,
        "market_state": state,
        "market_data_hash": identity,
        "market_data_timestamp": market_timestamp or timestamp,
        "continuation_evidence": 1,
        "correction_evidence": 2,
        "neutral_evidence": 3,
        "btc_structure_1h": {"trend": "HH_HL"},
        "btc_structure_4h": {"trend": "MIXED"},
        "breadth": {"above_ema20_pct": 40, "above_ema50_pct": 50},
        "breadth_delta": {"classification": "STABLE"},
        "sell_pressure": {
            "4h": {"classification": "NORMAL", "ratio": 1.2},
            "12h": {"classification": "DECLINING", "ratio": 0.8},
        },
        "breakout_retention_pct": 60,
        "median_pullback_depth_pct": 29,
        "rs_leaders": [{"asset": asset} for asset in ("ZRO", "MORPHO", "STX", "OTHER")],
    }
    if identity is None:
        row.pop("market_data_hash")
    return row


class MarketTransitionHistoryTests(unittest.TestCase):
    def write(self, directory, name, value):
        (Path(directory) / name).write_text(json.dumps(value), encoding="utf-8")

    def test_24h_filtering_and_chronological_ordering(self):
        with tempfile.TemporaryDirectory() as td:
            self.write(td, "z.json", snapshot("2026-08-23T17:00:00Z", identity="new"))
            self.write(td, "a.json", snapshot("2026-08-22T17:59:59Z", identity="old"))
            self.write(td, "m.json", snapshot("2026-08-23T01:00:00+00:00", identity="middle"))
            rows, warnings = history.load_history(Path(td), hours=24, now=NOW)
        self.assertFalse(warnings)
        self.assertEqual([row["market_data_hash"] for row in rows], ["middle", "new"])

    def test_state_timeline_and_collapsed_state_changes(self):
        rows = []
        for hour, state in enumerate(("CONSOLIDATION", "HEALTHY_PULLBACK", "HEALTHY_PULLBACK", "CONTINUATION_READY"), 10):
            item = snapshot(f"2026-08-23T{hour}:00:00Z", state, f"hash-{hour}")
            item["_prediction_timestamp"] = history.parse_timestamp(item["timestamp"])
            item["_source_file"] = f"{hour}.json"
            rows.append(item)
        report = history.render_history(rows, hours=24, now=NOW, missing=[])
        self.assertIn("CONSOLIDATION → HEALTHY_PULLBACK → HEALTHY_PULLBACK → CONTINUATION_READY", report)
        self.assertIn("STATE CHANGES:\nCONSOLIDATION → HEALTHY_PULLBACK → CONTINUATION_READY", report)
        self.assertIn("State transitions: 2", report)

    def test_duplicate_hash_detection_and_non_independent_statistics(self):
        rows = []
        for hour, state in ((12, "CONSOLIDATION"), (13, "HEALTHY_PULLBACK"), (14, "CONTINUATION_READY")):
            item = snapshot(f"2026-08-23T{hour}:00:00Z", state, "same" if hour < 14 else "different")
            item["_prediction_timestamp"] = history.parse_timestamp(item["timestamp"])
            item["_source_file"] = f"{hour}.json"
            rows.append(item)
        report = history.render_history(rows, hours=24, now=NOW, missing=[])
        self.assertIn("Duplicate modern hashes: 1", report)
        self.assertIn("Duplicate modern hash details: same (x2)", report)
        self.assertIn("Independent market observations: 2", report)
        self.assertIn("STATE_CONFLICT_WITHIN_SAME_MARKET_OBSERVATION → CONTINUATION_READY", report)

    def test_legacy_predictions_are_clearly_marked(self):
        item = snapshot("2026-08-23T12:00:00Z", identity=None)
        item["_prediction_timestamp"] = history.parse_timestamp(item["timestamp"])
        item["_source_file"] = "legacy.json"
        report = history.render_history([item], now=NOW, missing=[])
        self.assertIn("LEGACY — NO MARKET_DATA_HASH", report)
        self.assertIn("Legacy timestamp-grouped observations: 1", report)

    def test_legacy_timestamp_grouping_unknown_and_mixed_history(self):
        rows = [
            snapshot("2026-08-23T10:00:00Z", identity=None, market_timestamp="2026-08-23T05:00:00Z"),
            snapshot("2026-08-23T10:05:00Z", identity=None, market_timestamp="2026-08-23T05:00:00+00:00"),
            snapshot("2026-08-23T11:00:00Z", identity=None, market_timestamp="2026-08-23T06:00:00Z"),
            snapshot("2026-08-23T12:00:00Z", identity="modern"),
            snapshot("2026-08-23T13:00:00Z", identity="modern"),
        ]
        unknown = snapshot("2026-08-23T14:00:00Z", identity=None)
        unknown.pop("market_data_timestamp")
        rows.append(unknown)
        for index, item in enumerate(rows):
            item["_prediction_timestamp"] = history.parse_timestamp(item["timestamp"])
            item["_source_file"] = f"{index}.json"
        report = history.render_history(rows, now=NOW, missing=[])
        self.assertIn("Predictions in window: 6", report)
        self.assertIn("Independent market observations: 3", report)
        self.assertIn("Modern hash-identified observations: 1", report)
        self.assertIn("Legacy timestamp-grouped observations: 2", report)
        self.assertIn("Legacy independence unknown: 1", report)
        self.assertIn("Duplicate legacy market timestamps: 1", report)
        self.assertIn("LEGACY_OBSERVATION_INDEPENDENCE_UNCERTAIN", report)

    def test_conflict_shares_and_duration_use_collapsed_observations(self):
        rows = [
            snapshot("2026-08-23T10:00:00Z", "A", "same", "2026-08-23T05:00:00Z"),
            snapshot("2026-08-23T10:05:00Z", "B", "same", "2026-08-23T05:00:00Z"),
            snapshot("2026-08-23T11:00:00Z", "B", "next", "2026-08-23T07:00:00Z"),
            snapshot("2026-08-23T12:00:00Z", "B", "last", "2026-08-23T10:00:00Z"),
        ]
        for index, item in enumerate(rows):
            item["_prediction_timestamp"] = history.parse_timestamp(item["timestamp"])
            item["_source_file"] = f"{index}.json"
        report = history.render_history(rows, now=NOW, missing=[])
        self.assertIn("STATE_CONFLICT_WITHIN_SAME_MARKET_OBSERVATION", report)
        self.assertIn("recorded states: A, B", report)
        self.assertIn("RAW PREDICTION SHARE:\n  A: 25.0% (1/4)\n  B: 75.0% (3/4)", report)
        self.assertIn("INDEPENDENT OBSERVATION SHARE:", report)
        self.assertIn("B: 66.7% (2/3)", report)
        self.assertIn("OBSERVED STATE DURATION APPROXIMATION:\n  B: 3.00h", report)

    def test_distinct_modern_hashes_and_insufficient_duration(self):
        rows = [snapshot("2026-08-23T10:00:00Z", identity="a"), snapshot("2026-08-23T10:01:00Z", identity="b")]
        for index, item in enumerate(rows):
            item.pop("market_data_timestamp")
            item["_prediction_timestamp"] = history.parse_timestamp(item["timestamp"])
            item["_source_file"] = str(index)
        report = history.render_history(rows, now=NOW, missing=[])
        self.assertIn("Independent market observations: 2", report)
        self.assertIn("INSUFFICIENT_INDEPENDENT_TIMESTAMPS_FOR_DURATION_ESTIMATE", report)

    def test_build_report_does_not_modify_historical_files(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "prediction.json"
            self.write(td, path.name, snapshot("2026-08-23T12:00:00Z"))
            before = path.read_bytes()
            history.build_report(hours=24, now=NOW, prediction_dir=Path(td), missing_dir=Path(td) / "missing")
            self.assertEqual(path.read_bytes(), before)

    def test_malformed_and_partial_snapshots_fail_soft(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "broken.json").write_text("{", encoding="utf-8")
            self.write(td, "untimestamped.json", {"market_state": "CONSOLIDATION"})
            self.write(td, "partial.json", {"timestamp": "2026-08-23T12:00:00Z", "market_state": "INDETERMINATE"})
            report = history.build_report(hours=24, now=NOW, prediction_dir=Path(td), missing_dir=Path(td) / "missing")
        self.assertIn("INDETERMINATE", report)
        self.assertIn("WARNINGS (2 malformed/partial files)", report)
        self.assertIn("BTC: 1H N/A | 4H N/A", report)

    def test_empty_history(self):
        with tempfile.TemporaryDirectory() as td:
            report = history.build_report(hours=24, now=NOW, prediction_dir=Path(td), missing_dir=Path(td))
        self.assertIn("No predictions recorded in this window.", report)
        self.assertIn("STATE CHANGES:\nNONE", report)
        self.assertIn("Latest state: NONE", report)

    def test_timezone_offsets_are_normalized_and_naive_snapshots_rejected(self):
        self.assertEqual(history.parse_timestamp("2026-08-23T20:00:00+02:00"), NOW)
        with self.assertRaisesRegex(ValueError, "timezone"):
            history.parse_timestamp("2026-08-23T18:00:00")
        with self.assertRaisesRegex(ValueError, "timezone"):
            history.load_history(Path("unused"), now=datetime(2026, 8, 23, 18, 0))
        with tempfile.TemporaryDirectory() as td:
            self.write(td, "offset.json", snapshot("2026-08-23T19:00:00+02:00"))
            rows, warnings = history.load_history(Path(td), hours=2, now=NOW)
        self.assertEqual(len(rows), 1)
        self.assertFalse(warnings)

    def test_missing_scheduled_observations_are_read_not_inferred(self):
        with tempfile.TemporaryDirectory() as td:
            self.write(td, "miss.json", {"expected_timestamp": "2026-08-23T16:00:00Z", "status": "MISSING_SCHEDULED_OBSERVATION"})
            missing, warnings = history.load_missing_observations(Path(td), hours=24, now=NOW)
        self.assertEqual(len(missing), 1)
        self.assertFalse(warnings)


if __name__ == "__main__":
    unittest.main()
