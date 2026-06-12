#!/bin/bash

echo "=== TICKER ==="
kraken ticker BTCUSD -o json

echo "=== OHLC 15M ==="
kraken ohlc BTCUSD --interval 15 -o json

echo "=== ORDERBOOK ==="
kraken orderbook BTCUSD --count 10 -o json
