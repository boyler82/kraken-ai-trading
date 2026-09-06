from __future__ import annotations
import json,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import market_memory_opportunity as m
import tactical_outcome_tracker as tracker

def prediction(path,cutoff,state='A',ema=50):
 path.write_text(json.dumps({'market_data_timestamp':cutoff,'timestamp':cutoff,'market_state':state,'breadth':{'above_ema20_pct':ema,'above_ema50_pct':ema},'btc_structure_1h':{'trend':'UP'},'btc_structure_4h':{'trend':'MIXED'},'sell_pressure':{'4h':{'classification':'DECLINING','ratio':.5}},'data_quality':{'tracked_assets':10},'rs_leaders':[]}))

def candidate(asset='ALT',invalidation=80):
 return {'asset':asset,'identity':{'kraken_pair':f'{asset}USD'},'current_data':{'freshness':'FRESH','live_reference_price':100,'live_reference_timestamp':'2026-01-31T00:00:00Z'},'momentum':{'stage':'BREAKOUT_DEVELOPING','acceleration':2,'volatility_expansion':1.2,'volume_z_score':1,'return_4h_pct':2,'breakout_level':105},'relative_strength':{'percentile_rank':90},'consolidation':{'range_low':invalidation,'midpoint':102,'range_high':110,'rr_to_high':999},'rotation':{'edge_validation_status':'UNVALIDATED'},'validation':{'historical_sample_size':0}}

def test_memory_deduplicates_orders_and_never_synthesizes(tmp_path):
 prediction(tmp_path/'b.json','2026-01-31T00:00:00Z','B',60);prediction(tmp_path/'a.json','2026-01-01T00:00:00Z');prediction(tmp_path/'duplicate.json','2026-01-31T00:00:00Z','C',99)
 out=m.build_market_memory(tmp_path,'2026-01-31T00:00:00Z')
 assert len(out['snapshots'])==2 and out['snapshots'][0]['market_data_cutoff']<out['snapshots'][1]['market_data_cutoff']
 assert out['snapshots'][0]['capital_flow_state']=='UNAVAILABLE'
 assert out['trajectory']['change_7d']['status']=='DERIVED' and out['trajectory']['change_30d']['status']=='DERIVED'

def test_partial_history_marks_7d_30d_insufficient(tmp_path):
 prediction(tmp_path/'a.json','2026-01-30T00:00:00Z')
 out=m.build_market_memory(tmp_path,'2026-01-31T00:00:00Z')
 assert out['coverage']['status']=='INSUFFICIENT_30D_HISTORY'
 assert out['trajectory']['change_7d']['status']==out['trajectory']['change_30d']['status']=='INSUFFICIENT_HISTORY'

def test_ranking_deterministic_transparent_and_rr_excluded():
 a=candidate('A');b=candidate('B');b['momentum']['acceleration']=3;b['consolidation']['rr_to_high']=-999
 chief={'candidates':[a,b]};first=m.rank_opportunities(chief);a['consolidation']['rr_to_high']=-1e9
 assert [x['asset'] for x in first]==[x['asset'] for x in m.rank_opportunities(chief)]==['B','A']
 assert first[0]['raw_opportunity_components'] and 'risk' not in ''.join(first[0]['raw_opportunity_components']).lower()
 assert m.rank_opportunities({'candidates':[]})==[]

def test_scenario_survives_low_evidence_and_flags_wide_invalidation():
 c=candidate();c['consolidation']['range_low']=90;c['momentum']['invalidation_reference_level']=80
 row=m.rank_opportunities({'candidates':[c]})[0];scenario=row['technical_scenario']
 assert scenario['reference_timestamp'] and scenario['activation_level']==105 and scenario['upside_references']
 assert scenario['technical_invalidation_level']==80 and scenario['user_constraint_status']=='INVALIDATION_TOO_WIDE_FOR_USER_CONSTRAINT'
 assert row['statistical_evidence']['status']=='UNVALIDATED'

def test_invalidation_at_or_above_entry_zone_is_inconsistent():
 c=candidate(invalidation=90);c['momentum']['invalidation_reference_level']=95
 result=m.scenario(c)
 assert result['scenario_level_status']=='LEVELS_INCONSISTENT'
 assert 'INVALIDATION_NOT_BELOW_ENTRY_ZONE' in result['reason_codes']
 assert result['technical_invalidation']==95

