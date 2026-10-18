from __future__ import annotations
import copy,json,sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from quant_research_v2.schemas import *
from quant_research_v2.adapters import historical,prospective
from quant_research_v2.registry import Registry
from quant_research_v2.outcomes import outcome
from quant_research_v2.parameters import split,research,edges
from quant_research_v2.governance import create,transition,state
from quant_research_v2.runner import run

T=datetime(2026,1,1,tzinfo=timezone.utc)
def ts(h=0):return (T+timedelta(hours=h)).isoformat()
def signal(**kwargs):
    args=dict(source_event_id='source-1',asset='TEST',pair='TESTUSD',strategy_id='EE_DYNAMIC_BREAKOUT',
       strategy_version='1.0',configuration_version='hash1',observation_time=ts(.5),reference_close=ts(),reference_price=100,
       features={'version':'1','values':{'rs_percentile':80,'volume_z':1},'available_at_utc':ts(.5),'cutoff_utc':ts()},
       regime={'version':'1','values':{'market_state':'TEST'},'available_at_utc':ts(.5),'cutoff_utc':ts()},
       provenance={'source_digests':['abc']},levels={'target':110,'invalidation':90})
    args.update(kwargs);return prospective(**args)
def bars(count=73):
    return [{'start':ts(h-1),'end':ts(h),'open':100.,'high':112.,'low':88.,'close':100.+h,'volume':10.} for h in range(count)]
def validbars(count=73):
    return [{'start':ts(h-1),'end':ts(h),'open':100.,'high':max(112.,101.+h),'low':88.,'close':100.+h,'volume':10.} for h in range(count)]

def test_registry_ids_duplicates_conflicts_and_rollback(tmp_path):
    r=Registry(tmp_path/'db');s=signal()
    with r.db:r.register(s);r.register(copy.deepcopy(s))
    assert len(r.signals())==1
    altered=copy.deepcopy(s);altered['reference_price']=101
    with pytest.raises(ValueError),r.db:r.register(altered)
    assert r.signals()[0]['reference_price']==100;r.close()

def test_ids_version_isolation():
    assert signal()['signal_id']==signal()['signal_id']
    assert signal(configuration_version='other')['signal_id']!=signal()['signal_id']

@pytest.mark.parametrize('field',['market_data_cutoff_utc','feature_cutoff_utc','reference_price_timestamp_utc','observation_timestamp_utc'])
def test_schema_rejects_missing_timestamps(field):
    s=signal();s[field]=None
    with pytest.raises(ValueError):validate(s)

def test_no_future_feature_snapshot_or_reference():
    s=signal();s['features']['available_at_utc']=ts(1)
    with pytest.raises(ValueError,match='FUTURE_SNAPSHOT'):validate(s)
    with pytest.raises(ValueError):signal(observation_time=ts(-1))
    s=signal();s['reference_price_timestamp_utc']=ts(1)
    with pytest.raises(ValueError):validate(s)

def test_no_naive_timestamps_or_nonfinite():
    with pytest.raises(ValueError):utc('2026-01-01T00:00:00')
    with pytest.raises(ValueError):strict_loads('{"x":NaN}')
    with pytest.raises(ValueError):strict_loads('{"x":1,"x":2}')

@pytest.mark.parametrize('h',HORIZONS)
def test_pending_matures_only_after_complete_horizon(h):
    s=signal();b=validbars()
    assert outcome(s,h,b,b,ts(h-.01))['status']=='PENDING'
    result=outcome(s,h,b,b,ts(h))
    assert result['status']=='COMPLETE'
    assert result['return_pct']==pytest.approx(h)
    assert result['btc_relative_return_pct']==pytest.approx(0)
    assert result['metric_name']==f'return_cc_{h}h'

@pytest.mark.parametrize('observation',[1,2])
def test_precreation_horizon_ineligible(observation):
    s=signal(observation_time=ts(observation))
    assert outcome(s,1,validbars(),validbars(),ts(5))['status']=='INELIGIBLE_PRE_CREATION_HORIZON'

def test_mfe_mae_first_touch_and_short():
    o=outcome(signal(),1,validbars(),validbars(),ts(2))
    assert o['mfe_pct']==pytest.approx(12);assert o['mae_pct']==pytest.approx(-12)
    assert o['first_touch']=='AMBIGUOUS_SAME_CANDLE'
    assert o['time_to_target_hours_bounds']==[0,1]
    o=outcome(signal(direction='SHORT',levels={'target':90,'invalidation':110}),1,validbars(),validbars(),ts(2))
    assert o['return_pct']==pytest.approx(-1);assert o['btc_relative_return_pct']==pytest.approx(-2)

