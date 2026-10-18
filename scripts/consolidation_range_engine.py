from __future__ import annotations

import argparse
import json
import math
import os
from datetime import timedelta
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd

from lib.universe import active_assets, report_dir


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "DATASETS" / "market_raw"
BTC_OPERATIONAL_PATH = ROOT / "DATASETS" / "BTC_4H_DONCHIAN_V1" / "BTCUSD_15m_operational.csv"
DISCLAIMER = ["RESEARCH_ONLY", "NOT_A_BUY_SIGNAL", "NOT_A_SELL_SIGNAL", "LIVE_NOT_AUTHORIZED"]
BAR_HOURS = 4
MIN_WINDOW = 30
MAX_WINDOW = 90
FRESHNESS_THRESHOLD_HOURS = float(os.environ.get("CONSOLIDATION_FRESH_HOURS", "8"))
STALE_THRESHOLD_HOURS = float(os.environ.get("CONSOLIDATION_STALE_HOURS", "24"))


@dataclass(frozen=True)
class BoundaryEvent:
    index: int
    timestamp: str


def completed_4h_bars(df: pd.DataFrame, as_of: pd.Timestamp | str | None = None,
                      source_timeframe: str | None = None) -> pd.DataFrame:
    """Aggregate complete source candles into complete 4H candles, without filling gaps."""
    required = {"timestamp", "open", "high", "low", "close"}
    if not required.issubset(df.columns):
        raise ValueError(f"OHLC data missing columns: {sorted(required - set(df.columns))}")
    work = df.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], utc=True, errors="coerce")
    for col in ("open", "high", "low", "close", "volume"):
        if col in work:
            work[col] = pd.to_numeric(work[col], errors="coerce")
    work = work.dropna(subset=["timestamp", "open", "high", "low", "close"])
    work = work.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    if work.empty:
        return work
    cutoff = pd.to_datetime(pd.Timestamp.now(tz="UTC") if as_of is None else as_of, utc=True)
    work = work[work["timestamp"] < cutoff]
    work["bucket"] = pd.to_datetime(work["timestamp"].dt.floor("4h"), utc=True)
    expected_by_timeframe = {"15m": 16, "1H": 4, "4H": 1}
    source_step = work["timestamp"].diff().dropna().median()
    source_hours = source_step.total_seconds() / 3600 if pd.notna(source_step) else 4.0
    expected = expected_by_timeframe.get(source_timeframe or "", max(1, int(round(BAR_HOURS / source_hours))))
    aggregations: dict[str, Any] = {"open": "first", "high": "max", "low": "min", "close": "last", "timestamp": "count"}
    if "volume" in work:
        aggregations["volume"] = "sum"
    out = work.groupby("bucket", sort=True).agg(aggregations).rename(columns={"timestamp": "source_count"}).reset_index()
    out["bucket"] = pd.to_datetime(out["bucket"], utc=True)
    completion_delta = timedelta(hours=4)
    out = out[(out["bucket"] + completion_delta <= cutoff) & (out["source_count"] == expected)]
    return out.rename(columns={"bucket": "timestamp"}).reset_index(drop=True)


def _source_metadata(path: Path, timeframe: str, raw: pd.DataFrame, derived: pd.DataFrame,
                     as_of: pd.Timestamp | str | None) -> dict[str, Any]:
    generated = pd.to_datetime(pd.Timestamp.now(tz="UTC") if as_of is None else as_of, utc=True)
    raw_ts = pd.to_datetime(raw["timestamp"], utc=True, errors="coerce").dropna()
    derived_ts = pd.to_datetime(derived["timestamp"], utc=True, errors="coerce").dropna() if not derived.empty else pd.Series(dtype="datetime64[ns, UTC]")
    latest = derived_ts.iloc[-1] if len(derived_ts) else None
    age = None if latest is None else max(0.0, (generated - latest).total_seconds() / 3600)
    freshness = "UNAVAILABLE" if age is None else "FRESH" if age <= FRESHNESS_THRESHOLD_HOURS else "DELAYED" if age <= STALE_THRESHOLD_HOURS else "STALE"
    raw_buckets = raw_ts.dt.floor("4h").nunique()
    return {
        "source_path": str(path), "source_timeframe": timeframe, "source_row_count": int(len(raw)),
        "source_first_timestamp": None if raw_ts.empty else raw_ts.iloc[0].isoformat(),
        "source_last_timestamp": None if raw_ts.empty else raw_ts.iloc[-1].isoformat(),
        "derived_4h_first_timestamp": None if derived_ts.empty else derived_ts.iloc[0].isoformat(),
        "derived_4h_last_timestamp": None if derived_ts.empty else derived_ts.iloc[-1].isoformat(),
        "derived_4h_bar_count": int(len(derived)),
        "incomplete_4h_bucket_count": max(0, int(raw_buckets) - int(len(derived))),
        "data_age_hours": age, "freshness_threshold_hours": FRESHNESS_THRESHOLD_HOURS,
        "stale_threshold_hours": STALE_THRESHOLD_HOURS, "freshness_status": freshness,
    }


