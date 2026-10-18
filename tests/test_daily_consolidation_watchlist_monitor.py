from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import daily_consolidation_watchlist_monitor as daily
import morning_brief
import weekly_intraday_market_backfill as backfill


def hourly(count=12, start="2026-08-02T12:00:00Z", price=.01833):
    timestamps = pd.date_range(start, periods=count, freq="1h", tz="UTC")
    return pd.DataFrame({
        "timestamp": timestamps, "open": price, "high": price * 1.01,
        "low": price * .99, "close": price, "volume": 10.0, "trades": 1,
    })


def selected(asset="NIGHT", pair="NIGHTUSD"):
    return {
        "asset": asset, "kraken_pair": pair, "rank": 1,
        "range_low": .01765, "range_high": .019351, "midpoint": .0185005,
        "watchlist_expiry_date": "2026-08-08",
    }


def test_refresh_calls_only_unique_weekly_pairs(monkeypatch, tmp_path):
    monkeypatch.setattr(daily, "INTRADAY_DIR", tmp_path)
    calls = []

    def updater(pair, cutoff):
        calls.append(pair)
        return hourly(), {"freshness_status": "FRESH"}

    rows = [selected(), selected("NIGHT-DUP", "NIGHTUSD"), selected("INJ", "INJUSD")]
    result = daily.refresh_selected_pairs(rows, "2026-08-03T00:30:00Z", updater)
    assert calls == ["INJUSD", "NIGHTUSD"]
    assert set(result) == {"INJUSD", "NIGHTUSD"}


def test_refresh_failure_preserves_file_and_suppresses_old_current_price(monkeypatch, tmp_path):
    monkeypatch.setattr(daily, "INTRADAY_DIR", tmp_path)
    path = tmp_path / "NIGHTUSD_1H.csv"
    old = hourly(8, "2026-08-01T00:00:00Z")
    path.write_text(old.to_csv(index=False))
    before = path.read_bytes()

    def failure(pair, cutoff):
        raise RuntimeError("Kraken unavailable")

    refresh = daily.refresh_selected_pairs([selected()], "2026-08-03T00:30:00Z", failure)["NIGHTUSD"]
    row = daily.monitor_row(selected(), refresh["bars"], "2026-08-03T00:30:00Z", refresh)
    assert path.read_bytes() == before
    assert row["freshness_status"] == "REFRESH_FAILED_STALE"
    assert row["current_price"] is None and row["position_pct"] is None
    assert row["refresh_failure_reason"] == "Kraken unavailable"


def test_completed_hour_and_frozen_boundaries():
    raw = hourly(13, "2026-08-02T12:00:00Z")
    clean, quality = backfill.merge_incremental(pd.DataFrame(), raw, "2026-08-03T00:30:00Z")
    assert len(clean) == 12 and quality["incomplete_bars_rejected"] == 1
    item = selected()
    row = daily.monitor_row(item, clean, "2026-08-03T00:30:00Z")
    assert row["range_low"] == item["range_low"]
    assert row["range_high"] == item["range_high"]


def test_below_range_monitor_nulls_risk_reward(monkeypatch):
    raw = hourly(16, "2026-08-02T08:00:00Z", price=.01700)
    monkeypatch.setattr(daily, "breakout_events", lambda *args, **kwargs: {
        "confirmed_above": [], "confirmed_below": [], "false_above": [],
        "false_below": [], "events": [],
    })
    row = daily.monitor_row(selected(), raw, "2026-08-03T00:30:00Z")
    assert row["status"] == "BELOW_RANGE_PENDING_RECOVERY"
    assert row["range_still_valid"] is False
    assert row["downside_to_invalidation_pct"] is None
    assert row["risk_reward_to_midpoint"] is None
    assert row["risk_reward_to_high"] is None
    assert row["recovery_condition"] == "CLOSE_AT_OR_ABOVE_RANGE_LOW"
    assert row["invalidation_reason"] == "CURRENT_PRICE_BELOW_RANGE_LOW_WITHOUT_FALSE_BREAKDOWN_RECOVERY"


def test_nan_and_adaptive_night_formatting():
    assert morning_brief._readable(float("nan"), "not invalidated") == "not invalidated"
    assert morning_brief._fmt_num(.01765) == "0.017650"
    assert morning_brief._fmt_num(.019351) == "0.019351"
    assert morning_brief._fmt_num(.0185005) == "0.018500"
    assert "nan" not in morning_brief._readable(None).lower()
