"""Offline, standalone study. Run with .venv-research/bin/python RESEARCH/RS_PULLBACK_V1/run.py."""
from pathlib import Path
import hashlib, io, json, platform
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEC = json.loads((HERE / 'spec.json').read_text())
STABLE = set('USDT USDC DAI PYUSD EURT USDS FDUSD TUSD USDP GUSD USD1 USDE USDD RLUSD FRAX'.split())

def digest(b):
    return hashlib.sha256(b).hexdigest()

def main():
    manifest, frames = [], {}
    for path in sorted((ROOT / 'DATASETS/market_intraday_weekly').glob('*USD_1H.csv')):
        raw = path.read_bytes()
        d = pd.read_csv(io.BytesIO(raw))
        d['timestamp'] = pd.to_datetime(d.timestamp, utc=True)
        d = d[d.timestamp < pd.Timestamp(SPEC['cutoff_exclusive_utc'])].copy()
        cols = ['open', 'high', 'low', 'close', 'volume']
        d[cols] = d[cols].apply(pd.to_numeric, errors='coerce')
        invalid = (~np.isfinite(d[cols]).all(axis=1) | (d[cols[:4]] <= 0).any(axis=1)
                   | (d.volume < 0) | (d.high < d[['open','close','low']].max(axis=1))
                   | (d.low > d[['open','close','high']].min(axis=1))
                   | (d.timestamp != d.timestamp.dt.floor('h')))
        duplicates = d.timestamp.duplicated(keep=False)
        bad = invalid | duplicates
        clean = d[~bad].set_index('timestamp').sort_index()[cols]
        asset = path.name.removesuffix('USD_1H.csv')
        manifest.append(dict(path=str(path.relative_to(ROOT)), sha256=digest(raw), rows=len(d),
                             rejected=int(bad.sum()), start=str(clean.index.min()), end=str(clean.index.max()),
                             missing_hours=int((clean.index.max()-clean.index.min()).total_seconds()/3600+1-len(clean)) if len(clean) else 0))
        if asset not in STABLE:
            frames[asset] = clean
    btc = frames.pop('XBT')
    frames.pop('BTC', None)
    idx = pd.date_range(btc.index.min(), btc.index.max(), freq='h')
    btc = btc.reindex(idx)
    close = pd.DataFrame({a:d.close.reindex(idx) for a,d in frames.items()})
    ratio = close.div(btc.close, axis=0)
    rs = ratio / ratio.shift(168)-1
    rs48 = ratio / ratio.shift(48)-1
    eligible, features = {}, {}
    for a,d in frames.items():
        d = d.reindex(idx)
        joint = d.notna().all(axis=1) & btc.notna().all(axis=1)
        continuity = joint.rolling(169).sum().eq(169)
        eligible[a] = continuity & (d.close*d.volume).rolling(24).sum().ge(1e6)
        tr = pd.concat([d.high-d.low, (d.high-d.close.shift()).abs(), (d.low-d.close.shift()).abs()],axis=1).max(axis=1)
        features[a] = (d, joint, tr.rolling(14).mean()/d.close)
    elig = pd.DataFrame(eligible)
    ranks = rs.where(elig).rank(axis=1, pct=True, method='average')
    leader = elig & ranks.ge(.8) & rs.gt(0) & rs48.gt(0)
    leader.loc[elig.sum(axis=1)<10,:] = False
    vol = btc.close.pct_change(fill_method=None).rolling(168).std()
    vm = vol.rolling(720).median()
    trend = btc.close > btc.close.rolling(168).mean()
    rows, exclusions = [], dict(warmup_regime=0, incomplete_outcome=0)
    for a in close:
        d,joint,atr = features[a]
        transitions = np.flatnonzero((leader[a] & ~leader[a].shift(1,fill_value=False)).to_numpy())
        last = -10000
        for s in transitions:
            if s-last < 168:
                continue
            last = s
            if pd.isna(vm.iloc[s]):
                exclusions['warmup_regime'] += 1
                continue
            if s+97 >= len(idx) or not joint.iloc[s-168:s+98].all():
                exclusions['incomplete_outcome'] += 1
                continue
            e = s+1
            regime = ('UP' if trend.iloc[s] else 'DOWN')+'_'+('HIGH' if vol.iloc[s]>vm.iloc[s] else 'LOW')
            common = e+72
            for variant in ['A', *SPEC['variants']]:
                entry = e if variant=='A' else None
                if variant!='A':
                    lo,hi = SPEC['variants'][variant]
                    if variant=='B_ATR': lo,hi = lo*atr.iloc[s],hi*atr.iloc[s]
                    peak = d.close.iloc[s]
                    for t in range(s+1,s+25):
                        peak = max(peak,d.close.iloc[t])
                        dd = 1-d.close.iloc[t]/peak
                        if dd>hi: break
                        if lo<=dd<=hi and d.close.iloc[t]>d.close.iloc[t-1] and rs[a].iloc[t]>0:
                            entry=t+1
                            break
                r = dict(asset=a,signal=str(idx[s]),variant=variant,regime=regime,week=str(idx[s].date()-pd.Timedelta(days=idx[s].weekday())),
                         common_exit=str(idx[common]),filled=entry is not None)
                r['entry'] = str(idx[entry]) if entry is not None else ''
                r['delay_hours'] = entry-e if entry is not None else np.nan
                r['btc_policy_gross'] = (btc.open.iloc[common]/btc.open.iloc[e]-1)*100
                if entry is not None:
                    p=d.open.iloc[entry]
                    r['policy_gross']=(d.open.iloc[common]/p-1)*100
                    for h in [24,48,72]:
                        g=(d.open.iloc[entry+h]/p-1)*100
                        b=(btc.open.iloc[entry+h]/btc.open.iloc[entry]-1)*100
                        r.update({f'gross_{h}':g,f'btc_{h}':b,f'relative_{h}':((1+g/100)/(1+b/100)-1)*100,
                                  f'mfe_{h}':(d.high.iloc[entry:entry+h].max()/p-1)*100,
                                  f'mae_{h}':(d.low.iloc[entry:entry+h].min()/p-1)*100})
                else: r['policy_gross']=0.
                rows.append(r)
    trades=pd.DataFrame(rows)
    assert len(trades), 'No complete observations'
    signals=trades[trades.variant=='A'].sort_values('signal').copy()
    end=None; cluster=-1; cmap={}
    for r in signals.itertuples():
        start=pd.Timestamp(r.signal); finish=pd.Timestamp(r.common_exit)
        if end is None or start>end: cluster+=1
        end=max(end,finish) if end is not None else finish
        cmap[(r.asset,r.signal)]=cluster
    trades['cluster']=[cmap[(r.asset,r.signal)] for r in trades.itertuples()]
    trades['policy_net']=trades.policy_gross-trades.filled.astype(int)*.6
    trades['btc_policy_net']=trades.btc_policy_gross-.6
    trades['half']=np.where(pd.to_datetime(trades.signal)<pd.to_datetime(signals.signal).sort_values().iloc[len(signals)//2],'EARLY','LATE')
    def summary(g):
        f=g[g.filled]
        return dict(signals=len(g),fills=len(f),fill_rate_pct=g.filled.mean()*100,policy_ev_pct=g.policy_net.mean(),
                    btc_policy_ev_pct=g.btc_policy_net.mean(),policy_minus_btc_pp=(g.policy_net-g.btc_policy_net).mean(),
                    filled_ev_48_pct=(f.gross_48-.6).mean(),win_rate_48_pct=(f.gross_48>.6).mean()*100,
                    mfe_48_pct=f.mfe_48.mean(),mae_48_pct=f.mae_48.mean(),relative_48_pct=f.relative_48.mean(),
                    btc_48_net_pct=(f.btc_48-.6).mean(),clusters=g.cluster.nunique())
    def grouped(keys,name):
        out=[]
        for k,g in trades.groupby(keys):
            if not isinstance(k,tuple):k=(k,)
            out.append({**dict(zip(keys,k)),**summary(g)})
        pd.DataFrame(out).to_csv(HERE/name,index=False)
    grouped(['variant'],'summary.csv'); grouped(['variant','regime'],'regimes.csv')
    grouped(['variant','half'],'halves.csv');grouped(['variant','asset'],'assets.csv');grouped(['variant','cluster'],'clusters.csv')
    sensitivity=[]
    for v,g in trades.groupby('variant'):
        f=g[g.filled]
        for cost in [.3,.6,1.,1.5]:
            for h in [24,48,72]:
                sensitivity.append(dict(variant=v,cost_pct=cost,horizon=h,fills=len(f),ev_pct=(f[f'gross_{h}']-cost).mean(),
                                        win_rate_pct=(f[f'gross_{h}']>cost).mean()*100,btc_ev_pct=(f[f'btc_{h}']-cost).mean(),
                                        policy_ev_pct=(g.policy_gross-g.filled.astype(int)*cost).mean()))
    pd.DataFrame(sensitivity).to_csv(HERE/'sensitivity.csv',index=False)
    paired=[]; rng=np.random.default_rng(20261022)
    a=trades[trades.variant=='A'].set_index(['asset','signal'])
    for v in SPEC['variants']:
        g=trades[trades.variant==v].set_index(['asset','signal'])
        delta=g.policy_net-a.policy_net
        blocks=pd.DataFrame({'delta':delta,'week':g.week}).groupby('week').delta.agg(['sum','count'])
        ix=rng.integers(0,len(blocks),size=(5000,len(blocks)))
        boot=blocks['sum'].to_numpy()[ix].sum(axis=1)/blocks['count'].to_numpy()[ix].sum(axis=1)
        filled=g.filled
        loo=[g[g.index.get_level_values('asset')!=asset].policy_net.mean() for asset in g.index.get_level_values('asset').unique()]
        paired.append(dict(variant=v,policy_B_minus_A_pp=delta.mean(),week_bootstrap_low=float(np.quantile(boot,.025)),week_bootstrap_high=float(np.quantile(boot,.975)),
                           filled_common_exit_B_minus_A_pp=delta[filled].mean(),matched_A_policy_ev_pct=a.loc[filled].policy_net.mean(),
                           leave_one_asset_out_min_ev_pct=min(loo),leave_one_asset_out_max_ev_pct=max(loo),weeks=len(blocks)))
    pd.DataFrame(paired).to_csv(HERE/'paired.csv',index=False)
    trades.to_csv(HERE/'observations.csv',index=False)
    checks=dict(unique_observations=not trades.duplicated(['asset','signal','variant']).any(),
                paired_complete=len(trades)==len(signals)*4,finite_policy=bool(np.isfinite(trades.policy_net).all()),
                entry_after_signal=bool((pd.to_datetime(trades.loc[trades.filled,'entry'])>pd.to_datetime(trades.loc[trades.filled,'signal'])).all()),
                no_fill_cash=bool((trades.loc[~trades.filled,'policy_net']==0).all()))
    assert all(checks.values()),checks
    (HERE/'manifest.json').write_text(json.dumps(dict(spec_sha256=digest((HERE/'spec.json').read_bytes()),code_sha256=digest(Path(__file__).read_bytes()),
         python=platform.python_version(),pandas=pd.__version__,numpy=np.__version__,cutoff=SPEC['cutoff_exclusive_utc'],sources=manifest,
         exclusions=exclusions,checks=checks,signals=len(signals),assets=signals.asset.nunique(),clusters=cluster+1),indent=2)+'\n')
    print(pd.read_csv(HERE/'summary.csv').to_string(index=False))
    print(pd.read_csv(HERE/'paired.csv').to_string(index=False))

if __name__=='__main__': main()
