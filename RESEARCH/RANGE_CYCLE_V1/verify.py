"""Independent source/outcome reconciliation, plus causal feature checks."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
from run import features

P=Path(__file__).resolve().parent;ROOT=P.parents[1]
m=json.loads((P/'manifest.json').read_text());t=pd.read_csv(P/'observations.csv')
for item in m['sources']:
    assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256'],item['path']
for file,key in [('spec.json','spec_sha256'),('run.py','code_sha256')]:
    assert hashlib.sha256((P/file).read_bytes()).hexdigest()==m[key]
data={}
for a in [*t.asset.unique(),'XBT']:
    d=pd.read_csv(ROOT/f'DATASETS/market_intraday_weekly/{a}USD_1H.csv')
    d.index=pd.to_datetime(d.timestamp,utc=True);data[a]=d
btc=data['XBT']
for row in t.itertuples():
    s=pd.Timestamp(row.signal);e=pd.Timestamp(row.entry);d=data[row.asset];price=d.at[e,'open']
    assert e==s+pd.Timedelta(hours=1)
    for h in [12,24,48]:
        x=e+pd.Timedelta(hours=h);held=d.loc[e:x-pd.Timedelta(hours=1)]
        assert len(held)==h
        g=100*(d.at[x,'open']/price-1);b=100*(btc.at[x,'open']/btc.at[e,'open']-1)
        assert np.isclose(getattr(row,f'gross_{h}'),g)
        assert np.isclose(getattr(row,f'btc_{h}'),b)
        assert np.isclose(getattr(row,f'relative_{h}'),100*((1+g/100)/(1+b/100)-1))
        assert np.isclose(getattr(row,f'mfe_{h}'),100*(held.high.max()/price-1))
        assert np.isclose(getattr(row,f'mae_{h}'),100*(held.low.min()/price-1))
    past=d.loc[s-pd.Timedelta(hours=row.window):s-pd.Timedelta(hours=1)]
    assert len(past)==row.window
    assert np.isclose(row.support,past.low.min()) and np.isclose(row.resistance,past.high.max())
    width=row.resistance-row.support
    assert 3<=100*(row.resistance/row.support-1)<=15
    changes=np.abs(np.diff(past.close.to_numpy())).sum()
    assert abs(past.close.iloc[-1]-past.close.iloc[0])/changes<=.30
    for positions in np.array_split(np.arange(row.window),3):
        third=past.iloc[positions]
        assert third.high.max()-third.low.min()>=.5*width
    levels=np.where(past.close<=row.support+.2*width,-1,np.where(past.close>=row.resistance-.2*width,1,0))
    positions=np.flatnonzero(levels)
    visits=[i for j,i in enumerate(positions) if j==0 or levels[i]!=levels[positions[j-1]]]
    assert max(0,len(visits)-1)==row.transitions
    if row.rule!='BASE_TOUCH':
        assert row.transitions>=4 and 2<=np.median(np.diff(visits))<=24
    current=d.loc[s]
    if row.side=='SUPPORT':
        assert row.support<=current.close<=row.support+.2*width
        if row.rule=='CYCLE_REJECT':assert current.close>d.at[s-pd.Timedelta(hours=1),'close']
    else:
        assert row.resistance-.2*width<=current.close<=row.resistance
        if row.rule=='CYCLE_REJECT':assert current.close<d.at[s-pd.Timedelta(hours=1),'close']
    held=d.loc[e:e+pd.Timedelta(hours=23)]
    hit=np.flatnonzero((held.high>=row.resistance if row.side=='SUPPORT' else held.low<=row.support).to_numpy())
    fail=np.flatnonzero((held.low<=row.support-.1*width if row.side=='SUPPORT' else held.high>=row.resistance+.1*width).to_numpy())
    ti=int(hit[0]) if len(hit) else 100;fi=int(fail[0]) if len(fail) else 100
    expected='NONE' if ti==fi==100 else 'AMBIGUOUS' if ti==fi else 'TARGET' if ti<fi else 'FAILURE'
    assert row.first_event==expected
    assert row.target_touch_24==bool(len(hit)) and row.failure_touch_24==bool(len(fail))
    assert np.isclose(row.net24,row.gross_24-.6)

# Purpose-built repeated oscillation and one-way drift checks.
c=105+5*np.cos(np.arange(97)*2*np.pi/12)
d=pd.DataFrame({'open':c,'high':c+.1,'low':c-.1,'close':c,'volume':1.})
f=features(d,48,48)
assert f is not None and f[4]>=4 and 2<=f[5]<=24
altered=d.copy();altered.loc[48:,'close']=10000
assert features(altered,48,48)==f, 'Future mutation changed signal-time features'
assert features(d.iloc[:48],48,48)==f, 'Prefix changed features'
c=np.linspace(100,110,97)
drift=pd.DataFrame({'open':c,'high':c+.1,'low':c-.1,'close':c,'volume':1.})
assert features(drift,48,48) is None
print(f'PASS: {len(m["sources"])} source hashes; {len(t)} rows reconciled; oscillation/drift and prefix/future-mutation checks.')
