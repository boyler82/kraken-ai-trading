from __future__ import annotations

import glob
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from lib.data_loader import load_ohlc  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "journal" / "project_memory.sqlite"
REPORT_DIR = ROOT / "DAILY_REPORTS"
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
        SELECT *
        FROM signals
        WHERE status = 'OPEN'
        ORDER BY planned_exit_date ASC, date ASC, asset ASC
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
    return f"{str(row.get('asset', '')).strip().upper()}:{str(row.get('recommendation', '')).strip().upper()}"


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


def run_engine() -> pd.DataFrame:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    with _connect() as conn:
        open_signals = _load_open_signals(conn)
        if open_signals.empty:
            report = pd.DataFrame(
                [
                    {
                        "metric": "message",
                        "value": "No open signals to close.",
                    }
                ]
            )
            report.to_csv(OUT_CSV, index=False)
            OUT_MD.write_text(
                "\n".join(
                    [
                        "# Signal Outcome Engine",
                        "",
                        f"Date: {TODAY}",
                        "",
                        "No open signals to close.",
                        "",
                    ]
                )
            )
            return report

        ohlc = _ohlc_map()
        rows = []
        closed_count = 0
        skipped_count = 0
        still_open_count = 0

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
            signal_key = _signal_key(row)
            now = _now()

            if not _outcome_exists(conn, signal_id):
                conn.execute(
                    """
                    INSERT INTO signal_outcomes (
                        signal_key, signal_id, asset, recommendation, open_date,
                        close_date, close_reason, entry_price, exit_price,
                        real_return_pct, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        signal_key,
                        signal_id,
                        asset,
                        row.get("recommendation"),
                        row.get("date"),
                        close_date,
                        "planned_exit_date_reached",
                        float(entry_price),
                        float(exit_price),
                        float(return_pct),
                        now,
                        now,
                    ),
                )

            conn.execute(
                """
                UPDATE signals
                SET status = 'CLOSED',
                    close_price = ?,
                    real_return_pct = ?,
                    updated_at = ?
                WHERE signal_id = ?
                """,
                (float(exit_price), float(return_pct), now, signal_id),
            )

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

        conn.commit()

    report = pd.DataFrame(rows)
    report.to_csv(OUT_CSV, index=False)

    closed_rows = report[report["action"] == "CLOSED"] if not report.empty else pd.DataFrame()
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

    if (report["note"].fillna("").astype(str).str.contains("planned_exit_date is NULL").any() if not report.empty else False):
        md_lines += ["", "## Notes", ""]
        for _, row in report[report["note"].fillna("").astype(str).str.contains("planned_exit_date is NULL")].iterrows():
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
