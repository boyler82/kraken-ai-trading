from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd
from portfolio_state import load_current_portfolio,mark_to_market

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config/capital_efficiency_v1.json"
OUT = ROOT / "CAPITAL_EFFICIENCY"
SNAPSHOTS = OUT / "SNAPSHOTS"
LATEST_JSON = OUT / "latest_capital_efficiency.json"
LATEST_MD = OUT / "latest_capital_efficiency.md"
MARKET = ROOT / "DATASETS/market_intraday_weekly"
FEATURES = ROOT / "DATASETS/FEATURE_STORE/latest_market_features.csv"
PORTFOLIO = ROOT / "journal/portfolio_positions.csv"

MODULE_FILES = {
    "CONSOLIDATION": ROOT / "DAILY_REPORTS/DAILY_CONSOLIDATION/latest_daily_consolidation_scan.csv",
    "RANGE_PERSONALITY": ROOT / "DECISION_REGISTRY/range_personality.json",
    "RANGE_QUALITY": ROOT / "DECISION_REGISTRY/range_quality_index.json",
    "EARLY_EXPANSION": ROOT / "DECISION_REGISTRY/early_expansion.json",
    "MOMENTUM": ROOT / "DAILY_REPORTS/MOMENTUM_BREAKOUT/latest_momentum_breakout_radar.csv",
    "RELATIVE_STRENGTH": ROOT / "DAILY_REPORTS/RELATIVE_STRENGTH/latest_relative_strength.json",
    "BTC_ROTATION": ROOT / "DAILY_REPORTS/BTC_ROTATION/latest_btc_rotation_dashboard.json",
}


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {} if default is None else default


def load_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def clean(value: Any) -> Any:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return min(high, max(low, value))


def pct_change(current: float, previous: float) -> float | None:
    return None if not previous else (current / previous - 1) * 100


def market_statistics(frame: pd.DataFrame, minimum_bars: int) -> dict[str, Any]:
    if len(frame) < minimum_bars:
        return {"history_status": "INSUFFICIENT_SAMPLE"}
    d = frame.copy().sort_values("timestamp").reset_index(drop=True)
    for column in ("open", "high", "low", "close", "volume"):
        d[column] = pd.to_numeric(d[column], errors="coerce")
    d = d.dropna(subset=["high", "low", "close"])
    if len(d) < minimum_bars:
        return {"history_status": "INSUFFICIENT_SAMPLE"}
    close = d.close
    current = float(close.iloc[-1])
    returns = {hours: pct_change(current, float(close.iloc[-hours - 1])) if len(d) > hours else None for hours in (1, 6, 12, 24)}
    def recent_range(hours: int) -> float | None:
        sample = d.iloc[-hours:]
        return (float(sample.high.max()) / float(sample.low.min()) - 1) * 100 if len(sample) == hours and sample.low.min() > 0 else None
    # Non-overlapping blocks reduce dependence in the historical range sample.
    blocks12, blocks24 = [], []
    for size, target in ((12, blocks12), (24, blocks24)):
        start = len(d) % size
        for i in range(start, len(d) - size + 1, size):
            block = d.iloc[i:i + size]
            low = float(block.low.min())
            if low > 0:
                target.append((float(block.high.max()) / low - 1) * 100)
    previous = close.shift(1)
    true_range = pd.concat([(d.high - d.low), (d.high - previous).abs(), (d.low - previous).abs()], axis=1).max(axis=1)
    atr_pct = float(true_range.tail(14).mean() / current * 100) if len(true_range) >= 14 and current else None
    log_returns = (close / close.shift(1)).apply(lambda x: math.log(x) if pd.notna(x) and x > 0 else None).dropna()
    realized = float(log_returns.tail(168).std(ddof=1) * math.sqrt(24) * 100) if len(log_returns) >= 24 else None
    quote_volume = float((d.tail(24).close * d.tail(24).volume.fillna(0)).sum()) if len(d) >= 24 else None
    return {
        "history_status": "AVAILABLE", "history_bars": len(d), "current_price": current,
        "return_1h": returns[1], "return_6h": returns[6], "return_12h": returns[12], "return_24h": returns[24],
        "absolute_return_12h": abs(returns[12]) if returns[12] is not None else None,
        "high_low_range_12h_pct": recent_range(12), "high_low_range_24h_pct": recent_range(24),
        "ATR_pct": atr_pct, "realized_volatility": realized, "volume_24h_usd": quote_volume,
        "median_abs_move_12h": median([abs(pct_change(float(d.close.iloc[i + 11]), float(d.close.iloc[i])) or 0) for i in range(len(d) % 12, len(d) - 11, 12)]),
        "median_range_12h": median(blocks12) if blocks12 else None, "median_range_24h": median(blocks24) if blocks24 else None,
        "pct_periods_range_ge_3": 100 * sum(x >= 3 for x in blocks12) / len(blocks12) if blocks12 else None,
        "pct_periods_range_ge_5": 100 * sum(x >= 5 for x in blocks12) / len(blocks12) if blocks12 else None,
    }


