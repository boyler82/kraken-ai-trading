from __future__ import annotations

"""Market-only, research-only transition monitor.

The rules in this module are deliberately fixed and evidence-count based.  Forward
results are observations only; they are never fed back into classification.
"""

import argparse
import hashlib
import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from daily_momentum_breakout_radar import _hourly_for
from lib.feature_store import load_features
from weekly_consolidation_common import INTRADAY_DIR, ROOT, atomic_write, utc_timestamp, validate_hourly

MEMORY = ROOT / "RESEARCH_MEMORY" / "market_transition"
PREDICTIONS = MEMORY / "predictions"
EVALUATIONS = MEMORY / "evaluations"
MISSED = MEMORY / "missing_observations"
OPERATIONS = MEMORY / "operational_events"
HORIZONS = (6, 12, 24)
SCHEDULE_SECONDS = 5400
MAX_SOURCE_AGE_HOURS = 3.0
STATES = {"CONTINUATION_READY", "HEALTHY_PULLBACK", "CONSOLIDATION", "DEEPER_CORRECTION_RISK", "INDETERMINATE"}


class DuplicateMarketDataError(RuntimeError):
    pass


def _number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if np.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def market_structure(bars: pd.DataFrame, hours: int) -> dict[str, Any]:
    """Classify structure from confirmed 3-bar pivots in the requested window."""
    b = bars.sort_values("timestamp").tail(hours).reset_index(drop=True)
    if len(b) < min(hours, 12):
        return {"trend": "UNAVAILABLE", "distance_from_swing_high_pct": None, "distance_from_swing_low_pct": None}
    highs, lows, close = b.high.astype(float), b.low.astype(float), float(b.close.iloc[-1])
    ph = highs[(highs > highs.shift(1)) & (highs >= highs.shift(-1))]
    pl = lows[(lows < lows.shift(1)) & (lows <= lows.shift(-1))]
    swing_high = float(ph.iloc[-1]) if len(ph) else float(highs.max())
    swing_low = float(pl.iloc[-1]) if len(pl) else float(lows.min())
    if len(ph) >= 2 and len(pl) >= 2:
        if ph.iloc[-1] > ph.iloc[-2] and pl.iloc[-1] > pl.iloc[-2]: trend = "HH_HL"
        elif ph.iloc[-1] < ph.iloc[-2] and pl.iloc[-1] < pl.iloc[-2]: trend = "LH_LL"
        else: trend = "MIXED"
    else: trend = "INDETERMINATE"
    return {"trend": trend, "recent_swing_high": swing_high, "recent_swing_low": swing_low,
            "distance_from_swing_high_pct": round((close / swing_high - 1) * 100, 4),
            "distance_from_swing_low_pct": round((close / swing_low - 1) * 100, 4)}


def sell_pressure(bars: pd.DataFrame, hours: int) -> dict[str, Any]:
    b = bars.sort_values("timestamp").tail(hours)
    red = float(b.loc[b.close < b.open, "volume"].sum())
    green = float(b.loc[b.close >= b.open, "volume"].sum())
    ratio = red / green if green > 0 else None
    previous = bars.sort_values("timestamp").iloc[-2 * hours:-hours]
    pr = float(previous.loc[previous.close < previous.open, "volume"].sum())
    pg = float(previous.loc[previous.close >= previous.open, "volume"].sum())
    old = pr / pg if pg > 0 else None
    change = None if ratio is None or old is None or old == 0 else ratio / old - 1
    label = "NORMAL" if change is None or abs(change) < .20 else "INCREASING" if change > 0 else "DECLINING"
    return {"ratio": None if ratio is None else round(ratio, 4), "classification": label}


