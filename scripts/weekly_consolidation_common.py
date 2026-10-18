from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import urllib.parse
import urllib.request
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_DIR = ROOT / "DATASETS" / "universe"
INTRADAY_DIR = ROOT / "DATASETS" / "market_intraday_weekly"
WEEKLY_REPORT_DIR = ROOT / "DAILY_REPORTS" / "WEEKLY_CONSOLIDATION"
WATCHLIST_DIR = ROOT / "WATCHLISTS"
CHECKPOINT_DIR = ROOT / "DATASETS" / "weekly_consolidation_checkpoints"
LABELS = ["RESEARCH_ONLY", "NOT_A_BUY_SIGNAL", "NOT_A_SELL_SIGNAL", "PAPER_NOT_AUTHORIZED", "LIVE_NOT_AUTHORIZED"]
STABLECOINS = {"USDT", "USDC", "DAI", "PYUSD", "EURT", "USDS", "FDUSD", "TUSD", "USDP", "GUSD", "USD1", "USDE", "USDD", "RLUSD", "FRAX"}
WRAPPED_PREFIXES = ("W", "ST")
QUOTE_ORDER = {"USD": 0, "USDT": 1, "EUR": 2}
DEFAULTS = {
    "min_quote_volume": 250_000.0, "max_spread_pct": 0.75,
    "min_1h_candles": 336, "preferred_1h_candles": 720,
    "fees_pct": 0.40, "slippage_pct": 0.20, "watchlist_quality": 60.0,
    "watchlist_net_return": 1.5, "fresh_hours": 8.0, "stale_hours": 24.0,
    "max_practical_range_pct": 15.0,
    "request_pause_seconds": float(os.environ.get("WEEKLY_SCAN_REQUEST_PAUSE", "1.0")),
}


def utc_timestamp(value: Any = None) -> pd.Timestamp:
    return pd.to_datetime(pd.Timestamp.now(tz="UTC") if value is None else value, utc=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path: Path, content: str, backup: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content)
    if backup and path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    os.replace(temporary, path)


def write_json(path: Path, payload: Any, backup: bool = True) -> None:
    atomic_write(path, json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", backup)


def get_json(url: str, params: dict[str, Any] | None = None, retries: int = 3,
             pause: float | None = None, opener=urllib.request.urlopen) -> Any:
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    delay = DEFAULTS["request_pause_seconds"] if pause is None else pause
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "kraken-ai-trading-research/1.0"})
            with opener(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if delay > 0:
                time.sleep(delay)
            return payload
        except Exception as exc:  # public endpoint failures are reported, never hidden
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(delay * (2 ** attempt))
    raise RuntimeError(f"public API request failed after {retries} attempts: {last_error}")


def normalize_symbol(value: str) -> str:
    symbol = str(value).upper()
    aliases = {"XBT": "BTC", "XDG": "DOGE"}
    while len(symbol) > 3 and symbol[0] in {"X", "Z"}:
        symbol = symbol[1:]
    return aliases.get(symbol, symbol)


def exclusion_reason(coin: dict[str, Any]) -> str | None:
    symbol = str(coin.get("symbol", "")).upper()
    name = str(coin.get("name", "")).lower()
    coin_id = str(coin.get("id", "")).lower()
    if symbol in STABLECOINS or any(term in name for term in ("stablecoin", "usd coin", "dollar", "tether")):
        return "STABLECOIN_OR_FIAT_PEG"
    if "wrapped" in name or coin_id.startswith("wrapped-") or (symbol.startswith("W") and len(symbol) > 3):
        return "WRAPPED_DUPLICATE"
    if any(term in name for term in ("2x", "3x", "bull token", "bear token", "leveraged", "index token")):
        return "LEVERAGED_OR_SYNTHETIC"
    return None


def freshness(last_timestamp: Any, as_of: Any) -> tuple[float | None, str]:
    if last_timestamp is None or pd.isna(last_timestamp):
        return None, "UNAVAILABLE"
    age = max(0.0, (utc_timestamp(as_of) - utc_timestamp(last_timestamp)).total_seconds() / 3600)
    return age, "FRESH" if age <= DEFAULTS["fresh_hours"] else "DELAYED" if age <= DEFAULTS["stale_hours"] else "STALE"


def validate_hourly(df: pd.DataFrame, as_of: Any) -> tuple[pd.DataFrame, dict[str, Any]]:
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        raise ValueError(f"missing OHLCV columns: {sorted(required - set(df.columns))}")
    work = df.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], utc=True, errors="coerce")
    for col in ("open", "high", "low", "close", "volume", "trades"):
        if col in work:
            work[col] = pd.to_numeric(work[col], errors="coerce")
    duplicate_count = int(work["timestamp"].duplicated().sum())
    invalid = work[list(required)].isna().any(axis=1)
    invalid |= (work[["open", "high", "low", "close"]] <= 0).any(axis=1)
    ohlc_bad = (work["high"] < work[["open", "close", "low"]].max(axis=1)) | (work["low"] > work[["open", "close", "high"]].min(axis=1))
    negative_volume = work["volume"] < 0
    cutoff = utc_timestamp(as_of)
    incomplete = work["timestamp"] + timedelta(hours=1) > cutoff
    clean = work[~invalid & ~ohlc_bad & ~negative_volume & ~incomplete].sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    diffs = clean["timestamp"].diff().dropna().dt.total_seconds().div(3600)
    missing = int(sum(max(0, int(gap) - 1) for gap in diffs))
    age, fresh = freshness(clean.iloc[-1]["timestamp"] if len(clean) else None, cutoff)
    return clean.reset_index(drop=True), {
        "duplicate_count": duplicate_count, "missing_expected_1h_bars": missing,
        "longest_gap_hours": float(diffs.max()) if len(diffs) else 0.0,
        "incomplete_bars_rejected": int(incomplete.sum()), "ohlc_anomalies": int(ohlc_bad.sum()),
        "negative_volume_rows": int(negative_volume.sum()), "freshness_age_hours": age,
        "freshness_status": "DATA_INCONSISTENT" if invalid.any() or ohlc_bad.any() or negative_volume.any() else fresh,
    }


