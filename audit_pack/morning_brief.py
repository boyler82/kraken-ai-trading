from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "DAILY_REPORTS"
JOURNAL_DIR = ROOT / "journal"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print a compact morning brief from daily reports.")
    parser.add_argument(
        "--date",
        default=None,
        help="Report date in YYYY-MM-DD format. Defaults to today.",
    )
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
    path = _path_for(date_text, "signal_exit_calendar.csv")
    return _read_csv(path)


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
    if abs(num) >= 1000:
        return f"{num:,.2f}"
    return f"{num:.2f}".rstrip("0").rstrip(".")


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


def main() -> None:
    args = _parse_args()
    date_text = _report_date(args.date)

    daily_md = _load_daily_decision(date_text)
    candidates_df = _load_trade_candidates(date_text)
    health_md = _load_project_health(date_text)
    signal_exit_df = _load_signal_exit_calendar(date_text)
    realized_df = _load_realized_trades(date_text)
    position_df = _position_manager_today(date_text)

    final_decision = _final_decision(daily_md)
    portfolio_summary = _portfolio_summary(daily_md)
    if position_df.empty:
        portfolio_summary = "No open positions"
    top_candidates = _top_candidates(candidates_df)
    watchlist_count = _watchlist_count_from_md(daily_md)
    open_signal_exits = _open_signal_exits(signal_exit_df)
    realized_summary = _realized_summary(realized_df)
    project_health = _project_health(health_md)
    next_action = _next_action(final_decision, top_candidates, watchlist_count, realized_summary)

    print(f"Date: {date_text}")
    print(f"Final decision: {final_decision}")
    print(f"Portfolio position summary: {portfolio_summary}")
    print("Top 3 candidates:")
    if top_candidates:
        for item in top_candidates:
            print(f"- {item}")
    else:
        print("- No candidates available.")
    print(f"Watchlist count: {watchlist_count}")
    print(f"Open signal exits: {open_signal_exits}")
    print(f"Realized trades summary: {realized_summary}")
    print(f"Project health: {project_health}")
    print(f"Next action: {next_action}")


if __name__ == "__main__":
    main()
