# Daily Quant ChatGPT Handoff

Run: 2026-09-17T15:25:31.514851+00:00
Pipeline status: OK_WITH_WARNINGS
Market-data cutoff: 2026-09-17T14:00:00+00:00

## System Health

{"clock_safety": "SAFE", "coverage": {"candidates": 12, "live_prices": 12}, "module_failures": [], "required_missing": [], "stale_inputs": [], "warnings": ["INSUFFICIENT_INDEPENDENT_OBSERVATIONS"]}

## Market State

{"breadth": {"above_ema20_pct": 90.7692, "above_ema50_pct": 81.5385, "assets_ema20": 65, "assets_ema50": 65}, "btc_structure": {"1h": {"distance_from_swing_high_pct": -0.6264, "distance_from_swing_low_pct": 0.6695, "recent_swing_high": 77095.3, "recent_swing_low": 76102.9, "trend": "MIXED"}, "4h": {"distance_from_swing_high_pct": -0.1201, "distance_from_swing_low_pct": 2.2082, "recent_swing_high": 76704.5, "recent_swing_low": 74957.2, "trend": "MIXED"}}, "capital_flow": {"capital_flow_confidence": 30, "derived_proxy": "group breadth and relative performance", "inference_disclaimer": "Inferred proxy; not direct measurement of capital transfers", "observed_data": "completed-candle returns and volumes", "primary_state": "NO_CLEAR_FLOW"}, "market_transition_state": "CONSOLIDATION", "regime": "BEAR", "sell_pressure": {"12h": {"classification": "INCREASING", "ratio": 1.2953}, "4h": {"classification": "NORMAL", "ratio": 1.1942}}}

## Changes Since Previous Independent Observation

[]

## Research Memory

{"statistical_warnings": ["OOS_NOT_FOR_OPTIMIZATION", "MULTIPLE_TESTING_RISK", "DATA_SNOOPING_RISK", "CORRELATED_VARIANT_SAMPLE", "REGIME_IMBALANCE"], "status": "AVAILABLE", "strategies": [{"ev_95_ci_pct": [0.20989466969307588, 0.49001249971473476], "expected_value_pct": 0.35344128415116066, "oos_n": 1553, "profit_factor": 1.2945280055033461, "strategy": "MULTI_TP4_SL2", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [-0.3641211466440402, 0.15544288610980425], "expected_value_pct": -0.10191185181640948, "oos_n": 322, "profit_factor": 0.9165597155028107, "strategy": "MOMENTUM_TP3_SL2", "validation_status": "OOS_NEGATIVE"}, {"ev_95_ci_pct": [0.23220521000461342, 0.9579822242706897], "expected_value_pct": 0.5810149947900483, "oos_n": 321, "profit_factor": 1.4386692083232508, "strategy": "MOMENTUM_STRUCTURE_EXIT", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [0.23220521000461342, 0.9579822242706897], "expected_value_pct": 0.5810149947900483, "oos_n": 321, "profit_factor": 1.4386692083232508, "strategy": "MOMENTUM_TP5_SL2", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [-0.38584169908840815, 0.20151108132453224], "expected_value_pct": -0.08785891857902019, "oos_n": 239, "profit_factor": 0.9253771112390715, "strategy": "RANGE_FIXED_3", "validation_status": "OOS_NEGATIVE"}], "warnings": ["MULTIPLE_TESTING_RISK", "DATA_SNOOPING_RISK", "CORRELATED_VARIANT_SAMPLE", "REGIME_IMBALANCE"]}

## Strategy Evidence