def pullback_depth(bars: pd.DataFrame) -> float | None:
    """Retracement of the latest material low-to-high impulse in the last 7 days."""
    b = bars.sort_values("timestamp").tail(168).reset_index(drop=True)
    if len(b) < 24: return None
    high_i = int(b.high.astype(float).idxmax())
    if high_i < 4: return None
    peak = float(b.high.iloc[high_i]); base = float(b.low.iloc[:high_i + 1].min())
    amplitude = peak - base
    if amplitude <= 0 or amplitude / base < .03: return None
    return round((peak - float(b.close.iloc[-1])) / amplitude * 100, 4)


def recent_breakout(bars: pd.DataFrame) -> tuple[float, bool] | None:
    """A valid range break is a close above the prior 7-day high in the last 24h."""
    b = bars.sort_values("timestamp").reset_index(drop=True)
    if len(b) < 192: return None
    for i in range(len(b) - 1, max(167, len(b) - 25), -1):
        level = float(b.high.iloc[i-168:i].max())
        if float(b.close.iloc[i]) > level:
            return level, bool(float(b.close.iloc[-1]) >= level)
    return None


def breadth_metrics(features: pd.DataFrame, previous: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    f = features.copy()
    price = pd.to_numeric(f.get("current_price"), errors="coerce")
    e20 = pd.to_numeric(f.get("ema20"), errors="coerce")
    e50 = pd.to_numeric(f.get("ema50"), errors="coerce")
    valid20 = price.notna() & e20.notna(); valid50 = price.notna() & e50.notna()
    result = {"above_ema20_pct": round(float((price[valid20] > e20[valid20]).mean() * 100), 4) if valid20.any() else None,
              "above_ema50_pct": round(float((price[valid50] > e50[valid50]).mean() * 100), 4) if valid50.any() else None,
              "assets_ema20": int(valid20.sum()), "assets_ema50": int(valid50.sum())}
    prior = (previous or {}).get("breadth", {})
    deltas = {k: None if result[k] is None or _number(prior.get(k)) is None else round(result[k] - float(prior[k]), 4)
              for k in ("above_ema20_pct", "above_ema50_pct")}
    known = [x for x in deltas.values() if x is not None]
    delta = sum(known) / len(known) if known else None
    deltas["classification"] = "UNAVAILABLE" if delta is None else "IMPROVING" if delta >= 3 else "DETERIORATING" if delta <= -3 else "STABLE"
    return result, deltas


def classify(snapshot: dict[str, Any]) -> tuple[str, int, int, int, list[str]]:
    """Fixed V1 rules; one vote per independent evidence family."""
    c = k = n = 0; reasons: list[str] = []
    def vote(kind: str, reason: str) -> None:
        nonlocal c, k, n
        c += kind == "c"; k += kind == "k"; n += kind == "n"; reasons.append(reason)
    structures = [snapshot[x].get("trend") for x in ("btc_structure_1h", "btc_structure_4h")]
    vote("c" if structures.count("HH_HL") == 2 else "k" if "LH_LL" in structures else "n", "BTC_STRUCTURE")
    bd = snapshot["breadth_delta"].get("classification")
    vote("c" if bd == "IMPROVING" else "k" if bd == "DETERIORATING" else "n", "BREADTH_CHANGE")
    sp = [snapshot["sell_pressure"][x]["classification"] for x in ("4h", "12h")]
    vote("c" if sp.count("DECLINING") >= 1 and "INCREASING" not in sp else "k" if sp.count("INCREASING") >= 1 else "n", "SELL_PRESSURE")
    br = snapshot.get("breakout_retention_pct")
    vote("c" if br is not None and br >= 65 else "k" if br is not None and br < 40 else "n", "BREAKOUT_RETENTION")
    pb = snapshot.get("median_pullback_depth_pct")
    vote("c" if pb is not None and 15 <= pb <= 45 else "k" if pb is not None and pb > 60 else "n", "PULLBACK_DEPTH")
    rs = snapshot.get("rs_leaders_retained_pct")
    vote("c" if rs is not None and rs >= 60 else "k" if rs is not None and rs < 30 else "n", "RS_PERSISTENCE")
    if snapshot["data_quality"]["status"] == "INSUFFICIENT": return "INDETERMINATE", c, k, n, reasons
    if k >= 4 and k >= c + 2: state = "DEEPER_CORRECTION_RISK"
    elif c >= 4 and c >= k + 2 and (pb is None or pb < 20): state = "CONTINUATION_READY"
    elif c >= 3 and c > k and pb is not None and 15 <= pb <= 50: state = "HEALTHY_PULLBACK"
    elif n >= 3 or abs(c-k) <= 1: state = "CONSOLIDATION"
    else: state = "INDETERMINATE"
    return state, c, k, n, reasons


def _latest_prediction(before: pd.Timestamp | None = None) -> dict[str, Any] | None:
    if not PREDICTIONS.exists(): return None
    candidates = sorted(PREDICTIONS.glob("*.json"), reverse=True)
    for path in candidates:
        try:
            item = json.loads(path.read_text())
            if before is None or utc_timestamp(item["timestamp"]) < before: return item
        except (OSError, ValueError, KeyError): continue
    return None


def build_snapshot(features: pd.DataFrame, bars_by_asset: dict[str, pd.DataFrame], as_of: Any = None,
                   previous: dict[str, Any] | None = None) -> dict[str, Any]:
    now = utc_timestamp(as_of); warnings: list[str] = []
    btc = bars_by_asset.get("BTC", pd.DataFrame())
    breadth, delta = breadth_metrics(features, previous)
    depths = {a: pullback_depth(b) for a, b in bars_by_asset.items() if a != "BTC"}
    depths = {a: v for a, v in depths.items() if v is not None}
    breakouts = [recent_breakout(b) for a, b in bars_by_asset.items() if a != "BTC"]
    breakouts = [x for x in breakouts if x is not None]
    alt = features[features.asset.astype(str) != "BTC"].copy()
    # Prefer returns computed from the same completed hourly bars used by every
    # other monitor metric.  This also supplies 12h RS when the feature store's
    # compatibility schema does not yet carry that column.
    btc_close = btc.sort_values("timestamp").close.astype(float) if len(btc) else pd.Series(dtype=float)
    btc_returns = {h: (float(btc_close.iloc[-1]) / float(btc_close.iloc[-1-h]) - 1) * 100
                   for h in (4, 12, 24) if len(btc_close) > h}
    rs_from_bars: dict[str, dict[str, float]] = {}
    for asset, asset_bars in bars_by_asset.items():
        if asset == "BTC": continue
        close = asset_bars.sort_values("timestamp").close.astype(float)
        values = {}
        for h in (4, 12, 24):
            if len(close) > h and h in btc_returns:
                values[f"btc_relative_return_{h}h"] = (float(close.iloc[-1]) / float(close.iloc[-1-h]) - 1) * 100 - btc_returns[h]
        rs_from_bars[asset] = values
    for col in ("btc_relative_return_4h", "btc_relative_return_12h", "btc_relative_return_24h"):
        if col not in alt: alt[col] = np.nan
        alt[col] = pd.to_numeric(alt[col], errors="coerce")
    for idx, row in alt.iterrows():
        calculated = rs_from_bars.get(str(row.asset), {})
        for h in (4, 12, 24):
            key = f"btc_relative_return_{h}h"
            if key in calculated: alt.at[idx, key] = calculated[key]
    eligible = alt.dropna(subset=["btc_relative_return_4h", "btc_relative_return_12h", "btc_relative_return_24h"])
    leaders = eligible.sort_values(["btc_relative_return_24h", "asset"], ascending=[False, True]).head(5)
    leader_rows = [{"asset": str(r.asset), "rs_4h_pct": _number(r.btc_relative_return_4h),
                    "rs_12h_pct": _number(r.btc_relative_return_12h), "rs_24h_pct": _number(r.btc_relative_return_24h),
                    "retained": bool(r.btc_relative_return_4h > 0 and r.btc_relative_return_24h > 0)} for _, r in leaders.iterrows()]
    quality_inputs = {"btc_bars": len(btc), "tracked_assets": len(bars_by_asset), "breadth_assets": breadth["assets_ema20"],
                      "pullback_assets": len(depths), "rs_assets": len(eligible)}
    quality = "GOOD" if len(btc) >= 168 and min(len(bars_by_asset), breadth["assets_ema20"], len(depths), len(eligible)) >= 10 else "LIMITED"
    if len(btc) < 48 or len(bars_by_asset) < 3: quality = "INSUFFICIENT"
    latest_bar = max((utc_timestamp(b.timestamp.max()) for b in bars_by_asset.values() if len(b)), default=None)
    age_hours = None if latest_bar is None else max(0.0, (now-latest_bar).total_seconds()/3600)
    quality_inputs["latest_bar_timestamp"] = None if latest_bar is None else latest_bar.isoformat()
    quality_inputs["data_age_hours"] = None if age_hours is None else round(age_hours, 4)
    if age_hours is None or age_hours > 24:
        quality = "INSUFFICIENT"
        warnings.append("STALE_MARKET_DATA" if age_hours is not None else "MARKET_DATA_UNAVAILABLE")
    elif age_hours > 8 and quality == "GOOD":
        quality = "LIMITED"; warnings.append("DELAYED_MARKET_DATA")
    if previous is None: warnings.append("BREADTH_DELTA_UNAVAILABLE_NO_PRIOR_SNAPSHOT")
    if not breakouts: warnings.append("NO_RECENT_VALID_BREAKOUTS")
    snap = {"timestamp": now.isoformat(), "market_state": None,
            "market_data_timestamp": None if latest_bar is None else latest_bar.isoformat(),
            "market_data_hash": market_data_identity(bars_by_asset),
            "btc_structure_1h": market_structure(btc, 72) if len(btc) else {"trend":"UNAVAILABLE"},
            "btc_structure_4h": market_structure(btc.set_index("timestamp").resample("4h").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna().reset_index(), 72) if len(btc) else {"trend":"UNAVAILABLE"},
            "breadth": breadth, "breadth_delta": delta,
            "sell_pressure": {"4h": sell_pressure(btc, 4), "12h": sell_pressure(btc, 12)} if len(btc) >= 24 else {"4h":{"ratio":None,"classification":"NORMAL"},"12h":{"ratio":None,"classification":"NORMAL"}},
            "breakout_retention_pct": round(sum(x[1] for x in breakouts) / len(breakouts) * 100, 4) if breakouts else None,
            "breakout_asset_count": len(breakouts), "median_pullback_depth_pct": round(float(np.median(list(depths.values()))), 4) if depths else None,
            "asset_pullback_depth_pct": depths, "rs_leaders": leader_rows,
            "rs_leaders_retained_pct": round(sum(r["retained"] for r in leader_rows) / len(leader_rows) * 100, 4) if leader_rows else None,
            "continuation_evidence": 0, "correction_evidence": 0, "neutral_evidence": 0,
            "data_quality": {"status": quality, **quality_inputs}, "warnings": warnings,
            "labels": ["RESEARCH_ONLY", "MARKET_ONLY", "NOT_A_BUY_SIGNAL", "NOT_A_SELL_SIGNAL"]}
    state, c, k, n, reasons = classify(snap); snap.update(market_state=state, continuation_evidence=c, correction_evidence=k, neutral_evidence=n)
    snap["evidence_families"] = reasons
    return snap


def load_market_inputs(as_of: Any = None) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[str]]:
    cutoff = utc_timestamp(as_of); features = load_features(); bars: dict[str, pd.DataFrame] = {}; warnings = []
    if features.empty or "asset" not in features or "pair" not in features:
        raise RuntimeError("Kraken market feature data is unavailable; no snapshot was written")
    for _, row in features.iterrows():
        asset, pair = str(row.get("asset")), str(row.get("pair"))
        try:
            # The lightweight refresher writes every pair, including BTC, to the
            # established canonical hourly store. Fall back to the legacy BTC
            # operational source only for compatibility with older installations.
            path = INTRADAY_DIR / f"{pair}_1H.csv"
            bars[asset] = validate_hourly(pd.read_csv(path), cutoff)[0] if path.exists() else _hourly_for(asset, pair, cutoff)
        except Exception as exc: warnings.append(f"{asset}: {type(exc).__name__}")
    # Recompute the breadth inputs from the newly refreshed completed bars. The
    # feature store supplies the tracked universe/schema, not cached prices.
    features = features.copy()
    for idx, row in features.iterrows():
        asset_bars = bars.get(str(row.get("asset")))
        if asset_bars is None or asset_bars.empty:
            continue
        close = pd.to_numeric(asset_bars.sort_values("timestamp")["close"], errors="coerce").dropna()
        if close.empty:
            continue
        features.at[idx, "current_price"] = float(close.iloc[-1])
        features.at[idx, "ema20"] = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        features.at[idx, "ema50"] = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
    return features, bars, warnings


