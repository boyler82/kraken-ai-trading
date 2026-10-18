from __future__ import annotations
import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from tactical_opportunities import ALLOWED_ACTIONS, ALLOWED_CONVICTIONS, ALLOWED_RECOMMENDATIONS, build


def candidate(asset, stage, **overrides):
    row={"asset":asset,"current_data":{"current_price":100,"freshness":"FRESH"},"decision_metrics":{"current_primary_hypothesis":stage,"evidence_confidence_score":70,"confidence_band":"MEDIUM","opportunity_age_status":"FRESH"},"momentum":{"stage":stage,"extension_risk":"LOW","breakout_level":105,"distance_to_breakout_pct":1,"confirmation_closes":1,"invalidation_condition":"close below 95","invalidation_reference_level":95,"acceleration":2,"return_24h_pct":3,"return_48h_pct":4,"volume_z_score":1.5,"volatility_expansion":1.4},"consolidation":{"range_validity":True,"range_state":"VALID_RANGE","position_percent":50,"range_low":90,"range_quality":60,"average_cycle_hours":48},"relative_strength":{"relative_trend":"OUTPERFORMING","percentile_rank":80,"return_vs_btc_24h_pct":2,"return_vs_btc_7d_pct":4,"return_vs_btc_14d_pct":5},"rotation":{"score_advantage":12,"net_edge_after_costs":3,"edge_validation_status":"UNVALIDATED"},"validation":{"historical_sample_size":0,"validation_grade":"INSUFFICIENT_SAMPLE"},"evidence":{"supporting_modules":["momentum"]}}
    for section, values in overrides.items():row[section].update(values)
    return row


def exit_memory():
    return {"strategy_memory":[
        {"strategy_family":"MOMENTUM_BREAKOUT","strategy_variant":"MOMENTUM_STRUCTURE_EXIT","unique_episode_count":111,"median_holding_hours":24.08},
        {"strategy_family":"CONSOLIDATION_RANGE","strategy_variant":"RANGE_HIGH","unique_episode_count":777,"median_holding_hours":47.71},
    ],"oos_summary":[
        {"strategy":"MOMENTUM_STRUCTURE_EXIT","oos_n":71,"oos_status":"OOS_POSITIVE_UNVALIDATED"},
        {"strategy":"RANGE_HIGH","oos_n":42,"oos_status":"OOS_POSITIVE_UNVALIDATED"},
    ]}


