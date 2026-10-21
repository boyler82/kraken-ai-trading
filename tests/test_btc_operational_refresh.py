"""Hermetic BTC operational refresh and daily dependency-order checks."""
import csv
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from quant_research_v2.schemas import utc
import btc_operational_refresh as btc

def write_bars(path,times):
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=['timestamp','open','high','low','close','volume']);w.writeheader()
        w.writerows(dict(timestamp=t,open=10,high=11,low=9,close=10,volume=1) for t in times)

def test_btc_refresh_precedes_validation_and_covers_gap(tmp_path,monkeypatch):
    p=tmp_path/'btc.csv'; end=btc.timestamp('2026-10-19T00:00:00Z')-900
    start=end-77*86400;write_bars(p,[start]);calls=[]
    def refresh(args,**kwargs):
        calls.append(args);write_bars(p,range(start,end+900,900));return SimpleNamespace(returncode=0)
    monkeypatch.setattr(btc.subprocess,'run',refresh)
    monkeypatch.setattr(btc,'datetime',type('Clock',(),{'now':staticmethod(lambda tz:utc('2026-10-19T00:00:00Z')),'fromisoformat':staticmethod(__import__('datetime').datetime.fromisoformat),'fromtimestamp':staticmethod(__import__('datetime').datetime.fromtimestamp)}))
    assert btc.ensure_operational(path=p)['status']=='OK'
    assert '--incremental' in calls[0] and int(calls[0][-1])>=78

@pytest.mark.parametrize('problem',['stale','gap','off_grid','future','duplicate'])
def test_btc_rejects_bad_reference_window(tmp_path,problem):
    p=tmp_path/'btc.csv';now='2026-10-19T00:00:00Z';end=btc.timestamp(now)-900
    times=list(range(end-7200,end+900,900))
    if problem=='stale':times.pop()
    if problem=='gap':times.remove(end-900)
    if problem=='off_grid':times[0]+=1
    if problem=='future':times.append(end+900)
    if problem=='duplicate':times.append(end)
    write_bars(p,times)
    with pytest.raises(ValueError,match='BTC_OPERATIONAL_'):btc.validate(p,now)

def test_failed_refresh_stops_consumers(monkeypatch):
    import run_complete_daily_research as daily
    monkeypatch.setattr(btc,'ensure_operational',lambda **k: (_ for _ in ()).throw(ValueError('BTC_OPERATIONAL_STALE')))
    monkeypatch.setattr(daily,'call',lambda *a: pytest.fail('consumer ran before BTC gate'))
    with pytest.raises(ValueError,match='BTC_OPERATIONAL_STALE'):daily.run()

def test_refresh_catches_up_across_candle_boundary(tmp_path,monkeypatch):
    from datetime import datetime
    p=tmp_path/'btc.csv';start=btc.timestamp('2026-10-18T23:00:00Z');write_bars(p,[start]);calls=[]
    clock=type('Clock',(),{'now':staticmethod(lambda tz:utc('2026-10-19T00:30:00Z')),'fromisoformat':staticmethod(datetime.fromisoformat),'fromtimestamp':staticmethod(datetime.fromtimestamp)})
    monkeypatch.setattr(btc,'datetime',clock)
    def refresh(args,**kwargs):
        calls.append(args);end=btc.timestamp('2026-10-19T00:00:00Z' if len(calls)==1 else '2026-10-19T00:30:00Z')-900
        write_bars(p,range(start,end+900,900));return SimpleNamespace(returncode=0)
    monkeypatch.setattr(btc.subprocess,'run',refresh)
    assert btc.ensure_operational(as_of='2026-10-19T00:00:00Z',path=p)['status']=='OK'
    assert len(calls)==2

@pytest.mark.parametrize('exit_code',[0,1])
def test_refresh_failure_or_no_progress_fails_closed(tmp_path,monkeypatch,exit_code):
    p=tmp_path/'btc.csv';write_bars(p,[btc.timestamp('2026-08-03T17:00:00Z')])
    monkeypatch.setattr(btc.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=exit_code))
    with pytest.raises(ValueError,match='BTC_OPERATIONAL_REFRESH_'):
        btc.ensure_operational(path=p)

def test_live_consumers_share_validated_btc_cutoff(monkeypatch):
    import run_complete_daily_research as daily
    cutoff='2026-10-19T00:30:00+00:00';calls=[]
    monkeypatch.setattr(btc,'ensure_operational',lambda **k:{'validated_as_of_utc':cutoff})
    class ReachedMarket(Exception):pass
    def call(args):
        calls.append(args)
        if args[0]=='scripts/run_daily_market_opportunity_scan.py':
            assert args[args.index('--as-of')+1]==cutoff
            raise ReachedMarket()
        return True,''
    monkeypatch.setattr(daily,'call',call)
    with pytest.raises(ReachedMarket):daily.run()
    assert calls[0]==['scripts/run_research.py']


def test_existing_refresher_is_public_and_uses_canonical_path():
    import importlib.util
    spec=importlib.util.spec_from_file_location('btc_trade_refresher',btc.REFRESHER)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.TRADES_URL=='https://api.kraken.com/0/public/Trades'
    assert module.OPERATIONAL_PATH==btc.SOURCE
    assert module.INTERVAL==btc.INTERVAL==900


def test_offline_validation_never_substitutes_source(tmp_path,monkeypatch):
    path=tmp_path/'btc.csv';cutoff='2026-10-19T00:00:00Z';end=btc.timestamp(cutoff)-900
    write_bars(path,range(end-7200,end+900,900))
    monkeypatch.setattr(btc.subprocess,'run',lambda *a,**k:pytest.fail('offline invoked refresh'))
    assert btc.ensure_operational(as_of=cutoff,refresh=False,path=path)['status']=='OK'
    with pytest.raises(ValueError,match='BTC_OPERATIONAL_STALE'):
        btc.ensure_operational(as_of='2026-10-19T00:15:00Z',refresh=False,path=path)
    with pytest.raises(FileNotFoundError):
        btc.ensure_operational(as_of=cutoff,refresh=False,path=tmp_path/'missing.csv')


@pytest.mark.parametrize('value',['nan','inf','-1'])
def test_invalid_candle_fails_closed(tmp_path,value):
    path=tmp_path/'btc.csv';cutoff='2026-10-19T00:00:00Z';end=btc.timestamp(cutoff)-900
    write_bars(path,range(end-7200,end+900,900))
    rows=btc.read_rows(path);rows[-1]['close']=value
    with path.open('w') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    with pytest.raises(ValueError,match='BTC_OPERATIONAL_INVALID_OHLCV'):
        btc.validate(path,cutoff)
