import copy,hashlib,json,sqlite3,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from quant_research_v2.registry import Registry
from quant_research_v2.schemas import canonical,digest
from quant_research_v2.outcomes import outcome,load_bars
from quant_research_v2.lifecycle import asset_facts,benchmark,preflight,MODEL
from quant_research_v2.evidence import measurement_counts,joined

@pytest.fixture
def fixture():
    return json.loads((ROOT/'tests/fixtures/v2_lifecycle/virtual_1h.json').read_text())

def seed(f):
    r=Registry(':memory:');r.register(f['signal']);r.put_outcome(f['legacy_outcome'])
    r.immutable('metadata','manifest:fixture',{'as_of_utc':f['original_as_of'],'outcomes_digest':digest(r.outcomes())})
    r.bind_legacy_availability(f['original_as_of']);r.db.commit();return r

def calculate(f, btc, at):
    a=outcome(f['signal'],1,f['asset_bars'],[],at)
    return a,benchmark(f['signal'],a,btc,at)

def test_virtual_legacy_replay_and_late_enrichment(fixture):
    f=fixture;r=seed(f);raw=r.db.execute('select payload from outcomes').fetchone()[0]
    replay=outcome(f['signal'],1,f['asset_bars'],f['original_benchmark_bars'],f['original_as_of'])
    assert canonical(replay)==raw
    a,b=calculate(f,f['original_benchmark_bars'],f['original_as_of'])
    with r.db:r.put_asset(a,f['original_as_of']);r.put_benchmark(b)
    view=r.measurements(f['original_as_of'])[0]
    assert (view['asset_state'],view['benchmark_state'],view['status'])==('ASSET_COMPLETE','BENCHMARK_PENDING_REFERENCE_DATA','PARTIALLY_MEASURABLE')
    assert view['btc_relative_return_pct'] is None
    before=measurement_counts(r.signals(),r.measurements(f['original_as_of']))
    a,b=calculate(f,f['benchmark_bars'],f['enriched_as_of'])
    with r.db:r.put_asset(a,f['enriched_as_of']);r.put_benchmark(b)
    enriched=r.measurements(f['enriched_as_of'])[0]
    assert enriched['status']=='COMPLETE'
    assert enriched['btc_return_pct']==pytest.approx(-0.2898073718767047)
    assert enriched['btc_relative_return_pct']==pytest.approx(-1.3780175065110645)
    assert enriched['benchmark_available_as_of']==f['enriched_as_of']
    assert enriched['asset_available_as_of']==f['original_as_of']
    assert r.measurements(f['original_as_of'])[0]==view
    assert r.db.execute('select payload from outcomes').fetchone()[0]==raw
    after=measurement_counts(r.signals(),r.measurements(f['enriched_as_of']))
    assert before['asset_measurable_sample_count']==after['asset_measurable_sample_count']==1
    assert before['independent_cluster_count']==after['independent_cluster_count']==1
    assert before['btc_relative_sample_count']==0 and after['btc_relative_sample_count']==1
    snapshot=r.db.serialize()
    with r.db:r.put_asset(a,f['enriched_as_of']);r.put_benchmark(b)
    assert snapshot==r.db.serialize()
    # Reversed file order yields exactly the same benchmark facts and source bars.
    assert benchmark(f['signal'],a,list(reversed(f['benchmark_bars'])),f['enriched_as_of'])==b
    assert len(joined(r.signals(),r.measurements(f['enriched_as_of'])*2))==1
    r.close()

@pytest.mark.parametrize('field',['return_pct','mfe_pct','mae_pct','target_hit','invalidation_hit','data_digest','endpoint_utc'])
def test_asset_fact_conflicts_rollback(fixture,field):
    r=seed(fixture);before=r.db.serialize();a=asset_facts(fixture['legacy_outcome']);a[field]='changed'
    with pytest.raises(ValueError,match='IMMUTABLE_ASSET_OUTCOME_CONFLICT'),r.db:r.put_asset(a,fixture['enriched_as_of'])
    assert r.db.serialize()==before;r.close()

def test_completed_benchmark_conflict_and_future_view(fixture):
    f=fixture;r=seed(f);a,b=calculate(f,f['benchmark_bars'],f['enriched_as_of'])
    with r.db:r.put_benchmark(b)
    assert r.measurements(f['original_as_of'])[0]['btc_relative_return_pct'] is None
    changed=copy.deepcopy(b);changed['benchmark_return_pct']+=1;before=r.db.serialize()
    with pytest.raises(ValueError,match='IMMUTABLE_BENCHMARK_CONFLICT'),r.db:r.put_benchmark(changed)
    assert r.db.serialize()==before
    with pytest.raises(sqlite3.IntegrityError,match='IMMUTABLE_BENCHMARK'),r.db:r.db.execute('delete from benchmark_measurements')
    r.close()

def test_benchmark_preflight_requires_hourly_windows(fixture):
    f=fixture
    assert preflight([f['signal']],f['benchmark_bars'],f['original_as_of'])['required_windows']==1
    with pytest.raises(ValueError,match='BTC_HOURLY_PREFLIGHT_FAILED'):preflight([f['signal']],f['original_benchmark_bars'],f['original_as_of'])
    with pytest.raises(ValueError,match='BTC_HOURLY_PREFLIGHT_FAILED'):preflight([f['signal']],f['benchmark_bars'][1:],f['original_as_of'])
    with pytest.raises(ValueError,match='BTC_HOURLY_PREFLIGHT_FAILED'):preflight([f['signal']],f['benchmark_bars']*2,f['original_as_of'])

