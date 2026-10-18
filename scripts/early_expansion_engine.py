from __future__ import annotations

import argparse, csv, json, math, os, re
from pathlib import Path
from typing import Any

try:
    from weekly_consolidation_common import ROOT, atomic_write, utc_timestamp
except ModuleNotFoundError:
    from scripts.weekly_consolidation_common import ROOT, atomic_write, utc_timestamp

CONFIG_PATH=ROOT/'config/early_expansion_engine_v1.json';OUT=ROOT/'DAILY_REPORTS/EARLY_EXPANSION';REGISTRY=ROOT/'DECISION_REGISTRY/early_expansion.json'
SOURCES={'consolidation':ROOT/'DAILY_REPORTS/DAILY_CONSOLIDATION/latest_daily_consolidation_scan.json','rqi':ROOT/'DAILY_REPORTS/RANGE_QUALITY_INDEX/latest_range_quality_index.json','personality':ROOT/'DAILY_REPORTS/RANGE_PERSONALITY/latest_range_personality.json','relative':ROOT/'DAILY_REPORTS/RELATIVE_STRENGTH/latest_relative_strength.json','momentum':ROOT/'DAILY_REPORTS/MOMENTUM_BREAKOUT/latest_momentum_breakout_radar.json','capital':ROOT/'DAILY_REPORTS/CAPITAL_FLOW/latest_capital_flow.json','rotation':ROOT/'DAILY_REPORTS/BTC_ROTATION/latest_btc_rotation_dashboard.json','chief':ROOT/'DAILY_REPORTS/CHATGPT_EXPORT/latest_ai_chief_strategist_packet.json'}
DATED={'consolidation':('DAILY_REPORTS/DAILY_CONSOLIDATION','daily_consolidation_scan'),'rqi':('DAILY_REPORTS/RANGE_QUALITY_INDEX','range_quality_index'),'relative':('DAILY_REPORTS/RELATIVE_STRENGTH','relative_strength'),'momentum':('DAILY_REPORTS/MOMENTUM_BREAKOUT','momentum_breakout_radar')}
VALID_STATES={'VALID_RANGE','LOWER_HALF','UPPER_HALF','NEAR_RANGE_LOW','NEAR_RANGE_HIGH','IN_RANGE','FALSE_BREAKDOWN_RECOVERY','FALSE_BREAKOUT_RECOVERY'}

def load_config(path:Path=CONFIG_PATH)->dict[str,Any]:
    c=json.loads(path.read_text())
    if c.get('version')!='1.0.0' or sum(c['weights'].values())!=100 or sum(c['energy_weights'].values())!=100:raise ValueError('invalid Early Expansion V1 config')
    return c
def _read(path:Path)->dict:
    try:return json.loads(path.read_text())
    except Exception:return {}
def _num(v:Any,d:float|None=None)->float|None:
    try:
        x=float(v);return x if math.isfinite(x) else d
    except (TypeError,ValueError):return d
def _clip(x:float)->float:return max(0,min(100,x))
def _maps(reports:dict[str,dict])->dict[str,dict[str,dict]]:
    keys={'consolidation':'candidates','rqi':'assets','personality':'assets','relative':'candidates','momentum':'candidates'};out={}
    for name,key in keys.items():out[name]={str(x.get('asset')):x for x in reports.get(name,{}).get(key,[]) if x.get('asset')}
    chief=reports.get('chief',{});out['chief']={str(x.get('asset')):x for x in chief.get('candidates',[]) if x.get('asset')};return out
def load_current()->dict[str,dict]:return {k:_read(v) for k,v in SOURCES.items()}
def _dated_path(name:str,date:str)->Path:
    folder,suffix=DATED[name];return ROOT/folder/f'{date}_{suffix}.json'
def available_dates()->list[str]:
    sets=[]
    for name in DATED:
        folder,suffix=DATED[name];sets.append({p.name[:10] for p in (ROOT/folder).glob(f'????-??-??_{suffix}.json')})
    return sorted(set.intersection(*sets)) if sets else []
def load_date(date:str)->dict[str,dict]:
    reports={k:_read(_dated_path(k,date)) for k in DATED};reports['personality']=_read(SOURCES['personality']);reports['capital']=_read(SOURCES['capital']);reports['rotation']=_read(SOURCES['rotation']);reports['chief']={};return reports

