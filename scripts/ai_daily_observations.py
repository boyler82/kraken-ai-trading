from __future__ import annotations

import argparse
import json
import math
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PACKET_DIR = ROOT / "DAILY_REPORTS/CHATGPT_EXPORT"
DEFAULT_CURRENT = PACKET_DIR / "latest_ai_chief_strategist_packet.json"
OUT_DIR = ROOT / "DAILY_REPORTS/AI_DAILY_OBSERVATIONS"
JOURNAL_PATH = ROOT / "AI_DAILY_OBSERVATIONS.md"
HISTORY_PATH = ROOT / "DATASETS/AI_DAILY_OBSERVATIONS/observations_history.jsonl"
LABELS = ["RESEARCH_ONLY", "NOT_A_BUY_SIGNAL", "NOT_A_SELL_SIGNAL", "USER_DECISION_REQUIRED"]
DATED_PACKET = re.compile(r"^(\d{4}-\d{2}-\d{2})_ai_chief_strategist_packet\.json$")


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text)
    os.replace(temporary, path)


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict): raise ValueError(f"packet is not an object: {path}")
    return data


def packet_date(path: Path, data: dict[str, Any] | None = None) -> str | None:
    match = DATED_PACKET.match(path.name)
    return (data or {}).get("report_date") or (match.group(1) if match else None)


def select_previous_packet(current_path: Path, current: dict[str, Any], explicit: Path | None = None) -> Path | None:
    current_resolved = current_path.resolve(); current_date = packet_date(current_path, current)
    if explicit:
        if explicit.resolve() == current_resolved: raise ValueError("previous packet cannot be the current packet")
        previous = read_json(explicit)
        if current_date and packet_date(explicit, previous) and packet_date(explicit, previous) >= current_date:
            raise ValueError("previous packet must be from an earlier report date")
        return explicit
    choices=[]
    for path in PACKET_DIR.glob("????-??-??_ai_chief_strategist_packet.json"):
        if path.resolve() == current_resolved: continue
        match=DATED_PACKET.match(path.name)
        if match and (not current_date or match.group(1)<current_date): choices.append((match.group(1),path))
    return max(choices,key=lambda x:x[0])[1] if choices else None


def _finite(value: Any) -> Any:
    if isinstance(value,float) and not math.isfinite(value): return None
    if isinstance(value,dict): return {str(k):_finite(v) for k,v in sorted(value.items())}
    if isinstance(value,list): return [_finite(v) for v in value]
    return value


def _num(value: Any) -> float | None:
    try:
        result=float(value)
        return result if math.isfinite(result) else None
    except (TypeError,ValueError): return None


def _candidate_map(packet: dict[str,Any]) -> dict[str,dict[str,Any]]:
    return {str(r.get("asset")):r for r in packet.get("candidates",[]) if r.get("asset")}


def _candidate_state(row: dict[str,Any]) -> str:
    return str(row.get("decision_metrics",{}).get("current_primary_hypothesis") or row.get("momentum",{}).get("stage") or "UNKNOWN")


def _record(asset: str, old: dict[str,Any], new: dict[str,Any], metrics: dict[str,Any], reasons: list[str], direction: str) -> dict[str,Any]:
    text="Evidence strengthened under deterministic material-change rules." if direction=="STRENGTHENING" else "Evidence weakened or risk increased under deterministic material-change rules."
    return {"asset":asset,"previous_state":_candidate_state(old),"current_state":_candidate_state(new),
            "metric_changes":metrics,"reason_codes":sorted(set(reasons)),"interpretation":text}


