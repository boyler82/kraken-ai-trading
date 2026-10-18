from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import pandas as pd
from lib.research_module_contract import sanitize
from weekly_consolidation_common import ROOT,atomic_write,sha256,utc_timestamp
STORE=ROOT/"DATASETS/FEATURE_STORE";MOMENTUM=ROOT/"DAILY_REPORTS/MOMENTUM_BREAKOUT/latest_momentum_breakout_radar.csv";CONSOLIDATION=ROOT/"DAILY_REPORTS/DAILY_CONSOLIDATION/latest_daily_consolidation_scan.csv"
def build_feature_store(as_of:Any=None)->tuple[pd.DataFrame,dict[str,Any]]:
    if not MOMENTUM.exists():raise FileNotFoundError(str(MOMENTUM))
    m=pd.read_csv(MOMENTUM);c=pd.read_csv(CONSOLIDATION) if CONSOLIDATION.exists() else pd.DataFrame()
    rename={"kraken_pair":"pair","latest_completed_candle_timestamp":"source_timestamp","freshness_status":"freshness","kraken_24h_quote_volume":"quote_volume","bid_ask_spread_pct":"spread","current_price":"current_price","change_1h_pct":"return_1h","change_4h_pct":"return_4h","change_12h_pct":"return_12h","change_24h_pct":"return_24h","change_48h_pct":"return_48h","change_7d_pct":"return_7d","relative_strength_vs_btc_4h_pct":"btc_relative_return_4h","relative_strength_vs_btc_24h_pct":"btc_relative_return_24h","relative_strength_vs_btc_48h_pct":"btc_relative_return_48h","ema20":"ema20","ema50":"ema50","ema20_slope_pct":"ema20_slope","atr14_pct":"atr14_pct","realized_volatility_pct":"realized_volatility","volume_z_score":"volume_z_score","volume_ratio":"volume_ratio","volatility_expansion_ratio":"volatility_expansion","momentum_stage":"momentum_stage","momentum_breakout_score":"momentum_score"}
    keep=[x for x in rename if x in m.columns]+["asset","market_cap_rank","liquidity_pass","spread_pass","sufficient_history"]
    f=m[keep].rename(columns=rename).copy()
    for column in ("return_14d","return_30d","btc_relative_return_7d","btc_relative_return_14d","btc_relative_return_30d","downside_volatility","sector_category"):
        if column not in f:f[column]=None
    if not c.empty:
        cols=[x for x in ["asset","daily_status","position_pct","range_quality","range_still_valid","risk_flags"] if x in c.columns]
        f=f.merge(c[cols].rename(columns={"daily_status":"consolidation_status","position_pct":"consolidation_position","range_quality":"consolidation_quality","risk_flags":"data_quality_flags"}),on="asset",how="left",validate="one_to_one")
    f=f.sort_values("asset").reset_index(drop=True);STORE.mkdir(parents=True,exist_ok=True);csv=STORE/"latest_market_features.csv";atomic_write(csv,f.to_csv(index=False))
    parquet=STORE/"latest_market_features.parquet";parquet_status="OK"
    try:f.to_parquet(parquet,index=False)
    except Exception as exc:parquet_status=f"UNAVAILABLE: {exc}";atomic_write(parquet,json.dumps({"format":"parquet_unavailable","csv_fallback":str(csv)})+"\n")
    manifest={"generated_at_utc":utc_timestamp(as_of).isoformat(),"rows":len(f),"columns":list(f.columns),"synchronization":"completed-candle source rows only; no fill or interpolation","parquet_status":parquet_status,"source_files":[str(MOMENTUM),str(CONSOLIDATION)],"csv_sha256":sha256(csv)};atomic_write(STORE/"latest_market_features_manifest.json",json.dumps(sanitize(manifest),indent=2,sort_keys=True)+"\n");return f,manifest
def load_features()->pd.DataFrame:
    path=STORE/"latest_market_features.csv";return pd.read_csv(path) if path.exists() else pd.DataFrame()
