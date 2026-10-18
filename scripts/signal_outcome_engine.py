from __future__ import annotations

import glob
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
from lib.universe import project_memory_db, report_dir

from lib.data_loader import load_ohlc  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = project_memory_db()
REPORT_DIR = report_dir()
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")
OUT_CSV = REPORT_DIR / f"{TODAY}_signal_outcome_engine.csv"
OUT_MD = REPORT_DIR / f"{TODAY}_signal_outcome_engine.md"


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found: {DB_PATH}")
    return sqlite3.connect(DB_PATH)


def _load_open_signals(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT s.*
        FROM signals s
        LEFT JOIN signal_outcomes o ON o.signal_id = s.signal_id
        WHERE s.status = 'OPEN'
           OR (s.status = 'CLOSED' AND o.signal_id IS NULL)
        ORDER BY s.planned_exit_date ASC, s.date ASC, s.asset ASC
        """,
        conn,
    )


def _ohlc_map() -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for path_text in sorted(glob.glob(str(ROOT / "DATASETS" / "market_raw" / "*_D1.json"))):
        path = Path(path_text)
        try:
            df = load_ohlc(path).copy()
        except Exception:
            continue
        if df.empty:
            continue
        stem = path.stem
        base = stem[:-3] if stem.endswith("_D1") else stem
        if base.endswith("x"):
            base = base[:-1]
        asset = base[:-3] if base.endswith("USD") or base.endswith("EUR") else base
        frames[asset.upper()] = df.sort_values("date").reset_index(drop=True)
    return frames


def _lookup_exit_price(df: pd.DataFrame, planned_exit_date: str) -> tuple[float | None, str | None]:
    if df.empty or not planned_exit_date:
        return None, None

    target = pd.Timestamp(planned_exit_date)
    after = df[df["date"] >= target].sort_values("date")
    if after.empty:
        return None, None

    row = after.iloc[0]
    return float(row["close"]), pd.Timestamp(row["date"]).strftime("%Y-%m-%d")


def _signal_key(row: pd.Series) -> str:
    return str(row.get("signal_id", "")).strip()


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _format_price(value: object) -> str:
    if value is None or pd.isna(value):
        return "None"
    try:
        return f"{float(value):.8f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(value)


def _outcome_exists(conn: sqlite3.Connection, signal_id: str) -> bool:
    cur = conn.execute("SELECT 1 FROM signal_outcomes WHERE signal_id = ? LIMIT 1", (signal_id,))
    return cur.fetchone() is not None


OUTCOME_FIELDS = [
    "signal_key", "signal_id", "asset", "recommendation", "open_date", "close_date",
    "close_reason", "entry_price", "exit_price", "real_return_pct", "created_at", "updated_at",
]
COMPLETE_OUTCOME_FIELDS = [
    "signal_id", "asset", "recommendation", "open_date", "close_date", "close_reason",
    "entry_price", "exit_price", "real_return_pct", "created_at",
]


def _ensure_history_status_columns(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(signal_history)")}
    for column in ("old_status", "new_status"):
        if column not in columns:
            conn.execute(f"ALTER TABLE signal_history ADD COLUMN {column} TEXT")


def _migrate_outcome_keys(conn: sqlite3.Connection) -> int:
    """Use signal_id as the unique outcome identity without changing outcome values."""
    with conn:
        changed = conn.execute(
            "UPDATE signal_outcomes SET signal_key = signal_id WHERE signal_key <> signal_id"
        ).rowcount
    return changed


def _existing_outcome(conn: sqlite3.Connection, signal_key: str) -> dict[str, object] | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM signal_outcomes WHERE signal_key = ?", (signal_key,)).fetchone()
    conn.row_factory = None
    return dict(row) if row is not None else None


def _outcome_complete(outcome: dict[str, object]) -> bool:
    return all(outcome.get(field) is not None for field in COMPLETE_OUTCOME_FIELDS)


def _persist_outcome_and_close(
    conn: sqlite3.Connection,
    signal: dict[str, object],
    outcome: dict[str, object],
    counters: dict[str, int],
) -> None:
    """Persist outcome, signal status, and history as one atomic transaction."""
    signal_key = str(outcome["signal_key"])
    signal_id = str(signal["signal_id"])
    now = str(outcome["updated_at"])

    with conn:
        existing = _existing_outcome(conn, signal_key)
        if existing is None:
            placeholders = ", ".join("?" for _ in OUTCOME_FIELDS)
            conn.execute(
                f"INSERT INTO signal_outcomes ({', '.join(OUTCOME_FIELDS)}) VALUES ({placeholders})",
                tuple(outcome.get(field) for field in OUTCOME_FIELDS),
            )
            counters["outcomes_inserted"] += 1
            persisted = outcome
        elif _outcome_complete(existing):
            counters["outcomes_already_complete"] += 1
            persisted = existing
        else:
            assignments = ", ".join(
                f"{field} = COALESCE({field}, ?)" for field in OUTCOME_FIELDS
                if field not in {"signal_key", "created_at", "updated_at"}
            )
            update_fields = [
                field for field in OUTCOME_FIELDS
                if field not in {"signal_key", "created_at", "updated_at"}
            ]
            conn.execute(
                f"UPDATE signal_outcomes SET {assignments}, updated_at = ? WHERE signal_key = ?",
                (*[outcome.get(field) for field in update_fields], now, signal_key),
            )
            counters["outcomes_updated"] += 1
            persisted = _existing_outcome(conn, signal_key) or outcome

        changed = conn.execute(
            """
            UPDATE signals
            SET status = 'CLOSED',
                close_price = COALESCE(close_price, ?),
                real_return_pct = COALESCE(real_return_pct, ?),
                updated_at = ?
            WHERE signal_id = ? AND status = 'OPEN'
            """,
            (persisted.get("exit_price"), persisted.get("real_return_pct"), now, signal_id),
        ).rowcount
        if changed:
            counters["signals_closed"] += 1
            duplicate = conn.execute(
                """
                SELECT 1 FROM signal_history
                WHERE signal_id = ? AND old_status = 'OPEN' AND new_status = 'CLOSED'
                LIMIT 1
                """,
                (signal_id,),
            ).fetchone()
            if duplicate:
                counters["duplicate_history_events_skipped"] += 1
            else:
                history_key = f"{signal_key}:STATUS_CLOSED:{signal_id}"
                conn.execute(
                    """
                    INSERT INTO signal_history (
                        signal_key, signal_id, run_date, asset, recommendation,
                        old_status, new_status, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'OPEN', 'CLOSED', ?)
                    """,
                    (history_key, signal_id, TODAY, signal.get("asset"), signal.get("recommendation"), now),
                )


def run_engine() -> pd.DataFrame:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    with _connect() as conn:
        _ensure_history_status_columns(conn)
        migrated_outcome_keys = _migrate_outcome_keys(conn)
        open_signals = _load_open_signals(conn)
        ohlc = _ohlc_map()
        rows = []
        closed_count = 0
        skipped_count = 0
        still_open_count = 0
        counters = {
            "outcome_keys_migrated": migrated_outcome_keys,
            "outcomes_inserted": 0,
            "outcomes_updated": 0,
            "outcomes_already_complete": 0,
            "signals_closed": 0,
            "duplicate_history_events_skipped": 0,
        }

        for _, row in open_signals.iterrows():
            asset = str(row.get("asset", "")).strip().upper()
            signal_id = str(row.get("signal_id", "")).strip()
            planned_exit_date = row.get("planned_exit_date")
            entry_price = row.get("entry_price")
            status = str(row.get("status", "")).upper()
            close_date = None
            exit_price = None
            return_pct = None
            note = ""

            if pd.isna(planned_exit_date) or not str(planned_exit_date).strip():
                still_open_count += 1
                skipped_count += 1
                note = "planned_exit_date is NULL"
                rows.append(
                    {
                        "signal_id": signal_id,
                        "asset": asset,
                        "status": status,
                        "planned_exit_date": None,
                        "entry_price": entry_price,
                        "exit_price": None,
                        "return_pct": None,
                        "action": "SKIP",
                        "note": note,
                    }
                )
                continue

            planned_exit_date = str(planned_exit_date)
            if pd.Timestamp(planned_exit_date) > pd.Timestamp(TODAY):
                still_open_count += 1
                skipped_count += 1
                rows.append(
                    {
                        "signal_id": signal_id,
                        "asset": asset,
                        "status": status,
                        "planned_exit_date": planned_exit_date,
                        "entry_price": entry_price,
                        "exit_price": None,
                        "return_pct": None,
                        "action": "SKIP",
                        "note": "planned exit date not reached",
                    }
                )
                continue

            signal_key = _signal_key(row)
            existing = _existing_outcome(conn, signal_key)
            if existing is not None and _outcome_complete(existing):
                _persist_outcome_and_close(conn, row.to_dict(), existing, counters)
                closed_count += 1
                rows.append(
                    {
                        "signal_id": signal_id, "asset": asset, "status": status,
                        "planned_exit_date": planned_exit_date, "close_date": existing.get("close_date"),
                        "entry_price": existing.get("entry_price"), "exit_price": existing.get("exit_price"),
                        "return_pct": existing.get("real_return_pct"), "action": "CLOSED_EXISTING_OUTCOME",
                        "note": "existing complete outcome reused",
                    }
                )
                continue

            df = ohlc.get(asset)
            if df is None:
                skipped_count += 1
                rows.append(
                    {
                        "signal_id": signal_id,
                        "asset": asset,
                        "status": status,
                        "planned_exit_date": planned_exit_date,
                        "entry_price": entry_price,
                        "exit_price": None,
                        "return_pct": None,
                        "action": "SKIP",
                        "note": "no OHLC dataset found",
                    }
                )
                continue

            exit_price, close_date = _lookup_exit_price(df, planned_exit_date)
            if exit_price is None or entry_price in (None, 0) or pd.isna(entry_price):
                skipped_count += 1
                rows.append(
                    {
                        "signal_id": signal_id,
                        "asset": asset,
                        "status": status,
                        "planned_exit_date": planned_exit_date,
                        "entry_price": entry_price,
                        "exit_price": None,
                        "return_pct": None,
                        "action": "SKIP",
                        "note": "no close price on or after planned exit date",
                    }
                )
                continue

            return_pct = (exit_price / float(entry_price) - 1.0) * 100.0
            now = _now()
            outcome = {
                "signal_key": signal_key, "signal_id": signal_id, "asset": asset,
                "recommendation": row.get("recommendation"), "open_date": row.get("date"),
                "close_date": close_date, "close_reason": "planned_exit_date_reached",
                "entry_price": float(entry_price), "exit_price": float(exit_price),
                "real_return_pct": float(return_pct), "created_at": now, "updated_at": now,
            }
            _persist_outcome_and_close(conn, row.to_dict(), outcome, counters)

            closed_count += 1
            rows.append(
                {
                    "signal_id": signal_id,
                    "asset": asset,
                    "status": status,
                    "planned_exit_date": planned_exit_date,
                    "close_date": close_date,
                    "entry_price": float(entry_price),
                    "exit_price": float(exit_price),
                    "return_pct": round(float(return_pct), 4),
                    "action": "CLOSED",
                    "note": "",
                }
            )

    detail_report = pd.DataFrame(rows)
    report = pd.DataFrame([{"metric": key, "value": value} for key, value in counters.items()])
    report.to_csv(OUT_CSV, index=False)

    closed_rows = detail_report[detail_report["action"].astype(str).str.startswith("CLOSED")] if not detail_report.empty else pd.DataFrame()
    md_lines = [
        "# Signal Outcome Engine",
        "",
        f"Date: {TODAY}",
        "",
        "## Summary",
        "",
        f"- closed signals count: {closed_count}",
        f"- still open count: {still_open_count}",
        f"- skipped count: {skipped_count}",
        *[f"- {key}: {value}" for key, value in counters.items()],
        "",
        "## Closed Signals",
        "",
    ]

    if closed_rows.empty:
        md_lines.append("No open signals to close.")
    else:
        for _, row in closed_rows.iterrows():
            md_lines.append(
                f"- {row['asset']} | entry {_format_price(row['entry_price'])} | exit {_format_price(row['exit_price'])} | return {row['return_pct']}%"
            )

    if (detail_report["note"].fillna("").astype(str).str.contains("planned_exit_date is NULL").any() if not detail_report.empty else False):
        md_lines += ["", "## Notes", ""]
        for _, row in detail_report[detail_report["note"].fillna("").astype(str).str.contains("planned_exit_date is NULL")].iterrows():
            md_lines.append(f"- {row['signal_id']}: planned_exit_date is NULL")

    md_lines.append("")
    OUT_MD.write_text("\n".join(md_lines))
    return report


def main() -> None:
    report = run_engine()
    print(f"Saved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")
    if report.empty:
        print("No open signals to close.")
    else:
        print(report.to_string(index=False))


if __name__ == "__main__":
    main()