def compare_candidates(current: dict[str,Any], previous: dict[str,Any]) -> dict[str,list[dict[str,Any]]]:
    cur=_candidate_map(current); old=_candidate_map(previous); new=[]; removed=[]; stronger=[]; weaker=[]; invalid=[]; confirmed=[]; rp=[]
    for asset in sorted(set(cur)-set(old)):
        new.append(_record(asset,{},cur[asset],{},["ENTERED_CANDIDATE_SET"],"STRENGTHENING"))
    for asset in sorted(set(old)-set(cur)):
        removed.append(_record(asset,old[asset],{}, {},["LEFT_CANDIDATE_SET"],"WEAKENING"))
    rs_order={"LEADER":4,"OUTPERFORMER":3,"NEUTRAL":2,"LAGGARD":1,"WEAK":0}
    for asset in sorted(set(cur)&set(old)):
        a,b=old[asset],cur[asset]; reasons_up=[]; reasons_down=[]; metrics={}
        adm=a.get("decision_metrics",{}); bdm=b.get("decision_metrics",{}); ae=a.get("evidence",{}); be=b.get("evidence",{})
        for key,threshold,upcode,downcode in (("decision_impact_score",8,"DECISION_IMPACT_UP","DECISION_IMPACT_DOWN"),("evidence_confidence_score",10,"EVIDENCE_CONFIDENCE_UP","EVIDENCE_CONFIDENCE_DOWN")):
            av,bv=_num(adm.get(key)),_num(bdm.get(key))
            if av is not None and bv is not None and abs(bv-av)>=threshold:
                metrics[key]={"previous":av,"current":bv,"change":round(bv-av,4)};(reasons_up if bv>av else reasons_down).append(upcode if bv>av else downcode)
        ac=len(ae.get("supporting_modules",[]) or []);bc=len(be.get("supporting_modules",[]) or [])
        if ac!=bc: metrics["supporting_module_count"]={"previous":ac,"current":bc,"change":bc-ac};(reasons_up if bc>ac else reasons_down).append("SUPPORTING_MODULES_INCREASED" if bc>ac else "SUPPORTING_MODULES_DECREASED")
        ah,bh=adm.get("current_primary_hypothesis"),bdm.get("current_primary_hypothesis")
        if ah!=bh: metrics["primary_hypothesis"]={"previous":ah,"current":bh}; reasons_down.append("PRIMARY_HYPOTHESIS_CHANGED")
        aa,ba=adm.get("opportunity_age_status"),bdm.get("opportunity_age_status")
        if aa!=ba: metrics["opportunity_age_status"]={"previous":aa,"current":ba}; (reasons_down if ba in {"DECAYING","EXPIRED","INVALIDATED"} else reasons_up).append("OPPORTUNITY_STATUS_WEAKENED" if ba in {"DECAYING","EXPIRED","INVALIDATED"} else "OPPORTUNITY_STATUS_IMPROVED")
        ar,br=a.get("consolidation",{}),b.get("consolidation",{}); av,bv=ar.get("range_validity"),br.get("range_validity")
        if av is not bv and av!=bv:
            metrics["range_validity"]={"previous":av,"current":bv}
            if av is True and bv is not True:
                reasons_down.append("RANGE_INVALIDATED");invalid.append(_record(asset,a,b,metrics,["RANGE_INVALIDATED"],"WEAKENING"))
            elif bv is True: reasons_up.append("RANGE_VALIDATED")
        am,bm=a.get("momentum",{}),b.get("momentum",{}); ast,bst=am.get("stage"),bm.get("stage")
        if ast!=bst:
            metrics["momentum_stage"]={"previous":ast,"current":bst}
            if bst in {"BREAKOUT_CONFIRMED","CONFIRMED_BREAKOUT"}: reasons_up.append("BREAKOUT_CONFIRMED");confirmed.append(_record(asset,a,b,metrics,["BREAKOUT_CONFIRMED"],"STRENGTHENING"))
            if bst in {"FAILED_BREAKOUT","BREAKOUT_FAILED"}: reasons_down.append("BREAKOUT_FAILED")
        ars,brs=a.get("relative_strength",{}).get("relative_trend"),b.get("relative_strength",{}).get("relative_trend")
        if ars!=brs and (ars is not None or brs is not None):
            metrics["relative_strength"]={"previous":ars,"current":brs}; (reasons_up if rs_order.get(str(brs),2)>rs_order.get(str(ars),2) else reasons_down).append("RELATIVE_STRENGTH_IMPROVED" if rs_order.get(str(brs),2)>rs_order.get(str(ars),2) else "RELATIVE_STRENGTH_DETERIORATED")
        arp,brp=a.get("range_personality",{}),b.get("range_personality",{}); ap,bp=arp.get("classification"),brp.get("classification")
        if ap!=bp and (ap is not None or bp is not None):
            metrics["range_personality"]={"previous":ap,"current":bp};rp.append({"asset":asset,"previous_classification":ap,"current_classification":bp,"reason_code":"RANGE_PERSONALITY_CLASS_CHANGED"})
            order={"RANGE_SPECIALIST":5,"RANGE_FRIENDLY":4,"MIXED_BEHAVIOR":3,"TREND_DOMINANT":2,"BREAKOUT_PRONE":1,"CHAOTIC":0,"INSUFFICIENT_DATA":-1}
            (reasons_up if order.get(str(bp),-1)>order.get(str(ap),-1) else reasons_down).append("RANGE_PERSONALITY_IMPROVED" if order.get(str(bp),-1)>order.get(str(ap),-1) else "RANGE_PERSONALITY_DETERIORATED")
        if reasons_up: stronger.append(_record(asset,a,b,metrics,reasons_up,"STRENGTHENING"))
        if reasons_down: weaker.append(_record(asset,a,b,metrics,reasons_down,"WEAKENING"))
    return {"new_candidates":new,"removed_candidates":removed,"strengthening_candidates":stronger,"weakening_candidates":weaker,"new_invalidations":invalid,"new_confirmations":confirmed,"range_personality_changes":rp}


