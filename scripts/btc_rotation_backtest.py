from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
from btc_rotation_engine import synchronized_relative_series
from daily_momentum_breakout_radar import _hourly_for
from weekly_consolidation_common import INTRADAY_DIR, utc_timestamp


def performance_metrics(equity:pd.Series,periods_per_year:float=365*6)->dict[str,float]:
    returns=equity.pct_change().dropna(); downside=returns[returns<0]
    drawdown=equity/equity.cummax()-1; years=max(len(equity)/periods_per_year,1/periods_per_year)
    return {"cagr_pct":((float(equity.iloc[-1])/float(equity.iloc[0]))**(1/years)-1)*100,"maximum_drawdown_pct":float(drawdown.min()*100),"sharpe_like":float(returns.mean()/returns.std(ddof=0)*math.sqrt(periods_per_year)) if returns.std(ddof=0)>0 else 0.0,"sortino_like":float(returns.mean()/downside.std(ddof=0)*math.sqrt(periods_per_year)) if len(downside) and downside.std(ddof=0)>0 else 0.0}


def backtest_rotation(alt:pd.DataFrame,btc:pd.DataFrame,fee_pct:float=.4,slippage_pct:float=.2)->dict[str,Any]:
    data=synchronized_relative_series(alt,btc)
    if len(data)<100: raise ValueError("insufficient synchronized history for backtest")
    rel=data["alt_btc"]; ema20=rel.ewm(span=20,adjust=False).mean(); ema50=rel.ewm(span=50,adjust=False).mean()
    signal=((rel>ema20)&(ema20>ema50)&(ema20.pct_change(4)>0)).shift(1,fill_value=False).astype(bool) # next-bar execution
    holding="BTC"; btc_units=1.0; trades=[]; equity=[]; entry=None; total_cost=0.0; alt_units=0.0; last_exit=-999; entry_indices=[]
    cost=(fee_pct+slippage_pct)/100
    for i,row in data.iterrows():
        want_alt=bool(signal.iloc[i])
        recent_entries=sum(i-x<=168 for x in entry_indices)
        if want_alt and holding=="BTC" and i-last_exit>=24 and recent_entries<2:
            alt_units=btc_units/float(row["alt_btc"])*(1-cost); total_cost+=btc_units*cost; entry=(i,float(row["alt_btc"]),btc_units); holding="ALT"
            entry_indices.append(i)
        elif not want_alt and holding=="ALT" and entry is not None and i-entry[0]>=24:
            before=entry[2] if entry else btc_units; btc_units=alt_units*float(row["alt_btc"])*(1-cost); total_cost+=alt_units*float(row["alt_btc"])*cost
            trades.append({"entry_index":entry[0],"exit_index":i,"holding_bars":i-entry[0],"btc_pnl":btc_units-before,"return_pct":(btc_units/before-1)*100}); holding="BTC"; entry=None; last_exit=i
        value=btc_units if holding=="BTC" else alt_units*float(row["alt_btc"])
        equity.append(value)
    if holding=="ALT": btc_units=alt_units*float(data.iloc[-1]["alt_btc"])*(1-cost)
    curve=pd.Series(equity,dtype=float); perf=performance_metrics(curve)
    wins=[t["btc_pnl"] for t in trades if t["btc_pnl"]>0]; losses=[t["btc_pnl"] for t in trades if t["btc_pnl"]<0]
    btc_start=float(data.iloc[0]["btc_usd"]); btc_end=float(data.iloc[-1]["btc_usd"])
    usd_terminal=btc_units*btc_end; usd_hold=btc_start; btc_hold_usd=btc_end
    btc_prices=data["btc_usd"];btc_trend=(btc_prices>btc_prices.ewm(span=50,adjust=False).mean()).shift(1,fill_value=False)
    trend_usd=btc_start;trend_btc=0.0;trend_holding="USD"
    for price,want_btc in zip(btc_prices,btc_trend):
        if want_btc and trend_holding=="USD":trend_btc=trend_usd/float(price)*(1-cost);trend_holding="BTC"
        elif not want_btc and trend_holding=="BTC":trend_usd=trend_btc*float(price)*(1-cost);trend_holding="USD"
    btc_trend_usd=trend_usd if trend_holding=="USD" else trend_btc*btc_end
    alt_bars=int(signal.sum()); total=len(signal)
    return {"execution_assumption":"signal on completed candle; execution at next completed candle close","terminal_btc_units":btc_units,"terminal_usd_value":usd_terminal,"btc_hold_terminal_btc_units":1.0,"btc_hold_terminal_usd_value":btc_hold_usd,"usd_hold_terminal_btc_units":usd_hold/btc_end,"usd_hold_terminal_usd_value":usd_hold,"btc_trend_filter_terminal_btc_units":btc_trend_usd/btc_end,"btc_trend_filter_terminal_usd_value":btc_trend_usd,"btc_unit_return_pct":(btc_units-1)*100,"usd_return_pct":(usd_terminal/btc_start-1)*100,"relative_performance_vs_btc_hold_pct":(btc_units-1)*100,**perf,"win_rate_pct":len(wins)/len(trades)*100 if trades else 0,"profit_factor":sum(wins)/abs(sum(losses)) if losses else None,"expected_value_per_rotation_btc":float(np.mean([t["btc_pnl"] for t in trades])) if trades else 0,"number_of_rotations":len(trades),"average_holding_hours":float(np.mean([t["holding_bars"] for t in trades])) if trades else 0,"turnover":len(trades)*2,"total_fees_and_slippage_btc":total_cost,"worst_rotation_pct":min((t["return_pct"] for t in trades),default=0),"best_rotation_pct":max((t["return_pct"] for t in trades),default=0),"percent_time_btc":(total-alt_bars)/total*100,"percent_time_usd":0.0,"percent_time_alts":alt_bars/total*100,"train_end_index":int(total*.6),"validation_end_index":int(total*.8),"test_start_index":int(total*.8),"test_optimization_performed":False}


def main()->None:
    p=argparse.ArgumentParser();p.add_argument("--asset");p.add_argument("--as-of");a=p.parse_args();cutoff=utc_timestamp(a.as_of)
    universe=pd.read_csv(ROOT/"DATASETS/universe/weekly_consolidation_universe.csv"); included=universe[universe["inclusion_status"]=="INCLUDED"]
    asset=(a.asset or next((x for x in ["ADA","ZEC","INJ","NIGHT"] if x in set(included["symbol"])),None))
    if not asset: raise RuntimeError("no cached altcoin available for rotation backtest")
    pair=str(included[included["symbol"]==asset].iloc[0]["selected_kraken_pair"]); btcrow=included[included["symbol"]=="BTC"]
    btc=_hourly_for("BTC",str(btcrow.iloc[0]["selected_kraken_pair"] if len(btcrow) else "XBTUSD"),cutoff); alt=_hourly_for(asset,pair,cutoff)
    result=backtest_rotation(alt,btc);print(json.dumps({"asset":asset,**result},indent=2,allow_nan=False))


if __name__=="__main__":main()
