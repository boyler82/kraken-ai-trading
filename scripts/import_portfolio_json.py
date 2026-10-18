from __future__ import annotations
import argparse,hashlib,json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from portfolio_state import CURRENT,ROOT,get_portfolio_concentration

INPUT=ROOT/'PORTFOLIO_MEMORY/INPUT';HISTORY=ROOT/'PORTFOLIO_MEMORY/HISTORY';DB=ROOT/'PORTFOLIO_MEMORY/portfolio_memory.sqlite';SUPPORTED={'1.0'}
def read(path:Path)->dict:
 try:return json.loads(path.read_text())
 except Exception:return {}
def number(v):
 if v is None:return None
 try:return float(v)
 except (TypeError,ValueError):return None
def parsed_time(v):
 try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(timezone.utc)
 except Exception:return None
def normalize(data:dict)->tuple[dict,list[str],bool]:
 errors=[];warnings=list(data.get('warnings') or []);holdings=data.get('holdings')
 if str(data.get('schema_version')) not in SUPPORTED:errors.append('UNSUPPORTED_SCHEMA_VERSION')
 if not parsed_time(data.get('captured_at')):errors.append('INVALID_CAPTURED_AT')
 if not isinstance(holdings,list):return {},sorted(set(errors+['HOLDINGS_NOT_LIST'])),False
 merged={}
 for source in holdings:
  if not isinstance(source,dict):errors.append('INVALID_HOLDING_ROW');continue
  row={k:source.get(k) for k in ('asset','quantity','portfolio_weight_pct','usd_value','displayed_pnl_usd','displayed_pnl_pct')};row['asset']=str(row.get('asset') or '').strip().upper()
  if not row['asset']:errors.append('EMPTY_ASSET');continue
  for field in ('quantity','portfolio_weight_pct','usd_value'):
   value=number(row.get(field))
   if row.get(field) is not None and value is None:errors.append(f'INVALID_{field.upper()}_{row["asset"]}')
   if value is not None and value<0:errors.append(f'NEGATIVE_{field.upper()}_{row["asset"]}')
  if row['asset'] in merged:
   if merged[row['asset']]!=row:errors.append(f'DUPLICATE_ASSET_{row["asset"]}')
  else:merged[row['asset']]=row
 total=number(data.get('visible_total_usd'))
 if data.get('visible_total_usd') is not None and (total is None or total<0):errors.append('INVALID_VISIBLE_TOTAL_USD')
 weight=sum(number(x.get('portfolio_weight_pct')) or 0 for x in merged.values())
 if weight>101:errors.append('PORTFOLIO_WEIGHT_SUM_INVALID')
 if weight<80:warnings.append('PORTFOLIO_SNAPSHOT_INCOMPLETE')
 for row in merged.values():row.update(snapshot_usd_value=row.get('usd_value'),snapshot_portfolio_weight_pct=row.get('portfolio_weight_pct'),snapshot_displayed_pnl_usd=row.get('displayed_pnl_usd'),snapshot_displayed_pnl_pct=row.get('displayed_pnl_pct'))
 normalized={'schema_version':'1.0','captured_at':data.get('captured_at'),'source':data.get('source'),'base_currency':str(data.get('base_currency') or 'USD').upper(),'snapshot_completeness':data.get('snapshot_completeness'),'holdings':list(merged.values()),'visible_total_usd':data.get('visible_total_usd'),'visible_weight_sum':weight,'open_orders_visible':data.get('open_orders_visible'),'warnings':sorted(set(warnings))}
 concentration=get_portfolio_concentration(normalized)
 if (concentration['largest_position_pct'] or 0)>=35:normalized['warnings'].append('SINGLE_ASSET_CONCENTRATION_HIGH')
 if concentration['top3_weight_pct']>=70:normalized['warnings'].append('TOP3_CONCENTRATION_HIGH')
 normalized['warnings']=sorted(set(normalized['warnings']+['COST_BASIS_NOT_RECONSTRUCTED']))
 return normalized,sorted(set(errors)),not errors