def test_refresh_is_explicit_and_failure_blocks_runner(monkeypatch,tmp_path):
    import quant_research_v2.integration as integration
    called=[]
    def fail(*a,**k):called.append('refresh');raise ValueError('BTC_HOURLY_PREFLIGHT_FAILED:test')
    monkeypatch.setattr(integration,'refresh_hourly_btc',fail)
    monkeypatch.setattr(integration,'run',lambda *a,**k:called.append('run'))
    p={'run_metadata':{'pipeline_status':'OK'},'system_health':{'module_failures':[]},'SYSTEM_HEALTH':{}}
    integration.extend_handoff(p,tmp_path)
    assert called==['refresh'] and p['run_metadata']['pipeline_status']=='FAILED_REQUIRED_DATA'
    assert p['V2_RESEARCH']['trading_capability']=='DISABLED'

@pytest.mark.archive
def test_all_314_legacy_records_are_preserved_and_not_duplicated():
    path=ROOT/'DATASETS/QUANT_RESEARCH_V2/research.sqlite'
    if not path.exists():pytest.fail('Required archive unavailable: V2 production snapshot')
    before=hashlib.sha256(path.read_bytes()).hexdigest();ro=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
    r=Registry(':memory:')
    # Copy data into an initialized schema; sqlite backup would remove new tables.
    for table in ('signals','outcomes','metadata'):
        for row in ro.execute('select * from '+table):r.db.execute('insert into '+table+' values('+','.join('?' for _ in row)+')',row)
    legacy=[(s,b,h,p) for s,b,h,p in r.db.execute('select * from outcomes') if json.loads(p)['status']=='COMPLETE' and 'lifecycle_model_version' not in json.loads(p)]
    assert len(legacy)==314
    r.bind_legacy_availability('2026-10-13T16:00:00+00:00');signals={s['signal_id']:s for s in r.signals()};btc=load_bars(ROOT/'DATASETS/market_intraday_weekly/XBTUSD_1H.csv');cache={}
    for key,basis,h,raw in legacy:
        s=signals[key];cache.setdefault(s['pair'],load_bars(ROOT/f"DATASETS/market_intraday_weekly/{s['pair']}_1H.csv"))
        a=outcome(s,h,cache[s['pair']],[],'2026-10-13T16:00:00+00:00');r.put_asset(a,'2026-10-13T16:00:00+00:00')
        r.put_benchmark(benchmark(s,a,btc,'2026-10-13T16:00:00+00:00'))
        assert r.db.execute('select payload from outcomes where signal_id=? and basis=? and horizon=?',(key,basis,h)).fetchone()[0]==raw
    assert r.db.execute('select count(*) from benchmark_measurements').fetchone()[0]==314
    ids={x[0] for x in legacy};view=[o for o in r.measurements('2026-10-13T16:00:00+00:00') if o['signal_id'] in ids and o['horizon_hours']==1]
    counts=measurement_counts(r.signals(),view)
    assert counts['asset_measurable_sample_count']==counts['btc_relative_sample_count']==314
    assert counts['independent_cluster_count']==1
    r.close();ro.close();assert hashlib.sha256(path.read_bytes()).hexdigest()==before


def test_benchmark_completes_independently_of_missing_asset_window(fixture):
    f=fixture;r=Registry(':memory:');r.register(f['signal'])
    missing=outcome(f['signal'],1,f['asset_bars'][:1],[],f['original_as_of'])
    with r.db:
        a=r.put_asset(missing,f['original_as_of'])
        b=r.put_benchmark(benchmark(f['signal'],a,f['benchmark_bars'],f['original_as_of']))
    view=r.measurements(f['original_as_of'])[0]
    assert view['asset_state']=='ASSET_UNMEASURABLE'
    assert view['benchmark_state']=='BENCHMARK_COMPLETE'
    assert view['btc_relative_return_pct'] is None
    counts=measurement_counts(r.signals(),[view])
    assert counts['asset_measurable_sample_count']==0
    assert counts['benchmark_measurable_sample_count']==1
    raw=r.db.execute('select payload from benchmark_measurements').fetchone()[0]
    complete=outcome(f['signal'],1,f['asset_bars'],[],f['enriched_as_of'])
    with r.db:
        a=r.put_asset(complete,f['enriched_as_of'])
        enriched=r.put_benchmark(benchmark(f['signal'],a,f['benchmark_bars'],f['enriched_as_of']))
    assert r.db.execute('select payload from benchmark_measurements where id=?',(b['evidence_id'],)).fetchone()[0]==raw
    assert enriched['evidence_id']!=b['evidence_id']
    view=r.measurements(f['enriched_as_of'])[0]
    assert view['status']=='COMPLETE' and view['btc_relative_return_pct'] is not None
    counts=measurement_counts(r.signals(),[view])
    assert counts['asset_measurable_sample_count']==counts['benchmark_measurable_sample_count']==counts['independent_cluster_count']==1
    before=r.db.serialize()
    with r.db:r.put_asset(complete,f['enriched_as_of']);r.put_benchmark(enriched)
    assert r.db.serialize()==before
    changed=copy.deepcopy(enriched);changed['benchmark_data_digest']='changed'
    with pytest.raises(ValueError,match='IMMUTABLE_BENCHMARK_CONFLICT'),r.db:r.put_benchmark(changed)
    assert r.db.serialize()==before
    r.close()
