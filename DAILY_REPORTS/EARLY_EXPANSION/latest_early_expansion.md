# Early Expansion Engine V1

RESEARCH_ONLY | NOT_A_BUY_SIGNAL | NOT_A_SELL_SIGNAL | USER_DECISION_REQUIRED | LIVE_NOT_AUTHORIZED

## Market Summary

- State: PRE_MOVE_CONDITIONS_PRESENT
- Assets evaluated: 58
- Pre-move candidates: 1
- PRE_MOVE_STRONG: 0
- PRE_MOVE_BUILDING: 0
- Too late: 16

## Top Pre-Move Candidates

### AKE
- Classification: EARLY_EXPANSION_DEVELOPING | combined: 58.15 | energy: 50.0
- Confidence: 69 (MEDIUM)
- Range position: 6.157128749270145% | 24h return: -28.554831987496755% | breakout distance: 45.4948%
- Main strength: range_position
- Primary risk: volatility_compression

## Fastest Energy Build

- XMR: energy 60.35, combined 58.33
- AKE: energy 50.0, combined 58.15
- EURC: energy 41.04, combined 55.19
- CRV: energy 40.85, combined 54.07
- TIA: energy 40.27, combined 50.96

## Too Late / Already Extended

- PEPE: RETURN_24H_EXCEEDED, RETURN_48H_EXCEEDED, UPPER_RANGE_POSITION
- KAS: EXTREME_VOLUME_SPIKE
- ASTER: UPPER_RANGE_POSITION
- TAO: UPPER_RANGE_POSITION
- DOGE: UPPER_RANGE_POSITION

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
