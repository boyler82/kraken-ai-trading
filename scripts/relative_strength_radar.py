from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
import numpy as np,pandas as pd
from lib.decision_registry import write_record
from lib.feature_store import load_features
from lib.research_module_contract import make_result,sanitize,write_result
from weekly_consolidation_common import ROOT,atomic_write,utc_timestamp
from btc_rotation_engine import rotation_features
from daily_momentum_breakout_radar import _hourly_for
OUT=ROOT/"DAILY_REPORTS/RELATIVE_STRENGTH"
def score_row(r:dict[str,Any])->tuple[float,dict[str,float],dict[str,float]]:
    short=min(20,max(0,10+(float(r.get("btc_relative_return_24h") or 0)+float(r.get("btc_relative_return_48h") or 0))*1.5));long=min(20,max(0,10+float(r.get("btc_relative_return_7d") or 0)))
    trend=20 if float(r.get("relative_ema20_slope") or 0)>0 and float(r.get("relative_distance_ema20") or 0)>0 else 8;acc=min(15,max(0,7.5+float(r.get("relative_acceleration") or 0)*2));persist=min(15,max(0,float(r.get("relative_persistence") or 0)*.15));liq=10 if r.get("freshness")=="FRESH" and r.get("liquidity_pass") else 0
    parts={"short_relative_returns":short,"long_relative_returns":long,"relative_trend_quality":trend,"relative_acceleration":acc,"persistence":persist,"liquidity_freshness":liq};pen={"overextension":15 if float(r.get("btc_relative_return_48h") or 0)>10 else 0,"one_candle_spike":10 if float(r.get("btc_relative_return_4h") or 0)>6 else 0,"low_liquidity":20 if not r.get("liquidity_pass") else 0,"stale_data":25 if r.get("freshness")!="FRESH" else 0,"excessive_relative_volatility":10 if float(r.get("relative_volatility") or 0)>100 else 0,"insufficient_history":10 if not r.get("sufficient_history") else 0};return round(max(0,min(100,sum(parts.values())-sum(pen.values()))),4),parts,pen
def classify(r:dict[str,Any])->str:
    if not r.get("sufficient_history"):return "INSUFFICIENT_DATA"
    if float(r.get("btc_relative_return_48h") or 0)>10:return "OVEREXTENDED_RELATIVE_MOVE"
    score=float(r.get("relative_strength_score",0));slope=float(r.get("relative_ema20_slope") or 0);acc=float(r.get("relative_acceleration") or 0)
    if score>=75 and slope>0:return "ESTABLISHED_RELATIVE_LEADER"
    if score>=60 and acc>0:return "EMERGING_RELATIVE_LEADER"
    if score>=50 and acc>0:return "IMPROVING"
    if score<30:return "RELATIVE_LAGGARD"
    if slope<0 and acc<0:return "DETERIORATING"
    return "NEUTRAL"
def analyze(features:pd.DataFrame,as_of:Any=None)->dict[str,Any]:
    rows=[]
    for _,x in features.iterrows():
        if str(x.get("asset"))=="BTC":continue
        r={"asset":str(x["asset"]),"pair":x.get("pair"),"source_timestamp":x.get("source_timestamp"),"freshness":x.get("freshness"),"liquidity_pass":bool(x.get("liquidity_pass")),"sufficient_history":bool(x.get("sufficient_history")),"btc_relative_return_4h":x.get("btc_relative_return_4h"),"btc_relative_return_12h":x.get("btc_relative_return_12h"),"btc_relative_return_24h":x.get("btc_relative_return_24h"),"btc_relative_return_48h":x.get("btc_relative_return_48h"),"btc_relative_return_7d":x.get("btc_relative_return_7d"),"btc_relative_return_14d":x.get("btc_relative_return_14d"),"btc_relative_return_30d":x.get("btc_relative_return_30d"),"relative_ema20":x.get("relative_ema20"),"relative_ema50":x.get("relative_ema50"),"relative_ema20_slope":x.get("relative_ema20_slope",x.get("ema20_slope")),"relative_distance_ema20":x.get("relative_distance_ema20",x.get("return_24h")),"relative_acceleration":x.get("relative_acceleration",float(x.get("btc_relative_return_4h") or 0)-float(x.get("btc_relative_return_24h") or 0)/6),"relative_drawdown":x.get("relative_drawdown"),"relative_volatility":x.get("relative_volatility",x.get("realized_volatility")),"relative_persistence":x.get("relative_persistence",50+max(-50,min(50,float(x.get("btc_relative_return_24h") or 0)*5))),"positive_relative_periods":sum(float(x.get(k) or 0)>0 for k in ("btc_relative_return_4h","btc_relative_return_24h","btc_relative_return_48h","btc_relative_return_7d","btc_relative_return_14d","btc_relative_return_30d")),"percentile_rank_change":None}
        score,parts,pen=score_row(r);r.update({"relative_strength_score":score,"score_components":parts,"penalties":pen});rows.append(r)
    rows=sorted(rows,key=lambda r:(-r["relative_strength_score"],r["asset"]));n=max(1,len(rows)-1)
    for i,r in enumerate(rows):r["percentile_rank"]=round((len(rows)-1-i)/n*100,2);r["classification"]=classify(r);r["rank"]=i+1
    breadth=sum(float(r.get("btc_relative_return_24h") or 0)>0 for r in rows)/len(rows)*100 if rows else 0
    fresh="FRESH" if rows and sum(r["freshness"]=="FRESH" for r in rows)>=len(rows)/2 else "STALE"
    return make_result("relative_strength","1.0.0",as_of,freshness=fresh,source_timestamps={r["asset"]:r["source_timestamp"] for r in rows},summary={"eligible_assets":len(rows),"relative_strength_breadth_pct":breadth},candidates=rows,risks=["LIMITED_LONG_HORIZON_FEATURES"] if any(r["btc_relative_return_30d"] is None for r in rows) else [],unknowns=["Percentile-rank change unavailable without prior feature-store snapshot"],source_files=[str(ROOT/"DATASETS/FEATURE_STORE/latest_market_features.csv")])
