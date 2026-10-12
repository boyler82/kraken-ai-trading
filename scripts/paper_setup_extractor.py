from __future__ import annotations
import json,math
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
SOURCES={'consolidation':ROOT/'DAILY_REPORTS/DAILY_CONSOLIDATION/latest_daily_consolidation_scan.json','rqi':ROOT/'DAILY_REPORTS/RANGE_QUALITY_INDEX/latest_range_quality_index.json','personality':ROOT/'DAILY_REPORTS/RANGE_PERSONALITY/latest_range_personality.json','early_expansion':ROOT/'DAILY_REPORTS/EARLY_EXPANSION/latest_early_expansion.json','momentum':ROOT/'DAILY_REPORTS/MOMENTUM_BREAKOUT/latest_momentum_breakout_radar.json','relative_strength':ROOT/'DAILY_REPORTS/RELATIVE_STRENGTH/latest_relative_strength.json','capital_flow':ROOT/'DAILY_REPORTS/CAPITAL_FLOW/latest_capital_flow.json','rotation':ROOT/'DAILY_REPORTS/BTC_ROTATION/latest_btc_rotation_dashboard.json'}
def read(path:Path)->dict:
 try:return json.loads(path.read_text())
 except Exception:return {}
def _map(d:dict,key:str)->dict:return {str(x.get('asset')):x for x in d.get(key,[]) if x.get('asset')}
def load_reports()->dict:return {k:read(v) for k,v in SOURCES.items()}
def extract_setups(reports:dict|None=None,as_of:str|None=None,*,include_parent_provenance:bool=False)->list[dict[str,Any]]:
 r=reports or load_reports();con=_map(r.get('consolidation',{}),'candidates');rqi=_map(r.get('rqi',{}),'assets');rp=_map(r.get('personality',{}),'assets');ee=_map(r.get('early_expansion',{}),'assets');mom=_map(r.get('momentum',{}),'candidates');rs=_map(r.get('relative_strength',{}),'candidates');flow=str((r.get('capital_flow',{}).get('summary') or {}).get('primary_state') or 'NO_CLEAR_FLOW');out=[]
 def add(asset,strategy,price,score,confidence,modules,extra):
  if price is None:return
  ts=extra.get('source_timestamp') or as_of;fresh=str(extra.get('freshness') or 'FRESH')
  if fresh!='FRESH':return
  out.append({'asset':asset,'pair':extra.get('pair') or asset+'USD','strategy_name':strategy,'entry_reference_price':float(price),'setup_score':score,'confidence':confidence,'source_modules':sorted(set(modules)),'source_timestamp':ts,'first_eligible_timestamp':ts,'source_packet_date':str(ts or '')[:10],'metadata':extra})
 for a,c in con.items():
  q=rqi.get(a,{});p=rp.get(a,{});pos=q.get('position_zone');price=c.get('latest_available_market_price')
  if c.get('range_valid',c.get('range_still_valid')) and pos in {'LOWER_ZONE','LOWER_MIDDLE'} and q.get('rqi_classification') in {'ACCEPTABLE_RANGE','GOOD_RANGE','EXCELLENT_RANGE'}:add(a,'CONSOLIDATION_RANGE',price,q.get('rqi_score'),q.get('rqi_confidence_score'),['CONSOLIDATION','RANGE_QUALITY','RANGE_PERSONALITY'],{'pair':c.get('kraken_pair'),'freshness':c.get('freshness_status'),'source_timestamp':c.get('latest_completed_candle_timestamp'),'midpoint':c.get('midpoint'),'range_high':c.get('range_high'),'range_low':c.get('range_low'),'range_valid':True,'personality':p.get('classification')})
 for a,x in ee.items():
  if x.get('classification') in {'PRE_MOVE_BUILDING','PRE_MOVE_STRONG','EARLY_EXPANSION_DEVELOPING'}:add(a,'EARLY_EXPANSION',x.get('current_price'),x.get('combined_pre_move_score'),x.get('confidence_score'),['EARLY_EXPANSION']+(['RELATIVE_STRENGTH'] if (rs.get(a,{}).get('relative_acceleration') or 0)>0 else [])+(['CAPITAL_FLOW'] if flow=='BROAD_RISK_ON' else []),x)
 for a,x in mom.items():
  if x.get('momentum_stage') in {'EARLY_MOMENTUM','BREAKOUT_DEVELOPING','BREAKOUT_CONFIRMED'} and x.get('overextension_risk')!='HIGH':add(a,'MOMENTUM_BREAKOUT',x.get('current_price'),x.get('momentum_score'),x.get('confidence'),['MOMENTUM'],{'pair':x.get('kraken_pair'),'freshness':x.get('freshness_status'),'source_timestamp':x.get('latest_completed_candle_timestamp'),'breakout_level':x.get('breakout_level'),'range_valid':True})
 rot=r.get('rotation',{});cands=rot.get('top_candidates',[]) or rot.get('candidates',[])
 for x in cands:
  if x.get('candidate_disposition')=='ACTIONABLE_REVIEW' or x.get('user_facing_rotation_state')=='REVIEW_BTC_TO_ALT':add(str(x.get('asset')),'BTC_ROTATION',x.get('current_price'),x.get('alt_rotation_score'),x.get('confidence'),['BTC_ROTATION'],{'pair':x.get('pair'),'freshness':rot.get('data_freshness','FRESH'),'source_timestamp':rot.get('report_timestamp'),'btc_price':x.get('btc_price'),'range_valid':True})
 # Exact combinations are recorded on the same deterministic underlying setup.
 for x in list(out):
  mods=set(x['source_modules']);combos=[]
  if x['asset'] in con and x['asset'] in rs:combos.append(['CONSOLIDATION','RELATIVE_STRENGTH'])
  if x['asset'] in con and x['asset'] in ee:combos.append(['CONSOLIDATION','EARLY_EXPANSION'])
  if x['asset'] in ee and x['asset'] in rs:combos.append(['EARLY_EXPANSION','RELATIVE_STRENGTH'])
  if x['asset'] in ee and flow=='BROAD_RISK_ON':combos.append(['EARLY_EXPANSION','CAPITAL_FLOW'])
  for combo in combos:
   y=dict(x)
   if include_parent_provenance:
    y['parent_setup']={'strategy_name':x['strategy_name'],'source_modules':sorted(set(x['source_modules'])),'pair':x['pair'],'source_timestamp':x['metadata'].get('source_timestamp'),'setup_episode_id':x.get('setup_episode_id')}
   y['strategy_name']='MULTI_MODULE_CONFIRMATION';y['source_modules']=combo;y['setup_score']=x.get('setup_score');out.append(y)
 return sorted(out,key=lambda x:(x['asset'],x['strategy_name'],','.join(x['source_modules'])))