def test_entry_zone_states_are_explicit():
 c=candidate();c['consolidation'].update(range_low=90,midpoint=110);c['momentum']['invalidation_reference_level']=80
 c['current_data']['live_reference_price']=85;assert m.scenario(c)['entry_zone_state']=='BELOW_ENTRY_ZONE'
 c['current_data']['live_reference_price']=100;assert m.scenario(c)['entry_zone_state']=='IN_ENTRY_ZONE'
 c['current_data']['live_reference_price']=115;assert m.scenario(c)['entry_zone_state']=='ABOVE_ENTRY_ZONE'
 c['momentum']['extension_risk']='HIGH';assert m.scenario(c)['entry_zone_state']=='EXTENDED_FROM_ENTRY_ZONE'

def test_activation_semantics_do_not_treat_crossed_level_as_future():
 c=candidate();c['consolidation']['range_low']=90;c['momentum']['invalidation_reference_level']=80
 c['current_data']['live_reference_price']=106
 assert m.scenario(c)['activation_state']=='ACTIVATION_ALREADY_CROSSED'
 c['momentum'].update(stage='BREAKOUT_CONFIRMED',confirmation_closes=1)
 assert m.scenario(c)['activation_state']=='BREAKOUT_CONFIRMED'
 c['current_data']['live_reference_price']=104
 assert m.scenario(c)['activation_state']=='APPROACHING_ACTIVATION'
 c['current_data']['live_reference_price']=90
 assert m.scenario(c)['activation_state']=='WAITING_FOR_ACTIVATION'

def test_references_below_current_are_not_upside_targets():
 c=candidate();c['consolidation'].update(range_low=80,midpoint=90,range_high=110);c['momentum'].update(invalidation_reference_level=70,breakout_level=95)
 result=m.scenario(c)
 assert next(x for x in result['structural_references'] if x['price']==95)['semantic_type']=='PAST_REFERENCE'
 assert all(x['price']>100 and x['semantic_type']=='UPSIDE_REFERENCE' for x in result['upside_references'])

def test_scenario_is_deterministic_and_strict_json():
 c=candidate();c['consolidation']['range_low']=90;c['momentum']['invalidation_reference_level']=80
 first=m.scenario(c);assert first==m.scenario(c)
 json.dumps(first,allow_nan=False)

def test_observation_identity_append_only_and_idempotent(tmp_path):
 path=tmp_path/'history.jsonl';chief={'generated_at_utc':'2026-01-31T00:00:00Z','candidates':[candidate()]}
 assert m.append_opportunity_observations(chief,path)==1 and m.append_opportunity_observations(chief,path)==0
 row=json.loads(path.read_text());assert row['observation_id']==row['snapshot_id'] and row['market_data_cutoff'] is None

def test_post_observation_mfe_mae_and_incomplete_evidence(tmp_path):
 snap={'snapshot_id':'s','timestamp':'2026-01-01T00:30:00Z','asset':'ALT','kraken_pair':'ALTUSD','current_price':100,'methodology_version':m.VERSION}
 pd.DataFrame([('2026-01-01T00:00:00Z',100,999,1,100),('2026-01-01T01:00:00Z',100,110,90,105)],columns=['timestamp','open','high','low','close']).to_csv(tmp_path/'ALTUSD_1H.csv',index=False)
 events=tracker.update_events([snap],[],pd.Timestamp('2026-01-01T02:00:00Z'),tmp_path)
 assert events==[] # no due horizon; pre-observation candle cannot fabricate an outcome

def test_btc_cash_context_and_correlated_clusters(tmp_path,monkeypatch):
 history=tmp_path/'h.jsonl';history.write_text('\n'.join(json.dumps({'timestamp':'t','asset':a}) for a in ('A','B'))+'\n');monkeypatch.setattr(m,'TACTICAL_SNAPSHOTS',history)
 out=m.opportunity_context({'candidates':[],'btc_rotation':{}},{'coverage':{}},{})
 assert out['watchlist_status']=='NO_COMPELLING_OPPORTUNITY' and out['btc_cash_benchmark']['no_position_cash']
 assert out['history_summary']['independent_market_clusters']==1 and out['trading_capability']=='DISABLED'
