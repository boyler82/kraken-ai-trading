from __future__ import annotations
import argparse
from pathlib import Path
from typing import Any
import pandas as pd
from consolidation_range_engine import BTC_OPERATIONAL_PATH,_read_operational_15m
from portfolio_state import load_current_portfolio
from asset_pair_resolver import resolve_kraken_pair
from weekly_consolidation_common import CHECKPOINT_DIR,INTRADAY_DIR,atomic_write,get_json,utc_timestamp,validate_hourly,write_json
from weekly_consolidation_universe import KRAKEN_PAIRS_URL,map_pair,parse_kraken_pairs
from weekly_intraday_market_backfill import KRAKEN_OHLC_URL,merge_incremental,parse_kraken_ohlc

FIAT={'USD','EUR','USDT','USDC'}
def held_crypto_assets(portfolio:dict|None=None)->list[str]:
 p=portfolio if portfolio is not None else load_current_portfolio();return sorted({str(x.get('asset')).upper() for x in p.get('holdings',[]) if str(x.get('asset')).upper() not in FIAT and (x.get('quantity') or 0)>0})
def canonical_path(asset:str)->Path:return INTRADAY_DIR/f'{asset}USD_1H.csv'
def _btc_hourly(as_of:Any)->pd.DataFrame:
 raw=_read_operational_15m(BTC_OPERATIONAL_PATH).copy();raw['timestamp']=pd.to_datetime(raw['timestamp'],utc=True);raw=raw[raw.timestamp<=utc_timestamp(as_of)]
 hourly=raw.set_index('timestamp').resample('1h',label='left',closed='left').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna().reset_index();hourly['vwap']=hourly['close'];hourly['trades']=0;return hourly[['timestamp','open','high','low','close','vwap','volume','trades']]
def ensure_asset(asset:str,as_of:Any=None,no_network:bool=False,pairs:list[dict]|None=None)->dict:
 asset=asset.upper();path=canonical_path(asset);existing=pd.read_csv(path) if path.exists() else pd.DataFrame()
 try:
  if asset=='BTC' and BTC_OPERATIONAL_PATH.exists():
   incoming=_btc_hourly(as_of);source='BTC_OPERATIONAL_15M_RESAMPLED'
   if not no_network:
    mapping=map_pair(asset,pairs or parse_kraken_pairs(get_json(KRAKEN_PAIRS_URL)))
    since=int(pd.to_datetime(incoming.iloc[-1]['timestamp'],utc=True).timestamp()) if not incoming.empty else None
    public=parse_kraken_ohlc(get_json(KRAKEN_OHLC_URL,{'pair':mapping['altname'],'interval':60,**({'since':since} if since else {})})) if mapping else pd.DataFrame()
    incoming=pd.concat([incoming,public],ignore_index=True);source='BTC_OPERATIONAL_15M_PLUS_KRAKEN_PUBLIC_OHLC'
  elif no_network:
   if existing.empty:raise FileNotFoundError(f'no cached hourly USD data for held asset {asset}')
   incoming=pd.DataFrame(columns=existing.columns);source='CACHED_KRAKEN_PUBLIC_OHLC'
  else:
   mapping=map_pair(asset,pairs or parse_kraken_pairs(get_json(KRAKEN_PAIRS_URL)))
   if not mapping or mapping.get('quote')!='USD':raise ValueError(f'no active Kraken USD spot pair for {asset} ({resolve_kraken_pair(asset)})')
   since=int(pd.to_datetime(existing.iloc[-1]['timestamp'],utc=True).timestamp()) if not existing.empty else None
   payload=get_json(KRAKEN_OHLC_URL,{'pair':mapping['altname'],'interval':60,**({'since':since} if since else {})});incoming=parse_kraken_ohlc(payload);source=f"KRAKEN_PUBLIC_OHLC:{mapping['altname']}"
  clean,quality=merge_incremental(existing,incoming,as_of);atomic_write(path,clean.to_csv(index=False,date_format='%Y-%m-%dT%H:%M:%SZ'));CHECKPOINT_DIR.mkdir(parents=True,exist_ok=True);write_json(CHECKPOINT_DIR/f'{asset}USD.json',{'asset':asset,'canonical_pair':f'{asset}USD','source':source,'rows':len(clean),'last_completed_timestamp':clean.iloc[-1]['timestamp'].isoformat()})
  return {'asset':asset,'status':'AVAILABLE','path':str(path),'rows':len(clean),'source':source,**quality}
 except Exception as exc:return {'asset':asset,'status':'HELD_ASSET_DATA_INSUFFICIENT','path':str(path),'error':str(exc)}
def run(as_of:Any=None,no_network:bool=False)->dict:
 assets=held_crypto_assets();pairs=None
 if not no_network and any(a!='BTC' and not canonical_path(a).exists() for a in assets):
  try:pairs=parse_kraken_pairs(get_json(KRAKEN_PAIRS_URL))
  except Exception:pairs=[]
 rows=[ensure_asset(asset,as_of,no_network,pairs) for asset in assets];return {'status':'AVAILABLE' if rows else 'PORTFOLIO_CONTEXT_UNAVAILABLE','held_assets':assets,'assets':rows,'warnings':['HELD_ASSET_DATA_INSUFFICIENT'] if any(x['status']!='AVAILABLE' for x in rows) else []}
def main():
 p=argparse.ArgumentParser();p.add_argument('--as-of');p.add_argument('--no-network',action='store_true');a=p.parse_args();result=run(a.as_of,a.no_network);print(f"Held asset data: {sum(x['status']=='AVAILABLE' for x in result['assets'])}/{len(result['assets'])} available");print('\n'.join(f"{x['asset']}: {x['status']}" for x in result['assets']))
if __name__=='__main__':main()