@pytest.mark.parametrize('defect',['gap','duplicate','later_close','impossible','negative_volume'])
def test_bad_data_never_rescues_horizon(defect):
    b=validbars(6)
    if defect=='gap':b.pop(2)
    if defect=='duplicate':b.append(b[2])
    if defect=='later_close':b[4]['end']=ts(4.5)
    if defect=='impossible':b[2]['high']=1
    if defect=='negative_volume':b[2]['volume']=-1
    result=outcome(signal(),4,b,validbars(),ts(7))
    assert result['status']=='UNMEASURABLE';assert result['return_pct'] is None

def test_history_missing_cutoff_and_later_reference_preserved():
    raw={'snapshot_id':'x','asset':'X','timestamp':ts(.5),'current_price':100,
         'technical_scenario':{'reference_timestamp':ts(1)}}
    s=historical(raw)
    assert s['source_record']==raw and s['market_data_cutoff_utc'] is None
    assert s['classification']=='QUARANTINED'
    assert {'MISSING_MARKET_CUTOFF','REFERENCE_PRICE_AFTER_OBSERVATION','AMBIGUOUS_CONFIGURATION_VERSION'}<=set(s['reason_codes'])
    assert s['research_uses']['inventory']
    assert outcome(s,1,validbars(),validbars(),ts(4))['status']=='UNMEASURABLE'

def test_completed_outcomes_immutable(tmp_path):
    r=Registry(tmp_path/'db');s=signal();r.register(s)
    o=outcome(s,1,validbars(),validbars(),ts(1));r.put_outcome(o);r.put_outcome(o)
    o['return_pct']=999
    with pytest.raises(ValueError):r.put_outcome(o)
    r.close()

def test_split_purges_overlaps_and_keeps_cluster_together():
    rows=[{'cluster_id':'a','observation_timestamp_utc':ts(0),'endpoint_utc':ts(72)},
          {'cluster_id':'a','observation_timestamp_utc':ts(10),'endpoint_utc':ts(82)},
          {'cluster_id':'b','observation_timestamp_utc':ts(180),'endpoint_utc':ts(252)}]
    result=split(rows,ts(80),ts(300),ts(600))
    assert result['TRAIN']==[];assert len(result['PURGED'])==2;assert len(result['VALIDATION'])==1
    with pytest.raises(ValueError):split(rows,ts(80),ts(300),ts(600),1)

def test_training_bins_no_oos_leakage():
    train=[{'features':{'x':i}} for i in range(60)]
    assert edges(train,'x')==[20,40]
    assert research([],None)['hypotheses_tested']==0

def version():
    return dict(strategy_id='S',version='1',created_at_utc=ts(),parameters={'a':1},parameter_differences={},
                rationale='test',training_window=None,validation_window=None,oos_window=None,evidence_summary={})
def test_frozen_version_and_owner_governance(tmp_path):
    r=Registry(tmp_path/'db');spec=version();key=create(r,spec)
    transition(r,key,'CHALLENGER',ts(1))
    transition(r,key,'FORWARD_VALIDATION',ts(2),requirements={'end_utc':ts(10),'min_outcomes':2,'min_clusters':2})
    spec['parameters']['a']=2
    with pytest.raises(ValueError):create(r,spec)
    with pytest.raises(ValueError):transition(r,key,'CANDIDATE_FOR_PROMOTION',ts(3),evidence={'outcomes':10,'clusters':10})
    transition(r,key,'CANDIDATE_FOR_PROMOTION',ts(11),evidence={'outcomes':2,'clusters':2})
    with pytest.raises(ValueError,match='OWNER'):transition(r,key,'CHAMPION',ts(12))
    assert state(r,key)['status']=='CANDIDATE_FOR_PROMOTION';r.close()

def fixture_root(tmp_path):
    (tmp_path/'config').mkdir();(tmp_path/'config/quant_research_v2.json').write_text((ROOT/'config/quant_research_v2.json').read_text())
    p=tmp_path/'DATASETS/TACTICAL_OUTCOMES/tactical_candidate_snapshots.jsonl';p.parent.mkdir(parents=True)
    p.write_text(json.dumps({'snapshot_id':'h','asset':'X','timestamp':ts(.5),'current_price':100})+'\n')
    return p

def test_runner_idempotent_and_malformed_fail_closed(tmp_path):
    source=fixture_root(tmp_path)
    first=run(tmp_path,ts(4));second=run(tmp_path,ts(4));assert first==second
    manifest=tmp_path/'RESEARCH_REPORTS/QUANT_RESEARCH_V2/latest_manifest.json';before=manifest.read_bytes()
    source.write_text('{broken')
    with pytest.raises(ValueError):run(tmp_path,ts(4))
    assert manifest.read_bytes()==before

