from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
import warnings
import pytest
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import consolidation_range_engine as engine
import morning_brief


def _bars(count: int = 60, start: str = "2026-01-01", freq: str = "4h") -> pd.DataFrame:
    timestamps = pd.date_range(start, periods=count, freq=freq, tz="UTC")
    close = 100 + np.sin(np.arange(count) * np.pi / 4) * 8
    return pd.DataFrame({
        "timestamp": timestamps, "open": close, "high": close + 1,
        "low": close - 1, "close": close, "volume": 1.0,
    })


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_completed_candles_only_and_no_future_leakage():
    hourly = _bars(13, freq="1h")
    cutoff = pd.Timestamp("2026-01-01 10:30", tz="UTC")
    before = engine.completed_4h_bars(hourly, cutoff)
    assert list(before["timestamp"]) == list(pd.to_datetime(["2026-01-01 00:00Z", "2026-01-01 04:00Z"]))
    future = _bars(6, start="2026-01-01 13:00", freq="1h")
    after = engine.completed_4h_bars(pd.concat([hourly, future]), cutoff)
    pd.testing.assert_frame_equal(before, after)


def test_missing_source_candle_is_not_filled():
    hourly = _bars(8, freq="1h").drop(index=2)
    result = engine.completed_4h_bars(hourly, "2026-01-02T00:00:00Z")
    assert len(result) == 1
    assert result.iloc[0]["timestamp"] == pd.Timestamp("2026-01-01 04:00Z")


def test_atr_boundary_tolerance_and_consecutive_touch_merge():
    df = _bars(4)
    df["low"] = [101.9, 101.0, 101.5, 103.0]
    tolerance = pd.Series([2.0] * 4)
    events = engine.boundary_events(df, boundary=100, tolerance=tolerance, side="lower")
    assert [event.index for event in events] == [0]
    df.loc[2, "low"] = 103.0
    df.loc[3, "low"] = 101.0
    events = engine.boundary_events(df, 100, tolerance, "lower")
    assert [event.index for event in events] == [0, 3]


def test_false_and_confirmed_breakout_classification():
    df = _bars(7)
    df["high"] = [105, 111, 106, 105, 112, 113, 105]
    df["low"] = 95
    df["close"] = [100, 109, 100, 100, 111, 112, 100]
    found = engine.breakout_events(df, low=90, high=110, tolerance=pd.Series([0.5] * 7))
    assert found["false_above"] == [1]
    assert found["confirmed_above"] == [4]


def test_traversal_durations_both_directions():
    lows = [engine.BoundaryEvent(2, "a"), engine.BoundaryEvent(12, "b")]
    highs = [engine.BoundaryEvent(7, "c"), engine.BoundaryEvent(18, "d")]
    assert engine.traversal_durations(lows, highs, []) == [5, 6]
    assert engine.traversal_durations(highs, lows, []) == [5]
    assert engine.traversal_durations(lows, highs, [5]) == [6]


def test_position_percentage():
    assert engine.position_pct(125, 100, 200) == 25


def test_below_range_candidate_has_explicit_non_normal_state():
    bars = _bars(70)
    bars.loc[bars.index[-1], ["open", "high", "low", "close"]] = [89.0, 90.0, 88.0, 89.0]
    row = engine.analyze_candidate(bars, "ONDO", 40)
    assert row["status"] in {"BELOW_RANGE_PENDING_RECOVERY", "FALSE_BREAKDOWN_RECOVERY", "RANGE_INVALIDATED", "BREAKDOWN_CONFIRMED"}
    assert not (row["range_valid"] and row["status"] == "BELOW_RANGE_PENDING_RECOVERY")
    if row["status"] == "FALSE_BREAKDOWN_RECOVERY":
        assert row["recovery_condition"] == "CLOSE_AT_OR_ABOVE_RANGE_LOW"
    else:
        assert row["range_valid"] is False
        assert row["invalidation_reason"]


