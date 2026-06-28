from __future__ import annotations

import csv
import glob
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "journal" / "project_memory.sqlite"
REPORT_DIR = ROOT / "DAILY_REPORTS"

ALLOWED_RECOMMENDATIONS = {
    "ACTIVE_OPPORTUNITY",
    "WATCHLIST",
    "HIGH_PRIORITY_REVIEW",
    "MANUAL_REVIEW",
    "DAY1_OBSERVE_ONLY",
    "WATCH_CLOSELY",
}


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signals (
                signal_id TEXT PRIMARY KEY,
                date TEXT,
                asset TEXT,
                recommendation TEXT,
                bucket TEXT,
                current_phase TEXT,
                entry_day REAL,
                hold_days REAL,
                entry_price REAL,
                planned_exit_date TEXT,
                expected_value_pct REAL,
                profit_factor REAL,
                win_rate_pct REAL,
                quality_score REAL,
                confidence_score REAL,
                opportunity_score REAL,
                status TEXT,
                executed INTEGER,
                paper_trade INTEGER,
                close_price REAL,
                real_return_pct REAL,
                notes TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_runs (
                run_date TEXT PRIMARY KEY,
                final_status TEXT,
                active_signals INTEGER,
                high_priority_signals INTEGER,
                portfolio_allocation_pct REAL,
                notes TEXT,
                created_at TEXT
            )
            """
        )
        conn.commit()


def latest_ranking_file() -> Path:
    files = sorted(REPORT_DIR.glob("*_crypto_opportunity_ranking.csv"))
    if not files:
        raise FileNotFoundError("No crypto opportunity ranking files found.")
    return files[-1]


def _parse_date_from_filename(path: Path) -> str:
    return path.name.split("_crypto_opportunity_ranking.csv")[0]


def _to_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _planned_exit_date(date_text: str, hold_days: Any) -> str | None:
    if pd.isna(hold_days):
        return None
    try:
        dt = datetime.strptime(date_text, "%Y-%m-%d").date()
        exit_dt = dt + timedelta(days=int(float(hold_days)))
        return exit_dt.isoformat()
    except (TypeError, ValueError):
        return None


def record_signals_from_ranking(conn: sqlite3.Connection, ranking_path: Path) -> int:
    df = pd.read_csv(ranking_path)
    run_date = _parse_date_from_filename(ranking_path)
    now = datetime.utcnow().isoformat(timespec="seconds")
    added = 0

    for _, row in df.iterrows():
        recommendation = str(row.get("recommendation", ""))
        if recommendation not in ALLOWED_RECOMMENDATIONS:
            continue

        asset = str(row.get("asset", "")).strip()
        current_phase = str(row.get("current_phase", "")).strip()
        signal_id = f"{run_date}_{asset}_{recommendation}_{current_phase}"
        planned_exit_date = _planned_exit_date(run_date, row.get("hold_days"))
        status = "OPEN"

        cur = conn.execute("SELECT 1 FROM signals WHERE signal_id = ?", (signal_id,))
        if cur.fetchone():
            continue

        conn.execute(
            """
            INSERT INTO signals (
                signal_id, date, asset, recommendation, bucket, current_phase,
                entry_day, hold_days, entry_price, planned_exit_date,
                expected_value_pct, profit_factor, win_rate_pct, quality_score,
                confidence_score, opportunity_score, status, executed,
                paper_trade, close_price, real_return_pct, notes,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?
            )
            """,
            (
                signal_id,
                run_date,
                asset,
                recommendation,
                str(row.get("bucket", "")).strip(),
                current_phase,
                _to_float(row.get("entry_day")),
                _to_float(row.get("hold_days")),
                _to_float(row.get("entry_price", row.get("close"))),
                planned_exit_date,
                _to_float(row.get("expected_value_pct")),
                _to_float(row.get("profit_factor")),
                _to_float(row.get("win_rate_pct")),
                _to_float(row.get("quality_score")),
                _to_float(row.get("confidence_score")),
                _to_float(row.get("opportunity_score")),
                status,
                0,
                1,
                None,
                None,
                "",
                now,
                now,
            ),
        )
        added += 1

    conn.commit()
    return added


def close_expired_signals(conn: sqlite3.Connection) -> int:
    # TODO: Close signals only when a valid exit price is available.
    return 0


def record_daily_run(
    conn: sqlite3.Connection,
    run_date: str,
    final_status: str,
    active_signals: int,
    high_priority_signals: int,
    portfolio_allocation_pct: float | None = None,
    notes: str = "",
) -> None:
    now = datetime.utcnow().isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO daily_runs (
            run_date, final_status, active_signals, high_priority_signals,
            portfolio_allocation_pct, notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_date) DO UPDATE SET
            final_status=excluded.final_status,
            active_signals=excluded.active_signals,
            high_priority_signals=excluded.high_priority_signals,
            portfolio_allocation_pct=excluded.portfolio_allocation_pct,
            notes=excluded.notes
        """,
        (
            run_date,
            final_status,
            active_signals,
            high_priority_signals,
            portfolio_allocation_pct,
            notes,
            now,
        ),
    )
    conn.commit()


def main() -> None:
    init_db()
    ranking_path = latest_ranking_file()
    run_date = _parse_date_from_filename(ranking_path)

    with sqlite3.connect(DB_PATH) as conn:
        added = record_signals_from_ranking(conn, ranking_path)
        close_expired_signals(conn)

        stats = conn.execute(
            """
            SELECT
                COUNT(*) AS open_signals,
                SUM(CASE WHEN recommendation = 'HIGH_PRIORITY_REVIEW' THEN 1 ELSE 0 END) AS high_priority_signals
            FROM signals
            WHERE status = 'OPEN'
            """
        ).fetchone()

        open_signals = int(stats[0] or 0)
        high_priority_signals = int(stats[1] or 0)

        record_daily_run(
            conn,
            run_date=run_date,
            final_status="RECORDED",
            active_signals=open_signals,
            high_priority_signals=high_priority_signals,
            portfolio_allocation_pct=None,
            notes=f"Source ranking: {ranking_path.name}",
        )

    print(f"signals added: {added}")
    print(f"open signals: {open_signals}")
    print("daily run recorded")


if __name__ == "__main__":
    main()
