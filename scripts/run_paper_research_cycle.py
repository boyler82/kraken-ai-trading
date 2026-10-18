from __future__ import annotations
import argparse,hashlib,json,shutil,tempfile
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
try:
 from paper_setup_extractor import extract_setups,load_reports
 from paper_strategy_decision_engine import create_decisions
 from paper_position_tracker import connect,existing_entries,open_decisions,update_open_trades,DB_PATH
 from paper_strategy_expectancy import update_stats,write_comparison
 from paper_strategy_decision_engine import config as decision_config
except ModuleNotFoundError:
 from scripts.paper_setup_extractor import extract_setups,load_reports
 from scripts.paper_strategy_decision_engine import create_decisions
 from scripts.paper_position_tracker import connect,existing_entries,open_decisions,update_open_trades,DB_PATH
 from scripts.paper_strategy_expectancy import update_stats,write_comparison
 from scripts.paper_strategy_decision_engine import config as decision_config
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'PAPER_RESEARCH';SNAPS=BASE/'SNAPSHOTS';TRADES=BASE/'TRADES';REG=ROOT/'DECISION_REGISTRY/paper_strategy_research.json'
def write_current_state(db):
 rows=[dict(r) for r in db.execute('SELECT t.*,s.setup_episode_id FROM paper_trades t JOIN paper_signals s ON s.signal_id=t.signal_id ORDER BY COALESCE(t.exit_timestamp,t.entry_timestamp) DESC,t.asset,t.strategy_variant')]
 def grouped(status,limit):
  groups={}
  for r in rows:
   if r['status']!=status:continue
   key=(r['asset'],r['setup_episode_id'],r['strategy_name']);groups.setdefault(key,[]).append(r)
  return list(groups.items())[:limit]
 open_lines=['# Latest Open Paper Trades','','PAPER_ONLY | NO_REAL_ORDERS','']
 for (asset,episode,strategy),items in grouped('OPEN',30):
  first=items[0];open_lines += [f"## {asset} | {strategy} | entry {first['entry_price']}",f"- Setup episode: {episode}",f"- Variants: {', '.join(x['strategy_variant'] for x in items)}",f"- Stops: {', '.join(str(x['stop_price']) for x in items)}",'- Status: OPEN','']
 closed_lines=['# Latest Closed Paper Trades','','PAPER_ONLY | NO_REAL_ORDERS','']
 for (asset,episode,strategy),items in grouped('CLOSED',20):
  closed_lines += [f"## {asset} | {strategy} | episode {episode}",f"- Entry: {items[0]['entry_price']} | latest exit: {items[0]['exit_timestamp']}",'- Outcomes: '+'; '.join(f"{x['strategy_variant']}={x['exit_reason']} ({x['net_return_pct']:.2f}%)" for x in items),'']
 (BASE/'latest_open_paper_trades.md').write_text('\n'.join(open_lines)+'\n');(BASE/'latest_closed_paper_trades.md').write_text('\n'.join(closed_lines)+'\n')
def _episodes(db,setups,ts):
 identities=set()
 for s in setups:
  identity=f"{s['asset']}|{s['strategy_name']}|{','.join(s['source_modules'])}";identities.add(identity);row=db.execute('SELECT * FROM paper_setup_episodes WHERE setup_identity=?',(identity,)).fetchone()
  if row and row['active']:episode=row['setup_episode_id'];first=row['first_eligible_timestamp']
  elif not row:
   prior=db.execute('SELECT setup_episode_id,timestamp FROM paper_signals WHERE asset=? AND strategy_name=? AND source_modules=? ORDER BY timestamp DESC LIMIT 1',(s['asset'],s['strategy_name'],json.dumps(s['source_modules']))).fetchone();episode=prior['setup_episode_id'] if prior else hashlib.sha256(f'{identity}|{ts}'.encode()).hexdigest()[:20];first=prior['timestamp'] if prior else ts
  else:episode=hashlib.sha256(f'{identity}|{ts}'.encode()).hexdigest()[:20];first=ts
  s['setup_episode_id']=episode;s['first_eligible_timestamp']=first;db.execute('INSERT OR REPLACE INTO paper_setup_episodes VALUES(?,?,?,?,?)',(identity,episode,1,first,ts))
 if identities:
  marks=','.join('?' for _ in identities);db.execute(f'UPDATE paper_setup_episodes SET active=0 WHERE setup_identity NOT IN ({marks})',tuple(sorted(identities)))
 else:db.execute('UPDATE paper_setup_episodes SET active=0')
 db.commit();return setups
def _market(reports):
 out={}
 for x in reports.get('momentum',{}).get('candidates',[]):out[str(x.get('asset'))]={'price':x.get('current_price'),'high':x.get('latest_high',x.get('current_price')),'low':x.get('latest_low',x.get('current_price')),'structure_valid':True}
 for x in reports.get('consolidation',{}).get('candidates',[]):out.setdefault(str(x.get('asset')),{'price':x.get('latest_available_market_price'),'structure_valid':x.get('range_valid',x.get('range_still_valid'))})
 return out