def compare_rqi(current: dict[str,Any], previous: dict[str,Any]) -> list[dict[str,Any]]:
    """Return only material RQI changes; sub-eight-point score noise is ignored."""
    def rows(packet):
        block=packet.get("range_quality_index",{});items=block.get("top_candidates",[])+block.get("deteriorating_ranges",[])
        return {str(x.get("asset")):x for x in items if x.get("asset")}
    cur,old=rows(current),rows(previous);out=[];cur_top=set(list(cur)[:5]);old_top=set(list(old)[:5])
    for asset in sorted(set(cur)|set(old)):
        a,b=old.get(asset,{}),cur.get(asset,{});reasons=[];metrics={};av,bv=_num(a.get("rqi_score")),_num(b.get("rqi_score"))
        if av is not None and bv is not None and abs(bv-av)>=8:reasons.append("RQI_SCORE_CHANGE_AT_LEAST_8");metrics["score"]={"previous":av,"current":bv,"change":round(bv-av,2)}
        for key,code in (("rqi_classification","RQI_CLASSIFICATION_CHANGED"),("rqi_confidence_band","RQI_CONFIDENCE_BAND_CHANGED"),("rqi_status","RQI_STATUS_CHANGED")):
            if a.get(key)!=b.get(key) and (a.get(key) is not None or b.get(key) is not None):reasons.append(code);metrics[key]={"previous":a.get(key),"current":b.get(key)}
        if asset in cur_top-old_top:reasons.append("ENTERED_TOP_5_RQI")
        if asset in old_top-cur_top:reasons.append("EXITED_TOP_5_RQI")
        if reasons:out.append({"asset":asset,"reason_codes":reasons,"metric_changes":metrics})
    ac=(previous.get("range_quality_index",{}).get("CSPR_diagnostic") or {}).get("repeatable_1_2_day_cycle_hypothesis");bc=(current.get("range_quality_index",{}).get("CSPR_diagnostic") or {}).get("repeatable_1_2_day_cycle_hypothesis")
    if ac!=bc and (ac is not None or bc is not None):out.append({"asset":"CSPR","reason_codes":["CSPR_DIAGNOSTIC_CONCLUSION_CHANGED"],"metric_changes":{"conclusion":{"previous":ac,"current":bc}}})
    return out