[{"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [0.41445449227253545, 2.1318349194473676], "diagnostic_effective_n": 164.0, "ev_pct": 1.2388920258794933, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.44181788918692577, 2.12669229733436], "raw_n": 164, "regime_coverage": ["BEAR"], "strategy": "EE_DYNAMIC_BREAKOUT"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.6666886220975257, 1.0851846467455557], "diagnostic_effective_n": 142.71150058585582, "ev_pct": 0.13396036706400832, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.4460691973544438, 0.7790064353153353], "raw_n": 228, "regime_coverage": ["BEAR"], "strategy": "RANGE_HIGH"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.8090752190015186, 0.25527033511950875], "diagnostic_effective_n": 111.37840843515295, "ev_pct": -0.27687814390546067, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.5976394724714638, 0.05424347112374764], "raw_n": 239, "regime_coverage": ["BEAR"], "strategy": "RANGE_MIDPOINT"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.1942204561380379, 0.9728926025979736], "diagnostic_effective_n": 63.56277901981397, "ev_pct": 0.35344128415116066, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.21085038970034703, 0.4900054979910988], "raw_n": 1553, "regime_coverage": ["BEAR"], "strategy": "MULTI_TP4_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.6511480194147209, 0.3779279271773184], "diagnostic_effective_n": 58.51951575493805, "ev_pct": -0.14524925940164476, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.4831781020715912, 0.18581959170948276], "raw_n": 169, "regime_coverage": ["BEAR"], "strategy": "EE_TP3_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.4829187168141481, 0.9235149596495834], "diagnostic_effective_n": 55.69807485643011, "ev_pct": 0.17514038887206007, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.24076285618693877, 0.5830183148070497], "raw_n": 234, "regime_coverage": ["BEAR"], "strategy": "RANGE_FIXED_5"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.32839127821117126, 1.016034666287104], "diagnostic_effective_n": 54.93895059921792, "ev_pct": 0.3316418040200868, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.11349776361966167, 0.7839014015084886], "raw_n": 168, "regime_coverage": ["BEAR"], "strategy": "EE_TP5_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.44967731789696636, 0.7761452160305035], "diagnostic_effective_n": 54.37069784817491, "ev_pct": 0.1410831678129912, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.24972177831919404, 0.5435327065402644], "raw_n": 169, "regime_coverage": ["BEAR"], "strategy": "EE_TP4_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.73193163186161, 0.5561113705213492], "diagnostic_effective_n": 48.100346505091174, "ev_pct": -0.08785891857902019, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.3841216625341138, 0.20722551384966412], "raw_n": 239, "regime_coverage": ["BEAR"], "strategy": "RANGE_FIXED_3"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.8258748105407452, 0.7635965378635788], "diagnostic_effective_n": 34.34573949101017, "ev_pct": -0.10191185181640948, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.34970470860635294, 0.16273447962246662], "raw_n": 322, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_TP3_SL2"}, {"alias_group": "ALIAS_008", "alias_status": "EXECUTION_IDENTICAL_ALIAS", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.41602575318786633, 1.8885190540163346], "diagnostic_effective_n": 32.68592521028404, "ev_pct": 0.5810149947900483, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "naive_ci_pct": [0.224689043703523, 0.9461131692966317], "raw_n": 321, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_STRUCTURE_EXIT"}, {"alias_group": "ALIAS_008", "alias_status": "EXECUTION_IDENTICAL_ALIAS", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.41602575318786633, 1.8885190540163346], "diagnostic_effective_n": 32.68592521028404, "ev_pct": 0.5810149947900483, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "naive_ci_pct": [0.224689043703523, 0.9461131692966317], "raw_n": 321, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_TP5_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_10D"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_3D"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_5D"}]

## FORWARD VALIDATION BOARD

