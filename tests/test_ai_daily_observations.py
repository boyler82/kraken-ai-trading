from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.ai_daily_observations as obs


def candidate(asset,impact=50,confidence=50,valid=True,momentum="NO_MOMENTUM",hypothesis="WATCH",level=None):
    return {"asset":asset,"decision_metrics":{"decision_impact_score":impact,"evidence_confidence_score":confidence,"current_primary_hypothesis":hypothesis,"opportunity_age_status":"ACTIVE"},
            "evidence":{"supporting_modules":["a"]},"consolidation":{"range_validity":valid,"range_low":level},
            "momentum":{"stage":momentum,"breakout_level":level},"relative_strength":{"relative_trend":"NEUTRAL"},
            "range_personality":{"classification":"RANGE_FRIENDLY"}}


def packet(date="2026-08-06",candidates=None):
    return {"report_date":date,"generated_at_utc":date+"T00:00:00+00:00","candidates":candidates or [],
            "market_state":{"crypto_regime":"BEAR","environment_status":"DEFENSIVE","opportunity_regime":"QUIET","btc_trend_state":"ABOVE_EMA20","breadth_state":"DETERIORATING","universe_outperforming_btc_24h_pct":30},
            "btc_rotation":{"preferred_state":"HOLD_BTC","best_score_advantage":2,"confidence":"LOW"},
            "capital_flow":{"primary_state":"NO_CLEAR_FLOW","confidence":30},
            "portfolio":{"open_positions":[],"missing_position_records":[]}}


def build(cur,old=None,tmp_path=Path("/tmp")):
    cp=tmp_path/"current.json";pp=tmp_path/"previous.json";cp.write_text(json.dumps(cur))
    if old is not None:pp.write_text(json.dumps(old))
    return obs.build_observation(cur,old,cp,pp if old is not None else None,cur["report_date"])


def test_baseline_creation(tmp_path):
    report=build(packet(),None,tmp_path)
    assert report["status"]=="BASELINE_CREATED" and not report["market_changes"]


def test_new_removed_strengthening_weakening_invalidation_confirmation(tmp_path):
    old=packet("2026-08-05",[candidate("OLD"),candidate("UP",40,40),candidate("DOWN",70,70),candidate("INV",valid=True),candidate("BREAK")])
    cur=packet(candidates=[candidate("NEW"),candidate("UP",50,52),candidate("DOWN",60,55),candidate("INV",valid=False),candidate("BREAK",momentum="BREAKOUT_CONFIRMED")])
    report=build(cur,old,tmp_path)
    assert [x["asset"] for x in report["new_candidates"]]==["NEW"]
    assert [x["asset"] for x in report["removed_candidates"]]==["OLD"]
    assert "UP" in [x["asset"] for x in report["strengthening_candidates"]]
    assert "DOWN" in [x["asset"] for x in report["weakening_candidates"]]
    assert [x["asset"] for x in report["new_invalidations"]]==["INV"]
    assert [x["asset"] for x in report["new_confirmations"]]==["BREAK"]


def test_market_rotation_flow_thresholds_and_noise(tmp_path):
    old=packet("2026-08-05");cur=packet();cur["market_state"]["universe_outperforming_btc_24h_pct"]=34.9
    assert not build(cur,old,tmp_path)["market_changes"]
    cur["market_state"]["universe_outperforming_btc_24h_pct"]=35
    cur["btc_rotation"]["preferred_state"]="REVIEW_BTC_TO_ALT";cur["capital_flow"]["primary_state"]="ALT_FLOW"
    report=build(cur,old,tmp_path)
    assert report["market_changes"] and report["rotation_changes"] and report["capital_flow_changes"]


def test_portfolio_is_not_inferred_and_missing_record_is_preserved(tmp_path):
    old=packet("2026-08-05",[candidate("INV",valid=True)]);cur=packet(candidates=[candidate("INV",valid=False),candidate("FAKE")])
    cur["portfolio"]={"open_positions":[{"asset":"INV","quantity":1}],"missing_position_records":[{"asset":"TAO"}]}
    changes=build(cur,old,tmp_path)["portfolio_relevant_changes"]
    assert {x["asset"] for x in changes}=={"INV","TAO"} and "FAKE" not in {x["asset"] for x in changes}


def test_watch_uses_only_packet_level_and_compact_limits(tmp_path):
    old=packet("2026-08-05");cur=packet(candidates=[candidate(f"A{i}",level=100+i) for i in range(8)])
    report=build(cur,old,tmp_path);watch=report["tomorrow_watch"]
    assert len(watch)<=5 and all("999" not in x for x in watch)
    compact=obs.compact_for_strategist(report,"2026-08-06")
    assert len(compact["new_candidates"])<=3 and len(compact["tomorrow_watch"])<=5


def test_previous_selection_never_self_compares(tmp_path,monkeypatch):
    monkeypatch.setattr(obs,"PACKET_DIR",tmp_path)
    cur=tmp_path/"latest_ai_chief_strategist_packet.json";cur.write_text(json.dumps(packet()))
    p4=tmp_path/"2026-08-04_ai_chief_strategist_packet.json";p4.write_text(json.dumps(packet("2026-08-04")))
    p5=tmp_path/"2026-08-05_ai_chief_strategist_packet.json";p5.write_text(json.dumps(packet("2026-08-05")))
    assert obs.select_previous_packet(cur,packet())==p5
    with pytest.raises(ValueError):obs.select_previous_packet(cur,packet(),cur)


def test_idempotent_markdown_jsonl_and_valid_json(tmp_path,monkeypatch):
    monkeypatch.setattr(obs,"OUT_DIR",tmp_path/"reports");monkeypatch.setattr(obs,"JOURNAL_PATH",tmp_path/"journal.md");monkeypatch.setattr(obs,"HISTORY_PATH",tmp_path/"history/history.jsonl")
    report=build(packet(),packet("2026-08-05"),tmp_path);obs.write_outputs(report);obs.write_outputs(report)
    assert obs.JOURNAL_PATH.read_text().count("## 2026-08-06")==1
    lines=obs.HISTORY_PATH.read_text().splitlines();assert len(lines)==1 and json.loads(lines[0])["report_date"]=="2026-08-06"
    assert "NaN" not in json.dumps(report,allow_nan=False) and not list(tmp_path.rglob("*.tmp"))


def test_deterministic_order(tmp_path):
    cur=packet(candidates=[candidate("Z"),candidate("A")]);old=packet("2026-08-05")
    assert [x["asset"] for x in build(cur,old,tmp_path)["new_candidates"]]==["A","Z"]
