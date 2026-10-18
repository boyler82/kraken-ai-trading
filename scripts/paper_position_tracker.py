from __future__ import annotations
import json,sqlite3,uuid
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1];DB_PATH=ROOT/'PAPER_RESEARCH/paper_strategy_research.sqlite'
SCHEMA='''
CREATE TABLE IF NOT EXISTS paper_signals(signal_id TEXT PRIMARY KEY,timestamp TEXT,asset TEXT,pair TEXT,strategy_name TEXT,strategy_variant TEXT,setup_episode_id TEXT,source_modules TEXT,source_packet_date TEXT,source_snapshot_id TEXT,entry_reference_price REAL,stop_price REAL,target_price REAL,max_hold_hours REAL,setup_score REAL,confidence REAL,status TEXT, UNIQUE(setup_episode_id,strategy_variant));
CREATE TABLE IF NOT EXISTS paper_trades(trade_id TEXT PRIMARY KEY,signal_id TEXT UNIQUE,asset TEXT,strategy_name TEXT,strategy_variant TEXT,source_modules TEXT,entry_timestamp TEXT,entry_price REAL,exit_timestamp TEXT,exit_price REAL,stop_price REAL,target_price REAL,max_hold_hours REAL,exit_reason TEXT,gross_return_pct REAL,estimated_cost_pct REAL,net_return_pct REAL,holding_hours REAL,mfe_pct REAL DEFAULT 0,mae_pct REAL DEFAULT 0,result_class TEXT,status TEXT,notional_usd REAL,benchmark_entry_price REAL,benchmark_exit_price REAL,benchmark_return_pct REAL,relative_return_vs_btc_pct REAL);
CREATE TABLE IF NOT EXISTS paper_trade_events(id INTEGER PRIMARY KEY AUTOINCREMENT,trade_id TEXT,timestamp TEXT,event_type TEXT,price REAL,details_json TEXT);
CREATE TABLE IF NOT EXISTS paper_strategy_stats(strategy_name TEXT,strategy_variant TEXT,sample_size INTEGER,wins INTEGER,losses INTEGER,win_rate REAL,average_win_pct REAL,average_loss_pct REAL,payoff_ratio REAL,expected_value_pct REAL,break_even_win_rate REAL,profit_factor REAL,maximum_drawdown_pct REAL,longest_loss_streak INTEGER,median_holding_hours REAL,average_mfe_pct REAL,average_mae_pct REAL,sample_quality TEXT,status TEXT,updated_at TEXT,PRIMARY KEY(strategy_name,strategy_variant));
CREATE TABLE IF NOT EXISTS paper_strategy_variants(strategy_name TEXT,strategy_variant TEXT,config_json TEXT,PRIMARY KEY(strategy_name,strategy_variant));
CREATE TABLE IF NOT EXISTS paper_snapshot_runs(snapshot_id TEXT PRIMARY KEY,timestamp TEXT,status TEXT,details_json TEXT);
CREATE TABLE IF NOT EXISTS paper_module_combinations(module_combination TEXT PRIMARY KEY,sample_size INTEGER,expected_value_pct REAL,profit_factor REAL,updated_at TEXT);
CREATE TABLE IF NOT EXISTS paper_setup_episodes(setup_identity TEXT PRIMARY KEY,setup_episode_id TEXT,active INTEGER,first_eligible_timestamp TEXT,last_eligible_timestamp TEXT);
'''
def connect(path:Path=DB_PATH)->sqlite3.Connection:
 path.parent.mkdir(parents=True,exist_ok=True);db=sqlite3.connect(path);db.row_factory=sqlite3.Row;db.executescript(SCHEMA);cols={r[1] for r in db.execute('PRAGMA table_info(paper_trades)')}
 for name in ('benchmark_entry_price','benchmark_exit_price','benchmark_return_pct','relative_return_vs_btc_pct'):
  if name not in cols:db.execute(f'ALTER TABLE paper_trades ADD COLUMN {name} REAL')
 stats_cols={r[1] for r in db.execute('PRAGMA table_info(paper_strategy_stats)')}
 for name in ('variant_trade_count','unique_setup_episode_count','unique_asset_episode_count'):
  if name not in stats_cols:db.execute(f'ALTER TABLE paper_strategy_stats ADD COLUMN {name} INTEGER DEFAULT 0')
 return db
