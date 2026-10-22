"""Standalone offline study; specification frozen in spec.json before testing."""
from pathlib import Path
import hashlib, io, json, platform
import numpy as np
import pandas as pd

P=Path(__file__).resolve().parent
ROOT=P.parents[1]
SPEC=json.loads((P/'spec.json').read_text())
STABLE=set('USDT USDC DAI PYUSD EURT USDS FDUSD TUSD USDP GUSD USD1 USDE USDD RLUSD FRAX'.split())
def sha(b): return hashlib.sha256(b).hexdigest()

def load():
    frames={}; manifest=[]
    for p in sorted((ROOT/'DATASETS/market_intraday_weekly').glob('*USD_1H.csv')):
        raw=p.read_bytes(); d=pd.read_csv(io.BytesIO(raw))
        d['timestamp']=pd.to_datetime(d.timestamp,utc=True)
        d=d[d.timestamp<pd.Timestamp(SPEC['cutoff_exclusive_utc'])].copy()
        cols=['open','high','low','close','volume'];d[cols]=d[cols].apply(pd.to_numeric,errors='coerce')
        bad=(~np.isfinite(d[cols]).all(axis=1)|(d[cols[:4]]<=0).any(axis=1)|(d.volume<0)
             |(d.high<d[['open','low','close']].max(axis=1))|(d.low>d[['open','high','close']].min(axis=1))
             |d.timestamp.duplicated(keep=False)|(d.timestamp!=d.timestamp.dt.floor('h')))
        clean=d.loc[~bad].set_index('timestamp').sort_index()[cols]
        manifest.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(raw),rows_before_cutoff=len(d),rejected=int(bad.sum()),
                             start=str(clean.index.min()),end=str(clean.index.max()),
                             missing_hours=int((clean.index.max()-clean.index.min()).total_seconds()/3600+1-len(clean)) if len(clean) else 0))
        a=p.name.removesuffix('USD_1H.csv')
        if a not in STABLE: frames[a]=clean
    return frames,manifest

def features(d,s,w):
    past=d.iloc[s-w:s]; lo=past.low.min();hi=past.high.max();width=hi-lo
    amp=(hi/lo-1)*100
    c=past.close.to_numpy(); movement=np.abs(np.diff(c)).sum()
    efficiency=abs(c[-1]-c[0])/movement if movement>0 else 1.
    if not 3<=amp<=15 or efficiency>.30 or width<=0: return None
    for third in np.array_split(np.arange(w),3):
        z=past.iloc[third]
        if z.high.max()-z.low.min()<.5*width:return None
    visits=[];last=None
    for i,price in enumerate(c):
        side='L' if price<=lo+.2*width else 'U' if price>=hi-.2*width else None
        if side is not None and side!=last:
            visits.append(i);last=side
    transitions=max(0,len(visits)-1)
    duration=float(np.median(np.diff(visits))) if transitions else np.nan
    return lo,hi,amp,efficiency,transitions,duration

