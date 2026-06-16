# Daily Decision Engine

Date: 2026-06-16

## Summary

### BTC

- Status: **RESEARCH_ONLY**
- Decision: **RESEARCH ONLY**
- Close: 66825.5
- RSI(2): 100.0
- MA200: 77525.47
- Above MA200: False
- ATR%: 4.14
- Median ATR%: 3.15
- High volatility regime: True
- Model: BTC D1 RSI2 Mean Reversion
- Condition: RSI2 < 10
- Exit: 3 days
- Historical win rate: 56.1%
- Historical avg return: -0.13%
- Historical median return: 0.48%
- Historical worst return: -10.52%
- Confidence: NONE

### ETH

- Status: **PROMISING_RESEARCH**
- Decision: **NO SIGNAL**
- Close: 1829.99
- RSI(2): 100.0
- MA200: 2402.06
- Above MA200: False
- ATR%: 5.67
- Median ATR%: 5.25
- High volatility regime: True
- Model: ETH D1 RSI2 + MA200 + HIGH_VOL
- Condition: RSI2 < 10 and Close > MA200 and ATR% > median ATR%
- Exit: 3 days
- Historical win rate: 54.55%
- Historical avg return: 1.89%
- Historical median return: 0.01%
- Historical worst return: -5.72%
- Confidence: NONE

## Process Note

- BTC D1 RSI2 remains Research Only after failed equity curve validation.
- ETH D1 RSI2 + MA200 + HIGH_VOL is Promising Research, not production-ready.
- Model has only 11 historical trades, so sample size risk is high.
- No trade should be considered without active signal, risk review and manual context check.
- This report is analytical, not financial advice.
