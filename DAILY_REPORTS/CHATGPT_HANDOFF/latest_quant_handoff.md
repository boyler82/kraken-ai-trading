# Daily Quant ChatGPT Handoff

Run: 2026-09-27T15:59:02.107141+00:00
Pipeline status: OK
Market-data cutoff: 2026-09-27T14:00:00+00:00

## System Health

{"clock_safety": "SAFE", "coverage": {"candidates": 12, "live_prices": 12}, "module_failures": [], "required_missing": [], "stale_inputs": [], "warnings": []}

## Market State

{"breadth": {"above_ema20_pct": 29.4872, "above_ema50_pct": 52.5641, "assets_ema20": 78, "assets_ema50": 78}, "btc_structure": {"1h": {"distance_from_swing_high_pct": -0.7342, "distance_from_swing_low_pct": -0.0695, "recent_swing_high": 85142.8, "recent_swing_low": 84576.5, "trend": "HH_HL"}, "4h": {"distance_from_swing_high_pct": 0.2408, "distance_from_swing_low_pct": 0.837, "recent_swing_high": 84314.7, "recent_swing_low": 83816.2, "trend": "MIXED"}}, "capital_flow": {"capital_flow_confidence": 30, "derived_proxy": "group breadth and relative performance", "inference_disclaimer": "Inferred proxy; not direct measurement of capital transfers", "observed_data": "completed-candle returns and volumes", "primary_state": "NO_CLEAR_FLOW"}, "market_transition_state": "INDETERMINATE", "regime": "BEAR", "sell_pressure": {"12h": {"classification": "INCREASING", "ratio": 0.9385}, "4h": {"classification": "INCREASING", "ratio": 2.8074}}}

## Changes Since Previous Independent Observation

[{"current": "INDETERMINATE", "field": "market_state", "previous": "HEALTHY_PULLBACK"}, {"current": 29.4872, "field": "breadth_above_ema20_pct", "previous": 91.0256}, {"current": "INCREASING", "field": "sell_pressure_4h", "previous": "DECLINING"}]

## Research Memory

{"statistical_warnings": ["OOS_NOT_FOR_OPTIMIZATION", "MULTIPLE_TESTING_RISK", "DATA_SNOOPING_RISK", "CORRELATED_VARIANT_SAMPLE", "REGIME_IMBALANCE"], "status": "AVAILABLE", "strategies": [{"ev_95_ci_pct": [0.39974012644324086, 0.6583101343611313], "expected_value_pct": 0.5302542306401282, "oos_n": 1862, "profit_factor": 1.467502031499812, "strategy": "MULTI_TP4_SL2", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [-0.21019441064917058, 0.2557016460231211], "expected_value_pct": 0.01813446096895647, "oos_n": 399, "profit_factor": 1.0156192576891625, "strategy": "MOMENTUM_TP3_SL2", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [0.4557773899854686, 1.1089602816619126], "expected_value_pct": 0.7765407033560989, "oos_n": 396, "profit_factor": 1.6210363125930791, "strategy": "MOMENTUM_STRUCTURE_EXIT", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [0.4557773899854686, 1.1089602816619126], "expected_value_pct": 0.7765407033560989, "oos_n": 396, "profit_factor": 1.6210363125930791, "strategy": "MOMENTUM_TP5_SL2", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [-0.314627007330592, 0.34661307996275664], "expected_value_pct": 0.014611374305555038, "oos_n": 266, "profit_factor": 1.0131459549021864, "strategy": "RANGE_MIDPOINT", "validation_status": "OOS_POSITIVE_UNVALIDATED"}], "warnings": ["MULTIPLE_TESTING_RISK", "DATA_SNOOPING_RISK", "CORRELATED_VARIANT_SAMPLE", "REGIME_IMBALANCE"]}

## Strategy Evidence

