from __future__ import annotations
import argparse,json
from collections import defaultdict
from pathlib import Path
from statistics import median
from lib.research_memory import ROOT,STATS,atomic_json,connect,metrics,sample_quality

def _med(rows,key):
 v=[float(x[key]) for x in rows if x[key] is not None];return median(v) if v else None
def fast_range_candidates(db,minimum=5):
 source=ROOT/'DATASETS/RANGE_PERSONALITY/range_episode_history.json';episodes=json.loads(source.read_text()).get('episodes',[]) if source.exists() else []
 grouped=defaultdict(list)
 for e in episodes:
  for t in e.get('traversals',[]):
   if 2.5<=float(t.get('gross_move_percent') or 0)<=5.5 and 8<=float(t.get('hours') or 0)<=18:grouped[e.get('asset')].append((e,t))
 latest={r['asset']:r for r in db.execute('SELECT * FROM research_market_snapshots WHERE (asset,timestamp_utc) IN (SELECT asset,max(timestamp_utc) FROM research_market_snapshots GROUP BY asset)')}
 out=[]
 for asset,items in grouped.items():
  if len(items)<minimum:continue
  snap=latest.get(asset);moves=[float(t['gross_move_percent']) for _,t in items];dur=[float(t['hours']) for _,t in items]
  out.append({'asset':asset,'historical_fast_range_episode_count':len(items),'median_move_pct':median(moves),'median_duration_hours':median(dur),'false_break_rate':100*sum(bool(t.get('false_break_during_traversal')) for _,t in items)/len(items),'median_mfe':median([float(t.get('maximum_favorable_movement') or 0) for _,t in items]),'median_mae':median([float(t.get('maximum_adverse_movement') or 0) for _,t in items]),'liquidity':snap['liquidity'] if snap else None,'spread':snap['spread'] if snap else None,'current_range_position':snap['range_position_pct'] if snap else None,'current_range_validity':snap['range_validity'] if snap else None,'sample_quality':sample_quality(len(items))})
 return sorted(out,key=lambda x:(-x['historical_fast_range_episode_count'],-x['median_move_pct'],x['asset']))
def run(db_path=None):
 db=connect(Path(db_path)) if db_path else connect();assets=[x[0] for x in db.execute('SELECT asset FROM research_market_snapshots UNION SELECT asset FROM research_setup_outcomes')];rows=[]
 episodes=json.loads((ROOT/'DATASETS/RANGE_PERSONALITY/range_episode_history.json').read_text()).get('episodes',[]) if (ROOT/'DATASETS/RANGE_PERSONALITY/range_episode_history.json').exists() else []
 for asset in assets:
  snaps=[dict(x) for x in db.execute('SELECT s.*,f.* FROM research_market_snapshots s LEFT JOIN research_forward_outcomes f USING(snapshot_id) WHERE asset=?',(asset,))];outs=[dict(x) for x in db.execute('SELECT * FROM research_setup_outcomes WHERE asset=?',(asset,))];by=defaultdict(list)
  for x in outs:by[x['strategy_family']].append(x)
  valid=[(k,metrics(v)) for k,v in by.items() if metrics(v)['unique_episode_count']>=10];best=max(valid,key=lambda x:x[1]['expected_value_pct'],default=None);reg=defaultdict(list)
  for x in outs:
   if x['market_regime_at_entry']:reg[x['market_regime_at_entry']].append(x)
  validreg=[(k,metrics(v)) for k,v in reg.items() if metrics(v)['unique_episode_count']>=10];ranges=[e for e in episodes if e.get('asset')==asset]
  rows.append({'asset':asset,'snapshot_count':len(snaps),'completed_episode_count':len({x['setup_episode_id'] for x in outs}),'best_observed_strategy_family':best[0] if best else 'INSUFFICIENT_SAMPLE','best_observed_strategy_ev':best[1]['expected_value_pct'] if best else None,'best_observed_strategy_pf':best[1]['profit_factor'] if best else None,'median_4h_move':_med(snaps,'return_4h_pct'),'median_12h_move':_med(snaps,'return_12h_pct'),'median_24h_move':_med(snaps,'return_24h_pct'),'median_48h_move':_med(snaps,'return_48h_pct'),'median_mfe_24h':_med(snaps,'mfe_24h_pct'),'median_mae_24h':_med(snaps,'mae_24h_pct'),'range_episode_count':len(ranges),'median_range_move':median([100*(e['range_high']/e['range_low']-1) for e in ranges]) if ranges else None,'median_range_duration':median([e.get('calendar_duration_hours') for e in ranges if e.get('calendar_duration_hours') is not None]) if ranges else None,'momentum_episode_count':len({x['setup_episode_id'] for x in outs if x['strategy_family']=='MOMENTUM_BREAKOUT'}),'best_observed_regime':max(validreg,key=lambda x:x[1]['expected_value_pct'])[0] if validreg else 'INSUFFICIENT_SAMPLE','worst_observed_regime':min(validreg,key=lambda x:x[1]['expected_value_pct'])[0] if validreg else 'INSUFFICIENT_SAMPLE'})
 fast=fast_range_candidates(db);db.close();atomic_json(STATS/'latest_coin_personality.json',{'assets':rows,'research_only':True});atomic_json(STATS/'latest_fast_range_candidates.json',{'minimum_completed_fast_range_episodes':5,'candidates':fast,'status':'OK' if fast else 'INSUFFICIENT_SAMPLE','research_only':True})
 lines=['# Fast Range Candidates','','RESEARCH_ONLY | minimum 5 completed 2.5%-5.5% traversals lasting 8-18h','']+([f"- {x['asset']} | N={x['historical_fast_range_episode_count']} | move={x['median_move_pct']:.2f}% | duration={x['median_duration_hours']:.1f}h | quality={x['sample_quality']}" for x in fast] or ['- No assets qualify; no ranking fabricated.']);(STATS/'latest_fast_range_candidates.md').write_text('\n'.join(lines)+'\n');return {'assets':rows,'fast_range':fast}
def main():
 p=argparse.ArgumentParser();p.add_argument('--db');a=p.parse_args();r=run(a.db);print(f"Assets: {len(r['assets'])}; fast-range candidates: {len(r['fast_range'])}")
if __name__=='__main__':main()
