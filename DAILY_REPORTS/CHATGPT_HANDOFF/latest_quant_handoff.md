# Daily Quant ChatGPT Handoff

Run: 2026-09-06T07:43:53.915425+00:00
Pipeline status: OK
Market-data cutoff: 2026-09-06T06:00:00+00:00

## System Health

{"clock_safety": "SAFE", "coverage": {"candidates": 12, "live_prices": 12}, "module_failures": [], "required_missing": [], "stale_inputs": [], "warnings": []}

## Market State

{"breadth": {"above_ema20_pct": 76.5625, "above_ema50_pct": 90.625, "assets_ema20": 64, "assets_ema50": 64}, "btc_structure": {"1h": {"distance_from_swing_high_pct": -0.4186, "distance_from_swing_low_pct": 0.0421, "recent_swing_high": 80100.0, "recent_swing_low": 79731.1, "trend": "MIXED"}, "4h": {"distance_from_swing_high_pct": -0.4568, "distance_from_swing_low_pct": 0.0793, "recent_swing_high": 80130.7, "recent_swing_low": 79701.5, "trend": "MIXED"}}, "capital_flow": {"capital_flow_confidence": 30, "derived_proxy": "group breadth and relative performance", "inference_disclaimer": "Inferred proxy; not direct measurement of capital transfers", "observed_data": "completed-candle returns and volumes", "primary_state": "NO_CLEAR_FLOW"}, "market_transition_state": "CONSOLIDATION", "regime": "BEAR", "sell_pressure": {"12h": {"classification": "INCREASING", "ratio": 1.1305}, "4h": {"classification": "INCREASING", "ratio": 0.3839}}}

## Changes Since Previous Independent Observation

[{"current": 76.5625, "field": "breadth_above_ema20_pct", "previous": 89.7059}, {"current": "INCREASING", "field": "sell_pressure_4h", "previous": "DECLINING"}, {"current": "MIXED", "field": "btc_structure_1h", "previous": "HH_HL"}]

## Research Memory

{"statistical_warnings": ["OOS_NOT_FOR_OPTIMIZATION", "MULTIPLE_TESTING_RISK", "DATA_SNOOPING_RISK", "CORRELATED_VARIANT_SAMPLE", "REGIME_IMBALANCE"], "status": "AVAILABLE", "strategies": [{"ev_95_ci_pct": [0.5633941495288302, 0.9521255897336464], "expected_value_pct": 0.760290731758345, "oos_n": 782, "profit_factor": 1.7578840560672284, "strategy": "MULTI_TP4_SL2", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [0.08696294471711746, 0.774464218158701], "expected_value_pct": 0.4320714639435498, "oos_n": 172, "profit_factor": 1.4647774603781745, "strategy": "MOMENTUM_TP3_SL2", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [0.7633310553153854, 1.7751603114159553], "expected_value_pct": 1.27468002897063, "oos_n": 167, "profit_factor": 2.22068144236601, "strategy": "MOMENTUM_STRUCTURE_EXIT", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [0.7633310553153854, 1.7751603114159553], "expected_value_pct": 1.27468002897063, "oos_n": 167, "profit_factor": 2.22068144236601, "strategy": "MOMENTUM_TP5_SL2", "validation_status": "OOS_POSITIVE_UNVALIDATED"}, {"ev_95_ci_pct": [-0.33918681397767164, 0.5226286052090278], "expected_value_pct": 0.08586821963753892, "oos_n": 101, "profit_factor": 1.085432161293486, "strategy": "RANGE_FIXED_3", "validation_status": "OOS_POSITIVE_UNVALIDATED"}], "warnings": ["MULTIPLE_TESTING_RISK", "DATA_SNOOPING_RISK", "CORRELATED_VARIANT_SAMPLE", "REGIME_IMBALANCE"]}

## Strategy Evidence

