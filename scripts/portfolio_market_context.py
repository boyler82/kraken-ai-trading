from __future__ import annotations
from pathlib import Path
import pandas as pd
from asset_pair_resolver import resolve_kraken_pair
from daily_momentum_breakout_radar import calculate_features
from btc_rotation_engine import rotation_features
from portfolio_state import load_current_portfolio
from weekly_consolidation_common import ROOT,INTRADAY_DIR,freshness,utc_timestamp

def _csv(path):
 try:return pd.read_csv(path)
 except Exception:return pd.DataFrame()
def build(as_of=None)->dict:
 cutoff=utc_timestamp(as_of);portfolio=load_current_portfolio();held=[x for x in portfolio.get('holdings',[]) if x.get('asset') not in {'USD','EUR','USDT','USDC'}];btc=_csv(INTRADAY_DIR/'BTCUSD_1H.csv');btc['timestamp']=pd.to_datetime(btc.get('timestamp'),utc=True) if len(btc) else None
 con=_csv(ROOT/'DAILY_REPORTS/DAILY_CONSOLIDATION/latest_daily_consolidation_scan.csv');conmap={str(x.asset):x.where(pd.notna(x),None).to_dict() for _,x in con.iterrows()} if len(con) else {};rs=_csv(ROOT/'DAILY_REPORTS/RELATIVE_STRENGTH/latest_relative_strength.csv');rsmap={str(x.asset):x.where(pd.notna(x),None).to_dict() for _,x in rs.iterrows()} if len(rs) else {};contexts={};warnings=[]
 for holding in held:
  asset=str(holding['asset']);path=INTRADAY_DIR/f'{asset}USD_1H.csv';bars=_csv(path)
  try:
   bars['timestamp']=pd.to_datetime(bars['timestamp'],utc=True);bars=bars[bars.timestamp<cutoff];age,fresh=freshness(bars.iloc[-1].timestamp,cutoff)
   momentum=calculate_features(bars,btc,conmap.get(asset),cutoff);relative=rotation_features(bars,btc) if asset!='BTC' else {};existing_rs=rsmap.get(asset,{})
   contexts[asset]={'asset':asset,'kraken_pair':resolve_kraken_pair(asset),'current_price':momentum.get('current_price'),'source_timestamp':momentum.get('latest_completed_candle_timestamp'),'freshness':fresh,'data_age_hours':age,'spread':None,'liquidity':float((pd.to_numeric(bars.close)*pd.to_numeric(bars.volume)).tail(24).sum()),'momentum':momentum,'relative_strength':{'return_vs_btc_24h_pct':relative.get('relative_return_24h_pct'),'return_vs_btc_48h_pct':relative.get('relative_return_48h_pct'),'return_vs_btc_7d_pct':relative.get('relative_return_7d_pct'),'return_vs_btc_14d_pct':relative.get('relative_return_14d_pct'),'percentile_rank':existing_rs.get('percentile_rank'),'relative_trend':existing_rs.get('classification')},'consolidation':conmap.get(asset,{})}
   if fresh=='STALE':warnings.append(f'HELD_ASSET_MARKET_DATA_STALE:{asset}')
  except Exception:warnings.append(f'HELD_ASSET_MARKET_CONTEXT_MISSING:{asset}')
 total=sum(float(x.get('portfolio_weight_pct') or 0) for x in held);fresh_weight=sum(float(x.get('portfolio_weight_pct') or 0) for x in held if contexts.get(str(x['asset']),{}).get('freshness')=='FRESH');stale=[a for a,x in contexts.items() if x['freshness']!='FRESH'];missing=[str(x['asset']) for x in held if str(x['asset']) not in contexts]
 return {'contexts':contexts,'warnings':warnings,'coverage':{'held_asset_count':len(held),'held_assets_with_fresh_market_context':sum(x.get('freshness')=='FRESH' for x in contexts.values()),'held_assets_with_stale_context':stale,'held_assets_missing_context':missing,'portfolio_weight_with_fresh_market_context_pct':round(min(100,fresh_weight),2)}}
