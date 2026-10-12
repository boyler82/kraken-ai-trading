# Early Expansion Engine V1

RESEARCH_ONLY | NOT_A_BUY_SIGNAL | NOT_A_SELL_SIGNAL | USER_DECISION_REQUIRED | LIVE_NOT_AUTHORIZED

## Market Summary

- State: PRE_MOVE_CONDITIONS_PRESENT
- Assets evaluated: 73
- Pre-move candidates: 16
- PRE_MOVE_STRONG: 0
- PRE_MOVE_BUILDING: 16
- Too late: 5

## Top Pre-Move Candidates

### ALGO
- Classification: PRE_MOVE_BUILDING | combined: 66.45 | energy: 65.12
- Confidence: 69 (MEDIUM)
- Range position: 65.32748538011703% | 24h return: -3.9026275115919495% | breakout distance: 13.8254%
- Main strength: data_quality
- Primary risk: volume_buildup

### HBAR
- Classification: PRE_MOVE_BUILDING | combined: 65.58 | energy: 62.18
- Confidence: 69 (MEDIUM)
- Range position: 17.352092352092455% | 24h return: -4.835960801022587% | breakout distance: 13.1018%
- Main strength: range_position
- Primary risk: volatility_compression

### XLM
- Classification: PRE_MOVE_BUILDING | combined: 65.11 | energy: 64.13
- Confidence: 69 (MEDIUM)
- Range position: 37.81022485016696% | 24h return: -5.062952179713132% | breakout distance: 10.1074%
- Main strength: data_quality
- Primary risk: relative_strength_delta

### ICP
- Classification: PRE_MOVE_BUILDING | combined: 64.12 | energy: 63.35
- Confidence: 69 (MEDIUM)
- Range position: 64.62483708806546% | 24h return: 2.152886115444619% | breakout distance: 9.1565%
- Main strength: data_quality
- Primary risk: range_position

### AVAX
- Classification: PRE_MOVE_BUILDING | combined: 63.87 | energy: 58.43
- Confidence: 69 (MEDIUM)
- Range position: 38.38422883649017% | 24h return: -4.551270334490942% | breakout distance: 10.933%
- Main strength: data_quality
- Primary risk: momentum_precursor

### SHIB
- Classification: PRE_MOVE_BUILDING | combined: 63.82 | energy: 58.11
- Confidence: 69 (MEDIUM)
- Range position: 17.48478701825577% | 24h return: -4.0897575099529515% | breakout distance: 10.5485%
- Main strength: range_position
- Primary risk: volatility_compression

### SPX
- Classification: PRE_MOVE_BUILDING | combined: 63.3 | energy: 60.04
- Confidence: 69 (MEDIUM)
- Range position: 11.910112359550622% | 24h return: -4.715745349751099% | breakout distance: 21.2259%
- Main strength: range_position
- Primary risk: relative_strength_delta

### MORPHO
- Classification: PRE_MOVE_BUILDING | combined: 61.91 | energy: 55.84
- Confidence: 69 (MEDIUM)
- Range position: 20.10319692482729% | 24h return: -3.0131530046698107% | breakout distance: 14.8001%
- Main strength: range_position
- Primary risk: relative_strength_delta

### FET
- Classification: PRE_MOVE_BUILDING | combined: 61.56 | energy: 63.16
- Confidence: 66 (MEDIUM)
- Range position: 24.45652173913046% | 24h return: -8.94039735099338% | breakout distance: 14.2634%
- Main strength: range_position
- Primary risk: volatility_compression

### SKY
- Classification: PRE_MOVE_BUILDING | combined: 61.43 | energy: 59.49
- Confidence: 69 (MEDIUM)
- Range position: 32.8571428571429% | 24h return: -4.0494938132733305% | breakout distance: 16.0525%
- Main strength: data_quality
- Primary risk: relative_strength_delta

## Fastest Energy Build

- ALGO: energy 65.12, combined 66.45
- XLM: energy 64.13, combined 65.11
- POL: energy 64.0, combined 57.55
- ICP: energy 63.35, combined 64.12
- FET: energy 63.16, combined 61.56

## Too Late / Already Extended

- VVV: EXTREME_VOLUME_SPIKE
- TRUMP: UPPER_RANGE_POSITION
- STX: UPPER_RANGE_POSITION, EXTREME_VOLUME_SPIKE
- XRP: EXTREME_VOLUME_SPIKE
- INJ: UPPER_RANGE_POSITION

## PUMP Retrospective

- {"asset": "PUMP", "earliest_eligible_timestamp": "2026-08-15", "energy_delta": 51.86, "later_observed_moves": [{"date": "2026-08-16", "return_24h_pct": -1.5417712441735287, "return_48h_pct": -2.5204117855874952}, {"date": "2026-08-17", "return_24h_pct": 5.959780621572208, "return_48h_pct": 2.5840707964601917}], "look_ahead_used_for_detection": false, "price": 0.002775, "result": "PRE_MOVE_BUILDING", "score": 62.85, "state": "PRE_MOVE_BUILDING"}

## TAO Retrospective

- {"asset": "TAO", "earliest_eligible_timestamp": "2026-08-13", "energy_delta": 64.44, "later_observed_moves": [{"date": "2026-08-14", "return_24h_pct": -0.16260734370330265, "return_48h_pct": -2.1977659662941407}, {"date": "2026-08-15", "return_24h_pct": 0.5361227529213641, "return_48h_pct": -1.6682389897969108}], "look_ahead_used_for_detection": false, "price": 202.1458, "result": "PRE_MOVE_BUILDING", "score": 74.22, "state": "PRE_MOVE_BUILDING"}

## Methodology

- Current-state score combines eight explicitly weighted components.
- Energy Delta compares only the current report with an earlier available snapshot.
- Combined score weights current state at 65% and Energy Delta at 35%.
- Confirmed breakouts and extended moves are excluded from the pre-move ranking.
- Rankings use deterministic asset-symbol tie-breaking.
- The target research horizon is 12–48 hours for a 3–5% move.

## Source Coverage

- Daily Consolidation: current structure and range position.
- Range Quality Index: structural quality and daily change.
- Range Personality: historical sample quality.
- Relative Strength: rank, returns, acceleration, and persistence.
- Momentum Breakout Radar: stage, volatility, volume, and extension.
- Capital Flow: broad environment alignment.
- BTC Rotation and Chief Strategist: supplementary evidence changes.

## Limitations

- Uses existing canonical reports only; it does not rebuild source indicators.
- Energy Delta is neutral when no prior snapshot exists.
- Confidence is evidence quality, not probability.
- Retrospective detection uses only information available at each evaluated timestamp.
- No execution action is authorized.
