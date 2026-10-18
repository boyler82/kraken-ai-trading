from __future__ import annotations
import json,math
from pathlib import Path
from typing import Any
import pandas as pd
from weekly_consolidation_common import atomic_write,utc_timestamp

STATUSES={"OK","WARNING","FAILED","UNAVAILABLE"};FRESHNESS={"FRESH","DELAYED","STALE","UNAVAILABLE"}
FIELDS=("module_name","module_version","generated_at_utc","report_date","status","freshness","source_timestamps","summary","candidates","confirmations","conflicts","risks","unknowns","errors","source_files")

def sanitize(value:Any)->Any:
    if isinstance(value,dict):return {str(k):sanitize(v) for k,v in sorted(value.items(),key=lambda x:str(x[0]))}
    if isinstance(value,(list,tuple,set)):return [sanitize(v) for v in value]
    if isinstance(value,(pd.Timestamp,)):return value.isoformat()
    if isinstance(value,(float,np_floating())):return None if not math.isfinite(float(value)) else float(value)
    if pd.isna(value) if not isinstance(value,(str,bytes,bool)) else False:return None
    if hasattr(value,"item"):return sanitize(value.item())
    return value

def np_floating():
    try:
        import numpy as np
        return np.floating
    except ImportError:return float

def make_result(module_name:str,module_version:str,as_of:Any=None,status:str="OK",freshness:str="UNAVAILABLE",**kwargs)->dict[str,Any]:
    now=utc_timestamp(as_of);result={"module_name":module_name,"module_version":module_version,"generated_at_utc":now.isoformat(),"report_date":now.strftime("%Y-%m-%d"),"status":status,"freshness":freshness,"source_timestamps":{},"summary":{},"candidates":[],"confirmations":[],"conflicts":[],"risks":[],"unknowns":[],"errors":[],"source_files":[]};result.update(kwargs);return sanitize(result)

def validate_result(result:dict[str,Any])->list[str]:
    errors=[]
    for field in FIELDS:
        if field not in result:errors.append(f"missing field: {field}")
    if result.get("status") not in STATUSES:errors.append("invalid status")
    if result.get("freshness") not in FRESHNESS:errors.append("invalid freshness")
    try:
        ts=pd.Timestamp(result.get("generated_at_utc"));
        if ts.tzinfo is None:errors.append("generated_at_utc must be timezone-aware")
    except Exception:errors.append("invalid generated_at_utc")
    try:json.dumps(sanitize(result),allow_nan=False)
    except Exception as exc:errors.append(f"not JSON-safe: {exc}")
    return errors

def write_result(path:Path,result:dict[str,Any])->None:
    clean=sanitize(result);errors=validate_result(clean)
    if errors:raise ValueError("; ".join(errors))
    atomic_write(path,json.dumps(clean,indent=2,sort_keys=True,allow_nan=False)+"\n")
