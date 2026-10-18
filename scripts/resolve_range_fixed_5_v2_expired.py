from __future__ import annotations

import argparse,hashlib,json,sqlite3
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import Any
import pandas as pd

from range_fixed_5_v2_monitor import Candidate,bar_candidate,monitor_observation,structure_candidate
from range_fixed_5_v2_storage import DB_PATH,active_manifest,initialize_database,load_config,load_phase4_config,sha256_json
from weekly_consolidation_common import ROOT,atomic_write

MARKET_DIR=ROOT/'DATASETS/market_intraday_weekly';OUT=ROOT/'RESEARCH_REPORTS/range_fixed_5_v2_expired_preview_latest.json'
PRIORITY={'STOP_HIT':0,'TARGET_HIT':1,'STRUCTURE_INVALIDATION':2,'TIME_EXIT':3}

def utc(value:Any)->datetime:
 d=value if isinstance(value,datetime) else datetime.fromisoformat(str(value).replace('Z','+00:00'))
 if d.tzinfo is None:raise ValueError('timestamp must be timezone-aware')
 return d.astimezone(timezone.utc)
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_frozen(db_path:Path=DB_PATH)->dict:
 cfg=load_config();phase=load_phase4_config()
 db=sqlite3.connect(f'file:{db_path.resolve()}?mode=ro&immutable=1',uri=True);db.row_factory=sqlite3.Row
 try:
  manifest=active_manifest(db)
  if not manifest:raise ValueError('active frozen V2 manifest unavailable')
  base=sha256_json(cfg)
  if manifest['config_sha256']!=base:raise ValueError('FROZEN_HASH_MISMATCH: base config')
  extension=db.execute("select base_config_sha256,extension_config_sha256 from v2_strategy_extensions where extension_id='RANGE_FIXED_5_FORWARD_V2_PHASE4_ENTRY_V1'").fetchone()
  if not extension or extension['base_config_sha256']!=base or extension['extension_config_sha256']!=sha256_json(phase):raise ValueError('FROZEN_HASH_MISMATCH: Phase-4 extension')
  return {'manifest_id':manifest['manifest_id'],'base_config_sha256':base,'stored_config_sha256':manifest['config_sha256'],'phase4_config_sha256':sha256_json(phase),'activation_timestamp':manifest['official_cohort_start_timestamp']}
 finally:db.close()

def ensure_monitor_schema(db_path:Path=DB_PATH)->list[str]:
 db=sqlite3.connect(db_path);db.row_factory=sqlite3.Row
 try:
  columns={x[1] for x in db.execute('pragma table_info(v2_completed_outcomes)')};missing=[x for x in ('total_fee_pct','total_slippage_pct') if x not in columns];active=active_manifest(db);manifest=json.loads(active['manifest_json']) if active else None
 finally:db.close()
 if missing:
  if not manifest:raise ValueError('active frozen manifest unavailable for schema migration')
  initialize_database(db_path,load_config(),manifest)
 verify_frozen(db_path);return missing

def open_entries(db_path:Path=DB_PATH)->list[dict]:
 db=sqlite3.connect(f'file:{db_path.resolve()}?mode=ro&immutable=1',uri=True);db.row_factory=sqlite3.Row
 try:return [dict(x) for x in db.execute('''select o.*,d.range_low,d.range_high,d.market_data_cutoff,d.source_candle_open_timestamp,d.source_candle_completion_timestamp,e.spread_pct,e.canonical_payload_json from v2_open_observations o join v2_decision_snapshots d using(snapshot_id) join v2_entry_observations e using(signal_id) order by o.entry_timestamp,o.asset''')]
 finally:db.close()

def load_hourly(entry:dict,market_dir:Path=MARKET_DIR)->tuple[pd.DataFrame,dict]:
 path=market_dir/f"{entry['kraken_pair']}_1H.csv"
 if not path.exists():return pd.DataFrame(),{'status':'INSUFFICIENT_PUBLIC_MARKET_EVIDENCE','missing_interval':[entry['entry_timestamp'],entry['expiry_timestamp']],'reason':'PUBLIC_HOURLY_FILE_MISSING','source_path':str(path)}
 raw=pd.read_csv(path);required={'timestamp','open','high','low','close','volume'}
 if not required.issubset(raw.columns):return pd.DataFrame(),{'status':'INSUFFICIENT_PUBLIC_MARKET_EVIDENCE','missing_interval':[entry['entry_timestamp'],entry['expiry_timestamp']],'reason':'PUBLIC_HOURLY_SCHEMA_INVALID','source_path':str(path)}
 raw['timestamp']=pd.to_datetime(raw.timestamp,utc=True,errors='coerce');raw=raw.dropna(subset=['timestamp']).sort_values('timestamp').drop_duplicates('timestamp',keep=False)
 for c in ('open','high','low','close','volume'):raw[c]=pd.to_numeric(raw[c],errors='coerce')
 raw=raw.dropna(subset=['open','high','low','close','volume']);return raw,{'source_path':str(path),'source_sha256':sha(path)}

