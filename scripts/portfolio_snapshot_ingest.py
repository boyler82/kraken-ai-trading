from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/portfolio_snapshot_ingest_v1.json"
MEMORY = ROOT / "PORTFOLIO_MEMORY"
CURRENT = MEMORY / "CURRENT/latest_portfolio_snapshot.json"
SNAPSHOTS = MEMORY / "SNAPSHOTS"
REJECTED = MEMORY / "REJECTED"


def read_json(path: Path, default=None):
    try: return json.loads(path.read_text())
    except Exception: return {} if default is None else default


def finite_number(value: Any) -> float | None:
    try:
        number=float(value)
        return number if math.isfinite(number) else None
    except (TypeError,ValueError): return None


def validate(payload: dict, previous: dict | None = None, config: dict | None = None) -> dict:
    cfg=config or read_json(CONFIG);errors=[];warnings=[];normalized=[];seen=set()
    extractor=payload.get("extraction",{}).get("method")
    if extractor not in cfg["allowed_extractors"]:errors.append("UNSUPPORTED_EXTRACTION_METHOD")
    if not payload.get("captured_at_utc"):errors.append("CAPTURE_TIMESTAMP_REQUIRED")
    for index,source in enumerate(payload.get("positions",[])):
        asset=str(source.get("asset") or "").strip().upper();quantity=finite_number(source.get("quantity"));value=finite_number(source.get("market_value_usd"));weight=finite_number(source.get("portfolio_weight_pct"));pnl=finite_number(source.get("unrealized_pnl_usd"));pnl_pct=finite_number(source.get("unrealized_pnl_pct"))
        prefix=f"ROW_{index+1}_{asset or 'UNKNOWN'}"
        if not asset:errors.append(f"{prefix}_ASSET_REQUIRED");continue
        if asset in seen:errors.append(f"DUPLICATE_ASSET_{asset}");continue
        seen.add(asset)
        if quantity is None or quantity < 0:errors.append(f"{prefix}_INVALID_QUANTITY")
        if value is None or value < 0:errors.append(f"{prefix}_INVALID_MARKET_VALUE")
        if weight is None or not 0 <= weight <= 100:errors.append(f"{prefix}_INVALID_WEIGHT")
        if any(x.startswith(prefix) for x in errors):continue
        cost_basis=value-pnl if pnl is not None else None
        entry_price=cost_basis/quantity if cost_basis is not None and quantity else None
        if cost_basis is not None and cost_basis <= 0:errors.append(f"{prefix}_INVALID_DERIVED_COST_BASIS")
        if pnl is not None and pnl_pct is not None and cost_basis:
            derived=100*pnl/cost_basis
            if abs(derived-pnl_pct)>.15:errors.append(f"{prefix}_PNL_PERCENT_MISMATCH")
        normalized.append({"asset":asset,"quantity":quantity,"portfolio_weight_pct":weight,"market_value_usd":value,"unrealized_pnl_usd":pnl,"unrealized_pnl_pct":pnl_pct,"cost_basis_usd":cost_basis,"derived_entry_price_usd":entry_price,"source_confidence":source.get("source_confidence","VISIBLE"),"validation_notes":source.get("validation_notes",[])})
    visible_total=sum(x["market_value_usd"] for x in normalized);displayed=finite_number(payload.get("displayed_total_value_usd"));tolerance=max(cfg["total_tolerance_usd"],visible_total*cfg["total_tolerance_pct"]/100)
    if displayed is None:warnings.append("DISPLAYED_TOTAL_NOT_VISIBLE")
    elif abs(displayed-visible_total)>tolerance:errors.append("VISIBLE_TOTAL_MISMATCH")
    total_weight=sum(x["portfolio_weight_pct"] for x in normalized)
    if not cfg["minimum_total_weight_pct"] <= total_weight <= cfg["maximum_total_weight_pct"]:warnings.append("VISIBLE_WEIGHTS_DO_NOT_SUM_TO_APPROX_100")
    implied_total=displayed or visible_total
    if implied_total:
        for row in normalized:
            implied=100*row["market_value_usd"]/implied_total
            if abs(implied-row["portfolio_weight_pct"])>cfg["weight_tolerance_percentage_points"]:errors.append(f"WEIGHT_VALUE_MISMATCH_{row['asset']}")
    previous_rows={x["asset"]:x for x in (previous or {}).get("positions",[])}
    large=[]
    for row in normalized:
        old=previous_rows.get(row["asset"])
        if not old:continue
        old_q=finite_number(old.get("quantity"));old_v=finite_number(old.get("market_value_usd"))
        q_change=abs(row["quantity"]/old_q-1)*100 if old_q else 0;v_change=abs(row["market_value_usd"]/old_v-1)*100 if old_v else 0
        if row["market_value_usd"]>=cfg["large_change_minimum_usd"] and (q_change>cfg["large_quantity_change_pct"] or v_change>cfg["large_value_change_pct"]):large.append({"asset":row["asset"],"quantity_change_pct":q_change,"value_change_pct":v_change})
    if large:warnings.append("LARGE_CHANGE_VS_PREVIOUS_CURRENT")
    return {"valid":not errors,"errors":sorted(set(errors)),"warnings":sorted(set(warnings)),"positions":normalized,"computed_visible_total_usd":visible_total,"visible_weight_sum_pct":total_weight,"large_changes":large}


def atomic_write(path:Path,text:str):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+".tmp");tmp.write_text(text);tmp.replace(path)


def ingest(input_path:Path,promote:bool=True,accept_large_changes:bool=False,current_path:Path=CURRENT)->dict:
    source=read_json(input_path);previous=read_json(current_path,{}) if current_path.exists() else None;result=validate(source,previous)
    blocked_large=bool(result["large_changes"] and not accept_large_changes)
    status="REJECTED" if not result["valid"] else "REVIEW_REQUIRED" if blocked_large else "ACCEPTED"
    record={"schema_version":"PORTFOLIO_SNAPSHOT_V1","status":status,"source":source.get("source"),"captured_at_utc":source.get("captured_at_utc"),"extraction":source.get("extraction"),"positions":result["positions"],"computed_visible_total_usd":result["computed_visible_total_usd"],"displayed_total_value_usd":source.get("displayed_total_value_usd"),"validation":{"errors":result["errors"],"warnings":result["warnings"],"visible_weight_sum_pct":result["visible_weight_sum_pct"],"large_changes":result["large_changes"]},"research_only":True}
    encoded=json.dumps(record,indent=2,sort_keys=True,allow_nan=False)+"\n";digest=hashlib.sha256(encoded.encode()).hexdigest()[:16];directory=REJECTED if status=="REJECTED" else SNAPSHOTS;snapshot=directory/f"{str(record['captured_at_utc'])[:10]}_{digest}.json"
    if not snapshot.exists():atomic_write(snapshot,encoded)
    if promote and status=="ACCEPTED":atomic_write(current_path,encoded)
    record["snapshot_path"]=str(snapshot);record["promoted_to_current"]=bool(promote and status=="ACCEPTED");return record


def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--validate-only",action="store_true");p.add_argument("--accept-large-changes",action="store_true");a=p.parse_args();result=ingest(a.input,not a.validate_only,a.accept_large_changes);print(json.dumps({k:result[k] for k in ("status","promoted_to_current","snapshot_path","validation")},indent=2));raise SystemExit(0 if result["status"]=="ACCEPTED" else 2)
if __name__=="__main__":main()
