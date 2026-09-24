# Daily Quant ChatGPT Handoff

Run: 2026-09-24T18:34:08.796773+00:00
Pipeline status: OK
Market-data cutoff: 2026-09-24T17:00:00+00:00

## System Health

{"clock_safety": "SAFE", "coverage": {"candidates": 12, "live_prices": 12}, "module_failures": [], "required_missing": [], "stale_inputs": [], "warnings": []}

## Market State

{"breadth": {"above_ema20_pct": 82.5, "above_ema50_pct": 70.0, "assets_ema20": 80, "assets_ema50": 80}, "btc_structure": {"1h": {"distance_from_swing_high_pct": -0.9604, "distance_from_swing_low_pct": 0.8827, "recent_swing_high": 84900.0, "recent_swing_low": 83348.9, "trend": "MIXED"}, "4h": {"distance_from_swing_high_pct": -0.9777, "distance_from_swing_low_pct": 1.5118, "recent_swing_high": 84914.8, "recent_swing_low": 82832.3, "trend": "MIXED"}}, "capital_flow": {"capital_flow_confidence": 30, "derived_proxy": "group breadth and relative performance", "inference_disclaimer": "Inferred proxy; not direct measurement of capital transfers", "observed_data": "completed-candle returns and volumes", "primary_state": "NO_CLEAR_FLOW"}, "market_transition_state": "HEALTHY_PULLBACK", "regime": "BEAR", "sell_pressure": {"12h": {"classification": "NORMAL", "ratio": 1.4352}, "4h": {"classification": "INCREASING", "ratio": 1.8374}}}

## Changes Since Previous Independent Observation

[{"current": "HEALTHY_PULLBACK", "field": "market_state", "previous": "CONSOLIDATION"}, {"current": 82.5, "field": "breadth_above_ema20_pct", "previous": 8.75}, {"current": "MIXED", "field": "btc_structure_1h", "previous": "LH_LL"}]

## Research Memory

{"statistical_warnings": ["OOS_NOT_FOR_OPTIMIZATION", "MULTIPLE_TESTING_RISK", "DATA_SNOOPING_RISK", "CORRELATED_VARIANT_SAMPLE", "REGIME_IMBALANCE"], "status": "AVAILABLE", "strategies": [{"ev_95_ci_pct": [0.37100040758809394, 0.6350495040878994], "expected_value_pct": 0.5028740601032029, "oos_n": 1802, "profit_factor": 1.43815397816042, "strategy": "MULTI_TP4_SL2", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [-0.22275243970155006, 0.24353534328420465], "expected_value_pct": 0.009655593274874101, "oos_n": 386, "profit_factor": 1.0082830816105826, "strategy": "MOMENTUM_TP3_SL2", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [0.4223478351443554, 1.085915255247345], "expected_value_pct": 0.7518875741551091, "oos_n": 383, "profit_factor": 1.5959632729244142, "strategy": "MOMENTUM_STRUCTURE_EXIT", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [0.4223478351443554, 1.085915255247345], "expected_value_pct": 0.7518875741551091, "oos_n": 383, "profit_factor": 1.5959632729244142, "strategy": "MOMENTUM_TP5_SL2", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [-0.2373652205314178, 0.33917981166366534], "expected_value_pct": 0.0553912248446701, "oos_n": 260, "profit_factor": 1.04979985630238, "strategy": "RANGE_FIXED_3", "validation_status": "OOS_POSITIVE_UNVALIDATED"}], "warnings": ["MULTIPLE_TESTING_RISK", "DATA_SNOOPING_RISK", "CORRELATED_VARIANT_SAMPLE", "REGIME_IMBALANCE"]}

## Strategy Evidence

