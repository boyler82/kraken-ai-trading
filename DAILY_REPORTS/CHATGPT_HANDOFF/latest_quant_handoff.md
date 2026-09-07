# Daily Quant ChatGPT Handoff

Run: 2026-09-07T14:03:46.046777+00:00
Pipeline status: OK
Market-data cutoff: 2026-09-07T13:00:00+00:00

## System Health

{"clock_safety": "SAFE", "coverage": {"candidates": 12, "live_prices": 12}, "module_failures": [], "required_missing": [], "stale_inputs": [], "warnings": []}

## Market State

{"breadth": {"above_ema20_pct": 87.5, "above_ema50_pct": 87.5, "assets_ema20": 64, "assets_ema50": 64}, "btc_structure": {"1h": {"distance_from_swing_high_pct": -0.4928, "distance_from_swing_low_pct": 0.6493, "recent_swing_high": 80541.2, "recent_swing_low": 79627.3, "trend": "MIXED"}, "4h": {"distance_from_swing_high_pct": -0.4928, "distance_from_swing_low_pct": 1.1449, "recent_swing_high": 80541.2, "recent_swing_low": 79237.1, "trend": "MIXED"}}, "capital_flow": {"capital_flow_confidence": 30, "derived_proxy": "group breadth and relative performance", "inference_disclaimer": "Inferred proxy; not direct measurement of capital transfers", "observed_data": "completed-candle returns and volumes", "primary_state": "NO_CLEAR_FLOW"}, "market_transition_state": "CONSOLIDATION", "regime": "BEAR", "sell_pressure": {"12h": {"classification": "INCREASING", "ratio": 0.7264}, "4h": {"classification": "DECLINING", "ratio": 0.1552}}}

## Changes Since Previous Independent Observation

[{"current": "CONSOLIDATION", "field": "market_state", "previous": "HEALTHY_PULLBACK"}, {"current": 87.5, "field": "breadth_above_ema20_pct", "previous": 89.0625}]

## Research Memory

{"statistical_warnings": ["OOS_NOT_FOR_OPTIMIZATION", "MULTIPLE_TESTING_RISK", "DATA_SNOOPING_RISK", "CORRELATED_VARIANT_SAMPLE", "REGIME_IMBALANCE"], "status": "AVAILABLE", "strategies": [{"ev_95_ci_pct": [0.8109571866492268, 1.172391283300776], "expected_value_pct": 0.9931289585000284, "oos_n": 910, "profit_factor": 2.0770651724984726, "strategy": "MULTI_TP4_SL2", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [0.3293635427637033, 0.9348246219701883], "expected_value_pct": 0.6355159796033523, "oos_n": 206, "profit_factor": 1.7571945502335373, "strategy": "MOMENTUM_TP3_SL2", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [1.1524340126973809, 2.03470817988732], "expected_value_pct": 1.5943858947168916, "oos_n": 201, "profit_factor": 2.6868035672936004, "strategy": "MOMENTUM_STRUCTURE_EXIT", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [1.1524340126973809, 2.03470817988732], "expected_value_pct": 1.5943858947168916, "oos_n": 201, "profit_factor": 2.6868035672936004, "strategy": "MOMENTUM_TP5_SL2", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [-0.5073611913192948, 0.3277731828697821], "expected_value_pct": -0.10923066755677412, "oos_n": 116, "profit_factor": 0.8809355192780012, "strategy": "RANGE_MIDPOINT", "validation_status": "OOS_NEGATIVE"}], "warnings": ["MULTIPLE_TESTING_RISK", "DATA_SNOOPING_RISK", "CORRELATED_VARIANT_SAMPLE", "REGIME_IMBALANCE"]}

## Strategy Evidence