def barrier_events(frame: pd.DataFrame, target_pct: float, stop_pct: float, horizon: int, minimum: int) -> dict[str, Any]:
    """Non-overlapping first-touch episodes; ambiguous same-bar touches are conservatively losses."""
    d = frame.sort_values("timestamp").reset_index(drop=True)
    episodes, i = [], 0
    while i < len(d) - 1:
        entry = float(d.close.iloc[i]); resolved = False
        for j in range(i + 1, min(len(d), i + horizon + 1)):
            hit_target = float(d.high.iloc[j]) >= entry * (1 + target_pct / 100)
            hit_stop = float(d.low.iloc[j]) <= entry * (1 - stop_pct / 100)
            if hit_target or hit_stop:
                episodes.append({"success": bool(hit_target and not hit_stop), "hours": j - i})
                i = j + 1; resolved = True; break
        if not resolved:
            i += horizon + 1
    if len(episodes) < minimum:
        return {"status": "INSUFFICIENT_SAMPLE", "n": len(episodes), "probability_pct": None, "median_time_hours": None}
    successes = [x for x in episodes if x["success"]]
    return {"status": "AVAILABLE", "n": len(episodes), "probability_pct": 100 * len(successes) / len(episodes), "median_time_hours": median([x["hours"] for x in successes]) if successes else None}


def liquidity_metrics(volume: float | None, spread: float | None, cfg: dict, position_notional: float | None = None) -> dict[str, Any]:
    if volume is None or volume <= 0:
        return {"spread_pct": spread, "estimated_slippage_5k": None, "estimated_slippage_10k": None, "liquidity_status": "UNSUITABLE", "liquidity_score": 0.0,"position_notional_usd":position_notional,"estimated_slippage_position_size":None,"estimated_execution_cost_position_size":None,"liquidity_status_position_size":"UNSUITABLE" if position_notional is not None else None,"POSITION_LIQUIDITY_SCORE":0.0 if position_notional is not None else None,"POSITION_ENTRY_DIFFICULTY":"UNSUITABLE" if position_notional is not None else None,"POSITION_EXIT_DIFFICULTY":"UNSUITABLE" if position_notional is not None else None,"effective_liquidity_score":0.0}
    spread_value = max(0.0, float(spread or 0))
    coefficient = float(cfg["impact_coefficient_pct"])
    def estimate(notional: float) -> float:
        return spread_value / 2 + coefficient * math.sqrt(notional / volume)
    slip5, slip10 = estimate(5000), estimate(10000)
    def classify(notional:float,slippage:float,multiplier:float=1.0)->str:
        adjusted=slippage*multiplier;participation=notional/volume*100
        if participation>cfg["maximum_participation_10k_pct"] or volume<cfg["minimum_volume_24h_usd"]:return "UNSUITABLE"
        if adjusted<=cfg["good_max_slippage_10k_pct"]:return "GOOD"
        if adjusted<=cfg["acceptable_max_slippage_10k_pct"]:return "ACCEPTABLE"
        if adjusted<=cfg["poor_max_slippage_10k_pct"]:return "POOR"
        return "UNSUITABLE"
    score_map={"GOOD":100.0,"ACCEPTABLE":70.0,"POOR":30.0,"UNSUITABLE":0.0};participation=10000/volume*100;status5=classify(5000,slip5);status=classify(10000,slip10)
    actual_slippage=estimate(float(position_notional)) if position_notional is not None else None;actual_status=classify(float(position_notional),actual_slippage) if actual_slippage is not None else None;entry=classify(float(position_notional),actual_slippage,cfg.get('entry_impact_multiplier',1.0)) if actual_slippage is not None else None;exit_status=classify(float(position_notional),actual_slippage,cfg.get('exit_impact_multiplier',1.25)) if actual_slippage is not None else None;position_score=score_map.get(actual_status) if actual_status else None
    return {"spread_pct": spread, "estimated_slippage_5k": slip5,"liquidity_status_5k":status5, "estimated_slippage_10k": slip10, "liquidity_status": status, "liquidity_score": score_map[status], "volume_participation_10k_pct": participation,"position_notional_usd":position_notional,"estimated_slippage_position_size":actual_slippage,"estimated_execution_cost_position_size":actual_slippage+cfg.get('execution_fee_pct_per_side',.2) if actual_slippage is not None else None,"liquidity_status_position_size":actual_status,"POSITION_LIQUIDITY_SCORE":position_score,"POSITION_ENTRY_DIFFICULTY":entry,"POSITION_EXIT_DIFFICULTY":exit_status,"effective_liquidity_score":position_score if position_score is not None else score_map[status],"effective_liquidity_status":actual_status or status}