def existing_entries(db)->set[tuple[str,str]]:return {(r['setup_episode_id'],r['strategy_variant']) for r in db.execute('SELECT setup_episode_id,strategy_variant FROM paper_signals')}
def open_decisions(db,decisions:list[dict],snapshot_id:str)->list[str]:
 ids=[]
 for d in decisions:
  tid='PT-'+d['signal_id'];ts=d.get('first_eligible_timestamp') or d.get('source_timestamp')
  try:
   db.execute('INSERT INTO paper_signals VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(d['signal_id'],ts,d['asset'],d.get('pair'),d['strategy_name'],d['strategy_variant'],d['setup_episode_id'],json.dumps(d['source_modules']),d.get('source_packet_date'),snapshot_id,d['entry_price'],d['stop_price'],d['target_price'],d['max_hold_hours'],d.get('setup_score'),d.get('confidence'),'OPEN'))
   db.execute('INSERT INTO paper_trades(trade_id,signal_id,asset,strategy_name,strategy_variant,source_modules,entry_timestamp,entry_price,stop_price,target_price,max_hold_hours,estimated_cost_pct,status,notional_usd,benchmark_entry_price) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,d['signal_id'],d['asset'],d['strategy_name'],d['strategy_variant'],json.dumps(d['source_modules']),ts,d['entry_price'],d['stop_price'],d['target_price'],d['max_hold_hours'],d['estimated_cost_pct'],'OPEN',d['notional_usd'],(d.get('metadata') or {}).get('btc_price')))
   db.execute('INSERT INTO paper_trade_events(trade_id,timestamp,event_type,price,details_json) VALUES(?,?,?,?,?)',(tid,ts,'OPENED',d['entry_price'],json.dumps({'snapshot_id':snapshot_id})));ids.append(tid)
  except sqlite3.IntegrityError:pass
 db.commit();return ids
def _hours(a:str,b:str)->float:return max(0,(datetime.fromisoformat(b.replace('Z','+00:00'))-datetime.fromisoformat(a.replace('Z','+00:00'))).total_seconds()/3600)
def update_open_trades(db,market:dict[str,dict],timestamp:str)->dict[str,list]:
 updated=[];closed=[];gaps=[]
 for t in db.execute("SELECT * FROM paper_trades WHERE status='OPEN'").fetchall():
  x=market.get(t['asset'])
  if not x or x.get('price') is None:gaps.append(t['trade_id']);db.execute('INSERT INTO paper_trade_events(trade_id,timestamp,event_type,details_json) VALUES(?,?,?,?)',(t['trade_id'],timestamp,'DATA_GAP','{}'));continue
  price=float(x['price']);high=float(x.get('high',price));low=float(x.get('low',price));hours=_hours(t['entry_timestamp'],timestamp);mfe=max(t['mfe_pct'] or 0,(high/t['entry_price']-1)*100);mae=min(t['mae_pct'] or 0,(low/t['entry_price']-1)*100);reason=None;exit_price=None;details={}
  if low<=t['stop_price'] and high>=t['target_price']:reason='STOP_FIRST_UNCERTAIN_INTRABAR';exit_price=t['stop_price'];details={'flag':'INTRABAR_SEQUENCE_UNKNOWN'}
  elif low<=t['stop_price']:reason='STOP_HIT';exit_price=t['stop_price']
  elif high>=t['target_price']:reason='MIDPOINT_REACHED' if t['strategy_variant']=='RANGE_MIDPOINT' else 'RANGE_HIGH_REACHED' if t['strategy_variant']=='RANGE_HIGH' else 'TARGET_HIT';exit_price=t['target_price']
  elif x.get('structure_valid') is False:reason='STRUCTURE_INVALIDATED';exit_price=price
  elif hours>=t['max_hold_hours']:reason='TIME_EXIT';exit_price=price
  if reason:
   gross=(exit_price/t['entry_price']-1)*100;net=gross-t['estimated_cost_pct'];result='WIN' if net>0 else 'LOSS' if net<0 else 'FLAT';btc=(market.get('BTC') or {}).get('price');bench=(float(btc)/t['benchmark_entry_price']-1)*100 if btc is not None and t['benchmark_entry_price'] else None;relative=None if bench is None else gross-bench;db.execute("UPDATE paper_trades SET exit_timestamp=?,exit_price=?,exit_reason=?,gross_return_pct=?,net_return_pct=?,holding_hours=?,mfe_pct=?,mae_pct=?,result_class=?,status='CLOSED',benchmark_exit_price=?,benchmark_return_pct=?,relative_return_vs_btc_pct=? WHERE trade_id=?",(timestamp,exit_price,reason,gross,net,hours,mfe,mae,result,btc,bench,relative,t['trade_id']));db.execute("UPDATE paper_signals SET status='CLOSED' WHERE signal_id=?",(t['signal_id'],));db.execute('INSERT INTO paper_trade_events(trade_id,timestamp,event_type,price,details_json) VALUES(?,?,?,?,?)',(t['trade_id'],timestamp,reason,exit_price,json.dumps(details)));closed.append(t['trade_id'])
  else:db.execute('UPDATE paper_trades SET mfe_pct=?,mae_pct=? WHERE trade_id=?',(mfe,mae,t['trade_id']));updated.append(t['trade_id'])
 db.commit();return {'updated':updated,'closed':closed,'data_gaps':gaps}
