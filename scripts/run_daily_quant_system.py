from __future__ import annotations
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from typing import Any,Callable
from run_complete_daily_research import run as run_complete_research
from print_market_transition_history import independent_observations,load_history
from print_range_fixed_5_v2_status import read_status as read_v2_status
from range_fixed_5_v2_clock import clock_safety_preflight
from range_fixed_5_v2_storage import DB_PATH,STRATEGY_ID
from weekly_consolidation_common import ROOT,atomic_write
from strategy_evidence_audit import OUT_JSON as EVIDENCE_PATH, run as run_evidence_audit
from forward_validation_board import BOARD_JSON as FORWARD_BOARD_PATH, refresh as refresh_forward_board
from market_memory_opportunity import MEMORY as MARKET_MEMORY_PATH,build_market_memory,write_memory,append_opportunity_observations,opportunity_context

OUT=ROOT/'DAILY_REPORTS/CHATGPT_HANDOFF'
PATHS={'chief':ROOT/'DAILY_REPORTS/CHATGPT_EXPORT/latest_ai_chief_strategist_packet.json','memory':ROOT/'DAILY_REPORTS/CHATGPT_EXPORT/latest_ai_research_memory_packet.json','capital':ROOT/'CAPITAL_EFFICIENCY/latest_capital_efficiency.json','transition':ROOT/'RESEARCH_MEMORY/market_transition/latest.json','evidence':EVIDENCE_PATH,'forward_board':FORWARD_BOARD_PATH}
V2_RUNNER=ROOT/'scripts/range_fixed_5_v2_official_runner.py'

def utc(value:Any=None)->datetime:
 p=datetime.now(timezone.utc) if value is None else value if isinstance(value,datetime) else datetime.fromisoformat(str(value).replace('Z','+00:00'))
 if p.tzinfo is None or p.utcoffset() is None:raise ValueError('timestamp must be timezone-aware')
 return p.astimezone(timezone.utc)
def read_json(path:Path)->dict:
 x=json.loads(path.read_text())
 if not isinstance(x,dict):raise ValueError('top-level JSON is not an object')
 return x
def age(value:Any,now:datetime)->float|None:
 try:return max(0.0,(now-utc(value)).total_seconds())
 except (TypeError,ValueError):return None
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()

def transition_changes(now:datetime)->tuple[list[dict],list[str]]:
 rows,warnings=load_history(hours=24,now=now);obs=independent_observations(rows)
 if len(obs)<2:return [],warnings+['INSUFFICIENT_INDEPENDENT_OBSERVATIONS']
 old,new=obs[-2:];out=[]
 getters={'market_state':lambda x:x.get('market_state'),'breadth_above_ema20_pct':lambda x:x.get('breadth',{}).get('above_ema20_pct'),'sell_pressure_4h':lambda x:x.get('sell_pressure',{}).get('4h',{}).get('classification'),'btc_structure_1h':lambda x:x.get('btc_structure_1h',{}).get('trend')}
 for field,getter in getters.items():
  before,after=getter(old),getter(new)
  if before!=after:out.append({'field':field,'previous':before,'current':after})
 return out,warnings

def memory_section(memory:dict)->dict:
 return {'status':memory.get('status','RESEARCH_MEMORY_UNAVAILABLE'),'strategies':[{'strategy':x.get('strategy'),'oos_n':x.get('oos_n'),'expected_value_pct':x.get('oos_ev'),'profit_factor':x.get('oos_pf'),'ev_95_ci_pct':[x.get('oos_ev_ci_lower'),x.get('oos_ev_ci_upper')],'validation_status':x.get('oos_status')} for x in memory.get('oos_summary',[])],'statistical_warnings':memory.get('research_memory_statistical_warnings',[]),'warnings':memory.get('warnings',[])}