def _stage_score(stage:str)->float:return {'NO_MOMENTUM':35,'EARLY_MOMENTUM':68,'BREAKOUT_DEVELOPING':72,'BREAKOUT_CONFIRMED':20,'EXTENDED_MOVE':0}.get(stage,30)
def _position_score(pos:float|None)->float:
    if pos is None:return 25
    if pos<=30:return 100
    if pos<=50:return 82
    if pos<=70:return 48
    if pos<=100:return 15
    return 0
def _capital_state(report:dict)->str:
    return str((report.get('summary') or {}).get('primary_state') or (report.get('candidates') or [{}])[0].get('state') or 'NO_CLEAR_FLOW')

def calculate_asset(asset:str,reports:dict[str,dict],previous:dict[str,dict]|None=None,config:dict|None=None)->dict:
    """Interpret canonical report fields only; no candles, range detection, or market calls."""
    c=config or load_config();m=_maps(reports);pm=_maps(previous or {});con=m['consolidation'].get(asset,{});rq=m['rqi'].get(asset,{});rp=m['personality'].get(asset,{});rs=m['relative'].get(asset,{});mom=m['momentum'].get(asset,{});chief=m['chief'].get(asset,{})
    pc=pm.get('consolidation',{}).get(asset,{});prq=pm.get('rqi',{}).get(asset,{});prs=pm.get('relative',{}).get(asset,{});pmom=pm.get('momentum',{}).get(asset,{});pch=pm.get('chief',{}).get(asset,{})
    state=str(con.get('range_state') or con.get('structural_state') or con.get('status') or 'INSUFFICIENT_DATA');valid=con.get('range_valid',con.get('range_still_valid',False));pos=_num(con.get('position_pct',rq.get('position_pct')));stage=str(mom.get('momentum_stage') or 'NO_MOMENTUM');extension=str(mom.get('overextension_risk') or 'UNKNOWN')
    atr=_num(mom.get('atr14_pct'));expansion=_num(mom.get('volatility_expansion_ratio'),1) or 1;bb=_num(mom.get('bollinger_band_width_pct'));volatility=_clip(85-(max(0,expansion-0.65)*55)-(max(0,(atr or 1.5)-2)*10)-(max(0,(bb or 5)-8)*4));volatility=max(15,volatility) if expansion<1.3 else volatility
    rsrank=_num(rs.get('percentile_rank'),50) or 50;rankchg=_num(rs.get('percentile_rank_change'),0) or 0;relacc=_num(rs.get('relative_acceleration'),0) or 0;rsdelta=_clip(45+rankchg*1.5+relacc*8+(_num(rs.get('btc_relative_return_4h'),0) or 0)*3)
    vz=_num(mom.get('volume_z_score'),0) or 0;vr=_num(mom.get('volume_ratio'),1) or 1;volume=_clip(50+min(2,max(-2,vz))*18+min(1,max(-.5,vr-1))*20);volume=20 if vz>c['overextension']['max_volume_zscore'] else volume
    accel=_num(mom.get('acceleration_4h_pct'),0) or 0;confirm=int(_num(mom.get('number_completed_closes_above_breakout'),0) or 0);dist=_num(mom.get('distance_above_breakout_pct'));momentum=_clip(_stage_score(stage)+min(20,max(-15,accel*6))+(12 if confirm==0 else -confirm*10)+(10 if extension=='LOW' else 0));
    deltas={'relative_strength_delta':round(rsrank-(_num(prs.get('percentile_rank'),rsrank) or rsrank),2),'volume_zscore_delta':round(vz-(_num(pmom.get('volume_z_score'),vz) or vz),2),'momentum_delta':round(_stage_score(stage)-_stage_score(str(pmom.get('momentum_stage') or stage))+accel-(_num(pmom.get('acceleration_4h_pct'),accel) or accel),2),'rqi_delta':round((_num(rq.get('rqi_score'),0) or 0)-(_num(prq.get('rqi_score'),_num(rq.get('rqi_score'),0)) or 0),2),'rotation_delta':0.0,'confidence_delta':round((_num((chief.get('decision_metrics') or {}).get('evidence_confidence_score'),0) or 0)-(_num((pch.get('decision_metrics') or {}).get('evidence_confidence_score'),_num((chief.get('decision_metrics') or {}).get('evidence_confidence_score'),0)) or 0),2)}
    prev_exp=_num(pmom.get('volatility_expansion_ratio'),expansion) or expansion;vol_delta=(prev_exp-expansion)*50;energy_parts={'volatility_compression':_clip(50+vol_delta),'relative_strength':_clip(50+deltas['relative_strength_delta']*2),'relative_acceleration':_clip(50+(relacc-(_num(prs.get('relative_acceleration'),relacc) or relacc))*12),'volume_zscore':_clip(50+deltas['volume_zscore_delta']*20),'momentum':_clip(50+deltas['momentum_delta']*4),'range_quality':_clip(50+deltas['rqi_delta']*3),'rotation':50,'evidence_confidence':_clip(50+deltas['confidence_delta']*2)}
    previous_available=bool(previous);energy=sum(energy_parts[k]*w/100 for k,w in c['energy_weights'].items()) if previous_available else 50
    improving=sum([deltas['relative_strength_delta']>0,deltas['volume_zscore_delta']>0,deltas['momentum_delta']>0,deltas['rqi_delta']>0,deltas['confidence_delta']>0,vol_delta>0]);cross=_clip(25+improving*12.5+(10 if rq.get('rqi_score') and rq['rqi_score']>=60 else 0));flow=_capital_state(reports.get('capital',{}));capital=85 if flow=='BROAD_RISK_ON' else 20 if flow in {'BROAD_RISK_OFF','RISK_OFF'} else 50
    fresh=str(con.get('freshness_status') or mom.get('freshness_status') or rs.get('freshness') or 'UNAVAILABLE');liq=con.get('liquidity_pass',rs.get('liquidity_pass',True));spread=con.get('spread_pass',True);quality=(45 if fresh=='FRESH' else 15)+(30 if liq else 0)+(25 if spread else 0)
    components={'volatility_compression':volatility,'range_position':_position_score(pos),'relative_strength_delta':rsdelta,'volume_buildup':volume,'momentum_precursor':momentum,'cross_module_improvement':cross,'capital_flow_alignment':capital,'data_quality':quality};components={k:round(_clip(v),2) for k,v in components.items()};early=round(sum(components[k]*w/100 for k,w in c['weights'].items()),2);combined=round(_clip(c['combined_coefficients']['current_state']*early+c['combined_coefficients']['energy_delta']*energy),2)
    r24=_num(mom.get('change_24h_pct'));r48=_num(mom.get('change_48h_pct'));reasons=[];o=c['overextension']
    if r24 is not None and r24>o['max_pre_move_24h_return_pct']:reasons.append('RETURN_24H_EXCEEDED')
    if r48 is not None and r48>o['max_pre_move_48h_return_pct']:reasons.append('RETURN_48H_EXCEEDED')
    if pos is not None and pos>o['max_range_position_pct']:reasons.append('UPPER_RANGE_POSITION')
    if extension=='HIGH':reasons.append('HIGH_EXTENSION_RISK')
    if stage=='BREAKOUT_CONFIRMED' and not o['allow_breakout_confirmed']:reasons.append('BREAKOUT_CONFIRMED')
    if stage=='EXTENDED_MOVE' and not o['allow_extended_move']:reasons.append('EXTENDED_MOVE')
    if vz>o['max_volume_zscore']:reasons.append('EXTREME_VOLUME_SPIKE')
    if (_num(mom.get('distance_above_ema20_atr'),0) or 0)>o['max_distance_above_ema_atr']:reasons.append('EMA_ATR_EXTENSION')
    structure=bool(valid) and state in VALID_STATES;too_late=bool(reasons);positive=energy>50
    if not con or not mom:classification='INSUFFICIENT_DATA'
    elif not structure:classification='INVALID_STRUCTURE'
    elif too_late:classification='TOO_LATE'
    elif combined>=c['classification']['strong'] and improving>=c['classification']['minimum_improving_modules_strong']:classification='PRE_MOVE_STRONG'
    elif combined>=c['classification']['building'] and positive:classification='PRE_MOVE_BUILDING'
    elif stage in {'EARLY_MOMENTUM','BREAKOUT_DEVELOPING'} and extension in {'LOW','MEDIUM'}:classification='EARLY_EXPANSION_DEVELOPING'
    else:classification='TOO_EARLY'
    supporting=[name for name,val in components.items() if val>=65];opposing=[name for name,val in components.items() if val<40];sample=str(rp.get('sample_quality') or rq.get('historical_sample_quality') or 'INSUFFICIENT');confidence=_clip(20+min(40,len(supporting)*8)+(20 if fresh=='FRESH' else 0)+(10 if liq else 0)+(10 if sample in {'MEDIUM','HIGH'} else 0));confidence=min(confidence,69) # no validated Early Expansion outcomes exist in V1
    refs=[str(SOURCES[n]) for n in ('consolidation','rqi','personality','relative','momentum','capital','rotation') if reports.get(n)]
    return {'asset':asset,'pair':con.get('kraken_pair') or rs.get('pair') or mom.get('kraken_pair'),'source_timestamp':mom.get('latest_completed_candle_timestamp') or con.get('latest_completed_candle_timestamp'),'freshness':fresh,'current_price':_num(mom.get('current_price',con.get('latest_available_market_price'))),'range_state':state,'range_valid':bool(valid),'range_position_pct':pos,'return_4h_pct':_num(mom.get('change_4h_pct')),'return_24h_pct':r24,'return_48h_pct':r48,'early_expansion_score':early,'energy_delta_score':round(energy,2),'combined_pre_move_score':combined,'classification':classification,'pre_move_status':'TOO_LATE' if too_late else 'PASS' if structure else 'INVALID_STRUCTURE','confidence_score':round(confidence,2),'confidence_band':'HIGH' if confidence>=70 else 'MEDIUM' if confidence>=40 else 'LOW','components':components,'change_metrics':deltas,'distance_to_breakout_pct':None if dist is None else round(abs(dist),4),'breakout_level':_num(mom.get('breakout_level')),'overextension_status':'FAIL' if too_late else 'PASS','overextension_reasons':reasons,'supporting_modules':supporting,'opposing_modules':opposing,'main_strength':max(components,key=components.get),'primary_risk':reasons[0] if reasons else min(components,key=components.get),'invalidation_condition':mom.get('invalidation_condition') or 'Current range invalidates or pre-move conditions deteriorate','activation_condition':mom.get('activation_condition') or 'Independent modules strengthen without overextension','historical_sample_quality':sample,'independent_modules_improving':improving,'previous_snapshot_available':previous_available,'source_refs':refs}

