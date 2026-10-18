from __future__ import annotations

import argparse,hashlib,json,math,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

from lib.research_memory import ROOT,atomic_json,maximum_drawdown
from print_range_fixed_5_v2_status import read_status
from range_fixed_5_v2_storage import DB_PATH as V2_DB,STRATEGY_ID,active_manifest,load_config,sha256_json
from strategy_evidence_audit import OUT_JSON as AUDIT_PATH,bootstrap_ci,concentration,metrics,normalized_timestamp

REPORT_DIR=ROOT/'RESEARCH_REPORTS';REGISTRY=REPORT_DIR/'forward_validation_registry.json';BOARD_JSON=REPORT_DIR/'forward_validation_board_latest.json';BOARD_MD=REPORT_DIR/'forward_validation_board_latest.md';MANIFEST_DIR=REPORT_DIR/'FORWARD_FREEZE_MANIFESTS';GATES_PATH=ROOT/'config/forward_validation_gates_v1.json'
STATES=('RESEARCH','CANDIDATE_FOR_FREEZE','FROZEN_FORWARD','COLLECTING','EVALUATION_READY','VALIDATED','FAILED_VALIDATION','PAUSED')
TRANSITIONS={'RESEARCH':['CANDIDATE_FOR_FREEZE'],'CANDIDATE_FOR_FREEZE':['FROZEN_FORWARD','RESEARCH'],'FROZEN_FORWARD':['COLLECTING','PAUSED'],'COLLECTING':['EVALUATION_READY','PAUSED'],'EVALUATION_READY':['VALIDATED','FAILED_VALIDATION','COLLECTING','PAUSED'],'VALIDATED':['PAUSED'],'FAILED_VALIDATION':['PAUSED'],'PAUSED':['COLLECTING']}