def _asset_rows(value: Any) -> dict[str, dict]:
    rows: list[dict] = []
    if isinstance(value, list): rows = value
    elif isinstance(value, dict):
        for item in value.values():
            if isinstance(item, list): rows.extend(x for x in item if isinstance(x, dict))
    return {str(x.get("asset")): x for x in rows if x.get("asset")}


def module_context() -> tuple[dict[str, list[str]], dict[str, float], list[str]]:
    active: dict[str, list[str]] = {}; quality: dict[str, list[float]] = {}; warnings = []
    for name, path in MODULE_FILES.items():
        if not path.exists(): warnings.append(f"{name}_UNAVAILABLE"); continue
        rows = _asset_rows(load_csv(path).where(pd.notna(load_csv(path)), None).to_dict("records") if path.suffix == ".csv" else load_json(path))
        for asset, row in rows.items():
            # Presence is not enough: require an affirmative/current setup signal.
            text = json.dumps(row, default=str).upper()
            inactive = any(flag in text for flag in ('"NO_MOMENTUM"', '"INVALIDATED"', '"UNAVAILABLE"'))
            affirmative = any(flag in text for flag in ("VALID_RANGE", "BREAKOUT", "ACTIVE", "SPECIALIST", "FRIENDLY", "REVIEW_", "LEADER", "EARLY"))
            if affirmative and not inactive:
                active.setdefault(asset, []).append(name)
                candidates = [row.get(k) for k in ("range_quality", "rqi_score", "score", "momentum_breakout_score", "evidence_confidence_score")]
                numeric = [float(x) for x in candidates if isinstance(x, (int, float)) and math.isfinite(float(x))]
                quality.setdefault(asset, []).append(max(numeric) if numeric else 50.0)
    return active, {a: sum(v) / len(v) for a, v in quality.items()}, warnings


def score_asset(stats: dict, e3: dict, e5: dict, liquidity: dict, setup_count: int, setup_quality: float, cfg: dict) -> tuple[dict, float]:
    scales, weights = cfg["score_scales"], cfg["score_weights"]
    movement = clamp(100 * float(stats.get("median_range_24h") or 0) / scales["movement_range_pct_full_score"])
    times = [x for x in (e3.get("median_time_hours"), e5.get("median_time_hours")) if x is not None]
    speed_hours = sum(times) / len(times) if times else scales["speed_hours_zero_score"]
    speed = clamp(100 * (scales["speed_hours_zero_score"] - speed_hours) / (scales["speed_hours_zero_score"] - scales["speed_hours_full_score"]))
    probabilities = [x for x in (e3.get("probability_pct"), e5.get("probability_pct")) if x is not None]
    probability = sum(probabilities) / len(probabilities) if probabilities else 0.0
    setup = clamp(setup_quality) if setup_count else 0.0
    components = {"MOVEMENT_SCORE": movement, "SPEED_SCORE": speed, "PROBABILITY_SCORE": probability, "LIQUIDITY_SCORE": liquidity.get("effective_liquidity_score",liquidity["liquidity_score"]), "SETUP_SCORE": setup}
    if liquidity.get('POSITION_LIQUIDITY_SCORE') is not None:components['POSITION_LIQUIDITY_SCORE']=liquidity['POSITION_LIQUIDITY_SCORE']
    total_weight = sum(weights.values())
    total = sum(components[k.upper() + "_SCORE"] * weights[k] for k in weights) / total_weight
    # An unsuitable market cannot score as capital-efficient regardless of volatility.
    if liquidity.get("effective_liquidity_status",liquidity["liquidity_status"]) == "UNSUITABLE": total = min(total, 35.0)
    return components, round(total, 2)

