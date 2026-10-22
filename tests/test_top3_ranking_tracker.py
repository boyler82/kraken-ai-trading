import json
import sqlite3
import sys
from contextlib import closing
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import top3_ranking_tracker as t

START = pd.Timestamp('2026-10-01T07:00:00Z')


def archive(tmp_path, asset='ALT', reference=100, finish=110):
    folder = tmp_path / 'DATASETS/market_intraday_weekly'
    folder.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range(START-t.HOUR, periods=26, freq='h')
    d = pd.DataFrame(dict(timestamp=dates, open=reference, high=max(reference, finish)+2,
                          low=reference-10, close=reference, volume=100))
    d.loc[0, 'high'] = reference*100  # Reference candle must not enter MFE.
    d.loc[24, 'close'] = finish
    d.loc[25, ['high','close']] = reference*10  # Not yet closed at +24h.
    path = folder / f'{asset}USD_1H.csv'
    d.to_csv(path, index=False)
    return path


def setup(tmp_path):
    archive(tmp_path)
    archive(tmp_path, 'XBT', 200, 210)
    return t.HourlyArchive(tmp_path)


def rankings(rows=None):
    return {'CONTINUATION': rows if rows is not None else [dict(asset='ALT', pair='ALTUSD', rank=1)],
            'REVERSAL': [], 'RELATIVE_STRENGTH': None}


def obs(db):
    return [json.loads(r[0]) for r in db.execute('SELECT payload FROM observations ORDER BY id')]


def events(db):
    return [dict(r) for r in db.execute('SELECT * FROM outcomes ORDER BY observation_id,kind')]


def test_top3_and_top10_are_preserved_no_reranking(tmp_path):
    a = setup(tmp_path)
    rows = [dict(asset=f'A{i}', pair='ALTUSD', rank=i) for i in range(1,12)]
    with closing(t.connect(tmp_path/'db')) as db:
        t.capture(db, 'scan1', START, 'BEAR', rankings(rows), a)
        assert sorted(o['rank'] for o in obs(db)) == [1,2,3]
        assert all(o['regime']=='BEAR' and o['reference_price']==100 for o in obs(db))
        scan = json.loads(db.execute("SELECT payload FROM scans WHERE ranking_type='CONTINUATION'").fetchone()[0])
        assert [r['asset'] for r in scan['top10']] == [f'A{i}' for i in range(1,11)]
        assert db.execute('SELECT count(*) FROM scans').fetchone()[0] == 3


def test_price_maturity_exact_window_btc_and_excursions(tmp_path):
    a = setup(tmp_path)
    with closing(t.connect(tmp_path/'db')) as db:
        t.capture(db, 's1', START+timedelta(minutes=5), 'BULL', rankings(), a)
        frozen = obs(db)
        t.mature(db, START+timedelta(hours=23,minutes=59), a)
        assert events(db) == []
        t.mature(db, START+timedelta(hours=24), a)
        result = json.loads(events(db)[0]['payload'])
        assert result['return_24h_pct'] == pytest.approx(10)
        assert result['btc_return_24h_pct'] == pytest.approx(5)
        assert result['btc_relative_return_24h_pct'] == pytest.approx((1.1/1.05-1)*100)
        assert result['mfe_pct'] == pytest.approx(12)
        assert result['mae_pct'] == pytest.approx(-10)
        assert obs(db) == frozen


def test_gaps_remain_pending_and_retry_does_not_rewrite(tmp_path):
    setup(tmp_path)
    path = tmp_path/'DATASETS/market_intraday_weekly/ALTUSD_1H.csv'
    full = path.read_bytes()
    pd.read_csv(path).drop(index=10).to_csv(path,index=False)
    with closing(t.connect(tmp_path/'db')) as db:
        t.capture(db, 's', START, 'RANGE', rankings(), t.HourlyArchive(tmp_path))
        assert t.mature(db, START+timedelta(hours=24), t.HourlyArchive(tmp_path))
        assert events(db)==[]
        path.write_bytes(full)
        t.mature(db, START+timedelta(hours=24), t.HourlyArchive(tmp_path))
        frozen = events(db)
        d=pd.read_csv(path);d.loc[24,'close']=105;d.to_csv(path,index=False)
        t.mature(db, START+timedelta(hours=48), t.HourlyArchive(tmp_path))
        assert events(db)==frozen


