import copy,csv,json,sqlite3,sys,hashlib
from pathlib import Path
from datetime import timedelta
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from quant_research_v2.capture import capture
from quant_research_v2.registry import Registry
from quant_research_v2.schemas import canonical,utc
from quant_research_v2.outcomes import outcome
from paper_setup_extractor import SOURCES


def prepare(tmp_path,day):
    fixture=json.loads((ROOT/f'tests/fixtures/v2_identity/oct{day}.json').read_text())
    for name,path in SOURCES.items():
        dest=tmp_path/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(fixture['reports'][name]))
    p=tmp_path/'config/paper_strategy_research_v1.json';p.parent.mkdir();p.write_text(json.dumps(fixture['config']))
    for pair,rows in fixture['bars'].items():
        assert len(rows)==1
        p=tmp_path/f'DATASETS/market_intraday_weekly/{pair}_1H.csv';p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    at=(max(utc(r.get('generated_at_utc') or r.get('report_timestamp')) for r in fixture['reports'].values())+timedelta(seconds=1)).isoformat()
    return at


@pytest.mark.parametrize('day,combinations', [('11',16),('12',18)])
def test_collision_sets_replay_order_and_measurement_separation(tmp_path,day,combinations):
    at=prepare(tmp_path,day);r=Registry(':memory:')
    with r.db:capture(r,tmp_path,at,at)
    original=r.signals();combos=[s for s in original if s['strategy_id']=='MULTI_TP4_SL2']
    assert len(combos)==combinations
    assert len({s['signal_id'] for s in combos})==combinations
    assert all(s['parent_setup']['strategy_name']!='MULTI_MODULE_CONFIRMATION' for s in combos)
    with r.db:capture(r,tmp_path,(utc(at)+timedelta(seconds=1)).isoformat(),at)
    assert r.signals()==original
    for path in SOURCES.values():
        p=tmp_path/path.relative_to(ROOT);data=json.loads(p.read_text())
        for k in ('assets','candidates','top_candidates'):
            if k in data:data[k].reverse()
        p.write_text(json.dumps(data))
    other=Registry(':memory:')
    with other.db:capture(other,tmp_path,at,at)
    assert other.signals()==original
    for signal in original:
        before=canonical(signal)
        for horizon in (1,4,12,24,72):
            for now in (at,(utc(at)+timedelta(hours=100)).isoformat()):
                outcome(signal,horizon,[],[],now)
        assert canonical(signal)==before
    r.close();other.close()


@pytest.mark.parametrize('change',['feature','level'])
def test_changed_facts_fail_before_capture_writes_and_rollback(tmp_path,change):
    at=prepare(tmp_path,'12');r=Registry(':memory:')
    with r.db:capture(r,tmp_path,at,at)
    before=r.db.serialize()
    path=SOURCES['momentum' if change=='feature' else 'early_expansion'];p=tmp_path/path.relative_to(ROOT);data=json.loads(p.read_text())
    row=data['candidates' if change=='feature' else 'assets'][0]
    row['volume_z_score' if change=='feature' else 'breakout_level']=999
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='IMMUTABLE_PAYLOAD_CONFLICT'),r.db:
        capture(r,tmp_path,at,at)
    assert r.db.serialize()==before
    r.close()


def test_duplicate_preflight(tmp_path,monkeypatch):
    import quant_research_v2.capture as module
    at=prepare(tmp_path,'12');original=module.extract_setups
    def duplicate(*args,**kwargs):
        rows=original(*args,**kwargs);extra=copy.deepcopy(rows[0]);extra['entry_reference_price']*=1.01
        return rows+[extra]
    monkeypatch.setattr(module,'extract_setups',duplicate)
    r=Registry(':memory:');before=r.db.serialize()
    with pytest.raises(ValueError,match='DUPLICATE_PAYLOAD_CONFLICT'),r.db:capture(r,tmp_path,at,at)
    assert r.db.serialize()==before
    r.close()


def test_existing_history_and_forward_outcomes_untouched(tmp_path):
    at=prepare(tmp_path,'12')
    paths=[ROOT/'DATASETS/QUANT_RESEARCH_V2/research.sqlite',ROOT/'FORWARD_RESEARCH/RANGE_FIXED_5_FORWARD_V2/range_fixed_5_forward_v2.sqlite']
    if not all(p.exists() for p in paths):pytest.skip('local protected stores unavailable')
    hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    ro=sqlite3.connect(paths[0].as_uri()+'?mode=ro',uri=True);r=Registry(':memory:');ro.backup(r.db)
    previous=r.db.execute('select id,payload from signals').fetchall();oldout=r.db.execute('select * from outcomes').fetchall()
    with r.db:capture(r,tmp_path,at,at)
    assert all(r.db.execute('select payload from signals where id=?',(key,)).fetchone()[0]==value for key,value in previous)
    assert r.db.execute('select * from outcomes').fetchall()==oldout
    forward=sqlite3.connect(paths[1].as_uri()+'?mode=ro',uri=True)
    assert forward.execute('select count(*) from v2_completed_outcomes').fetchone()[0]==8
    forward.close();r.close();ro.close()
    assert hashes==[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]

@pytest.mark.parametrize('field', ['reference_price','event_study_levels','features','regime','parent_setup','provenance','quality_flags','decision_status'])
def test_full_immutable_fact_comparison(tmp_path,field):
    from quant_research_v2.capture import replay_event
    at=prepare(tmp_path,'11');r=Registry(':memory:')
    with r.db:capture(r,tmp_path,at,at)
    old=r.signals()[0];changed=copy.deepcopy(old)
    if isinstance(changed[field],dict):changed[field]['unexpected_fact']='changed'
    elif isinstance(changed[field],list):changed[field].append('changed')
    elif isinstance(changed[field],(int,float)):changed[field]+=1
    else:changed[field]='changed'
    with pytest.raises(ValueError,match='IMMUTABLE_PAYLOAD_CONFLICT'):replay_event(changed,old)
    r.close()


def test_mature_measurements_do_not_mutate_observation(tmp_path):
    at=prepare(tmp_path,'12');r=Registry(':memory:')
    with r.db:capture(r,tmp_path,at,at)
    s=r.signals()[0];original=canonical(s);ref=utc(s['reference_candle_close_utc']);price=s['reference_price']
    bars=[{'start':(ref+timedelta(hours=i-1)).isoformat(),'end':(ref+timedelta(hours=i)).isoformat(),
           'open':price,'high':price*1.1,'low':price*.9,'close':price*(1+i/10000),'volume':10.} for i in range(73)]
    for horizon in (1,4,12,24,72):
        due=ref+timedelta(hours=horizon)
        pending=outcome(s,horizon,bars,bars,(due-timedelta(seconds=1)).isoformat())
        complete=outcome(s,horizon,bars,bars,due.isoformat())
        assert pending['status']=='PENDING' and complete['status']=='COMPLETE'
        assert complete['btc_relative_return_pct']==0
        assert complete['mfe_pct']>0 and complete['mae_pct']<0
        assert canonical(s)==original
    r.close()

@pytest.mark.parametrize('day',['11','12'])
def test_parent_annotation_preserves_legacy_signal_definitions(day):
    from paper_setup_extractor import extract_setups
    fixture=json.loads((ROOT/f'tests/fixtures/v2_identity/oct{day}.json').read_text())
    plain=extract_setups(fixture['reports'],'2026-10-12T16:00:00+00:00')
    enriched=extract_setups(fixture['reports'],'2026-10-12T16:00:00+00:00',include_parent_provenance=True)
    assert [{k:v for k,v in s.items() if k!='parent_setup'} for s in enriched]==plain
