# Daily Quant ChatGPT Handoff

Run: 2026-10-12T17:01:36.858751+00:00
Pipeline status: OK
Market-data cutoff: 2026-10-12T16:00:00+00:00

## System Health

{"clock_safety": "SAFE", "coverage": {"candidates": 12, "live_prices": 12}, "module_failures": [], "required_missing": [], "stale_inputs": [], "warnings": []}

## Market State

{"breadth": {"above_ema20_pct": 4.1096, "above_ema50_pct": 13.6986, "assets_ema20": 73, "assets_ema50": 73}, "btc_structure": {"1h": {"distance_from_swing_high_pct": -0.456, "distance_from_swing_low_pct": 0.3923, "recent_swing_high": 83019.7, "recent_swing_low": 82318.2, "trend": "LH_LL"}, "4h": {"distance_from_swing_high_pct": -1.9097, "distance_from_swing_low_pct": -0.6712, "recent_swing_high": 84250.0, "recent_swing_low": 83199.5, "trend": "HH_HL"}}, "capital_flow": {"capital_flow_confidence": 30, "derived_proxy": "group breadth and relative performance", "inference_disclaimer": "Inferred proxy; not direct measurement of capital transfers", "observed_data": "completed-candle returns and volumes", "primary_state": "NO_CLEAR_FLOW"}, "market_transition_state": "DEEPER_CORRECTION_RISK", "regime": "BEAR", "sell_pressure": {"12h": {"classification": "INCREASING", "ratio": 1.4074}, "4h": {"classification": "DECLINING", "ratio": 1.5354}}}

## Changes Since Previous Independent Observation

[{"current": "DEEPER_CORRECTION_RISK", "field": "market_state", "previous": "INDETERMINATE"}, {"current": 4.1096, "field": "breadth_above_ema20_pct", "previous": 36.9863}, {"current": "DECLINING", "field": "sell_pressure_4h", "previous": "INCREASING"}, {"current": "LH_LL", "field": "btc_structure_1h", "previous": "MIXED"}]

## Research Memory

{"statistical_warnings": ["OOS_NOT_FOR_OPTIMIZATION", "MULTIPLE_TESTING_RISK", "DATA_SNOOPING_RISK", "CORRELATED_VARIANT_SAMPLE", "REGIME_IMBALANCE"], "status": "AVAILABLE", "strategies": [{"ev_95_ci_pct": [0.32693799498916853, 0.5762991294354152], "expected_value_pct": 0.44894772832852586, "oos_n": 1964, "profit_factor": 1.3906831077390787, "strategy": "MULTI_TP4_SL2", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [0.43433995672177256, 1.0606286021531168], "expected_value_pct": 0.7480904956933796, "oos_n": 406, "profit_factor": 1.60193418165775, "strategy": "MOMENTUM_STRUCTURE_EXIT", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [-0.2335687030677467, 0.22556807868975387], "expected_value_pct": -0.0009402949426981794, "oos_n": 406, "profit_factor": 0.9991900473786104, "strategy": "MOMENTUM_TP3_SL2", "validation_status": "OOS_NEGATIVE"}, {"ev_95_ci_pct": [0.43433995672177256, 1.0606286021531168], "expected_value_pct": 0.7480904956933796, "oos_n": 406, "profit_factor": 1.60193418165775, "strategy": "MOMENTUM_TP5_SL2", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [-0.2920293595073442, 0.24238991002471988], "expected_value_pct": -0.025547688993725712, "oos_n": 287, "profit_factor": 0.9773942189687079, "strategy": "RANGE_FIXED_3", "validation_status": "OOS_NEGATIVE"}], "warnings": ["MULTIPLE_TESTING_RISK", "DATA_SNOOPING_RISK", "CORRELATED_VARIANT_SAMPLE", "REGIME_IMBALANCE"]}

## Strategy Evidence