[{"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [0.8057063488788511, 2.924408500025478], "diagnostic_effective_n": 135.04535372216597, "ev_pct": 1.8169244197857566, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.972900719787237, 2.722377404801199], "raw_n": 182, "regime_coverage": ["BEAR"], "strategy": "EE_DYNAMIC_BREAKOUT"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.624480533515409, 0.495379788271314], "diagnostic_effective_n": 98.77501986065361, "ev_pct": -0.0698402326024008, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.3996821801267567, 0.2894565149979031], "raw_n": 257, "regime_coverage": ["BEAR"], "strategy": "RANGE_MIDPOINT"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [0.002820439144243444, 1.0750919092496085], "diagnostic_effective_n": 77.97303553628655, "ev_pct": 0.5028740601032029, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.3668307207109013, 0.6329264539341469], "raw_n": 1802, "regime_coverage": ["BEAR"], "strategy": "MULTI_TP4_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.4915213715914999, 0.48601111945166037], "diagnostic_effective_n": 64.52872375032231, "ev_pct": -0.008329463912620972, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.3386849763097265, 0.3096215606782758], "raw_n": 183, "regime_coverage": ["BEAR"], "strategy": "EE_TP3_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.1830993412717424, 1.2077486634642827], "diagnostic_effective_n": 61.79034866682353, "ev_pct": 0.47088412266958274, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.06322286749242269, 0.8553945461516117], "raw_n": 257, "regime_coverage": ["BEAR"], "strategy": "RANGE_FIXED_5"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.28544532116416227, 0.8809423324692028], "diagnostic_effective_n": 59.71483872587015, "ev_pct": 0.29023002201251197, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.09719198433058622, 0.6841925501238754], "raw_n": 182, "regime_coverage": ["BEAR"], "strategy": "EE_TP4_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.09430890164941926, 1.2186799943091444], "diagnostic_effective_n": 59.2024522631512, "ev_pct": 0.5334869874794299, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.09567149173215458, 0.9803146717447311], "raw_n": 182, "regime_coverage": ["BEAR"], "strategy": "EE_TP5_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.5400119225684605, 0.6542992535895507], "diagnostic_effective_n": 53.407877846667034, "ev_pct": 0.0553912248446701, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.22902677359798587, 0.33373526705891926], "raw_n": 260, "regime_coverage": ["BEAR"], "strategy": "RANGE_FIXED_3"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.16784275058757897, 1.9239991697569916], "diagnostic_effective_n": 91.91550322608762, "ev_pct": 0.7810808094397805, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.17642404967940528, 1.4700705676826844], "raw_n": 252, "regime_coverage": ["BEAR"], "strategy": "RANGE_HIGH"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.6568043190512851, 0.7409497184211686], "diagnostic_effective_n": 44.09764689880099, "ev_pct": 0.009655593274874101, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.22582839117053227, 0.2525080707490251], "raw_n": 386, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_TP3_SL2"}, {"alias_group": "ALIAS_008", "alias_status": "EXECUTION_IDENTICAL_ALIAS", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.14696364283677937, 1.8699014346153722], "diagnostic_effective_n": 41.23045414560249, "ev_pct": 0.7518875741551091, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "naive_ci_pct": [0.41808066902189583, 1.0850634251479248], "raw_n": 383, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_STRUCTURE_EXIT"}, {"alias_group": "ALIAS_008", "alias_status": "EXECUTION_IDENTICAL_ALIAS", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.14696364283677937, 1.8699014346153722], "diagnostic_effective_n": 41.23045414560249, "ev_pct": 0.7518875741551091, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "naive_ci_pct": [0.41808066902189583, 1.0850634251479248], "raw_n": 383, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_TP5_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_10D"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_3D"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_5D"}]

## FORWARD VALIDATION BOARD

