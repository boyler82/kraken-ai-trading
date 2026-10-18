from __future__ import annotations

import argparse
from datetime import timedelta
import json
from pathlib import Path
from typing import Any

import pandas as pd

from consolidation_range_engine import BTC_OPERATIONAL_PATH, _read_operational_15m, completed_4h_bars, detect_range
from weekly_consolidation_common import (
    DEFAULTS, INTRADAY_DIR, LABELS, UNIVERSE_DIR, WATCHLIST_DIR, WEEKLY_REPORT_DIR,
    atomic_write, opportunity_metrics, opportunity_score, risk_flags, utc_timestamp, write_json,
)


def weekly_status(row: dict[str, Any]) -> str:
    if row.get("freshness_status") == "STALE": return "STALE_DATA"
    if row.get("data_quality_status") == "DATA_INCONSISTENT": return "DATA_INCONSISTENT"
    if row.get("status") in {"BREAKOUT_CONFIRMED", "BREAKDOWN_CONFIRMED", "RANGE_INVALIDATED"}: return row["status"]
    if not row.get("is_valid_horizontal_consolidation"): return "POSSIBLE_RANGE"
    return {"NEAR_RANGE_LOW": "ACTIVE_RANGE_NEAR_LOW", "LOWER_HALF": "ACTIVE_RANGE_LOWER_HALF",
            "MID_RANGE": "ACTIVE_RANGE_MID", "UPPER_HALF": "ACTIVE_RANGE_UPPER_HALF",
            "NEAR_RANGE_HIGH": "ACTIVE_RANGE_NEAR_HIGH", "BELOW_RANGE": "BREAKDOWN_PENDING",
            "ABOVE_RANGE": "BREAKOUT_PENDING"}.get(row.get("position_zone"), "POSSIBLE_RANGE")


def flatten_scan(row: dict[str, Any]) -> dict[str, Any]:
    result = {k: v for k, v in row.items() if not isinstance(v, (dict, list))}
    for direction in ("low_to_high", "high_to_low", "full_traversal"):
        for metric, value in row[direction].items():
            if metric != "events": result[f"{direction}_{metric}"] = value
    for name, value in row["weekly_score_components"].items(): result[f"weekly_score_{name}"] = value
    result["risk_flags"] = "|".join(row["risk_flags"])
    return result


def rank_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda r: (not r.get("is_valid_horizontal_consolidation", False), -r["weekly_range_opportunity_score"], -r["estimated_net_range_return_pct"], -(r.get("completed_traversals_per_30d") or 0), -r.get("kraken_24h_quote_volume", 0), r["asset"]))
    for rank, row in enumerate(ordered, 1): row["weekly_rank"] = rank
    return ordered


def select_watchlist(rows: list[dict[str, Any]], date_text: str, size: int = 15) -> list[dict[str, Any]]:
    selected = []
    expiry = (pd.Timestamp(date_text) + timedelta(days=7)).strftime("%Y-%m-%d")
    for row in rows:
        traversals = row["low_to_high"]["count"] + row["high_to_low"]["count"]
        eligible = (row["freshness_status"] == "FRESH" and row["is_valid_horizontal_consolidation"]
                    and row["range_quality"] >= DEFAULTS["watchlist_quality"]
                    and row["estimated_net_range_return_pct"] >= DEFAULTS["watchlist_net_return"]
                    and row["lower_boundary_tests"] >= 2 and row["upper_boundary_tests"] >= 2
                    and traversals >= 2 and row["liquidity_pass"] and not row["risk_flags"])
        if not eligible: continue
        selected.append({"weekly_selection_date": date_text, "watchlist_expiry_date": expiry,
                         "rank": row["weekly_rank"], "asset": row["asset"], "kraken_pair": row["kraken_pair"],
                         "range_low": row["range_low"], "range_high": row["range_high"], "midpoint": row["midpoint"],
                         "width_pct": row["width_pct"], "estimated_net_range_return_pct": row["estimated_net_range_return_pct"],
                         "average_cycle_hours": row["average_full_cycle_hours"], "cycles_per_30d": row["estimated_cycles_per_30d"],
                         "range_quality": row["range_quality"], "opportunity_score": row["weekly_range_opportunity_score"],
                         "current_position_zone": row["position_zone"], "invalidation_reason": None,
                         "source_timestamp": row["latest_available_market_timestamp"]})
        if len(selected) >= size: break
    return selected


def write_watchlist(rows: list[dict[str, Any]]) -> None:
    WATCHLIST_DIR.mkdir(parents=True, exist_ok=True); frame = pd.DataFrame(rows)
    atomic_write(WATCHLIST_DIR / "consolidation_weekly_watchlist.csv", frame.to_csv(index=False))
    write_json(WATCHLIST_DIR / "consolidation_weekly_watchlist.json", {"labels": LABELS, "watchlist": rows})
    lines = ["# Consolidation Weekly Watchlist", "", *LABELS, ""] + ([f"- #{r['rank']} {r['asset']} | {r['current_position_zone']} | quality {r['range_quality']:.2f} | score {r['opportunity_score']:.2f}" for r in rows] if rows else ["No eligible weekly candidates."])
    atomic_write(WATCHLIST_DIR / "consolidation_weekly_watchlist.md", "\n".join(lines) + "\n")