def main():
    frames,sources=load();btc=frames.pop('XBT');frames.pop('BTC',None)
    idx=pd.date_range(btc.index.min(),btc.index.max(),freq='h');btc=btc.reindex(idx)
    vol=btc.close.pct_change(fill_method=None).rolling(168).std(); median=vol.rolling(720).median()
    trend=btc.close>btc.close.rolling(168).mean()
    rows=[];excluded=0;accepted=0
    for asset,raw in frames.items():
        d=raw.reindex(idx); joint=d.notna().all(axis=1)&btc.notna().all(axis=1)
        continuous=joint.rolling(169).sum().eq(169)
        liquid=(d.close*d.volume).rolling(24).sum().ge(1e6)
        eligible=np.flatnonzero((continuous&liquid).to_numpy())
        vratio=d.volume/d.volume.shift().rolling(24).mean()
        for w in SPEC['windows_hours']:
            last={(v,side):-10000 for v in SPEC['variants'] for side in ['SUPPORT','RESISTANCE']}
            # Vectorized range prefilter; detailed cycle scan only for plausible events.
            lo_series=d.low.shift().rolling(w).min();hi_series=d.high.shift().rolling(w).max()
            for s in eligible:
                lo=lo_series.iloc[s];hi=hi_series.iloc[s];width=hi-lo
                sides=[]
                if lo<=d.close.iloc[s]<=lo+.2*width and d.low.iloc[s]<=lo+.2*width:sides.append('SUPPORT')
                if hi-.2*width<=d.close.iloc[s]<=hi and d.high.iloc[s]>=hi-.2*width:sides.append('RESISTANCE')
                if not sides:continue
                feat=features(d,s,w)
                if feat is None:continue
                lo,hi,amp,eff,trans,duration=feat
                cycle=trans>=4 and 2<=duration<=24
                for side in sides:
                    rejection=d.close.iloc[s]>d.close.iloc[s-1] if side=='SUPPORT' else d.close.iloc[s]<d.close.iloc[s-1]
                    for v in SPEC['variants']:
                        if v!='BASE_TOUCH' and not cycle:continue
                        if v=='CYCLE_REJECT' and not rejection:continue
                        if s-last[(v,side)]<48:continue
                        last[(v,side)]=s;accepted+=1
                        if s+49>=len(idx) or not joint.iloc[s:s+50].all():
                            excluded+=1;continue
                        e=s+1; price=d.open.iloc[e]
                        regime='UNKNOWN' if pd.isna(median.iloc[s]) else ('UP' if trend.iloc[s] else 'DOWN')+'_'+('HIGH' if vol.iloc[s]>median.iloc[s] else 'LOW')
                        vr=vratio.iloc[s]
                        r=dict(asset=asset,signal=str(idx[s]),entry=str(idx[e]),variant=f'W{w}_{v}',window=w,rule=v,side=side,
                               support=lo,resistance=hi,amplitude_pct=amp,efficiency=eff,transitions=trans,cycle_duration_hours=duration,
                               amplitude_bin='3-6' if amp<6 else '6-10' if amp<10 else '10-15',
                               duration_bin='NO_CYCLE' if not cycle else '2-6' if duration<6 else '6-12' if duration<12 else '12-24',
                               volume_ratio=vr,volume_context='LOW' if vr<.75 else 'NORMAL' if vr<=1.5 else 'HIGH',
                               regime=regime,week=idx[s].strftime('%G-W%V'),exit48=str(idx[e+48]))
                        for h in [12,24,48]:
                            held=d.iloc[e:e+h];g=(d.open.iloc[e+h]/price-1)*100;b=(btc.open.iloc[e+h]/btc.open.iloc[e]-1)*100
                            r.update({f'gross_{h}':g,f'btc_{h}':b,f'relative_{h}':((1+g/100)/(1+b/100)-1)*100,
                                      f'mfe_{h}':(held.high.max()/price-1)*100,f'mae_{h}':(held.low.min()/price-1)*100})
                        held=d.iloc[e:e+24]
                        target=held.high.ge(hi) if side=='SUPPORT' else held.low.le(lo)
                        failure=held.low.le(lo-.1*width) if side=='SUPPORT' else held.high.ge(hi+.1*width)
                        ti=np.flatnonzero(target.to_numpy());fi=np.flatnonzero(failure.to_numpy())
                        first_t=int(ti[0]) if len(ti) else 100;first_f=int(fi[0]) if len(fi) else 100
                        r.update(target_touch_24=bool(len(ti)),failure_touch_24=bool(len(fi)),
                                 first_event='NONE' if first_t==first_f==100 else 'AMBIGUOUS' if first_t==first_f else 'TARGET' if first_t<first_f else 'FAILURE',
                                 entry_outside_range=not lo<=price<=hi)
                        rows.append(r)
    t=pd.DataFrame(rows);assert len(t)>0
    end=None;cluster=-1;cmap={}
    for r in t.sort_values('signal').itertuples():
        start=pd.Timestamp(r.signal);finish=pd.Timestamp(r.exit48)
        if end is None or start>end:cluster+=1
        end=max(end,finish) if end is not None else finish
        cmap[(r.asset,r.signal)]=cluster
    t['cluster']=[cmap[(r.asset,r.signal)] for r in t.itertuples()]
    t['net24']=t.gross_24-.6
    midpoint=pd.Timestamp(t.signal.min())+(pd.Timestamp(t.signal.max())-pd.Timestamp(t.signal.min()))/2
    t['half']=np.where(pd.to_datetime(t.signal)<midpoint,'EARLY','LATE')
    def stats(g):
        return dict(n=len(g),assets=g.asset.nunique(),clusters=g.cluster.nunique(),ev_pct=g.net24.mean(),median_pct=g.net24.median(),
                    win_rate_pct=(g.net24>0).mean()*100,mfe_pct=g.mfe_24.mean(),mae_pct=g.mae_24.mean(),
                    btc_net_pct=(g.btc_24-.6).mean(),relative_gross_pct=g.relative_24.mean(),excess_net_pp=(g.gross_24-g.btc_24).mean(),
                    target_touch_pct=g.target_touch_24.mean()*100,failure_touch_pct=g.failure_touch_24.mean()*100,
                    target_first_pct=g.first_event.eq('TARGET').mean()*100,failure_first_pct=g.first_event.eq('FAILURE').mean()*100,
                    ambiguous_pct=g.first_event.eq('AMBIGUOUS').mean()*100)
    def group(keys,name):
        out=[]
        for k,g in t.groupby(keys):
            if not isinstance(k,tuple):k=(k,)
            out.append({**dict(zip(keys,k)),**stats(g)})
        pd.DataFrame(out).to_csv(P/name,index=False)
    for key,name in [('regime','regimes'),('volume_context','volume'),('amplitude_bin','amplitude'),('duration_bin','duration'),('half','halves'),('asset','assets'),('cluster','clusters')]:
        group(['variant','side',key],name+'.csv')
    group(['variant','side'],'summary.csv')
    sens=[];rob=[];rng=np.random.default_rng(20261022)
    for (v,side),g in t.groupby(['variant','side']):
        for cost in [.3,.6,1.,1.5]:
            for h in [12,24,48]:
                sens.append(dict(variant=v,side=side,horizon=h,cost_pct=cost,n=len(g),ev_pct=(g[f'gross_{h}']-cost).mean(),
                                 win_rate_pct=(g[f'gross_{h}']>cost).mean()*100,btc_net_pct=(g[f'btc_{h}']-cost).mean()))
        blocks=g.groupby('week').net24.agg(['sum','count']);ix=rng.integers(0,len(blocks),(5000,len(blocks)))
        boot=blocks['sum'].to_numpy()[ix].sum(axis=1)/blocks['count'].to_numpy()[ix].sum(axis=1)
        loo=[g.loc[g.asset!=a,'net24'].mean() for a in g.asset.unique()]
        rob.append(dict(variant=v,side=side,weeks=len(blocks),week_boot_low=np.quantile(boot,.025),week_boot_high=np.quantile(boot,.975),
                        loo_min=min(loo),loo_max=max(loo),without_top3=g.net24.sort_values().iloc[:-3].mean()))
    pd.DataFrame(sens).to_csv(P/'sensitivity.csv',index=False);pd.DataFrame(rob).to_csv(P/'robustness.csv',index=False)
    comparisons=[]
    for w in SPEC['windows_hours']:
        for side in ['SUPPORT','RESISTANCE']:
            base=t[(t.window==w)&(t.side==side)&(t.rule=='BASE_TOUCH')].set_index(['asset','signal'])
            for v in ['CYCLE_TOUCH','CYCLE_REJECT']:
                g=t[(t.window==w)&(t.side==side)&(t.rule==v)].set_index(['asset','signal'])
                shared=base.index.intersection(g.index)
                comparisons.append(dict(window=w,side=side,rule=v,baseline_n=len(base),cycle_n=len(g),
                                         baseline_ev=base.net24.mean(),cycle_ev=g.net24.mean(),unpaired_difference_pp=g.net24.mean()-base.net24.mean(),
                                         shared_signals=len(shared),shared_difference_pp=(g.loc[shared,'net24']-base.loc[shared,'net24']).mean()))
    pd.DataFrame(comparisons).to_csv(P/'comparisons.csv',index=False)
    t.to_csv(P/'observations.csv',index=False)
    checks=dict(unique_rows=not t.duplicated(['asset','signal','variant','side']).any(),finite=bool(np.isfinite(t[['gross_12','gross_24','gross_48','net24']]).all().all()),
                next_open=bool((pd.to_datetime(t.entry)-pd.to_datetime(t.signal)).eq(pd.Timedelta(hours=1)).all()),
                cycles=bool((t.loc[t.rule!='BASE_TOUCH','transitions']>=4).all()))
    assert all(checks.values())
    (P/'manifest.json').write_text(json.dumps(dict(spec_sha256=sha((P/'spec.json').read_bytes()),code_sha256=sha(Path(__file__).read_bytes()),
          python=platform.python_version(),pandas=pd.__version__,numpy=np.__version__,sources=sources,accepted_before_outcome_filter=accepted,
          excluded_incomplete_outcome=excluded,rows=len(t),unique_asset_signals=len(t[['asset','signal']].drop_duplicates()),
          global_clusters=cluster+1,checks=checks),indent=2)+'\n')
    print(pd.read_csv(P/'summary.csv').to_string(index=False))

if __name__=='__main__':main()
