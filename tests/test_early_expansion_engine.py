from __future__ import annotations
import hashlib,json
from pathlib import Path
import pytest
import scripts.early_expansion_engine as ee
import scripts.ai_daily_observations as obs

def reports(asset='NEAR',**overrides):
    con={'asset':asset,'kraken_pair':asset+'USD','range_state':'VALID_RANGE','range_valid':True,'position_pct':25,'freshness_status':'FRESH','liquidity_pass':True,'spread_pass':True,'latest_completed_candle_timestamp':'2026-08-09T00:00:00Z'}
    rq={'asset':asset,'rqi_score':68,'historical_sample_quality':'MEDIUM'};rp={'asset':asset,'sample_quality':'MEDIUM'}
    rs={'asset':asset,'percentile_rank':62,'percentile_rank_change':8,'relative_acceleration':1.2,'btc_relative_return_4h':1,'freshness':'FRESH','liquidity_pass':True}
    mom={'asset':asset,'kraken_pair':asset+'USD','momentum_stage':'EARLY_MOMENTUM','overextension_risk':'LOW','current_price':10,'atr14_pct':1.4,'volatility_expansion_ratio':.75,'bollinger_band_width_pct':5,'volume_z_score':.4,'volume_ratio':1.1,'acceleration_4h_pct':.8,'number_completed_closes_above_breakout':0,'change_4h_pct':.5,'change_24h_pct':1.5,'change_48h_pct':2.5,'distance_above_breakout_pct':-4,'breakout_level':10.4,'distance_above_ema20_atr':.6}
    for key,value in overrides.items():
        target,field=key.split('__',1);{'con':con,'rq':rq,'rp':rp,'rs':rs,'mom':mom}[target][field]=value
    return {'consolidation':{'candidates':[con]},'rqi':{'assets':[rq]},'personality':{'assets':[rp]},'relative':{'candidates':[rs]},'momentum':{'candidates':[mom]},'capital':{'summary':{'primary_state':'BROAD_RISK_ON'}},'rotation':{},'chief':{'candidates':[]}}

def previous(asset='NEAR'):
    return reports(asset,rs__percentile_rank=48,rs__percentile_rank_change=0,rs__relative_acceleration=-.4,mom__volume_z_score=-.8,mom__acceleration_4h_pct=-.2,mom__momentum_stage='NO_MOMENTUM',rq__rqi_score=58,mom__volatility_expansion_ratio=.95)

def calc(**kw):return ee.calculate_asset('NEAR',reports(**kw),previous())

def test_compressed_valid_range_improving_rs():
    r=calc();assert r['components']['volatility_compression']>60 and r['components']['relative_strength_delta']>60 and r['range_valid']
def test_improving_volume_without_overextension():
    r=calc(mom__volume_z_score=.8);assert r['components']['volume_buildup']>50 and r['overextension_status']=='PASS'
def test_rising_energy_delta():assert calc()['energy_delta_score']>50
def test_strong_absolute_momentum_already_too_late():assert calc(mom__change_24h_pct=9,mom__acceleration_4h_pct=4)['classification']=='TOO_LATE'
def test_confirmed_breakout_exclusion():assert calc(mom__momentum_stage='BREAKOUT_CONFIRMED')['classification']=='TOO_LATE'
def test_upper_range_penalty():assert calc(con__position_pct=75)['components']['range_position']<calc(con__position_pct=25)['components']['range_position']
def test_lower_range_reward():assert calc(con__position_pct=20)['components']['range_position']==100
def test_high_extension_risk_exclusion():assert calc(mom__overextension_risk='HIGH')['classification']=='TOO_LATE'
def test_market_regime_conflict():
    r=reports();r['capital']['summary']['primary_state']='RISK_OFF';assert ee.calculate_asset('NEAR',r,previous())['components']['capital_flow_alignment']==20
def test_positive_capital_flow_alignment():assert calc()['components']['capital_flow_alignment']==85
def test_insufficient_previous_snapshot_is_neutral():
    r=ee.calculate_asset('NEAR',reports(),None);assert r['energy_delta_score']==50 and not r['previous_snapshot_available']
def test_no_lookahead_contract():assert ee.build_report(reports(),previous(),'2026-08-09',with_retrospective=False)['methodology']['no_look_ahead_detection']
def test_deterministic_ranking():
    a=ee.calculate_asset('A',reports('A'),previous('A'));z=ee.calculate_asset('Z',reports('Z'),previous('Z'));assert ee.rank([z,a])==ee.rank([a,z])
def test_pump_retrospective_no_data(monkeypatch):monkeypatch.setattr(ee,'available_dates',lambda:[]);assert ee.retrospective('PUMP')['result']=='NOT_DETECTED'
def test_tao_retrospective_no_lookahead(monkeypatch):
    monkeypatch.setattr(ee,'available_dates',lambda:['2026-08-08']);monkeypatch.setattr(ee,'load_date',lambda d:reports('TAO'));r=ee.retrospective('TAO');assert r['look_ahead_used_for_detection'] is False
def test_no_nan_infinity():
    r=calc(mom__volume_z_score=float('nan'));json.dumps(r,allow_nan=False)
def test_daily_observations_material_rules():
    old={'early_expansion':{'top_pre_move_candidates':[{'asset':'A','combined_pre_move_score':60,'energy_delta_score':50,'classification':'PRE_MOVE_BUILDING'}]}};new={'early_expansion':{'top_pre_move_candidates':[{'asset':'A','combined_pre_move_score':69.9,'energy_delta_score':64.9,'classification':'PRE_MOVE_BUILDING'}]}};assert not obs.compare_early_expansion(new,old);new['early_expansion']['top_pre_move_candidates'][0]['energy_delta_score']=65;assert obs.compare_early_expansion(new,old)
def test_chief_compact_fields():
    row=calc();keys=('asset','combined_pre_move_score','energy_delta_score','classification','confidence_score','range_position_pct','return_24h_pct','distance_to_breakout_pct','main_strength','primary_risk');assert len({k:row[k] for k in keys})==10
def test_invalid_structure():assert calc(con__range_valid=False)['classification']=='INVALID_STRUCTURE'
def test_extreme_volume_too_late():assert calc(mom__volume_z_score=4)['classification']=='TOO_LATE'
def test_score_bounds():
    r=calc();assert all(0<=r[k]<=100 for k in ('early_expansion_score','energy_delta_score','combined_pre_move_score','confidence_score'))
def test_no_source_module_strategy_sqlite_mutation():
    root=Path(__file__).resolve().parents[1];protected=[root/'scripts/consolidation_range_engine.py',root/'scripts/range_quality_index.py',root/'scripts/btc_rotation_engine.py']+list((root/'journal').glob('*.sqlite'))+[p for p in (root/'STRATEGIES').rglob('*') if p.is_file()];before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected};calc();assert before=={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
def test_no_order_or_kraken_calls():
    text=(Path(__file__).resolve().parents[1]/'scripts/early_expansion_engine.py').read_text().lower();assert 'add_order' not in text and 'private endpoint' not in text and 'requests.' not in text
