from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

import pandas as pd
from lib.universe import project_memory_db, report_dir
from lib.portfolio_positions import load_active_positions, open_position_summary


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = report_dir()
JOURNAL_DIR = ROOT / "journal"
PORTFOLIO_POSITIONS = JOURNAL_DIR / "portfolio_positions.csv"
DAILY_CONSOLIDATION_WATCHLIST = ROOT / "WATCHLISTS" / "consolidation_daily_watchlist.csv"
MOMENTUM_REPORT_DIR = ROOT / "DAILY_REPORTS" / "MOMENTUM_BREAKOUT"
ROTATION_DASHBOARD = ROOT / "DAILY_REPORTS" / "BTC_ROTATION" / "latest_btc_rotation_dashboard.json"
ANALYST_PACKET_DIR = ROOT / "DAILY_REPORTS" / "ANALYST_PACKET"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print a compact morning brief from daily reports.")
    parser.add_argument(
        "--date",
        default=None,
        help="Report date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument("--universe", choices=["full_crypto", "btc_only"], default=None)
    return parser.parse_args()


def _report_date(arg_date: str | None) -> str:
    if arg_date:
        return arg_date
    return pd.Timestamp.today().strftime("%Y-%m-%d")


def _path_for(date_text: str, suffix: str) -> Path:
    return REPORT_DIR / f"{date_text}_{suffix}"


def _read_text(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _read_json(path: Path) -> dict:
    if not path.exists(): return {}
    try: return json.loads(path.read_text())
    except (json.JSONDecodeError,OSError): return {}


def render_analyst_packet_brief(packet: dict) -> str:
    """Render only the decision packet fields intended for terminal use."""
    if not packet:
        return ""
    context = packet.get("market_context", {})
    decision = packet.get("decision_summary", {})
    rotation = packet.get("rotation", {})
    positions = packet.get("active_position_context", {}).get("open_positions", [])
    candidates = []
    for kind, rows in (
        ("CONSOLIDATION", packet.get("top_consolidations", [])),
        ("MOMENTUM", packet.get("top_momentum", [])),
        ("ROTATION", rotation.get("alternatives", [])),
    ):
        for row in rows:
            score = row.get("opportunity_score", row.get("momentum_score", row.get("score")))
            candidates.append((kind, row.get("asset"), score))
    lines = [
        f"Date: {packet.get('report_date')}",
        "MARKET CONTEXT",
        f"- regime {context.get('crypto_regime')} | volatility {context.get('volatility_regime')} | opportunity {context.get('opportunity_regime')} | environment {context.get('environment_score')} {context.get('environment_status')} | freshness {context.get('freshness')}",
        "STRONGEST HYPOTHESIS",
        f"- {decision.get('strongest_current_hypothesis')} | {decision.get('strongest_candidate')} | {decision.get('strongest_reason')} | confidence {decision.get('confidence')}",
        "TOP 3 CANDIDATES",
    ]
    lines.extend(f"- {kind} | {asset} | score {score}" for kind, asset, score in candidates[:3])
    if not candidates:
        lines.append("- NONE")
    lines.extend(["ROTATION RESULT", f"- {rotation.get('preferred_state')} | best {rotation.get('best_candidate')} | net edge {rotation.get('theoretical_net_relative_edge_pct')} | cost guard {rotation.get('cost_guard')}", "ACTIVE-POSITION ALERTS"])
    if positions:
        for row in positions:
            lines.append(f"- {row.get('asset')} | net PnL {row.get('estimated_net_pnl_pct')}% | invalidation distance {row.get('distance_to_invalidation_pct')}% | risk {','.join(row.get('current_risk_flags', [])) or 'NONE'}")
    else:
        lines.append("- NONE")
    lines.append("TOP 5 RISKS")
    lines.extend(f"- {r.get('severity')} | {r.get('asset')} | {r.get('code')} | {r.get('evidence')}" for r in packet.get("risk_summary", [])[:5])
    lines.append("NEXT CONDITIONS")
    lines.extend([f"- invalidation {decision.get('primary_invalidation')}", f"- RSI2 {packet.get('rsi2', {}).get('next_trigger')}", f"- action {decision.get('immediate_action_requirement')}"])
    return "\n".join(lines)


def _first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def _extract_section_value(md: str, heading: str) -> str | None:
    pattern = rf"(?ms)^##+\s+{re.escape(heading)}\s*$\n(.*?)(?=^##+\s+|\Z)"
    match = re.search(pattern, md)
    if not match:
        return None
    section = match.group(1).strip()
    if not section:
        return None
    for line in section.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("- "):
            return line[2:].strip()
        return line
    return None


def _extract_bullets(md: str, heading: str) -> list[str]:
    pattern = rf"(?ms)^##+\s+{re.escape(heading)}\s*$\n(.*?)(?=^##+\s+|\Z)"
    match = re.search(pattern, md)
    if not match:
        return []
    section = match.group(1).strip()
    return [line[2:].strip() for line in section.splitlines() if line.strip().startswith("- ")]


def _extract_section_lines(md: str, heading: str) -> list[str]:
    """Return report section content without changing the source report."""
    pattern = rf"(?ms)^##+\s+{re.escape(heading)}\s*$\n(.*?)(?=^##+\s+|\Z)"
    match = re.search(pattern, md)
    if not match:
        return []
    rows = []
    for line in match.group(1).strip().splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(line[2:].strip() if line.startswith("- ") else line)
    return rows


def _load_daily_decision(date_text: str) -> str:
    path = _path_for(date_text, "daily_decision_dashboard.md")
    return path.read_text() if path.exists() else ""


def _load_trade_candidates(date_text: str) -> pd.DataFrame:
    path = _path_for(date_text, "trade_candidate_dashboard.csv")
    return _read_csv(path)


def _load_project_health(date_text: str) -> str:
    path = _path_for(date_text, "project_health_check.md")
    return path.read_text() if path.exists() else ""


def _load_signal_exit_calendar(date_text: str) -> pd.DataFrame:
    db_path = project_memory_db()
    if not db_path.exists():
        return pd.DataFrame()
    try:
        with sqlite3.connect(db_path) as conn:
            return pd.read_sql_query(
                "SELECT signal_id, asset, date, planned_exit_date, status "
                "FROM signals WHERE status = 'OPEN' ORDER BY asset",
                conn,
            )
    except (sqlite3.Error, pd.errors.DatabaseError):
        return pd.DataFrame()


def _load_realized_trades(date_text: str) -> pd.DataFrame:
    report_path = _path_for(date_text, "realized_trades.csv")
    if report_path.exists():
        return _read_csv(report_path)
    journal_path = JOURNAL_DIR / "realized_trades.csv"
    return _read_csv(journal_path)


def _fmt_num(value) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    magnitude = abs(num)
    if magnitude >= 1000:
        return f"{num:,.2f}"
    if magnitude >= 1:
        return f"{num:.4f}"
    if magnitude >= .01:
        return f"{num:.6f}"
    return f"{num:.8f}"


def _readable(value, missing: str = "n/a") -> str:
    return missing if value is None or pd.isna(value) else str(value)


def _fmt_metric(value) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.1f}"


def _final_decision(md: str) -> str:
    value = _extract_section_value(md, "FINAL DECISION")
    if value:
        return value
    return _first_match(md, [r"^Date:\s*(.+)$"]) or "n/a"


def _portfolio_summary(md: str) -> str:
    rows = _extract_bullets(md, "CURRENT POSITION")
    if rows:
        if len(rows) == 1 and rows[0] == "No open positions":
            return "No open positions"
        return " | ".join(rows[:3])
    rows = _extract_bullets(md, "PORTFOLIO ALLOCATION")
    if rows:
        return " | ".join(rows[:2])
    return "No open positions"


def _top_candidates(df: pd.DataFrame) -> list[str]:
    if df.empty or "asset" not in df.columns:
        return []
    cols = [c for c in ["asset", "priority", "readiness_pct", "research_score", "recommendation"] if c in df.columns]
    out = []
    for _, row in df.head(3).iterrows():
        parts = [str(row["asset"])]
        if "priority" in cols:
            parts.append(f"{row.get('priority')}")
        if "readiness_pct" in cols:
            parts.append(f"ready {_fmt_num(row.get('readiness_pct'))}")
        if "research_score" in cols:
            parts.append(f"research {_fmt_num(row.get('research_score'))}")
        if "recommendation" in cols:
            parts.append(f"{row.get('recommendation')}")
        out.append(" | ".join(parts))
    return out


def _setup_rows(df: pd.DataFrame, status: str) -> list[str]:
    if df.empty or "current_setup_status" not in df.columns:
        return []
    selected = df[df["current_setup_status"].astype(str).str.upper() == status]
    rows = []
    for _, row in selected.iterrows():
        rows.append(
            f"{row.get('asset')} | {row.get('recommendation')} | "
            f"readiness {_fmt_num(row.get('readiness_pct'))} | "
            f"research {_fmt_num(row.get('research_score'))}"
        )
    return rows


def _paper_signals(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return []
    if "status" in df.columns:
        statuses = df["status"].astype(str).str.upper()
        df = df[statuses.isin({"OPEN", "WAITING"})]
    rows = []
    for _, row in df.iterrows():
        rows.append(
            f"{row.get('signal_id')} | {row.get('asset')} | date {row.get('date')} | "
            f"planned exit {row.get('planned_exit_date')} | {row.get('status')}"
        )
    return rows


def _print_section(title: str, rows: list[str], empty_text: str) -> None:
    print(f"\n{title}")
    if rows:
        for row in rows:
            print(f"- {row}")
    else:
        print(empty_text)


def _watchlist_count(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    if "watch_status" in df.columns:
        return int(df["watch_status"].astype(str).str.contains("WATCH", case=False, na=False).sum())
    if "recommendation" in df.columns:
        return int(df["recommendation"].astype(str).str.contains("WATCH", case=False, na=False).sum())
    return 0


def _watchlist_count_from_md(md: str) -> int:
    rows = _extract_bullets(md, "WATCHLIST")
    if not rows:
        return 0
    if len(rows) == 1 and "No watchlist assets" in rows[0]:
        return 0
    return len(rows)


def _open_signal_exits(df: pd.DataFrame) -> str:
    if df.empty:
        return "No open signal exits"
    if "asset" in df.columns:
        rows = []
        for _, row in df.head(3).iterrows():
            asset = row.get("asset")
            planned = row.get("planned_exit_date") or row.get("exit_date")
            status = row.get("status")
            rows.append(f"{asset} | {planned} | {status}")
        return f"{len(df)}: " + " | ".join(rows)
    return f"{len(df)} open signal exits"


def _consolidation_range_rows(df: pd.DataFrame) -> list[str]:
    """Render only brief-eligible research ranges; malformed reports fail closed."""
    required = {
        "asset", "status", "range_state", "range_start", "duration_bars",
        "range_low", "range_high", "midpoint", "width_pct", "latest_available_market_price",
        "position_pct", "lower_boundary_tests", "upper_boundary_tests",
        "false_breakouts_above", "false_breakdowns_below",
        "low_to_high_count", "high_to_low_count", "full_traversal_average_hours",
        "range_quality", "breakout_risk",
    }
    if df.empty or not required.issubset(df.columns):
        return []
    allowed_statuses = {
        "NEAR_RANGE_LOW", "NEAR_RANGE_HIGH", "FALSE_BREAKOUT_ABOVE",
        "FALSE_BREAKDOWN_BELOW",
    }
    mask = df["status"].astype(str).str.upper().isin(allowed_statuses)
    mask |= df["range_state"].astype(str).str.upper().eq("VALID_RANGE")
    excluded_statuses = {
        "BREAKOUT_CONFIRMED", "BREAKDOWN_CONFIRMED", "RANGE_INVALIDATED",
        "DATA_INCONSISTENT", "STALE_DATA", "WEAK_RANGE", "POSSIBLE_RANGE",
    }
    mask &= ~df["status"].astype(str).str.upper().isin(excluded_statuses)
    selected = df[mask].copy().sort_values(["range_quality", "asset"], ascending=[False, True])
    rows = []
    for _, row in selected.iterrows():
        rows.append(
            f"{row['asset']} | {row['status']} | start {row['range_start']} | "
            f"duration {_fmt_num(row['duration_bars'])} bars | low {_fmt_num(row['range_low'])} | "
            f"high {_fmt_num(row['range_high'])} | midpoint {_fmt_num(row['midpoint'])} | "
            f"width {_fmt_num(row['width_pct'])}% | latest available {_fmt_num(row['latest_available_market_price'])} | "
            f"location {row.get('position_zone', row.get('current_location', 'UNKNOWN'))}"
            f"{' (' + _fmt_num(row['position_pct']) + '% raw)' if float(row['position_pct']) < 0 or float(row['position_pct']) > 100 else ''} | tests L/U "
            f"{_fmt_num(row['lower_boundary_tests'])}/{_fmt_num(row['upper_boundary_tests'])} | "
            f"false A/B {_fmt_num(row['false_breakouts_above'])}/{_fmt_num(row['false_breakdowns_below'])} | "
            f"traversals L→H/H→L {_fmt_num(row['low_to_high_count'])}/{_fmt_num(row['high_to_low_count'])} | "
            f"avg traversal {_fmt_num(row['full_traversal_average_hours'])}h | "
            f"quality {_fmt_num(row['range_quality'])} | breakout risk {row['breakout_risk']}"
        )
    return rows


def _weekly_consolidation_rows(df: pd.DataFrame, stale: bool = False) -> list[str]:
    required = {
        "asset", "simple_color", "simple_zone", "simple_display", "range_low",
        "range_high", "midpoint", "current_price", "position_pct",
        "estimated_net_movement_to_midpoint_pct", "estimated_net_movement_to_high_pct",
        "average_cycle_hours", "range_quality", "freshness_status", "range_still_valid",
    }
    if df.empty or not required.issubset(df.columns):
        return []
    selected = df.copy()
    color_order = {"GREEN": 0, "YELLOW": 1, "RED": 2}
    selected["_color"] = selected["simple_color"].map(color_order).fillna(2)
    selected["_position"] = pd.to_numeric(selected["position_pct"], errors="coerce").fillna(float("inf"))
    selected["_net_high"] = pd.to_numeric(selected["estimated_net_movement_to_high_pct"], errors="coerce").fillna(float("-inf"))
    selected["_quality"] = pd.to_numeric(selected["range_quality"], errors="coerce").fillna(float("-inf"))
    selected["_cycle"] = pd.to_numeric(selected["average_cycle_hours"], errors="coerce").fillna(float("inf"))
    selected["_fresh"] = ~selected["freshness_status"].astype(str).str.upper().eq("FRESH")
    selected = selected.sort_values(
        ["_color", "_position", "_net_high", "_quality", "_cycle", "_fresh", "asset"],
        ascending=[True, True, False, False, True, True, True], kind="mergesort",
    )
    emoji = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}
    rows = []
    for _, r in selected.iterrows():
        valid = str(r["range_still_valid"]).lower() in {"true", "1"}
        rows.append(
            f"{emoji.get(r['simple_color'], '🔴')} {r['asset']} | {r['simple_display']} | "
            f"current {_fmt_num(r['current_price'])} | range {_fmt_num(r['range_low'])}–{_fmt_num(r['range_high'])} | "
            f"midpoint {_fmt_num(r['midpoint'])} | position {_fmt_metric(r['position_pct'])}% | "
            f"net to midpoint {_fmt_metric(r['estimated_net_movement_to_midpoint_pct'])}% | "
            f"net to high {_fmt_metric(r['estimated_net_movement_to_high_pct'])}% | "
            f"cycle {_fmt_metric(r['average_cycle_hours'])}h | quality {_fmt_metric(r['range_quality'])} | "
            f"{r['freshness_status']} | range valid {'YES' if valid else 'NO'}"
        )
    return rows


def _daily_consolidation_rows(df: pd.DataFrame) -> list[str]:
    required = {
        "asset", "simple_color", "simple_display", "current_price", "range_low",
        "midpoint", "range_high", "position_pct", "estimated_net_movement_to_midpoint_pct",
        "estimated_net_movement_to_high_pct", "average_cycle_hours", "cycles_per_30d",
        "range_quality", "opportunity_score", "freshness_status", "range_still_valid", "risk_flags",
    }
    if df.empty or not required.issubset(df.columns): return []
    emoji={"GREEN":"🟢","YELLOW":"🟡","RED":"🔴"}; order={"GREEN":0,"YELLOW":1,"RED":2}
    work=df.copy(); work["_order"]=work["simple_color"].map(order).fillna(2)
    work["_position"]=pd.to_numeric(work["position_pct"],errors="coerce").fillna(float("inf"))
    work=work.sort_values(["_order","_position","asset"],kind="mergesort").head(4)
    rows=[]
    for _,r in work.iterrows():
        valid=str(r["range_still_valid"]).lower() in {"true","1"}
        rows.append(
            f"{emoji.get(r['simple_color'],'🔴')} {r['asset']} | {r['simple_display']} | current {_fmt_num(r['current_price'])} | "
            f"range {_fmt_num(r['range_low'])}–{_fmt_num(r['range_high'])} | midpoint {_fmt_num(r['midpoint'])} | "
            f"position {_fmt_metric(r['position_pct'])}% | net to midpoint {_fmt_metric(r['estimated_net_movement_to_midpoint_pct'])}% | "
            f"net to high {_fmt_metric(r['estimated_net_movement_to_high_pct'])}% | cycle {_fmt_metric(r['average_cycle_hours'])}h | "
            f"cycles/30d {_fmt_metric(r['cycles_per_30d'])} | quality {_fmt_metric(r['range_quality'])} | "
            f"score {_fmt_metric(r['opportunity_score'])} | {r['freshness_status']} | range valid {'YES' if valid else 'NO'} | "
            f"risk {_readable(r['risk_flags'],'none') or 'none'}"
        )
    return rows


def _momentum_rows(df: pd.DataFrame) -> list[str]:
    required={"asset","momentum_stage","change_4h_pct","change_24h_pct","change_48h_pct","relative_strength_vs_btc_24h_pct","volume_z_score","breakout_level","current_price","distance_above_breakout_pct","volatility_expansion_ratio","momentum_breakout_score","overextension_risk","freshness_status"}
    if df.empty or not required.issubset(df.columns): return []
    relevant=df[df["momentum_stage"].astype(str).ne("NO_MOMENTUM")].copy()
    relevant["_score"]=pd.to_numeric(relevant["momentum_breakout_score"],errors="coerce").fillna(0)
    relevant=relevant.sort_values(["_score","asset"],ascending=[False,True],kind="mergesort").head(5)
    rows=[]
    for _,r in relevant.iterrows():
        stage=str(r["momentum_stage"])
        if stage in {"EARLY_MOMENTUM","BREAKOUT_DEVELOPING"}: emoji,action="🟢","KANDYDAT DO RĘCZNEGO PRZEGLĄDU" if stage=="EARLY_MOMENTUM" else "OBSERWUJ POTWIERDZENIE"
        elif stage=="BREAKOUT_CONFIRMED": emoji,action="🟡","OBSERWUJ POTWIERDZENIE"
        else: emoji,action="🔴","NIE GONIĆ RUCHU"
        transition=f" | transition {r['consolidation_transition']}" if "consolidation_transition" in r and pd.notna(r.get("consolidation_transition")) else ""
        rows.append(f"{emoji} {r['asset']} | {stage} | 4h {_fmt_metric(r['change_4h_pct'])}% | 24h {_fmt_metric(r['change_24h_pct'])}% | 48h {_fmt_metric(r['change_48h_pct'])}% | RS vs BTC 24h {_fmt_metric(r['relative_strength_vs_btc_24h_pct'])}% | volume z {_fmt_metric(r['volume_z_score'])} | breakout {_fmt_num(r['breakout_level'])} | current {_fmt_num(r['current_price'])} | distance {_fmt_metric(r['distance_above_breakout_pct'])}% | volatility expansion {_fmt_metric(r['volatility_expansion_ratio'])}x | score {_fmt_metric(r['momentum_breakout_score'])} | extension {r['overextension_risk']} | {r['freshness_status']}{transition} | {action}")
    return rows


def _rotation_rows(dashboard: dict) -> list[str]:
    required={"objective","current_holding","btc_hold_score","market_regime","preferred_state","top_candidates","rotation_cost_guard","rotation_cooldown_status","data_freshness","confidence","main_invalidation_condition"}
    if not required.issubset(dashboard): return []
    rows=[f"Objective: {dashboard['objective']}",f"Current holding: {dashboard['current_holding']}",f"BTC hold score: {_fmt_metric(dashboard['btc_hold_score'])}",f"Broad regime: {dashboard['market_regime']}",f"Preferred state: {dashboard['preferred_state']}"]
    for candidate in dashboard.get("top_candidates",[])[:3]: rows.append(f"#{candidate.get('rank')} {candidate.get('asset')} | score {_fmt_metric(candidate.get('alt_rotation_score'))} | advantage {_fmt_metric(candidate.get('score_advantage'))} | net relative edge {_fmt_metric(candidate.get('net_relative_upside_after_costs'))}% | confidence {candidate.get('confidence')}")
    rows += [f"Cost guard: {dashboard['rotation_cost_guard']}",f"Cooldown: {dashboard['rotation_cooldown_status']}",f"Freshness: {dashboard['data_freshness']}",f"Confidence: {dashboard['confidence']}",f"Invalidation: {dashboard['main_invalidation_condition']}","MANUAL_REVIEW_REQUIRED | RESEARCH_ONLY | USER_DECISION_REQUIRED"]
    return rows


def _realized_summary(df: pd.DataFrame) -> str:
    if df.empty:
        return "No realized trades recorded."
    trades = len(df)
    proceeds = pd.to_numeric(df.get("proceeds"), errors="coerce").fillna(0).sum() if "proceeds" in df.columns else 0
    pnl = pd.to_numeric(df.get("realized_pnl"), errors="coerce").fillna(0).sum() if "realized_pnl" in df.columns else 0
    fx_required = 0
    if "status" in df.columns:
        fx_required = df["status"].astype(str).str.contains("FX_REQUIRED", na=False).sum()
    elif "notes" in df.columns:
        fx_required = df["notes"].astype(str).str.contains("FX_REQUIRED", na=False).sum()
    return f"trades {trades} | proceeds {_fmt_num(proceeds)} | realized_pnl {_fmt_num(pnl)} | FX_REQUIRED {fx_required}"


def _project_health(md: str) -> str:
    status = _first_match(md, [r"^Status:\s*(.+)$", r"^Status:\s*(.+)$"])
    if not status:
        status = _extract_section_value(md, "SUMMARY") or "n/a"
    lines = _extract_bullets(md, "Summary")
    if lines:
        return f"{status} | " + " | ".join(lines[:3])
    return status


def _position_manager_today(date_text: str) -> pd.DataFrame:
    path = _path_for(date_text, "position_manager.csv")
    return _read_csv(path)


def _next_action(final_decision: str, candidates: list[str], watchlist_count: int, realized_summary: str) -> str:
    decision = final_decision.upper()
    if "ACTION_REVIEW" in decision:
        return "Review allocation and candidate readiness."
    if watchlist_count > 0:
        return "Monitor watchlist conditions and signal exits."
    if candidates:
        return "Check top candidates for any new readiness changes."
    if "WAIT" in decision:
        return "Stand by; no immediate action."
    if "No realized trades" in realized_summary:
        return "Verify report generation and data freshness."
    return "Review dashboard details."


def _decision_from_current_research(
    actionable: list[str], developing: list[str], watch_assets: list[str]
) -> tuple[str, str]:
    """Preserve the existing Morning Brief decision precedence."""
    if actionable:
        return "BUY_REVIEW", "Actionable RSI2 setup available."
    if developing:
        return "WAIT_AND_WATCH", "Current RSI2 setup is still developing."
    if watch_assets:
        assets = ", ".join(watch_assets)
        verb = "remains" if len(watch_assets) == 1 else "remain"
        return (
            "WAIT_AND_WATCH",
            f"No current RSI2 setup; {assets} {verb} on universal watchlist.",
        )
    return "WAIT", "No current setup or watchlist conditions."


def _market_regime_rows(regime: pd.DataFrame) -> list[str]:
    if regime.empty or not {"metric", "value"}.issubset(regime.columns):
        return []
    lookup = {str(row["metric"]): row["value"] for _, row in regime.iterrows()}
    return [
        f"Crypto regime: {lookup.get('crypto_regime', 'UNKNOWN')}",
        f"Equity regime: {lookup.get('equity_regime', 'UNKNOWN')}",
        f"Volatility regime: {lookup.get('volatility_regime', 'UNKNOWN')}",
        f"Opportunity regime: {lookup.get('opportunity_regime', 'UNKNOWN')}",
        f"Environment score: {_fmt_num(lookup.get('environment_score'))}",
        f"Environment status: {lookup.get('environment_status', 'UNKNOWN')}",
    ]


def _opportunity_ranking_rows(
    ranking: pd.DataFrame, candidates: pd.DataFrame
) -> list[str]:
    if ranking.empty or "asset" not in ranking.columns:
        return []
    current_status: dict[str, str] = {}
    if not candidates.empty and {"asset", "current_setup_status"}.issubset(candidates.columns):
        current_status = {
            str(row["asset"]).upper(): str(row["current_setup_status"]).upper()
            for _, row in candidates.iterrows()
        }
    rows = []
    for _, row in ranking.head(10).iterrows():
        asset = str(row.get("asset")).upper()
        rows.append(
            f"{asset} | rank {len(rows) + 1} | bucket {row.get('bucket')} | "
            f"opportunity {_fmt_num(row.get('opportunity_score'))} | "
            f"confidence {_fmt_num(row.get('confidence_score'))} | "
            f"research recommendation {row.get('recommendation')} | "
            f"current setup {current_status.get(asset, 'UNKNOWN')}"
        )
    return rows


def render_research_dashboard(
    regime: pd.DataFrame,
    opportunity_ranking: pd.DataFrame,
    candidates: pd.DataFrame,
    research_score_md: str,
    radar_md: str,
) -> str:
    """Render additive research context from existing report artifacts."""
    sections: list[tuple[str, list[str], str]] = [
        (
            "MARKET REGIME ENGINE",
            _market_regime_rows(regime),
            "Market regime report unavailable.",
        ),
        (
            "OPPORTUNITY RANKING — RESEARCH OUTPUT, NOT CURRENT SIGNALS",
            _opportunity_ranking_rows(opportunity_ranking, candidates),
            "Opportunity ranking report unavailable.",
        ),
        (
            "RESEARCH SCORE BREAKDOWN",
            _extract_section_lines(research_score_md, "Research Score Breakdown"),
            "Research Score breakdown unavailable.",
        ),
    ]
    for heading in (
        "Fastest Improving Assets",
        "Fastest Deteriorating Assets",
        "Newly Emerging Candidates",
        "Disappearing Candidates",
        "Research Score Trend — Last 7 Days",
        "Readiness Trend — Last 7 Days",
        "Market Rotation Observations",
    ):
        sections.append(
            (
                f"CRYPTO RESEARCH RADAR — {heading.upper()}",
                _extract_section_lines(radar_md, heading),
                "Crypto Research Radar section unavailable.",
            )
        )

    lines = ["", "UNIFIED RESEARCH DASHBOARD"]
    for title, rows, empty_text in sections:
        lines.extend(["", title])
        if rows:
            lines.extend(f"- {row}" for row in rows)
        else:
            lines.append(empty_text)
    return "\n".join(lines)


def main() -> None:
    args = _parse_args()
    if args.universe:
        import os
        os.environ["KRAKEN_UNIVERSE"] = args.universe
        global REPORT_DIR
        REPORT_DIR = report_dir()
    date_text = _report_date(args.date)

    packet_path = ANALYST_PACKET_DIR / f"{date_text}_analyst_decision_packet.json"
    if not packet_path.exists() and args.date is None:
        packet_path = ANALYST_PACKET_DIR / "latest_analyst_decision_packet.json"
    packet = _read_json(packet_path)
    if packet:
        print(render_analyst_packet_brief(packet))
        return

    daily_md = _load_daily_decision(date_text)
    candidates_df = _load_trade_candidates(date_text)
    universal_df = _read_csv(_path_for(date_text, "universal_market_scanner.csv"))
    regime_df = _read_csv(_path_for(date_text, "research_regime.csv"))
    opportunity_ranking_df = _read_csv(
        _path_for(date_text, "crypto_opportunity_ranking.csv")
    )
    research_score_md = _read_text(_path_for(date_text, "research_score.md"))
    radar_md = _read_text(_path_for(date_text, "crypto_research_radar.md"))
    health_md = _load_project_health(date_text)
    signal_exit_df = _load_signal_exit_calendar(date_text)
    realized_df = _load_realized_trades(date_text)
    consolidation_df = _read_csv(_path_for(date_text, "consolidation_ranges.csv"))
    weekly_monitor_df = _read_csv(_path_for(date_text, "consolidation_watchlist_monitor.csv"))
    daily_consolidation_df = _read_csv(DAILY_CONSOLIDATION_WATCHLIST)
    momentum_df = _read_csv(MOMENTUM_REPORT_DIR / f"{date_text}_momentum_breakout_radar.csv")
    if momentum_df.empty:
        momentum_df = _read_csv(MOMENTUM_REPORT_DIR / "latest_momentum_breakout_radar.csv")
    rotation_dashboard = _read_json(ROTATION_DASHBOARD)
    active_portfolio = load_active_positions(PORTFOLIO_POSITIONS)

    final_decision = _final_decision(daily_md)
    portfolio_summary = open_position_summary(active_portfolio)
    watchlist_count = _watchlist_count_from_md(daily_md)
    realized_summary = _realized_summary(realized_df)
    project_health = _project_health(health_md)
    actionable = _setup_rows(candidates_df, "ACTIONABLE")
    developing = _setup_rows(candidates_df, "DEVELOPING")
    historical = _setup_rows(candidates_df, "HISTORICAL_ONLY")
    paper = _paper_signals(signal_exit_df)
    universal_watch = pd.DataFrame()
    if not universal_df.empty and "recommendation" in universal_df.columns:
        watch_mask = universal_df["recommendation"].astype(str).str.upper().eq("WATCHLIST")
        if "data_freshness_status" in universal_df.columns:
            watch_mask &= universal_df["data_freshness_status"].astype(str).str.upper().eq("FRESH")
        universal_watch = universal_df[watch_mask].copy()
    universal_watch_rows = []
    for _, row in universal_watch.iterrows():
        universal_watch_rows.append(
            f"{row.get('asset')} | WATCHLIST | Opp {_fmt_num(row.get('opportunity_score'))} | Conf {_fmt_num(row.get('confidence_score'))}"
        )
    watch_assets = universal_watch["asset"].astype(str).tolist() if "asset" in universal_watch.columns else []
    no_current = not actionable and not developing
    final_decision, reason = _decision_from_current_research(
        actionable, developing, watch_assets
    )

    print(f"Date: {date_text}")
    _print_section("TODAY'S DECISION", [final_decision, f"Reason: {reason}"], "WAIT")
    _print_section("ACTIONABLE NOW", actionable, "No actionable entry-ready recommendations.")
    _print_section(
        "DEVELOPING SETUPS",
        developing,
        "No current RSI2 entry setup. Wait for a new oversold episode." if no_current else "No developing setups.",
    )
    _print_section("HISTORICAL EDGE — NO CURRENT SIGNAL", historical, "No historical-edge assets to note.")
    _print_section("UNIVERSAL WATCHLIST", universal_watch_rows, "No current universal watchlist assets.")
    _print_section(
        "CONSOLIDATION RANGE CANDIDATES",
        _consolidation_range_rows(consolidation_df),
        "Consolidation range report unavailable or no brief-eligible ranges.",
    )
    print("RESEARCH_ONLY | NOT_A_BUY_SIGNAL | NOT_A_SELL_SIGNAL | LIVE_NOT_AUTHORIZED")
    _print_section("TOP DAILY CONSOLIDATION CANDIDATES", _daily_consolidation_rows(daily_consolidation_df), "Daily consolidation scan unavailable or no eligible candidates.")
    _print_section("MOMENTUM & BREAKOUT RADAR", _momentum_rows(momentum_df), "Momentum radar unavailable or no active momentum candidates.")
    _print_section("BTC ROTATION ENGINE", _rotation_rows(rotation_dashboard), "BTC rotation analysis unavailable.")
    _print_section("CONSOLIDATION WATCHLIST — WEEKLY SELECTION", _weekly_consolidation_rows(weekly_monitor_df), "Weekly consolidation monitor unavailable or no active candidates.")
    print("RESEARCH_ONLY | NOT_A_BUY_SIGNAL | NOT_A_SELL_SIGNAL")
    _print_section("PAPER SIGNALS — NOT CURRENT BUY OPPORTUNITIES", paper, "No open paper signals.")
    _print_section("PORTFOLIO", [f"Portfolio position summary: {portfolio_summary}"], "Portfolio position summary: No open positions")
    next_condition = (
        "Wait for a new oversold episode."
        if no_current
        else "Monitor only today's developing setup conditions for an explicit entry-ready recommendation."
    )
    _print_section("NEXT CONDITION", [next_condition], "Wait for fresh market data.")
    print(
        render_research_dashboard(
            regime_df,
            opportunity_ranking_df,
            candidates_df,
            research_score_md,
            radar_md,
        )
    )


if __name__ == "__main__":
    main()