def write_scan(rows: list[dict[str, Any]], date_text: str) -> None:
    WEEKLY_REPORT_DIR.mkdir(parents=True, exist_ok=True); base = WEEKLY_REPORT_DIR / f"{date_text}_weekly_consolidation_scan"
    frame = pd.DataFrame([flatten_scan(row) for row in rows]); csv_text = frame.to_csv(index=False)
    atomic_write(base.with_suffix(".csv"), csv_text); write_json(base.with_suffix(".json"), {"labels": LABELS, "candidates": rows})
    lines = ["# Weekly Consolidation Market Scanner V1", "", *LABELS, "", "THEORETICAL_RANGE_RETURN", "ESTIMATED_NET_RANGE_MOVEMENT", "NOT_REALIZED_PNL", "", "## Top 20 Overall", ""]
    lines += [f"- #{r['weekly_rank']} {r['asset']} | {r['weekly_status']} | score {r['weekly_range_opportunity_score']:.2f} | quality {r['range_quality']:.2f} | gross {r['gross_range_return_pct']:.2f}% | fees {r['estimated_fees_pct']:.2f}% | slippage {r['estimated_slippage_pct']:.2f}% | net {r['estimated_net_range_return_pct']:.2f}% | cycle {r['average_full_cycle_hours']}h" for r in rows[:20]]
    for title, predicate, key in (("Top 10 Near Lower Boundary", lambda r:r["position_zone"]=="NEAR_RANGE_LOW", "weekly_range_opportunity_score"), ("Top 10 Near Upper Boundary", lambda r:r["position_zone"]=="NEAR_RANGE_HIGH", "weekly_range_opportunity_score"), ("Top 10 Fastest Cycles", lambda r:r["average_full_cycle_hours"] is not None, "average_full_cycle_hours"), ("Top 10 Widest Net Ranges", lambda r:True, "estimated_net_range_return_pct"), ("Top 10 Highest Quality", lambda r:True, "range_quality")):
        subset=[r for r in rows if predicate(r)]; subset=sorted(subset,key=lambda r:r[key], reverse=title!="Top 10 Fastest Cycles")[:10]
        lines += ["", f"## {title}", ""] + [f"- {r['asset']} | {key} {r[key]:.4f}" for r in subset]
    lines += ["", "## Invalidated Ranges", ""] + ([f"- {r['asset']} | {r['weekly_status']} | {','.join(r['risk_flags'])}" for r in rows if r["weekly_status"] in {"RANGE_INVALIDATED","BREAKOUT_CONFIRMED","BREAKDOWN_CONFIRMED"}] or ["- None"])
    lines += ["", "## Stale or Unavailable", ""] + ([f"- {r['asset']} | {r['weekly_status']}" for r in rows if r["weekly_status"] in {"STALE_DATA","UNAVAILABLE","DATA_INCONSISTENT"}] or ["- None"])
    atomic_write(base.with_suffix(".md"), "\n".join(lines)+"\n")
    for ext in (".csv", ".json", ".md"): atomic_write(WEEKLY_REPORT_DIR / f"latest_weekly_consolidation_scan{ext}", base.with_suffix(ext).read_text(), backup=False)


def scan(as_of: Any = None, watchlist_size: int = 15, dry_run: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cutoff=utc_timestamp(as_of); universe=pd.read_csv(UNIVERSE_DIR/"weekly_consolidation_universe.csv")
    quality_path=WEEKLY_REPORT_DIR/f"{cutoff:%Y-%m-%d}_intraday_quality.csv"; quality=pd.read_csv(quality_path) if quality_path.exists() else pd.DataFrame()
    quality_map={str(r["asset"]):r for _,r in quality.iterrows()} if not quality.empty else {}
    rows=[]
    for _,item in universe[universe["inclusion_status"]=="INCLUDED"].iterrows():
        asset,pair=str(item["symbol"]),str(item["selected_kraken_pair"]); q=quality_map.get(asset,{})
        try:
            if asset=="BTC": raw=_read_operational_15m(BTC_OPERATIONAL_PATH); bars=completed_4h_bars(raw,cutoff,"15m")
            else: raw=pd.read_csv(INTRADAY_DIR/f"{pair}_1H.csv"); bars=completed_4h_bars(raw,cutoff,"1H")
            row=detect_range(bars,asset); row.update({"kraken_pair":pair,"kraken_24h_quote_volume":float(item.get("kraken_24h_quote_volume",0)),"liquidity_pass":bool(item.get("liquidity_pass",False)),"spread_pass":bool(item.get("spread_pass",False)),"mapping_uncertain":bool(item.get("mapping_uncertain",False)),"freshness_status":q.get("freshness_status","UNAVAILABLE"),"data_quality_status":"OK" if q.get("usable_for_consolidation_scan",False) else "DATA_INCONSISTENT"})
            row.update(opportunity_metrics(row)); row["risk_flags"]=risk_flags(row,row["liquidity_pass"],row["spread_pass"]); score,components=opportunity_score(row); row["weekly_range_opportunity_score"]=score; row["weekly_score_components"]=components; row["weekly_status"]=weekly_status(row); rows.append(row)
        except Exception:
            continue
    rows=rank_rows(rows); watchlist=select_watchlist(rows,cutoff.strftime("%Y-%m-%d"),watchlist_size)
    if not dry_run: write_scan(rows,cutoff.strftime("%Y-%m-%d")); write_watchlist(watchlist)
    return rows,watchlist


def main() -> None:
    p=argparse.ArgumentParser();p.add_argument("--as-of");p.add_argument("--watchlist-size",type=int,default=15);p.add_argument("--dry-run",action="store_true");a=p.parse_args(); rows,watch=scan(a.as_of,a.watchlist_size,a.dry_run);print(f"Scanned: {len(rows)}; watchlist: {len(watch)}")
if __name__=="__main__":main()