def has_full_capital_efficiency_coverage(record:dict|None)->bool:
    required=('median_abs_move_12h','median_range_12h','median_range_24h','ATR_pct','realized_volatility','pct_periods_range_ge_3','pct_periods_range_ge_5','liquidity_status','capital_efficiency_score')
    return bool(record and all(record.get(key) is not None for key in required) and record.get('plus_3_before_minus_2',{}).get('status')=='AVAILABLE' and record.get('plus_5_before_minus_2',{}).get('status')=='AVAILABLE')


def market_regime() -> tuple[str, list[str]]:
    path = ROOT / "RESEARCH_MEMORY/research_memory.sqlite"
    if not path.exists(): return "UNKNOWN", ["REGIME_SAMPLE_UNAVAILABLE"]
    import sqlite3
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    values = [str(x[0]) for x in db.execute("SELECT market_regime FROM research_market_snapshots WHERE market_regime IS NOT NULL")]
    db.close()
    if not values: return "UNKNOWN", ["REGIME_SAMPLE_UNAVAILABLE"]
    current = values[-1]
    warnings = ["REGIME_SAMPLE_BIAS"] if len(set(values)) == 1 else []
    return current, warnings

def manual_execution_disagreement_warning(root:Path=ROOT)->list[str]:
    for path in (root/'PORTFOLIO_MEMORY/manual_execution_notes.json',root/'journal/execution_notes.json'):
        data=load_json(path)
        rows=data if isinstance(data,list) else data.get('notes',[]) if isinstance(data,dict) else []
        if any(isinstance(x,dict) and x.get('model_disagreement') is True for x in rows):return ['MODEL_EXECUTION_DISAGREES_WITH_OBSERVED_EXPERIENCE']
    return []


def portfolio_rows(prices: dict[str, float],as_of:Any=None) -> tuple[list[dict], list[str]]:
    current = mark_to_market(load_current_portfolio(),as_of)
    if current.get("holdings"):
        rows=[{"asset":str(x["asset"]),"capital_allocated_usd":x.get("current_market_value_usd"),"portfolio_weight":x.get("current_portfolio_weight_pct"),"current_quantity":x.get("quantity"),"displayed_pnl_usd":x.get("displayed_pnl_usd"),"displayed_pnl_pct":x.get("displayed_pnl_pct")} for x in current["holdings"] if str(x.get("asset")) not in {"USD","EUR","USDT","USDC"}]
        return rows, [x for x in current.get('warnings',[]) if str(x).startswith('MARK_TO_MARKET_PRICE_STALE')]
    return [], ["PORTFOLIO_CONTEXT_UNAVAILABLE"]


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); temp = path.with_suffix(path.suffix + ".tmp"); temp.write_text(text); temp.replace(path)