[{"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.41281240517424694, 0.9493083390784662], "diagnostic_effective_n": 29.08130374194526, "ev_pct": 0.17000867128114241, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "naive_ci_pct": [-0.3263714585405839, 0.6574026358648315], "raw_n": 74, "regime_coverage": ["BEAR"], "strategy": "EE_TP3_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.9084459152893215, 0.44662892327110437], "diagnostic_effective_n": 65.24976768629591, "ev_pct": -0.18330067865752175, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.6247081156677015, 0.26968516028997347], "raw_n": 101, "regime_coverage": ["BEAR"], "strategy": "RANGE_MIDPOINT"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.09321600017885995, 2.261278769520249], "diagnostic_effective_n": 52.896517194953205, "ev_pct": 1.0990660061481268, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.3780151826367304, 1.8936427081500105], "raw_n": 98, "regime_coverage": ["BEAR"], "strategy": "RANGE_HIGH"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.13212979369681352, 1.7080218605495106], "diagnostic_effective_n": 35.36995005821441, "ev_pct": 0.760290731758345, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [0.559314784514733, 0.9569812424618135], "raw_n": 782, "regime_coverage": ["BEAR"], "strategy": "MULTI_TP4_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.6224332087757776, 0.8684097511894132], "diagnostic_effective_n": 32.41943637569642, "ev_pct": 0.08586821963753892, "major_warning": "LIMITED_REGIME_COVERAGE", "naive_ci_pct": [-0.3406396440703822, 0.5073618401158794], "raw_n": 101, "regime_coverage": ["BEAR"], "strategy": "RANGE_FIXED_3"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.10743418509576148, 2.4224004634101686], "diagnostic_effective_n": 28.12067554392323, "ev_pct": 1.0352599271294909, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "naive_ci_pct": [0.11861447248712742, 2.0261136359637373], "raw_n": 66, "regime_coverage": ["BEAR"], "strategy": "EE_DYNAMIC_BREAKOUT"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.17964702548976214, 1.4245561918327512], "diagnostic_effective_n": 27.819594854106747, "ev_pct": 0.48306446770561695, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "naive_ci_pct": [-0.09938576185192305, 1.0784472928818014], "raw_n": 72, "regime_coverage": ["BEAR"], "strategy": "EE_TP4_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.10640163545451843, 2.225604388807501], "diagnostic_effective_n": 26.338262089048587, "ev_pct": 1.0298038736151867, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "naive_ci_pct": [0.4006369069334978, 1.6352015405486506], "raw_n": 100, "regime_coverage": ["BEAR"], "strategy": "RANGE_FIXED_5"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.18191026245637862, 1.6462595850879447], "diagnostic_effective_n": 26.026079608603062, "ev_pct": 0.5992985578585751, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "naive_ci_pct": [-0.0790641097286233, 1.257387906787757], "raw_n": 71, "regime_coverage": ["BEAR"], "strategy": "EE_TP5_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.569860871844994, 1.2766101222046111], "diagnostic_effective_n": 24.611092363517393, "ev_pct": 0.4320714639435498, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "naive_ci_pct": [0.07956683649807708, 0.7725850142608263], "raw_n": 172, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_TP3_SL2"}, {"alias_group": "ALIAS_008", "alias_status": "EXECUTION_IDENTICAL_ALIAS", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.19126158016942804, 2.6194318225415496], "diagnostic_effective_n": 21.42026079679892, "ev_pct": 1.27468002897063, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "naive_ci_pct": [0.804084056776615, 1.7879224801873905], "raw_n": 167, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_STRUCTURE_EXIT"}, {"alias_group": "ALIAS_008", "alias_status": "EXECUTION_IDENTICAL_ALIAS", "classification": "RESEARCH", "cluster_aware_ci_pct": [-0.19126158016942804, 2.6194318225415496], "diagnostic_effective_n": 21.42026079679892, "ev_pct": 1.27468002897063, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "naive_ci_pct": [0.804084056776615, 1.7879224801873905], "raw_n": 167, "regime_coverage": ["BEAR"], "strategy": "MOMENTUM_TP5_SL2"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_10D"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_3D"}, {"alias_group": null, "alias_status": "ECONOMICALLY_UNIQUE", "classification": "RESEARCH", "cluster_aware_ci_pct": [null, null], "diagnostic_effective_n": null, "ev_pct": null, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "naive_ci_pct": [null, null], "raw_n": 0, "regime_coverage": [], "strategy": "ROTATION_5D"}]

## FORWARD VALIDATION BOARD