[{"aliases": [], "execution_hash_short": "422eaf08bf98", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.4915213715914999, 0.48601111945166037], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP3_SL2"}, {"aliases": [], "execution_hash_short": "71fb28e84ea7", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.6568043190512851, 0.7409497184211686], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MOMENTUM_TP3_SL2"}, {"aliases": [], "execution_hash_short": "7b50c9d06d56", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.5400119225684605, 0.6542992535895507], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_FIXED_3"}, {"aliases": [], "execution_hash_short": "9ce597d35a2a", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.28544532116416227, 0.8809423324692028], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP4_SL2"}, {"aliases": [], "execution_hash_short": "a5e1f74d016e", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [0.002820439144243444, 1.0750919092496085], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MULTI_TP4_SL2"}, {"aliases": [], "execution_hash_short": "a67e1c4c6b2f", "forward_clustered_ci_95": [-2.4000000000000075, -2.399999999999996], "forward_completed_outcomes": 8, "forward_ev_pct": -2.4000000000000017, "governance_state": "COLLECTING", "historical_clustered_ci_95": [-0.1830993412717424, 1.2077486634642827], "independent_forward_clusters": 1, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 8/50; independent clusters 1/20", "regime_coverage": [], "strategy": "RANGE_FIXED_5"}, {"aliases": [], "execution_hash_short": "acc076b635e7", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_10D"}, {"aliases": ["MOMENTUM_TP5_SL2"], "execution_hash_short": "c71f362e36dd", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.14696364283677937, 1.8699014346153722], "independent_forward_clusters": 0, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MOMENTUM_STRUCTURE_EXIT"}, {"aliases": [], "execution_hash_short": "d0f1e752c2a1", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "CANDIDATE_FOR_FREEZE", "historical_clustered_ci_95": [0.8057063488788511, 2.924408500025478], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_DYNAMIC_BREAKOUT"}, {"aliases": [], "execution_hash_short": "d4c1126e41a5", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.624480533515409, 0.495379788271314], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_MIDPOINT"}, {"aliases": [], "execution_hash_short": "d55bce5c8e3b", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.09430890164941926, 1.2186799943091444], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP5_SL2"}, {"aliases": [], "execution_hash_short": "e866f21be395", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_3D"}, {"aliases": [], "execution_hash_short": "e9ed863fd44d", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.16784275058757897, 1.9239991697569916], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_HIGH"}, {"aliases": [], "execution_hash_short": "f50c2081eebd", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_5D"}]

## Current Candidates

