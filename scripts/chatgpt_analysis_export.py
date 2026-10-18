from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from typing import Any
from lib.decision_registry import read_all
from lib.research_module_contract import sanitize
from weekly_consolidation_common import ROOT,atomic_write,utc_timestamp
OUT=ROOT/"DAILY_REPORTS/CHATGPT_EXPORT";MAX_PACKET_BYTES=1_000_000;TARGET_PACKET_BYTES=500_000;MAX_UNIQUE_ASSETS=12;MAX_RISKS=10;MAX_CONFLICTS=8;MAX_CONFIRMATIONS=8;MAX_UNKNOWNS=8;MAX_ANALYST_QUESTIONS=6;MAX_SOURCE_INDEX=30
def impact_components(asset:str,evidence:dict,current:str,use_portfolio:bool=False)->dict[str,float]:
    result={'signal_evidence_strength':min(20,len(evidence)*5),'confidence':15 if any(float(v.get('evidence_confidence_score',0) or 0)>=60 for v in evidence.values() if isinstance(v,dict)) else 6,'risk_magnitude':15 if any(v.get('risk_flags') for v in evidence.values() if isinstance(v,dict)) else 5,'freshness':10 if all(v.get('freshness','FRESH')=='FRESH' for v in evidence.values() if isinstance(v,dict)) else 2,'cross_module_agreement':min(10,len(evidence)*2)}
    if use_portfolio:result.update(relevance_to_current_holding=25 if asset==current else 8,portfolio_exposure=5 if asset==current else 0)
    return result
def impact(asset:str,evidence:dict,current:str,use_portfolio:bool=False)->float:return sum(impact_components(asset,evidence,current,use_portfolio).values())
def unified_candidates(registry:dict,current:str,use_portfolio:bool=False)->list[dict]:
    gathered={}
    mapping={'consolidation':('candidates',4),'momentum':('candidates',5),'relative_strength':('top_leaders',5),'btc_rotation':('top_candidates',3),'ai_confidence':('candidates',5),'opportunity_aging':('new_opportunities',5)}
    for module,(key,limit) in mapping.items():
        for row in registry.get(module,{}).get(key,[])[:limit]:
            asset=row.get('asset');
            if not asset:continue
            concise={k:v for k,v in row.items() if k in {'asset','rank','classification','score','relative_strength_score','momentum_stage','momentum_breakout_score','simple_zone','position_pct','range_quality','alt_rotation_score','score_advantage','evidence_confidence_score','confidence_band','freshness','freshness_status','source_timestamp','invalidation_condition','risk_flags','age_hours'}}
            concise.update({'source_module':module,'source_file':registry[module].get('source_file'),'source_timestamp':registry[module].get('generated_at_utc'),'freshness':registry[module].get('freshness'),'config_version':'1.0'})
            gathered.setdefault(str(asset),{})[module]=sanitize(concise)
    rows=[{'asset':a,'evidence':e,'decision_impact_score':impact(a,e,current,use_portfolio),'decision_impact_components':impact_components(a,e,current,use_portfolio)} for a,e in gathered.items()];return sorted(rows,key=lambda r:(-r['decision_impact_score'],r['asset']))[:MAX_UNIQUE_ASSETS]