def now()->str:return datetime.now(timezone.utc).isoformat()
def strict_load(path:Path)->dict:return json.loads(path.read_text(),parse_constant=lambda x:(_ for _ in()).throw(ValueError(x)))
def digest(value:Any)->str:return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def file_hash(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()

def blank(a:dict)->dict:
 return {'strategy_name':a['strategy_name'],'aliases':[],'execution_definition_hash':a['execution_definition_hash'],'alias_group':a.get('alias_group'),'governance_state':'RESEARCH','frozen_at':None,'activated_at':None,'historical_evidence_snapshot_hash':file_hash(AUDIT_PATH),'frozen_strategy_spec_hash':None,'forward_experiment_name':None,'forward_data_start':None,'forward_data_end':None,'raw_forward_n':0,'independent_entry_timestamps':0,'unique_market_data_timestamps':0,'independent_signal_clusters':0,'diagnostic_effective_n':None,'unique_assets':0,'regime_coverage':[],'completed_outcomes':0,'open_outcomes':0,'forward_ev_pct':None,'forward_profit_factor':None,'forward_profit_factor_status':'UNDEFINED_NO_OUTCOMES','forward_clustered_ci_95':[None,None],'forward_max_drawdown_pct':None,'historical_oos_ev_pct':a.get('statistics',{}).get('ev_pct'),'historical_clustered_ci_95':[a.get('cluster_aware_ci',{}).get('lower_pct'),a.get('cluster_aware_ci',{}).get('upper_pct')],'ev_decay_pct':None,'ev_decay_status':'INSUFFICIENT_EVIDENCE','evidence_result':'NOT_EVALUATED','validation_notes':[],'major_warnings':list(a.get('major_warnings',[])),'trading_capability':'DISABLED'}

def initial_entries(audit:dict)->list[dict]:
 by_hash={};rank={'MOMENTUM_STRUCTURE_EXIT':0,'MOMENTUM_TP5_SL2':1}
 for a in sorted(audit['strategies'],key=lambda x:(x['execution_definition_hash'],rank.get(x['strategy_name'],0),x['strategy_name'])):
  h=a['execution_definition_hash']
  if h in by_hash:by_hash[h]['aliases'].append(a['strategy_name']);continue
  e=blank(a);by_hash[h]=e
  if a['strategy_name']=='EE_DYNAMIC_BREAKOUT':e['governance_state']='CANDIDATE_FOR_FREEZE';e['validation_notes'].append('Historical audit supports freeze review only; activation requires explicit user action.')
 return list(by_hash.values())

def v2_update(entry:dict,current:datetime)->None:
 status=read_status(V2_DB,current);cfg=load_config()
 with sqlite3.connect(f'file:{V2_DB.resolve()}?mode=ro&immutable=1',uri=True) as db:
  db.row_factory=sqlite3.Row;m=active_manifest(db);signals=[dict(x) for x in db.execute('SELECT s.signal_id,s.signal_timestamp,s.asset,d.market_data_cutoff,d.source_candle_completion_timestamp FROM v2_signals s JOIN v2_decision_snapshots d USING(snapshot_id)')];accepted=[dict(x) for x in db.execute('SELECT signal_id,observed_at AS entry_timestamp FROM v2_entry_observations')];outcomes=[dict(x) for x in db.execute('SELECT * FROM v2_completed_outcomes')];opens=[dict(x) for x in db.execute('SELECT * FROM v2_open_observations')];events=[dict(x) for x in db.execute('SELECT event_timestamp,event_type FROM v2_monitor_events ORDER BY event_timestamp DESC')]
 rows=[{'setup_episode_id':x['signal_id'],'asset':next((s['asset'] for s in signals if s['signal_id']==x['signal_id']),'UNKNOWN'),'entry_timestamp':normalized_timestamp(x['entry_timestamp']),'market_data_timestamp':normalized_timestamp(x['entry_timestamp']),'cluster_timestamp':normalized_timestamp(x['entry_timestamp']),'net_return_pct':x['net_return_pct']} for x in outcomes]
 stat=metrics(rows);ci=bootstrap_ci(rows,True) if rows else {'lower_pct':None,'upper_pct':None};conc=concentration(rows,stat['ev_pct']) if rows else {};entries={normalized_timestamp(x['entry_timestamp']) for x in accepted};market_times={normalized_timestamp(s['source_candle_completion_timestamp']) for s in signals};signal_clusters={normalized_timestamp(s['market_data_cutoff']) for s in signals};assets={s['asset'] for s in signals};expired=sum(datetime.fromisoformat(x['expiry_timestamp'].replace('Z','+00:00')).astimezone(timezone.utc)<current for x in opens)
 entry.update(governance_state='COLLECTING' if status['collection_state']=='COLLECTING' else 'FROZEN_FORWARD',frozen_at=m['created_at_utc'],activated_at=m['official_cohort_start_timestamp'],frozen_strategy_spec_hash=m['config_sha256'],forward_experiment_name=STRATEGY_ID,forward_data_start=m['official_cohort_start_timestamp'],forward_data_end=max((x['exit_timestamp'] for x in outcomes),default=None),raw_forward_n=len(signals),independent_entry_timestamps=len(entries),unique_market_data_timestamps=len(market_times),independent_signal_clusters=len(signal_clusters),unique_assets=len(assets),completed_outcomes=len(outcomes),open_outcomes=len(opens),forward_ev_pct=stat['ev_pct'],forward_profit_factor=stat['profit_factor'],forward_profit_factor_status=stat['profit_factor_status'],forward_clustered_ci_95=[ci['lower_pct'],ci['upper_pct']],forward_max_drawdown_pct=maximum_drawdown([x['net_return_pct'] for x in sorted(outcomes,key=lambda x:x['exit_timestamp'])]) if outcomes else None,single_asset_ev_delta_pct=conc.get('leave_one_asset_out',{}).get('max_absolute_ev_delta_pct'),single_timestamp_ev_delta_pct=conc.get('leave_one_timestamp_out',{}).get('max_absolute_ev_delta_pct'),monitor_status='ACTIVE' if status['collection_state']=='COLLECTING' else status['collection_state'],last_monitor_timestamp=events[0]['event_timestamp'] if events else None,next_monitor_requirement='Resolve expired open observations from public market evidence; never fabricate an exit.' if expired else 'Run official monitor after new completed market data.',experiment_age_days=max(0,(current-datetime.fromisoformat(m['official_cohort_start_timestamp'].replace('Z','+00:00'))).total_seconds()/86400))
 if expired:entry['major_warnings']=sorted(set(entry['major_warnings']+['OPEN_OBSERVATIONS_PAST_EXPIRY_REQUIRE_MONITOR']))
 entry['validation_notes']=list(dict.fromkeys(entry['validation_notes']+['Existing immutable RANGE_FIXED_5_FORWARD_V2 integrated without semantic changes.']))
 assert sha256_json(cfg)==m['config_sha256']

def gates(entry:dict,policy:dict)->dict:
 checks={'completed_forward_outcomes':entry['completed_outcomes']>=policy['minimum_completed_forward_outcomes'],'independent_signal_clusters':entry['independent_signal_clusters']>=policy['minimum_independent_signal_clusters'],'unique_market_timestamps':entry['unique_market_data_timestamps']>=policy['minimum_unique_market_timestamps'],'unique_assets':entry['unique_assets']>=policy['minimum_unique_assets'],'single_timestamp_concentration':entry.get('single_timestamp_ev_delta_pct') is not None and entry['single_timestamp_ev_delta_pct']<=policy['maximum_single_timestamp_ev_delta_pct'],'single_asset_concentration':entry.get('single_asset_ev_delta_pct') is not None and entry['single_asset_ev_delta_pct']<=policy['maximum_single_asset_ev_delta_pct'],'regime_diversity':len(entry['regime_coverage'])>=policy['minimum_regime_diversity']}
 return {'passed':all(checks.values()),'checks':checks,'policy_version':policy['version']}

def apply_evaluation_state(entry:dict,policy:dict)->None:
 entry['evaluation_gates']=gates(entry,policy)
 if entry['governance_state']=='COLLECTING' and entry['evaluation_gates']['passed']:
  lower,upper=entry.get('forward_clustered_ci_95',[None,None])
  entry['governance_state']='EVALUATION_READY'
  entry['evidence_result']='PASS_FORWARD_EVIDENCE' if lower is not None and lower>0 else 'FAIL_FORWARD_EVIDENCE' if upper is not None and upper<0 else 'INCONCLUSIVE'
  entry['validation_notes'].append('Evaluation gates met; no automatic VALIDATED transition is permitted.')

def refresh(registry_path:Path=REGISTRY,audit_path:Path=AUDIT_PATH,current:datetime|None=None)->dict:
 current=(current or datetime.now(timezone.utc)).astimezone(timezone.utc);audit=strict_load(audit_path);existing={x['execution_definition_hash']:x for x in strict_load(registry_path).get('entries',[])} if registry_path.exists() else {}
 entries=initial_entries(audit)
 for e in entries:
  old=existing.get(e['execution_definition_hash'])
  if old:
   immutable={k:old.get(k) for k in ('governance_state','frozen_at','activated_at','frozen_strategy_spec_hash','forward_experiment_name','validation_notes')};e.update({k:v for k,v in immutable.items() if v is not None})
  if e['strategy_name']=='RANGE_FIXED_5':v2_update(e,current)
 policy=strict_load(GATES_PATH)
 for e in entries:
  apply_evaluation_state(e,policy)
  if e['completed_outcomes']>=policy['minimum_completed_forward_outcomes'] and e.get('forward_ev_pct') is not None and e.get('historical_oos_ev_pct') is not None:e['ev_decay_pct']=e['forward_ev_pct']-e['historical_oos_ev_pct'];e['ev_decay_status']='AVAILABLE'
  missing=[]
  if not e['evaluation_gates']['checks']['completed_forward_outcomes']:missing.append(f"completed outcomes {e['completed_outcomes']}/{policy['minimum_completed_forward_outcomes']}")
  if not e['evaluation_gates']['checks']['independent_signal_clusters']:missing.append(f"independent clusters {e['independent_signal_clusters']}/{policy['minimum_independent_signal_clusters']}")
  e['next_required_evidence']='; '.join(missing) or 'Manual evaluation under predefined policy required.'
 document={'schema_version':'1.0.0','updated_at_utc':current.isoformat(),'purpose':'PROSPECTIVE_RESEARCH_GOVERNANCE_ONLY','states':list(STATES),'transition_rules':TRANSITIONS,'evaluation_policy':policy,'entries':entries,'trading_capability':'DISABLED'};atomic_json(registry_path,document)
 board={'schema_version':'1.0.0','generated_at_utc':current.isoformat(),'registry_path':str(registry_path),'entries':entries,'trading_capability':'DISABLED'};atomic_json(BOARD_JSON,board);BOARD_MD.write_text(render(board));return board

def freeze(name:str,spec_path:Path,registry_path:Path=REGISTRY)->dict:
 registry=strict_load(registry_path);entry=next((x for x in registry['entries'] if name==x['strategy_name'] or name in x['aliases']),None)
 if not entry:raise ValueError('strategy not found')
 if entry['governance_state'] not in ('CANDIDATE_FOR_FREEZE','FROZEN_FORWARD'):raise ValueError('strategy is not CANDIDATE_FOR_FREEZE')
 spec=strict_load(spec_path);required=('signal_family','entry_rule','entry_price_semantics','target','stop','max_hold_or_expiry','exit_logic','fees','slippage','spread_semantics','universe_rules','timeframe','regime_filters','execution_assumptions','paper_only','real_orders')
 missing=[x for x in required if x not in spec]
 if missing:raise ValueError('freeze specification missing: '+','.join(missing))
 if spec['paper_only'] is not True or spec['real_orders'] is not False:raise ValueError('freeze must remain paper-only with real orders disabled')
 spec_hash=digest({'execution_definition_hash':entry['execution_definition_hash'],'immutable_strategy_spec':spec});path=MANIFEST_DIR/f'{entry["execution_definition_hash"]}_{spec_hash}.json'
 if entry.get('activated_at') and entry.get('frozen_strategy_spec_hash')!=spec_hash:raise ValueError('activated experiment is immutable; create a new version/experiment')
 if path.exists():manifest=strict_load(path)
 else:
  manifest={'manifest_version':'1.0.0','strategy_name':entry['strategy_name'],'execution_definition_hash':entry['execution_definition_hash'],'historical_evidence_snapshot_hash':file_hash(AUDIT_PATH),'frozen_at_utc':now(),'immutable_strategy_spec':spec,'frozen_strategy_spec_hash':spec_hash,'trading_capability':'DISABLED'};MANIFEST_DIR.mkdir(parents=True,exist_ok=True);atomic_json(path,manifest)
 entry.update(governance_state='FROZEN_FORWARD',frozen_at=manifest['frozen_at_utc'],historical_evidence_snapshot_hash=manifest['historical_evidence_snapshot_hash'],frozen_strategy_spec_hash=spec_hash,forward_experiment_name=f"{entry['strategy_name']}_FORWARD_V1");atomic_json(registry_path,registry);return manifest

def activate(name:str,registry_path:Path=REGISTRY)->dict:
 registry=strict_load(registry_path);entry=next((x for x in registry['entries'] if name==x['strategy_name'] or name in x['aliases']),None)
 if not entry or entry['governance_state']!='FROZEN_FORWARD' or not entry.get('frozen_strategy_spec_hash'):raise ValueError('strategy must have an immutable FROZEN_FORWARD manifest')
 if entry.get('activated_at'):raise ValueError('experiment already activated and immutable')
 entry['activated_at']=now();entry['forward_data_start']=entry['activated_at'];entry['validation_notes'].append('Explicit manual activation recorded; collection begins only when prospective observations arrive.');atomic_json(registry_path,registry);return entry

def render(board:dict)->str:
 lines=['# Forward Validation Board V1','','Research governance only. Trading capability: DISABLED.','','## Strategies','']
 for x in board['entries']:lines.append(f"- {x['strategy_name']} | {x['governance_state']} | {x['execution_definition_hash'][:12]} | historical CI {x['historical_clustered_ci_95']} | forward {x['completed_outcomes']} outcomes / {x['independent_signal_clusters']} clusters | EV {x['forward_ev_pct']} | forward CI {x['forward_clustered_ci_95']} | regimes {x['regime_coverage'] or 'none'} | warning {(x['major_warnings'] or ['none'])[0]} | next {x['next_required_evidence']}")
 return '\n'.join(lines)+'\n'

def main()->None:
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command');sub.add_parser('refresh');f=sub.add_parser('freeze');f.add_argument('strategy');f.add_argument('--spec',type=Path,required=True);a=sub.add_parser('activate');a.add_argument('strategy');args=p.parse_args()
 if args.command in (None,'refresh'):refresh();print(BOARD_JSON)
 elif args.command=='freeze':print(json.dumps(freeze(args.strategy,args.spec),indent=2,allow_nan=False))
 else:print(json.dumps(activate(args.strategy),indent=2,allow_nan=False))

if __name__=='__main__':main()
