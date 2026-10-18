from __future__ import annotations
import json
from typing import Any
import pandas as pd
from lib.decision_registry import read_record,write_record
from lib.research_module_contract import make_result,sanitize,write_result
from weekly_consolidation_common import ROOT,atomic_write,utc_timestamp
STATE_DIR=ROOT/"DATASETS/OPPORTUNITY_AGING";STATE=STATE_DIR/"opportunity_state.json";HISTORY=STATE_DIR/"opportunity_history.csv";OUT=ROOT/"DAILY_REPORTS/OPPORTUNITY_AGING"
def current_opportunities()->list[dict]:
    items=[]
    sources=[('consolidation','consolidation'),('momentum','momentum'),('relative_strength','btc_relative_leader'),('btc_rotation','rotation_candidate'),('leadership_rotation','sector_leadership')]
    for name,kind in sources:
        rec=read_record(name);candidates=rec.get('candidates') or rec.get('top_leaders') or rec.get('top_sectors') or rec.get('top_candidates') or []
        for r in candidates[:5]:
            asset=str(r.get('asset') or r.get('sector') or 'UNKNOWN');score=r.get('score') or r.get('relative_strength_score') or r.get('sector_leadership_score') or r.get('momentum_breakout_score') or r.get('opportunity_score') or 0;items.append({'opportunity_id':f'{kind}:{asset}','asset':asset,'opportunity_type':kind,'current_score':float(score or 0),'current_price':r.get('current_price'),'btc_relative_value':r.get('btc_relative_return_24h')})
    return sorted(items,key=lambda x:x['opportunity_id'])
def update_state(current:list[dict],as_of:Any=None,previous:dict|None=None)->tuple[dict,list[dict]]:
    now=utc_timestamp(as_of);prev=(previous or {}).get('opportunities',{});updated={};rows=[]
    for item in current:
        old=prev.get(item['opportunity_id'],{});first=old.get('first_seen_timestamp',now.isoformat());age=max(0,(now-utc_timestamp(first)).total_seconds()/3600);initial=float(old.get('initial_score',item['current_score']));peak=max(float(old.get('peak_score',item['current_score'])),item['current_score']);change=item['current_score']-float(old.get('current_score',item['current_score']));strength=int(old.get('strengthening_count',0))+(change>0);weak=int(old.get('weakening_count',0))+(change<0)
        cls='NEW' if age<24 else 'EARLY' if age<72 else 'MATURING' if age<168 else 'DECAYING' if change<0 and weak>=2 else 'ESTABLISHED'
        row={**item,'first_seen_timestamp':first,'latest_seen_timestamp':now.isoformat(),'age_hours':age,'age_days':age/24,'initial_score':initial,'peak_score':peak,'score_change':item['current_score']-initial,'readiness_change':change,'price_change_since_first_seen':None,'btc_relative_change_since_first_seen':None,'maximum_favorable_movement':None,'maximum_adverse_movement':None,'status_history':(old.get('status_history',[])+[cls])[-30:],'strengthening_count':strength,'weakening_count':weak,'stale_count':int(old.get('stale_count',0)),'invalidation_status':False,'persistence':'PERSISTENT' if age>=72 else 'DEVELOPING','useful_life_estimate':None,'confidence':'LOW','classification':cls};updated[item['opportunity_id']]=row;rows.append(row)
    for oid,old in prev.items():
        if oid not in updated:
            row={**old,'latest_seen_timestamp':now.isoformat(),'classification':'EXPIRED','invalidation_status':True};updated[oid]=row;rows.append(row)
    return {'generated_at_utc':now.isoformat(),'opportunities':updated},sorted(rows,key=lambda r:(r['classification'],r['opportunity_id']))
def run(as_of=None):
    previous=json.loads(STATE.read_text()) if STATE.exists() else {};state,rows=update_state(current_opportunities(),as_of,previous);STATE_DIR.mkdir(parents=True,exist_ok=True);atomic_write(STATE,json.dumps(sanitize(state),indent=2,sort_keys=True)+"\n");atomic_write(HISTORY,pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,list)} for r in rows]).to_csv(index=False));result=make_result('opportunity_aging','1.0.0',as_of,freshness='FRESH',summary={'tracked':len(rows),'new':sum(r['classification']=='NEW' for r in rows),'decaying':sum(r['classification']=='DECAYING' for r in rows)},candidates=rows,risks=['HISTORICAL_USEFUL_LIFE_UNAVAILABLE'],unknowns=['Useful-life estimates require historical samples'],source_files=[str(STATE),str(ROOT/'DECISION_REGISTRY')]);OUT.mkdir(parents=True,exist_ok=True);base=OUT/f"{result['report_date']}_opportunity_aging";write_result(base.with_suffix('.json'),result);atomic_write(base.with_suffix('.csv'),pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,list)} for r in rows]).to_csv(index=False));atomic_write(base.with_suffix('.md'),"# Opportunity Aging\n\n"+"\n".join(f"- {r['opportunity_id']} | {r['classification']} | {r['age_hours']:.1f}h" for r in rows[:20])+"\n");
    for ext in ('.json','.csv','.md'):atomic_write(OUT/f"latest_opportunity_aging{ext}",base.with_suffix(ext).read_text(),backup=False)
    write_record('opportunity_aging',{'module_name':'opportunity_aging','status':result['status'],'freshness':result['freshness'],'generated_at_utc':result['generated_at_utc'],'summary':result['summary'],'new_opportunities':[r for r in rows if r['classification']=='NEW'][:5],'strengthening_opportunities':sorted(rows,key=lambda r:-r['score_change'])[:5],'decaying_opportunities':[r for r in rows if r['classification']=='DECAYING'][:5],'risks':result['risks'][:5],'source_file':str(base.with_suffix('.json'))});return result
if __name__=='__main__':print(f"Aging tracked: {len(run()['candidates'])}")
