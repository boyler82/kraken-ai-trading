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

## Daily Workflow

Run:

```bash
./scripts/run_daily_portfolio_scan.sh