def build_packet(objective='btc',current_holding='BTC',as_of:Any=None,use_portfolio:bool=False)->dict:
    reg=read_all();now=utc_timestamp(as_of);rotation=reg.get('btc_rotation',{});candidates=unified_candidates(reg,current_holding.upper(),use_portfolio);risks=[];conflicts=[];confirm=[];unknown=[];sources=[]
    for name,r in reg.items():
        risks += [{'module':name,'risk':x} for x in r.get('risks',[])]
        conflicts += [{'module':name,**x} if isinstance(x,dict) else {'module':name,'conflict':x} for x in r.get('conflicts',[])]
        confirm += [{'module':name,**x} if isinstance(x,dict) else {'module':name,'confirmation':x} for x in r.get('confirmations',[])]
        unknown += [{'module':name,'unknown':x} for x in r.get('unknowns',[])]
        if r.get('source_file'):sources.append({'module':name,'path':r['source_file'],'timestamp':r.get('generated_at_utc'),'freshness':r.get('freshness'),'config_version':'1.0'})
    packet={'packet_version':'1.0.0','generated_at_utc':now.isoformat(),'report_date':now.strftime('%Y-%m-%d'),'objective':'BTC_ACCUMULATION' if objective=='btc' else 'USD_GROWTH','current_holding':current_holding.upper(),'run_status':{n:r.get('status','UNAVAILABLE') for n,r in reg.items()},'market_context':reg.get('market_regime',{}).get('summary',{}),'portfolio':reg.get('portfolio',{}).get('summary',{}),'decision_summary':{'rotation_state':rotation.get('summary',{}).get('preferred_state'),'candidate_count':len(candidates)},'top_candidates':candidates,'relative_strength':reg.get('relative_strength',{}).get('summary',{}),'sector_leadership':reg.get('leadership_rotation',{}).get('summary',{}),'capital_flow':reg.get('capital_flow',{}).get('summary',{}),'ai_confidence':reg.get('ai_confidence',{}).get('summary',{}),'opportunity_aging':reg.get('opportunity_aging',{}).get('summary',{}),'rotation':rotation.get('summary',{}),'module_conflicts':conflicts[:MAX_CONFLICTS],'module_confirmations':confirm[:MAX_CONFIRMATIONS],'risks':risks[:MAX_RISKS],'unknowns':unknown[:MAX_UNKNOWNS],'analyst_questions':['Which scenario best explains current cross-module evidence?','Which invalidations matter most for the current holding?','Does any candidate justify manual rotation review after costs?'][:MAX_ANALYST_QUESTIONS],'data_quality':reg.get('data_quality',{}).get('summary',{}),'source_index':sources[:MAX_SOURCE_INDEX]}
    packet['research_mode']='PORTFOLIO' if use_portfolio else 'MARKET_ONLY'
    if not use_portfolio:
        packet.pop('current_holding',None);packet.pop('portfolio',None);packet['analyst_questions']=[x.replace('the current holding','the market benchmark') for x in packet['analyst_questions']]
    original=len(json.dumps(sanitize(packet)).encode());rules=[];removed=0
    if original>TARGET_PACKET_BYTES:
        packet['source_index']=packet['source_index'][:10];rules.append('reduced low-impact source metadata')
        while len(json.dumps(sanitize(packet)).encode())>TARGET_PACKET_BYTES and len(packet['top_candidates'])>5:packet['top_candidates'].pop();removed+=1
        if removed:rules.append('removed low-impact candidate records')
    final=len(json.dumps(sanitize(packet)).encode());packet['packet_compression']={'original_bytes':original,'final_bytes':final,'records_removed':removed,'rules_applied':rules};
    if final>MAX_PACKET_BYTES:raise ValueError('standard packet exceeds hard size limit')
    return sanitize(packet)
def markdown(packet:dict,full_path:Path)->str:
    lines=['# ChatGPT Analysis Packet','',f"Generated: {packet['generated_at_utc']}",f"Objective: {packet['objective']}",f"Research mode: {packet['research_mode']}",'','## Top candidates','']
    lines += [f"- {r['asset']} | impact {r['decision_impact_score']:.1f} | modules {', '.join(r['evidence'])}" for r in packet['top_candidates']]
    for title,key in [('Confirmations','module_confirmations'),('Conflicts','module_conflicts'),('Risks','risks'),('Unknowns','unknowns'),('Analyst questions','analyst_questions')]:lines += ['',f'## {title}','']+[f"- {json.dumps(x,ensure_ascii=False)}" if not isinstance(x,str) else f'- {x}' for x in packet[key]]
    lines += ['',f'Full bundle: {full_path}','', 'RESEARCH_ONLY | USER_DECISION_REQUIRED'];return '\n'.join(lines)+'\n'
def generate(objective='btc',current_holding='BTC',as_of:Any=None,include_full=True,include_raw_features=False,use_portfolio=False):
    packet=build_packet(objective,current_holding,as_of,use_portfolio);date=packet['report_date'];OUT.mkdir(parents=True,exist_ok=True);base=OUT/f'{date}_chatgpt_analysis_packet';latest=OUT/'latest_chatgpt_analysis_packet.json';full_path=OUT/f'{date}_chatgpt_full_research_bundle.json';reg=read_all();full={'bundle_version':'1.0.0','generated_at_utc':packet['generated_at_utc'],'registry':reg,'source_manifest':packet['source_index'],'hashes':{x['path']:hashlib.sha256(Path(x['path']).read_bytes()).hexdigest() for x in packet['source_index'] if Path(x['path']).is_file()},'raw_features_included':include_raw_features}
    if include_raw_features:
        p=ROOT/'DATASETS/FEATURE_STORE/latest_market_features.csv';full['raw_features']=p.read_text() if p.exists() else None
    atomic_write(base.with_suffix('.json'),json.dumps(packet,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n');atomic_write(latest,base.with_suffix('.json').read_text(),backup=False);atomic_write(OUT/f'latest_chatgpt_full_research_bundle.json',json.dumps(sanitize(full),indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n',backup=False);atomic_write(full_path,(OUT/'latest_chatgpt_full_research_bundle.json').read_text(),backup=False);md=markdown(packet,full_path);atomic_write(base.with_suffix('.md'),md);atomic_write(OUT/'latest_chatgpt_analysis_packet.md',md,backup=False);return packet,latest,OUT/'latest_chatgpt_full_research_bundle.json'
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--objective',choices=['btc','usd'],default='btc');p.add_argument('--current-holding',default='BTC');p.add_argument('--as-of');p.add_argument('--include-raw-features',action='store_true');a=p.parse_args();_,path,_=generate(a.objective,a.current_holding,a.as_of,True,a.include_raw_features);print(path)
