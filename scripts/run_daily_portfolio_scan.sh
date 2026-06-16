#!/bin/bash

set -e

echo "Updating market data..."

kraken ohlc BTCUSD --interval 1440 -o json > DATASETS/market_raw/BTCUSD_D1.json
kraken ohlc SPYx/USD --interval 1440 --asset-class tokenized_asset -o json > DATASETS/market_raw/SPYx_USD_D1.json
kraken ohlc QQQx/USD --interval 1440 --asset-class tokenized_asset -o json > DATASETS/market_raw/QQQx_USD_D1.json
kraken ohlc GLDx/USD --interval 1440 --asset-class tokenized_asset -o json > DATASETS/market_raw/GLDx_USD_D1.json
kraken ohlc NVDAx/USD --interval 1440 --asset-class tokenized_asset -o json > DATASETS/market_raw/NVDAx_USD_D1.json

echo "Running portfolio decision engine..."

python3 scripts/daily_decision_engine.py

echo "Done."