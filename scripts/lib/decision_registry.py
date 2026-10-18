from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from lib.research_module_contract import sanitize
from weekly_consolidation_common import ROOT,atomic_write
REGISTRY_DIR=ROOT/"DECISION_REGISTRY"
NAMES=("relative_strength","leadership_rotation","capital_flow","ai_confidence","opportunity_aging","consolidation","momentum","btc_rotation","rsi2","market_regime","portfolio","data_quality")
def write_record(name:str,record:dict[str,Any])->Path:
    if name not in NAMES:raise ValueError(f"unknown registry record: {name}")
    path=REGISTRY_DIR/f"{name}.json";atomic_write(path,json.dumps(sanitize(record),indent=2,sort_keys=True,allow_nan=False)+"\n");return path
def read_record(name:str)->dict[str,Any]:
    path=REGISTRY_DIR/f"{name}.json"
    if not path.exists():return {"module_name":name,"status":"UNAVAILABLE","summary":{},"candidates":[],"risks":[],"unknowns":["registry record unavailable"]}
    try:return json.loads(path.read_text())
    except Exception as exc:return {"module_name":name,"status":"FAILED","summary":{},"candidates":[],"risks":[],"unknowns":[],"errors":[str(exc)]}
def read_all()->dict[str,dict[str,Any]]:return {name:read_record(name) for name in NAMES}