[{"aliases": [], "execution_hash_short": "422eaf08bf98", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.6511480194147209, 0.3779279271773184], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP3_SL2"}, {"aliases": [], "execution_hash_short": "71fb28e84ea7", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.8258748105407452, 0.7635965378635788], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MOMENTUM_TP3_SL2"}, {"aliases": [], "execution_hash_short": "7b50c9d06d56", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.73193163186161, 0.5561113705213492], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_FIXED_3"}, {"aliases": [], "execution_hash_short": "9ce597d35a2a", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.44967731789696636, 0.7761452160305035], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP4_SL2"}, {"aliases": [], "execution_hash_short": "a5e1f74d016e", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.1942204561380379, 0.9728926025979736], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MULTI_TP4_SL2"}, {"aliases": [], "execution_hash_short": "a67e1c4c6b2f", "forward_clustered_ci_95": [-2.4000000000000075, -2.399999999999996], "forward_completed_outcomes": 8, "forward_ev_pct": -2.4000000000000017, "governance_state": "COLLECTING", "historical_clustered_ci_95": [-0.4829187168141481, 0.9235149596495834], "independent_forward_clusters": 1, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 8/50; independent clusters 1/20", "regime_coverage": [], "strategy": "RANGE_FIXED_5"}, {"aliases": [], "execution_hash_short": "acc076b635e7", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_10D"}, {"aliases": ["MOMENTUM_TP5_SL2"], "execution_hash_short": "c71f362e36dd", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.41602575318786633, 1.8885190540163346], "independent_forward_clusters": 0, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MOMENTUM_STRUCTURE_EXIT"}, {"aliases": [], "execution_hash_short": "d0f1e752c2a1", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "CANDIDATE_FOR_FREEZE", "historical_clustered_ci_95": [0.41445449227253545, 2.1318349194473676], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_DYNAMIC_BREAKOUT"}, {"aliases": [], "execution_hash_short": "d4c1126e41a5", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.8090752190015186, 0.25527033511950875], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_MIDPOINT"}, {"aliases": [], "execution_hash_short": "d55bce5c8e3b", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.32839127821117126, 1.016034666287104], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP5_SL2"}, {"aliases": [], "execution_hash_short": "e866f21be395", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_3D"}, {"aliases": [], "execution_hash_short": "e9ed863fd44d", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.6666886220975257, 1.0851846467455557], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_HIGH"}, {"aliases": [], "execution_hash_short": "f50c2081eebd", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_5D"}]

## Current Candidates

