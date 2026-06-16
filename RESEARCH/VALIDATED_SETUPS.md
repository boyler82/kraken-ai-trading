Validated Setups

Last Updated: 2026-06-16

Methodology notes:

* Descriptive regime tables are for analysis only.
* Prefer walk-forward or train/test checks over full-sample thresholds.
* Portfolio conclusions override single-asset conclusions when they conflict.

⸻

PROMISING_RESEARCH

Cross Asset RSI2 v1 (NO_ETH)

Status: PROMISING_RESEARCH

Assets:

* BTC
* SPY
* QQQ
* GLD
* NVDA

Rules:

* RSI(2) < 10
* Hold 3 days
* Position size 5%
* Cost assumption 0.25%

Research Results:

* Trades: 484
* Total Return: +6.97%
* Average Trade: +0.34%
* Median Trade: +0.42%
* Max Drawdown: -1.92%

Notes:

ETH removed due to weak portfolio contribution.

⸻

RESEARCH_ONLY

BTC D1 RSI2 Mean Reversion

Status: RESEARCH_ONLY

Reason:

Positive win rate but negative average return and weaker equity curve behavior.

Results:

* Win Rate: 56.10%
* Average Return: -0.13%

⸻

ETH D1 RSI2 + MA200

Status: RESEARCH_ONLY

Reason:

Interesting results but insufficient validation for inclusion in the current portfolio.

Results:

* Win Rate: 52.38%
* Average Return: +1.07%

⸻

INCONCLUSIVE

ETH D1 RSI2 + MA200 + HIGH_VOL

Status: INCONCLUSIVE

Reason:

Sample size too small.

Results:

* Trades: 11
* Total Return: +19.95%
* Max Drawdown: -8.23%

Needs:

* More history
* Additional validation

⸻

REJECTED

BTC Intraday Oversold Reversion

Status: REJECTED

Reason:

Negative expectancy after validation.

Evidence:

* Negative average return
* Weak forward performance
* No stable edge

⸻

Promotion Rules

A model may enter PROMISING_RESEARCH only if:

* positive expectancy
* acceptable drawdown
* survives cost assumptions
* survives portfolio analysis
* has a documented out-of-sample check

A model may be promoted only after additional validation.

⸻

Research Process

A model may enter PROMISING_RESEARCH only if:

* positive expectancy
* acceptable drawdown
* survives cost assumptions
* survives portfolio analysis

A model may be promoted only after additional validation.

No model in this document is investment advice.