@pytest.mark.archive
def test_actual_919_history_unchanged_and_attrition():
    path=ROOT/'DATASETS/TACTICAL_OUTCOMES/tactical_candidate_snapshots.jsonl'
    original=path.read_bytes();rows=[strict_loads(x) for x in original.decode().splitlines()]
    imported=[historical(x) for x in rows]
    assert len(imported)==len(rows)
    assert all(s['source_record']==r for s,r in zip(imported,rows))
    assert path.read_bytes()==original
    assert all(s['classification']=='QUARANTINED' for s in imported)


def test_capture_stale_sources_fails_closed(tmp_path, monkeypatch):
    from quant_research_v2 import capture as c
    p=fixture_root(tmp_path)
    monkeypatch.setattr(c,'SOURCES',{'momentum':ROOT/'DAILY_REPORTS/MOMENTUM_BREAKOUT/latest.json'})
    src=tmp_path/'DAILY_REPORTS/MOMENTUM_BREAKOUT/latest.json';src.parent.mkdir(parents=True)
    src.write_text(json.dumps({'generated_at_utc':ts(),'candidates':[]}))
    r=Registry(tmp_path/'state.sqlite')
    with pytest.raises(ValueError,match='STALE_SOURCE'),r.db:
        c.capture(r,tmp_path,ts(10),ts(0))
    assert not r.signals();r.close()


def test_full_prospective_capture_and_same_scan_rerun(tmp_path,monkeypatch):
    from quant_research_v2 import capture as c
    fixture_root(tmp_path)
    (tmp_path/'scripts').mkdir()
    (tmp_path/'config/paper_strategy_research_v1.json').write_text((ROOT/'config/paper_strategy_research_v1.json').read_text())
    sources={name:ROOT/('source_'+name+'.json') for name in c.SOURCES}
    monkeypatch.setattr(c,'SOURCES',sources)
    m={'asset':'TEST','kraken_pair':'TESTUSD','latest_completed_candle_timestamp':ts(-1),
       'current_price':100.,'momentum_stage':'BREAKOUT_DEVELOPING','overextension_risk':'LOW',
       'freshness_status':'FRESH','ema20':99,'breakout_level':101}
    for name in sources:
        content={'generated_at_utc':ts(.2),'candidates':[m] if name=='momentum' else [],'assets':[]}
        (tmp_path/('source_'+name+'.json')).write_text(json.dumps(content))
    market=tmp_path/'DATASETS/market_intraday_weekly';market.mkdir(parents=True)
    (market/'TESTUSD_1H.csv').write_text('timestamp,open,high,low,close,volume\n'+ts(-1)+',100,100,100,100,1\n')
    r=Registry(tmp_path/'capture.sqlite')
    with r.db:first=c.capture(r,tmp_path,ts(.5),ts(.3))
    with r.db:second=c.capture(r,tmp_path,ts(.5),ts(.3))
    assert first==second;assert len(r.signals())==3
    for s in r.signals():
        assert s['cohort']==FORWARD;assert s['reference_candle_close_utc']==ts()
        assert s['observation_timestamp_utc']==ts(.5)
        assert outcome(s,1,validbars(),validbars(),ts(.9))['status']=='PENDING'
        assert outcome(s,1,validbars(),validbars(),ts(1))['status']=='COMPLETE'
    r.close()


def test_integration_failure_is_visible_and_never_enables_trading(monkeypatch):
    from quant_research_v2 import integration
    def fail(*a,**kw):raise ValueError('STALE_SOURCE')
    monkeypatch.setattr(integration,'run',fail)
    monkeypatch.setattr(integration,'refresh_hourly_btc',lambda *a,**k: {'status':'OK'})
    p={'run_metadata':{'pipeline_status':'OK'},'system_health':{'module_failures':[]},'SYSTEM_HEALTH':{}}
    integration.extend_handoff(p,ROOT)
    assert p['V2_RESEARCH']['status']=='FAILED'
    assert p['run_metadata']['pipeline_status']=='FAILED_REQUIRED_DATA'
    assert p['V2_RESEARCH']['trading_capability']=='DISABLED'


