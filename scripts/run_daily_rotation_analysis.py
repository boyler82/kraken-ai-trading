from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from btc_rotation_engine import DEFAULTS,LABELS,allocation_review_band,alt_rotation_score,btc_hold_score,choose_state,risk_flags,rotation_controls,rotation_disposition,rotation_features,theoretical_edge
from btc_rotation_paper_tracker import controls_from_state,load_state,record_paper_review
from daily_momentum_breakout_radar import _hourly_for
from weekly_consolidation_common import ROOT,atomic_write,utc_timestamp,write_json

REPORT_DIR=ROOT/"DAILY_REPORTS"/"BTC_ROTATION";UNIVERSE=ROOT/"DATASETS/universe/weekly_consolidation_universe.csv";MOMENTUM=ROOT/"DAILY_REPORTS/MOMENTUM_BREAKOUT/latest_momentum_breakout_radar.csv";CONSOLIDATION=ROOT/"DAILY_REPORTS/DAILY_CONSOLIDATION/latest_daily_consolidation_scan.csv"


def _records(path:Path)->list[dict[str,Any]]:
    if not path.exists(): return []
    return pd.read_csv(path).replace({float("nan"):None}).to_dict("records")


def _regime(date_text:str)->str:
    path=ROOT/"DAILY_REPORTS"/f"{date_text}_research_regime.csv"
    if not path.exists(): return "UNKNOWN"
    frame=pd.read_csv(path); row=frame[frame["metric"]=="crypto_regime"]
    return str(row.iloc[0]["value"]) if len(row) else "UNKNOWN"


def _usd_score(features:dict[str,Any],context:dict[str,Any])->float:
    trend=30 if features.get("price_vs_ema20_pct",0)>0 and features.get("price_vs_ema50_pct",0)>0 else 10
    momentum=max(0,min(30,15+(features.get("absolute_return_24h_pct") or 0)*3))
    quality=float(context.get("momentum_breakout_score") or 0)*.25
    safety=15 if context.get("freshness_status")=="FRESH" and context.get("liquidity_pass") else 0
    penalty=20 if context.get("overextension_risk")=="HIGH" else 0
    return round(max(0,min(100,trend+momentum+quality+safety-penalty)),4)


