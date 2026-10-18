from __future__ import annotations

import argparse
from datetime import timedelta
import json
import math
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
import pandas as pd

try:  # script execution
    from range_personality_registry_adapter import LABELS, build_registry
    from weekly_consolidation_common import ROOT, INTRADAY_DIR, atomic_write, utc_timestamp, write_json
except ModuleNotFoundError:  # package import in tests
    from scripts.range_personality_registry_adapter import LABELS, build_registry
    from scripts.weekly_consolidation_common import ROOT, INTRADAY_DIR, atomic_write, utc_timestamp, write_json

CONFIG_PATH = ROOT / "config/range_personality_v1.json"
REPORT_DIR = ROOT / "DAILY_REPORTS/RANGE_PERSONALITY"
HISTORY_DIR = ROOT / "DATASETS/RANGE_PERSONALITY"
REGISTRY_PATH = ROOT / "DECISION_REGISTRY/range_personality.json"
UNIVERSE_PATH = ROOT / "DATASETS/universe/weekly_consolidation_universe.csv"
CURRENT_RANGE_PATH = ROOT / "DAILY_REPORTS/DAILY_CONSOLIDATION/latest_daily_consolidation_scan.csv"


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    if cfg.get("version") != "1.0.0" or sum(cfg["score_weights"].values()) != 100:
        raise ValueError("invalid range personality V1 config")
    return cfg


def _clean_4h(frame: pd.DataFrame, as_of: Any = None) -> pd.DataFrame:
    required = {"timestamp", "open", "high", "low", "close"}
    if not required.issubset(frame): raise ValueError(f"missing OHLC columns: {sorted(required-set(frame))}")
    x = frame.copy(); x["timestamp"] = pd.to_datetime(x["timestamp"], utc=True, errors="coerce")
    for c in ("open", "high", "low", "close", "volume"): 
        if c in x: x[c] = pd.to_numeric(x[c], errors="coerce")
    x = x.dropna(subset=list(required)).sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    cutoff = utc_timestamp(as_of); x = x[x.timestamp + timedelta(hours=4) <= cutoff]
    return x.reset_index(drop=True)


def data_quality(frame: pd.DataFrame, as_of: Any, source_file: str = "", source_timeframe: str = "4H") -> dict[str, Any]:
    ts = frame.timestamp if len(frame) else pd.Series(dtype="datetime64[ns, UTC]")
    missing = int(sum(max(0, round(v / 4) - 1) for v in ts.diff().dropna().dt.total_seconds().div(3600)))
    age = None if not len(frame) else max(0.0, (utc_timestamp(as_of) - ts.iloc[-1] - timedelta(hours=4)).total_seconds()/3600)
    cfg = load_config()["data"]
    fresh = "UNAVAILABLE" if age is None else "FRESH" if age <= cfg["fresh_hours"] else "DELAYED" if age <= cfg["stale_hours"] else "STALE"
    coverage = 0.0 if len(frame) < 2 else (ts.iloc[-1]-ts.iloc[0]).total_seconds()/86400
    return {"source_file": source_file, "native_source_timeframe": source_timeframe,
            "derived_analysis_timeframe": "4H", "first_timestamp": None if not len(ts) else ts.iloc[0].isoformat(),
            "last_timestamp": None if not len(ts) else ts.iloc[-1].isoformat(), "completed_bar_count": len(frame),
            "missing_expected_bars": missing, "continuity_status": "CONTINUOUS" if missing == 0 else "GAPS_PRESENT",
            "freshness": fresh, "freshness_age_hours": age, "available_historical_coverage_days": round(coverage, 2)}


def _atr(frame: pd.DataFrame) -> pd.Series:
    prev = frame.close.shift(); tr = pd.concat([(frame.high-frame.low), (frame.high-prev).abs(), (frame.low-prev).abs()], axis=1).max(axis=1)
    return tr.rolling(14, min_periods=3).mean().bfill()