class TacticalOpportunityTests(unittest.TestCase):
    def test_atom_can_have_better_setup_but_lower_actionability_than_tao(self):
        atom=candidate("ATOM","NO_MOMENTUM",relative_strength={"percentile_rank":98,"return_vs_btc_7d_pct":8,"return_vs_btc_14d_pct":8},rotation={"score_advantage":15,"net_edge_after_costs":7})
        tao=candidate("TAO","EARLY_MOMENTUM",relative_strength={"percentile_rank":25,"return_vs_btc_7d_pct":0,"return_vs_btc_14d_pct":0},rotation={"score_advantage":None,"net_edge_after_costs":None,"edge_validation_status":None})
        rows={r["asset"]:r for r in build([atom,tao])["daily"]}
        self.assertGreater(rows["ATOM"]["setup_quality_score"],rows["TAO"]["setup_quality_score"])
        self.assertLess(rows["ATOM"]["actionability_score"],rows["TAO"]["actionability_score"])

    def test_buy_on_breakout_has_no_automatic_setup_bonus(self):
        active=candidate("A","EARLY_MOMENTUM");watch=candidate("B","NO_MOMENTUM")
        rows={r["asset"]:r for r in build([active,watch])["daily"]}
        self.assertNotIn("action",rows["A"]["score_breakdown"]["setup_quality"])
        self.assertEqual(rows["A"]["score_breakdown"]["setup_quality"]["base"],rows["B"]["score_breakdown"]["setup_quality"]["base"])

    def test_high_rs_does_not_rescue_weak_setup(self):
        weak=candidate("WEAK","FAILED_BREAKOUT",relative_strength={"percentile_rank":100})
        sound=candidate("SOUND","BREAKOUT_DEVELOPING",relative_strength={"percentile_rank":50})
        result=build([weak,sound]);rows={r["asset"]:r for r in result["avoid"]+result["daily"]}
        self.assertLess(rows["WEAK"]["setup_quality_score"],rows["SOUND"]["setup_quality_score"])

    def test_failed_breakout_is_avoid_but_not_forced_to_zero(self):
        row=build([candidate("ALGO","FAILED_BREAKOUT")])["avoid"][0]
        self.assertEqual(row["action"],"AVOID");self.assertGreater(row["setup_quality_score"],0)

    def test_missing_confidence_has_no_positive_bonus(self):
        row=build([candidate("SOL","EARLY_MOMENTUM",decision_metrics={"evidence_confidence_score":None,"confidence_band":None})])["daily"][0]
        self.assertLessEqual(row["score_breakdown"]["setup_quality"]["evidence_confidence"],0)

    def test_daily_and_weekly_can_rank_differently(self):
        fast=candidate("FAST","BREAKOUT_CONFIRMED",relative_strength={"percentile_rank":45,"return_vs_btc_7d_pct":-2,"return_vs_btc_14d_pct":-2},rotation={"score_advantage":None,"net_edge_after_costs":None,"edge_validation_status":None})
        slow=candidate("SLOW","NO_MOMENTUM",relative_strength={"percentile_rank":98,"return_vs_btc_7d_pct":10,"return_vs_btc_14d_pct":10},rotation={"score_advantage":18,"net_edge_after_costs":7})
        result=build([fast,slow])
        self.assertEqual(result["daily"][0]["asset"],"FAST");self.assertEqual(result["weekly"][0]["asset"],"SLOW")

    def test_hold_verdict_is_not_an_input_or_gate(self):
        row=build([candidate("SOL","BREAKOUT_CONFIRMED")])["daily"][0]
        self.assertEqual(row["action"],"BUY_NOW");self.assertIn("UNVALIDATED_EDGE",row["warnings"]);self.assertIn("INSUFFICIENT_SAMPLE",row["warnings"])

    def test_schema_actions_no_targets_and_backward_compatibility(self):
        row=build([candidate("SOL","EARLY_MOMENTUM")])["daily"][0]
        self.assertIn(row["action"],ALLOWED_ACTIONS);self.assertNotIn("target",row);self.assertIn("tactical_score",row)
        required={"rank","asset","setup_quality_score","actionability_score","daily_score","weekly_score","entry_trigger","stop_reference","relative_strength","rotation_score_advantage","net_edge_after_costs","evidence_confidence","validation","reasons","warnings","why_not_buy_now"}
        self.assertTrue(required.issubset(row))

    def test_avoid_sorted_by_setup_quality_not_alphabetically(self):
        better=candidate("ZZZ","EXTENDED_MOVE",momentum={"extension_risk":"HIGH"},relative_strength={"percentile_rank":90})
        worse=candidate("AAA","FAILED_BREAKOUT",relative_strength={"percentile_rank":20})
        self.assertEqual(build([worse,better])["avoid"][0]["asset"],"ZZZ")

    def test_negative_btc_edge_blocks_actionable_but_keeps_technical_action(self):
        shib=candidate("SHIB","BREAKOUT_DEVELOPING",rotation={"score_advantage":-1.2,"net_edge_after_costs":-0.6})
        row=build([shib],"BTC_ACCUMULATION")["daily"][0]
        self.assertEqual(row["technical_action"],"BUY_ON_BREAKOUT")
        self.assertNotEqual(row["recommendation"],"ACTIONABLE")
        self.assertIn("NEGATIVE_NET_EDGE_AFTER_COSTS",row["why_not_actionable"])
        self.assertIn("POSITIVE_BTC_RELATIVE_EDGE_REQUIRED",row["activation_requirements"])

    def test_atom_can_be_high_priority_watch(self):
        atom=candidate("ATOM","NO_MOMENTUM",relative_strength={"percentile_rank":98},rotation={"score_advantage":15,"net_edge_after_costs":7})
        row=build([atom])["weekly"][0]
        self.assertGreaterEqual(row["setup_quality_score"],60)
        self.assertLess(row["actionability_score"],60)
        self.assertEqual(row["recommendation"],"HIGH_PRIORITY_WATCH")

    def test_tao_can_be_speculative_with_trigger_but_weak_evidence(self):
        tao=candidate("TAO","EARLY_MOMENTUM",decision_metrics={"evidence_confidence_score":None,"confidence_band":None},relative_strength={"percentile_rank":25},rotation={"score_advantage":None,"net_edge_after_costs":None,"edge_validation_status":None},consolidation={"range_validity":False,"position_percent":120})
        row=build([tao],"BTC_ACCUMULATION")["daily"][0]
        self.assertEqual(row["technical_action"],"BUY_ON_BREAKOUT")
        self.assertEqual(row["recommendation"],"SPECULATIVE_REVIEW")
        self.assertIn("INSUFFICIENT_SAMPLE",row["why_not_actionable"])

    def test_avoid_recommendation_remains_avoid(self):
        row=build([candidate("ALGO","FAILED_BREAKOUT")])["avoid"][0]
        self.assertEqual(row["technical_action"],"AVOID")
        self.assertEqual(row["recommendation"],"AVOID")
        self.assertEqual(row["activation_requirements"],[])

    def test_hold_verdict_does_not_gate_recommendation(self):
        # The builder deliberately has no market-verdict input.
        row=build([candidate("SOL","BREAKOUT_CONFIRMED")])["daily"][0]
        self.assertIn(row["recommendation"],{"ACTIONABLE","SPECULATIVE_REVIEW"})

    def test_action_remains_backward_compatible_alias(self):
        for row in build([candidate("SOL","EARLY_MOMENTUM")])["daily"]:
            self.assertEqual(row["action"],row["technical_action"])
            self.assertIn(row["recommendation"],ALLOWED_RECOMMENDATIONS)
            self.assertIn(row["conviction"],ALLOWED_CONVICTIONS)

    def test_trade_plan_has_no_arbitrary_targets_when_evidence_is_insufficient(self):
        row=build([candidate("SOL","BREAKOUT_DEVELOPING")])["daily"][0]
        plan=row["trade_plan"]
        self.assertIsNotNone(plan)
        self.assertIsNone(plan["target_1"]);self.assertIsNone(plan["target_2"])
        self.assertIn("TARGET_NOT_VALIDATED",plan["warnings"])

    def test_trade_plan_stop_always_identifies_its_source(self):
        row=build([candidate("SOL","BREAKOUT_DEVELOPING")])["daily"][0]
        plan=row["trade_plan"]
        self.assertEqual(plan["stop_loss"],95)
        self.assertEqual(plan["stop_source"],"momentum.invalidation_reference_level")

    def test_breakout_entry_is_anchored_to_breakout_level(self):
        row=build([candidate("SOL","BREAKOUT_DEVELOPING")])["daily"][0]
        plan=row["trade_plan"]
        self.assertEqual(plan["preferred_entry"],105)
        self.assertEqual(plan["entry_zone_low"],105);self.assertEqual(plan["entry_zone_high"],105)
        self.assertEqual(plan["entry_method"],"BREAKOUT_LEVEL_WITH_CONFIRMATION")

    def test_high_priority_watch_plan_waits_for_trigger(self):
        atom=candidate("ATOM","NO_MOMENTUM",relative_strength={"percentile_rank":98},rotation={"score_advantage":15,"net_edge_after_costs":7})
        row=build([atom])["weekly"][0]
        self.assertEqual(row["recommendation"],"HIGH_PRIORITY_WATCH")
        self.assertEqual(row["trade_plan"]["status"],"WAITING_FOR_TRIGGER")

    def test_avoid_has_no_trade_plan(self):
        row=build([candidate("ALGO","FAILED_BREAKOUT")])["avoid"][0]
        self.assertIsNone(row["trade_plan"])

    def test_trade_plan_preserves_v2_scores_and_uses_supported_exit_context(self):
        item=candidate("SOL","BREAKOUT_DEVELOPING")
        before=build([item])["daily"][0]
        memory={"strategy_memory":[{"strategy_family":"MOMENTUM_BREAKOUT","strategy_variant":"MOMENTUM_STRUCTURE_EXIT","unique_episode_count":111,"median_holding_hours":24.08}],"oos_summary":[{"strategy":"MOMENTUM_STRUCTURE_EXIT","oos_n":71,"oos_status":"OOS_POSITIVE_UNVALIDATED"}]}
        after=build([item],research_memory=memory)["daily"][0]
        for field in ("setup_quality_score","actionability_score","daily_score","weekly_score"):
            self.assertEqual(before[field],after[field])
        self.assertEqual(after["trade_plan"]["exit_method"],"MOMENTUM_STRUCTURE_EXIT")
        self.assertEqual(after["trade_plan"]["supporting_sample_size"],111)
        self.assertIn("OOS_NOT_FOR_OPTIMIZATION",after["trade_plan"]["warnings"])

    def test_valid_range_targets_are_structural_and_sourced(self):
        item=candidate("RANGE","NO_MOMENTUM",consolidation={"position_percent":20,"range_low":90,"midpoint":105,"range_high":110,"range_validity":True},rotation={"score_advantage":8,"net_edge_after_costs":2})
        row=build([item])["weekly"][0]
        plan=row["trade_plan"]
        self.assertEqual(row["technical_action"],"BUY_ON_PULLBACK")
        self.assertEqual(plan["target_1"],105);self.assertEqual(plan["target_1_source"],"consolidation.midpoint")
        self.assertEqual(plan["target_2"],110);self.assertEqual(plan["target_2_source"],"consolidation.range_high")

    def test_breakout_above_range_high_never_uses_range_exit_family(self):
        item=candidate("ATOM","NO_MOMENTUM",momentum={"breakout_level":115},consolidation={"range_high":110,"range_low":90,"range_validity":True},relative_strength={"percentile_rank":98},rotation={"score_advantage":15,"net_edge_after_costs":7})
        plan=build([item],research_memory=exit_memory())["weekly"][0]["trade_plan"]
        self.assertEqual(plan["planned_trade_family"],"MOMENTUM_BREAKOUT")
        self.assertEqual(plan["exit_family"],"MOMENTUM_BREAKOUT")
        self.assertEqual(plan["exit_method"],"MOMENTUM_STRUCTURE_EXIT")

    def test_shib_and_tao_keep_momentum_structure_exit(self):
        for asset,stage in (("SHIB","BREAKOUT_DEVELOPING"),("TAO","EARLY_MOMENTUM")):
            with self.subTest(asset=asset):
                plan=build([candidate(asset,stage)],research_memory=exit_memory())["daily"][0]["trade_plan"]
                self.assertEqual(plan["planned_trade_family"],"MOMENTUM_BREAKOUT")
                self.assertEqual(plan["exit_family"],"MOMENTUM_BREAKOUT")
                self.assertEqual(plan["exit_method"],"MOMENTUM_STRUCTURE_EXIT")

    def test_missing_targets_report_unestimable_rr_and_very_wide_stop(self):
        item=candidate("SHIB","BREAKOUT_DEVELOPING",momentum={"breakout_level":105,"invalidation_reference_level":95})
        plan=build([item],research_memory=exit_memory())["daily"][0]["trade_plan"]
        self.assertEqual(plan["stop_width_band"],"VERY_WIDE")
        self.assertIn("RISK_REWARD_NOT_ESTIMABLE",plan["warnings"])
        self.assertIn("WIDE_STOP_WITHOUT_VALIDATED_TARGET",plan["warnings"])

    def test_five_to_eight_percent_stop_is_wide_without_very_wide_warning(self):
        item=candidate("TAO","BREAKOUT_DEVELOPING",momentum={"breakout_level":105,"invalidation_reference_level":98})
        plan=build([item],research_memory=exit_memory())["daily"][0]["trade_plan"]
        self.assertEqual(plan["stop_width_band"],"WIDE")
        self.assertIn("RISK_REWARD_NOT_ESTIMABLE",plan["warnings"])
        self.assertNotIn("WIDE_STOP_WITHOUT_VALIDATED_TARGET",plan["warnings"])

    def test_family_sample_is_not_current_setup_validation(self):
        plan=build([candidate("SHIB","BREAKOUT_DEVELOPING")],research_memory=exit_memory())["daily"][0]["trade_plan"]
        self.assertEqual(plan["supporting_sample_size"],111)
        self.assertEqual(plan["exit_support_level"],"FAMILY_LEVEL_ONLY")

    def test_no_compatible_support_keeps_exit_context_null(self):
        range_only={"strategy_memory":[{"strategy_family":"CONSOLIDATION_RANGE","strategy_variant":"RANGE_HIGH","unique_episode_count":777,"median_holding_hours":47.71}]}
        plan=build([candidate("SHIB","BREAKOUT_DEVELOPING")],research_memory=range_only)["daily"][0]["trade_plan"]
        self.assertEqual(plan["planned_trade_family"],"MOMENTUM_BREAKOUT")
        self.assertIsNone(plan["exit_method"]);self.assertIsNone(plan["exit_family"])
        self.assertIsNone(plan["supporting_sample_size"]);self.assertIsNone(plan["expected_holding_hours"])
        self.assertEqual(plan["exit_support_level"],"NO_COMPATIBLE_SUPPORT")
        self.assertIn("MATCHED_EXIT_STRATEGY_NOT_AVAILABLE",plan["warnings"])

if __name__=='__main__':unittest.main()
