from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "journal" / "project_memory.sqlite"
REPORT_DIR = ROOT / "DAILY_REPORTS"
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")
OUT_CSV = REPORT_DIR / f"{TODAY}_project_health_check.csv"
OUT_MD = REPORT_DIR / f"{TODAY}_project_health_check.md"

TABLES = ["signals", "signal_history", "signal_outcomes", "daily_runs"]
KEY_REPORT_PATTERNS = {
    "daily_decision_dashboard": "*_daily_decision_dashboard.md",
    "research_score": "*_research_score.csv",
    "strategy_performance": "*_strategy_performance.csv",
}


def _latest(pattern: str) -> Path | None:
    files = sorted(REPORT_DIR.glob(pattern))
    return files[-1] if files else None


def _exists_today(pattern: str) -> bool:
    return (REPORT_DIR / pattern).exists()


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found: {DB_PATH}")
    return sqlite3.connect(DB_PATH)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    )
    return cur.fetchone() is not None


def _count(conn: sqlite3.Connection, table: str) -> int | None:
    try:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
        row = cur.fetchone()
        return int(row[0]) if row else None
    except Exception:
        return None


def _status_from_checks(checks: list[bool], warnings: list[bool]) -> str:
    if not all(checks):
        return "ERROR"
    if any(warnings):
        return "WARNING"
    return "OK"


def build_health_check() -> tuple[pd.DataFrame, str]:
    report_rows = []
    checks: list[bool] = []
    warnings: list[bool] = []

    with _connect() as conn:
        db_exists = True
        checks.append(db_exists)
        report_rows.append({"section": "DATABASE", "check": "project_memory.sqlite", "value": "present", "status": "OK"})

        for table in TABLES:
            exists = _table_exists(conn, table)
            checks.append(exists)
            report_rows.append(
                {
                    "section": "TABLES",
                    "check": table,
                    "value": "present" if exists else "missing",
                    "status": "OK" if exists else "ERROR",
                }
            )

        open_signals = _count(conn, "signals")
        signal_history_rows = _count(conn, "signal_history")
        signal_outcomes_rows = _count(conn, "signal_outcomes")

        open_count = None
        try:
            cur = conn.execute("SELECT COUNT(*) FROM signals WHERE status='OPEN'")
            open_count = int(cur.fetchone()[0])
        except Exception:
            open_count = None

        counts = [
            ("OPEN signals", open_count),
            ("signal_history rows", signal_history_rows),
            ("signal_outcomes rows", signal_outcomes_rows),
        ]
        for label, value in counts:
            ok = value is not None
            checks.append(ok)
            report_rows.append(
                {
                    "section": "COUNTS",
                    "check": label,
                    "value": value if value is not None else "unavailable",
                    "status": "OK" if ok else "ERROR",
                }
            )

    for label, pattern in KEY_REPORT_PATTERNS.items():
        path = _latest(pattern)
        exists = path is not None
        if label == "strategy_performance" and not exists:
            warnings.append(True)
            report_rows.append(
                {
                    "section": "REPORTS",
                    "check": label,
                    "value": "missing",
                    "status": "WARNING",
                }
            )
        else:
            checks.append(exists)
            report_rows.append(
                {
                    "section": "REPORTS",
                    "check": label,
                    "value": path.name if path else "missing",
                    "status": "OK" if exists else "ERROR",
                }
            )

    status = _status_from_checks(checks, warnings)
    summary_rows = [
        {"section": "SUMMARY", "check": "status", "value": status, "status": status},
        {"section": "SUMMARY", "check": "date", "value": TODAY, "status": "OK"},
    ]

    df = pd.DataFrame(summary_rows + report_rows)

    md_lines = [
        "# Project Health Check",
        "",
        f"Date: {TODAY}",
        "",
        f"Status: {status}",
        "",
        "## Summary",
        "",
    ]
    md_lines.append(f"- SQLite database: {'present' if DB_PATH.exists() else 'missing'}")
    md_lines.append(f"- OPEN signals: {open_count if open_count is not None else 'unavailable'}")
    md_lines.append(f"- signal_history rows: {signal_history_rows if signal_history_rows is not None else 'unavailable'}")
    md_lines.append(f"- signal_outcomes rows: {signal_outcomes_rows if signal_outcomes_rows is not None else 'unavailable'}")
    md_lines.append("")
    md_lines.append("## Key Reports")
    md_lines.append("")
    for label, pattern in KEY_REPORT_PATTERNS.items():
        path = _latest(pattern)
        if path is None:
            if label == "strategy_performance":
                md_lines.append(f"- {label}: missing (warning)")
            else:
                md_lines.append(f"- {label}: missing")
        else:
            md_lines.append(f"- {label}: {path.name}")
    md_lines.append("")
    md_lines.append("## Details")
    md_lines.append("")
    for _, row in df.iterrows():
        md_lines.append(f"- {row['section']} | {row['check']} | {row['value']} | {row['status']}")
    md_lines.append("")

    return df, "\n".join(md_lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df, md = build_health_check()
    df.to_csv(OUT_CSV, index=False)
    OUT_MD.write_text(md)
    print(f"Saved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")
    print(md)


if __name__ == "__main__":
    main()