@pytest.mark.archive
def test_aero_regression_preserves_all_level_namespaces():
    rows=[strict_loads(x) for x in (ROOT/'DATASETS/TACTICAL_OUTCOMES/tactical_candidate_snapshots.jsonl').read_text().splitlines()]
    raw=next(x for x in rows if x['snapshot_id']=='odo_ad6b50bbdb12df41d1d5f7ec')
    s=historical(raw)
    assert 'REFERENCE_PRICE_AFTER_OBSERVATION' in s['reason_codes']
    assert s['source_record']['scenario_state']['activation_level']==0.86736
    assert s['source_record']['technical_scenario']['activation_level']==0.9366
    assert not s['event_study_levels']
    assert s['reference_candle_close_utc'] is None


def test_btc_missing_does_not_destroy_valid_asset_dimension():
    o=outcome(signal(),1,validbars(),[],ts(2))
    assert o['status']=='COMPLETE' and o['return_pct']==pytest.approx(1)
    assert o['btc_relative_return_pct'] is None
    assert 'BTC_MATCHED_WINDOW_UNAVAILABLE' in o['reason_codes']


def test_finer_resolution_cc_outcome_not_hourly_locked():
    b=[{'start':ts(-.5),'end':ts(),'open':100,'high':100,'low':100,'close':100,'volume':1},
       {'start':ts(),'end':ts(.5),'open':100,'high':102,'low':99,'close':101,'volume':1},
       {'start':ts(.5),'end':ts(1),'open':101,'high':103,'low':100,'close':102,'volume':1}]
    o=outcome(signal(),1,b,b,ts(1))
    assert o['status']=='COMPLETE';assert o['return_pct']==pytest.approx(2)


def test_first_touch_separate_candles():
    b=validbars(5)
    for r in b:r.update(high=105.,low=95.,close=100.)
    b[1]['high']=111;b[2]['low']=89
    o=outcome(signal(),4,b,b,ts(4));assert o['first_touch']=='TARGET'
    assert o['time_to_target_hours_bounds']==[0,1]


def test_parameter_research_isolates_versions_and_fits_train_only():
    rows=[]
    for version in ('1','2'):
        for i in range(60):
            rows.append(dict(strategy_id='S',strategy_version=version,configuration_version=version,
             cohort=FORWARD,timing_basis=BASIS,horizon_hours=1,cluster_id=f'c{i}',
             observation_timestamp_utc=ts(i*24),endpoint_utc=ts(i*24+1),
             features={'rs_percentile':i,'volume_z':i},return_pct=1,mfe_pct=2,mae_pct=-1,
             btc_relative_return_pct=0,regime_label='R'))
    windows={'train_end':ts(2000),'validation_end':ts(4000),'oos_end':ts(6000)}
    first=research(rows,windows)
    future=dict(rows[0],observation_timestamp_utc=ts(4500),endpoint_utc=ts(4501),cluster_id='oos',features={'rs_percentile':999,'volume_z':999})
    second=research(rows+[future],windows)
    assert len(first['maps'])==2
    assert first['maps'][0]['train_fitted_edges']==second['maps'][0]['train_fitted_edges']
    assert second['maps'][0]['partition_counts']['OOS']==1


def test_registry_writer_contention_is_atomic(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path=tmp_path/'concurrent.sqlite';Registry(path).close()
    def write(_):
        r=Registry(path)
        try:
            with r.db:r.register(signal())
        finally:r.close()
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(write,range(6)))
    r=Registry(path);assert len(r.signals())==1;r.close()


def test_runner_prospective_pending_maturation_and_exact_rerun(tmp_path):
    fixture_root(tmp_path)
    database=tmp_path/'DATASETS/QUANT_RESEARCH_V2/research.sqlite'
    r=Registry(database)
    with r.db:r.register(signal())
    r.close()
    market=tmp_path/'DATASETS/market_intraday_weekly';market.mkdir()
    import csv
    for pair in ('TESTUSD','XBTUSD'):
        with (market/f'{pair}_1H.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=['timestamp','open','high','low','close','volume']);w.writeheader()
            for b in validbars():w.writerow({'timestamp':b['start'],**{k:b[k] for k in ('open','high','low','close','volume')}})
    a=run(tmp_path,ts(.5));assert a['horizon_counts']['cc_1h']['PENDING']==1
    b=run(tmp_path,ts(1));assert b['horizon_counts']['cc_1h']['COMPLETE']==1
    assert b['horizon_counts']['cc_4h']['PENDING']==1
    assert b==run(tmp_path,ts(1))
    with pytest.raises(ValueError,match='REGRESSION'):run(tmp_path,ts(.5))


def test_feature_cutoff_cannot_exceed_market_cutoff_even_before_creation():
    s=signal();s['feature_cutoff_utc']=ts(.25)
    with pytest.raises(ValueError,match='FEATURE_AFTER_MARKET_CUTOFF'):validate(s)