def enriched_features(as_of=None)->pd.DataFrame:
    f=load_features();universe=pd.read_csv(ROOT/'DATASETS/universe/weekly_consolidation_universe.csv');inc=universe[universe.inclusion_status=='INCLUDED'];btcitem=inc[inc.symbol=='BTC'];btc=_hourly_for('BTC',str(btcitem.iloc[0].selected_kraken_pair if len(btcitem) else 'XBTUSD'),utc_timestamp(as_of));updates=[]
    for _,x in f.iterrows():
        if x.asset=='BTC':continue
        try:
            alt=_hourly_for(str(x.asset),str(x['pair']),utc_timestamp(as_of));z=rotation_features(alt,btc);updates.append({'asset':x.asset,**{f'btc_relative_return_{p}':z.get(f'relative_return_{p}_pct') for p in ('4h','12h','24h','48h','7d','14d','30d')},'relative_ema20':z['alt_btc_ema20'],'relative_ema50':z['alt_btc_ema50'],'relative_ema20_slope':z['alt_btc_ema20_slope_pct'],'relative_distance_ema20':z['alt_btc_distance_ema20_pct'],'relative_acceleration':z['relative_acceleration_pct'],'relative_drawdown':z['maximum_adverse_move_7d_pct'],'relative_volatility':z['realized_volatility_pct'],'relative_persistence':z['relative_strength_persistence_pct']})
        except Exception:continue
    if not updates:return f
    merged=f.merge(pd.DataFrame(updates),on='asset',how='left',suffixes=('', '_new'))
    for col in [c[:-4] for c in merged.columns if c.endswith('_new')]:merged[col]=merged[f'{col}_new'].combine_first(merged[col]);merged=merged.drop(columns=f'{col}_new')
    return merged
def run(as_of:Any=None)->dict[str,Any]:
    result=analyze(enriched_features(as_of),as_of);date=result["report_date"];OUT.mkdir(parents=True,exist_ok=True);base=OUT/f"{date}_relative_strength";write_result(base.with_suffix(".json"),result);atomic_write(base.with_suffix(".csv"),pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,dict)} for r in result["candidates"]]).to_csv(index=False));atomic_write(base.with_suffix(".md"),"# Relative Strength Radar\n\n"+"\n".join(f"- #{r['rank']} {r['asset']} | {r['classification']} | {r['relative_strength_score']:.1f}" for r in result["candidates"][:10])+"\n");
    for ext in (".json",".csv",".md"):atomic_write(OUT/f"latest_relative_strength{ext}",base.with_suffix(ext).read_text(),backup=False)
    leaders=result["candidates"][:5];emerging=[r for r in result["candidates"] if r["classification"]=="EMERGING_RELATIVE_LEADER"][:3];deteriorating=[r for r in result["candidates"] if r["classification"]=="DETERIORATING"][:3];write_record("relative_strength",{"module_name":"relative_strength","status":result["status"],"freshness":result["freshness"],"generated_at_utc":result["generated_at_utc"],"summary":result["summary"],"top_leaders":leaders,"emerging_leaders":emerging,"deteriorating_leaders":deteriorating,"risks":result["risks"][:5],"source_file":str(base.with_suffix('.json'))});return result
if __name__=="__main__":print(f"Relative strength assets: {len(run()['candidates'])}")
