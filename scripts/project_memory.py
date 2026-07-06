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
        existing_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(signals)").fetchall()
        }
        for column, ddl in [
            ("episode_start_date", "TEXT"),
            ("last_seen_date", "TEXT"),
            ("days_in_episode", "INTEGER"),
        ]:
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE signals ADD COLUMN {column} {ddl}")
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
    try:
        dt = datetime.strptime(date_text, "%Y-%m-%d").date()
        if pd.isna(hold_days):
            exit_dt = dt + timedelta(days=3)
        else:
            exit_dt = dt + timedelta(days=int(float(hold_days)))
        return exit_dt.isoformat()
    except (TypeError, ValueError):
        return None


def _episode_start_text(value: Any) -> str | None:
    if pd.isna(value) or value is None:
        return None
    text = str(value).strip()
    return text or None


def _phase_day(current_phase: str) -> int | None:
    if current_phase.startswith("OVERSOLD_DAY_"):
        try:
            return int(current_phase.replace("OVERSOLD_DAY_", ""))
        except ValueError:
            return None
    return None


def _existing_planned_exit_date(conn: sqlite3.Connection, signal_id: str) -> str | None:
    row = conn.execute(
        """
        SELECT planned_exit_date
        FROM signals
        WHERE signal_id = ?
        """,
        (signal_id,),
    ).fetchone()
    if row is None:
        return None
    value = row[0]
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _open_signal_row(
    conn: sqlite3.Connection,
    asset: str,
    recommendation: str,
):
    return conn.execute(
        """
        SELECT signal_id, episode_start_date, current_phase, days_in_episode, status
        FROM signals
        WHERE asset = ?
          AND recommendation = ?
          AND status = 'OPEN'
        LIMIT 1
        """,
        (asset, recommendation),
    )


def _upsert_episode_signal(
    conn: sqlite3.Connection,
    *,
    run_date: str,
    now: str,
    asset: str,
    recommendation: str,
    bucket: str,
    current_phase: str,
    episode_start_date: str,
    planned_exit_date: str | None,
    entry_day: float | None,
    hold_days: float | None,
    entry_price: float | None,
    expected_value_pct: float | None,
    profit_factor: float | None,
    win_rate_pct: float | None,
    quality_score: float | None,
    confidence_score: float | None,
    opportunity_score: float | None,
) -> bool:
    existing = _open_signal_row(conn, asset, recommendation)
    row = existing.fetchone()

    if row:
        signal_id = row[0]
        conn.execute(
            """
            UPDATE signals
            SET updated_at = ?,
                notes = CASE
                    WHEN notes IS NULL OR TRIM(notes) = '' THEN notes
                    ELSE notes
                END
            WHERE signal_id = ?
            """,
            (now, signal_id),
        )
        return False

    signal_id = f"{asset}_{episode_start_date}_{recommendation}"
    current_day = _phase_day(current_phase)
    conn.execute(
        """
        INSERT INTO signals (
            signal_id, date, asset, recommendation, bucket, current_phase,
            episode_start_date, last_seen_date, days_in_episode,
            entry_day, hold_days, entry_price, planned_exit_date,
            expected_value_pct, profit_factor, win_rate_pct, quality_score,
            confidence_score, opportunity_score, status, executed,
            paper_trade, close_price, real_return_pct, notes,
            created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?,
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
            bucket,
            current_phase,
            episode_start_date,
            run_date,
            current_day,
            entry_day,
            hold_days,
            entry_price,
            planned_exit_date,
            expected_value_pct,
            profit_factor,
            win_rate_pct,
            quality_score,
            confidence_score,
            opportunity_score,
            "CLOSED" if current_phase == "NO_OVERSOLD" else "OPEN",
            0,
            1,
            None,
            None,
            "",
            now,
            now,
        ),
    )
    return True


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
        episode_start_date = _episode_start_text(row.get("episode_start_date"))
        if not episode_start_date:
            episode_start_date = run_date
        bucket = str(row.get("bucket", "")).strip()
        hold_days = _to_float(row.get("hold_days"))
        planned_exit_date = _planned_exit_date(run_date, hold_days)
        inserted = _upsert_episode_signal(
            conn,
            run_date=run_date,
            now=now,
            asset=asset,
            recommendation=recommendation,
            bucket=bucket,
            current_phase=current_phase,
            episode_start_date=episode_start_date,
            planned_exit_date=planned_exit_date,
            entry_day=_to_float(row.get("entry_day")),
            hold_days=hold_days,
            entry_price=_to_float(row.get("entry_price", row.get("close"))),
            expected_value_pct=_to_float(row.get("expected_value_pct")),
            profit_factor=_to_float(row.get("profit_factor")),
            win_rate_pct=_to_float(row.get("win_rate_pct")),
            quality_score=_to_float(row.get("quality_score")),
            confidence_score=_to_float(row.get("confidence_score")),
            opportunity_score=_to_float(row.get("opportunity_score")),
        )
        if inserted:
            added += 1

    conn.commit()
    return added


def migrate_open_signals_missing_exit_date(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT signal_id, date, notes
        FROM signals
        WHERE status = 'OPEN'
          AND planned_exit_date IS NULL
        """
    ).fetchall()

    changed = 0
    for signal_id, date_text, notes in rows:
        try:
            existing_planned_exit = _existing_planned_exit_date(conn, signal_id)
            if existing_planned_exit:
                continue
            planned_exit_date = (
                datetime.strptime(date_text, "%Y-%m-%d").date() + timedelta(days=3)
            ).isoformat()
        except (TypeError, ValueError):
            continue

        new_notes = (notes or "").strip()
        if new_notes:
            new_notes += "; fallback planned_exit_date migration"
        else:
            new_notes = "fallback planned_exit_date migration"

        conn.execute(
            """
            UPDATE signals
            SET planned_exit_date = ?,
                notes = ?,
                updated_at = ?
            WHERE signal_id = ?
            """,
            (planned_exit_date, new_notes, datetime.utcnow().isoformat(timespec="seconds"), signal_id),
        )
        changed += 1

    conn.commit()
    return changed


def print_open_signals(conn: sqlite3.Connection, label: str) -> None:
    print(f"{label}:")
    rows = conn.execute(
        """
        SELECT asset, date, planned_exit_date, status
        FROM signals
        WHERE status = 'OPEN'
        ORDER BY asset, date
        """
    ).fetchall()
    if not rows:
        print("(none)")
        return
    for asset, date_text, planned_exit_date, status in rows:
        print(f"{asset} | {date_text} | {planned_exit_date} | {status}")


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
        print_open_signals(conn, "OPEN signals before")
        added = record_signals_from_ranking(conn, ranking_path)
        migrated = migrate_open_signals_missing_exit_date(conn)
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
        print_open_signals(conn, "OPEN signals after")

    print(f"signals added: {added}")
    print(f"migrated open signals: {migrated}")
    print(f"open signals: {open_signals}")
    print("daily run recorded")


if __name__ == "__main__":
    main()
