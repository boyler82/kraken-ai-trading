#!/bin/bash

set -e

echo "Updating crypto market data..."
./scripts/update_crypto_data.sh

echo "Running daily decision engine..."
python3 scripts/daily_decision_engine.py

echo "Running RSI2 episode tracker..."
python3 scripts/rsi2_episode_tracker.py

echo "Running RSI2 edge database..."
python3 scripts/rsi2_edge_database.py

echo "Building RSI2 best edge summary..."
python3 scripts/build_edge_summary.py

echo "Running market regime engine..."
python3 scripts/market_regime.py

echo "Running crypto opportunity ranking..."
python3 scripts/opportunity_ranking.py

echo "Done."