[{"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [0.7606816968514422, 2.6714757277604817], "diagnostic_effective_n": 154.424498282741, "ev_pct": 1.7100303310716882, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.9331427755099705, 2.5084831857745815], "raw_n": 205, "regime_coverage": ["BEAR"], "strategy": "EE_DYNAMIC_BREAKOUT"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.6255639016697317, 0.49547105806084285], "diagnostic_effective_n": 105.04969513340285, "ev_pct": -0.06750764778407864, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.38468868068999573, 0.2656180554009034], "raw_n": 287, "regime_coverage": ["BEAR"], "strategy": "RANGE_MIDPOINT"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.022356023104155746, 0.9875832547395746], "diagnostic_effective_n": 88.48532132373978, "ev_pct": 0.44894772832852586, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.32423931628809377, 0.5727210857549919], "raw_n": 1964, "regime_coverage": ["BEAR"], "strategy": "MULTI_TP4_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.2532797346130222, 1.0187997749245274], "diagnostic_effective_n": 71.6263404447579, "ev_pct": 0.36002126782678084, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.015183963120385476, 0.7327606646125753], "raw_n": 287, "regime_coverage": ["BEAR"], "strategy": "RANGE_FIXED_5"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.515527264005334, 0.4214237326747046], "diagnostic_effective_n": 70.7551194616187, "ev_pct": -0.04675138857008995, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.3496541551920968, 0.2520769981758704], "raw_n": 205, "regime_coverage": ["BEAR"], "strategy": "EE_TP3_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.301303640921366, 0.7792763418873111], "diagnostic_effective_n": 67.21700249047072, "ev_pct": 0.2356023460495561, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.12691260846521676, 0.5966634175130565], "raw_n": 205, "regime_coverage": ["BEAR"], "strategy": "EE_TP4_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.11042370238491876, 1.0667469365263416], "diagnostic_effective_n": 66.95538346096336, "ev_pct": 0.47068438386246475, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.06444286277180618, 0.8778589283825495], "raw_n": 205, "regime_coverage": ["BEAR"], "strategy": "EE_TP5_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.6030456266221454, 0.5349768393680137], "diagnostic_effective_n": 60.451784271320086, "ev_pct": -0.025547688993725712, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.29581532167009356, 0.23772334680018853], "raw_n": 287, "regime_coverage": ["BEAR"], "strategy": "RANGE_FIXED_3"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.028697395861773552, 1.9944128901912914], "diagnostic_effective_n": 104.466592264695, "ev_pct": 0.9054039834416504, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.3006666161579874, 1.5535334517820742], "raw_n": 286, "regime_coverage": ["BEAR"], "strategy": "RANGE_HIGH"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.6385553330049926, 0.6968114379930141], "diagnostic_effective_n": 49.34062379304324, "ev_pct": -0.0009402949426981794, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.22992656292171426, 0.2310233376718402], "raw_n": 406, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_TP3_SL2"}, {"alias_group": "ALIAS_008", "alias_status": "EXECUTION_IDENTICAL_ALIAS", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.11050483089382324, 1.8148673132662339], "diagnostic_effective_n": 46.521976559154574, "ev_pct": 0.7480904956933796, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "naive_ci_pct": [0.43269238344898525, 1.075209463709101], "raw_n": 406, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_STRUCTURE_EXIT"}, {"alias_group": "ALIAS_008", "alias_status": "EXECUTION_IDENTICAL_ALIAS", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.11050483089382324, 1.8148673132662339], "diagnostic_effective_n": 46.521976559154574, "ev_pct": 0.7480904956933796, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "naive_ci_pct": [0.43269238344898525, 1.075209463709101], "raw_n": 406, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_TP5_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_10D"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_3D"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_5D"}]

## FORWARD VALIDATION BOARD

