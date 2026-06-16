# Kraken AI Trading Research

Research pipeline for market analysis, backtesting and portfolio decision support.

This project is not an automated trading bot.

## Objective

Build a repeatable decision process based on:

- market data
- statistical testing
- backtests
- portfolio research
- daily reports
- risk awareness

Main principle:

Quality of decision > number of trades.

## Current Main Model

### Cross Asset RSI2 v1

Status: PROMISING_RESEARCH

Assets:

- BTC
- SPY
- QQQ
- GLD
- NVDA

Rules:

- Daily timeframe
- RSI(2) < 10
- Hold 3 days
- Position size: 5%
- Cost assumption: 0.25% roundtrip

ETH is excluded from v1 due to weaker portfolio contribution.

Latest documented NO_ETH snapshot:

- Total return: +6.97%
- Max drawdown: -1.92%

## Research Notes

- Backtests are research artifacts, not executable trading instructions.
- Portfolio and walk-forward reports are kept separate from descriptive regime analysis.
- When comparing reports, use the same dataset snapshot and script version.
- Treat any result without an explicit train/test split as in-sample only.

## Daily Workflow

Run:

```bash
./scripts/run_daily_portfolio_scan.sh
