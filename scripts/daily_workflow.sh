#!/bin/bash

echo "=== DAILY WORKFLOW START ==="

bash scripts/btc_scan.sh
bash scripts/market_scan.sh

echo ""
echo "Data generated in:"
echo "- data/btc/"
echo "- data/market/"

echo ""
echo "Next step:"
echo "Send latest BTC scan and market scan to ChatGPT for DAILY_REPORT."