[{"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [0.9720191278815042, 2.963149899845214], "diagnostic_effective_n": 154.02467551218925, "ev_pct": 1.918835304607244, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [1.09629496815628, 2.7968734757901985], "raw_n": 192, "regime_coverage": ["BEAR"], "strategy": "EE_DYNAMIC_BREAKOUT"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.5626262402383634, 0.5882740229317478], "diagnostic_effective_n": 98.92658294203159, "ev_pct": 0.014611374305555038, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.32028252395265644, 0.3620687888656169], "raw_n": 266, "regime_coverage": ["BEAR"], "strategy": "RANGE_MIDPOINT"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [0.028578778521712953, 1.0915243918941664], "diagnostic_effective_n": 83.0696334601959, "ev_pct": 0.5302542306401282, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.40029352554860625, 0.6569384484053045], "raw_n": 1862, "regime_coverage": ["BEAR"], "strategy": "MULTI_TP4_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.4361756571639336, 0.5308001900398439], "diagnostic_effective_n": 68.12271146012756, "ev_pct": 0.04310482269805383, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.2822280208289717, 0.3570376963433548], "raw_n": 192, "regime_coverage": ["BEAR"], "strategy": "EE_TP3_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.20750896346616904, 0.9178832895877327], "diagnostic_effective_n": 64.11235806196045, "ev_pct": 0.3445762580992384, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.020330214920313894, 0.727560815473855], "raw_n": 192, "regime_coverage": ["BEAR"], "strategy": "EE_TP4_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.022499147895483875, 1.222783476141879], "diagnostic_effective_n": 63.66960842946961, "ev_pct": 0.5955753088890627, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.18077920738780046, 1.0292723310815177], "raw_n": 192, "regime_coverage": ["BEAR"], "strategy": "EE_TP5_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.13356296811559945, 1.300641016008585], "diagnostic_effective_n": 61.51378714562131, "ev_pct": 0.5373194737907163, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.13184265633789263, 0.9291515170963253], "raw_n": 263, "regime_coverage": ["BEAR"], "strategy": "RANGE_FIXED_5"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.5255002023242538, 0.66128921079595], "diagnostic_effective_n": 54.66204727576881, "ev_pct": 0.07156966288010494, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.2080466766740881, 0.34590257320834433], "raw_n": 265, "regime_coverage": ["BEAR"], "strategy": "RANGE_FIXED_3"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.004558754270723503, 2.161542588255745], "diagnostic_effective_n": 88.56707272704641, "ev_pct": 0.96230617913553, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.33884979948315475, 1.6453474857219414], "raw_n": 258, "regime_coverage": ["BEAR"], "strategy": "RANGE_HIGH"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.6410013754143995, 0.7228906007642162], "diagnostic_effective_n": 48.400094075437856, "ev_pct": 0.01813446096895647, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.20872410601774277, 0.2518830661227563], "raw_n": 399, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_TP3_SL2"}, {"alias_group": "ALIAS_008", "alias_status": "EXECUTION_IDENTICAL_ALIAS", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.10213581229838413, 1.8540308883246688], "diagnostic_effective_n": 44.95958939278735, "ev_pct": 0.7765407033560989, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "naive_ci_pct": [0.4533990982410245, 1.1093828055390678], "raw_n": 396, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_STRUCTURE_EXIT"}, {"alias_group": "ALIAS_008", "alias_status": "EXECUTION_IDENTICAL_ALIAS", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.10213581229838413, 1.8540308883246688], "diagnostic_effective_n": 44.95958939278735, "ev_pct": 0.7765407033560989, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "naive_ci_pct": [0.4533990982410245, 1.1093828055390678], "raw_n": 396, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_TP5_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_10D"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_3D"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_5D"}]

## FORWARD VALIDATION BOARD

[{"aliases": [], "execution_hash_short": "422eaf08bf98", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.4361756571639336, 0.5308001900398439], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP3_SL2"}, {"aliases": [], "execution_hash_short": "71fb28e84ea7", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.6410013754143995, 0.7228906007642162], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MOMENTUM_TP3_SL2"}, {"aliases": [], "execution_hash_short": "7b50c9d06d56", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.5255002023242538, 0.66128921079595], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_FIXED_3"}, {"aliases": [], "execution_hash_short": "9ce597d35a2a", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.20750896346616904, 0.9178832895877327], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP4_SL2"}, {"aliases": [], "execution_hash_short": "a5e1f74d016e", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [0.028578778521712953, 1.0915243918941664], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MULTI_TP4_SL2"}, {"aliases": [], "execution_hash_short": "a67e1c4c6b2f", "forward_clustered_ci_95": [-2.4000000000000075, -2.399999999999996], "forward_completed_outcomes": 8, "forward_ev_pct": -2.4000000000000017, "governance_state": "COLLECTING", "historical_clustered_ci_95": [-0.13356296811559945, 1.300641016008585], "independent_forward_clusters": 1, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 8/50; independent clusters 1/20", "regime_coverage": [], "strategy": "RANGE_FIXED_5"}, {"aliases": [], "execution_hash_short": "acc076b635e7", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_10D"}, {"aliases": ["MOMENTUM_TP5_SL2"], "execution_hash_short": "c71f362e36dd", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.10213581229838413, 1.8540308883246688], "independent_forward_clusters": 0, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MOMENTUM_STRUCTURE_EXIT"}, {"aliases": [], "execution_hash_short": "d0f1e752c2a1", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "CANDIDATE_FOR_FREEZE", "historical_clustered_ci_95": [0.9720191278815042, 2.963149899845214], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_DYNAMIC_BREAKOUT"}, {"aliases": [], "execution_hash_short": "d4c1126e41a5", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.5626262402383634, 0.5882740229317478], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_MIDPOINT"}, {"aliases": [], "execution_hash_short": "d55bce5c8e3b", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.022499147895483875, 1.222783476141879], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP5_SL2"}, {"aliases": [], "execution_hash_short": "e866f21be395", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_3D"}, {"aliases": [], "execution_hash_short": "e9ed863fd44d", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.004558754270723503, 2.161542588255745], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_HIGH"}, {"aliases": [], "execution_hash_short": "f50c2081eebd", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_5D"}]

## Current Candidates