def compare_early_expansion(current: dict[str,Any], previous: dict[str,Any]) -> list[dict[str,Any]]:
    def rows(packet):
        block=packet.get('early_expansion',{});items=block.get('top_pre_move_candidates',[])+block.get('top_energy_delta_candidates',[])+block.get('too_late_candidates',[]);return {str(x.get('asset')):x for x in items if x.get('asset')}
    cur,old=rows(current),rows(previous);ct={x.get('asset') for x in current.get('early_expansion',{}).get('top_pre_move_candidates',[])[:5]};ot={x.get('asset') for x in previous.get('early_expansion',{}).get('top_pre_move_candidates',[])[:5]};out=[]
    for asset in sorted(set(cur)|set(old)):
        a,b=old.get(asset,{}),cur.get(asset,{});reasons=[];metrics={}
        if asset in ct-ot:reasons.append('ENTERED_TOP_5_EARLY_EXPANSION')
        if asset in ot-ct:reasons.append('EXITED_TOP_5_EARLY_EXPANSION')
        ac,bc=a.get('classification'),b.get('classification')
        if (ac,bc) in {('PRE_MOVE_BUILDING','PRE_MOVE_STRONG'),('TOO_EARLY','PRE_MOVE_BUILDING')} or (bc=='TOO_LATE' and ac!='TOO_LATE'):reasons.append('EARLY_EXPANSION_CLASSIFICATION_MATERIAL_CHANGE');metrics['classification']={'previous':ac,'current':bc}
        for key,threshold,code in (('combined_pre_move_score',10,'COMBINED_SCORE_CHANGE_AT_LEAST_10'),('energy_delta_score',15,'ENERGY_DELTA_CHANGE_AT_LEAST_15')):
            av,bv=_num(a.get(key)),_num(b.get(key))
            if av is not None and bv is not None and abs(bv-av)>=threshold:reasons.append(code);metrics[key]={'previous':av,'current':bv,'change':round(bv-av,2)}
        if reasons:out.append({'asset':asset,'reason_codes':reasons,'metric_changes':metrics})
    return out


def compare_market(current: dict[str,Any], previous: dict[str,Any]) -> tuple[list[dict[str,Any]],list[str]]:
    cur=current.get("market_state",{});old=previous.get("market_state",{});changes=[];unchanged=[]
    for key in ("crypto_regime","environment_status","opportunity_regime","btc_trend_state","breadth_state"):
        if old.get(key)!=cur.get(key): changes.append({"field":key,"previous":old.get(key),"current":cur.get(key),"reason_code":key.upper()+"_CHANGED"})
        elif cur.get(key) is not None: unchanged.append(f"{key}:{cur.get(key)}")
    for key in ("universe_outperforming_btc_24h_pct","universe_outperforming_btc_7d_pct","universe_above_ema20_pct"):
        a,b=_num(old.get(key)),_num(cur.get(key))
        if a is not None and b is not None and abs(b-a)>=5: changes.append({"field":key,"previous":a,"current":b,"change":round(b-a,4),"reason_code":"BREADTH_CHANGE_AT_LEAST_5PP"})
    return changes,unchanged


def compare_rotation(current: dict[str,Any], previous: dict[str,Any]) -> list[dict[str,Any]]:
    a=previous.get("btc_rotation",{});b=current.get("btc_rotation",{});changes=[]
    for key in ("preferred_state","best_candidate","confidence","cost_guard"):
        if a.get(key)!=b.get(key) and (a.get(key) is not None or b.get(key) is not None): changes.append({"field":key,"previous":a.get(key),"current":b.get(key),"reason_code":"ROTATION_"+key.upper()+"_CHANGED"})
    av,bv=_num(a.get("best_score_advantage")),_num(b.get("best_score_advantage"))
    if av is not None and bv is not None and abs(bv-av)>=3:changes.append({"field":"best_score_advantage","previous":av,"current":bv,"change":round(bv-av,4),"reason_code":"ROTATION_ADVANTAGE_CHANGE_AT_LEAST_3"})
    return changes