def market_data_identity(bars_by_asset: dict[str, pd.DataFrame]) -> str:
    """Hash the completed OHLCV rows actually available to the monitor."""
    digest = hashlib.sha256()
    for asset in sorted(bars_by_asset):
        bars = bars_by_asset[asset].sort_values("timestamp")
        digest.update(asset.encode())
        for row in bars[["timestamp", "open", "high", "low", "close", "volume"]].itertuples(index=False, name=None):
            digest.update((utc_timestamp(row[0]).isoformat() + "|" + "|".join(format(float(v), ".12g") for v in row[1:]) + "\n").encode())
    return digest.hexdigest()


def source_market_timestamp(bars_by_asset: dict[str, pd.DataFrame]) -> pd.Timestamp | None:
    stamps = [utc_timestamp(b.timestamp.max()) for b in bars_by_asset.values() if len(b)]
    return max(stamps) if stamps else None


def prediction_hash_exists(identity: str | None) -> bool:
    """Return whether completed market data already has an immutable prediction."""
    if not identity or not PREDICTIONS.exists():
        return False
    for path in PREDICTIONS.glob("*.json"):
        try:
            if json.loads(path.read_text()).get("market_data_hash") == identity:
                return True
        except (OSError, ValueError):
            continue
    return False


def record_operational_event(status: str, now: Any, **details: Any) -> Path:
    OPERATIONS.mkdir(parents=True, exist_ok=True)
    timestamp = utc_timestamp(now)
    path = OPERATIONS / f"{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}_{status.lower()}.json"
    payload = {"timestamp": timestamp.isoformat(), "status": status, "snapshot_created": False,
               "forward_validation_eligible": False, **details}
    try:
        with path.open("x") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False); handle.write("\n")
    except FileExistsError:
        pass
    return path


