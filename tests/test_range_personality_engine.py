from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.range_personality_engine import (current_intersection, extract_traversals,
    personality_change)


def candles(values):
    values=np.asarray(values,float); return pd.DataFrame({"timestamp":pd.date_range("2026-01-01",periods=len(values),freq="4h",tz="UTC"),
        "open":values,"high":values+.15,"low":values-.15,"close":values,"volume":1000})


def test_event_debouncing_does_not_duplicate_same_boundary():
    frame=candles([100,100.1,100,100.2,102,104,105,105.1,105,104,102,100])
    traversals=extract_traversals(frame,100,105)
    assert [x["direction"] for x in traversals]==["LOW_TO_HIGH","HIGH_TO_LOW"]


def test_personality_change_states():
    long={"classification":"RANGE_FRIENDLY","range_personality_score":60}
    assert personality_change({"classification":"RANGE_FRIENDLY","range_personality_score":62},{"classification":"RANGE_FRIENDLY","range_personality_score":60},long)=="STABLE_RANGE_PERSONALITY"
    assert personality_change({"classification":"RANGE_SPECIALIST","range_personality_score":80},{"classification":"RANGE_FRIENDLY","range_personality_score":60},long)=="IMPROVING_RANGE_PERSONALITY"
    assert personality_change({"classification":"TREND_DOMINANT","range_personality_score":30},{"classification":"RANGE_FRIENDLY","range_personality_score":65},long)=="SHIFTING_TO_TREND"
    assert personality_change({"classification":"CHAOTIC","range_personality_score":30},{"classification":"RANGE_FRIENDLY","range_personality_score":65},long)=="SHIFTING_TO_CHAOS"


def test_current_intersections():
    strong={"classification":"RANGE_SPECIALIST","range_personality_score":80,"median_cycle_hours":40,"freshness":"FRESH","liquidity_status":"PASS","personality_change":"STABLE_RANGE_PERSONALITY"}
    assert current_intersection(strong,{"range_still_valid":True,"range_quality":80})["intersection_state"]=="HISTORICALLY_STRONG_AND_CURRENTLY_ACTIVE"
    assert current_intersection(strong,{})["intersection_state"]=="HISTORICALLY_STRONG_NO_CURRENT_RANGE"
    weak={**strong,"classification":"MIXED_BEHAVIOR"}
    assert current_intersection(weak,{"range_still_valid":True})["intersection_state"]=="CURRENT_RANGE_BUT_WEAK_HISTORY"
    bad={**strong,"personality_change":"DETERIORATING_RANGE_PERSONALITY"}
    assert current_intersection(bad,{"range_still_valid":True})["intersection_state"]=="CURRENT_RANGE_PERSONALITY_DETERIORATING"