def analyze(objective:str="btc",current_holding:str="BTC",as_of:Any=None,allocation_reference:float|None=None,use_portfolio:bool=False)->dict[str,Any]:
    objective=objective.lower();holding=current_holding.upper() if use_portfolio else "BTC";cutoff=utc_timestamp(as_of);date_text=cutoff.strftime("%Y-%m-%d")
    if objective not in {"btc","usd"}: raise ValueError("objective must be btc or usd")
    universe=pd.read_csv(UNIVERSE); included=universe[universe["inclusion_status"]=="INCLUDED"]
    btcrow=included[included["symbol"]=="BTC"];btc_pair=str(btcrow.iloc[0]["selected_kraken_pair"] if len(btcrow) else "XBTUSD")
    btc_bars=_hourly_for("BTC",btc_pair,cutoff);btc_features=rotation_features(btc_bars,btc_bars)
    momentum={str(r["asset"]):r for r in _records(MOMENTUM)}; consolidation={str(r["asset"]):r for r in _records(CONSOLIDATION)}
    feature_rows=[]
    for _,item in included.iterrows():
        asset=str(item["symbol"])
        if asset=="BTC":continue
        try:
            bars=_hourly_for(asset,str(item["selected_kraken_pair"]),cutoff);features=rotation_features(bars,btc_bars)
            context={**consolidation.get(asset,{}),**momentum.get(asset,{})}
            context.update({"liquidity_pass":bool(item.get("liquidity_pass")),"spread_pass":bool(item.get("spread_pass")),"bid_ask_spread_pct":item.get("bid_ask_spread_pct"),"freshness_status":context.get("freshness_status","UNAVAILABLE")})
            feature_rows.append({"asset":asset,"kraken_pair":str(item["selected_kraken_pair"]),"features":features,"context":context})
        except Exception:continue
    btc_score,btc_parts,btc_environment=btc_hold_score(btc_features,[r["features"] for r in feature_rows],_regime(date_text),True)
    paper=load_state();paper_controls=controls_from_state(paper,cutoff)
    scored=[]
    for item in feature_rows:
        asset,features,context=item["asset"],item["features"],item["context"]
        score,parts,penalties=alt_rotation_score(features,context);edge=theoretical_edge(features,DEFAULTS["fees_pct"]+DEFAULTS["slippage_pct"])
        flags=risk_flags(features,context,paper_controls["rotations_7d"])
        if edge["confidence"]=="LOW": flags.append("LOW_CONFIDENCE")
        flags=sorted(set(flags))
        objective_score=score if objective=="btc" else _usd_score(features,context)
        baseline=btc_score if holding=="BTC" else (max(0,100-btc_score) if holding=="USD" else btc_score)
        advantage=objective_score-baseline;controls=rotation_controls(advantage,edge["net_relative_upside_after_costs"],**paper_controls)
        critical=bool(flags) or edge["confidence"]=="LOW" or context.get("overextension_risk")=="HIGH" or controls["overtrading_risk"]=="HIGH"
        scored.append({"asset":asset,"kraken_pair":item["kraken_pair"],"current_holding":holding,"objective":"BTC_ACCUMULATION" if objective=="btc" else "USD_GROWTH","alt_rotation_score":score,"objective_score":objective_score,"btc_hold_score":btc_score,"score_advantage":advantage,"relative_trend_state":features["relative_trend_state"],"momentum_stage":context.get("momentum_stage","UNKNOWN"),"consolidation_zone":context.get("simple_zone",context.get("position_zone","UNKNOWN")),"breakout_status":"FAILED" if context.get("failed_breakout") else "CONFIRMED" if context.get("close_above_previous_7d_high") else "NONE","volume_confirmation":context.get("volume_z_score"),"overextension_risk":context.get("overextension_risk","UNKNOWN"),"liquidity_pass":context.get("liquidity_pass"),"spread_pct":context.get("bid_ask_spread_pct"),"freshness_status":context.get("freshness_status"),"source_timestamp":features["source_timestamp"],**{k:v for k,v in features.items() if k.startswith("relative_return_")},**edge,"alt_score_components":parts,"alt_score_penalties":penalties,"risk_flags":flags,"critical_risk":critical,"controls":controls,"current_holding_context":features,"allocation_review_band":"NONE","scenario_base":{"expected_relative_path":"Continuation only while ALT/BTC remains above EMA20","probability_band":edge["probability_band"],"target_relative_move_pct":edge["theoretical_relative_upside_to_target_pct"],"holding_horizon":edge["expected_holding_window"]},"scenario_optimistic":{"continuation_conditions":"Positive relative EMA20 slope with volume confirmation","upper_relative_target_pct":edge["theoretical_relative_upside_to_target_pct"]*1.5},"scenario_pessimistic":{"invalidation_condition":edge["invalidation_condition"],"expected_relative_loss_pct":edge["theoretical_relative_downside_to_invalidation_pct"]},"unknowns":["No validated historical event sample","Regime transition uncertainty","Model probability unavailable"]})
    baseline = btc_score if holding=="BTC" else max(0,100-btc_score) if holding=="USD" else next((r["objective_score"] for r in scored if r["asset"]==holding),btc_score)
    for row in scored:
        row["score_advantage"]=row["objective_score"]-baseline
        row["controls"]=rotation_controls(row["score_advantage"],row["net_relative_upside_after_costs"],**paper_controls)
        row["candidate_disposition"],row["rejection_reasons"]=rotation_disposition(row)
        row["critical_risk"]=bool(row["risk_flags"]) or row["confidence"]=="LOW" or row["overextension_risk"]=="HIGH" or row["controls"]["overtrading_risk"]=="HIGH"
        row["user_facing_rotation_state"]=choose_state(objective,holding,btc_score,row,row["controls"],_regime(date_text),not use_portfolio)
    scored=sorted(scored,key=lambda r:(-r["objective_score"],-r["score_advantage"],r["asset"]))
    for i,row in enumerate(scored,1):row["rank"]=i;row["allocation_review_band"]=allocation_review_band(row)
    best=scored[0] if scored else None;controls=best["controls"] if best else rotation_controls(0,0,**paper_controls)
    best_for_state=dict(best) if best else None
    if best_for_state is not None and holding not in {"BTC","USD"}:
        held=next((r for r in scored if r["asset"]==holding),None)
        best_for_state["current_holding_context"]={} if held is None else held["current_holding_context"]
    preferred=choose_state(objective,holding,btc_score,best_for_state,controls,_regime(date_text),not use_portfolio)
    conclusion="BTC remains preferred after costs." if preferred=="HOLD_BTC" else "No rotation clears confidence and cost controls." if preferred=="NO_ROTATION" else "MANUAL_REVIEW_REQUIRED"
    dashboard={"report_timestamp":cutoff.isoformat(),"labels":LABELS,"objective":"BTC_ACCUMULATION" if objective=="btc" else "USD_GROWTH","current_holding":holding,"available_capital_reference":allocation_reference,"btc_hold_score":btc_score,"btc_hold_environment":btc_environment,"btc_hold_score_components":btc_parts,"market_regime":_regime(date_text),"preferred_state":preferred,"top_candidates":scored[:3],"best_score_advantage":best["score_advantage"] if best else None,"rotation_cost_guard":controls["rotation_cost_guard"],"rotation_cooldown_status":controls["rotation_cooldown_status"],"rotation_hysteresis_status":controls["rotation_hysteresis_status"],"overtrading_risk":controls["overtrading_risk"],"data_freshness":best["freshness_status"] if best else "UNAVAILABLE","confidence":best["confidence"] if best else "LOW","main_invalidation_condition":best["invalidation_condition"] if best else "n/a","suggested_manual_review_band":allocation_review_band(best),"conclusion":conclusion,"candidate_count":len(scored),"source_files":[str(UNIVERSE),str(MOMENTUM),str(CONSOLIDATION),str(ROOT/"DATASETS/market_intraday_weekly"/"*_1H.csv"),str(ROOT/"DATASETS/BTC_4H_DONCHIAN_V1/BTCUSD_15m_operational.csv")]}
    dashboard["research_mode"]="PORTFOLIO" if use_portfolio else "MARKET_ONLY"
    dashboard["benchmark_asset"]="BTC"
    dashboard["portfolio_context_status"]="AVAILABLE" if use_portfolio else "INTENTIONALLY_ABSENT_MARKET_ONLY"
    if not use_portfolio:dashboard.pop("current_holding",None)
    return {"dashboard":dashboard,"candidates":scored}


