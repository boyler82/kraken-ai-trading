from __future__ import annotations

import csv
import ast
import json
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "DAILY_REPORTS"
RESEARCH_DIR = ROOT / "RESEARCH"
DB_PATH = ROOT / "journal" / "project_memory.sqlite"
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")
OUT_MD = RESEARCH_DIR / "v2_0_release_audit.md"
OUT_CSV = RESEARCH_DIR / "v2_0_release_audit.csv"

REQUIRED_MODULES = [
    "scripts/opportunity_ranking.py",
    "scripts/project_memory.py",
    "scripts/signal_exit_calendar.py",
    "scripts/signal_outcome_engine.py",
    "scripts/morning_brief.py",
    "scripts/daily_decision_dashboard.py",
    "scripts/project_health_check.py",
    "scripts/position_manager.py",
    "scripts/realized_trade_manager.py",
    "scripts/run_research.py",
]

CRITICAL_OPEN_SIGNAL_FIELDS = ["signal_id", "date", "asset", "entry_price", "planned_exit_date", "status"]


@dataclass
class Check:
    section: str
    check: str
    status: str
    detail: str
    fatal: bool = False


def _add(rows: list[Check], section: str, check: str, ok: bool, detail: str, *, fatal: bool = False) -> None:
    rows.append(Check(section, check, "OK" if ok else ("FAIL" if fatal else "WARNING"), detail, fatal and not ok))


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _read_text(path: Path) -> str:
    try:
        return path.read_text()
    except Exception:
        return ""


def _today_report(suffix: str) -> Path:
    return REPORT_DIR / f"{TODAY}_{suffix}"


def _connect() -> sqlite3.Connection | None:
    if not DB_PATH.exists():
        return None
    return sqlite3.connect(DB_PATH)


def _open_signals(conn: sqlite3.Connection | None) -> pd.DataFrame:
    if conn is None:
        return pd.DataFrame(columns=CRITICAL_OPEN_SIGNAL_FIELDS)
    try:
        return pd.read_sql_query("SELECT * FROM signals WHERE status = 'OPEN'", conn)
    except Exception:
        return pd.DataFrame(columns=CRITICAL_OPEN_SIGNAL_FIELDS)


def _all_signals(conn: sqlite3.Connection | None) -> pd.DataFrame:
    if conn is None:
        return pd.DataFrame()
    try:
        return pd.read_sql_query("SELECT * FROM signals", conn)
    except Exception:
        return pd.DataFrame()


def _script_mentions(path: Path, needle: str) -> int:
    return _read_text(path).count(needle)


def _step_index(steps: list[str], name: str) -> int | None:
    try:
        return steps.index(name)
    except ValueError:
        return None


def _pipeline_steps() -> list[str]:
    text = _read_text(ROOT / "scripts" / "research_pipeline.py")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "STEPS":
                    try:
                        value = ast.literal_eval(node.value)
                    except (ValueError, SyntaxError):
                        return []
                    if isinstance(value, list):
                        return [str(item) for item in value]
    return []


def _status_values(df: pd.DataFrame, section: str) -> list[str]:
    if df.empty or "section" not in df.columns or "status" not in df.columns:
        return []
    return df.loc[df["section"].astype(str).str.upper() == section.upper(), "status"].astype(str).tolist()


def _asset_set(df: pd.DataFrame, column: str = "asset") -> set[str]:
    if df.empty or column not in df.columns:
        return set()
    return {str(v).strip().upper() for v in df[column].dropna().tolist() if str(v).strip()}


def _open_signal_key_set(df: pd.DataFrame) -> set[tuple[str, str, str]]:
    required = {"asset", "date", "planned_exit_date"}
    if df.empty or not required.issubset(df.columns):
        return set()
    return {
        (str(r.asset).strip().upper(), str(r.date).strip(), str(r.planned_exit_date).strip())
        for r in df[["asset", "date", "planned_exit_date"]].itertuples(index=False)
    }


