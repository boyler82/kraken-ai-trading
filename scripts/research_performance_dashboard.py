from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "journal" / "project_memory.sqlite"
REPORT_DIR = ROOT / "DAILY_REPORTS"
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")
OUT_CSV = REPORT_DIR / f"{TODAY}_research_performance_dashboard.csv"
OUT_MD = REPORT_DIR / f"{TODAY}_research_performance_dashboard.md"


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found: {DB_PATH}")
    return sqlite3.connect(DB_PATH)


def _read_table(conn: sqlite3.Connection, table: str) -> pd.DataFrame:
    try:
        return pd.read_sql_query(f"SELECT * FROM {table}", conn)
    except Exception:
        return pd.DataFrame()


def _count_open_signals(signals: pd.DataFrame) -> int:
    if signals.empty or "status" not in signals.columns:
        return 0
    return int((signals["status"].astype(str).str.upper() == "OPEN").sum())


def _count_closed_signals(signals: pd.DataFrame) -> int:
    if signals.empty or "status" not in signals.columns:
        return 0
    return int((signals["status"].astype(str).str.upper() == "CLOSED").sum())


def _active_signals(signals: pd.DataFrame) -> pd.DataFrame:
    if signals.empty:
        return signals
    df = signals.copy()
    if "status" in df.columns:
        df = df[df["status"].astype(str).str.upper() == "OPEN"]
    sort_cols = [c for c in ["updated_at", "created_at", "date"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, ascending=False, na_position="last")
    return df.head(10).reset_index(drop=True)


def _asset_summary(signals: pd.DataFrame, history: pd.DataFrame, outcomes: pd.DataFrame) -> pd.DataFrame:
    asset_frames = []
    for df, col, name in [
        (signals, "asset", "signals"),
        (history, "asset", "history"),
        (outcomes, "asset", "outcomes"),
    ]:
        if df.empty or col not in df.columns:
            continue
        asset_frames.append(df[[col]].rename(columns={col: "asset"}).assign(source=name))

    if not asset_frames:
        return pd.DataFrame(columns=["asset", "open_signals", "history_rows", "closed_outcomes"])

    assets = pd.concat(asset_frames, ignore_index=True)["asset"].dropna().astype(str).str.upper().unique()
    rows = []
    for asset in sorted(assets):
        open_count = 0
        if not signals.empty and "asset" in signals.columns and "status" in signals.columns:
            mask = signals["asset"].astype(str).str.upper() == asset
            open_count = int((signals.loc[mask, "status"].astype(str).str.upper() == "OPEN").sum())
        history_rows = 0
        if not history.empty and "asset" in history.columns:
            history_rows = int((history["asset"].astype(str).str.upper() == asset).sum())
        closed_outcomes = 0
        if not outcomes.empty and "asset" in outcomes.columns:
            closed_outcomes = int((outcomes["asset"].astype(str).str.upper() == asset).sum())
        rows.append(
            {
                "asset": asset,
                "open_signals": open_count,
                "history_rows": history_rows,
                "closed_outcomes": closed_outcomes,
            }
        )
    return pd.DataFrame(rows).sort_values(["open_signals", "history_rows", "closed_outcomes", "asset"], ascending=[False, False, False, True]).reset_index(drop=True)


def _best_worst(outcomes: pd.DataFrame) -> tuple[str, str]:
    if outcomes.empty or "real_return_pct" not in outcomes.columns:
        return "N/A", "N/A"
    valid = outcomes.dropna(subset=["real_return_pct"]).copy()
    if valid.empty:
        return "N/A", "N/A"
    best = valid.sort_values("real_return_pct", ascending=False).iloc[0]
    worst = valid.sort_values("real_return_pct", ascending=True).iloc[0]
    best_label = f"{best.get('asset', 'N/A')} | {best.get('recommendation', 'N/A')} | {best.get('real_return_pct', 'N/A')}%"
    worst_label = f"{worst.get('asset', 'N/A')} | {worst.get('recommendation', 'N/A')} | {worst.get('real_return_pct', 'N/A')}%"
    return best_label, worst_label


def build_dashboard() -> tuple[pd.DataFrame, str]:
    with _connect() as conn:
        signal_history = _read_table(conn, "signal_history")
        signal_outcomes = _read_table(conn, "signal_outcomes")
        signals = _read_table(conn, "signals")
        daily_runs = _read_table(conn, "daily_runs")

    open_signals = _count_open_signals(signals)
    closed_signals = _count_closed_signals(signals)
    history_rows = int(len(signal_history))
    outcome_rows = int(len(signal_outcomes))

    active = _active_signals(signals)
    asset_summary = _asset_summary(signals, signal_history, signal_outcomes)

    if not signal_outcomes.empty and "real_return_pct" in signal_outcomes.columns:
        valid = signal_outcomes.dropna(subset=["real_return_pct"]).copy()
        if valid.empty:
            win_rate = None
            avg_return = None
            best_signal = "N/A"
            worst_signal = "N/A"
        else:
            win_rate = float((valid["real_return_pct"] > 0).mean() * 100)
            avg_return = float(valid["real_return_pct"].mean())
            best_signal, worst_signal = _best_worst(valid)
    else:
        win_rate = None
        avg_return = None
        best_signal = "N/A"
        worst_signal = "N/A"

    summary_rows = [
        {"metric": "open_signals", "value": open_signals},
        {"metric": "closed_signals", "value": closed_signals},
        {"metric": "signal_history_rows", "value": history_rows},
        {"metric": "signal_outcomes_rows", "value": outcome_rows},
    ]

    if not asset_summary.empty:
        for _, row in asset_summary.iterrows():
            summary_rows.append(
                {
                    "metric": "asset_summary",
                    "asset": row["asset"],
                    "open_signals": int(row["open_signals"]),
                    "history_rows": int(row["history_rows"]),
                    "closed_outcomes": int(row["closed_outcomes"]),
                }
            )
    else:
        summary_rows.append(
            {
                "metric": "asset_summary",
                "asset": None,
                "open_signals": None,
                "history_rows": None,
                "closed_outcomes": None,
            }
        )

    if not signal_outcomes.empty and "real_return_pct" in signal_outcomes.columns:
        summary_rows.extend(
            [
                {"metric": "win_rate_pct", "value": round(win_rate, 2) if win_rate is not None else None},
                {"metric": "avg_return_pct", "value": round(avg_return, 4) if avg_return is not None else None},
                {"metric": "best_signal", "value": best_signal},
                {"metric": "worst_signal", "value": worst_signal},
            ]
        )
    else:
        summary_rows.append({"metric": "insufficient_live_outcome_data", "value": "No closed signal outcomes yet."})

    dashboard_csv = pd.DataFrame(summary_rows)
    md_lines = [
        "# Research Performance Dashboard",
        "",
        f"Date: {TODAY}",
        "",
        "Research only. No strategy changes.",
        "",
        "## Summary",
        "",
        f"- OPEN signals: {open_signals}",
        f"- CLOSED signals: {closed_signals}",
        f"- signal_history rows: {history_rows}",
        f"- signal_outcomes rows: {outcome_rows}",
        "",
        "## Last 10 Active Signals",
        "",
    ]

    if active.empty:
        md_lines.append("No active signals.")
    else:
        for _, row in active.head(10).iterrows():
            md_lines.append(
                f"- {row.get('signal_id', 'N/A')} | {row.get('asset', 'N/A')} | {row.get('recommendation', 'N/A')} | {row.get('current_phase', 'N/A')} | {row.get('status', 'N/A')} | score {row.get('opportunity_score', 'N/A')} | conf {row.get('confidence_score', 'N/A')}"
            )

    md_lines += [
        "",
        "## Asset Summary",
        "",
    ]
    if asset_summary.empty:
        md_lines.append("No asset summary available.")
    else:
        for _, row in asset_summary.iterrows():
            md_lines.append(
                f"- {row['asset']} | open_signals {int(row['open_signals'])} | history_rows {int(row['history_rows'])} | closed_outcomes {int(row['closed_outcomes'])}"
            )

    md_lines += ["", "## Outcomes"]
    if signal_outcomes.empty or "real_return_pct" not in signal_outcomes.columns or signal_outcomes.dropna(subset=["real_return_pct"]).empty:
        md_lines += ["", "Insufficient live outcome data", "", "No closed signal outcomes yet."]
    else:
        md_lines += [
            "",
            f"- Win rate: {win_rate:.2f}%",
            f"- Avg return: {avg_return:.4f}%",
            f"- Best signal: {best_signal}",
            f"- Worst signal: {worst_signal}",
            "",
            "### Daily Runs",
            "",
        ]
        if daily_runs.empty:
            md_lines.append("No daily run rows.")
        else:
            for _, row in daily_runs.sort_values(daily_runs.columns[0], ascending=False).head(10).iterrows():
                md_lines.append(
                    f"- {row.get('run_date', 'N/A')} | {row.get('final_status', 'N/A')} | active {row.get('active_signals', 'N/A')} | high priority {row.get('high_priority_signals', 'N/A')}"
                )

    return dashboard_csv, "\n".join(md_lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    dashboard_csv, dashboard_md = build_dashboard()
    dashboard_csv.to_csv(OUT_CSV, index=False)
    OUT_MD.write_text(dashboard_md)
    print(f"Saved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")


if __name__ == "__main__":
    main()
