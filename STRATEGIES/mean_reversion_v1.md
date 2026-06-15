# Mean Reversion v1

## Goal

Buy weakness.
Sell rebound.

## Markets

- BTC
- ETH
- SPY
- QQQ
- NVDA
- GLD

## Entry Conditions

1. RSI(2) < 10
2. Price below MA20
3. No major breakdown
4. Reversal candle

## Exit

1. MA20 touch
2. Resistance
3. Risk Reward >= 1.5

## Invalidations

- Strong trend breakdown
- Macro event
- Volume expansion against position

## Research Findings

### BTC

Best observed setup:

- Condition: RSI(2) < 10
- Holding period: 3 days
- Signals: 210
- Win rate: 60.95%
- Average return: +0.59%
- Median return: +0.83%
- Worst return: -10.52%
- Best return: +14.25%

MA200 filter did not improve BTC results.

### ETH

Best observed setup:

- Condition: RSI(2) < 10 and close > MA200
- Holding period: 3 days
- Signals: 40
- Win rate: 55.00%
- Average return: +1.05%
- Median return: +1.14%
- Worst return: -8.09%
- Best return: +18.54%

MA200 filter improved ETH 3-day average return.

## Current Hypothesis

BTC and ETH require separate mean reversion models.

BTC:
- RSI(2) < 10
- 3-day exit

ETH:
- RSI(2) < 10
- close > MA200
- 3-day exit

## What We Do Not Know Yet

- Whether results survive transaction fees.
- Whether stop loss improves or worsens expected value.
- Whether ATR-based exits outperform fixed 3-day exits.
- Whether results are stable by market regime.  