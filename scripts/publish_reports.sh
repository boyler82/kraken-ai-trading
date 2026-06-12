#!/bin/bash

git add analysis plans journal data/btc data/market prompts scripts templates

git commit -m "Update trading reports $(date '+%Y-%m-%d %H:%M')" || echo "Nothing to commit"

git push origin main
