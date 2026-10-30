# Early Expansion Engine V1

RESEARCH_ONLY | NOT_A_BUY_SIGNAL | NOT_A_SELL_SIGNAL | USER_DECISION_REQUIRED | LIVE_NOT_AUTHORIZED

## Market Summary

- State: PRE_MOVE_CONDITIONS_PRESENT
- Assets evaluated: 68
- Pre-move candidates: 8
- PRE_MOVE_STRONG: 0
- PRE_MOVE_BUILDING: 6
- Too late: 4

## Top Pre-Move Candidates

### SPX
- Classification: PRE_MOVE_BUILDING | combined: 74.63 | energy: 68.82
- Confidence: 69 (MEDIUM)
- Range position: 35.083333333333385% | 24h return: -9.041095890410954% | breakout distance: 12.464%
- Main strength: relative_strength_delta
- Primary risk: volume_buildup

### XRP
- Classification: PRE_MOVE_BUILDING | combined: 70.91 | energy: 68.54
- Confidence: 69 (MEDIUM)
- Range position: 3.9742096605711916% | 24h return: -4.206343141001145% | breakout distance: 6.6581%
- Main strength: range_position
- Primary risk: volume_buildup

### XDC
- Classification: PRE_MOVE_BUILDING | combined: 70.14 | energy: 67.25
- Confidence: 69 (MEDIUM)
- Range position: 12.53731343283582% | 24h return: -5.5622369212266936% | breakout distance: 11.2712%
- Main strength: range_position
- Primary risk: volume_buildup

### NIGHT
- Classification: PRE_MOVE_BUILDING | combined: 67.48 | energy: 61.17
- Confidence: 69 (MEDIUM)
- Range position: 47.752702446425104% | 24h return: -3.125000000000011% | breakout distance: 8.5674%
- Main strength: relative_strength_delta
- Primary risk: momentum_precursor

### ENA
- Classification: EARLY_EXPANSION_DEVELOPING | combined: 66.35 | energy: 49.35
- Confidence: 69 (MEDIUM)
- Range position: 17.244829886591006% | 24h return: -11.500701262272095% | breakout distance: 13.0055%
- Main strength: range_position
- Primary risk: cross_module_improvement

### MORPHO
- Classification: EARLY_EXPANSION_DEVELOPING | combined: 66.26 | energy: 42.67
- Confidence: 69 (MEDIUM)
- Range position: 27.640343123218003% | 24h return: -8.531490719359791% | breakout distance: 9.8328%
- Main strength: range_position
- Primary risk: cross_module_improvement

### LTC
- Classification: PRE_MOVE_BUILDING | combined: 62.66 | energy: 51.81
- Confidence: 69 (MEDIUM)
- Range position: 11.764705882352972% | 24h return: -4.985487450913439% | breakout distance: 6.8307%
- Main strength: range_position
- Primary risk: volume_buildup

### DASH
- Classification: PRE_MOVE_BUILDING | combined: 62.48 | energy: 51.66
- Confidence: 69 (MEDIUM)
- Range position: 4.511366991437925% | 24h return: -5.129051038230159% | breakout distance: 12.3292%
- Main strength: range_position
- Primary risk: volume_buildup

## Fastest Energy Build

- SPX: energy 68.82, combined 74.63
- XRP: energy 68.54, combined 70.91
- XDC: energy 67.25, combined 70.14
- NIGHT: energy 61.17, combined 67.48
- LTC: energy 51.81, combined 62.66

## Too Late / Already Extended

- BCH: UPPER_RANGE_POSITION
- POL: UPPER_RANGE_POSITION
- XPL: UPPER_RANGE_POSITION
- PEPE: UPPER_RANGE_POSITION

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