def test_deterministic_output(tmp_path):
    row = engine.analyze_candidate(_bars(70), "BTC", 40)
    first = tmp_path / "first"
    second = tmp_path / "second"
    engine.write_reports([row], [], "2026-01-01", first)
    engine.write_reports([row], [], "2026-01-01", second)
    for suffix in ("csv", "md", "json"):
        assert (first / f"2026-01-01_consolidation_ranges.{suffix}").read_bytes() == (second / f"2026-01-01_consolidation_ranges.{suffix}").read_bytes()


def test_engine_does_not_mutate_sqlite_or_strategies(tmp_path):
    protected = list((ROOT / "journal").glob("*.sqlite")) + list((ROOT / "STRATEGIES").rglob("*.py"))
    before = {path: _digest(path) for path in protected}
    row = engine.analyze_candidate(_bars(70), "BTC", 40)
    engine.write_reports([row], [], "2026-01-01", tmp_path)
    assert {path: _digest(path) for path in protected} == before


def test_quality_contributions_sum_to_score():
    row = engine.analyze_candidate(_bars(70), "BTC", 40)
    expected = round(max(0, min(100, sum(row["quality_components"].values()))), 2)
    assert row["range_quality"] == expected


def test_morning_brief_graceful_fallback_and_filter():
    assert morning_brief._consolidation_range_rows(pd.DataFrame()) == []
    assert morning_brief._consolidation_range_rows(pd.DataFrame([{"asset": "BTC"}])) == []
    base = engine._flat(engine.analyze_candidate(_bars(70), "BTC", 40))
    base["range_state"] = "WEAK_RANGE"
    base["status"] = "MID_RANGE"
    assert morning_brief._consolidation_range_rows(pd.DataFrame([base])) == []
    base["status"] = "NEAR_RANGE_LOW"
    assert len(morning_brief._consolidation_range_rows(pd.DataFrame([base]))) == 1


