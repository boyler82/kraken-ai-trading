from __future__ import annotations
import copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import run_daily_quant_system as q

NOW='2026-09-05T07:00:00Z'
def fixtures(tmp_path):
 chief={'objective':'BTC_ACCUMULATION','market_state':{'crypto_regime':'BEAR'},'capital_flow':{'primary_state':'NO_CLEAR_FLOW'},'unknowns':[], 'candidates':[{'asset':'ATOM','current_data':{'analysis_price':1.5,'analysis_price_timestamp':'2026-09-05T06:00:00Z','current_price':1.5,'live_reference_price':1.6,'live_reference_timestamp':'2026-09-05T06:59:55Z','live_price_status':'LIVE_PRICE_AVAILABLE','price_drift_pct':(1.6/1.5-1)*100},'momentum':{'stage':'BREAKOUT_DEVELOPING','activation_condition':'CLOSE_ABOVE','invalidation_condition':'CLOSE_BELOW'},'decision_metrics':{'current_primary_hypothesis':'BREAKOUT_DEVELOPING','evidence_confidence_score':50,'confidence_band':'MEDIUM'},'validation':{'historical_sample_size':0,'validation_grade':'INSUFFICIENT_SAMPLE'},'rotation':{'net_edge_after_costs':2,'edge_validation_status':'UNVALIDATED'},'consolidation':{'rr_to_high':3,'downside_to_invalidation_pct':2}}], 'tactical_opportunities':{'daily':[{'asset':'ATOM','setup_quality_score':80,'actionability_score':75,'recommendation':'SPECULATIVE_REVIEW','technical_action':'BUY_ON_BREAKOUT'}],'weekly':[],'avoid':[]}}
 memory={'status':'AVAILABLE','oos_summary':[{'strategy':'S','oos_n':10,'oos_ev':1,'oos_pf':1.2,'oos_ev_ci_lower':-1,'oos_ev_ci_upper':2,'oos_status':'OOS_POSITIVE_UNVALIDATED'}],'research_memory_statistical_warnings':['SMALL_SAMPLE']}
 capital={'status':'AVAILABLE'};transition={'market_data_timestamp':'2026-09-05T06:00:00Z','market_state':'HEALTHY_PULLBACK','btc_structure_1h':{'trend':'UP'},'breadth':{},'sell_pressure':{}}
 paths={}
 for name,value in [('chief',chief),('memory',memory),('capital',capital),('transition',transition)]:p=tmp_path/f'{name}.json';p.write_text(json.dumps(value));paths[name]=p
 return paths,chief,memory,capital,transition

def test_handoff_schema_semantics_and_determinism(tmp_path):
 paths,chief,memory,capital,transition=fixtures(tmp_path);v2={'collection_state':'COLLECTING','signals':1,'open_observations':1,'completed_outcomes':0,'clock_safety':'PASS'};run={'success':True,'warnings':[]}
 first=q.build_handoff(chief,memory,capital,transition,v2,run,NOW,paths,[],[]);second=q.build_handoff(copy.deepcopy(chief),memory,capital,transition,v2,run,NOW,paths,[],[])
 assert first==second
 assert {'run_metadata','system_health','market_state','changes_since_previous_independent_observation','research_memory','current_candidates','forward_experiments','conflicts','what_we_do_not_know','next_research_checks'}<=set(first)
 row=first['current_candidates'][0];assert row['analysis_price']==1.5 and row['live_reference_price']==1.6
 assert set(('setup_quality','evidence_quality','actionability','expected_edge'))<=set(row)
 assert row['expected_edge']['status']=='UNVALIDATED_EDGE' and row['risk_reward']['to_high'] is None
 assert 'TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED' in first['conflicts'][0]['conflicts']

def test_stale_required_analysis_fails_closed_and_live_never_falls_back(tmp_path):
 paths,chief,memory,capital,transition=fixtures(tmp_path);chief['candidates'][0]['current_data'].update({'analysis_price_timestamp':'2026-09-04T00:00:00Z','live_reference_price':None,'live_price_status':'LIVE_PRICE_STALE'})
 packet=q.build_handoff(chief,memory,capital,transition,{'clock_safety':'PASS'},{'success':True,'warnings':[]},NOW,paths,[],[])
 assert packet['run_metadata']['pipeline_status']=='FAILED_REQUIRED_DATA'
 row=packet['current_candidates'][0];assert row['live_reference_price'] is None and row['analysis_price']==1.5

def test_missing_required_output_and_partial_failure_are_explicit(tmp_path):
 paths,chief,memory,capital,transition=fixtures(tmp_path);paths['memory']=tmp_path/'missing.json'
 packet=q.build_handoff(chief,{},capital,transition,{'clock_safety':'UNAVAILABLE'},{'success':False,'warnings':['MODULE_X_FAILED']},NOW,paths,[],['V2_STATUS_UNAVAILABLE'])
 assert packet['run_metadata']['pipeline_status']=='FAILED_REQUIRED_DATA';assert 'memory' in packet['system_health']['required_missing'];assert 'MODULE_X_FAILED' in packet['system_health']['module_failures']

def test_required_module_failure_rejects_previous_artifact(tmp_path):
 paths,chief,memory,capital,transition=fixtures(tmp_path)
 packet=q.build_handoff(chief,memory,capital,transition,{'clock_safety':'PASS'},{'success':True,'warnings':['RESEARCH_MEMORY_UNAVAILABLE: failed']},NOW,paths,[],[])
 assert packet['run_metadata']['pipeline_status']=='FAILED_REQUIRED_DATA'

def test_orchestration_dependency_order(monkeypatch,tmp_path):
 paths,*_=fixtures(tmp_path);monkeypatch.setattr(q,'PATHS',paths);monkeypatch.setattr(q,'transition_changes',lambda now:([],[]));monkeypatch.setattr(q,'read_v2_status',lambda db,now:{'collection_state':'COLLECTING'});monkeypatch.setattr(q,'clock_safety_preflight',lambda:{'status':'PASS'});monkeypatch.setattr(q,'write_memory',lambda memory:tmp_path/'memory.json');monkeypatch.setattr(q,'append_opportunity_observations',lambda chief:0)
 packet,_,_=q.orchestrate(as_of=NOW,runner=lambda **kwargs:{'success':True,'warnings':[]},out_dir=tmp_path/'out')
 assert packet['run_metadata']['dependency_order']==['complete_daily_research','market_transition_summary','research_memory_summary','capital_efficiency_summary','range_fixed_5_v2_status','strategy_evidence_audit','forward_validation_board','market_memory_30d','opportunity_discovery_v1','canonical_decision_handoff']

def test_no_private_api_order_or_v2_runner_invocation():
 source=Path(q.__file__).read_text().lower();assert '/private/' not in source;assert 'addorder' not in source and 'cancelorder' not in source
 assert 'range_fixed_5_v2_official_runner.py' in source and 'subprocess' not in source
