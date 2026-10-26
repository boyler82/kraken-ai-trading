# Early Expansion Engine V1

RESEARCH_ONLY | NOT_A_BUY_SIGNAL | NOT_A_SELL_SIGNAL | USER_DECISION_REQUIRED | LIVE_NOT_AUTHORIZED

## Market Summary

- State: PRE_MOVE_CONDITIONS_PRESENT
- Assets evaluated: 65
- Pre-move candidates: 6
- PRE_MOVE_STRONG: 1
- PRE_MOVE_BUILDING: 5
- Too late: 15

## Top Pre-Move Candidates

### UNI
- Classification: PRE_MOVE_STRONG | combined: 79.53 | energy: 79.19
- Confidence: 69 (MEDIUM)
- Range position: 41.2680892813343% | 24h return: 1.5507552566147886% | breakout distance: 9.3245%
- Main strength: volume_buildup
- Primary risk: capital_flow_alignment

### PUMP
- Classification: PRE_MOVE_BUILDING | combined: 74.78 | energy: 71.42
- Confidence: 69 (MEDIUM)
- Range position: 19.886848847139145% | 24h return: -1.97928653624857% | breakout distance: 18.3787%
- Main strength: range_position
- Primary risk: capital_flow_alignment

### XMR
- Classification: PRE_MOVE_BUILDING | combined: 64.48 | energy: 52.22
- Confidence: 69 (MEDIUM)
- Range position: 25.033331343402214% | 24h return: -1.7302300890827849% | breakout distance: 9.7999%
- Main strength: range_position
- Primary risk: capital_flow_alignment

### CRV
- Classification: PRE_MOVE_BUILDING | combined: 63.72 | energy: 61.59
- Confidence: 69 (MEDIUM)
- Range position: 20.513540058930797% | 24h return: 0.633003281163802% | breakout distance: 15.3882%
- Main strength: range_position
- Primary risk: volatility_compression

### XRP
- Classification: PRE_MOVE_BUILDING | combined: 63.3 | energy: 55.93
- Confidence: 69 (MEDIUM)
- Range position: 21.20357886995948% | 24h return: -0.9407532149418141% | breakout distance: 7.4293%
- Main strength: range_position
- Primary risk: cross_module_improvement

### RAY
- Classification: PRE_MOVE_BUILDING | combined: 63.28 | energy: 62.19
- Confidence: 69 (MEDIUM)
- Range position: 37.57621951219514% | 24h return: -0.21798365122616126% | breakout distance: 11.9712%
- Main strength: data_quality
- Primary risk: relative_strength_delta

## Fastest Energy Build

- UNI: energy 79.19, combined 79.53
- PUMP: energy 71.42, combined 74.78
- RAY: energy 62.19, combined 63.28
- CRV: energy 61.59, combined 63.72
- XRP: energy 55.93, combined 63.3

## Too Late / Already Extended

- PENGU: EXTREME_VOLUME_SPIKE
- BONK: EXTREME_VOLUME_SPIKE
- HYPE: EXTREME_VOLUME_SPIKE
- BNB: UPPER_RANGE_POSITION
- PYTH: RETURN_48H_EXCEEDED

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
