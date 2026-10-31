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

### XDC
- Classification: PRE_MOVE_BUILDING | combined: 73.18 | energy: 58.43
- Confidence: 69 (MEDIUM)
- Range position: 10.669975186104217% | 24h return: 0.5734310289901234% | breakout distance: 10.8192%
- Main strength: range_position
- Primary risk: capital_flow_alignment

### QNT
- Classification: PRE_MOVE_BUILDING | combined: 70.7 | energy: 60.07
- Confidence: 69 (MEDIUM)
- Range position: 57.85263705534241% | 24h return: 1.9497738262361564% | breakout distance: 12.2763%
- Main strength: momentum_precursor
- Primary risk: range_position

### XMR
- Classification: PRE_MOVE_BUILDING | combined: 66.55 | energy: 62.89
- Confidence: 69 (MEDIUM)
- Range position: 39.26955397543637% | 24h return: 1.513264522733082% | breakout distance: 8.3739%
- Main strength: data_quality
- Primary risk: volume_buildup

### BNB
- Classification: PRE_MOVE_BUILDING | combined: 62.54 | energy: 59.0
- Confidence: 69 (MEDIUM)
- Range position: 1.9556820491969713% | 24h return: 0.779662956710836% | breakout distance: 7.7726%
- Main strength: range_position
- Primary risk: volume_buildup

### ASTER
- Classification: PRE_MOVE_BUILDING | combined: 60.03 | energy: 56.34
- Confidence: 66 (MEDIUM)
- Range position: 27.107415850878514% | 24h return: 1.506019679439241% | breakout distance: 5.322%
- Main strength: range_position
- Primary risk: volume_buildup

## Fastest Energy Build

- XMR: energy 62.89, combined 66.55
- QNT: energy 60.07, combined 70.7
- BNB: energy 59.0, combined 62.54
- XDC: energy 58.43, combined 73.18
- ASTER: energy 56.34, combined 60.03

## Too Late / Already Extended

- SKY: UPPER_RANGE_POSITION
- STX: RETURN_24H_EXCEEDED, RETURN_48H_EXCEEDED, UPPER_RANGE_POSITION, HIGH_EXTENSION_RISK, EXTENDED_MOVE, EXTREME_VOLUME_SPIKE, EMA_ATR_EXTENSION
- XPL: RETURN_24H_EXCEEDED, UPPER_RANGE_POSITION

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
