from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd

from weekly_consolidation_common import ROOT,atomic_write,utc_timestamp,write_json

PAPER_DIR=ROOT/"PAPER_TRADING"/"BTC_ROTATION";STATE=PAPER_DIR/"rotation_paper_state.json";HISTORY=PAPER_DIR/"rotation_paper_history.csv";DECISIONS=PAPER_DIR/"rotation_paper_decisions.md"
FIELDS=["timestamp","status","previous_holding","proposed_rotation","rotation_reason","exit_reason","entry_relative_price","btc_units_before","btc_units_after","costs_pct","relative_pnl_pct","usd_pnl","maximum_adverse_excursion_pct","maximum_favorable_excursion_pct","holding_duration_hours"]


def load_state()->dict[str,Any]:
    if not STATE.exists(): return {"authorization":"PAPER_NOT_AUTHORIZED","current_paper_holding":"BTC","entry_timestamp":None,"last_rotation_timestamp":None,"rotations":[]}
    payload=json.loads(STATE.read_text())
    if payload.get("authorization")!="PAPER_NOT_AUTHORIZED": raise ValueError("invalid isolated paper state authorization")
    return payload


def controls_from_state(state:dict[str,Any],as_of:Any=None)->dict[str,float]:
    now=utc_timestamp(as_of); entry=state.get("entry_timestamp"); last=state.get("last_rotation_timestamp")
    rotations=[utc_timestamp(x["timestamp"]) for x in state.get("rotations",[]) if x.get("timestamp")]
    return {"hours_held":999 if not entry else max(0,(now-utc_timestamp(entry)).total_seconds()/3600),"hours_since_rotation":999 if not last else max(0,(now-utc_timestamp(last)).total_seconds()/3600),"rotations_7d":sum((now-x).total_seconds()<=7*86400 for x in rotations)}


def record_paper_review(decision:dict[str,Any],as_of:Any=None)->dict[str,Any]:
    """Record a hypothetical manual review only; this module has no exchange integration."""
    state=load_state();now=utc_timestamp(as_of).isoformat();target=decision.get("candidate") or state["current_paper_holding"]
    record={k:None for k in FIELDS};record.update({"timestamp":now,"status":"PAPER_REVIEW_RECORDED_NOT_EXECUTED","previous_holding":state["current_paper_holding"],"proposed_rotation":target,"rotation_reason":decision.get("preferred_state"),"costs_pct":decision.get("estimated_round_trip_cost_pct")})
    state["last_review_timestamp"]=now;state.setdefault("reviews",[]).append(record)
    PAPER_DIR.mkdir(parents=True,exist_ok=True);write_json(STATE,state)
    existing=pd.read_csv(HISTORY).to_dict("records") if HISTORY.exists() and HISTORY.stat().st_size else []
    atomic_write(HISTORY,pd.DataFrame(existing+[record],columns=FIELDS).to_csv(index=False))
    previous=DECISIONS.read_text() if DECISIONS.exists() else "# BTC Rotation Paper Decisions\n\n"
    atomic_write(DECISIONS,previous+f"- {now} | {record['status']} | {record['previous_holding']} → {target} | {record['rotation_reason']}\n")
    return record
