from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
from statistics import median
from typing import Any

try:
    from weekly_consolidation_common import ROOT, atomic_write, utc_timestamp
except ModuleNotFoundError:
    from scripts.weekly_consolidation_common import ROOT, atomic_write, utc_timestamp

CONFIG_PATH = ROOT / "config/range_quality_index_v1.json"
CURRENT_PATH = ROOT / "DAILY_REPORTS/DAILY_CONSOLIDATION/latest_daily_consolidation_scan.json"
PERSONALITY_PATH = ROOT / "DAILY_REPORTS/RANGE_PERSONALITY/latest_range_personality.json"
PERSONALITY_REGISTRY_PATH = ROOT / "DECISION_REGISTRY/range_personality.json"
REPORT_DIR = ROOT / "DAILY_REPORTS/RANGE_QUALITY_INDEX"
REGISTRY_PATH = ROOT / "DECISION_REGISTRY/range_quality_index.json"
ALLOWED_STATES = {"VALID_RANGE", "LOWER_HALF", "UPPER_HALF", "NEAR_RANGE_LOW", "NEAR_RANGE_HIGH", "IN_RANGE", "FALSE_BREAKDOWN_RECOVERY", "FALSE_BREAKOUT_RECOVERY"}
RECOVERY_STATES = {"FALSE_BREAKDOWN_RECOVERY", "FALSE_BREAKOUT_RECOVERY"}
INVALID_STATES = {"RANGE_INVALIDATED", "BREAKOUT_CONFIRMED", "BREAKDOWN_CONFIRMED", "ABOVE_RANGE", "BELOW_RANGE"}


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    if cfg.get("version") != "1.0.0" or sum(cfg.get("weights", {}).values()) != 100:
        raise ValueError("invalid Range Quality Index V1 config")
    return cfg


def _num(value: Any, default: float | None = None) -> float | None:
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _clip(value: float) -> float: return max(0.0, min(100.0, value))
def _score(value: Any, scale: float = 1.0, default: float = 50.0) -> float: return _clip((_num(value, default) or 0) * scale)


def position_zone(position: Any) -> str:
    p = _num(position)
    if p is None or p < 0 or p > 100: return "OUTSIDE_RANGE"
    if p <= 30: return "LOWER_ZONE"
    if p < 50: return "LOWER_MIDDLE"
    if p < 70: return "UPPER_MIDDLE"
    return "UPPER_ZONE"


def classification(score: float | None) -> str:
    if score is None: return "NOT_APPLICABLE"
    if score >= 85: return "EXCELLENT_RANGE"
    if score >= 70: return "GOOD_RANGE"
    if score >= 55: return "ACCEPTABLE_RANGE"
    if score >= 40: return "WEAK_RANGE"
    return "POOR_RANGE"


def _quality_label(value: Any) -> str:
    text = str(value or "INSUFFICIENT").upper()
    return text if text in {"HIGH", "MEDIUM", "LOW"} else "LOW"