def rank(rows:list[dict])->list[dict]:
    conf={'HIGH':2,'MEDIUM':1,'LOW':0};eligible=[x for x in rows if x['classification'] in {'PRE_MOVE_STRONG','PRE_MOVE_BUILDING','EARLY_EXPANSION_DEVELOPING'} and x['overextension_status']=='PASS'];return sorted(eligible,key=lambda x:(-x['combined_pre_move_score'],-x['energy_delta_score'],-conf[x['confidence_band']],not bool(x.get('range_position_pct') is not None and x['range_position_pct']<=50),x['asset']))

def retrospective(asset:str,dates:list[str]|None=None)->dict:
    dates=dates or available_dates();observations=[]
    for i,date in enumerate(dates):
        reports=load_date(date);previous=load_date(dates[i-1]) if i else None;row=calculate_asset(asset,reports,previous)
        if row['classification'] in {'PRE_MOVE_STRONG','PRE_MOVE_BUILDING','TOO_EARLY'}:observations.append((date,row))
    eligible=next(((d,r) for d,r in observations if r['classification'] in {'PRE_MOVE_STRONG','PRE_MOVE_BUILDING'}),None);chosen=eligible or (observations[0] if observations else None)
    if not chosen:return {'asset':asset,'result':'NOT_DETECTED','earliest_eligible_timestamp':None,'look_ahead_used_for_detection':False}
    date,row=chosen;idx=dates.index(date);later=[]
    for future in dates[idx+1:idx+3]:
        fm=_maps(load_date(future))['momentum'].get(asset,{});later.append({'date':future,'return_24h_pct':_num(fm.get('change_24h_pct')),'return_48h_pct':_num(fm.get('change_48h_pct'))})
    return {'asset':asset,'result':row['classification'],'earliest_eligible_timestamp':date,'score':row['combined_pre_move_score'],'energy_delta':row['energy_delta_score'],'state':row['classification'],'price':row['current_price'],'later_observed_moves':later,'look_ahead_used_for_detection':False}