def four_hour(frame:pd.DataFrame,expiry:datetime)->list[dict]:
 f=frame[frame.timestamp+pd.Timedelta(hours=1)<=pd.Timestamp(expiry)].set_index('timestamp')
 grouped=f.resample('4h',origin='epoch').agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),volume=('volume','sum'),count=('close','count')).dropna()
 grouped=grouped[grouped['count']==4].reset_index();return [{k:(v.isoformat() if k=='timestamp' else float(v)) for k,v in row.items() if k!='count'} for row in grouped.to_dict('records')]

def preview_entry(entry:dict,market_dir:Path=MARKET_DIR)->dict:
 start,expiry=utc(entry['entry_timestamp']),utc(entry['expiry_timestamp']);frame,coverage=load_hourly(entry,market_dir)
 base={'asset':entry['asset'],'signal_id':entry['signal_id'],'entry_timestamp':start.isoformat(),'entry_price':entry['entry_reference_price'],'target':entry['target_price'],'stop':entry['stop_price'],'expiry':expiry.isoformat(),'spread_pct_at_entry':entry['spread_pct'],'fee_semantics':{'entry_fee_pct':.2,'exit_fee_pct':.2},'slippage_semantics':{'entry_slippage_pct':0.0,'exit_slippage_pct':0.0,'status':'NO_SEPARATE_SLIPPAGE_ESTIMATE; ENTRY_REFERENCE_IS_ACCEPTED_BEST_ASK'},'exit_price_semantics':None,'first_target_hit_evidence':None,'first_stop_hit_evidence':None,'ambiguity_status':'NONE','proposed_exit_reason':None,'proposed_exit_timestamp':None,'proposed_exit_price':None,'data_coverage':coverage}
 if frame.empty:return base
 overlap=frame[frame.timestamp==pd.Timestamp(start).floor('h')]
 if overlap.empty:
  base['data_coverage'].update(status='INSUFFICIENT_PUBLIC_MARKET_EVIDENCE',missing_interval=[pd.Timestamp(start).floor('h').isoformat(),pd.Timestamp(start).ceil('h').isoformat()],reason='ENTRY_OVERLAP_BAR_MISSING');return base
 overlap=overlap.iloc[0]
 if overlap.high>=entry['target_price'] or overlap.low<=entry['stop_price']:
  base['data_coverage'].update(status='INSUFFICIENT_PUBLIC_MARKET_EVIDENCE',missing_interval=[start.isoformat(),pd.Timestamp(start).ceil('h').isoformat()],reason='ENTRY_OVERLAP_BOUNDARY_TOUCH_REQUIRES_EXACT_PUBLIC_TRADES');return base
 complete=frame[(frame.timestamp>=pd.Timestamp(start).ceil('h'))&(frame.timestamp+pd.Timedelta(hours=1)<=pd.Timestamp(expiry))]
 expected=pd.date_range(pd.Timestamp(start).ceil('h'),pd.Timestamp(expiry).floor('h')-pd.Timedelta(hours=1),freq='1h',tz='UTC')
 missing=expected.difference(pd.DatetimeIndex(complete.timestamp))
 if len(missing):
  base['data_coverage'].update(status='INSUFFICIENT_PUBLIC_MARKET_EVIDENCE',missing_interval=[missing[0].isoformat(),(missing[0]+pd.Timedelta(hours=1)).isoformat()],reason='HOURLY_COVERAGE_GAP');return base
 bars=[{'open_timestamp':r.timestamp.isoformat(),'close_timestamp':(r.timestamp+pd.Timedelta(hours=1)).isoformat(),'open':float(r.open),'high':float(r.high),'low':float(r.low),'close':float(r.close),'volume':float(r.volume)} for r in complete.itertuples()]
 class Entry(dict):
  __getattr__=dict.__getitem__
 e=Entry(entry);boundary=bar_candidate(e,bars);structure=structure_candidate(e,four_hour(frame,expiry));candidates=[x for x in (boundary,structure) if x]
 winner=min(candidates,key=lambda x:(x.timestamp,PRIORITY[x.outcome])) if candidates else None
 target=next((x for x in candidates if x.outcome=='TARGET_HIT'),None);stop=next((x for x in candidates if x.outcome=='STOP_HIT'),None)
 base['first_target_hit_evidence']=None if not target else {'timestamp':target.timestamp.isoformat(),'source':target.payload['source']}
 base['first_stop_hit_evidence']=None if not stop else {'timestamp':stop.timestamp.isoformat(),'source':stop.payload['source']}
 if boundary and boundary.payload.get('ambiguity_flag'):base['ambiguity_status']=boundary.payload['ambiguity_flag']+' / '+boundary.payload['resolution_policy']
 if winner:
  base.update(proposed_exit_reason=winner.outcome,proposed_exit_timestamp=winner.timestamp.isoformat(),proposed_exit_price=winner.exit_price,exit_price_semantics=winner.payload['resolution_policy'])
  base['data_coverage'].update(status='COMPLETE_THROUGH_TERMINAL_EVIDENCE',verified_from=start.isoformat(),verified_through=winner.timestamp.isoformat(),missing_interval=None)
 else:base['data_coverage'].update(status='INSUFFICIENT_PUBLIC_MARKET_EVIDENCE',missing_interval=[expiry.isoformat(),'FIRST_VALID_PUBLIC_BEST_BID_AFTER_EXPIRY'],reason='HISTORICAL_EXPIRY_BID_UNAVAILABLE')
 base['_evidence']={'bars':bars,'completed_4h':four_hour(frame,expiry)}
 return base