def check_pipeline(rows: list[Check]) -> None:
    for module in REQUIRED_MODULES:
        _add(rows, "PIPELINE", f"module exists: {module}", (ROOT / module).exists(), module, fatal=True)

    steps = _pipeline_steps()
    _add(rows, "PIPELINE", "research_pipeline STEPS loaded", bool(steps), f"{len(steps)} steps", fatal=True)

    project_memory_count = steps.count("scripts/project_memory.py")
    _add(rows, "PIPELINE", "project_memory.py runs exactly once", project_memory_count == 1, f"count={project_memory_count}", fatal=True)

    idx_rank = _step_index(steps, "scripts/opportunity_ranking.py")
    idx_memory = _step_index(steps, "scripts/project_memory.py")
    idx_exit = _step_index(steps, "scripts/signal_exit_calendar.py")
    idx_outcome = _step_index(steps, "scripts/signal_outcome_engine.py")
    idx_health = _step_index(steps, "scripts/project_health_check.py")
    _add(rows, "PIPELINE", "opportunity_ranking before project_memory", idx_rank is not None and idx_memory is not None and idx_rank < idx_memory, f"ranking={idx_rank}, memory={idx_memory}", fatal=True)
    _add(rows, "PIPELINE", "project_memory before signal_exit_calendar", idx_memory is not None and idx_exit is not None and idx_memory < idx_exit, f"memory={idx_memory}, exit_calendar={idx_exit}", fatal=True)
    _add(rows, "PIPELINE", "project_memory before signal_outcome_engine", idx_memory is not None and idx_outcome is not None and idx_memory < idx_outcome, f"memory={idx_memory}, outcome={idx_outcome}", fatal=True)
    _add(rows, "PIPELINE", "project_health_check last", idx_health is not None and idx_health == len(steps) - 1, f"health={idx_health}, last={len(steps) - 1}", fatal=True)

    log_text = _read_text(ROOT / "logs" / "final_v2_audit.log")
    if log_text:
        pipeline_ok = "SUCCESS" in log_text and "Traceback" not in log_text and "CalledProcessError" not in log_text
        _add(rows, "PIPELINE", "final_v2_audit.log pipeline completed", pipeline_ok, "SUCCESS found" if pipeline_ok else "pipeline log has no SUCCESS or contains error", fatal=True)