def compare_capital_flow(current: dict[str,Any], previous: dict[str,Any]) -> list[dict[str,Any]]:
    a=previous.get("capital_flow",{});b=current.get("capital_flow",{});changes=[]
    for key in ("primary_state","inferred_primary_capital_flow"):
        av=a.get(key);bv=b.get(key)
        if av!=bv and (av is not None or bv is not None):changes.append({"field":key,"previous":av,"current":bv,"reason_code":"CAPITAL_FLOW_STATE_CHANGED"});break
    av,bv=_num(a.get("capital_flow_confidence") or a.get("confidence")),_num(b.get("capital_flow_confidence") or b.get("confidence"))
    if av is not None and bv is not None and abs(bv-av)>=15:changes.append({"field":"confidence","previous":av,"current":bv,"change":round(bv-av,4),"reason_code":"CAPITAL_FLOW_CONFIDENCE_CHANGE_AT_LEAST_15"})
    return changes


def portfolio_changes(current: dict[str,Any], previous: dict[str,Any], invalidations: list[dict[str,Any]]) -> list[dict[str,Any]]:
    p=current.get("portfolio",{});open_assets={str(r.get("asset")) for r in p.get("open_positions",[]) if r.get("asset")};out=[]
    for item in invalidations:
        if item["asset"] in open_assets:out.append({"asset":item["asset"],"change":"OPEN_POSITION_HYPOTHESIS_INVALIDATED","source":"portfolio.open_positions"})
    for missing in p.get("missing_position_records",[]):
        if missing.get("asset"):out.append({"asset":str(missing["asset"]),"change":"PORTFOLIO_RECORD_MISSING","source":"portfolio.missing_position_records"})
    return sorted(out,key=lambda x:(x["asset"],x["change"]))


def tomorrow_watch(packet: dict[str,Any], comparisons: dict[str,list[dict[str,Any]]]) -> list[str]:
    cmap=_candidate_map(packet);assets=[]
    for key in ("new_invalidations","new_confirmations","strengthening_candidates","weakening_candidates","new_candidates"):
        assets.extend(r["asset"] for r in comparisons[key])
    items=[]
    for asset in list(dict.fromkeys(assets)):
        row=cmap.get(asset)
        if not row:continue
        con=row.get("consolidation",{});mom=row.get("momentum",{})
        if con.get("range_low") is not None:items.append(f"Check whether {asset} remains above range low {con['range_low']}.")
        elif mom.get("breakout_level") is not None:items.append(f"Check whether {asset} confirms relative to breakout level {mom['breakout_level']}.")
        else:items.append(f"Recheck {asset} evidence and invalidation state in the next packet.")
        if len(items)>=4:break
    state=packet.get("btc_rotation",{}).get("preferred_state")
    if state is not None and len(items)<5:items.append(f"Check whether BTC rotation remains {state}.")
    return items[:5]