[{"aliases": [], "execution_hash_short": "422eaf08bf98", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.515527264005334, 0.4214237326747046], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP3_SL2"}, {"aliases": [], "execution_hash_short": "71fb28e84ea7", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.6385553330049926, 0.6968114379930141], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MOMENTUM_TP3_SL2"}, {"aliases": [], "execution_hash_short": "7b50c9d06d56", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.6030456266221454, 0.5349768393680137], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_FIXED_3"}, {"aliases": [], "execution_hash_short": "9ce597d35a2a", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.301303640921366, 0.7792763418873111], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP4_SL2"}, {"aliases": [], "execution_hash_short": "a5e1f74d016e", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.022356023104155746, 0.9875832547395746], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MULTI_TP4_SL2"}, {"aliases": [], "execution_hash_short": "a67e1c4c6b2f", "forward_clustered_ci_95": [-2.4000000000000075, -2.399999999999996], "forward_completed_outcomes": 8, "forward_ev_pct": -2.4000000000000017, "governance_state": "COLLECTING", "historical_clustered_ci_95": [-0.2532797346130222, 1.0187997749245274], "independent_forward_clusters": 1, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 8/50; independent clusters 1/20", "regime_coverage": [], "strategy": "RANGE_FIXED_5"}, {"aliases": [], "execution_hash_short": "acc076b635e7", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_10D"}, {"aliases": ["MOMENTUM_TP5_SL2"], "execution_hash_short": "c71f362e36dd", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.11050483089382324, 1.8148673132662339], "independent_forward_clusters": 0, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MOMENTUM_STRUCTURE_EXIT"}, {"aliases": [], "execution_hash_short": "d0f1e752c2a1", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "CANDIDATE_FOR_FREEZE", "historical_clustered_ci_95": [0.7606816968514422, 2.6714757277604817], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_DYNAMIC_BREAKOUT"}, {"aliases": [], "execution_hash_short": "d4c1126e41a5", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.6255639016697317, 0.49547105806084285], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_MIDPOINT"}, {"aliases": [], "execution_hash_short": "d55bce5c8e3b", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.11042370238491876, 1.0667469365263416], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP5_SL2"}, {"aliases": [], "execution_hash_short": "e866f21be395", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_3D"}, {"aliases": [], "execution_hash_short": "e9ed863fd44d", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.028697395861773552, 1.9944128901912914], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_HIGH"}, {"aliases": [], "execution_hash_short": "f50c2081eebd", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_5D"}]

## Current Candidates