def persist_prediction(snapshot: dict[str, Any]) -> Path:
    PREDICTIONS.mkdir(parents=True, exist_ok=True)
    identity = snapshot.get("market_data_hash")
    if identity:
        for existing in PREDICTIONS.glob("*.json"):
            try:
                if json.loads(existing.read_text()).get("market_data_hash") == identity:
                    raise DuplicateMarketDataError("identical market data already has a prediction")
            except (OSError, ValueError):
                continue
    stamp = utc_timestamp(snapshot["timestamp"]).strftime("%Y%m%dT%H%M%S%fZ")
    path = PREDICTIONS / f"{stamp}_{uuid.uuid4().hex[:8]}.json"
    # Exclusive creation is the immutability guarantee for historical predictions.
    with path.open("x") as handle: json.dump(snapshot, handle, indent=2, sort_keys=True, allow_nan=False); handle.write("\n")
    atomic_write(MEMORY / "latest.json", json.dumps(snapshot, indent=2, sort_keys=True, allow_nan=False) + "\n", backup=False)
    return path


def evaluate_due_predictions(bars_by_asset: dict[str, pd.DataFrame], as_of: Any = None) -> int:
    """Append one immutable evaluation file per prediction/horizon when data exists."""
    now = utc_timestamp(as_of); EVALUATIONS.mkdir(parents=True, exist_ok=True); count = 0
    for path in sorted(PREDICTIONS.glob("*.json")):
        pred = json.loads(path.read_text()); start = utc_timestamp(pred["timestamp"]); pred_id = path.stem
        for horizon in HORIZONS:
            out = EVALUATIONS / f"{pred_id}_{horizon}h.json"
            horizon_delta = timedelta(hours=horizon)
            if out.exists() or now < start + horizon_delta: continue
            returns, maes, mfes = {}, {}, {}
            for asset, bars in bars_by_asset.items():
                b = bars.copy(); b["timestamp"] = pd.to_datetime(b.timestamp, utc=True); b = b.sort_values("timestamp")
                base = b[b.timestamp <= start]; future = b[(b.timestamp > start) & (b.timestamp <= start + horizon_delta)]
                if base.empty or future.empty: continue
                p = float(base.close.iloc[-1]); returns[asset] = (float(future.close.iloc[-1]) / p - 1) * 100
                maes[asset] = (float(future.low.min()) / p - 1) * 100; mfes[asset] = (float(future.high.max()) / p - 1) * 100
            alts = [v for a, v in returns.items() if a != "BTC"]
            base_b = pred.get("breadth", {}).get("above_ema20_pct")
            current_f = []
            for a, b in bars_by_asset.items():
                eligible = b[pd.to_datetime(b.timestamp, utc=True) <= start + horizon_delta]
                if len(eligible) >= 20: current_f.append(float(eligible.close.iloc[-1]) > float(eligible.close.ewm(span=20, adjust=False).mean().iloc[-1]))
            current_b = sum(current_f) / len(current_f) * 100 if current_f else None
            record = {"prediction_id": pred_id, "prediction_timestamp": pred["timestamp"], "market_state": pred["market_state"],
                      "horizon_hours": horizon, "evaluated_at": now.isoformat(), "btc_forward_return_pct": returns.get("BTC"),
                      "median_alt_forward_return_pct": float(np.median(alts)) if alts else None,
                      "breadth_forward_change_pct_points": None if current_b is None or base_b is None else current_b - float(base_b),
                      "maximum_adverse_excursion_pct": min(maes.values()) if maes else None,
                      "maximum_favorable_excursion_pct": max(mfes.values()) if mfes else None, "asset_count": len(returns)}
            with out.open("x") as handle: json.dump(record, handle, indent=2, sort_keys=True, allow_nan=False); handle.write("\n")
            count += 1
    return count


