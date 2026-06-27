#!/bin/bash

set -e

mkdir -p DATASETS/market_raw

echo "Updating crypto market data..."

for symbol in BTCUSD ETHUSD SOLUSD XRPUSD LINKUSD ADAUSD AVAXUSD DOGEUSD LTCUSD
do
  echo "Downloading $symbol..."
  kraken ohlc $symbol --interval 1440 -o json > DATASETS/market_raw/${symbol}_D1.json
done

echo "Crypto data update complete."
