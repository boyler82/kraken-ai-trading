# Validated Setups

## Active Candidates

### BTC D1 RSI2 Mean Reversion

Status: Candidate  
Condition: RSI(2) < 10  
Exit model: 3 days  
Win rate: 60.95%  
Average return: +0.59%  
Median return: +0.83%  
Worst return: -10.52%  
Source: BACKTESTS/rsi2_backtest_results.csv

### ETH D1 RSI2 + MA200

Status: Candidate  
Condition: RSI(2) < 10 and Close > MA200  
Exit model: 3 days  
Win rate: 55.00%  
Average return: +1.05%  
Median return: +1.14%  
Worst return: -8.09%  
Source: BACKTESTS/rsi2_ma200_results.csv

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