def build_report(reports:dict[str,dict],previous:dict[str,dict]|None=None,as_of:Any=None,assets:set[str]|None=None,with_retrospective:bool=True)->dict:
    maps=_maps(reports);universe=sorted(set(maps['consolidation'])|set(maps['momentum'])|set(maps['relative']));rows=[calculate_asset(a,reports,previous) for a in universe if not assets or a in assets];top=rank(rows);energy=sorted([x for x in rows if x['overextension_status']=='PASS' and x['classification'] not in {'INVALID_STRUCTURE','INSUFFICIENT_DATA'}],key=lambda x:(-x['energy_delta_score'],-x['combined_pre_move_score'],x['asset']))[:5];late=sorted([x for x in rows if x['classification']=='TOO_LATE'],key=lambda x:(-x['combined_pre_move_score'],x['asset']));date=utc_timestamp(as_of).strftime('%Y-%m-%d');ret={'PUMP':retrospective('PUMP'),'TAO':retrospective('TAO')} if with_retrospective else {'PUMP':None,'TAO':None}
    market='PRE_MOVE_CONDITIONS_PRESENT' if top else 'NO_QUALIFIED_PRE_MOVE_CANDIDATES';return {'version':'1.0.0','generated_at_utc':utc_timestamp(as_of).isoformat(),'report_date':date,'labels':load_config()['labels'],'target_move_pct':[3,5],'target_horizon_hours':[12,48],'probability_claim':False,'market_state':market,'summary':{'assets_evaluated':len(rows),'pre_move_candidates':len(top),'pre_move_strong':sum(x['classification']=='PRE_MOVE_STRONG' for x in rows),'pre_move_building':sum(x['classification']=='PRE_MOVE_BUILDING' for x in rows),'too_late':len(late)},'assets':rows,'top_pre_move_candidates':top[:10],'top_energy_delta':energy,'top_pre_move_range_setups':sorted(top,key=lambda x:(-x['components']['range_position'],-x['combined_pre_move_score'],x['asset']))[:5],'top_pre_move_momentum_setups':sorted(top,key=lambda x:(-x['components']['momentum_precursor'],-x['combined_pre_move_score'],x['asset']))[:5],'too_late_watch':late[:10],'retrospectives':ret,'methodology':{'canonical_reports_only':True,'no_look_ahead_detection':True,'rebuilds_source_modules':False}}

