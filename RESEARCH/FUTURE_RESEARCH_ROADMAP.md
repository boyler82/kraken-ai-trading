FUTURE RESEARCH ROADMAP

Status: Active Research Backlog

Last Updated: 2026-06-21

⸻

Current Project Status

Current validated system:

Cross Asset RSI2 v1

Assets:

* BTC
* SPY
* QQQ
* GLD
* NVDA

Current process:

RSI2 < 10
→ Signal
→ Fixed Hold Period
→ Portfolio Allocation

Project has entered LIVE OBSERVATION phase.

Current priority:

Validate live behavior against historical research.

No major strategy modifications until sufficient live sample size is collected.

Target:

10–20 live signals before major model changes.

⸻

PRIORITY 1

RSI2 Signal Duration Analysis

Research ID:

RSI2_DURATION_001

Motivation:

Live BTC signal showed that RSI2 < 10 may identify oversold conditions before the actual bottom forms.

Questions:

* How long does RSI2 < 10 typically persist?
* Is entry on Day 1 optimal?
* Is Day 2 or Day 3 better?
* Does waiting for reversal improve results?

Required Metrics:

* Number of oversold episodes
* Average duration
* Median duration
* Maximum duration
* Return after Day 1 entry
* Return after Day 2 entry
* Return after reversal confirmation

Priority:

CRITICAL

Estimated Effort:

1–2 hours

⸻

PRIORITY 2

Day Of Week Analysis

Research ID:

WEEKDAY_EFFECT_001

Motivation:

Possible weekly market rhythm observed in BTC.

Questions:

* Which weekday produces strongest returns?
* Which weekday produces weakest returns?
* Does RSI2 perform better on specific weekdays?
* Are local highs/lows concentrated around certain days?

Assets:

* BTC
* ETH
* SOL

Required Metrics:

* Average return by weekday
* Median return by weekday
* Win rate by weekday
* Weekly high occurrence frequency
* Weekly low occurrence frequency

Priority:

HIGH

Estimated Effort:

1–2 hours

⸻

PRIORITY 3

Market Regime Detector

Research ID:

REGIME_001

Motivation:

Strategy performance may depend on market environment.

Potential Regimes:

* Bull Trend
* Bear Trend
* Sideways
* High Volatility
* Low Volatility

Questions:

* When does RSI2 perform best?
* When should signals be ignored?
* Does performance change significantly by regime?

Priority:

HIGH

Estimated Effort:

3–5 hours

⸻

PRIORITY 4

Multi-Coin Expansion

Research ID:

MULTI_COIN_001

Candidate Assets:

* SOL
* LINK
* XRP
* ADA
* AVAX
* LTC

Goal:

Increase opportunity set without reducing signal quality.

Rules:

No asset enters production portfolio without research validation.

Priority:

MEDIUM

Estimated Effort:

2–4 hours

⸻

PRIORITY 5

RSI2 + EMA200 Research

Research ID:

RSI2_EMA200_001

Questions:

* Does trend filtering improve signal quality?
* Is RSI2 more effective above EMA200?
* Is RSI2 more effective below EMA200?

Priority:

MEDIUM

Estimated Effort:

1–2 hours

⸻

PRIORITY 6

Momentum Ranking Portfolio

Research ID:

MOMENTUM_001

Concept:

Rank assets by momentum and allocate capital to strongest candidates.

Goal:

Create independent strategy separate from RSI2 system.

Priority:

LOW

Estimated Effort:

4–8 hours

⸻

PRIORITY 7

Breakout Research

Research ID:

BREAKOUT_001

Concept:

Trend-following strategy based on strength rather than weakness.

Note:

Must remain completely separate from RSI2 research.

Priority:

LOW

Estimated Effort:

4–8 hours

⸻

Research Principles

1. Research before implementation.
2. No strategy promotion without evidence.
3. Separate hypothesis from validated results.
4. Avoid overfitting.
5. Prefer robustness over profitability.
6. Live results override assumptions.
7. Process quality is more important than individual trade outcomes.