def run(as_of=None,dry_run=False,verbose=False,db_path:Path=DB_PATH)->dict:
 now=datetime.fromisoformat(str(as_of).replace('Z','+00:00')) if as_of else datetime.now(timezone.utc);now=now.astimezone(ZoneInfo('Europe/Warsaw'));ts=now.isoformat();snapshot_id=now.strftime('%Y-%m-%d_%H%M');reports=load_reports();required=('consolidation','momentum')
 if any(not reports.get(k) for k in required):raise RuntimeError('required current research outputs unavailable')
 setups=extract_setups(reports,ts);actual=db_path
 tempdir=None
 if dry_run:
  tempdir=Path(tempfile.mkdtemp(prefix='paper-research-dry-'));actual=tempdir/'dry.sqlite'
  if db_path.exists():shutil.copy2(db_path,actual)
 db=connect(actual)
 for family,variants in decision_config()['variants'].items():
  for variant,spec in variants.items():db.execute('INSERT OR REPLACE INTO paper_strategy_variants VALUES(?,?,?)',(family,variant,json.dumps(spec,sort_keys=True)))
 db.execute('INSERT OR REPLACE INTO paper_strategy_variants VALUES(?,?,?)',('MULTI_MODULE_CONFIRMATION','MULTI_TP4_SL2',json.dumps({'target_pct':4,'stop_pct':2,'max_hold_hours':72},sort_keys=True)));db.commit()
 setups=_episodes(db,setups,ts);decisions=create_decisions(setups,existing_entries(db));new=open_decisions(db,decisions,snapshot_id);updates=update_open_trades(db,_market(reports),ts);stats=update_stats(db);open_count=db.execute("SELECT count(*) FROM paper_trades WHERE status='OPEN'").fetchone()[0];closed_total=db.execute("SELECT count(*) FROM paper_trades WHERE status='CLOSED'").fetchone()[0]
 result={'status':'SUCCESS','snapshot_id':snapshot_id,'timestamp':ts,'market_regime':(reports.get('capital_flow',{}).get('summary') or {}).get('primary_state'),'btc_state':reports.get('rotation',{}).get('preferred_state'),'eligible_setups':len(setups),'newly_created_trades':len(new),'new_trade_ids':new,'updated_trades':updates['updated'],'closed_trades':updates['closed'],'data_gaps':updates['data_gaps'],'open_paper_trades':open_count,'total_closed_trades':closed_total,'updated_strategies':len(stats),'strategy_statistics_summary':stats[:10],'labels':['RESEARCH_ONLY','PAPER_ONLY','NO_REAL_ORDERS','LIVE_NOT_AUTHORIZED']}
 if not dry_run:
  SNAPS.mkdir(parents=True,exist_ok=True);TRADES.mkdir(parents=True,exist_ok=True);(BASE/'STRATEGY_VARIANTS').mkdir(parents=True,exist_ok=True);(BASE/'STATS').mkdir(parents=True,exist_ok=True);(SNAPS/f'{snapshot_id}_paper_snapshot.json').write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n');write_comparison(stats,db);write_current_state(db);summary={'module_name':'paper_strategy_research','status':'OK','generated_at_utc':ts,'total_closed_trades':closed_total,'sample_status':'INSUFFICIENT' if not stats or max(x['unique_setup_episode_count'] for x in stats)<20 else 'LOW' if max(x['unique_setup_episode_count'] for x in stats)<50 else 'MEDIUM' if max(x['unique_setup_episode_count'] for x in stats)<100 else 'HIGHER_CONFIDENCE','strategy_summaries':stats[:5],'best_observed_strategy':max(stats,key=lambda x:x['expected_value_pct'],default=None),'weakest_observed_strategy':min(stats,key=lambda x:x['expected_value_pct'],default=None),'important_changes':[f'{len(new)} paper trades created',f'{len(updates["closed"])} paper trades closed']};REG.parent.mkdir(parents=True,exist_ok=True);REG.write_text(json.dumps(summary,indent=2,sort_keys=True,allow_nan=False)+'\n');db.execute('INSERT OR REPLACE INTO paper_snapshot_runs VALUES(?,?,?,?)',(snapshot_id,ts,'SUCCESS',json.dumps({'new':len(new),'closed':len(updates['closed'])})));db.commit()
 db.close()
 if tempdir:shutil.rmtree(tempdir)
 if verbose:print(json.dumps(result,sort_keys=True))
 return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--as-of');p.add_argument('--reuse-existing-data',action='store_true');p.add_argument('--verbose',action='store_true');p.add_argument('--dry-run',action='store_true');a=p.parse_args();r=run(a.as_of,a.dry_run,a.verbose);print('PAPER RESEARCH: SUCCESS');print(f"Snapshot: {r['snapshot_id'].replace('_',' ')}");print(f"New paper trades: {r['newly_created_trades']}");print(f"Open paper trades: {r['open_paper_trades']}");print(f"Closed this cycle: {len(r['closed_trades'])}");print(f"Total closed: {r['total_closed_trades']}");print(f"Updated strategies: {r['updated_strategies']}")
if __name__=='__main__':main()
