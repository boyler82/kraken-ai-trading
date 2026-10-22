# Early Expansion Engine V1

RESEARCH_ONLY | NOT_A_BUY_SIGNAL | NOT_A_SELL_SIGNAL | USER_DECISION_REQUIRED | LIVE_NOT_AUTHORIZED

## Market Summary

- State: PRE_MOVE_CONDITIONS_PRESENT
- Assets evaluated: 70
- Pre-move candidates: 6
- PRE_MOVE_STRONG: 0
- PRE_MOVE_BUILDING: 5
- Too late: 7

## Top Pre-Move Candidates

### TRX
- Classification: PRE_MOVE_BUILDING | combined: 65.97 | energy: 61.42
- Confidence: 69 (MEDIUM)
- Range position: 21.13346972426626% | 24h return: -1.2841665539677583% | breakout distance: 2.4652%
- Main strength: range_position
- Primary risk: volume_buildup

### DASH
- Classification: PRE_MOVE_BUILDING | combined: 65.17 | energy: 55.46
- Confidence: 69 (MEDIUM)
- Range position: 51.06968452057985% | 24h return: -4.914937406771025% | breakout distance: 6.9667%
- Main strength: momentum_precursor
- Primary risk: range_position

### DOT
- Classification: PRE_MOVE_BUILDING | combined: 64.48 | energy: 53.7
- Confidence: 69 (MEDIUM)
- Range position: 42.332123411978266% | 24h return: -4.541974993620812% | breakout distance: 7.3092%
- Main strength: data_quality
- Primary risk: momentum_precursor

### AAVE
- Classification: EARLY_EXPANSION_DEVELOPING | combined: 63.99 | energy: 47.15
- Confidence: 69 (MEDIUM)
- Range position: 2.9451137884871375% | 24h return: -7.581707626045098% | breakout distance: 11.9964%
- Main strength: range_position
- Primary risk: cross_module_improvement

### ARB
- Classification: PRE_MOVE_BUILDING | combined: 60.68 | energy: 50.58
- Confidence: 69 (MEDIUM)
- Range position: 29.741196436147703% | 24h return: -6.84156378600822% | breakout distance: 11.0511%
- Main strength: range_position
- Primary risk: momentum_precursor

### HYPE
- Classification: PRE_MOVE_BUILDING | combined: 60.61 | energy: 55.6
- Confidence: 69 (MEDIUM)
- Range position: 18.082964156262765% | 24h return: -4.83831152801778% | breakout distance: 6.6021%
- Main strength: range_position
- Primary risk: relative_strength_delta

## Fastest Energy Build

- TRX: energy 61.42, combined 65.97
- Q: energy 61.2, combined 51.44
- SOL: energy 58.4, combined 59.6
- INJ: energy 56.96, combined 59.7
- BNB: energy 56.61, combined 56.87

## Too Late / Already Extended

- ETH: EXTREME_VOLUME_SPIKE
- ICP: EXTREME_VOLUME_SPIKE
- ASTER: EXTREME_VOLUME_SPIKE
- ALGO: EXTREME_VOLUME_SPIKE
- VIRTUAL: EXTREME_VOLUME_SPIKE

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