### AAVE
- Analysis snapshot price/time: 161.31 / 2026-10-12T16:00:00+00:00
- Kraken live reference/time: 161.505 / 2026-10-12T17:04:11.809318+00:00
- Setup quality: {'score': 58.36, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 22.0779, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 34.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_PULLBACK'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### HYPE
- Analysis snapshot price/time: 83.47 / 2026-10-12T16:00:00+00:00
- Kraken live reference/time: 83.62 / 2026-10-12T17:04:11.809318+00:00
- Setup quality: {'score': 65.14, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 34.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_PULLBACK'}
- Expected edge: {'value': 3.077237942255118, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / ALT/BTC closes below relative EMA20
### STX
- Analysis snapshot price/time: 0.3996 / 2026-10-12T16:00:00+00:00
- Kraken live reference/time: 0.4018 / 2026-10-12T17:04:11.809318+00:00
- Setup quality: {'score': 52.69, 'state': 'EARLY_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 65.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_BREAKOUT'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / CLOSE_BELOW_LOCAL_SWING_LOW
### ATOM
- Analysis snapshot price/time: 1.802 / 2026-10-12T16:00:00+00:00
- Kraken live reference/time: 1.81045 / 2026-10-12T17:04:11.809318+00:00
- Setup quality: {'score': 48.9, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 40.0, 'band': 'LOW', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 29.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': 6.349575559576115, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / ALT/BTC closes below relative EMA20
### ADA
- Analysis snapshot price/time: 0.240855 / 2026-10-12T16:00:00+00:00
- Kraken live reference/time: 0.242196 / 2026-10-12T17:04:11.809318+00:00
- Setup quality: {'score': 38.5, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 29.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### DOT
- Analysis snapshot price/time: 1.2158 / 2026-10-12T16:00:00+00:00
- Kraken live reference/time: 1.2208 / 2026-10-12T17:04:11.809318+00:00
- Setup quality: {'score': 35.06, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 33.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### HBAR
- Analysis snapshot price/time: 0.08934 / 2026-10-12T16:00:00+00:00
- Kraken live reference/time: 0.08939 / 2026-10-12T17:04:11.809318+00:00
- Setup quality: {'score': 63.05, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 34.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_PULLBACK'}
- Expected edge: {'value': 1.861820696418393, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / ALT/BTC closes below relative EMA20
### PUMP
- Analysis snapshot price/time: 0.005196 / 2026-10-12T16:00:00+00:00
- Kraken live reference/time: 0.0052035 / 2026-10-12T17:04:11.809318+00:00
- Setup quality: {'score': 45.29, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 29.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### TIA
- Analysis snapshot price/time: 0.5527 / 2026-10-12T16:00:00+00:00
- Kraken live reference/time: 0.5569500000000001 / 2026-10-12T17:04:11.809318+00:00
- Setup quality: {'score': 34.66, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 25.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### AERO
- Analysis snapshot price/time: 0.8889 / 2026-10-12T16:00:00+00:00
- Kraken live reference/time: 0.8925000000000001 / 2026-10-12T17:04:11.809318+00:00
- Setup quality: {'score': 35.2, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 25.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### ALGO
- Analysis snapshot price/time: 0.12435 / 2026-10-12T16:00:00+00:00
- Kraken live reference/time: 0.124345 / 2026-10-12T17:04:11.809318+00:00
- Setup quality: {'score': 57.94, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 29.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### APT
- Analysis snapshot price/time: 0.8258 / 2026-10-12T16:00:00+00:00
- Kraken live reference/time: 0.8314999999999999 / 2026-10-12T17:04:11.809318+00:00
- Setup quality: {'score': 39.81, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 29.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale

## Forward Experiments

- {"activation_state": "COLLECTING", "batch_dependence_warnings": ["SIMULTANEOUS_SIGNAL_COUNT_IS_BATCH_DEPENDENT"], "completed_outcomes": 8, "experiment_name": "RANGE_FIXED_5_FORWARD_V2", "monitoring_health": "SAFE", "official_monitor_runner": "AVAILABLE_NOT_RUN_READ_ONLY_ORCHESTRATOR", "open_observations": 0, "signals": 8, "trading_capability": "DISABLED"}

## Conflicts

- {"asset": "AAVE", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}
- {"asset": "HYPE", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}
- {"asset": "STX", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}
- {"asset": "HBAR", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}

## What We Do Not Know

- {"affected_conclusion": "Expected success likelihood", "asset": "MARKET", "available_workaround": "Use scenario analysis rather than probability claims", "unknown": "NO_VALIDATED_PROBABILITY", "why_it_matters": "Evidence confidence is not outcome probability"}
- {"affected_conclusion": "Net rotation edge", "asset": "MARKET", "available_workaround": "Stress-test higher costs", "unknown": "UNCERTAIN_SLIPPAGE", "why_it_matters": "Realized execution costs may differ"}
- {"affected_conclusion": "Capital-flow inference", "asset": "MARKET", "available_workaround": "Treat inferred flow confidence conservatively", "unknown": "NO_DERIVATIVES_OR_ON_CHAIN_DATA", "why_it_matters": "Positioning and flow proxies are incomplete"}

## Next Research Checks

- Observe the next completed market-data cutoff.
- Check stale inputs and technical activation/invalidation conditions.
- Accumulate independent OOS and forward outcomes; do not infer validation from actionability.