def opportunity_metrics(row: dict[str, Any], fees_pct: float = .40, slippage_pct: float = .20) -> dict[str, Any]:
    gross = (row["range_high"] / row["range_low"] - 1) * 100
    net = gross - fees_pct - slippage_pct
    midpoint = (row["midpoint"] / row["range_low"] - 1) * 100
    low_hours = row["low_to_high"]["average_hours"]
    high_hours = row["high_to_low"]["average_hours"]
    cycle = None if low_hours is None or high_hours is None else low_hours + high_hours
    cycles = None if not cycle else 720 / cycle
    days = max(float(row["duration_calendar_days"]), 1 / 6)
    traversals = row["low_to_high"]["count"] + row["high_to_low"]["count"]
    return {
        "gross_range_return_pct": gross, "estimated_fees_pct": fees_pct,
        "estimated_slippage_pct": slippage_pct, "estimated_total_friction_pct": fees_pct + slippage_pct,
        "estimated_net_range_return_pct": net, "lower_to_midpoint_return_pct": midpoint,
        "average_full_cycle_hours": cycle, "estimated_cycles_per_30d": cycles,
        "cycle_history_status": "SUFFICIENT" if cycle else "INSUFFICIENT_CYCLE_HISTORY",
        "completed_traversals_per_30d": traversals * 30 / days,
        "lower_events_per_30d": row["lower_boundary_tests"] * 30 / days,
        "upper_events_per_30d": row["upper_boundary_tests"] * 30 / days,
        "range_efficiency_net_pct_per_day": None if not cycle else net / (cycle / 24),
    }


def risk_flags(row: dict[str, Any], liquidity_pass: bool = True, spread_pass: bool = True) -> list[str]:
    flags: list[str] = []
    if not liquidity_pass: flags.append("LOW_LIQUIDITY")
    if not spread_pass: flags.append("WIDE_SPREAD")
    if row.get("freshness_status") != "FRESH": flags.append("STALE_DATA")
    if row.get("cycle_history_status") != "SUFFICIENT": flags.append("INSUFFICIENT_TRAVERSALS")
    if row.get("estimated_net_range_return_pct", 0) < 1.5: flags.append("RANGE_TOO_NARROW_AFTER_COSTS")
    if row.get("gross_range_return_pct", 0) > DEFAULTS["max_practical_range_pct"]: flags.append("RANGE_TOO_WIDE_HIGH_BREAKOUT_RISK")
    if row.get("false_breakouts_above", 0) + row.get("false_breakdowns_below", 0) >= 5: flags.append("EXCESSIVE_FALSE_BREAKS")
    lower, upper = row.get("lower_boundary_tests", 0), row.get("upper_boundary_tests", 0)
    if max(lower, upper, 1) and abs(lower - upper) / max(lower, upper, 1) > .5: flags.append("ASYMMETRIC_BOUNDARY_TESTS")
    if not row.get("trend_flatness_pass", False): flags.append("TREND_NOT_FLAT")
    if row.get("confirmed_breakouts", 0): flags.append("CONFIRMED_BREAKOUT")
    if row.get("confirmed_breakdowns", 0): flags.append("CONFIRMED_BREAKDOWN")
    if row.get("position_zone") == "ABOVE_RANGE": flags.append("BREAKOUT_PENDING")
    if row.get("position_zone") == "BELOW_RANGE": flags.append("BREAKDOWN_PENDING")
    if row.get("continuity_status") == "GAPS_PRESENT": flags.append("DATA_GAPS")
    if row.get("mapping_uncertain", False): flags.append("MAPPING_UNCERTAIN")
    return flags


def opportunity_score(row: dict[str, Any]) -> tuple[float, dict[str, float]]:
    location = row.get("position_zone")
    location_points = 100 if location in {"NEAR_RANGE_LOW", "NEAR_RANGE_HIGH"} else 60 if location in {"LOWER_HALF", "UPPER_HALF"} else 25
    cycle_points = 0 if row.get("estimated_cycles_per_30d") is None else min(100, row["estimated_cycles_per_30d"] / 6 * 100)
    stability = max(0, 100 - 10 * (row.get("false_breakouts_above", 0) + row.get("false_breakdowns_below", 0)))
    components = {
        "range_quality": row.get("range_quality", 0) * .25,
        "estimated_net_range_width": max(0, min(100, row.get("estimated_net_range_return_pct", 0) / 8 * 100)) * .20,
        "traversal_frequency": cycle_points * .20, "range_stability": stability * .15,
        "liquidity": (100 if row.get("liquidity_pass", False) else 0) * .10,
        "current_location_usefulness": location_points * .05,
        "data_quality_freshness": (100 if row.get("freshness_status") == "FRESH" and row.get("data_quality_status") == "OK" else 0) * .05,
    }
    return round(sum(components.values()), 4), {k: round(v, 4) for k, v in components.items()}