def build_observation(current: dict[str,Any], previous: dict[str,Any]|None, current_path: Path,
                      previous_path: Path|None, generated_at: Any=None) -> dict[str,Any]:
    now=pd.to_datetime(generated_at or pd.Timestamp.now(tz="UTC"),utc=True);report_date=now.strftime("%Y-%m-%d") if generated_at is not None else str(current.get("report_date") or now.strftime("%Y-%m-%d"));baseline=previous is None
    comparisons={k:[] for k in ("new_candidates","removed_candidates","strengthening_candidates","weakening_candidates","new_invalidations","new_confirmations","range_personality_changes")}
    market=[];unchanged=[];rotation=[];flow=[]
    if previous is not None:
        comparisons=compare_candidates(current,previous);market,unchanged=compare_market(current,previous);rotation=compare_rotation(current,previous);flow=compare_capital_flow(current,previous)
    portfolio=portfolio_changes(current,previous or {},comparisons["new_invalidations"]);watch=tomorrow_watch(current,comparisons)
    dominant=market[0]["reason_code"] if market else "NO_MATERIAL_MARKET_CHANGE";rot_state=current.get("btc_rotation",{}).get("preferred_state");flow_state=current.get("capital_flow",{}).get("primary_state") or current.get("market_state",{}).get("inferred_primary_capital_flow")
    if baseline:conclusion="INSUFFICIENT_CHANGE_DATA"
    elif any(x.get("current") in {"BEAR","DEFENSIVE","DETERIORATING"} for x in market):conclusion="MARKET_DETERIORATING"
    elif any(x.get("current") in {"BULL","IMPROVING"} for x in market):conclusion="MARKET_IMPROVING"
    elif comparisons["strengthening_candidates"] and not comparisons["weakening_candidates"]:conclusion="SELECTIVE_ALT_STRENGTH"
    elif rotation:conclusion="ROTATION_IMPROVING" if rot_state=="REVIEW_BTC_TO_ALT" else "ROTATION_WEAKENING"
    elif comparisons["new_invalidations"]:conclusion="RANGE_OPPORTUNITIES_WEAKENING"
    else:conclusion="MARKET_UNCHANGED"
    rqi_changes=[] if previous is None else compare_rqi(current,previous);early_changes=[] if previous is None else compare_early_expansion(current,previous);material=sum(len(x) for x in [market,rotation,flow,*comparisons.values(),portfolio,rqi_changes,early_changes])
    result={"journal_version":"1.0.0","report_date":report_date,"generated_at_utc":now.isoformat(),"status":"BASELINE_CREATED" if baseline else "OK",
        "labels":LABELS,"current_packet":str(current_path.resolve()),"previous_packet":None if previous_path is None else str(previous_path.resolve()),
        "market_changes":market,**comparisons,"rqi_changes":rqi_changes,"early_expansion_changes":early_changes,"rotation_changes":rotation,"capital_flow_changes":flow,"portfolio_relevant_changes":portfolio,
        "unchanged_key_states":unchanged,"tomorrow_watch":watch,"summary":{"dominant_market_change":dominant,
        "best_strengthening_candidate":comparisons["strengthening_candidates"][0]["asset"] if comparisons["strengthening_candidates"] else None,
        "largest_weakening_candidate":comparisons["weakening_candidates"][0]["asset"] if comparisons["weakening_candidates"] else None,
        "rotation_state":rot_state,"capital_flow_state":flow_state,"new_opportunity_count":len(comparisons["new_candidates"]),
        "invalidated_opportunity_count":len(comparisons["new_invalidations"]),"portfolio_warning_count":len(portfolio),"material_change_count":material,"journal_conclusion":conclusion},
        "source_refs":[{"source":"current_chief_strategist_packet","path":str(current_path.resolve())}]+([] if previous_path is None else [{"source":"previous_chief_strategist_packet","path":str(previous_path.resolve())}]),"warnings":[]}
    return _finite(result)


def render_day(report: dict[str,Any]) -> str:
    date=report["report_date"];lines=[f"## {date}"]
    if report["status"]=="BASELINE_CREATED":lines.append("- Baseline: current Chief Strategist state recorded; no earlier packet was available.")
    for x in report["market_changes"][:2]:lines.append(f"- Market: {x['field']} changed from {x.get('previous')} to {x.get('current')}.")
    if not report["market_changes"] and report["status"]!="BASELINE_CREATED":lines.append("- Market: key regime and breadth states had no material change.")
    if report["rotation_changes"]:lines.append(f"- Rotation: {report['rotation_changes'][0]['field']} changed from {report['rotation_changes'][0].get('previous')} to {report['rotation_changes'][0].get('current')}.")
    else:lines.append(f"- Rotation: {report['summary'].get('rotation_state')} unchanged.")
    for label,key in (("New","new_candidates"),("Stronger","strengthening_candidates"),("Weaker","weakening_candidates"),("Invalidated","new_invalidations"),("Confirmed","new_confirmations")):
        for item in report[key][:2]:lines.append(f"- {label}: {item['asset']} — {', '.join(item['reason_codes'])}.")
    for item in report["range_personality_changes"][:1]:lines.append(f"- Range personality: {item['asset']} changed from {item.get('previous_classification')} to {item.get('current_classification')}.")
    for item in report["portfolio_relevant_changes"][:2]:lines.append(f"- Portfolio issue: {item['asset']} — {item['change']}.")
    for item in report["tomorrow_watch"][:3]:lines.append(f"- Tomorrow: {item}")
    lines += ["","### Conclusion","",report["summary"]["journal_conclusion"]+"."]
    return "\n".join(lines)+"\n"


