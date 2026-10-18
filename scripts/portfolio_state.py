from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
CURRENT=ROOT/'PORTFOLIO_MEMORY/CURRENT/latest_portfolio.json'
INTRADAY=ROOT/'DATASETS/market_intraday_weekly'
CASH_ASSETS={'USD','EUR','USDT','USDC'}
MARK_PRICE_FRESH_HOURS=8.0

def load_current_portfolio(path:Path=CURRENT)->dict:
 try:
  data=json.loads(path.read_text())
  return data if isinstance(data,dict) and isinstance(data.get('holdings'),list) else {}
 except Exception:return {}
def get_holding(asset:str,portfolio:dict|None=None)->dict|None:
 p=portfolio if portfolio is not None else load_current_portfolio();symbol=str(asset).strip().upper()
 return next((x for x in p.get('holdings',[]) if str(x.get('asset')).upper()==symbol),None)
def get_total_visible_usd(portfolio:dict|None=None)->float|None:
 p=portfolio if portfolio is not None else load_current_portfolio();return p.get('visible_total_usd')
def get_portfolio_weight(asset:str,portfolio:dict|None=None)->float|None:
 row=get_holding(asset,portfolio);return (row.get('current_portfolio_weight_pct') if 'current_portfolio_weight_pct' in row else row.get('portfolio_weight_pct')) if row else None
def is_asset_held(asset:str,portfolio:dict|None=None)->bool:
 row=get_holding(asset,portfolio);return bool(row and (row.get('quantity') or 0)>0)
def get_portfolio_concentration(portfolio:dict|None=None)->dict[str,Any]:
 p=portfolio if portfolio is not None else load_current_portfolio();rows=p.get('holdings',[]);live='current_total_market_value_usd' in p;weighted=[(str(x.get('asset')).upper(),float((x.get('current_portfolio_weight_pct') if live else x.get('portfolio_weight_pct')) or 0)) for x in rows];ordered=sorted(weighted,key=lambda x:(-x[1],x[0]));btc=next((w for a,w in weighted if a=='BTC'),0.0);cash=sum(w for a,w in weighted if a in CASH_ASSETS);alt=sum(w for a,w in weighted if a not in CASH_ASSETS|{'BTC'})
 return {'largest_position':ordered[0][0] if ordered else None,'largest_position_pct':ordered[0][1] if ordered else None,'top3_weight_pct':sum(x[1] for x in ordered[:3]),'top5_weight_pct':sum(x[1] for x in ordered[:5]),'btc_weight_pct':btc,'alt_weight_pct':alt,'cash_weight_pct':cash,'holdings_count':len([x for x in rows if (x.get('quantity') or 0)>0])}

def _latest_public_mark(asset:str,as_of:Any=None,intraday_dir:Path=INTRADAY)->tuple[float|None,str|None,float|None]:
 """Return the latest completed public hourly close, timestamp, and age."""
 try:
  frame=pd.read_csv(intraday_dir/f'{asset}USD_1H.csv',usecols=['timestamp','close'])
  frame['timestamp']=pd.to_datetime(frame['timestamp'],utc=True,errors='coerce');frame['close']=pd.to_numeric(frame['close'],errors='coerce');frame=frame.dropna()
  cutoff=pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.now(tz='UTC')
  cutoff=cutoff.tz_localize('UTC') if cutoff.tzinfo is None else cutoff.tz_convert('UTC')
  frame=frame[frame.timestamp<cutoff]
  if frame.empty:return None,None,None
  row=frame.sort_values('timestamp').iloc[-1];age=max(0.0,(cutoff-row.timestamp).total_seconds()/3600)
  return float(row.close),row.timestamp.isoformat(),age
 except Exception:return None,None,None

def mark_to_market(portfolio:dict|None=None,as_of:Any=None,intraday_dir:Path=INTRADAY,prices:dict[str,dict]|None=None)->dict:
 """Build a live valuation view without mutating or persisting the snapshot."""
 source=portfolio if portfolio is not None else load_current_portfolio()
 marked=json.loads(json.dumps(source)) if source else {}
 warnings=list(marked.get('warnings') or []);total=0.0
 for row in marked.get('holdings',[]):
  asset=str(row.get('asset') or '').upper();snapshot_value=row.get('snapshot_usd_value',row.get('usd_value'));snapshot_weight=row.get('snapshot_portfolio_weight_pct',row.get('portfolio_weight_pct'))
  row.update({'snapshot_usd_value':snapshot_value,'snapshot_portfolio_weight_pct':snapshot_weight,'snapshot_displayed_pnl_usd':row.get('snapshot_displayed_pnl_usd',row.get('displayed_pnl_usd')),'snapshot_displayed_pnl_pct':row.get('snapshot_displayed_pnl_pct',row.get('displayed_pnl_pct'))})
  if asset in CASH_ASSETS:
   value=float(snapshot_value or 0);row.update(mark_price=1.0,mark_price_timestamp=None,current_market_value_usd=value,mark_to_market_change_since_snapshot_pct=0.0 if snapshot_value is not None else None);total+=value;continue
  supplied=(prices or {}).get(asset)
  if supplied is not None:price=supplied.get('price');timestamp=supplied.get('timestamp');age=supplied.get('age_hours',0)
  else:price,timestamp,age=_latest_public_mark(asset,as_of,intraday_dir)
  fresh=price is not None and float(price)>0 and age is not None and age<=MARK_PRICE_FRESH_HOURS
  if not fresh:
   row.update(mark_price=None,mark_price_timestamp=timestamp,current_market_value_usd=None,current_portfolio_weight_pct=None,mark_to_market_change_since_snapshot_pct=None);warnings.append(f'MARK_TO_MARKET_PRICE_STALE:{asset}');continue
  value=float(row.get('quantity') or 0)*float(price);change=None if not snapshot_value else (value/float(snapshot_value)-1)*100
  row.update(mark_price=float(price),mark_price_timestamp=timestamp,current_market_value_usd=value,mark_to_market_change_since_snapshot_pct=change);total+=value
 for row in marked.get('holdings',[]):
  value=row.get('current_market_value_usd');row['current_portfolio_weight_pct']=value/total*100 if value is not None and total else None
 marked['current_total_market_value_usd']=total if marked.get('holdings') else None;marked['mark_to_market_as_of']=str(as_of) if as_of is not None else pd.Timestamp.now(tz='UTC').isoformat();marked['warnings']=sorted(set(warnings))
 marked['concentration']=get_portfolio_concentration(marked)
 return marked