[{"aliases": [], "execution_hash_short": "422eaf08bf98", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.41281240517424694, 0.9493083390784662], "independent_forward_clusters": 0, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP3_SL2"}, {"aliases": [], "execution_hash_short": "71fb28e84ea7", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.569860871844994, 1.2766101222046111], "independent_forward_clusters": 0, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MOMENTUM_TP3_SL2"}, {"aliases": [], "execution_hash_short": "7b50c9d06d56", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.6224332087757776, 0.8684097511894132], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_FIXED_3"}, {"aliases": [], "execution_hash_short": "9ce597d35a2a", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.17964702548976214, 1.4245561918327512], "independent_forward_clusters": 0, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP4_SL2"}, {"aliases": [], "execution_hash_short": "a5e1f74d016e", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.13212979369681352, 1.7080218605495106], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MULTI_TP4_SL2"}, {"aliases": [], "execution_hash_short": "a67e1c4c6b2f", "forward_clustered_ci_95": [-2.4000000000000075, -2.399999999999996], "forward_completed_outcomes": 8, "forward_ev_pct": -2.4000000000000017, "governance_state": "COLLECTING", "historical_clustered_ci_95": [-0.10640163545451843, 2.225604388807501], "independent_forward_clusters": 1, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "next_required_evidence": "completed outcomes 8/50; independent clusters 1/20", "regime_coverage": [], "strategy": "RANGE_FIXED_5"}, {"aliases": [], "execution_hash_short": "acc076b635e7", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_10D"}, {"aliases": ["MOMENTUM_TP5_SL2"], "execution_hash_short": "c71f362e36dd", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.19126158016942804, 2.6194318225415496], "independent_forward_clusters": 0, "major_warning": "ALIAS_NOT_INDEPENDENT_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "MOMENTUM_STRUCTURE_EXIT"}, {"aliases": [], "execution_hash_short": "d0f1e752c2a1", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "CANDIDATE_FOR_FREEZE", "historical_clustered_ci_95": [-0.10743418509576148, 2.4224004634101686], "independent_forward_clusters": 0, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_DYNAMIC_BREAKOUT"}, {"aliases": [], "execution_hash_short": "d4c1126e41a5", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.9084459152893215, 0.44662892327110437], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_MIDPOINT"}, {"aliases": [], "execution_hash_short": "d55bce5c8e3b", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.18191026245637862, 1.6462595850879447], "independent_forward_clusters": 0, "major_warning": "LOW_DIAGNOSTIC_EFFECTIVE_N", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "EE_TP5_SL2"}, {"aliases": [], "execution_hash_short": "e866f21be395", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_3D"}, {"aliases": [], "execution_hash_short": "e9ed863fd44d", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [-0.09321600017885995, 2.261278769520249], "independent_forward_clusters": 0, "major_warning": "LIMITED_REGIME_COVERAGE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "RANGE_HIGH"}, {"aliases": [], "execution_hash_short": "f50c2081eebd", "forward_clustered_ci_95": [null, null], "forward_completed_outcomes": 0, "forward_ev_pct": null, "governance_state": "RESEARCH", "historical_clustered_ci_95": [null, null], "independent_forward_clusters": 0, "major_warning": "NO_REALIZED_OUTCOME_EVIDENCE", "next_required_evidence": "completed outcomes 0/50; independent clusters 0/20", "regime_coverage": [], "strategy": "ROTATION_5D"}]

## Current Candidates

### ATOM
- Analysis snapshot price/time: 1.5786 / 2026-09-06T06:00:00+00:00
- Kraken live reference/time: 1.58575 / 2026-09-06T07:44:24.813787+00:00
- Setup quality: {'score': 62.06, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 40.0, 'band': 'LOW', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 36.0, 'recommendation': 'HIGH_PRIORITY_WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': 6.349575559576115, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / ALT/BTC closes below relative EMA20
### DCR
- Analysis snapshot price/time: 16.934 / 2026-09-06T06:00:00+00:00
- Kraken live reference/time: 16.631500000000003 / 2026-09-06T07:44:24.813787+00:00
- Setup quality: {'score': 28.17, 'state': 'EARLY_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 51.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_BREAKOUT'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / CLOSE_BELOW_LOCAL_SWING_LOW
### EURC
- Analysis snapshot price/time: 1.16015 / 2026-09-06T06:00:00+00:00
- Kraken live reference/time: 1.161375 / 2026-09-06T07:44:24.813787+00:00
- Setup quality: {'score': 52.61, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 47.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_PULLBACK'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### ALGO
- Analysis snapshot price/time: 0.09417 / 2026-09-06T06:00:00+00:00
- Kraken live reference/time: 0.094745 / 2026-09-06T07:44:24.813787+00:00
- Setup quality: {'score': 42.52, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 40.0, 'band': 'LOW', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 33.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': 10.509112657221287, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / ALT/BTC closes below relative EMA20
### ENA
- Analysis snapshot price/time: 0.1756 / 2026-09-06T06:00:00+00:00
- Kraken live reference/time: 0.17435 / 2026-09-06T07:44:24.813787+00:00
- Setup quality: {'score': 58.98, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 37.6623, 'band': 'LOW', 'sample_size': 0, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 27.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': 4.954412638556583, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / ALT/BTC closes below relative EMA20
### ADA
- Analysis snapshot price/time: 0.220183 / 2026-09-06T06:00:00+00:00
- Kraken live reference/time: 0.21887800000000002 / 2026-09-06T07:44:24.813787+00:00
- Setup quality: {'score': 57.82, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 33.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### AERO
- Analysis snapshot price/time: 0.5443 / 2026-09-06T06:00:00+00:00
- Kraken live reference/time: 0.5391 / 2026-09-06T07:44:24.813787+00:00
- Setup quality: {'score': 52.55, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 22.0779, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 38.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### BCH
- Analysis snapshot price/time: 261.2 / 2026-09-06T06:00:00+00:00
- Kraken live reference/time: 259.17499999999995 / 2026-09-06T07:44:24.813787+00:00
- Setup quality: {'score': 54.2, 'state': 'BREAKOUT_DEVELOPING'}
- Evidence quality: {'score': 22.0779, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 70.0, 'recommendation': 'SPECULATIVE_REVIEW', 'technical_action': 'BUY_ON_BREAKOUT'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / CLOSE_BELOW_LOCAL_SWING_LOW
### DOT
- Analysis snapshot price/time: 0.9398 / 2026-09-06T06:00:00+00:00
- Kraken live reference/time: 0.94025 / 2026-09-06T07:44:24.813787+00:00
- Setup quality: {'score': 28.57, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 43.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### PUMP
- Analysis snapshot price/time: 0.003952 / 2026-09-06T06:00:00+00:00
- Kraken live reference/time: 0.0039545 / 2026-09-06T07:44:24.813787+00:00
- Setup quality: {'score': 40.59, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': 25.0, 'band': 'LOW', 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 34.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### AAVE
- Analysis snapshot price/time: 135.86 / 2026-09-06T06:00:00+00:00
- Kraken live reference/time: 134.81 / 2026-09-06T07:44:24.813787+00:00
- Setup quality: {'score': 51.47, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 33.0, 'recommendation': 'WATCH', 'technical_action': 'WATCH'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale
### APT
- Analysis snapshot price/time: 0.6187 / 2026-09-06T06:00:00+00:00
- Kraken live reference/time: 0.6208 / 2026-09-06T07:44:24.813787+00:00
- Setup quality: {'score': 30.0, 'state': 'NO_MOMENTUM'}
- Evidence quality: {'score': None, 'band': None, 'sample_size': None, 'validation_grade': 'INSUFFICIENT_SAMPLE'}
- Actionability: {'score': 25.0, 'recommendation': 'AVOID', 'technical_action': 'AVOID'}
- Expected edge: {'value': None, 'status': 'UNVALIDATED_EDGE'}
- R/R: {'to_midpoint': None, 'to_high': None, 'status': 'NOT_STATISTICALLY_OR_SEMANTICALLY_VALID'}
- Activation / invalidation: CLOSE_ABOVE_BREAKOUT_LEVEL / Hypothesis evidence weakens or becomes stale

## Forward Experiments

- {"activation_state": "COLLECTING", "batch_dependence_warnings": ["SIMULTANEOUS_SIGNAL_COUNT_IS_BATCH_DEPENDENT"], "completed_outcomes": 8, "experiment_name": "RANGE_FIXED_5_FORWARD_V2", "monitoring_health": "SAFE", "official_monitor_runner": "AVAILABLE_NOT_RUN_READ_ONLY_ORCHESTRATOR", "open_observations": 0, "signals": 8, "trading_capability": "DISABLED"}

## Conflicts

- {"asset": "DCR", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}
- {"asset": "EURC", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}
- {"asset": "BCH", "conflicts": ["TECHNICALLY_ACTIONABLE + STATISTICALLY_UNVALIDATED"]}

## What We Do Not Know

- {"affected_conclusion": "Expected success likelihood", "asset": "MARKET", "available_workaround": "Use scenario analysis rather than probability claims", "unknown": "NO_VALIDATED_PROBABILITY", "why_it_matters": "Evidence confidence is not outcome probability"}
- {"affected_conclusion": "Net rotation edge", "asset": "MARKET", "available_workaround": "Stress-test higher costs", "unknown": "UNCERTAIN_SLIPPAGE", "why_it_matters": "Realized execution costs may differ"}
- {"affected_conclusion": "Capital-flow inference", "asset": "MARKET", "available_workaround": "Treat inferred flow confidence conservatively", "unknown": "NO_DERIVATIVES_OR_ON_CHAIN_DATA", "why_it_matters": "Positioning and flow proxies are incomplete"}

## Next Research Checks

- Observe the next completed market-data cutoff.
- Check stale inputs and technical activation/invalidation conditions.
- Accumulate independent OOS and forward outcomes; do not infer validation from actionability.
