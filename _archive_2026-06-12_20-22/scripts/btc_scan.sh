#!/bin/bash

mkdir -p data/btc

OUT="data/btc/btc_scan_$(date +%Y-%m-%d_%H-%M).txt"

echo "# BTC SCAN" > "$OUT"
echo "Generated: $(date)" >> "$OUT"
echo "" >> "$OUT"

echo "=== TICKER ===" >> "$OUT"
kraken ticker BTCUSD -o json >> "$OUT"

echo "" >> "$OUT"
echo "=== OHLC 15M ===" >> "$OUT"
kraken ohlc BTCUSD --interval 15 -o json >> "$OUT"

echo "" >> "$OUT"
echo "=== ORDERBOOK ===" >> "$OUT"
kraken orderbook BTCUSD --count 10 -o json >> "$OUT"

echo "Saved to: $OUT"
