from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from consolidation_range_engine import BTC_OPERATIONAL_PATH, _read_operational_15m
from weekly_consolidation_common import INTRADAY_DIR, LABELS, ROOT, atomic_write, freshness, utc_timestamp, validate_hourly, write_json

REPORT_DIR = ROOT / "DAILY_REPORTS" / "MOMENTUM_BREAKOUT"


def _hourly_for(asset: str, pair: str, cutoff: Any) -> pd.DataFrame:
    if asset == "BTC":
        raw = _read_operational_15m(BTC_OPERATIONAL_PATH).copy()
        raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True)
        raw = raw.set_index("timestamp").sort_index()
        hourly = raw.resample("1h", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna().reset_index()
        return validate_hourly(hourly, cutoff)[0]
    return validate_hourly(pd.read_csv(INTRADAY_DIR / f"{pair}_1H.csv"), cutoff)[0]


def _ret(close: pd.Series, hours: int) -> float | None:
    return None if len(close) <= hours else (float(close.iloc[-1]) / float(close.iloc[-1-hours]) - 1) * 100


def calculate_features(bars: pd.DataFrame, btc_bars: pd.DataFrame | None = None,
                       consolidation: dict[str, Any] | None = None, as_of: Any = None) -> dict[str, Any]:
    work = bars.sort_values("timestamp").reset_index(drop=True)
    if len(work) < 50:
        raise ValueError("insufficient history: at least 50 completed hourly candles required")
    close = pd.to_numeric(work["close"], errors="coerce")
    high = pd.to_numeric(work["high"], errors="coerce")
    low = pd.to_numeric(work["low"], errors="coerce")
    volume = pd.to_numeric(work["volume"], errors="coerce")
    current = float(close.iloc[-1])
    returns = {f"change_{label}_pct": _ret(close, hours) for label, hours in (("1h",1),("4h",4),("12h",12),("24h",24),("48h",48),("7d",168))}
    acceleration_4h = None if len(close) <= 8 else returns["change_4h_pct"] - (float(close.iloc[-5]) / float(close.iloc[-9]) - 1) * 100
    acceleration_12h = None if len(close) <= 24 else returns["change_12h_pct"] - (float(close.iloc[-13]) / float(close.iloc[-25]) - 1) * 100
    acceleration_24h = None if len(close) <= 48 else returns["change_24h_pct"] - (float(close.iloc[-25]) / float(close.iloc[-49]) - 1) * 100
    btc_close = pd.to_numeric(btc_bars["close"], errors="coerce") if btc_bars is not None and len(btc_bars) else None
    rs = {}
    for label, hours in (("4h",4),("24h",24),("48h",48)):
        btc_return = _ret(btc_close, hours) if btc_close is not None else None
        own = returns[f"change_{label}_pct"]
        rs[f"relative_strength_vs_btc_{label}_pct"] = None if own is None or btc_return is None else own - btc_return
    previous_highs = {}
    breakouts = {}
    for label, hours in (("7d",168),("14d",336),("20d",480)):
        window = high.iloc[-hours-1:-1] if len(high) > hours else pd.Series(dtype=float)
        level = float(window.max()) if len(window) else None
        previous_highs[f"previous_{label}_high"] = level
        breakouts[f"distance_to_{label}_high_pct"] = None if not level else (current / level - 1) * 100
        breakouts[f"close_above_previous_{label}_high"] = bool(level and current > level)
    breakout_level = previous_highs["previous_7d_high"]
    closes_above = int((close.tail(24) > breakout_level).sum()) if breakout_level else 0
    attempt_window = high.iloc[-170:-2] if len(high) > 170 else pd.Series(dtype=float)
    attempt_level = float(attempt_window.max()) if len(attempt_window) else None
    failed_breakout = bool(attempt_level and float(close.iloc[-2]) > attempt_level and current < attempt_level)
    current_4h_volume = float(volume.tail(4).sum())
    volume_4h = volume.rolling(4).sum()
    volume_mean = float(volume_4h.iloc[-21:-1].mean()) if len(volume_4h.dropna()) >= 21 else float(volume.tail(20).mean())
    volume_std = float(volume_4h.iloc[-21:-1].std(ddof=0)) if len(volume_4h.dropna()) >= 21 else float(volume.tail(20).std(ddof=0))
    volume_ratio = current_4h_volume / volume_mean if volume_mean > 0 else None
    volume_z = (current_4h_volume - volume_mean) / volume_std if volume_std > 0 else 0.0
    previous_close = close.shift(1)
    tr = pd.concat([(high-low), (high-previous_close).abs(), (low-previous_close).abs()], axis=1).max(axis=1)
    atr14 = float(tr.rolling(14).mean().iloc[-1])
    atr_pct = atr14 / current * 100
    hourly_returns = close.pct_change()
    realized_vol = float(hourly_returns.tail(168).std(ddof=0) * math.sqrt(24 * 365) * 100)
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    basis = close.rolling(20).mean(); std = close.rolling(20).std(ddof=0)
    bandwidth = (4 * std / basis * 100)
    previous_bw = float(bandwidth.iloc[-21:-1].mean()) if len(bandwidth.dropna()) >= 21 else float(bandwidth.dropna().mean())
    volatility_expansion = float(bandwidth.iloc[-1] / previous_bw) if previous_bw > 0 else 1.0
    ema20_slope = (float(ema20.iloc[-1]) / float(ema20.iloc[-5]) - 1) * 100 if len(ema20) > 4 else 0.0
    extension_atr = (current - float(ema20.iloc[-1])) / atr14 if atr14 > 0 else 0.0
    distance_breakout = None if not breakout_level else (current / breakout_level - 1) * 100
    range_high = float(consolidation["range_high"]) if consolidation and consolidation.get("range_high") is not None else None
    range_breakout = bool(range_high and current > range_high)
    transition = "CONSOLIDATION_TO_BREAKOUT_TRANSITION" if range_breakout and volume_z >= 1 and (rs.get("relative_strength_vs_btc_24h_pct") or 0) > 0 else None
    age, fresh = freshness(work.iloc[-1]["timestamp"], utc_timestamp(as_of))
    overextension = "HIGH" if extension_atr >= 3 or (returns["change_24h_pct"] or 0) >= 15 else "MEDIUM" if extension_atr >= 2 or (returns["change_24h_pct"] or 0) >= 10 else "LOW"
    result = {
        **returns, "roc_4h_pct": returns["change_4h_pct"], "roc_12h_pct": returns["change_12h_pct"], "roc_24h_pct": returns["change_24h_pct"],
        "acceleration_4h_pct": acceleration_4h, "acceleration_12h_pct": acceleration_12h, "acceleration_24h_pct": acceleration_24h,
        **rs, **previous_highs, **breakouts, "breakout_level": breakout_level,
        "number_completed_closes_above_breakout": closes_above, "failed_breakout": failed_breakout,
        "breakout_from_consolidation": range_breakout, "consolidation_transition": transition,
        "current_1h_volume": float(volume.iloc[-1]), "current_4h_volume": current_4h_volume,
        "volume_20bar_average": volume_mean, "volume_ratio": volume_ratio, "volume_z_score": volume_z,
        "atr14_pct": atr_pct, "realized_volatility_pct": realized_vol,
        "bollinger_band_width_pct": float(bandwidth.iloc[-1]), "volatility_expansion_ratio": volatility_expansion,
        "ema20": float(ema20.iloc[-1]), "ema50": float(ema50.iloc[-1]), "ema20_slope_pct": ema20_slope,
        "price_vs_ema20_pct": (current / float(ema20.iloc[-1]) - 1) * 100,
        "price_vs_ema50_pct": (current / float(ema50.iloc[-1]) - 1) * 100,
        "distance_above_ema20_atr": extension_atr, "distance_above_breakout_pct": distance_breakout,
        "recent_range_position_pct": (current - float(low.tail(168).min())) / (float(high.tail(168).max()) - float(low.tail(168).min())) * 100 if float(high.tail(168).max()) > float(low.tail(168).min()) else None,
        "overextension_risk": overextension, "current_price": current,
        "local_swing_low": float(low.tail(24).min()),
        "sufficient_history": len(work) >= 480,
        "latest_completed_candle_timestamp": pd.Timestamp(work.iloc[-1]["timestamp"]).isoformat(),
        "retrieval_timestamp": utc_timestamp().isoformat(), "data_age_hours": age, "freshness_status": fresh,
    }
    result["movement_alert"] = movement_alert(result)
    result["momentum_stage"] = classify_stage(result)
    result.update(decision_conditions(result))
    score, components, penalties = score_momentum(result)
    result.update({"momentum_breakout_score": score, "momentum_score_components": components, "momentum_penalties": penalties})
    return result


def movement_alert(row: dict[str, Any]) -> bool:
    base = (row.get("change_24h_pct") or 0) >= 3 or (row.get("change_48h_pct") or 0) >= 5
    confirmations = sum((
        (row.get("volume_z_score") or 0) >= 1.5,
        (row.get("relative_strength_vs_btc_24h_pct") or 0) >= 2,
        bool(row.get("close_above_previous_7d_high")),
        (row.get("volatility_expansion_ratio") or 0) > 1.2,
        (row.get("ema20_slope_pct") or 0) > 0,
        bool(row.get("breakout_from_consolidation")),
        (row.get("acceleration_4h_pct") or 0) > 0,
    ))
    return bool(base and confirmations >= 2)


def classify_stage(row: dict[str, Any]) -> str:
    if row.get("freshness_status") != "FRESH": return "NO_MOMENTUM"
    if row.get("liquidity_pass") is False: return "NO_MOMENTUM"
    if row.get("failed_breakout"): return "FAILED_BREAKOUT"
    if row.get("overextension_risk") == "HIGH": return "EXTENDED_MOVE"
    above = bool(row.get("close_above_previous_7d_high"))
    if above and row.get("number_completed_closes_above_breakout", 0) >= 1 and (row.get("volume_ratio") or 0) >= 1 and ((row.get("volatility_expansion_ratio") or 0) > 1 or (row.get("relative_strength_vs_btc_24h_pct") or 0) > 0): return "BREAKOUT_CONFIRMED"
    near = row.get("distance_to_7d_high_pct") is not None and row["distance_to_7d_high_pct"] >= -2
    if near and (row.get("volume_ratio") or 0) >= 1 and (row.get("relative_strength_vs_btc_24h_pct") or 0) > 0: return "BREAKOUT_DEVELOPING"
    if (row.get("acceleration_4h_pct") or 0) > 0 and (row.get("acceleration_12h_pct") or 0) > 0 and (row.get("relative_strength_vs_btc_4h_pct") or 0) > 0 and (row.get("volume_ratio") or 0) >= .8: return "EARLY_MOMENTUM"
    return "NO_MOMENTUM"


def decision_conditions(row: dict[str, Any]) -> dict[str, Any]:
    """Return activation and invalidation conditions appropriate to the current stage."""
    stage = row.get("momentum_stage") or classify_stage(row)
    breakout = row.get("breakout_level")
    swing_low = row.get("local_swing_low")
    ema20 = row.get("ema20")
    failure_level = swing_low if swing_low is not None else ema20
    activation = "CLOSE_ABOVE_BREAKOUT_LEVEL" if breakout is not None else None
    if stage == "BREAKOUT_CONFIRMED":
        invalidation = "CLOSE_BELOW_BREAKOUT_LEVEL"
        reference = breakout
    elif stage in {"BREAKOUT_DEVELOPING", "EARLY_MOMENTUM", "FAILED_BREAKOUT"}:
        invalidation = "CLOSE_BELOW_LOCAL_SWING_LOW" if swing_low is not None else "CLOSE_BELOW_EMA20"
        reference = failure_level
    else:
        invalidation = None
        reference = None
    return {
        "activation_condition": activation,
        "invalidation_condition": invalidation,
        "invalidation_reference_level": reference,
    }


def score_momentum(row: dict[str, Any]) -> tuple[float, dict[str, float], dict[str, float]]:
    breakout = min(25, (15 if row.get("close_above_previous_7d_high") else 8 if (row.get("distance_to_7d_high_pct") or -99) >= -2 else 0) + (10 if row.get("breakout_from_consolidation") else 0))
    volume = min(20, max(0, (row.get("volume_ratio") or 0) * 10))
    relative = min(15, max(0, (row.get("relative_strength_vs_btc_24h_pct") or 0) / 5 * 15))
    acceleration = min(15, max(0, (row.get("acceleration_4h_pct") or 0) / 3 * 15))
    trend = min(10, max(0, 5 + (row.get("ema20_slope_pct") or 0) * 5)) if row.get("current_price", 0) > row.get("ema20", float("inf")) else 0
    volatility = min(10, max(0, ((row.get("volatility_expansion_ratio") or 1) - .8) / .7 * 10))
    liquid_fresh = 5 if row.get("freshness_status") == "FRESH" else 0
    components = {"breakout_quality": breakout, "volume_confirmation": volume, "relative_strength": relative, "price_acceleration": acceleration, "trend_quality": trend, "volatility_expansion": volatility, "liquidity_freshness": liquid_fresh}
    penalties = {
        "overextension": 20 if row.get("overextension_risk") == "HIGH" else 8 if row.get("overextension_risk") == "MEDIUM" else 0,
        "failed_breakout": 20 if row.get("failed_breakout") else 0,
        "stale_data": 30 if row.get("freshness_status") != "FRESH" else 0,
        "one_candle_spike": 10 if (row.get("change_1h_pct") or 0) > 8 else 0,
        "wide_spread": 10 if row.get("spread_pass") is False else 0,
        "low_liquidity": 20 if row.get("liquidity_pass") is False else 0,
        "insufficient_history": 10 if row.get("sufficient_history") is False else 0,
    }
    return round(max(0, min(100, sum(components.values()) - sum(penalties.values()))), 4), {k: round(v,4) for k,v in components.items()}, penalties


def flatten(row: dict[str, Any]) -> dict[str, Any]:
    result = {k: v for k, v in row.items() if not isinstance(v, dict)}
    result.update({f"score_{k}": v for k, v in row["momentum_score_components"].items()})
    result.update({f"penalty_{k}": v for k, v in row["momentum_penalties"].items()})
    return result


def rank_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stage_order = {"EARLY_MOMENTUM":0,"BREAKOUT_DEVELOPING":1,"BREAKOUT_CONFIRMED":2,"EXTENDED_MOVE":3,"FAILED_BREAKOUT":4,"NO_MOMENTUM":5}
    ordered = sorted(rows, key=lambda r: (stage_order.get(r["momentum_stage"], 9), -r["momentum_breakout_score"], -(r.get("change_24h_pct") or -999), r["asset"]))
    for rank, row in enumerate(ordered, 1): row["momentum_rank"] = rank
    return ordered


def write_outputs(rows: list[dict[str, Any]], cutoff: pd.Timestamp) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True); base = REPORT_DIR / f"{cutoff:%Y-%m-%d}_momentum_breakout_radar"
    atomic_write(base.with_suffix(".csv"), pd.DataFrame([flatten(r) for r in rows]).to_csv(index=False))
    write_json(base.with_suffix(".json"), {"generated_at_utc": cutoff.isoformat(), "labels": LABELS, "candidates": rows})
    lines = ["# Momentum & Breakout Radar", "", *LABELS]
    groups = (("Top 10 Early Momentum","EARLY_MOMENTUM"),("Top 10 Developing Breakouts","BREAKOUT_DEVELOPING"),("Confirmed Breakouts","BREAKOUT_CONFIRMED"),("Extended Moves","EXTENDED_MOVE"),("Failed Breakouts","FAILED_BREAKOUT"))
    for title, stage in groups:
        subset = [r for r in rows if r["momentum_stage"] == stage][:10]
        lines += ["", f"## {title}", ""] + ([f"- {r['asset']} | score {r['momentum_breakout_score']:.2f} | 24h {r.get('change_24h_pct')}%" for r in subset] or ["- None"])
    for title, key in (("Strongest Relative Strength vs BTC","relative_strength_vs_btc_24h_pct"),("Largest 24h Movers","change_24h_pct"),("Largest 48h Movers","change_48h_pct"),("Largest Positive Acceleration","acceleration_4h_pct"),("Volume Expansion Leaders","volume_z_score")):
        subset = sorted(rows, key=lambda r: r.get(key) if r.get(key) is not None else -999, reverse=True)[:10]
        lines += ["", f"## {title}", ""] + [f"- {r['asset']} | {key} {r.get(key)}" for r in subset]
    atomic_write(base.with_suffix(".md"), "\n".join(lines) + "\n")
    for ext in (".csv", ".json", ".md"):
        atomic_write(REPORT_DIR / f"latest_momentum_breakout_radar{ext}", base.with_suffix(ext).read_text(), backup=False)


