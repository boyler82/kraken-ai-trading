# Early Expansion Engine V1

RESEARCH_ONLY | NOT_A_BUY_SIGNAL | NOT_A_SELL_SIGNAL | USER_DECISION_REQUIRED | LIVE_NOT_AUTHORIZED

## Market Summary

- State: PRE_MOVE_CONDITIONS_PRESENT
- Assets evaluated: 68
- Pre-move candidates: 3
- PRE_MOVE_STRONG: 0
- PRE_MOVE_BUILDING: 2
- Too late: 39

## Top Pre-Move Candidates

### DASH
- Classification: PRE_MOVE_BUILDING | combined: 72.22 | energy: 58.87
- Confidence: 69 (MEDIUM)
- Range position: 25.20214140668269% | 24h return: -2.4586617505972685% | breakout distance: 7.2183%
- Main strength: range_position
- Primary risk: volatility_compression

### NEAR
- Classification: PRE_MOVE_BUILDING | combined: 66.22 | energy: 65.21
- Confidence: 69 (MEDIUM)
- Range position: 65.17190503867299% | 24h return: 0.09363091997822703% | breakout distance: 8.2017%
- Main strength: data_quality
- Primary risk: volatility_compression

### PYTH
- Classification: EARLY_EXPANSION_DEVELOPING | combined: 58.01 | energy: 50.0
- Confidence: 69 (MEDIUM)
- Range position: 61.106046794287586% | 24h return: 1.426352210139803% | breakout distance: 6.4478%
- Main strength: volume_buildup
- Primary risk: cross_module_improvement

## Fastest Energy Build

- NEAR: energy 65.21, combined 66.22
- DASH: energy 58.87, combined 72.22
- ICP: energy 55.95, combined 58.46
- PYTH: energy 50.0, combined 58.01
- VIRTUAL: energy 50.0, combined 53.36

## Too Late / Already Extended

- PUMP: RETURN_24H_EXCEEDED, UPPER_RANGE_POSITION
- BONK: UPPER_RANGE_POSITION
- XMR: EMA_ATR_EXTENSION
- ONDO: UPPER_RANGE_POSITION
- PENGU: UPPER_RANGE_POSITION

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