def _flat_candidate(row:dict[str,Any])->dict[str,Any]:
    out={k:v for k,v in row.items() if not isinstance(v,(dict,list))};out["risk_flags"]="|".join(row["risk_flags"])
    out.update({f"score_{k}":v for k,v in row["alt_score_components"].items()});out.update({f"penalty_{k}":v for k,v in row["alt_score_penalties"].items()});out.update(row["controls"]);return out


def write_reports(result:dict[str,Any],as_of:Any=None)->None:
    dashboard=result["dashboard"];rows=result["candidates"];cutoff=utc_timestamp(as_of or dashboard["report_timestamp"]);date=cutoff.strftime("%Y-%m-%d");REPORT_DIR.mkdir(parents=True,exist_ok=True)
    dashbase=REPORT_DIR/f"{date}_btc_rotation_dashboard";candbase=REPORT_DIR/f"{date}_btc_rotation_candidates"
    atomic_write(dashbase.with_suffix(".csv"),pd.DataFrame([{k:v for k,v in dashboard.items() if not isinstance(v,(dict,list))}]).to_csv(index=False));write_json(dashbase.with_suffix(".json"),dashboard)
    lines=["# BTC Rotation Engine", "",*LABELS,"",f"Objective: {dashboard['objective']}",f"Benchmark: {dashboard.get('current_holding','BTC')}",f"Preferred state: {dashboard['preferred_state']}",f"BTC hold score: {dashboard['btc_hold_score']:.2f}",f"Market regime: {dashboard['market_regime']}","","## Top candidates",""]+[f"- #{r['rank']} {r['asset']} | score {r['alt_rotation_score']:.2f} | advantage {r['score_advantage']:+.2f} | net edge {r['net_relative_upside_after_costs']:+.2f}% | confidence {r['confidence']}" for r in rows[:3]]+["","MANUAL_REVIEW_REQUIRED","RESEARCH_ONLY"]
    atomic_write(dashbase.with_suffix(".md"),"\n".join(lines)+"\n")
    atomic_write(candbase.with_suffix(".csv"),pd.DataFrame([_flat_candidate(r) for r in rows]).to_csv(index=False));write_json(candbase.with_suffix(".json"),{"report_timestamp":dashboard["report_timestamp"],"labels":LABELS,"candidates":rows});atomic_write(candbase.with_suffix(".md"),"# BTC Rotation Candidates\n\n"+"\n".join(f"- #{r['rank']} {r['asset']} | {r['objective']} | score {r['alt_rotation_score']:.2f} | risks {','.join(r['risk_flags']) or 'none'}" for r in rows)+"\n")
    for ext in (".csv",".md",".json"):atomic_write(REPORT_DIR/f"latest_btc_rotation_dashboard{ext}",dashbase.with_suffix(ext).read_text(),backup=False)
    handoff={k:dashboard.get(k) for k in ("report_timestamp","objective","current_holding","available_capital_reference","btc_hold_score","btc_hold_score_components","market_regime","preferred_state","best_score_advantage","rotation_cost_guard","rotation_cooldown_status","data_freshness","confidence","main_invalidation_condition","source_files")};handoff["top_candidates"]=rows[:3];handoff["unknowns"]=rows[0]["unknowns"] if rows else ["No eligible candidates"]
    handoff["benchmark_asset"]=dashboard["benchmark_asset"];handoff["portfolio_context_status"]=dashboard["portfolio_context_status"]
    write_json(REPORT_DIR/"latest_rotation_analyst_handoff.json",handoff,backup=False);atomic_write(REPORT_DIR/"latest_rotation_analyst_handoff.md",render_handoff(handoff),backup=False)