def check_data(rows: list[Check], open_df: pd.DataFrame) -> None:
    universal = _read_csv(_today_report("universal_market_scanner.csv"))
    crypto = universal[universal.get("asset_class", pd.Series(dtype=str)).astype(str).str.lower() == "crypto"] if not universal.empty and "asset_class" in universal.columns else pd.DataFrame()
    if crypto.empty:
        _add(rows, "DATA", "crypto freshness rows available", False, "no crypto rows in today's universal scanner", fatal=True)
    else:
        max_age = pd.to_numeric(crypto.get("data_age_days"), errors="coerce").max()
        _add(rows, "DATA", "latest crypto data_age_days <= 1", pd.notna(max_age) and max_age <= 1, f"max_crypto_age={max_age}", fatal=True)

    stale_assets = universal[universal.get("asset_class", pd.Series(dtype=str)).astype(str).str.lower().isin(["etf", "stock"])] if not universal.empty and "asset_class" in universal.columns else pd.DataFrame()
    if stale_assets.empty:
        _add(rows, "DATA", "ETF/stock stale rows available", False, "no ETF/stock rows in today's universal scanner")
    else:
        stale_ok = stale_assets.get("recommendation", pd.Series(dtype=str)).astype(str).eq("STALE_DATA").all()
        _add(rows, "DATA", "ETF/stock stale rows have STALE_DATA", bool(stale_ok), f"rows={len(stale_assets)}")

    if open_df.empty:
        _add(rows, "DATA", "active signals critical fields not NaN", True, "no OPEN signals")
        _add(rows, "DATA", "entry_price precision retained", True, "no OPEN signals")
        return

    missing_critical = open_df[CRITICAL_OPEN_SIGNAL_FIELDS].isna().any(axis=1) if set(CRITICAL_OPEN_SIGNAL_FIELDS).issubset(open_df.columns) else pd.Series([True])
    _add(rows, "DATA", "no NaN in critical OPEN signal fields", not bool(missing_critical.any()), f"missing_rows={int(missing_critical.sum())}", fatal=bool(missing_critical.any()))

    ranking = _read_csv(_today_report("crypto_opportunity_ranking.csv"))
    rounded = []
    if not ranking.empty and "asset" in ranking.columns and "close" in ranking.columns:
        close_map = {str(r.asset).upper(): str(r.close) for r in ranking[["asset", "close"]].itertuples(index=False)}
        for row in open_df.itertuples(index=False):
            asset = str(getattr(row, "asset", "")).upper()
            entry = getattr(row, "entry_price", None)
            close_text = close_map.get(asset)
            if close_text is None or pd.isna(entry):
                continue
            try:
                same = abs(float(entry) - float(close_text)) <= max(1e-12, abs(float(close_text)) * 1e-8)
            except ValueError:
                same = False
            if same and "." in close_text and "." in str(entry) and len(str(entry).split(".", 1)[1].rstrip("0")) < len(close_text.split(".", 1)[1].rstrip("0")):
                rounded.append(asset)
    _add(rows, "DATA", "entry_price not truncated versus ranking close", not rounded, f"rounded_assets={','.join(rounded) if rounded else 'none'}", fatal=bool(rounded))


def check_signals(rows: list[Check], conn: sqlite3.Connection | None, all_df: pd.DataFrame, open_df: pd.DataFrame) -> None:
    _add(rows, "SIGNALS", "SQLite database exists", conn is not None, str(DB_PATH), fatal=True)
    if all_df.empty:
        _add(rows, "SIGNALS", "signals table has rows", False, "no signals loaded", fatal=True)
        return

    unique = all_df["signal_id"].is_unique if "signal_id" in all_df.columns else False
    _add(rows, "SIGNALS", "signal_id is unique", bool(unique), f"rows={len(all_df)} unique={all_df['signal_id'].nunique() if 'signal_id' in all_df.columns else 0}", fatal=True)

    if open_df.empty:
        _add(rows, "SIGNALS", "OPEN signals have required fields", True, "no OPEN signals")
    else:
        missing = open_df[["date", "entry_price", "planned_exit_date"]].isna().any(axis=1)
        _add(rows, "SIGNALS", "OPEN signal has date, entry_price, planned_exit_date", not bool(missing.any()), f"missing_rows={int(missing.sum())}", fatal=bool(missing.any()))
        dates = pd.to_datetime(open_df["date"], errors="coerce")
        exits = pd.to_datetime(open_df["planned_exit_date"], errors="coerce")
        bad_dates = dates.isna() | exits.isna() | (exits < dates)
        _add(rows, "SIGNALS", "planned_exit_date >= signal date", not bool(bad_dates.any()), f"bad_rows={int(bad_dates.sum())}", fatal=bool(bad_dates.any()))

    project_text = _read_text(ROOT / "scripts" / "project_memory.py")
    immutable_markers = [
        "UPDATE signals",
        "SET updated_at = ?",
        "WHERE signal_id = ?",
        "INSERT INTO signals",
        "planned_exit_date",
    ]
    immutable_code = all(marker in project_text for marker in immutable_markers) and "_existing_planned_exit_date" in project_text
    _add(rows, "SIGNALS", "planned_exit_date not recalculated for existing signal_id", immutable_code, "existing OPEN update does not set planned_exit_date; migration only fills NULLs", fatal=not immutable_code)

    calendar = _read_csv(_today_report("signal_exit_calendar.csv"))
    db_keys = _open_signal_key_set(open_df)
    cal_keys = _open_signal_key_set(calendar)
    _add(rows, "SIGNALS", "signal_exit_calendar and SQLite have same OPEN dates", db_keys == cal_keys, f"db={len(db_keys)} calendar={len(cal_keys)}", fatal=db_keys != cal_keys)

    closed = all_df[all_df.get("status", pd.Series(dtype=str)).astype(str).eq("CLOSED")] if "status" in all_df.columns else pd.DataFrame()
    closed_open_overlap = _asset_set(closed, "signal_id") & _asset_set(open_df, "signal_id")
    _add(rows, "SIGNALS", "CLOSED signals do not appear as OPEN", not closed_open_overlap, f"overlap={','.join(sorted(closed_open_overlap)) if closed_open_overlap else 'none'}", fatal=bool(closed_open_overlap))

    dashboard = _read_csv(_today_report("daily_decision_dashboard.csv"))
    dash_signal_rows = dashboard[dashboard.get("section", pd.Series(dtype=str)).astype(str).eq("SIGNAL EXIT CALENDAR")] if not dashboard.empty and "section" in dashboard.columns else pd.DataFrame()
    dash_assets = _asset_set(dash_signal_rows[dash_signal_rows.get("key", pd.Series(dtype=str)).astype(str).str.lower() != "none"], "key")
    db_assets = _asset_set(open_df)
    _add(rows, "SIGNALS", "dashboard OPEN signal assets match SQLite", dash_assets == db_assets, f"db={sorted(db_assets)} dashboard={sorted(dash_assets)}", fatal=dash_assets != db_assets)


