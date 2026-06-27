# Entry Timing Research

Status: ACTIVE_RESEARCH

Last Updated: 2026-06-27

## Research Question

Does entering on the first RSI2 < 10 day produce worse results than waiting for Day 2 or Day 3 of the oversold episode?

## Method

For each RSI2 oversold episode:

- Entry Day 1
- Entry Day 2
- Entry Day 3

Each entry was tested with holding periods from 1 to 10 days.

Metrics:

- Average return
- Expected value
- Profit factor

Source:

BACKTESTS/rsi2_entry_timing_matrix.csv

---

## Key BTC Finding

BTC Day 1 entry is historically weak.

BTC results:

- Day 1 / Hold 3D: -0.03%
- Day 2 / Hold 3D: +0.89%
- Day 3 / Hold 3D: +0.90%

Best BTC zones:

- Day 2 / Hold 5D: +1.08%, Profit Factor 1.79
- Day 3 / Hold 4D: +1.07%, Profit Factor 1.83
- Day 3 / Hold 2D: +0.86%, Profit Factor 2.03

## Interpretation

For BTC, RSI2 < 10 should be treated as an oversold alert.

Immediate Day 1 entry may be too early.

Day 2 and Day 3 entries show stronger historical results.

## Important Limitation

This finding is research evidence, not a final trading rule.

Before changing live strategy rules, results should be validated on:

- more crypto assets
- different market regimes
- larger historical dataset
- live signal tracking

## Current Status

No automatic strategy change yet.

Research direction:

RSI2 < 10 -> Oversold Episode -> Evaluate Day 2 / Day 3 entry timing
