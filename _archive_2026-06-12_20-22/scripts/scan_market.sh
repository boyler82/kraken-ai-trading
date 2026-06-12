#!/bin/bash

PAIRS=("BTCUSD" "ETHUSD" "SOLUSD" "XRPUSD" "ADAUSD" "DOGEUSD" "LINKUSD" "AVAXUSD" "DOTUSD" "LTCUSD")

mkdir -p data/scans

for PAIR in "${PAIRS[@]}"
do
  echo "Scanning $PAIR..."

  {
    echo "=== $PAIR TICKER ==="
    kraken ticker "$PAIR" -o json

    echo "=== $PAIR OHLC 15M ==="
    kraken ohlc "$PAIR" --interval 15 -o json

    echo "=== $PAIR ORDERBOOK ==="
    kraken orderbook "$PAIR" --count 10 -o json
  } > "data/scans/${PAIR}.txt"

  sleep 1
done

echo "Scan complete. Files saved in data/scans/"