def check_portfolio(rows: list[Check]) -> None:
    positions_path = ROOT / "journal" / "portfolio_positions.csv"
    position_manager = _read_csv(_today_report("position_manager.csv"))
    dashboard = _read_csv(_today_report("daily_decision_dashboard.csv"))
    brief = subprocess.run([sys.executable, str(ROOT / "scripts" / "morning_brief.py")], cwd=ROOT, text=True, capture_output=True)

    positions = _read_csv(positions_path)
    portfolio_empty = positions.empty
    _add(rows, "PORTFOLIO", "portfolio_positions.csv empty means No open positions", (not portfolio_empty) or position_manager.empty, f"portfolio_empty={portfolio_empty}, position_manager_rows={len(position_manager)}", fatal=portfolio_empty and not position_manager.empty)

    current_rows = dashboard[dashboard.get("section", pd.Series(dtype=str)).astype(str).eq("CURRENT POSITION")] if not dashboard.empty and "section" in dashboard.columns else pd.DataFrame()
    dashboard_no_positions = current_rows.empty or current_rows.get("value", pd.Series(dtype=str)).astype(str).str.contains("No open positions", na=False).any()
    brief_no_positions = "Portfolio position summary: No open positions" in brief.stdout
    _add(rows, "PORTFOLIO", "position_manager, dashboard and morning_brief agree", (not portfolio_empty) or (position_manager.empty and dashboard_no_positions and brief_no_positions), f"portfolio_empty={portfolio_empty}, dashboard_no_positions={dashboard_no_positions}, brief_no_positions={brief_no_positions}", fatal=portfolio_empty and not (position_manager.empty and dashboard_no_positions and brief_no_positions))


def check_costs(rows: list[Check]) -> None:
    costs_path = ROOT / "config" / "trading_costs.json"
    _add(rows, "COSTS", "config/trading_costs.json exists", costs_path.exists(), str(costs_path), fatal=True)
    try:
        config = json.loads(_read_text(costs_path))
    except json.JSONDecodeError:
        config = {}
    _add(rows, "COSTS", "default_fee_pct = 0.20", config.get("default_fee_pct") == 0.20, f"default_fee_pct={config.get('default_fee_pct')}", fatal=True)

    realized_text = _read_text(ROOT / "scripts" / "realized_trade_manager.py")
    _add(rows, "COSTS", "realized_trade_manager shows estimated_fee", "estimated_fee" in realized_text, "estimated_fee token present")
    fx_guard = "FX_REQUIRED" in realized_text and "report.loc[fx_mask, \"realized_pnl\"] = None" in realized_text
    _add(rows, "COSTS", "FX_REQUIRED does not calculate false realized P/L", fx_guard, "FX_REQUIRED rows null realized_pnl fields", fatal=not fx_guard)