def run(universe: list[dict[str, Any]], consolidation_rows: list[dict[str, Any]], as_of: Any = None, dry_run: bool = False) -> list[dict[str, Any]]:
    cutoff = utc_timestamp(as_of)
    included = [r for r in universe if r.get("inclusion_status") == "INCLUDED"]
    btc_item = next((r for r in included if r.get("symbol") == "BTC"), None)
    btc_bars = _hourly_for("BTC", str(btc_item.get("selected_kraken_pair", "XBTUSD")), cutoff) if btc_item else None
    consolidation = {r["asset"]: r for r in consolidation_rows}
    rows = []
    for item in included:
        asset, pair = str(item["symbol"]), str(item["selected_kraken_pair"])
        try:
            bars = btc_bars if asset == "BTC" else _hourly_for(asset, pair, cutoff)
            row = calculate_features(bars, btc_bars, consolidation.get(asset), cutoff)
            row.update({"asset": asset, "kraken_pair": pair, "market_cap_rank": item.get("market_cap_rank"), "kraken_24h_quote_volume": item.get("kraken_24h_quote_volume"), "bid_ask_spread_pct": item.get("bid_ask_spread_pct"), "liquidity_pass": bool(item.get("liquidity_pass")), "spread_pass": bool(item.get("spread_pass")), "refresh_status": "REUSED_CACHE"})
            row["momentum_stage"] = classify_stage(row)
            row.update(decision_conditions(row))
            score, components, penalties = score_momentum(row)
            row.update({"momentum_breakout_score": score, "momentum_score_components": components, "momentum_penalties": penalties})
            rows.append(row)
        except Exception:
            continue
    rows = rank_rows(rows)
    if not dry_run: write_outputs(rows, cutoff)
    return rows


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--as-of"); parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args()
    universe_path=ROOT/"DATASETS"/"universe"/"weekly_consolidation_universe.csv"
    universe=pd.read_csv(universe_path).to_dict("records")
    rows=run(universe,[],args.as_of,args.dry_run); print(f"Momentum radar complete | assets {len(rows)}")


if __name__ == "__main__": main()