def validation_statistics(evaluation_dir: Path = EVALUATIONS) -> dict[str, dict[str, dict[str, Any]]]:
    """Aggregate forward records without changing thresholds or predictions.

    ``deeper_decline`` is a predeclared validation outcome: BTC's horizon return is
    negative and its observed MAE is at most -3%.  Empty groups remain explicit.
    """
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for path in sorted(evaluation_dir.glob("*.json")) if evaluation_dir.exists() else []:
        try:
            row = json.loads(path.read_text()); grouped.setdefault((row["market_state"], int(row["horizon_hours"])), []).append(row)
        except (OSError, ValueError, KeyError): continue
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for state in sorted(STATES):
        result[state] = {}
        for horizon in HORIZONS:
            rows = grouped.get((state, horizon), [])
            btc = [_number(r.get("btc_forward_return_pct")) for r in rows]; btc = [x for x in btc if x is not None]
            alt = [_number(r.get("median_alt_forward_return_pct")) for r in rows]; alt = [x for x in alt if x is not None]
            deeper = [r for r in rows if _number(r.get("btc_forward_return_pct")) is not None and _number(r.get("maximum_adverse_excursion_pct")) is not None]
            result[state][f"{horizon}h"] = {
                "observations": len(rows),
                "p_positive_btc_return": None if not btc else sum(x > 0 for x in btc) / len(btc),
                "p_positive_median_alt_return": None if not alt else sum(x > 0 for x in alt) / len(alt),
                "p_deeper_decline": None if not deeper else sum(float(r["btc_forward_return_pct"]) < 0 and float(r["maximum_adverse_excursion_pct"]) <= -3 for r in deeper) / len(deeper),
            }
    return result


