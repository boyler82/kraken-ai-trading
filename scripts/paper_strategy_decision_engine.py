from __future__ import annotations
import hashlib,json
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1];CONFIG=ROOT/'config/paper_strategy_research_v1.json'
def config():return json.loads(CONFIG.read_text())
def episode_key(s:dict)->str:return s.get('setup_episode_id') or hashlib.sha256(f"{s['asset']}|{s['strategy_name']}|{','.join(s['source_modules'])}|{s.get('first_eligible_timestamp')}".encode()).hexdigest()[:20]
def create_decisions(setups:list[dict],existing:set[tuple[str,str]]=set(),cfg:dict|None=None)->list[dict[str,Any]]:
 c=cfg or config();out=[]
 for s in setups:
  family=s['strategy_name'];variants=c['variants'].get(family)
  if family=='MULTI_MODULE_CONFIRMATION':variants={'MULTI_TP4_SL2':{'target_pct':4,'stop_pct':2,'max_hold_hours':72}}
  if not variants:continue
  ep=episode_key(s);entry=float(s['entry_reference_price']);meta=s.get('metadata',{})
  for name,v in variants.items():
   if (ep,name) in existing:continue
   target=entry*(1+v.get('target_pct',0)/100)
   if v.get('target')=='MIDPOINT':target=float(meta.get('midpoint') or target)
   elif v.get('target')=='RANGE_HIGH':target=float(meta.get('range_high') or target)
   elif v.get('target')=='BREAKOUT_PLUS_3':target=max(entry,float(meta.get('breakout_level') or entry))*1.03
   stop=entry*(1-v.get('stop_pct',2)/100);sid=hashlib.sha256(f'{ep}|{name}'.encode()).hexdigest()[:24]
   out.append({**s,'signal_id':sid,'setup_episode_id':ep,'strategy_variant':name,'entry_price':entry,'stop_price':round(stop,12),'target_price':round(target,12),'max_hold_hours':v['max_hold_hours'],'estimated_cost_pct':c['estimated_round_trip_cost_pct'],'notional_usd':c['standard_notional_usd']})
 return out