def _previous_date(as_of:str)->str|None:
    return max((d for d in available_dates() if d<as_of),default=None)
def _clean(v:Any)->Any:
    if isinstance(v,float) and not math.isfinite(v):return None
    if isinstance(v,dict):return {k:_clean(x) for k,x in v.items()}
    if isinstance(v,list):return [_clean(x) for x in v]
    return v
def render_markdown(r:dict)->str:
    s=r['summary'];lines=['# Early Expansion Engine V1','','RESEARCH_ONLY | NOT_A_BUY_SIGNAL | NOT_A_SELL_SIGNAL | USER_DECISION_REQUIRED | LIVE_NOT_AUTHORIZED','','## Market Summary','',f"- State: {r['market_state']}",f"- Assets evaluated: {s['assets_evaluated']}",f"- Pre-move candidates: {s['pre_move_candidates']}",f"- PRE_MOVE_STRONG: {s['pre_move_strong']}",f"- PRE_MOVE_BUILDING: {s['pre_move_building']}",f"- Too late: {s['too_late']}",'','## Top Pre-Move Candidates','']
    for x in r['top_pre_move_candidates']:lines += [f"### {x['asset']}",f"- Classification: {x['classification']} | combined: {x['combined_pre_move_score']} | energy: {x['energy_delta_score']}",f"- Confidence: {x['confidence_score']} ({x['confidence_band']})",f"- Range position: {x['range_position_pct']}% | 24h return: {x['return_24h_pct']}% | breakout distance: {x['distance_to_breakout_pct']}%",f"- Main strength: {x['main_strength']}",f"- Primary risk: {x['primary_risk']}",'']
    lines += ['## Fastest Energy Build','']+[f"- {x['asset']}: energy {x['energy_delta_score']}, combined {x['combined_pre_move_score']}" for x in r['top_energy_delta']]+['','## Too Late / Already Extended','']+[f"- {x['asset']}: {', '.join(x['overextension_reasons'])}" for x in r['too_late_watch'][:5]]
    for a in ('PUMP','TAO'):lines += ['',f'## {a} Retrospective','',f"- {json.dumps(r['retrospectives'].get(a),sort_keys=True)}"]
    lines += ['','## Methodology','','- Current-state score combines eight explicitly weighted components.','- Energy Delta compares only the current report with an earlier available snapshot.','- Combined score weights current state at 65% and Energy Delta at 35%.','- Confirmed breakouts and extended moves are excluded from the pre-move ranking.','- Rankings use deterministic asset-symbol tie-breaking.','- The target research horizon is 12–48 hours for a 3–5% move.','','## Source Coverage','','- Daily Consolidation: current structure and range position.','- Range Quality Index: structural quality and daily change.','- Range Personality: historical sample quality.','- Relative Strength: rank, returns, acceleration, and persistence.','- Momentum Breakout Radar: stage, volatility, volume, and extension.','- Capital Flow: broad environment alignment.','- BTC Rotation and Chief Strategist: supplementary evidence changes.','','## Limitations','','- Uses existing canonical reports only; it does not rebuild source indicators.','- Energy Delta is neutral when no prior snapshot exists.','- Confidence is evidence quality, not probability.','- Retrospective detection uses only information available at each evaluated timestamp.','- No execution action is authorized.'];return '\n'.join(lines)+'\n'
