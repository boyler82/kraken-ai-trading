from __future__ import annotations

from typing import Any

LABELS = ["RESEARCH_ONLY", "NOT_A_BUY_SIGNAL", "NOT_A_SELL_SIGNAL",
          "PAPER_NOT_AUTHORIZED", "LIVE_NOT_AUTHORIZED", "USER_DECISION_REQUIRED"]


def compact_profile(row: dict[str, Any]) -> dict[str, Any]:
    return {k: row.get(k) for k in (
        "rank", "asset", "classification", "range_personality_score",
        "valid_range_episodes", "complete_cycles", "median_cycle_hours",
        "median_cycle_move_pct", "cycles_in_2_to_4_pct_band",
        "historical_midpoint_recovery_rate", "historical_full_traversal_rate",
        "false_break_rate", "liquidity_status", "sample_quality",
        "personality_change", "current_range_status", "intersection_state",
        "range_research_priority_score")}


def build_registry(rows: list[dict[str, Any]], generated_at: str,
                   errors: list[str] | None = None) -> dict[str, Any]:
    eligible = [r for r in rows if r.get("classification") != "INSUFFICIENT_DATA"]
    hall = sorted(eligible, key=lambda r: (
        {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(r.get("sample_quality"), 0),
        r.get("range_personality_score") or 0), reverse=True)
    active = [r for r in eligible if r.get("intersection_state") in {
        "HISTORICALLY_STRONG_AND_CURRENTLY_ACTIVE", "CURRENT_RANGE_PERSONALITY_DETERIORATING"}]
    active.sort(key=lambda r: r.get("range_research_priority_score") or 0, reverse=True)
    deteriorating = [r for r in eligible if r.get("personality_change") in {
        "DETERIORATING_RANGE_PERSONALITY", "SHIFTING_TO_TREND", "SHIFTING_TO_CHAOS"}]
    deteriorating.sort(key=lambda r: r.get("range_personality_score") or 0, reverse=True)
    risks = []
    if any(r.get("sample_quality") == "LOW" for r in rows): risks.append("LOW_SAMPLE_ESTIMATES_PRESENT")
    if any(r.get("freshness") == "STALE" for r in rows): risks.append("STALE_DATA_PRESENT")
    if any(r.get("liquidity_status") == "FAIL" for r in rows): risks.append("LOW_LIQUIDITY_ASSETS_PRESENT")
    unknowns = list(dict.fromkeys((errors or []) + [
        "Historical rates are descriptive and are not future probabilities",
        "Personality score is not a probability of profit"]))[:5]
    return {
        "module_name": "range_personality_engine", "generated_at_utc": generated_at,
        "status": "OK" if rows else "UNAVAILABLE",
        "freshness": "FRESH" if any(r.get("freshness") == "FRESH" for r in rows) else "UNAVAILABLE",
        "labels": LABELS,
        "summary": {"assets_analyzed": len(rows),
                    "range_specialists": sum(r.get("classification") == "RANGE_SPECIALIST" for r in rows),
                    "range_friendly": sum(r.get("classification") == "RANGE_FRIENDLY" for r in rows),
                    "current_intersections": len(active)},
        "current_priority_candidates": [compact_profile(r) for r in active[:5]],
        "hall_of_fame": [compact_profile(r) for r in hall[:5]],
        "deteriorating_personalities": [compact_profile(r) for r in deteriorating[:3]],
        "risks": risks[:5], "unknowns": unknowns
    }


def strategist_summary(registry: dict[str, Any]) -> dict[str, Any]:
    if registry.get("status") != "OK":
        return {"range_personality_state": "NO_MATERIAL_UPDATE"}
    return {"range_personality_state": "MATERIAL_UPDATE",
            "hall_of_fame": registry.get("hall_of_fame", [])[:3],
            "active_intersections": registry.get("current_priority_candidates", [])[:3],
            "personality_changes": registry.get("deteriorating_personalities", [])[:3]}