### ALGO
- Analysis snapshot price/time: 0.09067 / 2026-09-17T14:00:00+00:00
- Kraken live reference/time: 0.09045 / 2026-09-17T15:28:32.378843+00:00
- Setup quality: {'score': 78.2, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 53.2468, 'band': 'MEDIUM', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 34.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_PULLBACK'}
- Expected edge: {'value': 10.509112657221287, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / ALT/BTC closes below relative EMA20
### HYPE
- Analysis snapshot price/time: 82.16 / 2026-09-17T14:00:00+00:00
- Kraken live reference/time: 81.81 / 2026-09-17T15:28:32.378843+00:00
- Setup quality: {'score': 55.64, 'state': 'EARLY_MOMENTUM'}
- Evidence quality: {'score': 22.0779, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 67.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_BREAKOUT'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / CLOSE_BELOW_LOCAL_SWING_LOW
### FIL
- Analysis snapshot price/time: 0.823 / 2026-09-17T14:00:00+00:00
- Kraken live reference/time: 0.8165 / 2026-09-17T15:28:32.378843+00:00
- Setup quality: {'score': 48.71, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 27.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_PULLBACK'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### ATOM
- Analysis snapshot price/time: 1.5344 / 2026-09-17T14:00:00+00:00
- Kraken live reference/time: 1.53585 / 2026-09-17T15:28:32.378843+00:00
- Setup quality: {'score': 48.21, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 40.0, 'band': 'LOW', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 34.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': 6.349575559576115, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / ALT/BTC closes below relative EMA20
### DOT
- Analysis snapshot price/time: 1.0336 / 2026-09-17T14:00:00+00:00
- Kraken live reference/time: 1.03625 / 2026-09-17T15:28:32.378843+00:00
- Setup quality: {'score': 62.91, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 40.0, 'band': 'LOW', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 25.0, 'recommendation': 'HIGH_PRIORITY_WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': 5.446310533453747, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / ALT/BTC closes below relative EMA20
### ADA
- Analysis snapshot price/time: 0.2016 / 2026-09-17T14:00:00+00:00
- Kraken live reference/time: 0.20066099999999998 / 2026-09-17T15:28:32.378843+00:00
- Setup quality: {'score': 40.46, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 42.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### ETHFI
- Analysis snapshot price/time: 0.6131 / 2026-09-17T14:00:00+00:00
- Kraken live reference/time: 0.6168 / 2026-09-17T15:28:32.378843+00:00
- Setup quality: {'score': 40.06, 'state': 'EARLY_MOMENTUM'}
- Evidence quality: {'score': 22.0779, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 66.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_BREAKOUT'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / CLOSE_BELOW_LOCAL_SWING_LOW
### FET
- Analysis snapshot price/time: 0.1646 / 2026-09-17T14:00:00+00:00
- Kraken live reference/time: 0.16335 / 2026-09-17T15:28:32.378843+00:00
- Setup quality: {'score': 53.83, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 22.0779, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 34.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_PULLBACK'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### PUMP
- Analysis snapshot price/time: 0.00398 / 2026-09-17T14:00:00+00:00
- Kraken live reference/time: 0.0039395 / 2026-09-17T15:28:32.378843+00:00
- Setup quality: {'score': 22.46, 'state': 'FAILED_BREAKOUT'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 7.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / CLOSE_BELOW_LOCAL_SWING_LOW
### AAVE
- Analysis snapshot price/time: 125.33 / 2026-09-17T14:00:00+00:00
- Kraken live reference/time: 124.32499999999999 / 2026-09-17T15:28:32.378843+00:00
- Setup quality: {'score': 28.49, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 35.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### AERO
- Analysis snapshot price/time: 0.5928 / 2026-09-17T14:00:00+00:00
- Kraken live reference/time: 0.5902499999999999 / 2026-09-17T15:28:32.378843+00:00
- Setup quality: {'score': 3.4, 'state': 'EXTENDED_MOVE'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 0.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### AKE
- Analysis snapshot price/time: 0.02133126 / 2026-09-17T14:00:00+00:00
- Kraken live reference/time: 0.021153255 / 2026-09-17T15:28:32.378843+00:00
- Setup quality: {'score': 32.53, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 25.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale

## Forward Experiments

- {"activation_state": "COLLECTING", "batch_dependence_warnings": ["SIMULTANEOUS_SIGNAL_COUNT_IS_BATCH_DEPENDENT"], "completed_outcomes": 8, "experiment_name": "RANGE_FIXED_5_FORWARD_V2", "monitoring_health": "SAFE", "official_monitor_runner": "AVAILABLE_NOT_RUN_READ_ONLY_ORCHESTRATOR", "open_observations": 0, "signals": 8, "trading_capability": "DISABLED"}

## Conflicts

- {"asset": "ALGO", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED", "HIGH_SCORE + INVALID_RANGE"]}
- {"asset": "HYPE", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}
- {"asset": "FIL", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}
- {"asset": "ETHFI", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}
- {"asset": "FET", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}

## What We Do Not Know

- {"affected_conclusion": "Expected success likelihood", "asset": "MARKET", "available_workaround": "Use scenario analysis rather than probability claims", "unknown": "NO_VALIDATED_PROBABILITY", "why_it_matters": "Evidence confidence is not outcome probability"}
- {"affected_conclusion": "Net rotation edge", "asset": "MARKET", "available_workaround": "Stress-test higher costs", "unknown": "UNCERTAIN_SLIPPAGE", "why_it_matters": "Realized execution costs may differ"}
- {"affected_conclusion": "Capital-flow inference", "asset": "MARKET", "available_workaround": "Treat inferred flow confidence conservatively", "unknown": "NO_DERIVATIVES_OR_ON_CHAIN_DATA", "why_it_matters": "Positioning and flow proxies are incomplete"}

## Next Research Checks

- Observe the next completed market-data cutoff.
- Check stale inputs and technical activation/invalidation conditions.
- Accumulate independent OOS and forward outcomes; do not infer validation from actionability.
