from __future__ import annotations

"""Compact 30-day market memory and research-only opportunity discovery.

This module consumes existing canonical artifacts.  It defines no trading rules,
does not estimate edge, and has no network, account, or order capability.
"""

import hashlib
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from weekly_consolidation_common import ROOT, atomic_write


VERSION = "OPPORTUNITY_DISCOVERY_V1"
PREDICTIONS = ROOT / "RESEARCH_MEMORY/market_transition/predictions"
MEMORY = ROOT / "RESEARCH_MEMORY/MARKET_MEMORY_30D/latest.json"
TACTICAL_SNAPSHOTS = ROOT / "DATASETS/TACTICAL_OUTCOMES/tactical_candidate_snapshots.jsonl"
TACTICAL_EVENTS = ROOT / "DATASETS/TACTICAL_OUTCOMES/tactical_outcome_events.jsonl"


def utc(value: Any) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def strict(path: Path) -> dict:
    return json.loads(path.read_text(), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def independent_snapshots(directory: Path = PREDICTIONS, now: Any = None) -> list[dict]:
    end = utc(now or pd.Timestamp.now(tz="UTC")); start = end - timedelta(days=30)
    by_cutoff: dict[str, dict] = {}
    for path in sorted(directory.glob("*.json")):
        try: row = strict(path); cutoff = utc(row["market_data_timestamp"])
        except (ValueError, KeyError, TypeError): continue
        if cutoff < start or cutoff > end: continue
        key = cutoff.isoformat()
        candidate = {**row, "_source_path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)}
        # Same cutoff is one economic observation; retain earliest recorded snapshot.
        prior = by_cutoff.get(key)
        if prior is None or utc(candidate.get("timestamp", cutoff)) < utc(prior.get("timestamp", cutoff)):
            by_cutoff[key] = candidate
    return [by_cutoff[key] for key in sorted(by_cutoff, key=utc)]


def _compact(row: dict, previous: dict | None = None) -> dict:
    breadth=row.get("breadth") or {}; sell=row.get("sell_pressure") or {}; quality=row.get("data_quality") or {}
    return {
        "market_data_cutoff": utc(row["market_data_timestamp"]).isoformat(),
        "snapshot_timestamp": row.get("timestamp"), "market_regime": "UNAVAILABLE",
        "market_transition_state": row.get("market_state", "UNAVAILABLE"),
        "previous_transition_state": previous.get("market_state", "UNAVAILABLE") if previous else "UNAVAILABLE",
        "btc_structure_1h": (row.get("btc_structure_1h") or {}).get("trend", "UNAVAILABLE"),
        "btc_structure_4h": (row.get("btc_structure_4h") or {}).get("trend", "UNAVAILABLE"),
        "breadth_above_ema20_pct": breadth.get("above_ema20_pct"), "breadth_above_ema50_pct": breadth.get("above_ema50_pct"),
        "sell_pressure_state": (sell.get("4h") or {}).get("classification", "UNAVAILABLE"),
        "sell_pressure_ratio": (sell.get("4h") or {}).get("ratio"),
        "capital_flow_state": "UNAVAILABLE", "capital_flow_confidence": "UNAVAILABLE",
        "capital_flow_evidence_limitation": "HISTORICAL_CAPITAL_FLOW_NOT_STORED_WITH_TRANSITION_SNAPSHOT",
        "volatility_state": "UNAVAILABLE", "volume_state": "UNAVAILABLE",
        "universe_size": quality.get("tracked_assets"),
        "leading_assets": [x.get("asset") for x in row.get("rs_leaders", [])], "lagging_assets": "UNAVAILABLE",
        "opportunity_candidates": "UNAVAILABLE", "cross_sectional_components": "UNAVAILABLE",
        "source_path": row.get("_source_path"), "observation_type": "OBSERVED",
    }


def _comparison(rows: list[dict], days: int) -> dict:
    if not rows: return {"status": "INSUFFICIENT_HISTORY"}
    current=rows[-1]; threshold=utc(current["market_data_cutoff"])-timedelta(days=days)
    eligible=[x for x in rows[:-1] if utc(x["market_data_cutoff"]) <= threshold]
    if not eligible:return {"status":"INSUFFICIENT_HISTORY"}
    old=eligible[-1]
    def delta(name):
        a,b=current.get(name),old.get(name);return None if a is None or b is None else round(float(a)-float(b),4)
    return {"status":"DERIVED","from_cutoff":old["market_data_cutoff"],"to_cutoff":current["market_data_cutoff"],
            "breadth_ema20_change_pct_points":delta("breadth_above_ema20_pct"),
            "breadth_ema50_change_pct_points":delta("breadth_above_ema50_pct"),
            "btc_structure_1h_change":[old["btc_structure_1h"],current["btc_structure_1h"]],
            "btc_structure_4h_change":[old["btc_structure_4h"],current["btc_structure_4h"]],
            "transition_change":[old["market_transition_state"],current["market_transition_state"]],
            "sell_pressure_change":[old["sell_pressure_state"],current["sell_pressure_state"]]}


def build_market_memory(directory: Path = PREDICTIONS, now: Any = None) -> dict:
    raw=independent_snapshots(directory,now);rows=[_compact(x,raw[i-1] if i else None) for i,x in enumerate(raw)]
    coverage_days=0.0 if len(rows)<2 else (utc(rows[-1]["market_data_cutoff"])-utc(rows[0]["market_data_cutoff"])).total_seconds()/86400
    previous={"status":"INSUFFICIENT_HISTORY"} if len(rows)<2 else {"status":"DERIVED","from_cutoff":rows[-2]["market_data_cutoff"],"changes":{k:[rows[-2].get(k),rows[-1].get(k)] for k in ("market_transition_state","btc_structure_1h","btc_structure_4h","breadth_above_ema20_pct","breadth_above_ema50_pct","sell_pressure_state")}}
    states=[x["market_transition_state"] for x in rows]
    trajectory={"current_state":rows[-1] if rows else None,"change_vs_previous":previous,"change_7d":_comparison(rows,7),"change_30d":_comparison(rows,30),
                "persistence":{"status":"DERIVED" if len(rows)>1 else "INSUFFICIENT_HISTORY","current_state_consecutive_snapshots":next((i for i in range(1,len(states)+1) if len(set(states[-i:]))>1),len(states)+1)-1 if states else 0},
                "leadership_rotation":"DERIVED_FROM_RECORDED_RS_LEADERS" if len(rows)>1 else "INSUFFICIENT_HISTORY"}
    return {"schema_version":"1.0.0","purpose":"MARKET_RESEARCH_DECISION_SUPPORT","window_days":30,
            "coverage":{"status":"SUFFICIENT_30D_HISTORY" if coverage_days>=27 else "INSUFFICIENT_30D_HISTORY","first_cutoff":rows[0]["market_data_cutoff"] if rows else None,"latest_cutoff":rows[-1]["market_data_cutoff"] if rows else None,"independent_snapshots":len(rows),"calendar_days":round(coverage_days,4)},
            "snapshots":rows,"trajectory":trajectory,"source_directory":str(directory.relative_to(ROOT)) if directory.is_relative_to(ROOT) else str(directory),"trading_capability":"DISABLED"}


def _number(value: Any, missing: float = -1e30) -> float:
    try:return float(value) if value is not None else missing
    except (TypeError,ValueError):return missing


def scenario(candidate: dict) -> dict:
    data=candidate.get("current_data") or {};momentum=candidate.get("momentum") or {};con=candidate.get("consolidation") or {}
    price=data.get("live_reference_price") or data.get("analysis_price"); low=con.get("range_low");mid=con.get("midpoint");high=con.get("range_high");activation=momentum.get("breakout_level")
    invalidation=momentum.get("invalidation_reference_level") or low
    distance=None if price in (None,0) or invalidation is None else (_number(invalidation)/_number(price)-1)*100
    refs=[]
    for value,reason in ((mid,"RECORDED_CONSOLIDATION_MIDPOINT"),(high,"RECORDED_CONSOLIDATION_HIGH"),(activation,"RECORDED_BREAKOUT_LEVEL")):
        if value is not None and price not in (None,0) and float(value)>float(price) and all(x["price"]!=float(value) for x in refs):refs.append({"price":float(value),"upside_pct":(float(value)/float(price)-1)*100,"reason":reason})
    return {"reference_price":price,"reference_timestamp":data.get("live_reference_timestamp") or data.get("analysis_price_timestamp"),
            "reference_semantics":data.get("live_reference_semantics") or "COMPLETED_CANDLE_ANALYSIS_PRICE",
            "observation_entry_zone_low":low,"observation_entry_zone_high":mid,"activation_level":activation,
            "technical_invalidation_level":invalidation,"invalidation_distance_pct":distance,
            "constraint_flag":"INVALIDATION_TOO_WIDE_FOR_USER_CONSTRAINT" if distance is not None and distance < -10 else None,
            "reference_levels":refs,"expected_horizon":"UNKNOWN","level_status":"TECHNICAL_SCENARIO_NOT_ORDER"}


def rank_opportunities(chief: dict, limit: int = 20) -> list[dict]:
    eligible=[]
    for c in chief.get("candidates",[]):
        data=c.get("current_data") or {};m=c.get("momentum") or {};rs=c.get("relative_strength") or {}
        if data.get("freshness") != "FRESH" or (m.get("stage") is None and rs.get("percentile_rank") is None):continue
        stage={"BREAKOUT_CONFIRMED":3,"BREAKOUT_DEVELOPING":2,"EARLY_EXPANSION":1,"EARLY_MOMENTUM":1}.get(m.get("stage"),0)
        raw={"momentum_stage":m.get("stage"),"momentum_stage_ordinal":stage,"return_4h_pct":m.get("return_4h_pct"),"return_24h_pct":m.get("return_24h_pct"),"momentum_acceleration":m.get("acceleration"),"breakout_distance_pct":m.get("distance_to_breakout_pct"),"volatility_expansion":m.get("volatility_expansion"),"volume_z_score":m.get("volume_z_score"),"relative_strength_percentile":rs.get("percentile_rank"),"relative_acceleration":rs.get("relative_acceleration"),"relative_persistence":rs.get("relative_persistence"),"rank_change":rs.get("rank_change")}
        # A candidate must have a movement state, top-quintile relative strength,
        # or volatility expansion confirmed by positive volume. This prevents a
        # broad input packet from forcing an uninteresting watchlist.
        qualifies=stage>0 or _number(raw["relative_strength_percentile"],0)>=80 or (_number(raw["volatility_expansion"],0)>=1.25 and _number(raw["volume_z_score"],-1)>0)
        if not qualifies:continue
        technical=scenario(c)
        if technical["invalidation_distance_pct"] is not None and technical["invalidation_distance_pct"] >= 0:continue
        # Deliberately transparent, non-fitted priority tuple. Risk/reward is absent.
        key=(stage,_number(raw["momentum_acceleration"]),_number(raw["volatility_expansion"]),_number(raw["volume_z_score"]),_number(raw["relative_strength_percentile"]),_number(raw["return_4h_pct"]))
        eligible.append((key,str(c.get("asset")),c,raw))
    eligible.sort(key=lambda x:(tuple(-v for v in x[0]),x[1]))
    out=[]
    for rank,(_,asset,c,raw) in enumerate(eligible[:limit],1):
        evidence=c.get("validation") or {};out.append({"rank":rank,"asset":asset,"methodology_version":VERSION,"ranking_method":"LEXICOGRAPHIC_EXISTING_MOVEMENT_COMPONENTS_NOT_OPTIMIZED","raw_opportunity_components":raw,"technical_scenario":scenario(c),"statistical_evidence":{"status":c.get("rotation",{}).get("edge_validation_status") or "UNKNOWN","historical_sample_size":evidence.get("historical_sample_size"),"claim":"NO_PREDICTIVE_EDGE_CLAIM"},"risk_reward_context_not_used_for_ranking":c.get("consolidation",{}).get("rr_to_high")})
    return out


def opportunity_context(chief: dict, memory: dict, tactical_summary: dict) -> dict:
    watch=rank_opportunities(chief);rotation=chief.get("btc_rotation") or {}
    return {"watchlist_status":"BROAD_WATCHLIST" if watch else "NO_COMPELLING_OPPORTUNITY","watchlist":watch,
            "btc_cash_benchmark":{"btc":rotation,"no_position_cash":{"artificial_feature_rank":None,"role":"VALID_BENCHMARK_WHEN_ALTCOIN_EVIDENCE_IS_NOT_COMPELLING"},"interpretation":"DECISION_CONTEXT_NOT_RECOMMENDATION"},
            "history_summary":{**(tactical_summary or {}),"independent_market_clusters":len({x.get("market_data_cutoff") or x.get("timestamp") for x in _read_jsonl(TACTICAL_SNAPSHOTS)}),"warnings":["DESCRIPTIVE_ONLY","DATA_SNOOPING_RISK","MULTIPLE_TESTING_RISK","RECENCY_BIAS_RISK","SELECTION_BIAS_RISK","SIMULTANEOUS_CANDIDATES_CORRELATED"]},
            "market_memory_coverage":memory["coverage"],"trading_capability":"DISABLED"}


def append_opportunity_observations(chief: dict, path: Path = TACTICAL_SNAPSHOTS) -> int:
    generated=utc(chief.get("generated_at_utc") or pd.Timestamp.now(tz="UTC")).isoformat();rows=[]
    by_asset={str(x.get("asset")):x for x in chief.get("candidates",[])}
    for item in rank_opportunities(chief):
        source=by_asset[item["asset"]];cutoff=(source.get("current_data") or {}).get("analysis_price_timestamp")
        identity="odo_"+hashlib.sha256(f'{item["asset"]}|{cutoff}|{generated}|{VERSION}'.encode()).hexdigest()[:24]
        rows.append({"snapshot_id":identity,"observation_id":identity,"timestamp":generated,"market_data_cutoff":cutoff,
                     "asset":item["asset"],"kraken_pair":source.get("identity",{}).get("kraken_pair"),"methodology_version":VERSION,
                     "opportunity_rank":item["rank"],"current_price":item["technical_scenario"]["reference_price"],
                     "technical_scenario":item["technical_scenario"],"raw_opportunity_components":item["raw_opportunity_components"],
                     "statistical_evidence":item["statistical_evidence"],"observation_only":True,"trading_capability":"DISABLED"})
    existing={x.get("snapshot_id") for x in _read_jsonl(path)};new=[x for x in rows if x["snapshot_id"] not in existing]
    if new:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("a",encoding="utf-8") as handle:
            for row in new:handle.write(json.dumps(row,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n")
    return len(new)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():return []
    out=[]
    for line in path.read_text().splitlines():
        try:out.append(json.loads(line))
        except ValueError:continue
    return out


def write_memory(memory: dict, path: Path = MEMORY) -> Path:
    atomic_write(path,json.dumps(memory,indent=2,sort_keys=True,allow_nan=False)+"\n",backup=False);return path
