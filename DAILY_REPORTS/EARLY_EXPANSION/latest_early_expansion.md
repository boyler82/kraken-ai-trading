# Early Expansion Engine V1

RESEARCH_ONLY | NOT_A_BUY_SIGNAL | NOT_A_SELL_SIGNAL | USER_DECISION_REQUIRED | LIVE_NOT_AUTHORIZED

## Market Summary

- State: PRE_MOVE_CONDITIONS_PRESENT
- Assets evaluated: 69
- Pre-move candidates: 12
- PRE_MOVE_STRONG: 1
- PRE_MOVE_BUILDING: 11
- Too late: 0

## Top Pre-Move Candidates

### RAY
- Classification: PRE_MOVE_STRONG | combined: 77.53 | energy: 69.57
- Confidence: 69 (MEDIUM)
- Range position: 17.257597684515144% | 24h return: -2.7972027972028024% | breakout distance: 13.125%
- Main strength: range_position
- Primary risk: relative_strength_delta

### CRV
- Classification: PRE_MOVE_BUILDING | combined: 72.53 | energy: 77.59
- Confidence: 69 (MEDIUM)
- Range position: 8.877578690473774% | 24h return: -2.268462302682417% | breakout distance: 13.54%
- Main strength: range_position
- Primary risk: volume_buildup

### PENDLE
- Classification: PRE_MOVE_BUILDING | combined: 71.38 | energy: 75.9
- Confidence: 69 (MEDIUM)
- Range position: 11.22031122031126% | 24h return: -4.7345767575322935% | breakout distance: 10.1083%
- Main strength: range_position
- Primary risk: relative_strength_delta

### POL
- Classification: PRE_MOVE_BUILDING | combined: 71.03 | energy: 61.25
- Confidence: 69 (MEDIUM)
- Range position: 0.22573363431152987% | 24h return: -1.9601437438745428% | breakout distance: 7.7372%
- Main strength: range_position
- Primary risk: capital_flow_alignment

### ASTER
- Classification: PRE_MOVE_BUILDING | combined: 70.38 | energy: 61.88
- Confidence: 69 (MEDIUM)
- Range position: 20.442700708555485% | 24h return: -2.1204350766456104% | breakout distance: 4.3652%
- Main strength: range_position
- Primary risk: relative_strength_delta

### WLD
- Classification: PRE_MOVE_BUILDING | combined: 68.93 | energy: 59.0
- Confidence: 69 (MEDIUM)
- Range position: 0.22163120567373465% | 24h return: -13.240223463687162% | breakout distance: 22.0251%
- Main strength: range_position
- Primary risk: volatility_compression

### XMR
- Classification: PRE_MOVE_BUILDING | combined: 67.51 | energy: 58.37
- Confidence: 69 (MEDIUM)
- Range position: 32.74663511314894% | 24h return: -1.344032758734559% | breakout distance: 9.0203%
- Main strength: relative_strength_delta
- Primary risk: volume_buildup

### XPL
- Classification: PRE_MOVE_BUILDING | combined: 67.09 | energy: 62.46
- Confidence: 69 (MEDIUM)
- Range position: 2.675159235668815% | 24h return: -5.08259212198221% | breakout distance: 13.6416%
- Main strength: range_position
- Primary risk: volume_buildup

### PENGU
- Classification: PRE_MOVE_BUILDING | combined: 64.55 | energy: 57.43
- Confidence: 69 (MEDIUM)
- Range position: 39.681838267786176% | 24h return: -5.850540806293003% | breakout distance: 8.8963%
- Main strength: data_quality
- Primary risk: volume_buildup

### PUMP
- Classification: PRE_MOVE_BUILDING | combined: 64.42 | energy: 54.33
- Confidence: 69 (MEDIUM)
- Range position: 7.183908045976999% | 24h return: -9.24842971626596% | breakout distance: 19.701%
- Main strength: range_position
- Primary risk: volume_buildup

## Fastest Energy Build

- CRV: energy 77.59, combined 72.53
- PENDLE: energy 75.9, combined 71.38
- RAY: energy 69.57, combined 77.53
- XPL: energy 62.46, combined 67.09
- ASTER: energy 61.88, combined 70.38

## Too Late / Already Extended


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
