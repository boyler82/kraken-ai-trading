# Early Expansion Engine V1

RESEARCH_ONLY | NOT_A_BUY_SIGNAL | NOT_A_SELL_SIGNAL | USER_DECISION_REQUIRED | LIVE_NOT_AUTHORIZED

## Market Summary

- State: PRE_MOVE_CONDITIONS_PRESENT
- Assets evaluated: 69
- Pre-move candidates: 5
- PRE_MOVE_STRONG: 0
- PRE_MOVE_BUILDING: 5
- Too late: 3

## Top Pre-Move Candidates

### HYPE
- Classification: PRE_MOVE_BUILDING | combined: 66.02 | energy: 59.53
- Confidence: 69 (MEDIUM)
- Range position: 9.22558922558902% | 24h return: 0.3550762756443948% | breakout distance: 7.4469%
- Main strength: range_position
- Primary risk: volume_buildup

### ETH
- Classification: PRE_MOVE_BUILDING | combined: 64.64 | energy: 55.5
- Confidence: 69 (MEDIUM)
- Range position: 3.070022309144181% | 24h return: -1.4350283919141171% | breakout distance: 7.6611%
- Main strength: range_position
- Primary risk: volume_buildup

### KAS
- Classification: PRE_MOVE_BUILDING | combined: 63.84 | energy: 54.39
- Confidence: 69 (MEDIUM)
- Range position: 28.73303167420815% | 24h return: -0.4761904761904856% | breakout distance: 9.9595%
- Main strength: range_position
- Primary risk: relative_strength_delta

### PENDLE
- Classification: PRE_MOVE_BUILDING | combined: 63.39 | energy: 55.55
- Confidence: 69 (MEDIUM)
- Range position: 17.43295019157091% | 24h return: -0.8534136546184734% | breakout distance: 10.8755%
- Main strength: range_position
- Primary risk: volume_buildup

### LTC
- Classification: PRE_MOVE_BUILDING | combined: 61.26 | energy: 55.92
- Confidence: 69 (MEDIUM)
- Range position: -1.0439164866810615% | 24h return: -0.01776514478593061% | breakout distance: 9.7209%
- Main strength: range_position
- Primary risk: relative_strength_delta

## Fastest Energy Build

- HYPE: energy 59.53, combined 66.02
- LTC: energy 55.92, combined 61.26
- PENDLE: energy 55.55, combined 63.39
- ETH: energy 55.5, combined 64.64
- KAS: energy 54.39, combined 63.84

## Too Late / Already Extended

- DASH: UPPER_RANGE_POSITION
- GRASS: RETURN_24H_EXCEEDED, UPPER_RANGE_POSITION
- BNB: UPPER_RANGE_POSITION

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
