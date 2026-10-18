from __future__ import annotations
from pathlib import Path
import pandas as pd
from weekly_consolidation_common import ROOT
ALIASES={'BTC':'XBTUSD'}
def normalize_asset(asset:str)->str:
 a=str(asset).strip().upper();return 'BTC' if a in {'XBT','XXBT'} else a
def resolve_kraken_pair(asset:str,universe_path:Path|None=None)->str|None:
 a=normalize_asset(asset)
 if a in ALIASES:return ALIASES[a]
 path=universe_path or ROOT/'DATASETS/universe/weekly_consolidation_universe.csv'
 try:
  frame=pd.read_csv(path);row=frame[frame['symbol'].astype(str).str.upper()==a]
  if len(row) and pd.notna(row.iloc[0].get('selected_kraken_pair')):return str(row.iloc[0]['selected_kraken_pair'])
 except Exception:pass
 return f'{a}USD' if a else None