def write_outputs(r:dict)->Path:
    r=_clean(r);OUT.mkdir(parents=True,exist_ok=True);date=r['report_date'];text=json.dumps(r,indent=2,sort_keys=True,allow_nan=False)+'\n';md=render_markdown(r)
    for p in (OUT/f'{date}_early_expansion.json',OUT/'latest_early_expansion.json'):atomic_write(p,text)
    for p in (OUT/f'{date}_early_expansion.md',OUT/'latest_early_expansion.md'):atomic_write(p,md)
    fields=['asset','pair','classification','pre_move_status','early_expansion_score','energy_delta_score','combined_pre_move_score','confidence_score','confidence_band','range_position_pct','return_24h_pct','distance_to_breakout_pct','main_strength','primary_risk']
    for p in (OUT/f'{date}_early_expansion.csv',OUT/'latest_early_expansion.csv'):
        t=p.with_suffix('.csv.tmp')
        with t.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:x.get(k) for k in fields} for x in r['assets'])
        os.replace(t,p)
    reg={'module_name':'early_expansion','status':'OK','generated_at_utc':r['generated_at_utc'],'market_state':r['market_state'],'labels':r['labels'],'top_pre_move_candidates':r['top_pre_move_candidates'][:5],'top_energy_delta_candidates':r['top_energy_delta'][:3],'too_late_candidates':r['too_late_watch'][:3],'risks':[{'asset':x['asset'],'risk':x['primary_risk']} for x in r['too_late_watch'][:5]],'unknowns':[{'asset':x['asset'],'unknown':'NO_PREVIOUS_SNAPSHOT'} for x in r['assets'] if not x['previous_snapshot_available']][:5],'retrospectives':r['retrospectives']};atomic_write(REGISTRY,json.dumps(reg,indent=2,sort_keys=True,allow_nan=False)+'\n');return (OUT/'latest_early_expansion.json').resolve()
def generate(as_of:Any=None,assets:set[str]|None=None,with_retrospective:bool=True)->tuple[dict,Path]:
    date=utc_timestamp(as_of).strftime('%Y-%m-%d');reports=load_current();pd=_previous_date(date);previous=load_date(pd) if pd else None;r=build_report(reports,previous,as_of,assets,with_retrospective);return r,write_outputs(r)
def main():
    p=argparse.ArgumentParser();p.add_argument('--assets');p.add_argument('--as-of');p.add_argument('--reuse-existing-data',action='store_true');p.add_argument('--retrospective',action='store_true');p.add_argument('--verbose',action='store_true');a=p.parse_args();assets={x.strip().upper() for x in a.assets.split(',')} if a.assets else None;r,path=generate(a.as_of,assets,a.retrospective);s=r['summary'];print('Early Expansion Engine V1: SUCCESS');print(f"Assets evaluated: {s['assets_evaluated']}");print(f"Pre-move candidates: {s['pre_move_candidates']}");print(f"PRE_MOVE_STRONG: {s['pre_move_strong']}");print(f"PRE_MOVE_BUILDING: {s['pre_move_building']}");print(f"Too late: {s['too_late']}");print(f'Saved: {path}');
    if a.verbose:print(json.dumps(s,sort_keys=True))
if __name__=='__main__':main()