def _debounced_events(frame: pd.DataFrame, low: float, high: float, tolerance: float, cooldown: int) -> list[dict[str, Any]]:
    events=[]; last=-10**9
    for i,r in frame.iterrows():
        side = "LOW" if r.low <= low+tolerance else "HIGH" if r.high >= high-tolerance else None
        if side and i-last >= cooldown and (not events or events[-1]["side"] != side):
            events.append({"side": side, "index": int(i), "timestamp": r.timestamp.isoformat()}); last=int(i)
    return events


def extract_traversals(frame: pd.DataFrame, low: float, high: float, config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg=(config or load_config())["episode"]; width=high-low
    events=_debounced_events(frame,low,high,width*cfg["boundary_tolerance_pct_of_width"]/100,cfg["event_cooldown_bars"])
    out=[]
    for a,b in zip(events,events[1:]):
        if a["side"]==b["side"]: continue
        segment=frame.iloc[a["index"]:b["index"]+1]; start=float(frame.iloc[a["index"]].close); end=float(frame.iloc[b["index"]].close)
        direction="LOW_TO_HIGH" if a["side"]=="LOW" else "HIGH_TO_LOW"; sign=1 if direction=="LOW_TO_HIGH" else -1
        changes=(segment.close/start-1)*100*sign
        false_break=bool((segment.low < low).any() if sign>0 else (segment.high > high).any())
        out.append({"direction":direction,"start_timestamp":a["timestamp"],"end_timestamp":b["timestamp"],
                    "bars":b["index"]-a["index"],"hours":(b["index"]-a["index"])*4,
                    "gross_move_percent":abs((end/start-1)*100),"maximum_adverse_movement":max(0.0,-float(changes.min())),
                    "maximum_favorable_movement":max(0.0,float(changes.max())),
                    "midpoint_crossed":bool((segment.low <= (low+high)/2).any() and (segment.high >= (low+high)/2).any()),
                    "opposite_boundary_reached":True,"false_break_during_traversal":false_break})
    return out


def _episode_candidate(frame: pd.DataFrame, start: int, end: int, cfg: dict[str, Any]) -> dict[str, Any] | None:
    # Boundaries are frozen from the seed only; extension/termination never revises them.
    seed=frame.iloc[start:start+cfg["seed_bars"]]; part=frame.iloc[start:end]
    low=float(seed.low.quantile(.08)); high=float(seed.high.quantile(.92)); width=high-low
    if low<=0 or width/low*100 < cfg["min_width_pct"] or width/low*100 > cfg["max_width_pct"]: return None
    tolerance=width*cfg["boundary_tolerance_pct_of_width"]/100
    events=_debounced_events(part.reset_index(drop=True),low,high,tolerance,cfg["event_cooldown_bars"])
    lower=sum(e["side"]=="LOW" for e in events); upper=sum(e["side"]=="HIGH" for e in events)
    containment=float(part.close.between(low-tolerance,high+tolerance).mean()*100)
    slope=np.polyfit(np.arange(len(part)),part.close,1)[0] if len(part)>1 else 0
    normalized=abs(float(slope))*len(part)/width
    if min(lower,upper)<cfg["min_boundary_reactions"] or containment<cfg["min_containment_pct"] or normalized>cfg["max_normalized_slope"]: return None
    return {"low":low,"high":high,"events":events,"containment":containment,"normalized_slope":normalized}


def detect_range_episodes(frame: pd.DataFrame, asset: str, config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    config=config or load_config(); cfg=config["episode"]; x=frame.reset_index(drop=True); episodes=[]; i=0
    while i+cfg["min_bars"]<=len(x):
        base=_episode_candidate(x,i,i+cfg["min_bars"],cfg)
        if not base: i+=max(1,cfg["seed_bars"]//3); continue
        end=i+cfg["min_bars"]; termination="DATA_END"
        while end<len(x):
            test=x.iloc[i:end+1]; atr=float(_atr(test).iloc[-1]); tol=max((base["high"]-base["low"])*.02,atr*cfg["break_tolerance_atr"])
            if len(test)>=2 and (test.close.iloc[-cfg["break_confirmation_bars"]:] > base["high"]+tol).all(): termination="CONFIRMED_BREAKOUT"; break
            if len(test)>=2 and (test.close.iloc[-cfg["break_confirmation_bars"]:] < base["low"]-tol).all(): termination="CONFIRMED_BREAKDOWN"; break
            candidate=_episode_candidate(x,i,end+1,cfg)
            if candidate is None: termination="RANGE_QUALITY_DECAY"; break
            base=candidate; end+=1
        part=x.iloc[i:end].reset_index(drop=True); low=base["low"]; high=base["high"]; mid=(low+high)/2; traversals=extract_traversals(part,low,high,config)
        atr_med=float(_atr(part).median()); returns=part.close.pct_change().dropna(); efficiency=abs(float(part.close.iloc[-1]-part.close.iloc[0]))/max(float(part.close.diff().abs().sum()),1e-12)
        false_up=int(((part.high>high)&(part.close<=high)).sum()); false_down=int(((part.low<low)&(part.close>=low)).sum())
        episodes.append({"episode_id":f"{asset}-{len(episodes)+1:04d}","asset":asset,"start_timestamp":part.timestamp.iloc[0].isoformat(),
            "end_timestamp":part.timestamp.iloc[-1].isoformat(),"completed_bar_count":len(part),"calendar_duration_hours":(part.timestamp.iloc[-1]-part.timestamp.iloc[0]).total_seconds()/3600+4,
            "range_low":low,"midpoint":mid,"range_high":high,"width_absolute":high-low,"width_percent":(high/low-1)*100,
            "atr_adjusted_width":None if not atr_med else (high-low)/atr_med,"lower_boundary_tests":sum(e["side"]=="LOW" for e in base["events"]),
            "upper_boundary_tests":sum(e["side"]=="HIGH" for e in base["events"]),"midpoint_crossings":int(((part.close-mid)*(part.close.shift()-mid)<0).sum()),
            "low_to_high_traversals":sum(t["direction"]=="LOW_TO_HIGH" for t in traversals),"high_to_low_traversals":sum(t["direction"]=="HIGH_TO_LOW" for t in traversals),
            "partial_traversals":0,"confirmed_breakouts":int(termination=="CONFIRMED_BREAKOUT"),"confirmed_breakdowns":int(termination=="CONFIRMED_BREAKDOWN"),
            "false_breakouts":false_up,"false_breakdowns":false_down,"close_containment_percent":base["containment"],"trend_flatness":1-base["normalized_slope"],
            "width_stability":max(0,1-float(part.rolling(min(12,len(part))).high.max().sub(part.rolling(min(12,len(part))).low.min()).dropna().std() or 0)/max(high-low,1e-12)),
            "continuity_status":"CONTINUOUS" if part.timestamp.diff().dropna().eq(timedelta(hours=4)).all() else "GAPS_PRESENT",
            "episode_termination_reason":termination,"directional_efficiency_ratio":efficiency,"return_volatility":float(returns.std() or 0),"traversals":traversals})
        i=max(end+1,i+cfg["min_bars"])
    return episodes


def _rate(n: int, d: int, quality: str) -> dict[str, Any]:
    value=None if not d else n/d*100; z=1.96; p=0 if not d else n/d; half=None if not d else z*math.sqrt(p*(1-p)/d)*100
    cap={"HIGH":10,"MEDIUM":18,"LOW":30,"INSUFFICIENT":50}.get(quality,50)
    return {"rate_pct":None if value is None else round(value,2),"numerator":n,"denominator":d,"sample_size":d,
            "confidence_band_pct":None if value is None else [round(max(0,value-min(half or 0,cap)),2),round(min(100,value+min(half or 0,cap)),2)],"confidence":quality}


def _sample_quality(episodes: int, traversals: int, cfg: dict[str, Any]) -> str:
    s=cfg["sample_quality"]
    if episodes<s["insufficient_min_episodes"] or traversals<s["insufficient_min_traversals"]: return "INSUFFICIENT"
    if episodes>=s["high_min_episodes"] and traversals>=s["high_min_traversals"]: return "HIGH"
    if episodes>=s["medium_min_episodes"] and traversals>=s["medium_min_traversals"]: return "MEDIUM"
    return "LOW"


def _clip(v: float) -> float: return max(0.0,min(100.0,v))
def _mean(values: list[float]) -> float | None: return None if not values else float(np.mean(values))
def _med(values: list[float]) -> float | None: return None if not values else float(np.median(values))
def _cv(values: list[float]) -> float | None:
    m=_mean(values); return None if not values or not m else float(np.std(values,ddof=0)/m)


def summarize_personality(asset: str, frame: pd.DataFrame, episodes: list[dict[str, Any]], quality_meta: dict[str, Any],
                          liquidity: dict[str, Any] | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg=config or load_config(); traversals=[t for e in episodes for t in e["traversals"]]; half_hours=[t["hours"] for t in traversals]; moves=[t["gross_move_percent"] for t in traversals]
    complete=[]
    for e in episodes:
        ts=e["traversals"]
        complete += [ts[j]["hours"]+ts[j+1]["hours"] for j in range(0,len(ts)-1,2) if ts[j]["direction"]!=ts[j+1]["direction"]]
    sample=_sample_quality(len(episodes),len(traversals),cfg); covered=sum(e["completed_bar_count"] for e in episodes); occupancy=100*covered/max(1,len(frame))
    cv=_cv(complete); move_cv=_cv(moves); midpoint_n=sum(t["midpoint_crossed"] for t in traversals); full_n=sum(t["opposite_boundary_reached"] for t in traversals)
    false_n=sum(e["false_breakouts"]+e["false_breakdowns"] for e in episodes); failures=sum(e["confirmed_breakouts"]+e["confirmed_breakdowns"] for e in episodes)
    widths=[e["width_percent"] for e in episodes]; durations=[e["calendar_duration_hours"] for e in episodes]; directional=float(np.median([e["directional_efficiency_ratio"] for e in episodes])) if episodes else (abs(float(frame.close.iloc[-1]-frame.close.iloc[0]))/max(float(frame.close.diff().abs().sum()),1e-12) if len(frame)>1 else 0)
    returns=frame.close.pct_change().dropna(); spike_rate=float((returns.abs()>max(.03,returns.abs().median()*6)).mean()) if len(returns) else 0
    liq=liquidity or {}; liquidity_pass=bool(liq.get("liquidity_pass",True)) and bool(liq.get("spread_pass",True)); fresh=quality_meta.get("freshness")
    components={"historical_range_occupancy":_clip(occupancy*1.35),"cycle_duration_regularity":_clip(100*(1-(cv if cv is not None else 1))),
        "move_size_regularity":_clip(100*(1-(move_cv if move_cv is not None else 1))),"midpoint_recovery":100*midpoint_n/max(1,len(traversals)),
        "full_traversal_completion":100*full_n/max(1,len(traversals)),"episode_persistence":_clip((_med(durations) or 0)/240*100),
        "liquidity_data_quality":100 if liquidity_pass and fresh!="STALE" else 30,"episode_consistency":_clip(100*(1-(_cv(widths) if _cv(widths) is not None else 1)))}
    score=sum(components[k]*w/100 for k,w in cfg["score_weights"].items()); penalties={}
    def pen(name,condition,scale=1):
        nonlocal score
        if condition: penalties[name]=cfg["penalties"][name]*scale; score-=penalties[name]
    pen("false_breaks",false_n/max(1,len(traversals))>.3); pen("confirmed_failures",failures/max(1,len(episodes))>.35); pen("trend_persistence",directional>.45)
    pen("spikes",spike_rate>.08); pen("poor_liquidity",not liquidity_pass); pen("stale_data",fresh=="STALE"); pen("low_sample",sample in {"LOW","INSUFFICIENT"})
    pen("unstable_cycle",cv is None or cv>.75); pen("unstable_width",_cv(widths) is None or _cv(widths)>.5); score=round(_clip(score),2)
    failure_rate=failures/max(1,len(episodes)); cls_cfg=cfg["classification"]
    if sample=="INSUFFICIENT": classification="INSUFFICIENT_DATA"
    elif not liquidity_pass and score>=35: classification="LOW_LIQUIDITY_RANGE"
    elif failure_rate>=cls_cfg["breakout_failure_rate"]: classification="BREAKOUT_PRONE"
    elif spike_rate>=cls_cfg["chaos_spike_rate"] or (cv is not None and cv>=cls_cfg["chaos_cycle_cv"]): classification="CHAOTIC"
    elif directional>=cls_cfg["trend_efficiency"] and occupancy<45: classification="TREND_DOMINANT"
    elif score>=cls_cfg["specialist_score"] and len(episodes)>=4: classification="RANGE_SPECIALIST"
    elif score>=cls_cfg["friendly_score"]: classification="RANGE_FRIENDLY"
    else: classification="MIXED_BEHAVIOR" if occupancy>=20 else "TREND_DOMINANT"
    midpoint_rate=_rate(midpoint_n,len(traversals),sample); traversal_rate=_rate(full_n,len(traversals),sample); false_rate=_rate(false_n,false_n+len(traversals),sample); confirmed_rate=_rate(failures,len(episodes),sample)
    lth=[t["hours"] for t in traversals if t["direction"]=="LOW_TO_HIGH"]; htl=[t["hours"] for t in traversals if t["direction"]=="HIGH_TO_LOW"]
    result={"asset":asset,"classification":classification,"range_personality_score":score,"historical_coverage_days":quality_meta.get("available_historical_coverage_days"),
        "valid_range_episodes":len(episodes),"historical_range_occupancy_pct":round(occupancy,2),"complete_cycles":len(complete),"half_cycles":len(traversals),
        "cycles_per_30d":round(len(complete)*30/max(1,quality_meta.get("available_historical_coverage_days") or 1),2),"median_cycle_hours":_med(complete),"average_cycle_hours":_mean(complete),
        "median_low_to_high_hours":_med(lth),"median_high_to_low_hours":_med(htl),"cycle_duration_std":None if not complete else float(np.std(complete)),"cycle_duration_cv":cv,
        "cycle_duration_iqr":None if not complete else float(np.percentile(complete,75)-np.percentile(complete,25)),"cycles_within_25pct_median_rate":None if not complete else round(100*sum(abs(x-median(complete))<=median(complete)*.25 for x in complete)/len(complete),2),
        "median_cycle_move_pct":_med(moves),"average_cycle_move_pct":_mean(moves),"move_size_std":None if not moves else float(np.std(moves)),"move_size_cv":move_cv,
        "cycles_in_2_to_4_pct_band":None if not moves else round(100*sum(2<=x<=4 for x in moves)/len(moves),2),"cycles_in_1_to_5_pct_band":None if not moves else round(100*sum(1<=x<=5 for x in moves)/len(moves),2),
        "median_maximum_adverse_movement":_med([t["maximum_adverse_movement"] for t in traversals]),"historical_midpoint_recovery_rate":midpoint_rate["rate_pct"],
        "historical_full_traversal_rate":traversal_rate["rate_pct"],"false_break_rate":false_rate["rate_pct"],"confirmed_failure_rate":confirmed_rate["rate_pct"],
        "historical_midpoint_recovery_evidence":midpoint_rate,"historical_full_traversal_evidence":traversal_rate,"false_break_evidence":false_rate,"confirmed_failure_evidence":confirmed_rate,
        "directional_efficiency_ratio":round(directional,4),"trend_persistence":round(directional,4),"one_candle_spike_frequency":round(spike_rate,4),
        "median_quote_volume":liq.get("kraken_24h_quote_volume"),"median_spread":liq.get("bid_ask_spread_pct"),"liquidity_status":"PASS" if liquidity_pass else "FAIL",
        "low_liquidity_flag":not liquidity_pass,"stale_data_flag":fresh=="STALE","insufficient_history_flag":sample=="INSUFFICIENT","sample_quality":sample,
        "score_components":components,"score_penalties":penalties,"primary_risk":max(penalties,key=penalties.get,default="LOW_SAMPLE_UNCERTAINTY"),
        "research_interpretation":"HISTORICALLY_"+classification,"probability_of_profit_claim":False,**quality_meta}
    return result


def analyze_asset(frame: pd.DataFrame, asset: str, as_of: Any = None, liquidity: dict[str, Any] | None = None,
                  source_file: str = "synthetic", source_timeframe: str = "4H", config: dict[str, Any] | None = None) -> tuple[dict[str, Any],list[dict[str,Any]]]:
    cfg=config or load_config(); x=_clean_4h(frame,as_of); meta=data_quality(x,as_of,source_file,source_timeframe)
    if len(x)<cfg["data"]["min_4h_bars"]:
        row={"asset":asset,"classification":"INSUFFICIENT_DATA","range_personality_score":0.0,"valid_range_episodes":0,"complete_cycles":0,"sample_quality":"INSUFFICIENT","liquidity_status":"UNKNOWN","insufficient_history_flag":True,**meta}
        return row,[]
    episodes=detect_range_episodes(x,asset,cfg); return summarize_personality(asset,x,episodes,meta,liquidity,cfg),episodes


def personality_change(recent: dict[str,Any]|None, medium: dict[str,Any]|None, long: dict[str,Any]) -> str:
    if not recent or not medium or recent.get("classification")=="INSUFFICIENT_DATA": return "INSUFFICIENT_HISTORY_FOR_CHANGE"
    rc=recent.get("classification"); delta=(recent.get("range_personality_score") or 0)-(medium.get("range_personality_score") or 0)
    if rc=="TREND_DOMINANT" and medium.get("classification") not in {"TREND_DOMINANT","INSUFFICIENT_DATA"}: return "SHIFTING_TO_TREND"
    if rc=="CHAOTIC" and medium.get("classification")!="CHAOTIC": return "SHIFTING_TO_CHAOS"
    if delta>=10:return "IMPROVING_RANGE_PERSONALITY"
    if delta<=-10:return "DETERIORATING_RANGE_PERSONALITY"
    return "STABLE_RANGE_PERSONALITY"


def current_intersection(row: dict[str,Any], current: dict[str,Any] | None) -> dict[str,Any]:
    current=current or {}; active=bool(current.get("range_still_valid",current.get("is_valid_horizontal_consolidation",False)))
    strong=row.get("classification") in {"RANGE_SPECIALIST","RANGE_FRIENDLY"}; change=row.get("personality_change")
    if active and change in {"DETERIORATING_RANGE_PERSONALITY","SHIFTING_TO_TREND","SHIFTING_TO_CHAOS"}: state="CURRENT_RANGE_PERSONALITY_DETERIORATING"
    elif active and strong: state="HISTORICALLY_STRONG_AND_CURRENTLY_ACTIVE"
    elif active: state="CURRENT_RANGE_BUT_WEAK_HISTORY"
    elif strong: state="HISTORICALLY_STRONG_NO_CURRENT_RANGE"
    else: state="NO_CURRENT_RANGE"
    position=float(current.get("position_pct",50) or 50); position_score=max(0,100-abs(position-25)*2); quality=float(current.get("range_quality",0) or 0)
    cycle=100 if row.get("median_cycle_hours") and 24<=row["median_cycle_hours"]<=96 else 50
    freshliq=100 if row.get("freshness")=="FRESH" and row.get("liquidity_status")=="PASS" else 40
    priority=round(.4*(row.get("range_personality_score") or 0)+.25*quality+.15*position_score+.1*cycle+.1*freshliq,2) if active else None
    return {"current_range_status":current.get("position_zone",current.get("simple_zone","NO_ACTIVE_RANGE" if not active else "ACTIVE_RANGE")),
            "current_setup_source":"existing_consolidation_engine" if current else "unavailable","intersection_state":state,"range_research_priority_score":priority}


def _load_source(pair: str, as_of: Any) -> tuple[pd.DataFrame,str,str]:
    try:
        from consolidation_range_engine import completed_4h_bars
    except ModuleNotFoundError:
        from scripts.consolidation_range_engine import completed_4h_bars
    candidates=[(INTRADAY_DIR/f"{pair}_4H.csv","4H"),(INTRADAY_DIR/f"{pair}_1H.csv","1H")]
    for path,tf in candidates:
        if path.exists():
            raw=pd.read_csv(path); return completed_4h_bars(raw,as_of,tf),str(path),tf
    raise FileNotFoundError(f"no native intraday source for {pair}")


def _window_profile(frame: pd.DataFrame, days: int, asset: str, as_of: Any, liq: dict[str,Any], cfg: dict[str,Any]) -> dict[str,Any] | None:
    cutoff=utc_timestamp(as_of)-timedelta(days=days); part=frame[frame.timestamp>=cutoff]
    if not len(part):return None
    return analyze_asset(part,asset,as_of,liq,"window","4H",cfg)[0]


def _hall_lists(rows: list[dict[str,Any]]) -> dict[str,list[dict[str,Any]]]:
    ranked=sorted(rows,key=lambda r:({"HIGH":3,"MEDIUM":2,"LOW":1}.get(r.get("sample_quality"),0),r.get("range_personality_score") or 0),reverse=True)
    eligible=[r for r in ranked if r.get("classification")!="INSUFFICIENT_DATA"]
    return {"top_20_historical_range_personalities":eligible[:20],
        "top_10_fastest_stable_cycles":sorted([r for r in eligible if (r.get("cycle_duration_cv") or 99)<.5 and r.get("median_cycle_hours")],key=lambda r:r["median_cycle_hours"])[:10],
        "top_10_most_regular_cycles":sorted([r for r in eligible if r.get("cycle_duration_cv") is not None],key=lambda r:r["cycle_duration_cv"])[:10],
        "top_10_deteriorating_personalities":[r for r in ranked if r.get("personality_change") in {"DETERIORATING_RANGE_PERSONALITY","SHIFTING_TO_TREND","SHIFTING_TO_CHAOS"}][:10],
        "top_10_insufficient_data_candidates_worth_collecting":[r for r in rows if r.get("classification")=="INSUFFICIENT_DATA"][:10]}


def _write_outputs(rows: list[dict[str,Any]], episodes: list[dict[str,Any]], cutoff: pd.Timestamp, errors: list[str]) -> None:
    REPORT_DIR.mkdir(parents=True,exist_ok=True); HISTORY_DIR.mkdir(parents=True,exist_ok=True); frame=pd.DataFrame(rows); date=cutoff.strftime("%Y-%m-%d")
    hall=_hall_lists(rows); cspr=next((r for r in rows if r.get("asset")=="CSPR"),None)
    payload={"generated_at_utc":cutoff.isoformat(),"labels":LABELS,"methodology":"HISTORICAL_RESEARCH_CLASSIFICATION_NOT_SIGNAL","assets":rows,"range_hall_of_fame":hall,"CSPR_research_diagnostic":cspr,"errors":errors}
    csv=frame.to_csv(index=False); js=json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+"\n"
    md=["# Range Personality Engine V1","",f"Generated: {cutoff.isoformat()}","",*LABELS,"","Range Hall of Fame is historical research, not a current buy list.",""]
    md += [f"- #{i} {r['asset']} | {r.get('classification')} | score {r.get('range_personality_score')} | sample {r.get('sample_quality')}" for i,r in enumerate(hall["top_20_historical_range_personalities"],1)]
    md_text="\n".join(md)+"\n"
    for suffix,content in (("csv",csv),("json",js),("md",md_text)):
        atomic_write(REPORT_DIR/f"{date}_range_personality.{suffix}",content); atomic_write(REPORT_DIR/f"latest_range_personality.{suffix}",content,backup=False)
    history=HISTORY_DIR/"range_personality_history.csv"; old=pd.read_csv(history) if history.exists() else pd.DataFrame(); snapshot=frame.copy(); snapshot.insert(0,"as_of",cutoff.isoformat()); atomic_write(history,pd.concat([old,snapshot],ignore_index=True).to_csv(index=False),backup=False)
    write_json(HISTORY_DIR/"range_episode_history.json",{"generated_at_utc":cutoff.isoformat(),"episodes":episodes},backup=False)
    write_json(HISTORY_DIR/"range_personality_state.json",{"generated_at_utc":cutoff.isoformat(),"assets":{r["asset"]:{"classification":r.get("classification"),"score":r.get("range_personality_score"),"personality_change":r.get("personality_change")} for r in rows}},backup=False)
    write_json(REGISTRY_PATH,build_registry(rows,cutoff.isoformat(),errors),backup=False)


def run(as_of: Any=None, assets: list[str]|None=None, top_universe: int=150, no_network: bool=False,
        reuse_existing_data: bool=False, verbose: bool=False) -> dict[str,Any]:
    del no_network,reuse_existing_data
    cfg=load_config(); cutoff=utc_timestamp(as_of); universe=pd.read_csv(UNIVERSE_PATH)
    if "symbol" not in universe:raise ValueError("corrupted universe")
    if assets: universe=universe[universe.symbol.astype(str).str.upper().isin(set(assets))]
    else: universe=universe.head(min(150,max(1,top_universe)))
    current=pd.read_csv(CURRENT_RANGE_PATH) if CURRENT_RANGE_PATH.exists() else pd.DataFrame(); current_map={str(r.asset):r.where(pd.notna(r),None).to_dict() for _,r in current.iterrows()} if "asset" in current else {}
    rows=[]; all_episodes=[]; errors=[]
    for _,u in universe.iterrows():
        asset=str(u.symbol).upper(); reason=u.get("exclusion_reason")
        if pd.notna(reason) and str(reason): rows.append({"asset":asset,"classification":"INSUFFICIENT_DATA","exclusion_reason":str(reason),"sample_quality":"INSUFFICIENT"}); continue
        try:
            frame,path,tf=_load_source(str(u.get("selected_kraken_pair")),cutoff); long_days=cfg["windows_days"]["long_cap"]; frame=frame[frame.timestamp>=cutoff-timedelta(days=long_days)].reset_index(drop=True)
            liq=u.where(pd.notna(u),None).to_dict(); row,eps=analyze_asset(frame,asset,cutoff,liq,path,tf,cfg)
            recent=_window_profile(frame,30,asset,cutoff,liq,cfg); medium=_window_profile(frame,90,asset,cutoff,liq,cfg)
            row.update({"recent_score":None if not recent else recent.get("range_personality_score"),"medium_score":None if not medium else medium.get("range_personality_score"),"long_score":row.get("range_personality_score")})
            scores=[x for x in (row["recent_score"],row["medium_score"],row["long_score"]) if x is not None]; row["score_stability"]=None if len(scores)<2 else round(max(0,100-float(np.std(scores))*3),2)
            row["personality_agreement_across_windows"]=bool(recent and medium and recent.get("classification")==medium.get("classification")==row.get("classification")); row["personality_change"]=personality_change(recent,medium,row)
            row.update(current_intersection(row,current_map.get(asset))); rows.append(row); all_episodes.extend(eps)
            if verbose: print(f"{asset}: {row['classification']} {row.get('range_personality_score')}")
        except Exception as exc:
            errors.append(f"{asset}: {exc}"); rows.append({"asset":asset,"classification":"INSUFFICIENT_DATA","status":"UNAVAILABLE","error_reason":str(exc),"sample_quality":"INSUFFICIENT"})
    if not any(r.get("completed_bar_count",0) for r in rows): raise RuntimeError("no valid intraday data across universe")
    ranked=sorted(rows,key=lambda r:({"HIGH":3,"MEDIUM":2,"LOW":1}.get(r.get("sample_quality"),0),r.get("range_personality_score") or 0),reverse=True)
    for rank,r in enumerate(ranked,1):r["rank"]=rank
    _write_outputs(ranked,all_episodes,cutoff,errors); return {"assets":ranked,"episodes":all_episodes,"errors":errors}


def main() -> None:
    p=argparse.ArgumentParser(description="Historical Range Personality research classifier")
    p.add_argument("--assets");p.add_argument("--top-universe",type=int,default=150);p.add_argument("--as-of");p.add_argument("--reuse-existing-data",action="store_true");p.add_argument("--no-network",action="store_true");p.add_argument("--verbose",action="store_true")
    a=p.parse_args(); chosen=[x.strip().upper() for x in a.assets.split(",") if x.strip()] if a.assets else None
    result=run(a.as_of,chosen,a.top_universe,a.no_network,a.reuse_existing_data,a.verbose); print(f"Range personality complete | assets {len(result['assets'])} | episodes {len(result['episodes'])} | failures {len(result['errors'])}")


if __name__=="__main__": main()