def test_missing_reference_recorded_and_never_backfilled(tmp_path):
    with closing(t.connect(tmp_path/'db')) as db:
        warnings=t.capture(db, 's', START, 'UNKNOWN', rankings(), t.HourlyArchive(tmp_path))
        assert warnings and obs(db)[0]['reference_price'] is None
        a=setup(tmp_path)
        t.mature(db, START+timedelta(hours=24), a)
        assert events(db)==[] and obs(db)[0]['reference_price'] is None


def test_next_day_first_available_scan_and_censored_rank(tmp_path):
    a=setup(tmp_path)
    with closing(t.connect(tmp_path/'db')) as db:
        t.capture(db,'s1',START,'BEAR',rankings(),a)
        # Unavailable must not be treated as an empty list or a loss of rank.
        t.capture(db,'s2',START+timedelta(days=1), 'BEAR', {}, a)
        t.mature(db, START+timedelta(days=1), a)
        assert not any(e['kind']=='NEXT_DAY_RANK' for e in events(db))
        t.capture(db,'s3',START+timedelta(days=1,hours=1),'BEAR',rankings([]),a)
        t.mature(db,START+timedelta(days=1,hours=1),a)
        e=json.loads(next(e['payload'] for e in events(db) if e['kind']=='NEXT_DAY_RANK'))
        assert not e['remained_top3'] and not e['remained_top10']
        assert e['rank_change'] is None and e['rank_censored']


def test_rank_change_uses_full_top10_and_original_regime(tmp_path):
    a=setup(tmp_path)
    with closing(t.connect(tmp_path/'db')) as db:
        t.capture(db,'s1',START,'BEAR',rankings(),a)
        rows=[dict(asset=f'OTHER{i}',pair='ALTUSD',rank=i) for i in range(1,5)]
        rows.append(dict(asset='ALT',pair='ALTUSD',rank=5))
        t.capture(db,'s2',START+timedelta(days=1),'BULL',rankings(rows),a)
        t.mature(db,START+timedelta(days=1),a)
        e=json.loads(next(e['payload'] for e in events(db) if e['kind']=='NEXT_DAY_RANK'))
        assert e['next_rank']==5 and e['rank_change']==-4
        assert e['remained_top10'] and not e['remained_top3']
        group=next(g for g in t.aggregate(db)['groups'] if g['level']=='TYPE_REGIME' and g['regime']=='BEAR')
        assert group['observations']==1 and group['price_completed']==group['rank_completed']==1
        assert group['mean_return_24h_pct']==pytest.approx(10)


def test_retry_and_immutable_tables(tmp_path):
    a=setup(tmp_path)
    with closing(t.connect(tmp_path/'db')) as db:
        t.capture(db,'s1',START,'BEAR',rankings(),a)
        before=obs(db)
        t.capture(db,'s1',START+timedelta(minutes=10),'CHANGED',rankings([]),a)
        assert obs(db)==before
        t.mature(db,START+timedelta(days=1),a)
        for table in ('observations','scans','outcomes'):
            with pytest.raises(sqlite3.IntegrityError,match='append-only'):
                db.execute(f"UPDATE {table} SET payload='{{}}'")
            db.rollback()
            with pytest.raises(sqlite3.IntegrityError,match='append-only'):
                db.execute(f'INSERT OR REPLACE INTO {table} SELECT * FROM {table}')
            db.rollback()
            with pytest.raises(sqlite3.IntegrityError,match='append-only'):
                db.execute(f'DELETE FROM {table}')
            db.rollback()


def test_invalid_order_rolls_back_entire_scan(tmp_path):
    a=setup(tmp_path)
    with closing(t.connect(tmp_path/'db')) as db:
        with pytest.raises(ValueError,match='published order'):
            t.capture(db,'bad',START,'BEAR',rankings([dict(asset='ALT',pair='ALTUSD',rank=2)]),a)
        assert db.execute('SELECT count(*) FROM scans').fetchone()[0]==0


