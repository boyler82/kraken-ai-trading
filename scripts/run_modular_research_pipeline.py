from __future__ import annotations
import json,traceback
from pathlib import Path
from typing import Any,Callable
import pandas as pd
from ai_confidence_engine import run as run_ai
from capital_flow_engine import run as run_flow
from leadership_rotation_engine import run as run_leadership
from opportunity_aging_engine import run as run_aging
from relative_strength_radar import run as run_relative
from lib.decision_registry import write_record
from lib.feature_store import build_feature_store
from weekly_consolidation_common import ROOT,utc_timestamp
def _csv(path):
    try:return pd.read_csv(path)
    except Exception:return pd.DataFrame()
def update_legacy_registry(as_of:Any=None)->None:
    now=utc_timestamp(as_of).isoformat()
    con=_csv(ROOT/'WATCHLISTS/consolidation_daily_watchlist.csv');cc=[x for x in ['asset','rank','simple_zone','position_pct','range_quality','opportunity_score','freshness_status','range_still_valid','risk_flags','latest_completed_candle_timestamp'] if x in con.columns];write_record('consolidation',{'module_name':'consolidation','status':'OK' if len(con) else 'UNAVAILABLE','freshness':'FRESH' if len(con) else 'UNAVAILABLE','generated_at_utc':now,'summary':{'candidate_count':len(con)},'candidates':con[cc].head(4).where(pd.notna(con[cc]),None).to_dict('records'),'risks':[],'unknowns':[],'source_file':str(ROOT/'WATCHLISTS/consolidation_daily_watchlist.csv')})
    mom=_csv(ROOT/'DAILY_REPORTS/MOMENTUM_BREAKOUT/latest_momentum_breakout_radar.csv');active=mom[mom.get('momentum_stage',pd.Series(dtype=str)).astype(str)!='NO_MOMENTUM'] if len(mom) else mom;mc=[x for x in ['asset','momentum_stage','momentum_breakout_score','change_24h_pct','relative_strength_vs_btc_24h_pct','overextension_risk','freshness_status','latest_completed_candle_timestamp'] if x in active.columns];write_record('momentum',{'module_name':'momentum','status':'OK' if len(mom) else 'UNAVAILABLE','freshness':'FRESH' if len(active) else 'UNAVAILABLE','generated_at_utc':now,'summary':{'active_count':len(active)},'candidates':active[mc].head(5).where(pd.notna(active[mc]),None).to_dict('records'),'risks':[],'unknowns':[],'source_file':str(ROOT/'DAILY_REPORTS/MOMENTUM_BREAKOUT/latest_momentum_breakout_radar.csv')})
    rotpath=ROOT/'DAILY_REPORTS/BTC_ROTATION/latest_btc_rotation_dashboard.json';rot=json.loads(rotpath.read_text()) if rotpath.exists() else {};write_record('btc_rotation',{'module_name':'btc_rotation','status':'OK' if rot else 'UNAVAILABLE','freshness':rot.get('data_freshness','UNAVAILABLE'),'generated_at_utc':rot.get('report_timestamp',now),'summary':{k:rot.get(k) for k in ('objective','current_holding','btc_hold_score','market_regime','preferred_state','best_score_advantage','confidence')},'top_candidates':rot.get('top_candidates',[])[:3],'risks':[],'unknowns':[],'source_file':str(rotpath)})
    regime_files=sorted((ROOT/'DAILY_REPORTS').glob('*_research_regime.csv'));reg=_csv(regime_files[-1]) if regime_files else pd.DataFrame();lookup={str(r.metric):r.value for _,r in reg.iterrows()} if {'metric','value'}.issubset(reg.columns) else {};write_record('market_regime',{'module_name':'market_regime','status':'OK' if lookup else 'UNAVAILABLE','freshness':'FRESH' if lookup else 'UNAVAILABLE','generated_at_utc':now,'summary':lookup,'candidates':[],'risks':[],'unknowns':[],'source_file':str(regime_files[-1]) if regime_files else None})
    port=_csv(ROOT/'journal/portfolio_positions.csv');openp=port[port.get('status',pd.Series(dtype=str)).astype(str).str.upper()=='OPEN'] if len(port) else port;write_record('portfolio',{'module_name':'portfolio','status':'OK','freshness':'FRESH','generated_at_utc':now,'summary':{'open_positions':openp.where(pd.notna(openp),None).to_dict('records')},'candidates':[],'risks':[],'unknowns':[],'source_file':str(ROOT/'journal/portfolio_positions.csv')})
    for name in ('rsi2','data_quality'):
        write_record(name,{'module_name':name,'status':'UNAVAILABLE','freshness':'UNAVAILABLE','generated_at_utc':now,'summary':{},'candidates':[],'risks':[],'unknowns':['Adapter not yet migrated'],'source_file':None})
def run(as_of:Any=None)->dict:
    statuses={};errors={}
    try:build_feature_store(as_of);statuses['feature_store']='OK'
    except Exception as exc:statuses['feature_store']='FAILED';errors['feature_store']=str(exc)
    try:update_legacy_registry(as_of);statuses['legacy_registry']='OK'
    except Exception as exc:statuses['legacy_registry']='FAILED';errors['legacy_registry']=str(exc)
    for name,fn in [('relative_strength',run_relative),('leadership_rotation',run_leadership),('capital_flow',run_flow),('opportunity_aging',run_aging),('ai_confidence',run_ai)]:
        try:fn(as_of);statuses[name]='OK'
        except Exception as exc:
            statuses[name]='FAILED';errors[name]=str(exc)
            try:write_record(name,{'module_name':name,'status':'FAILED','freshness':'UNAVAILABLE','generated_at_utc':utc_timestamp(as_of).isoformat(),'summary':{},'candidates':[],'risks':[],'unknowns':[],'errors':[str(exc)],'source_file':None})
            except Exception:pass
    return {'statuses':statuses,'errors':errors,'succeeded':sum(x=='OK' for x in statuses.values()),'total':len(statuses)}
if __name__=='__main__':print(run())
