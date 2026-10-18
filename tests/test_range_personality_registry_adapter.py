from scripts.range_personality_registry_adapter import build_registry, strategist_summary


def row(i, change="STABLE_RANGE_PERSONALITY"):
    return {"asset":f"A{i}","classification":"RANGE_SPECIALIST","range_personality_score":90-i,
            "sample_quality":"HIGH","intersection_state":"HISTORICALLY_STRONG_AND_CURRENTLY_ACTIVE",
            "range_research_priority_score":80-i,"personality_change":change,"freshness":"FRESH"}


def test_registry_and_packet_limits():
    rows=[row(i,"DETERIORATING_RANGE_PERSONALITY" if i<6 else "STABLE_RANGE_PERSONALITY") for i in range(20)]
    registry=build_registry(rows,"2026-01-01T00:00:00Z")
    assert len(registry["current_priority_candidates"])<=5
    assert len(registry["hall_of_fame"])<=5
    assert len(registry["deteriorating_personalities"])<=3
    packet=strategist_summary(registry)
    assert len(packet["hall_of_fame"])<=3
    assert len(packet["active_intersections"])<=3
    assert len(packet["personality_changes"])<=3