def test_json_contains_no_nonstandard_nan(tmp_path):
    row = engine.analyze_candidate(_bars(70), "BTC", 40)
    _, _, path = engine.write_reports([row], [], "2026-01-01", tmp_path)
    json.loads(path.read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def test_inclusive_duration_and_calendar_reconciliation():
    for count in (1, 2, 48):
        metrics = engine.timeline_metrics(_bars(count))
        assert metrics["duration_bars"] == count
        assert metrics["duration_trading_hours"] == count * 4
        assert metrics["duration_calendar_hours"] == (count - 1) * 4
        assert metrics["duration_calendar_days"] == (count - 1) * 4 / 24
        assert metrics["duration_reconciled"] is True
    crossing = _bars(3, start="2026-01-01 20:00")
    assert engine.timeline_metrics(crossing)["duration_bars"] == 3


def test_gap_reporting_and_data_inconsistent_reconciliation():
    gapped = _bars(4).drop(index=1).reset_index(drop=True)
    metrics = engine.timeline_metrics(gapped)
    assert metrics["missing_expected_4h_bars"] == 1
    assert metrics["continuity_status"] == "GAPS_PRESENT"
    descending = _bars(2).iloc[::-1].reset_index(drop=True)
    assert engine.timeline_metrics(descending)["duration_reconciled"] is False
    assert engine.timeline_metrics(descending)["continuity_status"] == "DATA_INCONSISTENT"


def test_failed_timeline_reconciliation_marks_candidate_data_inconsistent(monkeypatch):
    original = engine.timeline_metrics
    def failed(frame):
        result = original(frame)
        result["duration_reconciled"] = False
        result["continuity_status"] = "DATA_INCONSISTENT"
        return result
    monkeypatch.setattr(engine, "timeline_metrics", failed)
    assert engine.analyze_candidate(_bars(70), "BTC", 40)["status"] == "DATA_INCONSISTENT"


def test_selected_start_end_and_confirmed_breakout_precedence():
    df = _bars(70)
    df.loc[68:, ["open", "close", "high", "low"]] = [120, 120, 121, 119]
    row = engine.analyze_candidate(df, "BTC", 40)
    assert row["status"] == "BREAKOUT_CONFIRMED"
    assert row["range_active"] is False
    assert row["range_start_timestamp"] == pd.Timestamp(df.iloc[-40]["timestamp"]).isoformat()
    assert row["range_end_timestamp"] == pd.Timestamp(df.iloc[67]["timestamp"]).isoformat()
    assert row["breakout_event_timestamp"] == pd.Timestamp(df.iloc[68]["timestamp"]).isoformat()
    assert row["breakout_confirmation_timestamp"] == pd.Timestamp(df.iloc[69]["timestamp"]).isoformat()
    assert row["invalidation_timestamp"] != row["range_end_timestamp"]


def test_trend_flatness_excludes_post_breakout_bars():
    df = _bars(70)
    df.loc[68:, ["open", "close", "high", "low"]] = [150, 150, 151, 149]
    row = engine.analyze_candidate(df, "BTC", 40)
    included = df[(df["timestamp"] >= pd.Timestamp(row["range_start_timestamp"])) & (df["timestamp"] <= pd.Timestamp(row["range_end_timestamp"]))]
    x = pd.Series(range(len(included)), dtype=float)
    expected = included["close"].reset_index(drop=True).cov(x) / x.var()
    assert row["trend_slope_value"] == expected


def test_break_events_have_unique_ids_and_exclusive_classes():
    df = _bars(7)
    df["high"] = [105, 111, 106, 105, 112, 113, 105]
    df["low"] = 95
    df["close"] = [100, 109, 100, 100, 111, 112, 100]
    found = engine.breakout_events(df, 90, 110, pd.Series([0.5] * 7))
    ids = [event["event_id"] for event in found["events"]]
    assert len(ids) == len(set(ids))
    assert all(event["start_timestamp"] <= event["end_timestamp"] for event in found["events"])
    assert all(event["classification"] in {"FALSE_BREAKOUT_ABOVE", "FALSE_BREAKDOWN_BELOW", "BREAKOUT_CONFIRMED", "BREAKDOWN_CONFIRMED", "UNRESOLVED_BREAK_EVENT"} for event in found["events"])
    assert len(found["false_above"]) + len(found["confirmed_above"]) == 2
    assert {event["classification"] for event in found["events"] if event["direction"] == "ABOVE"} == {"FALSE_BREAKOUT_ABOVE", "BREAKOUT_CONFIRMED"}


def test_traversal_and_boundary_interval_audit_fields():
    row = engine.analyze_candidate(_bars(70), "BTC", 40)
    for group in (row["low_to_high"], row["high_to_low"], row["full_traversal"]):
        if group["average_bars"] is not None:
            assert group["average_hours"] == group["average_bars"] * 4
            assert group["median_hours"] == group["median_bars"] * 4
        assert group["count"] == len(group["events"])
        assert all(event["hours"] == event["bars"] * 4 for event in group["events"])
    for side in ("lower", "upper"):
        events = row[f"{side}_boundary_events"]
        intervals = row[f"{side}_test_intervals"]
        assert intervals["count"] == max(0, len(events) - 1)


def test_raw_clipped_position_and_quality_clarity():
    df = _bars(70)
    df.loc[68:, ["open", "close", "high", "low"]] = [120, 120, 121, 119]
    row = engine.analyze_candidate(df, "BTC", 40)
    assert row["position_pct"] > 100
    assert row["position_clipped_pct"] == 100
    assert row["position_zone"] == "ABOVE_RANGE"
    assert row["quality_band"] in {"LOW", "WEAK", "MODERATE", "STRONG", "VERY_STRONG"}
    assert row["failed_quality_conditions"]


def test_no_timedelta_deprecation_warning():
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        result = engine.completed_4h_bars(_bars(12, freq="1h"), "2026-01-02T00:00:00Z")
    assert str(result["timestamp"].dtype) == "datetime64[ns, UTC]"


def test_cross_output_consistency(tmp_path):
    row = engine.analyze_candidate(_bars(70), "BTC", 40)
    csv_path, md_path, json_path = engine.write_reports([row], [], "2026-01-01", tmp_path)
    csv_row = pd.read_csv(csv_path).iloc[0]
    json_row = json.loads(json_path.read_text())["candidates"][0]
    markdown = md_path.read_text()
    for key in ("range_start_timestamp", "range_end_timestamp", "duration_bars", "duration_trading_hours", "duration_calendar_hours", "duration_calendar_days", "status", "structural_state", "range_quality", "latest_available_market_price", "position_pct", "lower_boundary_tests", "upper_boundary_tests", "confirmed_breakouts", "confirmed_breakdowns"):
        if isinstance(json_row[key], (int, float)):
            assert np.isclose(float(csv_row[key]), float(json_row[key]))
        else:
            assert str(csv_row[key]) == str(json_row[key])
    assert json_row["range_start_timestamp"] in markdown
    assert json_row["range_end_timestamp"] in markdown
    assert json_row["status"] in markdown


def test_market_timestamps_are_honestly_labeled_and_trend_units_reconcile():
    df = _bars(70)
    df.loc[68:, ["open", "close", "high", "low"]] = [120, 120, 121, 119]
    row = engine.analyze_candidate(df, "BTC", 40)
    assert "current_market_timestamp" not in row
    assert "current_price" not in row
    assert row["post_breakout_reference_timestamp"] == row["latest_available_market_timestamp"]
    assert row["post_breakout_reference_price"] == row["latest_available_market_price"]
    expected = abs(row["trend_slope_value"] * (row["duration_bars"] - 1)) / row["trend_normalization_denominator"]
    assert np.isclose(row["trend_normalized_slope"], expected)
    assert row["trend_flatness_pass"] == (row["trend_normalized_slope"] <= row["trend_flatness_threshold"])
    assert row["trend_slope_units"] == "quote_currency_per_4h_bar"
    assert row["trend_flatness_threshold_units"] == row["trend_normalized_slope_units"]


def test_morning_brief_excludes_ended_and_inconsistent_ranges():
    base = engine._flat(engine.analyze_candidate(_bars(70), "BTC", 40))
    for status in ("BREAKOUT_CONFIRMED", "BREAKDOWN_CONFIRMED", "RANGE_INVALIDATED", "DATA_INCONSISTENT"):
        base["status"] = status
        base["range_state"] = "WEAK_RANGE"
        assert morning_brief._consolidation_range_rows(pd.DataFrame([base])) == []


def _quarter_hour_rows(count=20, start="2026-01-01T00:00:00Z"):
    timestamp = pd.date_range(start, periods=count, freq="15min", tz="UTC")
    values = np.arange(count, dtype=float) + 100
    return pd.DataFrame({"timestamp": timestamp, "open": values, "high": values + 2,
                         "low": values - 2, "close": values + .5, "volume": values / 10})


def test_exact_16_to_1_ohlcv_and_incomplete_bucket_rejection():
    raw = _quarter_hour_rows(20)
    result = engine.completed_4h_bars(raw, "2026-01-01T08:00:00Z", source_timeframe="15m")
    assert len(result) == 1
    row = result.iloc[0]
    assert row["open"] == raw.iloc[0]["open"]
    assert row["high"] == raw.iloc[:16]["high"].max()
    assert row["low"] == raw.iloc[:16]["low"].min()
    assert row["close"] == raw.iloc[15]["close"]
    assert row["volume"] == raw.iloc[:16]["volume"].sum()
    assert row["source_count"] == 16


def test_missing_15m_candle_is_rejected_not_filled():
    raw = _quarter_hour_rows(32).drop(index=7)
    result = engine.completed_4h_bars(raw, "2026-01-01T08:00:00Z", source_timeframe="15m")
    assert len(result) == 1
    assert result.iloc[0]["timestamp"] == pd.Timestamp("2026-01-01T04:00:00Z")


def test_btc_operational_source_precedence(monkeypatch, tmp_path):
    operational_path = tmp_path / "BTCUSD_15m_operational.csv"
    operational = _quarter_hour_rows(16 * 50)
    stored = operational.copy()
    stored["timestamp"] = stored["timestamp"].astype("int64") // 10**9
    stored.to_csv(operational_path, index=False)
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    hourly = _bars(200, start="2025-01-01", freq="1h")
    payload_rows = []
    for _, row in hourly.iterrows():
        payload_rows.append([int(row["timestamp"].timestamp()), row["open"], row["high"], row["low"], row["close"], row["close"], row["volume"], 1])
    (raw_dir / "BTCUSD_1H.json").write_text(json.dumps({"XXBTZUSD": payload_rows, "last": 0}))
    monkeypatch.setattr(engine, "BTC_OPERATIONAL_PATH", operational_path)
    monkeypatch.setattr(engine, "RAW_DIR", raw_dir)
    bars, metadata = engine.load_asset_4h("BTC", "2026-02-01T00:00:00Z")
    assert metadata["source_path"] == str(operational_path)
    assert metadata["source_timeframe"] == "15m"
    assert len(bars) == 50


def test_source_metadata_and_stale_safety():
    raw = _quarter_hour_rows(16 * 50)
    derived = engine.completed_4h_bars(raw, "2026-02-01T00:00:00Z", source_timeframe="15m")
    metadata = engine._source_metadata(Path("fixture.csv"), "15m", raw, derived, "2026-02-01T00:00:00Z")
    assert metadata["source_row_count"] == len(raw)
    assert metadata["derived_4h_bar_count"] == len(derived)
    assert metadata["derived_4h_last_timestamp"] == pd.Timestamp(derived.iloc[-1]["timestamp"]).isoformat()
    assert metadata["freshness_status"] == "STALE"
    candidate = engine.analyze_candidate(derived, "BTC", 30)
    stale = engine.apply_freshness_safety(candidate, metadata)
    assert stale["status"] == "STALE_DATA"
    assert stale["range_active"] is False
    assert stale["stale_data_warning"]
    flat = engine._flat(stale)
    assert morning_brief._consolidation_range_rows(pd.DataFrame([flat])) == []


@pytest.mark.archive
def test_loading_btc_source_does_not_mutate_operational_dataset():
    before = _digest(engine.BTC_OPERATIONAL_PATH)
    bars, metadata = engine.load_asset_4h("BTC", "2026-08-01T07:00:00Z")
    assert len(bars) > 0
    assert metadata["source_timeframe"] == "15m"
    assert _digest(engine.BTC_OPERATIONAL_PATH) == before


class ConsolidationRangeUnittestSmokeTests(unittest.TestCase):
    """Compatibility coverage for the project's requested unittest commands."""

    def test_stdlib_completion_delta_has_no_deprecation_warning(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            result = engine.completed_4h_bars(
                _quarter_hour_rows(16), "2026-01-01T04:00:00Z", source_timeframe="15m"
            )
        self.assertEqual(len(result), 1)

    @pytest.mark.archive
    def test_operational_btc_source_is_selected(self):
        bars, metadata = engine.load_asset_4h("BTC", "2026-08-01T07:00:00Z")
        self.assertGreater(len(bars), 0)
        self.assertEqual(metadata["source_path"], str(engine.BTC_OPERATIONAL_PATH))
        self.assertEqual(metadata["source_timeframe"], "15m")

    def test_exact_aggregation_and_incomplete_rejection(self):
        result = engine.completed_4h_bars(
            _quarter_hour_rows(20), "2026-01-01T08:00:00Z", source_timeframe="15m"
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(int(result.iloc[0]["source_count"]), 16)

    def test_stale_safety_status(self):
        candidate = {"status": "VALID_RANGE", "range_active": True}
        source = {"freshness_status": "STALE", "data_age_hours": 30.0, "stale_threshold_hours": 24.0}
        result = engine.apply_freshness_safety(candidate, source)
        self.assertEqual(result["status"], "STALE_DATA")
        self.assertFalse(result["range_active"])