def build(as_of: str | None = None, config_path: Path = CONFIG_PATH,use_portfolio:bool=False) -> dict[str, Any]:
    cfg = load_json(config_path); feature = load_csv(FEATURES); feature_map = {str(x.asset): x.to_dict() for _, x in feature.iterrows()} if not feature.empty and "asset" in feature else {}
    active, setup_quality, module_warnings = module_context(); regime, regime_warnings = market_regime();held,portfolio_warnings=portfolio_rows({},as_of) if use_portfolio else ([],[]);held_map={x['asset']:x for x in held}; assets = []
    for path in sorted(MARKET.glob("*USD_1H.csv")):
        asset = path.name.removesuffix("USD_1H.csv"); frame = load_csv(path)
        stats = market_statistics(frame, cfg["minimum_hourly_bars"])
        if stats["history_status"] != "AVAILABLE": continue
        e3 = barrier_events(frame, 3, cfg["event_stop_pct"], cfg["event_max_horizon_hours"], cfg["minimum_event_episodes"])
        e5 = barrier_events(frame, 5, cfg["event_stop_pct"], cfg["event_max_horizon_hours"], cfg["minimum_event_episodes"])
        spread = feature_map.get(asset, {}).get("spread"); spread = None if pd.isna(spread) else float(spread)
        position=held_map.get(asset);liq = liquidity_metrics(stats["volume_24h_usd"], spread, cfg["liquidity"],position.get('capital_allocated_usd') if position else None)
        modules = sorted(set(active.get(asset, []))); quality = setup_quality.get(asset, 0.0)
        components, total = score_asset(stats, e3, e5, liq, len(modules), quality, cfg)
        assets.append({"asset": asset, **stats, **liq, "plus_3_before_minus_2": e3, "plus_5_before_minus_2": e5,
            "probability_plus_3_before_minus_2_pct": e3["probability_pct"], "probability_plus_5_before_minus_2_pct": e5["probability_pct"],
            "median_time_to_plus_3_pct": e3["median_time_hours"], "median_time_to_plus_5_pct": e5["median_time_hours"],
            "active_modules": modules, "setup_count": len(modules), "best_setup": modules[0] if modules else None,
            "setup_quality": quality if modules else 0.0, "market_regime": regime, "component_scores": components,
            "capital_efficiency_score": total})
    assets.sort(key=lambda x: (-x["capital_efficiency_score"], x["asset"]))
    prices = {x["asset"]: x["current_price"] for x in assets};by_asset = {x["asset"]: x for x in assets}
    for asset in assets:
        position=held_map.get(asset['asset'])
        if use_portfolio:asset.update({'currently_held':position is not None,'current_quantity':position.get('current_quantity') if position else None,'current_usd_value':position.get('capital_allocated_usd') if position else None,'portfolio_weight_pct':position.get('portfolio_weight') if position else None,'displayed_pnl_usd':position.get('displayed_pnl_usd') if position else None,'displayed_pnl_pct':position.get('displayed_pnl_pct') if position else None})
        else:
            for key in ('position_notional_usd','estimated_slippage_position_size','estimated_execution_cost_position_size','liquidity_status_position_size','POSITION_LIQUIDITY_SCORE','POSITION_ENTRY_DIFFICULTY','POSITION_EXIT_DIFFICULTY'):asset.pop(key,None)
    eligible = [x for x in assets if x["liquidity_status"] in ("GOOD", "ACCEPTABLE")]
    best = eligible[0] if eligible else None
    thresholds = cfg["portfolio_status"]
    covered_weight=0.0;held_without_coverage=[]
    for position in held:
        record = by_asset.get(position["asset"]); score = record["capital_efficiency_score"] if record else None
        covered=has_full_capital_efficiency_coverage(record)
        if covered:covered_weight += float(position.get('portfolio_weight') or 0)
        else:held_without_coverage.append(position['asset'])
        difference = best["capital_efficiency_score"] - score if best and score is not None and best["asset"] != position["asset"] else 0.0 if score is not None else None
        if score is None: status = "IDLE"
        elif difference is not None and difference >= thresholds["high_opportunity_cost_difference"]: status = "HIGH_OPPORTUNITY_COST"
        elif score >= thresholds["productive_min_score"]: status = "PRODUCTIVE"
        elif score >= thresholds["neutral_min_score"]: status = "NEUTRAL"
        else: status = "IDLE"
        position.update({"capital_efficiency_score": score, "capital_efficiency_data_status":"FULL_COVERAGE" if covered else "HELD_ASSET_DATA_INSUFFICIENT", "capital_activity_status": status, "opportunity_cost_score": max(0.0, difference or 0.0), "best_alternative_asset": best["asset"] if best and best["asset"] != position["asset"] else None, "score_difference": difference})
    fr = cfg["fast_range"]
    fast = [{"asset": x["asset"], "median_move": x["median_range_24h"], "median_cycle": x["median_time_to_plus_3_pct"], "range_quality": x["setup_quality"], "liquidity": x["liquidity_status"], "capital_efficiency_score": x["capital_efficiency_score"]} for x in assets if x["median_range_24h"] is not None and fr["minimum_median_move_pct"] <= x["median_range_24h"] <= fr["maximum_median_move_pct"] and x["median_time_to_plus_3_pct"] is not None and fr["minimum_cycle_hours"] <= x["median_time_to_plus_3_pct"] <= fr["maximum_cycle_hours"] and x["capital_efficiency_score"] >= fr["minimum_score"] and x["liquidity_status"] != "UNSUITABLE"]
    timestamp = (pd.Timestamp(as_of) if as_of else pd.Timestamp.now(tz="UTC")).isoformat()
    coverage_warning=["CAPITAL_EFFICIENCY_PORTFOLIO_COVERAGE_INCOMPLETE"] if held and 100-covered_weight>20 else []
    warnings = sorted(set(module_warnings + regime_warnings + portfolio_warnings + coverage_warning + manual_execution_disagreement_warning() + (["HELD_ASSET_DATA_INSUFFICIENT"] if held_without_coverage else []) + (["INSUFFICIENT_SAMPLE"] if any(x["plus_3_before_minus_2"]["status"] != "AVAILABLE" or x["plus_5_before_minus_2"]["status"] != "AVAILABLE" for x in assets) else [])))
    result={"status": "AVAILABLE", "research_mode":"PORTFOLIO" if use_portfolio else "MARKET_ONLY", "purpose": "RESEARCH_ONLY", "generated_at_utc": timestamp, "config_version": cfg["version"], "market_regime": regime, "assets": assets, "best_capital_efficiency_candidates": eligible[:10], "FAST_RANGE_CANDIDATES": fast[:10], "warnings": warnings, "controls": ["NO_REAL_ORDERS", "PUBLIC_OR_CACHED_DATA_ONLY", "NO_STRATEGY_MUTATION", "NO_OOS_OPTIMIZATION"]}
    if use_portfolio:result.update(portfolio_capital_efficiency=held,portfolio_weight_covered_pct=round(min(100.0,covered_weight),2),held_assets_without_coverage=held_without_coverage)
    return result


