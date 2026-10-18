from __future__ import annotations
import hashlib,json
from pathlib import Path
import pytest
import scripts.range_quality_index as rqi
import scripts.ai_daily_observations as observations


def current(**kw):
    row={"asset":"TEST","kraken_pair":"TESTUSD","range_state":"VALID_RANGE","range_valid":True,"range_low":90,"midpoint":100,"range_high":110,"position_pct":45,"width_pct":22.22,"freshness_status":"FRESH","freshness_age_hours":2,"continuity_status":"CONTINUOUS","lower_boundary_tests":4,"upper_boundary_tests":4,"closes_inside_pct":96,"confirmed_breakouts":0,"confirmed_breakdowns":0,"false_breakouts_above":0,"false_breakdowns_below":0,"trend_normalized_slope":.08,"directional_efficiency_ratio":.1,"trend_flatness_pass":True,"width_stability_cv":.12,"estimated_total_friction_pct":.6,"low_to_high":{"count":3},"high_to_low":{"count":3},"midpoint_crossings":6,"liquidity_pass":True,"spread_pass":True}
    row.update(kw);return row


def history(**kw):
    row={"sample_quality":"HIGH","valid_range_episodes":9,"half_cycles":24,"cycle_duration_cv":.15,"cycles_within_25pct_median_rate":85,"personality_agreement_across_windows":True,"range_personality_score":82,"historical_midpoint_recovery_rate":88,"historical_full_traversal_rate":84,"false_break_rate":12,"median_cycle_hours":36,"intersection_state":"HISTORICALLY_STRONG_AND_CURRENTLY_ACTIVE","liquidity_status":"PASS","continuity_status":"CONTINUOUS"}
    row.update(kw);return row


def test_high_quality_balanced_range(): assert rqi.calculate_rqi(current(),history())["rqi_classification"] in {"GOOD_RANGE","EXCELLENT_RANGE"}
def test_one_sided_range_penalty_and_lower_score():
    good=rqi.calculate_rqi(current(),history());bad=rqi.calculate_rqi(current(lower_boundary_tests=8,upper_boundary_tests=1),history());assert bad["rqi_score"]<good["rqi_score"] and "ONE_SIDED_RANGE" in {p["code"] for p in bad["penalties"]}
def test_excessive_false_breaks_material_penalty():
    good=rqi.calculate_rqi(current(),history());bad=rqi.calculate_rqi(current(false_breakouts_above=3,false_breakdowns_below=3),history());assert good["rqi_score"]-bad["rqi_score"]>=12
def test_strong_current_weak_history_has_low_confidence(): assert rqi.calculate_rqi(current(),history(sample_quality="LOW",valid_range_episodes=1,half_cycles=2,range_personality_score=20))["rqi_confidence_band"]=="LOW"
@pytest.mark.parametrize("state",["RANGE_INVALIDATED","BREAKOUT_CONFIRMED","BREAKDOWN_CONFIRMED"])
def test_invalid_or_confirmed_break_is_not_applicable(state): assert rqi.calculate_rqi(current(range_state=state,range_valid=state!="RANGE_INVALIDATED"),history())["rqi_score"] is None
def test_false_breakdown_recovery_allowed_with_penalty():
    row=rqi.calculate_rqi(current(range_state="FALSE_BREAKDOWN_RECOVERY"),history());assert row["rqi_score"] is not None and "RECOVERY_STATE" in {p["code"] for p in row["penalties"]}
def test_insufficient_sample_caps_confidence(): assert rqi.calculate_rqi(current(),history(sample_quality="INSUFFICIENT"))["rqi_confidence_score"]<=39
def test_stale_data_not_applicable(): assert rqi.calculate_rqi(current(freshness_status="STALE",freshness_age_hours=30),history())["rqi_status"]=="STALE_DATA"
def test_deterministic_ranking_and_confidence_adjustment():
    a=rqi.calculate_rqi(current(asset="A"),history(sample_quality="LOW"));z=rqi.calculate_rqi(current(asset="Z",closes_inside_pct=94),history());rows=[a,z];assert rqi.rank_assets(rows)==rqi.rank_assets(list(reversed(rows))) and rqi.rank_assets(rows)[0]["asset"]=="Z"
def test_cspr_diagnostic():
    row=rqi.calculate_rqi(current(asset="CSPR"),history(median_cycle_hours=36));assert rqi.cspr_diagnostic(row)["repeatable_1_2_day_cycle_hypothesis"]=="SUPPORTED_BY_AVAILABLE_DATA"
def test_no_nan_or_infinity(): assert "NaN" not in json.dumps(rqi.calculate_rqi(current(width_stability_cv=float("nan")),history()),allow_nan=False)
def test_no_current_range_redetection_contract(): assert rqi.build_report({"candidates":[current()]},{"assets":[dict(history(),asset="TEST")]},"2026-08-06")["methodology"]["current_range_redetection"] is False
def test_chief_compact_schema():
    row=rqi.calculate_rqi(current(),history());compact={"score":row["rqi_score"],"classification":row["rqi_classification"],"confidence":row["rqi_confidence_score"],"confidence_band":row["rqi_confidence_band"],"research_priority":row["research_priority"],"position_zone":row["position_zone"],"main_strength":row["main_strengths"][0],"primary_risk":row["primary_risk"]};assert len(compact)==8 and "components" not in compact
def test_daily_observations_material_rqi_change():
    old={"range_quality_index":{"top_candidates":[{"asset":"A","rqi_score":60,"rqi_classification":"ACCEPTABLE_RANGE","rqi_confidence_band":"MEDIUM"}]}};new={"range_quality_index":{"top_candidates":[{"asset":"A","rqi_score":67.9,"rqi_classification":"ACCEPTABLE_RANGE","rqi_confidence_band":"MEDIUM"}]}};assert not observations.compare_rqi(new,old);new["range_quality_index"]["top_candidates"][0]["rqi_score"]=68;assert observations.compare_rqi(new,old)
def test_no_strategy_sqlite_mutation_or_order_generation():
    root=Path(__file__).resolve().parents[1];protected=list((root/"journal").glob("*.sqlite"))+[p for p in (root/"STRATEGIES").rglob("*") if p.is_file()];before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected};rqi.calculate_rqi(current(),history());assert before=={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected};source=(root/"scripts/range_quality_index.py").read_text().lower();assert "kraken api" not in source and "order generation" not in source
