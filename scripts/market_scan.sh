#!/bin/bash

PAIRS=("BTCUSD" "ETHUSD" "SOLUSD" "XRPUSD" "ADAUSD" "DOGEUSD" "LINKUSD" "AVAXUSD" "DOTUSD" "LTCUSD")

mkdir -p data/market

OUT="data/market/market_scan_$(date +%Y-%m-%d_%H-%M).txt"

echo "# MARKET SCAN" > "$OUT"
echo "Generated: $(date)" >> "$OUT"
echo "" >> "$OUT"

for PAIR in "${PAIRS[@]}"
do
  echo "Scanning $PAIR..."
  echo "===== $PAIR =====" >> "$OUT"
  kraken ticker "$PAIR" -o json >> "$OUT"
  echo "" >> "$OUT"
  sleep 1
done

echo "Saved to: $OUT"