[{"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [0.19457915215833654, 1.8210940152436992], "diagnostic_effective_n": 43.968799989873546, "ev_pct": 0.9931289585000284, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.8129668028219322, 1.173048328941761], "raw_n": 910, "regime_coverage": ["BEAR"], "strategy": "MULTI_TP4_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.2556620567472062, 1.0648721044044522], "diagnostic_effective_n": 36.732429300694115, "ev_pct": 0.32528778669727815, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.13271457327747174, 0.7668998797571139], "raw_n": 86, "regime_coverage": ["BEAR"], "strategy": "EE_TP3_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [0.4517804509419922, 2.9958857069203333], "diagnostic_effective_n": 34.099229810302695, "ev_pct": 1.626402197385279, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.7205205991271495, 2.564764655077684], "raw_n": 81, "regime_coverage": ["BEAR"], "strategy": "EE_DYNAMIC_BREAKOUT"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.7804019784156891, 0.46319406460574963], "diagnostic_effective_n": 83.67557099156645, "ev_pct": -0.10923066755677412, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.5089397894089575, 0.33219911454885315], "raw_n": 116, "regime_coverage": ["BEAR"], "strategy": "RANGE_MIDPOINT"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [0.01837128940973922, 2.479571233507036], "diagnostic_effective_n": 53.898903481170684, "ev_pct": 1.3134447027056315, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.5660799025010296, 2.100185099529878], "raw_n": 104, "regime_coverage": ["BEAR"], "strategy": "RANGE_HIGH"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.42998794005385044, 1.0215182230748736], "diagnostic_effective_n": 35.908405443709704, "ev_pct": 0.2685061623517092, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.14408970593127335, 0.6771743594007787], "raw_n": 112, "regime_coverage": ["BEAR"], "strategy": "RANGE_FIXED_3"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.19785560587752932, 1.3723063670896885], "diagnostic_effective_n": 32.06747024228981, "ev_pct": 0.6355159796033523, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.3177126928571474, 0.9406606607775801], "raw_n": 206, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_TP3_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.11567149952141839, 1.567252452196434], "diagnostic_effective_n": 27.88791379562206, "ev_pct": 0.6265213372678754, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "naive_ci_pct": [0.06520028524250834, 1.1922990961400357], "raw_n": 82, "regime_coverage": ["BEAR"], "strategy": "EE_TP4_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [0.08121121146154246, 2.395544777687984], "diagnostic_effective_n": 27.484719391345347, "ev_pct": 1.2146332163103581, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "naive_ci_pct": [0.6099352927833396, 1.7918033971714906], "raw_n": 108, "regime_coverage": ["BEAR"], "strategy": "RANGE_FIXED_5"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.09979485471990372, 1.8790721780836868], "diagnostic_effective_n": 25.67168385105306, "ev_pct": 0.8039160428636329, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "naive_ci_pct": [0.14093160257804913, 1.4226735576398168], "raw_n": 81, "regime_coverage": ["BEAR"], "strategy": "EE_TP5_SL2"}, {"alias_group": "ALIAS_008", "alias_status": "EXECUTION_IDENTICAL_ALIAS", "classification": "RESEARCH", "cluster_aware_ci_pct": [0.3627388445173971, 2.80115720453402], "diagnostic_effective_n": 30.18439240551279, "ev_pct": 1.5943858947168916, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "naive_ci_pct": [1.1605569849270279, 2.0442821949287926], "raw_n": 201, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_STRUCTURE_EXIT"}, {"alias_group": "ALIAS_008", "alias_status": "EXECUTION_IDENTICAL_ALIAS", "classification": "RESEARCH", "cluster_aware_ci_pct": [0.3627388445173971, 2.80115720453402], "diagnostic_effective_n": 30.18439240551279, "ev_pct": 1.5943858947168916, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "naive_ci_pct": [1.1605569849270279, 2.0442821949287926], "raw_n": 201, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_TP5_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_10D"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_3D"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_5D"}]

## FORWARD VALIDATION BOARD