def _replace_markdown_date(existing: str, report: dict[str,Any]) -> str:
    header="# AI Daily Observations\n\n";section=render_day(report).strip()+"\n"
    body=existing[len(header):] if existing.startswith(header) else existing
    pattern=re.compile(rf"(?ms)^## {re.escape(report['report_date'])}\n.*?(?=^## \d{{4}}-\d{{2}}-\d{{2}}\n|\Z)")
    body=pattern.sub("",body).strip();return header+(body+"\n\n" if body else "")+section


def write_outputs(report: dict[str,Any]) -> tuple[Path,Path]:
    date=report["report_date"];OUT_DIR.mkdir(parents=True,exist_ok=True);text=json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n";day=render_day(report);standalone="# AI Daily Observations\n\n"+day
    for path,content in ((OUT_DIR/f"{date}_ai_daily_observations.json",text),(OUT_DIR/"latest_ai_daily_observations.json",text),(OUT_DIR/f"{date}_ai_daily_observations.md",standalone),(OUT_DIR/"latest_ai_daily_observations.md",standalone)):atomic_write(path,content)
    atomic_write(JOURNAL_PATH,_replace_markdown_date(JOURNAL_PATH.read_text() if JOURNAL_PATH.exists() else "",report))
    records=[]
    if HISTORY_PATH.exists():
        for line in HISTORY_PATH.read_text().splitlines():
            if line.strip():
                item=json.loads(line)
                if item.get("report_date")!=date:records.append(item)
    records.append(report);records.sort(key=lambda x:x["report_date"]);atomic_write(HISTORY_PATH,"".join(json.dumps(x,sort_keys=True,allow_nan=False)+"\n" for x in records))
    return OUT_DIR/"latest_ai_daily_observations.md",HISTORY_PATH


def generate(current_packet: Path|str|None=None, previous_packet: Path|str|None=None,
             as_of: Any=None, verbose: bool=False) -> tuple[dict[str,Any],Path]:
    current_path=Path(current_packet) if current_packet else DEFAULT_CURRENT
    current=read_json(current_path);previous_path=select_previous_packet(current_path,current,Path(previous_packet) if previous_packet else None);previous=read_json(previous_path) if previous_path else None
    report=build_observation(current,previous,current_path,previous_path,as_of);latest,_=write_outputs(report)
    if verbose:print(json.dumps(report["summary"],sort_keys=True))
    return report,latest.resolve()


def compact_for_strategist(report: dict[str,Any], packet_date_value: str|None=None) -> dict[str,Any]:
    if not report or (packet_date_value and report.get("report_date")!=packet_date_value):return {"status":"UNAVAILABLE","dominant_change":"NO_MATERIAL_UPDATE","new_candidates":[],"strengthening":[],"weakening":[],"invalidated":[],"tomorrow_watch":[]}
    return {"status":report.get("status"),"dominant_change":report.get("summary",{}).get("dominant_market_change"),
        "new_candidates":[x["asset"] for x in report.get("new_candidates",[])[:3]],"strengthening":[x["asset"] for x in report.get("strengthening_candidates",[])[:3]],
        "weakening":[x["asset"] for x in report.get("weakening_candidates",[])[:3]],"invalidated":[x["asset"] for x in report.get("new_invalidations",[])[:3]],"tomorrow_watch":report.get("tomorrow_watch",[])[:5]}


def main() -> None:
    p=argparse.ArgumentParser();p.add_argument("--current-packet");p.add_argument("--previous-packet");p.add_argument("--as-of");p.add_argument("--verbose",action="store_true");a=p.parse_args()
    report,path=generate(a.current_packet,a.previous_packet,a.as_of,a.verbose);print(f"AI Daily Observations: {report['status']}");print(f"Current: {report['report_date']}");print(f"Previous: {Path(report['previous_packet']).name[:10] if report['previous_packet'] else 'NONE'}");print(f"Material changes: {report['summary']['material_change_count']}");print(f"Saved: {path}")


if __name__=="__main__":main()