def render_handoff(h:dict[str,Any])->str:
    holding=h.get("current_holding")
    holding_text=holding if holding is not None else f"not applicable ({h.get('portfolio_context_status','MARKET_ONLY')}; benchmark {h.get('benchmark_asset','BTC')})"
    lines=["# BTC Rotation Analyst Handoff", "",f"Report timestamp: {h['report_timestamp']}",f"Objective: {h['objective']}",f"Current holding: {holding_text}",f"Capital reference: {h.get('available_capital_reference') or 'not provided'}",f"BTC hold score: {h['btc_hold_score']}",f"Market regime: {h['market_regime']}",f"Preferred state: {h['preferred_state']}",f"Cost guard: {h['rotation_cost_guard']}",f"Cooldown: {h['rotation_cooldown_status']}",f"Confidence: {h['confidence']}",f"Invalidation: {h['main_invalidation_condition']}","","## Top candidates",""]
    for r in h["top_candidates"]:lines.append(f"- {r['asset']} | score {r['alt_rotation_score']} | advantage {r['score_advantage']:+.2f} | relative 24h {r.get('relative_return_24h_pct')}% | upside/downside {r['theoretical_relative_upside_to_target_pct']:.2f}%/{r['theoretical_relative_downside_to_invalidation_pct']:.2f}% | R/R {r['relative_risk_reward']} | costs {r['estimated_round_trip_cost_pct']}% | sample {r['historical_sample_size']} | confidence {r['confidence']} | risks {','.join(r['risk_flags']) or 'none'}")
    lines += ["","## Unknowns",""]+[f"- {x}" for x in h["unknowns"]]+["","## Exact source files",""]+[f"- {x}" for x in h["source_files"]]+["","MANUAL_REVIEW_REQUIRED","RESEARCH_ONLY"]
    return "\n".join(lines)+"\n"


def main()->None:
    p=argparse.ArgumentParser();p.add_argument("--objective",choices=["btc","usd"],default="btc");p.add_argument("--current-holding",default="BTC");p.add_argument("--as-of");p.add_argument("--no-network",action="store_true");p.add_argument("--reuse-existing-data",action="store_true");p.add_argument("--record-paper-review",action="store_true");p.add_argument("--allocation-reference",type=float);p.add_argument('--use-portfolio',action='store_true');a=p.parse_args()
    result=analyze(a.objective,a.current_holding,a.as_of,a.allocation_reference,a.use_portfolio);write_reports(result,a.as_of)
    if a.record_paper_review:record_paper_review({"candidate":result["candidates"][0]["asset"] if result["candidates"] else None,"preferred_state":result["dashboard"]["preferred_state"],"estimated_round_trip_cost_pct":DEFAULTS["fees_pct"]+DEFAULTS["slippage_pct"]},a.as_of)
    d=result["dashboard"];holding=d.get("current_holding") or f"N/A ({d['portfolio_context_status']})";print(f"BTC Rotation Engine | objective {d['objective']} | holding {holding} | BTC score {d['btc_hold_score']:.2f} | state {d['preferred_state']} | candidates {d['candidate_count']}")


if __name__=="__main__":main()
