from __future__ import annotations
from typing import Any
import json,pandas as pd
from lib.decision_registry import read_record,write_record
from lib.feature_store import load_features
from lib.research_module_contract import make_result,write_result
from weekly_consolidation_common import ROOT,atomic_write
OUT=ROOT/"DAILY_REPORTS/CAPITAL_FLOW"
def infer(features:pd.DataFrame,leadership:dict,as_of:Any=None)->dict:
    f=features.copy();f["rank"]=pd.to_numeric(f.get("market_cap_rank"),errors="coerce");f["r24"]=pd.to_numeric(f.get("return_24h"),errors="coerce");f["rel"]=pd.to_numeric(f.get("btc_relative_return_24h"),errors="coerce");fresh=f[f.get("freshness").astype(str)=="FRESH"] if "freshness" in f else f.iloc[0:0]
    large=fresh[fresh["rank"]<=20];mid=fresh[(fresh["rank"]>20)&(fresh["rank"]<=75)];small=fresh[fresh["rank"]>75];btc=fresh[fresh.asset=="BTC"]
    metric={"btc_return_24h":btc.r24.mean(),"large_return_24h":large.r24.mean(),"mid_return_24h":mid.r24.mean(),"small_return_24h":small.r24.mean(),"breadth_positive_pct":float((fresh.r24>0).mean()*100) if len(fresh) else None,"momentum_participation":float((fresh.get("momentum_stage",pd.Series(index=fresh.index,dtype=str)).astype(str)!="NO_MOMENTUM").mean()*100) if len(fresh) else None}
    flows=[]
    def add(state,frm,to,evidence,contra,confidence,invalidation):flows.append({"state":state,"from_group":frm,"to_group":to,"evidence":evidence,"supporting_metrics":metric,"contradicting_metrics":contra,"confidence":confidence,"persistence":"NEW_OR_UNVERIFIED","inception_timestamp":None,"risk_flags":["INFERENCE_NOT_DIRECT_FLOW_MEASUREMENT"],"invalidation_condition":invalidation,"observation_type":"INFERENCE_FROM_DERIVED_PROXIES"})
    b=metric["breadth_positive_pct"] or 0;lr=metric["large_return_24h"] or 0;mr=metric["mid_return_24h"] or 0;sr=metric["small_return_24h"] or 0;br=metric["btc_return_24h"] or 0
    if b>65 and mr>lr and sr>mr:add("BROAD_RISK_ON","BTC / large caps","mid and small caps",["broad positive breadth","smaller-cap outperformance"],[],70,"Breadth falls below 50%")
    elif br>0 and br>lr:add("DEFENSIVE_TO_BTC","USD / defensive","BTC",["BTC positive and outperforming large caps"],[],60,"BTC return turns negative")
    elif b<35 and br<0:add("RISK_OFF_TO_USD","crypto risk","USD / defensive",["negative BTC return","weak breadth"],[],70,"Breadth recovers above 50%")
    elif sr>mr+3:add("SPECULATIVE_EXCESS","mid caps","small/speculative",["small-cap return materially exceeds mid caps"],["flow is inferred, not observed"],55,"Small caps cease outperforming")
    else:add("NO_CLEAR_FLOW","mixed","mixed",["proxy signals lack alignment"],["group returns are fragmented"],30,"Multiple group proxies align")
    result=make_result("capital_flow","1.0.0",as_of,status="WARNING" if len(fresh)<5 else "OK",freshness="FRESH" if len(fresh)>=5 else "STALE",summary={"primary_state":flows[0]["state"],"capital_flow_confidence":flows[0]["confidence"],"observed_data":"completed-candle returns and volumes","derived_proxy":"group breadth and relative performance","inference_disclaimer":"Inferred proxy; not direct measurement of capital transfers"},candidates=flows[:3],risks=["CAPITAL_FLOW_IS_INFERRED_NOT_OBSERVED"],unknowns=["Stablecoin flow data unavailable","BTC dominance proxy unavailable"],source_files=[str(ROOT/"DATASETS/FEATURE_STORE/latest_market_features.csv"),str(ROOT/"DECISION_REGISTRY/leadership_rotation.json")]);return result
def run(as_of=None):
    result=infer(load_features(),read_record('leadership_rotation'),as_of);OUT.mkdir(parents=True,exist_ok=True);base=OUT/f"{result['report_date']}_capital_flow";write_result(base.with_suffix('.json'),result);atomic_write(base.with_suffix('.md'),"# Capital Flow Engine\n\n**Inference, not directly observed flow.**\n\n"+"\n".join(f"- {r['state']} | {r['from_group']} → {r['to_group']} | confidence {r['confidence']}" for r in result['candidates'])+"\n");
    for ext in ('.json','.md'):atomic_write(OUT/f"latest_capital_flow{ext}",base.with_suffix(ext).read_text(),backup=False)
    write_record('capital_flow',{"module_name":"capital_flow","status":result['status'],"freshness":result['freshness'],"generated_at_utc":result['generated_at_utc'],"summary":result['summary'],"primary_flows":result['candidates'][:3],"alternative_interpretations":result['conflicts'][:3],"risks":result['risks'][:5],"unknowns":result['unknowns'][:5],"source_file":str(base.with_suffix('.json'))});return result
if __name__=='__main__':print(run()['summary']['primary_state'])
