# Consolidation Range Engine V1

**RESEARCH_ONLY**  
**NOT_A_BUY_SIGNAL**  
**NOT_A_SELL_SIGNAL**  
**LIVE_NOT_AUTHORIZED**  

## Candidates

### BTC — STALE_DATA

- Report generated at: 2026-10-12T17:01:46.043229+00:00
- Source: /Users/tron/kraken-ai-trading/DATASETS/BTC_4H_DONCHIAN_V1/BTCUSD_15m_operational.csv (15m, 7863 rows)
- Source coverage: 2026-05-13T19:30:00+00:00 → 2026-08-03T17:00:00+00:00
- Derived 4H coverage: 2026-05-13T20:00:00+00:00 → 2026-08-03T12:00:00+00:00 (491 bars; 2 incomplete/rejected buckets)
- Freshness: STALE (age 1685.0294107219445h; fresh ≤ 8.0h; stale > 24.0h)
- **STALE DATA WARNING:** Latest completed 4H candle is 1685.03 hours old; stale threshold is 24.00 hours.
- Structural state: VALID_RANGE (valid horizontal consolidation: true)
- Quality: 42.85 (WEAK); breakout risk: MEDIUM
- Passed conditions: lower_boundary_reactions_passed, upper_boundary_reactions_passed, close_containment_passed, trend_flatness_passed, width_stability_passed, no_confirmed_directional_break_passed
- Failed conditions: none
- Historical range start: 2026-07-27T20:00:00+00:00
- Historical range end: 2026-08-03T12:00:00+00:00
- Duration: 41 completed 4H bars / 164 trading hours
- Calendar duration: 160.00 hours / 6.6667 days
- Continuity: CONTINUOUS (0 missing expected 4H bars)
- Invalidation / breakout confirmation: None / None
- Post-breakout reference: None / None
- Latest available market observation: 2026-08-03T12:00:00+00:00 / 63603.30000000
- Low / high / midpoint: 62428.70000000 / 64915.20000000 / 63671.95000000
- Width: 2486.50000000 (3.91%)
- Latest available position: raw 47.24%, clipped 47.24%, MID_RANGE
- Tests lower / upper: 3 / 2
- False above / below: 3 / 3
- Confirmed above / below: 0 / 0
- Traversals low→high / high→low: 0 / 1
- Full traversal avg / median: 22.0 / 22.0 bars; 88.0 / 88.0 hours
- Lower test intervals: avg 8.0 bars, median 8.0 bars, n=2
- Upper test intervals: avg 15.0 bars, median 15.0 bars, n=1
- Trend raw slope: -29.24567944 quote_currency_per_4h_bar
- Trend normalization denominator: 2486.50000000 quote_currency_range_width
- Trend normalized slope: 0.47047142 range_widths_over_included_candidate_duration
- Trend threshold: 0.5 range_widths_over_included_candidate_duration
- Trend comparison: 0.47047141673 <= 0.5 => true
- Quality contributions: lower_tests=+9.00, upper_tests=+6.00, boundary_symmetry=+6.67, closes_inside=+18.00, trend_flatness=+0.83, width_stability=+4.39, traversals=+2.50, duration=+5.47, false_breakout_penalty=-10.00

## Unavailable assets

- ADA: missing ADAUSD_1H.json; missing ADAUSD_4H.json | expected /Users/tron/kraken-ai-trading/DATASETS/market_raw/ADAUSD_1H.json | required native completed 1H or 4H candles | latest 1D | action: download native Kraken intraday history
- AVAX: missing AVAXUSD_1H.json; missing AVAXUSD_4H.json | expected /Users/tron/kraken-ai-trading/DATASETS/market_raw/AVAXUSD_1H.json | required native completed 1H or 4H candles | latest 1D | action: download native Kraken intraday history
- DOGE: missing DOGEUSD_1H.json; missing DOGEUSD_4H.json | expected /Users/tron/kraken-ai-trading/DATASETS/market_raw/DOGEUSD_1H.json | required native completed 1H or 4H candles | latest 1D | action: download native Kraken intraday history
- ETH: missing ETHUSD_1H.json; missing ETHUSD_4H.json | expected /Users/tron/kraken-ai-trading/DATASETS/market_raw/ETHUSD_1H.json | required native completed 1H or 4H candles | latest 1D | action: download native Kraken intraday history
- LINK: missing LINKUSD_1H.json; missing LINKUSD_4H.json | expected /Users/tron/kraken-ai-trading/DATASETS/market_raw/LINKUSD_1H.json | required native completed 1H or 4H candles | latest 1D | action: download native Kraken intraday history
- LTC: missing LTCUSD_1H.json; missing LTCUSD_4H.json | expected /Users/tron/kraken-ai-trading/DATASETS/market_raw/LTCUSD_1H.json | required native completed 1H or 4H candles | latest 1D | action: download native Kraken intraday history
- SOL: missing SOLUSD_1H.json; missing SOLUSD_4H.json | expected /Users/tron/kraken-ai-trading/DATASETS/market_raw/SOLUSD_1H.json | required native completed 1H or 4H candles | latest 1D | action: download native Kraken intraday history
- XRP: missing XRPUSD_1H.json; missing XRPUSD_4H.json | expected /Users/tron/kraken-ai-trading/DATASETS/market_raw/XRPUSD_1H.json | required native completed 1H or 4H candles | latest 1D | action: download native Kraken intraday history