def preview(db_path:Path=DB_PATH,market_dir:Path=MARKET_DIR)->dict:
 frozen=verify_frozen(db_path);rows=[preview_entry(x,market_dir) for x in open_entries(db_path)]
 public=[]
 for r in rows:
  clean={k:v for k,v in r.items() if k!='_evidence'};public.append(clean)
 result={'schema_version':'1.0.0','mode':'READ_ONLY_PREVIEW','frozen_verification':frozen,'observations':public,'observation_count':len(public),'ready_count':sum(x['data_coverage']['status']=='COMPLETE_THROUGH_TERMINAL_EVIDENCE' for x in public),'unresolved_count':sum(x['data_coverage']['status']!='COMPLETE_THROUGH_TERMINAL_EVIDENCE' for x in public),'independent_signal_clusters':len({x['market_data_cutoff'] for x in open_entries(db_path)}),'trading_capability':'DISABLED'}
 result['preview_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest();return result

def execute(db_path:Path=DB_PATH,market_dir:Path=MARKET_DIR)->dict:
 first,second=preview(db_path,market_dir),preview(db_path,market_dir)
 if first!=second:raise RuntimeError('NONDETERMINISTIC_PREVIEW_ABORT')
 if first['unresolved_count']:raise RuntimeError('INSUFFICIENT_PUBLIC_MARKET_EVIDENCE_ABORT')
 migrated_columns=ensure_monitor_schema(db_path);internal=[preview_entry(x,market_dir) for x in open_entries(db_path)];results=[]
 for row in internal:
  evidence=row['_evidence'];results.append({'asset':row['asset'],**monitor_observation(db_path,row['signal_id'],bars=evidence['bars'],completed_4h=evidence['completed_4h'],coverage_complete=True,entry_slippage_pct=0.0,exit_slippage_pct=0.0)})
 return {'status':'OFFICIAL_MONITOR_COMPLETE','preview_sha256':first['preview_sha256'],'schema_columns_added':migrated_columns,'results':results,'trading_capability':'DISABLED'}

def main()->None:
 p=argparse.ArgumentParser();p.add_argument('command',choices=('preview','execute'));p.add_argument('--db',type=Path,default=DB_PATH);p.add_argument('--market-dir',type=Path,default=MARKET_DIR);a=p.parse_args()
 if a.command=='preview':result=preview(a.db,a.market_dir);atomic_write(OUT,json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n',backup=False)
 else:result=execute(a.db,a.market_dir)
 print(json.dumps(result,indent=2,sort_keys=True,allow_nan=False))

if __name__=='__main__':main()