[{"aliases": [], "execution_hash_short": "422eaf08bf98", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.2556620567472062, 1.0648721044044522], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP3_SL2"}, {"aliases": [], "execution_hash_short": "71fb28e84ea7", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.19785560587752932, 1.3723063670896885], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MOMENTUM_TP3_SL2"}, {"aliases": [], "execution_hash_short": "7b50c9d06d56", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.42998794005385044, 1.0215182230748736], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_FIXED_3"}, {"aliases": [], "execution_hash_short": "9ce597d35a2a", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.11567149952141839, 1.567252452196434], "independent_forward_clusters": 0, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP4_SL2"}, {"aliases": [], "execution_hash_short": "a5e1f74d016e", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [0.19457915215833654, 1.8210940152436992], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MULTI_TP4_SL2"}, {"aliases": [], "execution_hash_short": "a67e1c4c6b2f", "forward_clustered_ci_95": [-2.4000000000000075, -2.399999999999996], "forward_completed_outcomes": 8, "forward_ev_pct": -2.4000000000000017, "governance_state": "COLLECTING", "historical_clustered_ci_95": [0.08121121146154246, 2.395544777687984], "independent_forward_clusters": 1, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "next_required_evidence": "completed outcomes 8/50; independent clusters 1/20", "regime_coverage": [], "strategy": "RANGE_FIXED_5"}, {"aliases": [], "execution_hash_short": "acc076b635e7", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_10D"}, {"aliases": ["MOMENTUM_TP5_SL2"], "execution_hash_short": "c71f362e36dd", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [0.3627388445173971, 2.80115720453402], "independent_forward_clusters": 0, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MOMENTUM_STRUCTURE_EXIT"}, {"aliases": [], "execution_hash_short": "d0f1e752c2a1", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "CANDIDATE_FOR_FREEZE", "historical_clustered_ci_95": [0.4517804509419922, 2.9958857069203333], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_DYNAMIC_BREAKOUT"}, {"aliases": [], "execution_hash_short": "d4c1126e41a5", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.7804019784156891, 0.46319406460574963], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_MIDPOINT"}, {"aliases": [], "execution_hash_short": "d55bce5c8e3b", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.09979485471990372, 1.8790721780836868], "independent_forward_clusters": 0, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP5_SL2"}, {"aliases": [], "execution_hash_short": "e866f21be395", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_3D"}, {"aliases": [], "execution_hash_short": "e9ed863fd44d", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [0.01837128940973922, 2.479571233507036], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_HIGH"}, {"aliases": [], "execution_hash_short": "f50c2081eebd", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_5D"}]

## Current Candidates

### PUMP
- Analysis snapshot price/time: 0.00437 / 2026-09-07T13:00:00+00:00
- Kraken live reference/time: 0.004338 / 2026-09-07T14:06:08.630486+00:00
- Setup quality: {'score': 70.76, 'state': 'EARLY_MOMENTUM'}
- Evidence quality: {'score': 53.2468, 'band': 'MEDIUM', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 57.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_BREAKOUT'}
- Expected edge: {'value': 4.578782086950284, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / CLOSE_BELOW_LOCAL_SWING_LOW
### LTC
- Analysis snapshot price/time: 57.47 / 2026-09-07T13:00:00+00:00
- Kraken live reference/time: 57.22 / 2026-09-07T14:06:08.630486+00:00
- Setup quality: {'score': 27.97, 'state': 'EARLY_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 64.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_BREAKOUT'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / CLOSE_BELOW_LOCAL_SWING_LOW
### TRUMP
- Analysis snapshot price/time: 2.286 / 2026-09-07T13:00:00+00:00
- Kraken live reference/time: 2.2755 / 2026-09-07T14:06:08.630486+00:00
- Setup quality: {'score': 59.04, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 34.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_PULLBACK'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### ATOM
- Analysis snapshot price/time: 1.665 / 2026-09-07T13:00:00+00:00
- Kraken live reference/time: 1.67075 / 2026-09-07T14:06:08.630486+00:00
- Setup quality: {'score': 48.22, 'state': 'BREAKOUT_DEVELOPING'}
- Evidence quality: {'score': 40.0, 'band': 'LOW', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 67.0, 'recommendation': 'ACTIONABLE', 'technical_action': 'BUY_ON_BREAKOUT'}
- Expected edge: {'value': 6.349575559576115, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / CLOSE_BELOW_LOCAL_SWING_LOW
### ADA
- Analysis snapshot price/time: 0.22267 / 2026-09-07T13:00:00+00:00
- Kraken live reference/time: 0.2213995 / 2026-09-07T14:06:08.630486+00:00
- Setup quality: {'score': 65.02, 'state': 'BREAKOUT_DEVELOPING'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 76.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_BREAKOUT'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / CLOSE_BELOW_LOCAL_SWING_LOW
### AKE
- Analysis snapshot price/time: 0.01659953 / 2026-09-07T13:00:00+00:00
- Kraken live reference/time: 0.01679435 / 2026-09-07T14:06:08.630486+00:00
- Setup quality: {'score': 24.16, 'state': 'EXTENDED_MOVE'}
- Evidence quality: {'score': 22.0779, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 0.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### APT
- Analysis snapshot price/time: 0.6415 / 2026-09-07T13:00:00+00:00
- Kraken live reference/time: 0.6428499999999999 / 2026-09-07T14:06:08.630486+00:00
- Setup quality: {'score': 35.53, 'state': 'EARLY_MOMENTUM'}
- Evidence quality: {'score': 22.0779, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 57.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / CLOSE_BELOW_LOCAL_SWING_LOW
### DOT
- Analysis snapshot price/time: 1.0576 / 2026-09-07T13:00:00+00:00
- Kraken live reference/time: 1.0692 / 2026-09-07T14:06:08.630486+00:00
- Setup quality: {'score': 37.82, 'state': 'BREAKOUT_CONFIRMED'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 79.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / CLOSE_BELOW_BREAKOUT_LEVEL
### HBAR
- Analysis snapshot price/time: 0.08292 / 2026-09-07T13:00:00+00:00
- Kraken live reference/time: 0.08257 / 2026-09-07T14:06:08.630486+00:00
- Setup quality: {'score': 65.32, 'state': 'BREAKOUT_DEVELOPING'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 80.0, 'recommendation': 'ACTIONABLE', 'technical_action': 'BUY_ON_BREAKOUT'}
- Expected edge: {'value': 1.861820696418393, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / CLOSE_BELOW_LOCAL_SWING_LOW
### TIA
- Analysis snapshot price/time: 0.4353 / 2026-09-07T13:00:00+00:00
- Kraken live reference/time: 0.43445 / 2026-09-07T14:06:08.630486+00:00
- Setup quality: {'score': 34.47, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 19.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### AAVE
- Analysis snapshot price/time: 133.07 / 2026-09-07T13:00:00+00:00
- Kraken live reference/time: 132.985 / 2026-09-07T14:06:08.630486+00:00
- Setup quality: {'score': 51.83, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 33.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### AERO
- Analysis snapshot price/time: 0.5393 / 2026-09-07T13:00:00+00:00
- Kraken live reference/time: 0.5381 / 2026-09-07T14:06:08.630486+00:00
- Setup quality: {'score': 28.88, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 33.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale

## Forward Experiments

- {"activation_state": "COLLECTING", "batch_dependence_warnings": ["SIMULTANEOUS_SIGNAL_COUNT_IS_BATCH_DEPENDENT"], "completed_outcomes": 8, "experiment_name": "RANGE_FIXED_5_FORWARD_V2", "monitoring_health": "SAFE", "official_monitor_runner": "AVAILABLE_NOT_RUN_READ_ONLY_ORCHESTRATOR", "open_observations": 0, "signals": 8, "trading_capability": "DISABLED"}

## Conflicts

- {"asset": "PUMP", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED", "HIGH_SCORE + INVALID_RANGE"]}
- {"asset": "LTC", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}
- {"asset": "TRUMP", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}
- {"asset": "ATOM", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}
- {"asset": "ADA", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}
- {"asset": "HBAR", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}

## What We Do Not Know

- {"affected_conclusion": "Expected success likelihood", "asset": "MARKET", "available_workaround": "Use scenario analysis rather than probability claims", "unknown": "NO_VALIDATED_PROBABILITY", "why_it_matters": "Evidence confidence is not outcome probability"}
- {"affected_conclusion": "Net rotation edge", "asset": "MARKET", "available_workaround": "Stress-test higher costs", "unknown": "UNCERTAIN_SLIPPAGE", "why_it_matters": "Realized execution costs may differ"}
- {"affected_conclusion": "Capital-flow inference", "asset": "MARKET", "available_workaround": "Treat inferred flow confidence conservatively", "unknown": "NO_DERIVATIVES_OR_ON_CHAIN_DATA", "why_it_matters": "Positioning and flow proxies are incomplete"}

## Next Research Checks

- Observe the next completed market-data cutoff.
- Check stale inputs and technical activation/invalidation conditions.
- Accumulate independent OOS and forward outcomes; do not infer validation from actionability.