def evidence_section(evidence:dict)->list[dict]:
 out=[]
 for x in evidence.get('strategies',[]):
  s=x.get('sample_structure',{});stat=x.get('statistics',{});naive=x.get('naive_ci',{});cluster=x.get('cluster_aware_ci',{});regime=x.get('regime_coverage',{})
  out.append({'strategy':x.get('strategy_name'),'classification':x.get('classification'),'raw_n':s.get('raw_episode_n'),'diagnostic_effective_n':s.get('diagnostic_effective_n'),'ev_pct':stat.get('ev_pct'),'naive_ci_pct':[naive.get('lower_pct'),naive.get('upper_pct')],'cluster_aware_ci_pct':[cluster.get('lower_pct'),cluster.get('upper_pct')],'regime_coverage':regime.get('observed',[]),'alias_status':x.get('alias_status'),'alias_group':x.get('alias_group'),'major_warning':(x.get('major_warnings') or [None])[0]})
 return out

def forward_board_section(board:dict)->list[dict]:
 return [{'strategy':x.get('strategy_name'),'aliases':x.get('aliases',[]),'governance_state':x.get('governance_state'),'execution_hash_short':str(x.get('execution_definition_hash',''))[:12],'historical_clustered_ci_95':x.get('historical_clustered_ci_95'),'forward_completed_outcomes':x.get('completed_outcomes'),'independent_forward_clusters':x.get('independent_signal_clusters'),'forward_ev_pct':x.get('forward_ev_pct'),'forward_clustered_ci_95':x.get('forward_clustered_ci_95'),'regime_coverage':x.get('regime_coverage',[]),'major_warning':(x.get('major_warnings') or [None])[0],'next_required_evidence':x.get('next_required_evidence')} for x in board.get('entries',[])]

def forward_attention(v2:dict,now:datetime)->dict|None:
 count=int(v2.get('open_observations') or 0)
 if not count:return None
 expired=0
 try:
  import sqlite3
  with sqlite3.connect(f'file:{DB_PATH.resolve()}?mode=ro&immutable=1',uri=True) as db:
   expired=sum(utc(row[0])<now for row in db.execute('SELECT expiry_timestamp FROM v2_open_observations'))
 except Exception:
  expired=0
 return {'experiment':STRATEGY_ID,'open_observations':count,'expired_unresolved':expired,'required_command':'./forward-monitor'}

