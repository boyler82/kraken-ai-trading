"""Independent outcome reconciliation and immutable source checks (offline)."""
from pathlib import Path
import hashlib, json
import numpy as np
import pandas as pd

P=Path(__file__).resolve().parent
R=P.parents[1]
m=json.loads((P/'manifest.json').read_text())
t=pd.read_csv(P/'observations.csv')
for source in m['sources']:
    assert hashlib.sha256((R/source['path']).read_bytes()).hexdigest()==source['sha256'],source['path']
assert hashlib.sha256((P/'run.py').read_bytes()).hexdigest()==m['code_sha256']
assert hashlib.sha256((P/'spec.json').read_bytes()).hexdigest()==m['spec_sha256']
data={}
for a in [*t.asset.unique(),'XBT']:
    d=pd.read_csv(R/f'DATASETS/market_intraday_weekly/{a}USD_1H.csv')
    d.index=pd.to_datetime(d.timestamp,utc=True)
    data[a]=d
btc=data['XBT']
for row in t.itertuples():
    s=pd.Timestamp(row.signal); end=pd.Timestamp(row.common_exit)
    assert end==s+pd.Timedelta(hours=73)
    if not row.filled:
        assert row.policy_net==0
        continue
    e=pd.Timestamp(row.entry); d=data[row.asset]; price=d.at[e,'open']
    assert s<e<=s+pd.Timedelta(hours=25)
    assert np.isclose(row.policy_net,100*(d.at[end,'open']/price-1)-.6)
    for h in [24,48,72]:
        x=e+pd.Timedelta(hours=h)
        assert np.isclose(getattr(row,f'gross_{h}'),100*(d.at[x,'open']/price-1))
        window=d.loc[e:x-pd.Timedelta(hours=1)]
        assert len(window)==h
        assert np.isclose(getattr(row,f'mfe_{h}'),100*(window.high.max()/price-1))
        assert np.isclose(getattr(row,f'mae_{h}'),100*(window.low.min()/price-1))
        assert np.isclose(getattr(row,f'btc_{h}'),100*(btc.at[x,'open']/btc.at[e,'open']-1))
print(f'PASS: {len(m["sources"])} source hashes; specification/code hashes; {len(t)} observations reconciled.')