### ALGO
- Analysis snapshot price/time: 0.11176 / 2026-09-24T17:00:00+00:00
- Kraken live reference/time: 0.111795 / 2026-09-24T18:37:22.626149+00:00
- Setup quality: {'score': 65.95, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 33.0, 'recommendation': 'HIGH_PRIORITY_WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': 10.509112657221287, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / ALT/BTC closes below relative EMA20
### CAKE
- Analysis snapshot price/time: 2.74 / 2026-09-24T17:00:00+00:00
- Kraken live reference/time: 2.7445000000000004 / 2026-09-24T18:37:22.626149+00:00
- Setup quality: {'score': 35.92, 'state': 'EARLY_MOMENTUM'}
- Evidence quality: {'score': 22.0779, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 59.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_BREAKOUT'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / CLOSE_BELOW_LOCAL_SWING_LOW
### SPX
- Analysis snapshot price/time: 0.4378 / 2026-09-24T17:00:00+00:00
- Kraken live reference/time: 0.44035 / 2026-09-24T18:37:22.626149+00:00
- Setup quality: {'score': 54.97, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 34.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_PULLBACK'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### PUMP
- Analysis snapshot price/time: 0.003905 / 2026-09-24T17:00:00+00:00
- Kraken live reference/time: 0.003885 / 2026-09-24T18:37:22.626149+00:00
- Setup quality: {'score': 72.84, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 53.2468, 'band': 'MEDIUM', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 34.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_PULLBACK'}
- Expected edge: {'value': 4.578782086950284, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / ALT/BTC closes below relative EMA20
### ATOM
- Analysis snapshot price/time: 1.7727 / 2026-09-24T17:00:00+00:00
- Kraken live reference/time: 1.7744 / 2026-09-24T18:37:22.626149+00:00
- Setup quality: {'score': 69.85, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 40.0, 'band': 'LOW', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 37.0, 'recommendation': 'HIGH_PRIORITY_WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': 6.349575559576115, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / ALT/BTC closes below relative EMA20
### ADA
- Analysis snapshot price/time: 0.246272 / 2026-09-24T17:00:00+00:00
- Kraken live reference/time: 0.2466865 / 2026-09-24T18:37:22.626149+00:00
- Setup quality: {'score': 35.0, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 33.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### DOT
- Analysis snapshot price/time: 1.1634 / 2026-09-24T17:00:00+00:00
- Kraken live reference/time: 1.1579 / 2026-09-24T18:37:22.626149+00:00
- Setup quality: {'score': 56.67, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 33.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### DRV
- Analysis snapshot price/time: 0.45257 / 2026-09-24T17:00:00+00:00
- Kraken live reference/time: 0.45763 / 2026-09-24T18:37:22.626149+00:00
- Setup quality: {'score': 29.63, 'state': 'EARLY_MOMENTUM'}
- Evidence quality: {'score': 22.0779, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 61.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / CLOSE_BELOW_LOCAL_SWING_LOW
### TIA
- Analysis snapshot price/time: 0.4847 / 2026-09-24T17:00:00+00:00
- Kraken live reference/time: 0.4845 / 2026-09-24T18:37:22.626149+00:00
- Setup quality: {'score': 40.49, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 25.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### AAVE
- Analysis snapshot price/time: 143.61 / 2026-09-24T17:00:00+00:00
- Kraken live reference/time: 144.14 / 2026-09-24T18:37:22.626149+00:00
- Setup quality: {'score': 54.96, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 29.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### AERO
- Analysis snapshot price/time: 0.6983 / 2026-09-24T17:00:00+00:00
- Kraken live reference/time: 0.7023999999999999 / 2026-09-24T18:37:22.626149+00:00
- Setup quality: {'score': 50.07, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 33.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### AKE
- Analysis snapshot price/time: 0.03911578 / 2026-09-24T17:00:00+00:00
- Kraken live reference/time: 0.039083074999999995 / 2026-09-24T18:37:22.626149+00:00
- Setup quality: {'score': 30.66, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 34.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale

## Forward Experiments

- {"activation_state": "COLLECTING", "batch_dependence_warnings": ["SIMULTANEOUS_SIGNAL_COUNT_IS_BATCH_DEPENDENT"], "completed_outcomes": 8, "experiment_name": "RANGE_FIXED_5_FORWARD_V2", "monitoring_health": "SAFE", "official_monitor_runner": "AVAILABLE_NOT_RUN_READ_ONLY_ORCHESTRATOR", "open_observations": 0, "signals": 8, "trading_capability": "DISABLED"}

## Conflicts

- {"asset": "CAKE", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}
- {"asset": "SPX", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}
- {"asset": "PUMP", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED", "HIGH_SCORE + INVALID_RANGE"]}

## What We Do Not Know

- {"affected_conclusion": "Expected success likelihood", "asset": "MARKET", "available_workaround": "Use scenario analysis rather than probability claims", "unknown": "NO_VALIDATED_PROBABILITY", "why_it_matters": "Evidence confidence is not outcome probability"}
- {"affected_conclusion": "Net rotation edge", "asset": "MARKET", "available_workaround": "Stress-test higher costs", "unknown": "UNCERTAIN_SLIPPAGE", "why_it_matters": "Realized execution costs may differ"}
- {"affected_conclusion": "Capital-flow inference", "asset": "MARKET", "available_workaround": "Treat inferred flow confidence conservatively", "unknown": "NO_DERIVATIVES_OR_ON_CHAIN_DATA", "why_it_matters": "Positioning and flow proxies are incomplete"}

## Next Research Checks

- Observe the next completed market-data cutoff.
- Check stale inputs and technical activation/invalidation conditions.
- Accumulate independent OOS and forward outcomes; do not infer validation from actionability.
