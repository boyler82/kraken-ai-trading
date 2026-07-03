from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "journal" / "project_memory.sqlite"
REPORT_DIR = ROOT / "DAILY_REPORTS"


HISTORY_COLUMNS = [
    "history_id",
    "signal_key",
    "signal_id",
    "run_date",
    "asset",
    "bucket",
    "recommendation",
    "current_phase",
    "opportunity_score",
    "confidence_score",
    "rsi2",
    "close",
    "trend",
    "volatility",
    "market_bias",
    "atr_pct",
    "entry_day",
    "hold_days",
    "entry_alignment_score",
    "trades",
    "win_rate_pct",
    "expected_value_pct",
    "profit_factor",
    "avg_return_pct",
    "median_return_pct",
    "worst_return_pct",
    "best_return_pct",
    "current_oversold_duration",
    "created_at",
]

OUTCOME_COLUMNS = [
    "signal_key",
    "signal_id",
    "asset",
    "recommendation",
    "open_date",
    "close_date",
    "close_reason",
    "entry_price",
    "exit_price",
    "real_return_pct",
    "created_at",
    "updated_at",
]


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signal_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_key TEXT NOT NULL,
                signal_id TEXT NOT NULL,
                run_date TEXT NOT NULL,
                asset TEXT,
                bucket TEXT,
                recommendation TEXT,
                current_phase TEXT,
                opportunity_score REAL,
                confidence_score REAL,
                rsi2 REAL,
                close REAL,
                trend TEXT,
                volatility TEXT,
                market_bias TEXT,
                atr_pct REAL,
                entry_day REAL,
                hold_days REAL,
                entry_alignment_score REAL,
                trades REAL,
                win_rate_pct REAL,
                expected_value_pct REAL,
                profit_factor REAL,
                avg_return_pct REAL,
                median_return_pct REAL,
                worst_return_pct REAL,
                best_return_pct REAL,
                current_oversold_duration REAL,
                created_at TEXT NOT NULL,
                UNIQUE(signal_key, run_date)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signal_outcomes (
                signal_key TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL,
                asset TEXT,
                recommendation TEXT,
                open_date TEXT,
                close_date TEXT,
                close_reason TEXT,
                entry_price REAL,
                exit_price REAL,
                real_return_pct REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
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


def _to_float(value):
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _signal_key(row: pd.Series) -> str:
    asset = str(row.get("asset", "")).strip().upper()
    recommendation = str(row.get("recommendation", "")).strip().upper()
    return f"{asset}:{recommendation}"


def _signal_id(row: pd.Series, run_date: str) -> str:
    asset = str(row.get("asset", "")).strip().upper()
    recommendation = str(row.get("recommendation", "")).strip().upper()
    current_phase = str(row.get("current_phase", "")).strip().upper()
    return f"{asset}_{run_date}_{recommendation}_{current_phase}"


def load_latest_ranking() -> pd.DataFrame:
    path = latest_ranking_file()
    return pd.read_csv(path), _parse_date_from_filename(path)


def upsert_signal_history(report: pd.DataFrame, run_date: str) -> int:
    now = datetime.utcnow().isoformat(timespec="seconds")
    inserted = 0

    with sqlite3.connect(DB_PATH) as conn:
        for _, row in report.iterrows():
            signal_key = _signal_key(row)
            signal_id = _signal_id(row, run_date)

            conn.execute(
                """
                INSERT OR IGNORE INTO signal_history (
                    signal_key, signal_id, run_date, asset, bucket, recommendation,
                    current_phase, opportunity_score, confidence_score, rsi2, close,
                    trend, volatility, market_bias, atr_pct, entry_day, hold_days,
                    entry_alignment_score, trades, win_rate_pct, expected_value_pct,
                    profit_factor, avg_return_pct, median_return_pct, worst_return_pct,
                    best_return_pct, current_oversold_duration, created_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?
                )
                """,
                (
                    signal_key,
                    signal_id,
                    run_date,
                    row.get("asset"),
                    row.get("bucket"),
                    row.get("recommendation"),
                    row.get("current_phase"),
                    _to_float(row.get("opportunity_score")),
                    _to_float(row.get("confidence_score")),
                    _to_float(row.get("rsi2")),
                    _to_float(row.get("close")),
                    row.get("trend"),
                    row.get("volatility"),
                    row.get("market_bias"),
                    _to_float(row.get("atr_pct")),
                    _to_float(row.get("entry_day")),
                    _to_float(row.get("hold_days")),
                    _to_float(row.get("entry_alignment_score")),
                    _to_float(row.get("trades")),
                    _to_float(row.get("win_rate_pct")),
                    _to_float(row.get("expected_value_pct")),
                    _to_float(row.get("profit_factor")),
                    _to_float(row.get("avg_return_pct")),
                    _to_float(row.get("median_return_pct")),
                    _to_float(row.get("worst_return_pct")),
                    _to_float(row.get("best_return_pct")),
                    _to_float(row.get("current_oversold_duration")),
                    now,
                ),
            )
            inserted += conn.execute("SELECT changes()").fetchone()[0]

        conn.commit()

    return inserted


def main() -> None:
    init_db()
    report, run_date = load_latest_ranking()
    inserted = upsert_signal_history(report, run_date)

    print("\nOPPORTUNITY TRACKER\n")
    print(f"Source: {latest_ranking_file()}")
    print(f"Run date: {run_date}")
    print(f"Active signals: {len(report)}")
    print(f"Inserted history rows: {inserted}")
    print(f"DB: {DB_PATH}")


if __name__ == "__main__":
    main()
