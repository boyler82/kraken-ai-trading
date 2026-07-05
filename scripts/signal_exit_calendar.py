from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "journal" / "project_memory.sqlite"
REPORT_DIR = ROOT / "DAILY_REPORTS"
TODAY = pd.Timestamp.today().normalize()
TODAY_TEXT = TODAY.strftime("%Y-%m-%d")
OUT_CSV = REPORT_DIR / f"{TODAY_TEXT}_signal_exit_calendar.csv"
OUT_MD = REPORT_DIR / f"{TODAY_TEXT}_signal_exit_calendar.md"


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found: {DB_PATH}")
    return sqlite3.connect(DB_PATH)


def _load_open_signals(conn: sqlite3.Connection) -> pd.DataFrame:
    try:
        return pd.read_sql_query(
            """
            SELECT asset, date, recommendation, current_phase, entry_price,
                   planned_exit_date, status, notes
            FROM signals
            WHERE status = 'OPEN'
            """,
            conn,
        )
    except Exception:
        return pd.DataFrame(columns=["asset", "date", "recommendation", "current_phase", "entry_price", "planned_exit_date", "status", "notes"])


def _status_note(planned_exit_date: str | None) -> str:
    if planned_exit_date is None or str(planned_exit_date).strip() == "":
        return "MISSING_EXIT_DATE"
    try:
        exit_date = pd.Timestamp(str(planned_exit_date)).normalize()
    except Exception:
        return "MISSING_EXIT_DATE"
    if exit_date <= TODAY:
        return "READY_FOR_OUTCOME_CHECK"
    return "WAITING"


def _days_to_exit(planned_exit_date: str | None) -> int | None:
    if planned_exit_date is None or str(planned_exit_date).strip() == "":
        return None
    try:
        exit_date = pd.Timestamp(str(planned_exit_date)).normalize()
    except Exception:
        return None
    return int((exit_date - TODAY).days)


def build_calendar() -> pd.DataFrame:
    with _connect() as conn:
        df = _load_open_signals(conn)

    if df.empty:
        return pd.DataFrame(columns=["asset", "date", "recommendation", "current_phase", "entry_price", "planned_exit_date", "days_to_exit", "status", "notes"])

    out = df.copy()
    out["days_to_exit"] = out["planned_exit_date"].apply(_days_to_exit)
    out["status"] = out["planned_exit_date"].apply(_status_note)
    out = out.sort_values(
        by=["planned_exit_date", "asset"],
        ascending=[True, True],
        na_position="last",
    ).reset_index(drop=True)
    return out[["asset", "date", "recommendation", "current_phase", "entry_price", "planned_exit_date", "days_to_exit", "status", "notes"]]


def render_markdown(df: pd.DataFrame) -> str:
    lines = [
        "# Signal Exit Calendar",
        "",
        f"Date: {TODAY_TEXT}",
        "",
        "Open signals only. Research only.",
        "",
        "## Open Signals",
        "",
    ]

    if df.empty:
        lines.append("No open signals.")
        lines.append("")
        return "\n".join(lines)

    for _, row in df.iterrows():
        lines.append(
            f"- {row['asset']} | date {row['date']} | rec {row['recommendation']} | phase {row['current_phase']} | entry {row['entry_price']} | exit {row['planned_exit_date']} | days_to_exit {row['days_to_exit']} | status {row['status']} | notes {row['notes']}"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    calendar = build_calendar()
    calendar.to_csv(OUT_CSV, index=False)
    OUT_MD.write_text(render_markdown(calendar))
    print(f"Saved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")
    if calendar.empty:
        print("No open signals.")
    else:
        print(calendar.to_string(index=False))


if __name__ == "__main__":
    main()