def candidate_section(chief:dict,now:datetime)->list[dict]:
 tactical={str(x.get('asset')):x for bucket in ('daily','weekly','avoid') for x in chief.get('tactical_opportunities',{}).get(bucket,[])};out=[]
 for c in chief.get('candidates',[]):
  asset=str(c.get('asset'));d=c.get('current_data',{});m=c.get('momentum',{});decision=c.get('decision_metrics',{});validation=c.get('validation',{});rotation=c.get('rotation',{});con=c.get('consolidation',{});t=tactical.get(asset,{})
  validated=validation.get('validation_grade')=='AVAILABLE' and rotation.get('edge_validation_status') in {'VALIDATED','OOS_VALIDATED'}
  rr_valid=validated and con.get('downside_to_invalidation_pct') not in (None,0) and (con.get('rr_to_midpoint') is not None or con.get('rr_to_high') is not None)
  analysis_ts=d.get('analysis_price_timestamp',d.get('source_timestamp'))
  out.append({'asset':asset,'analysis_price':d.get('analysis_price',d.get('current_price')),'analysis_price_timestamp':analysis_ts,'analysis_age_seconds':age(analysis_ts,now),'live_reference_price':d.get('live_reference_price'),'live_reference_timestamp':d.get('live_reference_timestamp'),'live_price_status':d.get('live_price_status','LIVE_PRICE_UNAVAILABLE'),'live_price_age_seconds':d.get('live_price_age_seconds'),'price_drift_pct':d.get('price_drift_pct'),'technical_state':m.get('stage') or decision.get('current_primary_hypothesis'),'activation':m.get('activation_condition') or t.get('activation_requirements'),'invalidation':m.get('invalidation_condition') or c.get('evidence',{}).get('invalidation_condition'),'setup_quality':{'score':t.get('setup_quality_score'),'state':decision.get('current_primary_hypothesis')},'evidence_quality':{'score':decision.get('evidence_confidence_score'),'band':decision.get('confidence_band'),'sample_size':validation.get('historical_sample_size'),'validation_grade':validation.get('validation_grade')},'actionability':{'score':t.get('actionability_score'),'recommendation':t.get('recommendation'),'technical_action':t.get('technical_action')},'expected_edge':{'value':rotation.get('validated_expected_edge') if validated else rotation.get('theoretical_target_edge') or rotation.get('net_edge_after_costs'),'status':'VALIDATED' if validated else 'UNVALIDATED_EDGE'},'risk_reward':{'to_midpoint':con.get('rr_to_midpoint'),'to_high':con.get('rr_to_high'),'status':'VALID'} if rr_valid else {'to_midpoint':None,'to_high':None,'status':'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}})
 return out

def conflict_section(rows:list[dict])->list[dict]:
 out=[]
 for x in rows:
  flags=[]
  if x['actionability'].get('recommendation') in {'ACTIONABLE','SPECULATIVE_REVIEW'} and x['expected_edge']['status']=='UNVALIDATED_EDGE':flags.append('TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED')
  if (x['setup_quality'].get('score') or 0)>=70 and x['risk_reward']['status']!='VALID':flags.append('HIGH_SCORE + INVALID_RANGE')
  if x['evidence_quality'].get('band')=='HIGH' and x.get('technical_state')=='NO_MOMENTUM':flags.append('STRONG_RS + NO_MOMENTUM')
  if x.get('price_drift_pct') is not None and (x.get('analysis_age_seconds') or 0)>28800:flags.append('LIVE_PRICE_DRIFT + OLD_ANALYSIS_SNAPSHOT')
  if flags:out.append({'asset':x['asset'],'conflicts':flags})
 return out

def build_handoff(chief:dict,memory:dict,capital:dict,transition:dict,v2:dict,result:dict,now:Any,paths:dict[str,Path],changes:list[dict],warnings:list[str])->dict:
 current=utc(now);candidates=candidate_section(chief,current);stale=[x['asset'] for x in candidates if x['analysis_age_seconds'] is None or x['analysis_age_seconds']>28800];live_missing=[x['asset'] for x in candidates if x['live_price_status']!='LIVE_PRICE_AVAILABLE'];missing=[k for k in ('chief','memory','capital') if not paths[k].exists()]
 cutoff=max((x['analysis_price_timestamp'] for x in candidates if x['analysis_price_timestamp']),default=transition.get('market_data_timestamp'));failures=list(result.get('warnings',[]))
 required_failure=any(str(x).startswith(('export:','chief_strategist_or_observations:','RESEARCH_MEMORY_UNAVAILABLE:','CAPITAL_EFFICIENCY_UNAVAILABLE:')) for x in failures)
 status='FAILED_REQUIRED_DATA' if not result.get('success') or missing or stale or required_failure else 'OK_WITH_WARNINGS' if failures or warnings or live_missing else 'OK'
 health={'coverage':{'candidates':len(candidates),'live_prices':len(candidates)-len(live_missing)},'stale_inputs':stale,'clock_safety':v2.get('clock_safety','UNAVAILABLE'),'module_failures':failures,'warnings':sorted(set(warnings+(['LIVE_PRICE_UNAVAILABLE_OR_STALE'] if live_missing else []))),'required_missing':missing}
 unknown=list(chief.get('unknowns',[]))+([{'unknown':'LIVE_REFERENCE_UNAVAILABLE','assets':live_missing}] if live_missing else [])
 return {'schema_version':'1.0.0','run_metadata':{'run_timestamp':current.isoformat(),'market_data_cutoff':cutoff,'hashes':{k:sha(p) for k,p in paths.items() if p.exists()},'data_freshness':{'analysis_stale_assets':stale,'live_unavailable_or_stale_assets':live_missing},'pipeline_status':status,'objective':chief.get('objective')},'system_health':health,'market_state':{'btc_structure':{'1h':transition.get('btc_structure_1h'),'4h':transition.get('btc_structure_4h')},'regime':chief.get('market_state',{}).get('crypto_regime'),'breadth':transition.get('breadth'),'sell_pressure':transition.get('sell_pressure'),'capital_flow':chief.get('capital_flow'),'market_transition_state':transition.get('market_state')},'changes_since_previous_independent_observation':changes,'research_memory':memory_section(memory),'current_candidates':candidates,'forward_experiments':[{'experiment_name':STRATEGY_ID,'activation_state':v2.get('collection_state','UNAVAILABLE'),'signals':v2.get('signals'),'open_observations':v2.get('open_observations'),'completed_outcomes':v2.get('completed_outcomes'),'batch_dependence_warnings':['SIMULTANEOUS_SIGNAL_COUNT_IS_BATCH_DEPENDENT'],'monitoring_health':v2.get('clock_safety','UNAVAILABLE'),'official_monitor_runner':'AVAILABLE_NOT_RUN_READ_ONLY_ORCHESTRATOR' if V2_RUNNER.exists() else 'OFFICIAL_MONITOR_RUNNER_NOT_FOUND','trading_capability':'DISABLED'}],'forward_experiment_attention':forward_attention(v2,current),'conflicts':conflict_section(candidates),'what_we_do_not_know':unknown,'next_research_checks':['Observe the next completed market-data cutoff.','Check stale inputs and technical activation/invalidation conditions.','Accumulate independent OOS and forward outcomes; do not infer validation from actionability.']}

def render(packet:dict)->str:
 lines=['# Daily Quant ChatGPT Handoff','',f"Run: {packet['run_metadata']['run_timestamp']}",f"Pipeline status: {packet['run_metadata']['pipeline_status']}",f"Market-data cutoff: {packet['run_metadata']['market_data_cutoff']}"]
 for title,key in [('System Health','system_health'),('Market State','market_state'),('Changes Since Previous Independent Observation','changes_since_previous_independent_observation'),('Research Memory','research_memory'),('Strategy Evidence','strategy_evidence'),('FORWARD VALIDATION BOARD','forward_validation_board')]:lines+=['',f'## {title}','',json.dumps(packet[key],sort_keys=True)]
 lines+=['','## Current Candidates','']
 for x in packet['current_candidates']:lines += [f"### {x['asset']}",f"- Analysis snapshot price/time: {x['analysis_price']} / {x['analysis_price_timestamp']}",f"- Kraken live reference/time: {x['live_reference_price'] if x['live_price_status']=='LIVE_PRICE_AVAILABLE' else x['live_price_status']} / {x['live_reference_timestamp']}",f"- Setup quality: {x['setup_quality']}",f"- Evidence quality: {x['evidence_quality']}",f"- Actionability: {x['actionability']}",f"- Expected edge: {x['expected_edge']}",f"- R/R: {x['risk_reward']}",f"- Activation / invalidation: {x['activation']} / {x['invalidation']}"]
 for title,key in [('Forward Experiments','forward_experiments'),('Conflicts','conflicts'),('What We Do Not Know','what_we_do_not_know'),('Next Research Checks','next_research_checks')]:lines+=['',f'## {title}','']+[f"- {x if isinstance(x,str) else json.dumps(x,sort_keys=True)}" for x in packet[key]]
 return '\n'.join(lines)+'\n'

def canonical_decision_sections(packet:dict,chief:dict,memory30:dict,opportunity:dict)->dict:
 return {
  'CURRENT_MARKET':{'market_state':packet['market_state'],'source_cutoff':memory30['coverage']['latest_cutoff'],'observation_type':'OBSERVED'},
  'MARKET_TRAJECTORY_7D_30D':memory30['trajectory'],
  'BROAD_OPPORTUNITY_WATCHLIST':{'status':opportunity['watchlist_status'],'candidates':opportunity['watchlist']},
  'TOP_RAW_OPPORTUNITY_COMPONENTS':[{'rank':x['rank'],'asset':x['asset'],'components':x['raw_opportunity_components']} for x in opportunity['watchlist'][:10]],
  'BTC_CASH_BENCHMARK_CONTEXT':opportunity['btc_cash_benchmark'],
  'OPPORTUNITY_HISTORY_SUMMARY':opportunity['history_summary'],
  'EDGE_RESEARCH_SUMMARY':{'strategies':packet.get('strategy_evidence',[]),'interpretation':'SEPARATE_FROM_CURRENT_TECHNICAL_OPPORTUNITY'},
  'FORWARD_VALIDATION_SUMMARY':{'experiments':packet.get('forward_experiments',[]),'board':packet.get('forward_validation_board',[])},
  'SYSTEM_HEALTH':{**packet['system_health'],'trading_capability':'DISABLED'},
  'WHAT_WE_DO_NOT_KNOW':packet['what_we_do_not_know']+['Opportunity ranking is heuristic and does not establish predictive edge.'],
  'SOURCE_REFERENCES':{'market_memory':str(MARKET_MEMORY_PATH.relative_to(ROOT)),'opportunity_observations':'DATASETS/TACTICAL_OUTCOMES/tactical_candidate_snapshots.jsonl','opportunity_events':'DATASETS/TACTICAL_OUTCOMES/tactical_outcome_events.jsonl','forward_registry':'RESEARCH_REPORTS/forward_validation_registry.json'},
 }

def orchestrate(objective='btc',as_of=None,no_network=False,reuse=False,runner:Callable[...,dict]=run_complete_research,out_dir:Path=OUT)->tuple[dict,Path,Path]:
 now=utc(as_of);order=['complete_daily_research'];result=runner(objective=objective,as_of=as_of,no_network=no_network,reuse=reuse);loaded={};warnings=[]
 if runner is run_complete_research:
  try:run_evidence_audit();refresh_forward_board(current=now)
  except Exception as exc:warnings.append(f'STRATEGY_EVIDENCE_AUDIT_UNAVAILABLE: {exc}')
 for name,path in PATHS.items():
  try:loaded[name]=read_json(path)
  except Exception as exc:loaded[name]={};warnings.append(f'{name.upper()}_UNAVAILABLE: {exc}')
 order+=['market_transition_summary']
 try:changes,extra=transition_changes(now);warnings+=extra
 except Exception as exc:changes=[];warnings.append(f'MARKET_TRANSITION_SUMMARY_UNAVAILABLE: {exc}')
 order+=['research_memory_summary','capital_efficiency_summary','range_fixed_5_v2_status']
 try:v2=read_v2_status(DB_PATH,now);v2['clock_safety']=clock_safety_preflight()['status']
 except Exception as exc:v2={'clock_safety':'UNAVAILABLE'};warnings.append(f'V2_STATUS_UNAVAILABLE: {exc}')
 packet=build_handoff(loaded['chief'],loaded['memory'],loaded['capital'],loaded['transition'],v2,result,now,PATHS,changes,warnings);packet['strategy_evidence']=evidence_section(loaded.get('evidence',{}));packet['forward_validation_board']=forward_board_section(loaded.get('forward_board',{}));packet['run_metadata']['dependency_order']=order+['strategy_evidence_audit','forward_validation_board']
 memory30=build_market_memory(now=now);write_memory(memory30);append_opportunity_observations(loaded['chief'])
 opportunity=opportunity_context(loaded['chief'],memory30,result.get('tactical_outcomes') or {})
 packet.update(canonical_decision_sections(packet,loaded['chief'],memory30,opportunity))
 packet['run_metadata']['dependency_order']+=['market_memory_30d','opportunity_discovery_v1','canonical_decision_handoff']
 out_dir.mkdir(parents=True,exist_ok=True);jp=out_dir/'latest_quant_handoff.json';mp=out_dir/'latest_quant_handoff.md';atomic_write(jp,json.dumps(packet,indent=2,sort_keys=True,allow_nan=False)+'\n',backup=False);atomic_write(mp,render(packet),backup=False);return packet,jp,mp

def main():
 p=argparse.ArgumentParser();p.add_argument('--objective',choices=['btc','usd'],default='btc');p.add_argument('--as-of');p.add_argument('--no-network',action='store_true');p.add_argument('--reuse-existing-data',action='store_true');a=p.parse_args();packet,jp,mp=orchestrate(a.objective,a.as_of,a.no_network,a.reuse_existing_data);print(jp.resolve());print(mp.resolve())
 attention=packet.get('forward_experiment_attention')
 if attention:print(f"\nFORWARD EXPERIMENT ATTENTION REQUIRED\n\n{attention['experiment']}\nopen observations: {attention['open_observations']}\nexpired unresolved: {attention['expired_unresolved']}\nrequired command: {attention['required_command']}")
 if packet['run_metadata']['pipeline_status']=='FAILED_REQUIRED_DATA':raise SystemExit(1)
if __name__=='__main__':main()