def atr14(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [(df["high"] - df["low"]), (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(14, min_periods=14).mean()


def boundary_events(df: pd.DataFrame, boundary: float, tolerance: pd.Series, side: str) -> list[BoundaryEvent]:
    in_zone = df["low"].le(boundary + tolerance) if side == "lower" else df["high"].ge(boundary - tolerance)
    # A new event begins only after a completed candle has left that boundary zone.
    starts = in_zone & ~in_zone.shift(1, fill_value=False)
    return [BoundaryEvent(int(i), pd.Timestamp(df.loc[i, "timestamp"]).isoformat()) for i in df.index[starts]]


def breakout_events(df: pd.DataFrame, low: float, high: float, tolerance: pd.Series) -> dict[str, Any]:
    """Classify each directional excursion exactly once, with auditable IDs."""
    close = df["close"]
    events: list[dict[str, Any]] = []
    for direction, crossed, inside, confirmed in (
        ("ABOVE", df["high"] > high, close <= high, close > high + tolerance),
        ("BELOW", df["low"] < low, close >= low, close < low - tolerance),
    ):
        starts = list(df.index[crossed & ~crossed.shift(1, fill_value=False)])
        for ordinal, start in enumerate(starts, 1):
            excursion_end = int(start)
            while excursion_end < int(df.index[-1]) and bool(crossed.loc[excursion_end + 1]):
                excursion_end += 1
            confirmation_index = None
            confirmation_start_index = None
            for i in range(int(start), excursion_end):
                if bool(confirmed.loc[i]) and bool(confirmed.loc[i + 1]):
                    confirmation_start_index = i
                    confirmation_index = i + 1
                    break
            returned = next((i for i in range(int(start), min(int(start) + 3, int(df.index[-1])) + 1) if bool(inside.loc[i])), None)
            if confirmation_index is not None:
                classification = f"BREAK{'' if direction == 'ABOVE' else 'DOWN'}OUT_CONFIRMED" if direction == "ABOVE" else "BREAKDOWN_CONFIRMED"
                # Keep the public spelling unambiguous.
                classification = "BREAKOUT_CONFIRMED" if direction == "ABOVE" else "BREAKDOWN_CONFIRMED"
            elif returned is not None:
                classification = "FALSE_BREAKOUT_ABOVE" if direction == "ABOVE" else "FALSE_BREAKDOWN_BELOW"
            else:
                classification = "UNRESOLVED_BREAK_EVENT"
            event = {
                "event_id": f"{direction}-{ordinal:03d}", "direction": direction,
                "classification": classification, "event_index": int(start),
                "event_timestamp": pd.Timestamp(df.loc[start, "timestamp"]).isoformat(),
                "start_timestamp": pd.Timestamp(df.loc[start, "timestamp"]).isoformat(),
                "end_index": excursion_end,
                "end_timestamp": pd.Timestamp(df.loc[excursion_end, "timestamp"]).isoformat(),
                "confirmation_index": confirmation_index,
                "confirmation_start_index": confirmation_start_index,
                "first_confirmed_close_timestamp": None if confirmation_start_index is None else pd.Timestamp(df.loc[confirmation_start_index, "timestamp"]).isoformat(),
                "confirmation_timestamp": None if confirmation_index is None else pd.Timestamp(df.loc[confirmation_index, "timestamp"]).isoformat(),
                "return_inside_index": returned,
                "return_inside_timestamp": None if returned is None else pd.Timestamp(df.loc[returned, "timestamp"]).isoformat(),
            }
            events.append(event)
    classes = {
        "false_above": "FALSE_BREAKOUT_ABOVE", "false_below": "FALSE_BREAKDOWN_BELOW",
        "confirmed_above": "BREAKOUT_CONFIRMED", "confirmed_below": "BREAKDOWN_CONFIRMED",
        "unresolved": "UNRESOLVED_BREAK_EVENT",
    }
    result: dict[str, Any] = {key: [e["event_index"] for e in events if e["classification"] == value] for key, value in classes.items()}
    result["events"] = sorted(events, key=lambda e: (e["event_index"], e["direction"]))
    return result


def traversal_durations(starts: list[BoundaryEvent], ends: list[BoundaryEvent], interruptions: list[int]) -> list[int]:
    durations: list[int] = []
    last_end = -1
    for start in starts:
        if start.index <= last_end:
            continue
        end = next((event for event in ends if event.index > start.index), None)
        if end is None:
            continue
        if any(start.index < item <= end.index for item in interruptions):
            continue
        durations.append(end.index - start.index)
        last_end = end.index
    return durations


def _timing(values: list[int], events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "count": len(values),
        "average_bars": round(sum(values) / len(values), 4) if values else None,
        "median_bars": round(float(median(values)), 4) if values else None,
        "average_hours": round(BAR_HOURS * sum(values) / len(values), 4) if values else None,
        "median_hours": round(BAR_HOURS * float(median(values)), 4) if values else None,
        "events": events or [],
    }


def position_pct(close: float, low: float, high: float) -> float:
    return (close - low) / (high - low) * 100


def _location(position: float) -> str:
    if position < 0:
        return "BELOW_RANGE"
    if position <= 20:
        return "NEAR_RANGE_LOW"
    if position <= 40:
        return "LOWER_HALF"
    if position <= 60:
        return "MID_RANGE"
    if position <= 80:
        return "UPPER_HALF"
    if position <= 100:
        return "NEAR_RANGE_HIGH"
    return "ABOVE_RANGE"


def _intervals(events: list[BoundaryEvent]) -> dict[str, Any]:
    gaps = [b.index - a.index for a, b in zip(events, events[1:])]
    avg = round(sum(gaps) / len(gaps), 4) if gaps else None
    med = round(float(median(gaps)), 4) if gaps else None
    return {"count": len(gaps), "average_bars": avg, "median_bars": med,
            "average_hours": None if avg is None else avg * BAR_HOURS,
            "median_hours": None if med is None else med * BAR_HOURS}


def _traversal_event_details(starts: list[BoundaryEvent], ends: list[BoundaryEvent], interruptions: list[int], direction: str) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    last_end = -1
    for start in starts:
        if start.index <= last_end:
            continue
        end = next((event for event in ends if event.index > start.index), None)
        if end is None or any(start.index < item <= end.index for item in interruptions):
            continue
        bars = end.index - start.index
        details.append({"direction": direction, "start_timestamp": start.timestamp,
                        "end_timestamp": end.timestamp, "bars": bars, "hours": bars * BAR_HOURS})
        last_end = end.index
    return details


def timeline_metrics(included: pd.DataFrame) -> dict[str, Any]:
    """Return inclusive bar duration and timestamp-based calendar duration invariants."""
    if included.empty:
        return {"duration_bars": 0, "duration_trading_hours": 0, "duration_calendar_hours": 0.0,
                "duration_calendar_days": 0.0, "missing_expected_4h_bars": 0,
                "continuity_status": "DATA_INCONSISTENT", "duration_reconciled": False}
    timestamps = pd.to_datetime(included["timestamp"], utc=True)
    start_ts, end_ts = timestamps.iloc[0], timestamps.iloc[-1]
    bars = int(len(timestamps))
    calendar_hours = (end_ts - start_ts).total_seconds() / 3600
    expected = int(calendar_hours // BAR_HOURS) + 1 if calendar_hours >= 0 else 0
    missing = max(0, expected - bars)
    aligned = bool(((timestamps.diff().dropna().dt.total_seconds() / 3600) >= BAR_HOURS).all())
    reconciled = bool(end_ts >= start_ts and bars >= 1 and bars * BAR_HOURS == bars * 4 and aligned
                      and start_ts == pd.Timestamp(included.iloc[0]["timestamp"])
                      and end_ts == pd.Timestamp(included.iloc[-1]["timestamp"]))
    return {"duration_bars": bars, "duration_trading_hours": bars * BAR_HOURS,
            "duration_calendar_hours": calendar_hours, "duration_calendar_days": calendar_hours / 24,
            "missing_expected_4h_bars": missing,
            "continuity_status": "CONTINUOUS" if reconciled and missing == 0 else "GAPS_PRESENT" if reconciled else "DATA_INCONSISTENT",
            "duration_reconciled": reconciled}


def analyze_candidate(df: pd.DataFrame, asset: str, window: int) -> dict[str, Any]:
    work = df.tail(window).copy().reset_index(drop=True)
    work["atr14"] = atr14(df).tail(window).reset_index(drop=True)
    work = work.dropna(subset=["atr14"]).reset_index(drop=True)
    if len(work) < MIN_WINDOW:
        raise ValueError("insufficient bars after ATR14")
    # Robust quantile boundaries keep isolated wicks from defining the range.
    low = float(work["low"].quantile(0.10))
    high = float(work["high"].quantile(0.90))
    if not math.isfinite(low) or not math.isfinite(high) or high <= low:
        raise ValueError("invalid candidate width")
    tolerance = 0.25 * work["atr14"]
    preliminary_breaks = breakout_events(work, low, high, tolerance)
    confirmed_events = [e for e in preliminary_breaks["events"] if e["classification"] in {"BREAKOUT_CONFIRMED", "BREAKDOWN_CONFIRMED"}]
    first_confirmed = min(confirmed_events, key=lambda e: e["event_index"]) if confirmed_events else None
    range_end_index = max(0, first_confirmed["confirmation_start_index"] - 1) if first_confirmed else len(work) - 1
    range_work = work.iloc[: range_end_index + 1].copy().reset_index(drop=True)
    range_tolerance = 0.25 * range_work["atr14"]
    lower = boundary_events(range_work, low, range_tolerance, "lower")
    upper = boundary_events(range_work, high, range_tolerance, "upper")
    breaks = preliminary_breaks
    lth_details = _traversal_event_details(lower, upper, breaks["confirmed_below"], "LOW_TO_HIGH")
    htl_details = _traversal_event_details(upper, lower, breaks["confirmed_above"], "HIGH_TO_LOW")
    lth = [event["bars"] for event in lth_details]
    htl = [event["bars"] for event in htl_details]
    inside_pct = float(range_work["close"].between(low, high).mean() * 100)
    x = pd.Series(range(len(range_work)), dtype=float)
    slope = float(range_work["close"].reset_index(drop=True).cov(x) / x.var()) if len(range_work) >= 2 and x.var() else 0.0
    trend_normalization_denominator = high - low
    normalized_slope = abs(slope * max(1, len(range_work) - 1)) / trend_normalization_denominator
    trend_ratio = normalized_slope
    thirds = [part for part in (range_work.iloc[i : i + max(1, len(range_work) // 3)] for i in range(0, len(range_work), max(1, len(range_work) // 3))) if len(part) >= 5]
    widths = [float(part["high"].quantile(.9) - part["low"].quantile(.1)) for part in thirds]
    width_cv = float(pd.Series(widths).std(ddof=0) / pd.Series(widths).mean()) if widths and pd.Series(widths).mean() else 1.0
    components = {
        "lower_tests": min(len(lower) / 4, 1) * 12,
        "upper_tests": min(len(upper) / 4, 1) * 12,
        "boundary_symmetry": (1 - abs(len(lower) - len(upper)) / max(len(lower), len(upper), 1)) * 10,
        "closes_inside": min(inside_pct / 90, 1) * 18,
        "trend_flatness": max(0, 1 - trend_ratio / .5) * 14,
        "width_stability": max(0, 1 - width_cv / .5) * 12,
        "traversals": min((len(lth) + len(htl)) / 4, 1) * 10,
        "duration": min(len(range_work) / 90, 1) * 12,
        "false_breakout_penalty": -min(len(breaks["false_above"]) + len(breaks["false_below"]), 5) * 2,
    }
    components = {key: round(value, 4) for key, value in components.items()}
    quality = round(max(0, min(100, sum(components.values()))), 2)
    conditions = {
        "lower_boundary_reactions": len(lower) >= 2,
        "upper_boundary_reactions": len(upper) >= 2,
        "close_containment": inside_pct >= 75,
        "trend_flatness": trend_ratio <= .5,
        "width_stability": width_cv <= .5,
        "no_confirmed_directional_break": not confirmed_events,
    }
    valid = all(conditions.values())
    latest_available_price = float(work.iloc[-1]["close"])
    pos = position_pct(latest_available_price, low, high)
    location = _location(pos)
    recovery_condition = None
    invalidation_reason = None
    status = location
    if first_confirmed:
        status = first_confirmed["classification"]
    elif pos > 100 and any(i >= len(work) - 3 for i in breaks["false_above"]):
        status = "FALSE_BREAKOUT_ABOVE"
    elif pos < 0 and any(i >= len(work) - 3 for i in breaks["false_below"]):
        status = "FALSE_BREAKDOWN_RECOVERY"
        recovery_condition = "CLOSE_AT_OR_ABOVE_RANGE_LOW"
    elif pos < 0:
        status = "BELOW_RANGE_PENDING_RECOVERY"
        valid = False
        recovery_condition = "CLOSE_AT_OR_ABOVE_RANGE_LOW"
        invalidation_reason = "CURRENT_PRICE_BELOW_RANGE_LOW_WITHOUT_FALSE_BREAKDOWN_RECOVERY"
    elif not valid:
        status = "RANGE_INVALIDATED"
        invalidation_reason = "RANGE_QUALITY_CONDITIONS_FAILED"
    start_ts = pd.Timestamp(range_work.iloc[0]["timestamp"])
    end_ts = pd.Timestamp(range_work.iloc[-1]["timestamp"])
    current_ts = pd.Timestamp(work.iloc[-1]["timestamp"])
    timeline = timeline_metrics(range_work)
    duration_bars = timeline["duration_bars"]
    calendar_hours = timeline["duration_calendar_hours"]
    reconciled = timeline["duration_reconciled"]
    if not reconciled:
        status = "DATA_INCONSISTENT"
        valid = False
        invalidation_reason = "RANGE_TIMELINE_DATA_INCONSISTENT"
    if first_confirmed:
        valid = False
        invalidation_reason = first_confirmed["classification"]
    quality_band = "LOW" if quality < 40 else "WEAK" if quality < 60 else "MODERATE" if quality < 75 else "STRONG" if quality < 90 else "VERY_STRONG"
    recent_false = sum(i >= len(work) - 6 for i in breaks["false_above"] + breaks["false_below"])
    risk_points = (20 if pos < 10 or pos > 90 else 0) + min(30, recent_false * 15) + max(0, 60 - quality)
    if status in {"BREAKOUT_CONFIRMED", "BREAKDOWN_CONFIRMED", "RANGE_INVALIDATED"}:
        risk_points = max(risk_points, 50)
    risk = "HIGH" if risk_points >= 50 else "MEDIUM" if risk_points >= 25 else "LOW"
    all_traversals = lth + htl
    lower_intervals = _intervals(lower)
    upper_intervals = _intervals(upper)
    return {
        "asset": asset, "range_state": "VALID_RANGE" if valid else "WEAK_RANGE", "structural_state": "VALID_RANGE" if valid else "WEAK_RANGE", "status": status,
        "range_valid": valid, "recovery_condition": recovery_condition,
        "invalidation_reason": invalidation_reason,
        "is_valid_horizontal_consolidation": valid, "range_active": valid and first_confirmed is None,
        "quality_band": quality_band,
        "passed_quality_conditions": [name + "_passed" for name, passed in conditions.items() if passed],
        "failed_quality_conditions": [name + "_failed" for name, passed in conditions.items() if not passed],
        "range_start_timestamp": start_ts.isoformat(), "range_end_timestamp": end_ts.isoformat(),
        "range_start": start_ts.isoformat(), "range_end": end_ts.isoformat(),
        "invalidation_timestamp": None if valid else (first_confirmed["confirmation_timestamp"] if first_confirmed else current_ts.isoformat()),
        "breakout_event_timestamp": None if first_confirmed is None else first_confirmed["first_confirmed_close_timestamp"],
        "breakout_confirmation_timestamp": None if first_confirmed is None else first_confirmed["confirmation_timestamp"],
        "breakout_direction": None if first_confirmed is None else first_confirmed["direction"],
        "post_breakout_reference_timestamp": current_ts.isoformat() if first_confirmed else None,
        "post_breakout_reference_price": latest_available_price if first_confirmed else None,
        "latest_available_market_timestamp": current_ts.isoformat(),
        "latest_available_market_price": latest_available_price,
        "duration_bars": duration_bars, "duration_trading_hours": timeline["duration_trading_hours"],
        "duration_calendar_hours": calendar_hours, "duration_calendar_days": timeline["duration_calendar_days"],
        "duration_hours": timeline["duration_trading_hours"], "missing_expected_4h_bars": timeline["missing_expected_4h_bars"],
        "continuity_status": timeline["continuity_status"],
        "duration_reconciled": reconciled, "range_low": low, "range_high": high,
        "midpoint": (low + high) / 2, "width_price": high - low, "width_pct": (high - low) / ((high + low) / 2) * 100,
        "position_pct": pos, "position_clipped_pct": min(100, max(0, pos)),
        "position_zone": location, "current_location": location,
        "lower_boundary_tests": len(lower), "upper_boundary_tests": len(upper),
        "false_breakouts_above": len(breaks["false_above"]), "false_breakdowns_below": len(breaks["false_below"]),
        "confirmed_breakouts": len(breaks["confirmed_above"]), "confirmed_breakdowns": len(breaks["confirmed_below"]),
        "low_to_high": _timing(lth, lth_details), "high_to_low": _timing(htl, htl_details),
        "full_traversal": _timing(all_traversals, lth_details + htl_details),
        "lower_boundary_events": [asdict(event) for event in lower], "upper_boundary_events": [asdict(event) for event in upper],
        "lower_test_intervals": lower_intervals, "upper_test_intervals": upper_intervals,
        "average_bars_between_lower_tests": lower_intervals["average_bars"], "average_hours_between_lower_tests": lower_intervals["average_hours"],
        "average_bars_between_upper_tests": upper_intervals["average_bars"], "average_hours_between_upper_tests": upper_intervals["average_hours"],
        "closes_inside_pct": inside_pct, "trend_ratio": trend_ratio, "width_stability_cv": width_cv,
        "trend_slope_value": slope, "trend_slope_units": "quote_currency_per_4h_bar",
        "trend_normalization_denominator": trend_normalization_denominator,
        "trend_normalization_denominator_units": "quote_currency_range_width",
        "trend_normalized_slope": normalized_slope,
        "trend_normalized_slope_units": "range_widths_over_included_candidate_duration",
        "trend_flatness_threshold": .5, "trend_flatness_threshold_units": "range_widths_over_included_candidate_duration",
        "trend_flatness_comparison": f"{normalized_slope:.12g} <= 0.5",
        "trend_flatness_pass": conditions["trend_flatness"],
        "trend_flatness_indicator": "absolute OLS close slope over included range, normalized by range width",
        "atr14_latest": float(work.iloc[-1]["atr14"]), "boundary_tolerance_latest": float(tolerance.iloc[-1]),
        "range_quality": quality, "quality_components": components, "breakout_risk": risk,
        "break_events": breaks["events"],
    }


def detect_range(df: pd.DataFrame, asset: str) -> dict[str, Any]:
    if len(df) < MIN_WINDOW + 14:
        raise ValueError(f"need at least {MIN_WINDOW + 14} completed 4H bars")
    candidates = [analyze_candidate(df, asset, window) for window in range(MIN_WINDOW, min(MAX_WINDOW, len(df) - 14) + 1)]
    # Prefer valid candidates, then the transparent score, then longer duration.
    return max(candidates, key=lambda row: (row["range_state"] == "VALID_RANGE", row["range_quality"], row["duration_bars"]))


def _read_json_ohlc(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text())
    key = next(key for key in payload if key != "last")
    rows = payload[key]
    raw = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "vwap", "volume", "trades"])
    raw["timestamp"] = pd.to_datetime(pd.to_numeric(raw["time"]), unit="s", utc=True)
    return raw


def _read_operational_15m(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if not required.issubset(raw.columns):
        raise ValueError(f"operational OHLC missing columns: {sorted(required - set(raw.columns))}")
    raw["timestamp"] = pd.to_datetime(pd.to_numeric(raw["timestamp"], errors="coerce"), unit="s", utc=True)
    return raw


def load_asset_4h(asset: str, as_of: pd.Timestamp | str | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Select the freshest valid native intraday source without using daily data."""
    choices: list[tuple[int, pd.DataFrame, dict[str, Any]]] = []
    specifications: list[tuple[Path, str, int]] = []
    if asset == "BTC":
        specifications.append((BTC_OPERATIONAL_PATH, "15m", 0))
        specifications.append((RAW_DIR / "BTCUSD_1H.json", "1H", 1))
    else:
        specifications.append((RAW_DIR / f"{asset}USD_1H.json", "1H", 0))
        specifications.append((RAW_DIR / f"{asset}USD_4H.json", "4H", 1))
    errors: list[str] = []
    for path, timeframe, precedence in specifications:
        if not path.exists():
            errors.append(f"missing {path.name}")
            continue
        try:
            raw = _read_operational_15m(path) if timeframe == "15m" else _read_json_ohlc(path)
            derived = completed_4h_bars(raw, as_of=as_of, source_timeframe=timeframe)
            metadata = _source_metadata(path, timeframe, raw, derived, as_of)
            if len(derived) < MIN_WINDOW + 14:
                errors.append(f"{path.name}: insufficient complete 4H bars ({len(derived)})")
                continue
            choices.append((precedence, derived, metadata))
        except (ValueError, KeyError, json.JSONDecodeError, pd.errors.ParserError) as exc:
            errors.append(f"{path.name}: {exc}")
    if not choices:
        raise FileNotFoundError("; ".join(errors) or "native intraday OHLC unavailable")
    # Newest completed 4H candle wins; configured precedence resolves equal timestamps.
    precedence, derived, metadata = max(
        choices, key=lambda item: (pd.Timestamp(item[1].iloc[-1]["timestamp"]), -item[0])
    )
    return derived, metadata


def apply_freshness_safety(candidate: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    result = {**candidate, **source}
    if source["freshness_status"] == "STALE":
        result["status"] = "STALE_DATA"
        result["range_active"] = False
        result["stale_data_warning"] = (
            f"Latest completed 4H candle is {source['data_age_hours']:.2f} hours old; "
            f"stale threshold is {source['stale_threshold_hours']:.2f} hours."
        )
    else:
        result["stale_data_warning"] = None
    return result


def _flat(row: dict[str, Any]) -> dict[str, Any]:
    result = {k: v for k, v in row.items() if not isinstance(v, dict)}
    for prefix in ("low_to_high", "high_to_low", "full_traversal"):
        result.update({f"{prefix}_{k}": v for k, v in row[prefix].items()})
    for key, value in row["quality_components"].items():
        result[f"quality_{key}"] = value
    return result


def write_reports(rows: list[dict[str, Any]], unavailable: list[dict[str, str]], date_text: str, output_dir: Path,
                  report_generated_at: str | None = None) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = report_generated_at or pd.Timestamp(f"{date_text}T00:00:00Z").isoformat()
    rows = [{**row, "report_generated_at": generated_at} for row in rows]
    base = output_dir / f"{date_text}_consolidation_ranges"
    flat = pd.DataFrame([_flat(row) for row in rows]).sort_values("asset") if rows else pd.DataFrame(columns=["asset", "status"])
    flat.to_csv(base.with_suffix(".csv"), index=False, float_format="%.8f")
    document = {"report_date": date_text, "report_generated_at": generated_at, "labels": DISCLAIMER, "timeframe": "4H", "candidates": sorted(rows, key=lambda r: r["asset"]), "unavailable_assets": sorted(unavailable, key=lambda r: r["asset"])}
    base.with_suffix(".json").write_text(json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n")
    lines = ["# Consolidation Range Engine V1", "", *(f"**{label}**  " for label in DISCLAIMER), "", "## Candidates", ""]
    if not rows:
        lines.append("No range candidates could be evaluated.")
    for row in sorted(rows, key=lambda r: r["asset"]):
        lines += [f"### {row['asset']} — {row['status']}", "", f"- Report generated at: {row['report_generated_at']}", f"- Source: {row.get('source_path', 'unspecified')} ({row.get('source_timeframe', 'unspecified')}, {row.get('source_row_count', 'n/a')} rows)", f"- Source coverage: {row.get('source_first_timestamp')} → {row.get('source_last_timestamp')}", f"- Derived 4H coverage: {row.get('derived_4h_first_timestamp')} → {row.get('derived_4h_last_timestamp')} ({row.get('derived_4h_bar_count', 'n/a')} bars; {row.get('incomplete_4h_bucket_count', 'n/a')} incomplete/rejected buckets)", f"- Freshness: {row.get('freshness_status', 'UNKNOWN')} (age {row.get('data_age_hours')}h; fresh ≤ {row.get('freshness_threshold_hours')}h; stale > {row.get('stale_threshold_hours')}h)", *(([f"- **STALE DATA WARNING:** {row['stale_data_warning']}"]) if row.get('stale_data_warning') else []), f"- Structural state: {row['structural_state']} (valid horizontal consolidation: {str(row['is_valid_horizontal_consolidation']).lower()})", f"- Quality: {row['range_quality']:.2f} ({row['quality_band']}); breakout risk: {row['breakout_risk']}", f"- Passed conditions: {', '.join(row['passed_quality_conditions']) or 'none'}", f"- Failed conditions: {', '.join(row['failed_quality_conditions']) or 'none'}", f"- Historical range start: {row['range_start_timestamp']}", f"- Historical range end: {row['range_end_timestamp']}", f"- Duration: {row['duration_bars']} completed 4H bars / {row['duration_trading_hours']} trading hours", f"- Calendar duration: {row['duration_calendar_hours']:.2f} hours / {row['duration_calendar_days']:.4f} days", f"- Continuity: {row['continuity_status']} ({row['missing_expected_4h_bars']} missing expected 4H bars)", f"- Invalidation / breakout confirmation: {row['invalidation_timestamp']} / {row['breakout_confirmation_timestamp']}", f"- Post-breakout reference: {row['post_breakout_reference_timestamp']} / {row['post_breakout_reference_price']}", f"- Latest available market observation: {row['latest_available_market_timestamp']} / {row['latest_available_market_price']:.8f}", f"- Low / high / midpoint: {row['range_low']:.8f} / {row['range_high']:.8f} / {row['midpoint']:.8f}", f"- Width: {row['width_price']:.8f} ({row['width_pct']:.2f}%)", f"- Latest available position: raw {row['position_pct']:.2f}%, clipped {row['position_clipped_pct']:.2f}%, {row['position_zone']}", f"- Tests lower / upper: {row['lower_boundary_tests']} / {row['upper_boundary_tests']}", f"- False above / below: {row['false_breakouts_above']} / {row['false_breakdowns_below']}", f"- Confirmed above / below: {row['confirmed_breakouts']} / {row['confirmed_breakdowns']}", f"- Traversals low→high / high→low: {row['low_to_high']['count']} / {row['high_to_low']['count']}", f"- Full traversal avg / median: {row['full_traversal']['average_bars']} / {row['full_traversal']['median_bars']} bars; {row['full_traversal']['average_hours']} / {row['full_traversal']['median_hours']} hours", f"- Lower test intervals: avg {row['lower_test_intervals']['average_bars']} bars, median {row['lower_test_intervals']['median_bars']} bars, n={row['lower_test_intervals']['count']}", f"- Upper test intervals: avg {row['upper_test_intervals']['average_bars']} bars, median {row['upper_test_intervals']['median_bars']} bars, n={row['upper_test_intervals']['count']}", f"- Trend raw slope: {row['trend_slope_value']:.8f} {row['trend_slope_units']}", f"- Trend normalization denominator: {row['trend_normalization_denominator']:.8f} {row['trend_normalization_denominator_units']}", f"- Trend normalized slope: {row['trend_normalized_slope']:.8f} {row['trend_normalized_slope_units']}", f"- Trend threshold: {row['trend_flatness_threshold']} {row['trend_flatness_threshold_units']}", f"- Trend comparison: {row['trend_flatness_comparison']} => {str(row['trend_flatness_pass']).lower()}", "- Quality contributions: " + ", ".join(f"{k}={v:+.2f}" for k, v in row["quality_components"].items()), ""]
    lines += ["## Unavailable assets", ""] + ([*(f"- {item['asset']}: {item['reason_unavailable']} | expected {item['expected_source_path']} | required {item['source_timeframe_required']} | latest {item['latest_available_timeframe']} | action: {item['action_required']}" for item in sorted(unavailable, key=lambda r: r["asset"]))] if unavailable else ["- None"])
    base.with_suffix(".md").write_text("\n".join(lines) + "\n")
    return base.with_suffix(".csv"), base.with_suffix(".md"), base.with_suffix(".json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only 4H consolidation range research engine")
    parser.add_argument("--date", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    parser.add_argument("--as-of", default=None, help="UTC cutoff; defaults to now")
    args = parser.parse_args()
    rows: list[dict[str, Any]] = []
    unavailable: list[dict[str, str]] = []
    for asset in active_assets():
        try:
            bars, source = load_asset_4h(asset, args.as_of)
            rows.append(apply_freshness_safety(detect_range(bars, asset), source))
        except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as exc:
            expected = str(BTC_OPERATIONAL_PATH if asset == "BTC" else RAW_DIR / f"{asset}USD_1H.json")
            daily_exists = (RAW_DIR / f"{asset}USD_D1.json").exists()
            unavailable.append({
                "asset": asset, "expected_source_path": expected,
                "source_path": expected, "source_timeframe": "15m" if asset == "BTC" else "1H or 4H",
                "source_row_count": 0, "source_first_timestamp": None, "source_last_timestamp": None,
                "derived_4h_first_timestamp": None, "derived_4h_last_timestamp": None,
                "report_generated_at": None, "data_age_hours": None,
                "freshness_threshold_hours": FRESHNESS_THRESHOLD_HOURS, "freshness_status": "UNAVAILABLE",
                "source_timeframe_required": "native completed 1H or 4H candles",
                "reason_unavailable": str(exc),
                "latest_available_timeframe": "1D" if daily_exists else "NONE",
                "can_be_analyzed": False,
                "action_required": "download native Kraken intraday history",
            })
    generated_at = pd.Timestamp.now(tz="UTC").isoformat()
    unavailable = [{**item, "report_generated_at": generated_at} for item in unavailable]
    paths = write_reports(rows, unavailable, args.date, report_dir(), report_generated_at=generated_at)
    print("Consolidation Range Engine V1 | " + " | ".join(DISCLAIMER))
    print(f"Candidates: {len(rows)}; unavailable: {len(unavailable)}")
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