def calculate_rqi(current: dict[str, Any], historical: dict[str, Any] | None = None,
                  config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Score canonical engine fields only; this function never inspects candles or detects ranges."""
    cfg = config or load_config(); hist = historical or {}; asset = str(current.get("asset") or "UNKNOWN")
    state = str(current.get("range_state") or current.get("structural_state") or current.get("status") or "INSUFFICIENT_DATA").upper()
    freshness = str(current.get("freshness_status") or current.get("freshness") or "UNAVAILABLE").upper()
    age = _num(current.get("freshness_age_hours")); valid = current.get("range_valid", current.get("range_still_valid", current.get("is_valid_horizontal_consolidation")))
    excluded = None
    if freshness == "STALE" or (age is not None and age > cfg["freshness"]["stale_hours"]): excluded = "STALE_DATA"
    elif state in INVALID_STATES or valid is False: excluded = "INVALID_RANGE" if state in {"RANGE_INVALIDATED", "BELOW_RANGE", "ABOVE_RANGE"} or valid is False else "NOT_APPLICABLE"
    elif state not in ALLOWED_STATES: excluded = "INSUFFICIENT_DATA" if state in {"INSUFFICIENT_DATA", "UNKNOWN", ""} else "NOT_APPLICABLE"

    low = _num(current.get("range_low")); high = _num(current.get("range_high")); width = _num(current.get("width_pct", current.get("range_width_pct")))
    if width is None and low and high: width = (high / low - 1) * 100
    base = {"asset": asset, "pair": current.get("kraken_pair") or current.get("pair"), "source_timestamp": current.get("latest_completed_candle_timestamp") or current.get("source_timestamp"),
            "freshness": freshness, "range_state": state, "range_valid": bool(valid), "range_low": low, "midpoint": _num(current.get("midpoint")), "range_high": high,
            "position_pct": _num(current.get("position_pct")), "position_zone": position_zone(current.get("position_pct")), "range_width_pct": width,
            "historical_sample_quality": _quality_label(hist.get("sample_quality")), "source_refs": [str(CURRENT_PATH), str(PERSONALITY_PATH)]}
    if excluded or low is None or high is None or high <= low:
        base.update({"rqi_status": excluded or "INSUFFICIENT_DATA", "rqi_score": None, "rqi_classification": "NOT_APPLICABLE", "rqi_confidence_score": 0.0,
                     "rqi_confidence_band": "LOW", "research_priority": "INVALID_OR_NOT_APPLICABLE", "adjusted_rqi_priority": None, "components": {}, "penalties": [],
                     "main_strengths": [], "main_weaknesses": [excluded or "missing range boundaries"], "primary_risk": excluded or "insufficient canonical input", "invalidation_condition": current.get("invalidation_reason") or "Current range ceases to be valid"})
        return base

    lower = int(_num(current.get("lower_boundary_tests"), 0) or 0); upper = int(_num(current.get("upper_boundary_tests"), 0) or 0); total = lower + upper
    symmetry = 0 if max(lower, upper) == 0 else min(lower, upper) / max(lower, upper)
    boundary = _clip(min(total, 8) / 8 * 55 + symmetry * 35 + (10 if min(lower, upper) >= 2 else 0))
    containment = _score(current.get("closes_inside_pct", current.get("close_containment_percent")))
    confirmed = int(_num(current.get("confirmed_breakouts"), 0) or 0) + int(_num(current.get("confirmed_breakdowns"), 0) or 0)
    excursions = int(_num(current.get("false_breakouts_above", current.get("false_breakouts")), 0) or 0) + int(_num(current.get("false_breakdowns_below", current.get("false_breakdowns")), 0) or 0)
    containment = _clip(containment - confirmed * 40 - min(20, excursions * 2))
    slope = abs(_num(current.get("trend_normalized_slope", current.get("trend_ratio")), .5) or 0); efficiency = _num(current.get("directional_efficiency_ratio"), slope) or 0
    flatness = _clip(100 - 70 * min(1, slope) - 30 * min(1, efficiency) + (10 if current.get("trend_flatness_pass") is True else 0))
    stability = _num(current.get("width_stability")); cv = _num(current.get("width_stability_cv")); stability_score = _score(stability, 100) if stability is not None and stability <= 1 else _clip(100 - 100 * (cv if cv is not None else .5))
    friction = _num(current.get("estimated_total_friction_pct"), .6) or .6; net_width = (width or 0) - friction
    width_score = _clip(stability_score * .65 + (35 if cfg["thresholds"]["minimum_net_width_pct"] <= net_width <= cfg["thresholds"]["maximum_width_pct"] else 5))
    lth = int(_num((current.get("low_to_high") or {}).get("count", current.get("low_to_high_traversals")), 0) or 0); htl = int(_num((current.get("high_to_low") or {}).get("count", current.get("high_to_low_traversals")), 0) or 0)
    traversals = lth + htl; trav_sym = 0 if max(lth, htl) == 0 else min(lth, htl) / max(lth, htl); midpoint_cross = _num(current.get("midpoint_crossings"), traversals) or 0
    traversal = _clip(min(traversals, 6) / 6 * 60 + trav_sym * 25 + min(midpoint_cross, 6) / 6 * 15)
    cycle_cv = _num(hist.get("cycle_duration_cv")); near_median = _num(hist.get("cycles_within_25pct_median_rate")); stability_hist = 100 if hist.get("personality_agreement_across_windows") is True else 55
    cycle = _clip((100 * (1 - min(1, cycle_cv)) if cycle_cv is not None else 35) * .5 + (near_median if near_median is not None else 35) * .3 + stability_hist * .2)
    personality = _clip((_num(hist.get("range_personality_score"), 35) or 35) * .5 + (_num(hist.get("historical_midpoint_recovery_rate"), 35) or 35) * .25 + (_num(hist.get("historical_full_traversal_rate"), 35) or 35) * .25)
    hist_false = _num(hist.get("false_break_rate"), 50) or 0; false_rel = _clip(100 - excursions * 7 - hist_false * .55)
    continuity = str(current.get("continuity_status") or hist.get("continuity_status") or "UNKNOWN"); liquidity_ok = current.get("liquidity_pass") is not False and str(hist.get("liquidity_status", "PASS")) != "FAIL"; spread_ok = current.get("spread_pass") is not False
    data_quality = _clip((35 if freshness == "FRESH" else 15) + (30 if continuity == "CONTINUOUS" else 10) + (20 if liquidity_ok else 0) + (15 if spread_ok else 0))
    components = {"boundary_quality": boundary, "range_containment": containment, "trend_flatness": flatness, "width_quality": width_score, "traversal_quality": traversal,
                  "cycle_regularity": cycle, "historical_personality": personality, "false_break_reliability": false_rel, "liquidity_data_quality": data_quality}
    components = {k: round(v, 2) for k, v in components.items()}; weighted = sum(components[k] * w / 100 for k, w in cfg["weights"].items())
    penalties=[]
    def penalize(code: str, condition: bool):
        if condition: penalties.append({"code": code.upper(), "points": -cfg["penalties"][code]})
    penalize("excessive_false_breaks", excursions >= cfg["thresholds"]["excessive_false_breaks"]); penalize("one_sided_range", total >= 3 and symmetry < cfg["thresholds"]["one_sided_symmetry"])
    penalize("low_liquidity", not liquidity_ok or not spread_ok); penalize("unstable_width", stability_score < 45); penalize("directional_trend", efficiency > cfg["thresholds"]["directional_efficiency_high"] or current.get("trend_flatness_pass") is False)
    penalize("range_too_narrow", net_width < cfg["thresholds"]["minimum_net_width_pct"]); penalize("recovery_state", state in RECOVERY_STATES)
    score = round(_clip(weighted + sum(x["points"] for x in penalties)), 2)
    sample = _quality_label(hist.get("sample_quality")); episodes = int(_num(hist.get("valid_range_episodes"), 0) or 0); hist_trav = int(_num(hist.get("half_cycles"), 0) or 0)
    sample_points = {"HIGH": 90, "MEDIUM": 68, "LOW": 35}[sample]; agreement = 85 if hist.get("intersection_state") == "HISTORICALLY_STRONG_AND_CURRENTLY_ACTIVE" else 55 if hist else 25
    confidence = _clip(sample_points * .35 + min(100, episodes * 12) * .15 + min(100, (traversals + hist_trav) * 10) * .2 + (100 if continuity == "CONTINUOUS" else 35) * .12 + (100 if freshness == "FRESH" else 40) * .08 + agreement * .1)
    if sample == "LOW": confidence = min(39, confidence); penalties.append({"code": "LOW_SAMPLE", "points": 0})
    confidence = round(confidence, 2); band = "HIGH" if confidence >= 70 else "MEDIUM" if confidence >= 40 else "LOW"; adjusted = round(score * cfg["confidence_multipliers"][band], 2)
    strengths = [k for k, v in sorted(components.items(), key=lambda x: (-x[1], x[0])) if v >= 70][:3]; weaknesses = [k for k, v in sorted(components.items(), key=lambda x: (x[1], x[0])) if v < 55][:3]
    base.update({"rqi_status": "APPLICABLE", "rqi_score": score, "rqi_classification": classification(score), "rqi_confidence_score": confidence, "rqi_confidence_band": band,
                 "research_priority": "HIGH_RESEARCH_PRIORITY" if adjusted >= 65 else "MEDIUM_RESEARCH_PRIORITY" if adjusted >= 45 else "LOW_RESEARCH_PRIORITY", "adjusted_rqi_priority": adjusted,
                 "components": components, "penalties": penalties, "main_strengths": strengths, "main_weaknesses": weaknesses, "primary_risk": (weaknesses[0] if weaknesses else penalties[0]["code"] if penalties else "No dominant structural weakness identified"),
                 "invalidation_condition": current.get("invalidation_reason") or "Confirmed directional break or loss of current range validity", "median_cycle_hours": _num(hist.get("median_cycle_hours") or current.get("average_full_cycle_hours")), "liquidity_pass": liquidity_ok})
    return base


def rank_assets(rows: list[dict[str, Any]], cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    quality = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
    valid = [r for r in rows if r.get("rqi_score") is not None]
    return sorted(valid, key=lambda r: (-float(r.get("adjusted_rqi_priority") or 0), -float(r["rqi_score"]), -float(r.get("rqi_confidence_score") or 0), -quality.get(r.get("historical_sample_quality"), 0), not bool(r.get("liquidity_pass")), r["asset"]))


def cspr_diagnostic(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row: return None
    cycle = row.get("median_cycle_hours"); conf = row.get("rqi_confidence_score", 0); cycle_score = row.get("components", {}).get("cycle_regularity")
    conclusion = "INSUFFICIENT_DATA" if row.get("rqi_score") is None or cycle is None else "SUPPORTED_BY_AVAILABLE_DATA" if 24 <= cycle <= 48 and conf >= 70 and (cycle_score or 0) >= 70 else "PARTIALLY_SUPPORTED" if 18 <= cycle <= 72 and (cycle_score or 0) >= 45 else "NOT_SUPPORTED"
    return {"current_range_state": row.get("range_state"), "current_position_pct": row.get("position_pct"), "rqi_score": row.get("rqi_score"), "rqi_classification": row.get("rqi_classification"),
            "confidence": row.get("rqi_confidence_score"), "confidence_band": row.get("rqi_confidence_band"), "boundary_quality": row.get("components", {}).get("boundary_quality"), "cycle_regularity": cycle_score,
            "historical_range_personality": row.get("components", {}).get("historical_personality"), "false_break_reliability": row.get("components", {}).get("false_break_reliability"),
            "liquidity_data_quality": row.get("components", {}).get("liquidity_data_quality"), "main_strengths": row.get("main_strengths", []), "main_weaknesses": row.get("main_weaknesses", []), "repeatable_1_2_day_cycle_hypothesis": conclusion}


def build_report(current: dict[str, Any], personality: dict[str, Any], as_of: Any = None, assets: set[str] | None = None) -> dict[str, Any]:
    cfg=load_config(); historical={str(x.get("asset")):x for x in personality.get("assets", []) if x.get("asset")}; rows=[]
    for item in current.get("candidates", []):
        asset=str(item.get("asset"));
        if assets and asset not in assets and asset != "CSPR": continue
        rows.append(calculate_rqi(item, historical.get(asset), cfg))
    ranked=rank_assets(rows,cfg); acceptable=[r for r in ranked if r["rqi_score"]>=55]; deteriorating=sorted(rows,key=lambda r:(r.get("rqi_score") is not None, r.get("rqi_score") if r.get("rqi_score") is not None else -1, r["asset"]))[:10]
    fastest=sorted([r for r in acceptable if r.get("median_cycle_hours") is not None],key=lambda r:(r["median_cycle_hours"],-r["rqi_score"],r["asset"]))[:5]
    intersection=sorted(ranked,key=lambda r:(-(r["rqi_score"]*(r["components"].get("historical_personality",0)/100)),-r["rqi_confidence_score"],r["asset"]))[:5]
    generated=utc_timestamp(as_of).isoformat(); diag=cspr_diagnostic(next((r for r in rows if r["asset"]=="CSPR"),None))
    return {"version":"1.0.0","generated_at_utc":generated,"report_date":generated[:10],"labels":cfg["labels"],"methodology":{"canonical_inputs_only":True,"current_range_redetection":False,"weights":cfg["weights"],"confidence_is_probability":False},
            "summary":{"assets_evaluated":len(rows),"valid_ranges":len(ranked),"excellent_ranges":sum(r["rqi_classification"]=="EXCELLENT_RANGE" for r in ranked),"good_ranges":sum(r["rqi_classification"]=="GOOD_RANGE" for r in ranked),"low_confidence_ranges":sum(r["rqi_confidence_band"]=="LOW" for r in ranked),"invalid_excluded_ranges":len(rows)-len(ranked)},
            "assets":rows,"top_current_range_quality":ranked[:10],"highest_confidence_ranges":sorted(ranked,key=lambda r:(-r["rqi_confidence_score"],-r["rqi_score"],r["asset"]))[:5],"fastest_acceptable_cycles":fastest,"strongest_historical_current_intersections":intersection,"weak_or_deceptive_ranges":deteriorating[:5],"CSPR_diagnostic":diag}


def _read(path: Path) -> dict[str, Any]: return json.loads(path.read_text()) if path.exists() else {}
def _clean(value: Any) -> Any:
    if isinstance(value,float) and not math.isfinite(value): return None
    if isinstance(value,dict): return {k:_clean(v) for k,v in value.items()}
    if isinstance(value,list): return [_clean(v) for v in value]
    return value


def render_markdown(report: dict[str, Any]) -> str:
    s=report["summary"]; lines=["# Range Quality Index V1","","RESEARCH_ONLY | NOT_A_BUY_SIGNAL | NOT_A_SELL_SIGNAL | USER_DECISION_REQUIRED | LIVE_NOT_AUTHORIZED","","## Summary","",f"- Assets evaluated: {s['assets_evaluated']}",f"- Valid ranges: {s['valid_ranges']}",f"- Excellent ranges: {s['excellent_ranges']}",f"- Good ranges: {s['good_ranges']}",f"- Low-confidence ranges: {s['low_confidence_ranges']}",f"- Invalid/excluded ranges: {s['invalid_excluded_ranges']}","","## Top Current Ranges",""]
    for r in report["top_current_range_quality"]: lines += [f"### {r['asset']}",f"- RQI: {r['rqi_score']} ({r['rqi_classification']})",f"- Confidence: {r['rqi_confidence_score']} ({r['rqi_confidence_band']})",f"- Position: {r['position_zone']} | width: {r.get('range_width_pct')}% | median cycle: {r.get('median_cycle_hours')}h",f"- Main strength: {(r['main_strengths'] or ['unknown'])[0]}",f"- Primary risk: {r['primary_risk']}",""]
    lines += ["## CSPR Diagnostic","",json.dumps(report.get("CSPR_diagnostic"),sort_keys=True),"","## Deteriorating or Invalid Ranges",""]
    for r in report["weak_or_deceptive_ranges"]: lines.append(f"- {r['asset']}: {r['rqi_classification']} / {r['rqi_status']} — {r['primary_risk']}")
    lines += ["","## Limitations","","- Aggregates existing canonical current-range and historical-personality reports; it does not detect ranges.","- Confidence measures evidence coverage and agreement, not likelihood of success.","- Missing historical samples reduce confidence and may limit cycle conclusions.","- No market data is fetched and no execution action is authorized."]
    return "\n".join(lines)+"\n"


def write_outputs(report: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True,exist_ok=True); REGISTRY_PATH.parent.mkdir(parents=True,exist_ok=True); date=report["report_date"]; clean=_clean(report); text=json.dumps(clean,indent=2,sort_keys=True,allow_nan=False)+"\n"; md=render_markdown(clean)
    for p in (REPORT_DIR/f"{date}_range_quality_index.json",REPORT_DIR/"latest_range_quality_index.json"): atomic_write(p,text)
    for p in (REPORT_DIR/f"{date}_range_quality_index.md",REPORT_DIR/"latest_range_quality_index.md"): atomic_write(p,md)
    fields=["asset","pair","range_state","rqi_status","rqi_score","rqi_classification","rqi_confidence_score","rqi_confidence_band","research_priority","position_zone","range_width_pct","median_cycle_hours","primary_risk"]
    for p in (REPORT_DIR/f"{date}_range_quality_index.csv",REPORT_DIR/"latest_range_quality_index.csv"):
        p.parent.mkdir(parents=True,exist_ok=True); temp=p.with_suffix(p.suffix+".tmp")
        with temp.open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r.get(k) for k in fields} for r in clean["assets"])
        os.replace(temp,p)
    registry={"module_name":"range_quality_index","status":"OK","generated_at_utc":clean["generated_at_utc"],"labels":clean["labels"],"top_candidates":clean["top_current_range_quality"][:5],"CSPR_diagnostic":clean["CSPR_diagnostic"],"deteriorating_ranges":clean["weak_or_deceptive_ranges"][:3],"risks":[{"asset":r["asset"],"risk":r["primary_risk"]} for r in clean["weak_or_deceptive_ranges"][:5]],"unknowns":[{"asset":r["asset"],"unknown":"LOW_SAMPLE"} for r in clean["assets"] if r.get("historical_sample_quality")=="LOW"][:5]}
    atomic_write(REGISTRY_PATH,json.dumps(registry,indent=2,sort_keys=True,allow_nan=False)+"\n");return (REPORT_DIR/"latest_range_quality_index.json").resolve()


def generate(as_of: Any=None, assets: set[str]|None=None) -> tuple[dict[str,Any],Path]:
    report=build_report(_read(CURRENT_PATH),_read(PERSONALITY_PATH),as_of,assets);return report,write_outputs(report)


def main() -> None:
    p=argparse.ArgumentParser();p.add_argument("--assets");p.add_argument("--as-of");p.add_argument("--reuse-existing-data",action="store_true");p.add_argument("--verbose",action="store_true");a=p.parse_args();assets={x.strip().upper() for x in a.assets.split(",") if x.strip()} if a.assets else None
    report,path=generate(a.as_of,assets);s=report["summary"];diag=report.get("CSPR_diagnostic") or {}
    print("Range Quality Index V1: SUCCESS");print(f"Assets evaluated: {s['assets_evaluated']}");print(f"Valid ranges: {s['valid_ranges']}");print(f"GOOD or better: {s['excellent_ranges']+s['good_ranges']}");print(f"CSPR diagnostic: {diag.get('repeatable_1_2_day_cycle_hypothesis','INSUFFICIENT_DATA')}");print(f"Saved: {path}")
    if a.verbose: print(json.dumps(report["summary"],sort_keys=True))


if __name__ == "__main__": main()
