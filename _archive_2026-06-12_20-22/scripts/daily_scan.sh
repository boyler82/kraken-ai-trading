#!/bin/bash

PAIRS=("BTCUSD" "ETHUSD" "SOLUSD" "XRPUSD" "ADAUSD" "DOGEUSD" "LINKUSD" "AVAXUSD" "DOTUSD" "LTCUSD")

mkdir -p data/daily

OUT="data/daily/daily_scan_$(date +%Y-%m-%d_%H-%M).txt"

echo "# DAILY CRYPTO SCAN" > "$OUT"
echo "Generated: $(date)" >> "$OUT"
echo "" >> "$OUT"

for PAIR in "${PAIRS[@]}"
do
  echo "Scanning $PAIR..."

  echo "===== $PAIR =====" >> "$OUT"
  echo "--- TICKER ---" >> "$OUT"
  kraken ticker "$PAIR" -o json >> "$OUT"

  echo "--- OHLC 15M ---" >> "$OUT"
  kraken ohlc "$PAIR" --interval 15 -o json >> "$OUT"

  echo "--- ORDERBOOK ---" >> "$OUT"
  kraken orderbook "$PAIR" --count 10 -o json >> "$OUT"

  echo "" >> "$OUT"
  sleep 1
done

echo "Saved scan to: $OUT"