def test_invalid_and_duplicate_candles_cannot_mature(tmp_path):
    setup(tmp_path)
    path=tmp_path/'DATASETS/market_intraday_weekly/ALTUSD_1H.csv'
    d=pd.read_csv(path);d.loc[10,'low']=10000
    d=pd.concat([d,d.iloc[[11]]]);d.to_csv(path,index=False)
    a=t.HourlyArchive(tmp_path)
    with pytest.raises(ValueError,match='Incomplete'):
        a.window('ALT','ALTUSD',START)
    with pytest.raises(ValueError,match='Unsupported'):
        a.reference('ALT','../ALTUSD',START)


def test_production_adapter_preserves_existing_lists_and_writes_summary(tmp_path):
    a=setup(tmp_path)
    chief=dict(generated_at_utc=START.isoformat(),market_state={'crypto_regime':'BEAR'},
               candidates=[dict(asset='ALT',identity={'kraken_pair':'ALTUSD'})])
    opportunity=dict(continuation_watchlist=[dict(asset='ALT',rank=1)],reversal_watchlist=[])
    relative=dict(generated_at_utc=START.isoformat(),freshness='FRESH',candidates=[dict(asset='ALT',rank=1,pair='ALTUSD')])
    frozen=t.encode([chief,opportunity,relative])
    report=tmp_path/'reports/summary.json'
    summary=t.track_daily(chief,opportunity,relative,START,path=tmp_path/'db',report=report,archive=a)
    assert t.encode([chief,opportunity,relative])==frozen
    assert summary['trading']=='DISABLED' and json.loads(report.read_text())['groups']
    with closing(t.connect(tmp_path/'db')) as db:
        assert {o['ranking_type'] for o in obs(db)}=={'CONTINUATION','RELATIVE_STRENGTH'}
    with pytest.raises(ValueError,match='stale or from future'):
        t.track_daily(chief,opportunity,relative,START+timedelta(days=1),path=tmp_path/'other',report=report,archive=a)


def test_daily_hook_gates_replay_and_surfaces_failure(monkeypatch):
    import run_daily_quant_system as q
    calls=[]
    monkeypatch.setattr(t,'track_daily',lambda *args: calls.append(args) or {'run_warnings':[],'groups':[]})
    chief={}; opportunity={};result={'success':True}
    assert q.ranking_tracker_section(chief,opportunity,result,genuine=False,current=START)['status']=='SKIPPED_REPLAY_OR_REUSE'
    assert not calls
    assert q.ranking_tracker_section(chief,opportunity,{'success':False},genuine=True,current=START)['status']=='SKIPPED_FAILED_SCAN'
    assert not calls
    assert q.ranking_tracker_section(chief,opportunity,result,genuine=True,current=START)['status']=='OK'
    assert len(calls)==1 and calls[0][2] is None
    def fail(*args):raise ValueError('tracker unavailable')
    monkeypatch.setattr(t,'track_daily',fail)
    assert q.ranking_tracker_section(chief,opportunity,result,genuine=True,current=START)['status']=='UNAVAILABLE'


def test_reopened_store_and_two_writers_deduplicate(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    a=setup(tmp_path)
    path=tmp_path/'db'
    with closing(t.connect(path)) as db:
        t.capture(db,'original',START,'BEAR',rankings(),a)
        frozen=obs(db)
    def write():
        with closing(t.connect(path)) as db:
            t.capture(db,'concurrent',START+timedelta(minutes=1),'BEAR',rankings(),a)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _:write(),range(2)))
    with closing(t.connect(path)) as db:
        assert len(obs(db))==2
        assert frozen[0] in obs(db)
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_missing_next_day_is_not_replaced_with_later_day(tmp_path):
    a=setup(tmp_path)
    with closing(t.connect(tmp_path/'db')) as db:
        t.capture(db,'s1',START,'BEAR',rankings(),a)
        t.capture(db,'s3',START+timedelta(days=2),'BEAR',rankings([]),a)
        t.mature(db,START+timedelta(days=2),a)
        assert not any(e['kind']=='NEXT_DAY_RANK' for e in events(db))
        group=next(g for g in t.aggregate(db)['groups'] if g['level']=='TYPE')
        assert group['rank_pending']==1 and group['rank_completed']==0
