Cross Asset RSI2 v1 Playbook

Status

PROMISING_RESEARCH

This model is a research-based decision framework.

It is not an automated trading strategy.

⸻

Objective

Identify statistically oversold conditions across a diversified portfolio:

* BTC
* SPY
* QQQ
* GLD
* NVDA

and evaluate mean reversion opportunities.

⸻

Entry Condition

Signal becomes active when:

RSI(2) < 10

on the daily timeframe.

⸻

Position Sizing

Research baseline:

* Position size: 5% of portfolio capital
* Cost assumption: 0.25% roundtrip

⸻

Exit Rule

Fixed holding period:

* 3 trading days

No discretionary extensions.

⸻

Historical Research

Portfolio:

BTC + SPY + QQQ + GLD + NVDA

Results:

* Trades: 484
* Total return: +6.97%
* Average trade: +0.34%
* Median trade: +0.42%
* Maximum drawdown: -1.92%

Research source:

BACKTESTS/cross_asset_portfolio_variants.csv

⸻

Do Not Enter If

* Data quality is uncertain
* Market data is missing
* Signal is generated from incomplete candles
* Risk cannot be quantified
* Portfolio concentration exceeds personal limits

⸻

Daily Workflow

1. Update market data
2. Run portfolio scan
3. Review active signals
4. Review near-signal watchlist
5. Review macro context
6. Make independent decision

⸻

Process Rules

Focus on process quality.

Do not chase markets.

Do not override signals because of emotions.

Document every discretionary deviation.

⸻

Research Notes

Current version:

Cross Asset RSI2 v1

Future versions must be validated separately.

No modifications should be accepted without backtesting.
