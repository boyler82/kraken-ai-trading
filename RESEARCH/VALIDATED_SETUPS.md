# Validated Setups

## Promising Research

### Cross Asset RSI2 v1 — NO_ETH

Status: PROMISING_RESEARCH

Condition:
- RSI(2) < 10
- Hold 3 days
- Position size: 5%
- Roundtrip cost assumption: 0.25%

Assets:
- BTC
- SPY
- QQQ
- GLD
- NVDA

Backtest:
- Trades: 484
- Total return: +8.43%
- Average trade: +0.34%
- Median trade: +0.42%
- Max drawdown: -2.15%

Reason:
Portfolio variant without ETH produced nearly the same return as ALL, but with much lower drawdown.

Source:
- BACKTESTS/cross_asset_portfolio_variants.csv
- BACKTESTS/cross_asset_rsi2_costs.csv
- BACKTESTS/cross_asset_rsi2_position_sizing.csv 

## Active Candidates

### ETH D1 RSI2 + MA200

Status: Candidate+  
Condition: RSI(2) < 10 and Close > MA200  
Exit model: 3 days  

Backtest:
- Trades: 21
- Win rate: 52.38%
- Average trade: +1.07%
- Median trade: +0.01%
- Worst trade: -8.09%
- Best trade: +18.54%
- Total return: +19.78%
- Max drawdown: -20.79%

Source:
- BACKTESTS/rsi2_ma200_results.csv
- BACKTESTS/equity_curve_summary.csv

## Research Only

### BTC D1 RSI2 Mean Reversion

Status: Research Only  
Condition: RSI(2) < 10  
Exit model: 3 days  

Reason:
Simple return test looked promising, but equity curve failed.

Backtest:
- Trades: 82
- Win rate: 56.10%
- Average trade: -0.13%
- Median trade: +0.48%
- Worst trade: -10.52%
- Best trade: +6.40%
- Total return: -14.83%
- Max drawdown: -31.32%

Conclusion:
Not tradable without additional filters.

Source:
- BACKTESTS/rsi2_backtest_results.csv
- BACKTESTS/equity_curve_summary.csv

## Rejected

### BTC 1H Mean Reversion

Reason: Negative expectancy  
Source: BACKTESTS/btc_intraday_backtest.csv

### BTC 1H Mean Reversion + Reclaim

Reason: Negative expectancy  
Source: BACKTESTS/btc_intraday_backtest_trigger.csv

### BTC 1H Momentum Breakout

Reason: Negative expectancy  
Source: BACKTESTS/btc_intraday_momentum_backtest.csv

### BTC 1H TP/SL Grid Search

Reason: All tested combinations negative expectancy  
Source: BACKTESTS/btc_intraday_grid_search.csv