def check_reports(rows: list[Check]) -> None:
    dashboard_md = _today_report("daily_decision_dashboard.md")
    _add(rows, "REPORTS", "today daily_decision_dashboard exists", dashboard_md.exists(), dashboard_md.name, fatal=True)

    brief = subprocess.run([sys.executable, str(ROOT / "scripts" / "morning_brief.py")], cwd=ROOT, text=True, capture_output=True)
    _add(rows, "REPORTS", "morning_brief runs", brief.returncode == 0, brief.stdout.splitlines()[0] if brief.stdout else brief.stderr[:120], fatal=brief.returncode != 0)

    health_csv = _read_csv(_today_report("project_health_check.csv"))
    statuses = _status_values(health_csv, "SUMMARY")
    health_ok = "OK" in statuses
    _add(rows, "REPORTS", "project_health_check = OK", health_ok, f"summary_statuses={statuses}", fatal=not health_ok)

    dashboard_text = _read_text(dashboard_md)
    old_refs = []
    for old in sorted(REPORT_DIR.glob("*_daily_decision_dashboard.md")):
        if old.name.startswith(TODAY):
            continue
        if old.name in dashboard_text:
            old_refs.append(old.name)
    _add(rows, "REPORTS", "no old report references when today's reports exist", not old_refs, f"old_refs={','.join(old_refs) if old_refs else 'none'}")


def final_status(rows: list[Check]) -> str:
    if any(row.status == "FAIL" for row in rows):
        return "FAIL"
    if any(row.status == "WARNING" for row in rows):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def write_outputs(rows: list[Check]) -> str:
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    status = final_status(rows)
    with OUT_CSV.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["section", "check", "status", "fatal", "detail"])
        writer.writeheader()
        for row in rows:
            writer.writerow({"section": row.section, "check": row.check, "status": row.status, "fatal": row.fatal, "detail": row.detail})

    lines = [
        "# v2.0 Release Audit",
        "",
        f"Date: {TODAY}",
        f"Final status: {status}",
        "",
        "## Summary",
        "",
    ]
    for section in ["PIPELINE", "DATA", "SIGNALS", "PORTFOLIO", "COSTS", "REPORTS"]:
        section_rows = [row for row in rows if row.section == section]
        fail = sum(1 for row in section_rows if row.status == "FAIL")
        warn = sum(1 for row in section_rows if row.status == "WARNING")
        ok = sum(1 for row in section_rows if row.status == "OK")
        lines.append(f"- {section}: OK={ok} WARNING={warn} FAIL={fail}")
    lines += ["", "## Findings", ""]
    for row in rows:
        lines.append(f"- {row.section} | {row.status} | {row.check} | {row.detail}")
    lines.append("")
    OUT_MD.write_text("\n".join(lines))
    return status


def main() -> None:
    rows: list[Check] = []
    conn = _connect()
    try:
        all_df = _all_signals(conn)
        open_df = _open_signals(conn)
        check_pipeline(rows)
        check_data(rows, open_df)
        check_signals(rows, conn, all_df, open_df)
        check_portfolio(rows)
        check_costs(rows)
        check_reports(rows)
    finally:
        if conn is not None:
            conn.close()

    status = write_outputs(rows)
    print(f"Saved: {OUT_MD}")
    print(f"Saved: {OUT_CSV}")
    print(f"Final status: {status}")
    if status == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