def render_markdown(payload: dict) -> str:
    lines = ["# Capital Efficiency", "", "RESEARCH_ONLY | no automatic allocation actions", "", f"Market regime: {payload['market_regime']}", "", "## MARKET CAPITAL EFFICIENCY", ""]
    if payload.get('research_mode')=='PORTFOLIO':lines += [f"- {x['asset']}: capital=${x['capital_allocated_usd'] or 0:,.2f}, score={x['capital_efficiency_score']}, status={x['capital_activity_status']}" for x in payload.get("portfolio_capital_efficiency",[])] or ["- No portfolio positions available."]
    lines += ["", "## Best Candidates", ""] + [f"- {i}. {x['asset']} | score={x['capital_efficiency_score']} | liquidity={x['liquidity_status']} | setups={x['setup_count']}" for i, x in enumerate(payload["best_capital_efficiency_candidates"], 1)]
    lines += ["", "## Fast Range Candidates", ""] + ([f"- {x['asset']} | median move={x['median_move']:.2f}% | cycle={x['median_cycle']:.1f}h | liquidity={x['liquidity']} | score={x['capital_efficiency_score']}" for x in payload["FAST_RANGE_CANDIDATES"]] or ["- NONE QUALIFIED"])
    lines += ["", "## Warnings", ""] + [f"- {x}" for x in payload["warnings"]]
    return "\n".join(lines) + "\n"


def run(as_of: str | None = None, config_path: Path = CONFIG_PATH,use_portfolio:bool=False) -> dict:
    payload = build(as_of, config_path,use_portfolio); encoded = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    atomic_write(LATEST_JSON, encoded); atomic_write(LATEST_MD, render_markdown(payload))
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    # Content addressing makes an identical scan idempotent while preserving a
    # distinct historical artifact when source observations change at one as-of.
    identity = hashlib.sha256(encoded.encode()).hexdigest()[:12]
    snapshot = SNAPSHOTS / f"{payload['generated_at_utc'][:10]}_{identity}.json"
    if not snapshot.exists(): snapshot.write_text(encoded)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--as-of"); parser.add_argument("--config", type=Path, default=CONFIG_PATH);parser.add_argument('--use-portfolio',action='store_true'); args = parser.parse_args()
    payload = run(args.as_of, args.config,args.use_portfolio); print(f"Capital efficiency: {len(payload['assets'])} assets; {len(payload['FAST_RANGE_CANDIDATES'])} fast-range candidates")


if __name__ == "__main__": main()