### HYPE
- Analysis snapshot price/time: 91.3 / 2026-09-27T14:00:00+00:00
- Kraken live reference/time: 91.445 / 2026-09-27T16:01:41.441963+00:00
- Setup quality: {'score': 60.5, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 37.0, 'recommendation': 'HIGH_PRIORITY_WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': 3.077237942255118, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / ALT/BTC closes below relative EMA20
### AKE
- Analysis snapshot price/time: 0.0323444 / 2026-09-27T14:00:00+00:00
- Kraken live reference/time: 0.03283313 / 2026-09-27T16:01:41.441963+00:00
- Setup quality: {'score': 52.07, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 34.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_PULLBACK'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### PUMP
- Analysis snapshot price/time: 0.004788 / 2026-09-27T14:00:00+00:00
- Kraken live reference/time: 0.0048735 / 2026-09-27T16:01:41.441963+00:00
- Setup quality: {'score': 27.57, 'state': 'EXTENDED_MOVE'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 7.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### ATOM
- Analysis snapshot price/time: 1.8599 / 2026-09-27T14:00:00+00:00
- Kraken live reference/time: 1.8685 / 2026-09-27T16:01:41.441963+00:00
- Setup quality: {'score': 48.78, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 40.0, 'band': 'LOW', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 33.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': 6.349575559576115, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / ALT/BTC closes below relative EMA20
### ADA
- Analysis snapshot price/time: 0.253326 / 2026-09-27T14:00:00+00:00
- Kraken live reference/time: 0.254429 / 2026-09-27T16:01:41.441963+00:00
- Setup quality: {'score': 56.53, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 33.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### ALGO
- Analysis snapshot price/time: 0.11688 / 2026-09-27T14:00:00+00:00
- Kraken live reference/time: 0.11647 / 2026-09-27T16:01:41.441963+00:00
- Setup quality: {'score': 39.06, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 33.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': 10.509112657221287, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / ALT/BTC closes below relative EMA20
### DOT
- Analysis snapshot price/time: 1.2306 / 2026-09-27T14:00:00+00:00
- Kraken live reference/time: 1.23115 / 2026-09-27T16:01:41.441963+00:00
- Setup quality: {'score': 55.89, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 33.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### DRV
- Analysis snapshot price/time: 0.41021 / 2026-09-27T14:00:00+00:00
- Kraken live reference/time: 0.405145 / 2026-09-27T16:01:41.441963+00:00
- Setup quality: {'score': 49.35, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 22.0779, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 34.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_PULLBACK'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### TIA
- Analysis snapshot price/time: 0.4927 / 2026-09-27T14:00:00+00:00
- Kraken live reference/time: 0.49245 / 2026-09-27T16:01:41.441963+00:00
- Setup quality: {'score': 34.51, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 25.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### XTZ
- Analysis snapshot price/time: 0.32228 / 2026-09-27T14:00:00+00:00
- Kraken live reference/time: 0.323935 / 2026-09-27T16:01:41.441963+00:00
- Setup quality: {'score': 39.9, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 34.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### AAVE
- Analysis snapshot price/time: 153.22 / 2026-09-27T14:00:00+00:00
- Kraken live reference/time: 153.65 / 2026-09-27T16:01:41.441963+00:00
- Setup quality: {'score': 36.29, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 38.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### AERO
- Analysis snapshot price/time: 0.8276 / 2026-09-27T14:00:00+00:00
- Kraken live reference/time: 0.82555 / 2026-09-27T16:01:41.441963+00:00
- Setup quality: {'score': 28.62, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 25.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale

## Forward Experiments

- {"activation_state": "COLLECTING", "batch_dependence_warnings": ["SIMULTANEOUS_SIGNAL_COUNT_IS_BATCH_DEPENDENT"], "completed_outcomes": 8, "experiment_name": "RANGE_FIXED_5_FORWARD_V2", "monitoring_health": "SAFE", "official_monitor_runner": "AVAILABLE_NOT_RUN_READ_ONLY_ORCHESTRATOR", "open_observations": 0, "signals": 8, "trading_capability": "DISABLED"}

## Conflicts

- {"asset": "AKE", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}
- {"asset": "DRV", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}

## What We Do Not Know

- {"affected_conclusion": "Expected success likelihood", "asset": "MARKET", "available_workaround": "Use scenario analysis rather than probability claims", "unknown": "NO_VALIDATED_PROBABILITY", "why_it_matters": "Evidence confidence is not outcome probability"}
- {"affected_conclusion": "Net rotation edge", "asset": "MARKET", "available_workaround": "Stress-test higher costs", "unknown": "UNCERTAIN_SLIPPAGE", "why_it_matters": "Realized execution costs may differ"}
- {"affected_conclusion": "Capital-flow inference", "asset": "MARKET", "available_workaround": "Treat inferred flow confidence conservatively", "unknown": "NO_DERIVATIVES_OR_ON_CHAIN_DATA", "why_it_matters": "Positioning and flow proxies are incomplete"}

## Next Research Checks

- Observe the next completed market-data cutoff.
- Check stale inputs and technical activation/invalidation conditions.
- Accumulate independent OOS and forward outcomes; do not infer validation from actionability.