def run(as_of: Any = None, persist: bool = True) -> tuple[dict[str, Any], Path | None, int]:
    now = utc_timestamp(as_of); previous = _latest_prediction(now)
    features, bars, load_warnings = load_market_inputs(now)
    market_timestamp = source_market_timestamp(bars)
    market_hash = market_data_identity(bars)
    age_hours = None if market_timestamp is None else (now - market_timestamp).total_seconds() / 3600
    previous_market_value = (previous or {}).get("market_data_timestamp") or (previous or {}).get("data_quality", {}).get("latest_bar_timestamp")
    previous_timestamp = utc_timestamp(previous_market_value) if previous_market_value else None
    previous_hash = previous.get("market_data_hash") if previous else None
    if market_timestamp is None or age_hours is None or age_hours > MAX_SOURCE_AGE_HOURS:
        result = {"timestamp": now.isoformat(), "status": "STALE_MARKET_DATA", "market_data_timestamp": None if market_timestamp is None else market_timestamp.isoformat(), "market_data_hash": market_hash}
        if persist: record_operational_event("STALE_MARKET_DATA", now, market_data_timestamp=result["market_data_timestamp"], market_data_hash=market_hash)
        return result, None, 0
    unchanged = previous and market_timestamp <= previous_timestamp if previous_timestamp is not None else False
    identical = previous and previous_hash == market_hash
    if (unchanged and (previous_hash is None or identical)) or prediction_hash_exists(market_hash):
        result = {"timestamp": now.isoformat(), "status": "NO_NEW_MARKET_DATA", "market_data_timestamp": market_timestamp.isoformat(), "market_data_hash": market_hash}
        if persist: record_operational_event("NO_NEW_MARKET_DATA", now, market_data_timestamp=result["market_data_timestamp"], market_data_hash=market_hash)
        return result, None, 0
    snapshot = build_snapshot(features, bars, now, previous); snapshot["warnings"].extend(load_warnings)
    evaluated = evaluate_due_predictions(bars, now) if PREDICTIONS.exists() else 0
    path = persist_prediction(snapshot) if persist else None
    return snapshot, path, evaluated


def main() -> None:
    parser = argparse.ArgumentParser(description="Research-only market transition monitor")
    parser.add_argument("--as-of"); parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--result-file", help="write the operational result separately from predictions")
    args = parser.parse_args(); snapshot, path, evaluated = run(args.as_of, not args.no_persist)
    operational = {
        "status": snapshot.get("status", "SUCCESS_NEW_OBSERVATION"),
        "timestamp": snapshot["timestamp"],
        "market_data_timestamp": snapshot.get("market_data_timestamp"),
        "market_data_hash": snapshot.get("market_data_hash"),
        "prediction_path": None if path is None else str(path),
    }
    if args.result_file:
        atomic_write(Path(args.result_file), json.dumps(operational, sort_keys=True, allow_nan=False) + "\n", backup=False)
    if snapshot.get("status"):
        print(snapshot["status"])
    else:
        print(f"MARKET TRANSITION MONITOR | {snapshot['market_state']} | prediction {path or 'not persisted'} | evaluations {evaluated}")


if __name__ == "__main__": main()
