from __future__ import annotations
import argparse,json,math
from pathlib import Path
from statistics import median
from lib.research_memory import ANALOGS,atomic_json,connect,sample_quality

NUM=['universe_above_ema20_pct','relative_strength_percentile','range_position_pct','range_quality','momentum_acceleration','volume_z_score','volatility_expansion','distance_to_breakout_pct','liquidity','spread']
CAT=['market_regime','relative_trend','range_state','momentum_stage','extension_risk']
def find(db,asset=None,snapshot_id=None,k=20,min_sample=5):
 target=db.execute('SELECT * FROM research_market_snapshots WHERE snapshot_id=?',(snapshot_id,)).fetchone() if snapshot_id else db.execute('SELECT * FROM research_market_snapshots WHERE asset=? ORDER BY timestamp_utc DESC LIMIT 1',(asset,)).fetchone()
 if not target:return {'status':'SNAPSHOT_NOT_FOUND','number_of_valid_analogs':0,'sample_quality':'INSUFFICIENT_ANALOG_SAMPLE','research_only':True}
 rows=db.execute('SELECT s.*,f.* FROM research_market_snapshots s JOIN research_forward_outcomes f USING(snapshot_id) WHERE s.snapshot_id<>? AND (f.return_12h_pct IS NOT NULL OR f.return_24h_pct IS NOT NULL OR f.return_48h_pct IS NOT NULL)',(target['snapshot_id'],)).fetchall()
 scales={}
 for f in NUM:
  vals=[float(r[f]) for r in rows if r[f] is not None]
  scales[f]=(max(vals)-min(vals)) if vals and max(vals)>min(vals) else None
 scored=[]
 for r in rows:
  parts=[]
  for f in NUM:
   if target[f] is not None and r[f] is not None and scales[f]:parts.append(abs(float(target[f])-float(r[f]))/scales[f])
  for f in CAT:
   if target[f] is not None and r[f] is not None:parts.append(0.0 if target[f]==r[f] else 1.0)
  if len(parts)>=4:scored.append((sum(parts)/len(parts),r))
 nearest=sorted(scored,key=lambda x:(x[0],x[1]['timestamp_utc'],x[1]['asset']))[:k]
 def med(field):
  v=[float(r[field]) for _,r in nearest if r[field] is not None];return median(v) if v else None
 def pos(field):
  v=[float(r[field]) for _,r in nearest if r[field] is not None];return 100*sum(x>0 for x in v)/len(v) if v else None
 n=len(nearest); result={'status':'OK' if n>=min_sample else 'INSUFFICIENT_ANALOG_SAMPLE','asset':target['asset'],'snapshot_id':target['snapshot_id'],'number_of_valid_analogs':n,
  'median_forward_return_12h':med('return_12h_pct'),'median_forward_return_24h':med('return_24h_pct'),'median_forward_return_48h':med('return_48h_pct'),'median_mfe_24h':med('mfe_24h_pct'),'median_mae_24h':med('mae_24h_pct'),
  'pct_positive_12h':pos('return_12h_pct'),'pct_positive_24h':pos('return_24h_pct'),'pct_positive_48h':pos('return_48h_pct'),'nearest_analog_dates':[r['timestamp_utc'] for _,r in nearest],
  'nearest_analog_assets':[r['asset'] for _,r in nearest],'distance_score':[d for d,_ in nearest],'sample_quality':sample_quality(n) if n>=min_sample else 'INSUFFICIENT_ANALOG_SAMPLE','research_only':True,'method':'transparent min-max normalized distance plus unit categorical mismatch penalties'}
 return result
def run(asset=None,snapshot_id=None,k=20,db_path=None):
 db=connect(Path(db_path)) if db_path else connect();r=find(db,asset,snapshot_id,k);db.close();atomic_json(ANALOGS/f"latest_{r.get('asset','unknown')}_analogs.json",r);return r
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--asset');g.add_argument('--snapshot-id');p.add_argument('-k',type=int,default=20);p.add_argument('--db');a=p.parse_args();print(json.dumps(run(a.asset,a.snapshot_id,a.k,a.db),indent=2))
if __name__=='__main__':main()