def canonical_bytes(data:dict)->bytes:return (json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()
def connect(path:Path=DB):
 path.parent.mkdir(parents=True,exist_ok=True);db=sqlite3.connect(path);db.executescript('''CREATE TABLE IF NOT EXISTS portfolio_snapshots(snapshot_id TEXT PRIMARY KEY,captured_at TEXT,source TEXT,base_currency TEXT,snapshot_completeness TEXT,visible_total_usd REAL,visible_weight_sum REAL,open_orders_visible INTEGER,source_hash TEXT UNIQUE,imported_at TEXT);CREATE TABLE IF NOT EXISTS portfolio_holdings(snapshot_id TEXT,asset TEXT,quantity REAL,usd_value REAL,portfolio_weight_pct REAL,displayed_pnl_usd REAL,displayed_pnl_pct REAL,PRIMARY KEY(snapshot_id,asset));CREATE TABLE IF NOT EXISTS portfolio_warnings(snapshot_id TEXT,warning TEXT,PRIMARY KEY(snapshot_id,warning));''');return db
def import_snapshot(data:dict,db_path:Path=DB,current_path:Path=CURRENT,history:Path=HISTORY)->dict:
 normalized,errors,valid=normalize(data)
 if not valid:return {'status':'INVALID_PORTFOLIO_SNAPSHOT','errors':errors,'warnings':normalized.get('warnings',[]) if normalized else []}
 encoded=canonical_bytes(normalized);source_hash=hashlib.sha256(encoded).hexdigest();snapshot_id=source_hash[:24];db=connect(db_path)
 if db.execute('SELECT 1 FROM portfolio_snapshots WHERE source_hash=?',(source_hash,)).fetchone():db.close();return {'status':'DUPLICATE_PORTFOLIO_SNAPSHOT_SKIPPED','snapshot_id':snapshot_id,'source_hash':source_hash,'portfolio':normalized}
 now=datetime.now(timezone.utc).isoformat();db.execute('INSERT INTO portfolio_snapshots VALUES(?,?,?,?,?,?,?,?,?,?)',(snapshot_id,normalized['captured_at'],normalized['source'],normalized['base_currency'],normalized['snapshot_completeness'],normalized['visible_total_usd'],normalized['visible_weight_sum'],normalized['open_orders_visible'],source_hash,now))
 for x in normalized['holdings']:db.execute('INSERT INTO portfolio_holdings VALUES(?,?,?,?,?,?,?)',(snapshot_id,x['asset'],x['quantity'],x['usd_value'],x['portfolio_weight_pct'],x['displayed_pnl_usd'],x['displayed_pnl_pct']))
 for warning in normalized['warnings']:db.execute('INSERT INTO portfolio_warnings VALUES(?,?)',(snapshot_id,warning))
 db.commit();db.close();history.mkdir(parents=True,exist_ok=True);archive=history/f"{normalized['captured_at'][:10]}_{snapshot_id}.json";archive.write_bytes(encoded)
 current=read(current_path);current_time=parsed_time(current.get('captured_at'));new_time=parsed_time(normalized['captured_at']);promoted=not current_time or (new_time and new_time>=current_time)
 if promoted:current_path.parent.mkdir(parents=True,exist_ok=True);tmp=current_path.with_suffix('.json.tmp');tmp.write_bytes(encoded);tmp.replace(current_path)
 return {'status':'IMPORTED','snapshot_id':snapshot_id,'source_hash':source_hash,'promoted_to_current':promoted,'history_path':str(archive),'portfolio':normalized}
def run(input_dir:Path=INPUT,**kwargs):
 candidates=[];invalid=[]
 for path in input_dir.glob('*_portfolio_snapshot.json') if input_dir.exists() else []:
  data=read(path);normalized,errors,valid=normalize(data);timestamp=parsed_time(normalized.get('captured_at')) if valid else None
  if valid:candidates.append((timestamp,path,data))
  else:invalid.append({'path':str(path),'errors':errors})
 if not candidates:return {'status':'USING_PREVIOUS_CURRENT','invalid':invalid} if CURRENT.exists() else {'status':'NO_VALID_PORTFOLIO_INPUT','invalid':invalid}
 _,path,data=max(candidates,key=lambda x:x[0]);result=import_snapshot(data,**kwargs);result['input_path']=str(path);result['invalid']=invalid;return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,default=INPUT);a=p.parse_args();result=run(a.input_dir);print(json.dumps({k:v for k,v in result.items() if k!='portfolio'},indent=2));raise SystemExit(0 if result['status'] in {'IMPORTED','DUPLICATE_PORTFOLIO_SNAPSHOT_SKIPPED','USING_PREVIOUS_CURRENT'} else 1)
if __name__=='__main__':main()
