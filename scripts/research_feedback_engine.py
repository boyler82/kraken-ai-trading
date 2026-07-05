from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "journal" / "project_memory.sqlite"
EDGE_PATH = ROOT / "BACKTESTS" / "rsi2_best_edge.csv"
REPORT_DIR = ROOT / "DAILY_REPORTS"
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")
OUT_CSV = REPORT_DIR / f"{TODAY}_research_feedback.csv"
OUT_MD = REPORT_DIR / f"{TODAY}_research_feedback.md"


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found: {DB_PATH}")
    return sqlite3.connect(DB_PATH)


def _read_outcomes(conn: sqlite3.Connection) -> pd.DataFrame:
    try:
        return pd.read_sql_query("SELECT * FROM signal_outcomes", conn)
    except Exception:
        return pd.DataFrame()


def _read_edge() -> pd.DataFrame:
    if not EDGE_PATH.exists():
        raise FileNotFoundError(f"Historical edge file not found: {EDGE_PATH}")
    return pd.read_csv(EDGE_PATH)


def _to_float_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _win_rate(series: pd.Series) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return float((valid > 0).mean() * 100)


def _avg(series: pd.Series) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return float(valid.mean())


def _median(series: pd.Series) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return float(valid.median())


def _grade(trades: int, paper_avg: float | None, hist_ev: float | None) -> str:
    if trades < 3:
        return "INSUFFICIENT_DATA"
    if paper_avg is None or hist_ev is None:
        return "INSUFFICIENT_DATA"
    if paper_avg >= hist_ev and trades >= 5:
        return "A"
    if paper_avg >= 0 and trades >= 3:
        return "B"
    if paper_avg < 0 and trades >= 3:
        return "C"
    return "INSUFFICIENT_DATA"


def build_feedback() -> tuple[pd.DataFrame, str]:
    edge = _read_edge()
    edge["asset"] = edge["asset"].astype(str).str.upper()
    edge["expected_value_pct"] = _to_float_series(edge["expected_value_pct"])

    with _connect() as conn:
        outcomes = _read_outcomes(conn)

    if outcomes.empty:
        csv_df = pd.DataFrame(
            [
                {
                    "asset": None,
                    "historical_expected_value_pct": None,
                    "paper_trades": 0,
                    "paper_win_rate_pct": None,
                    "paper_avg_return_pct": None,
                    "paper_median_return_pct": None,
                    "paper_best_return_pct": None,
                    "paper_worst_return_pct": None,
                    "ev_gap": None,
                    "feedback_grade": "No paper outcomes available yet.",
                    "message": "No paper outcomes available yet.",
                }
            ]
        )
        md = "\n".join(
            [
                "# Research Feedback Engine",
                "",
                f"Date: {TODAY}",
                "",
                "No paper outcomes available yet.",
                "",
            ]
        )
        return csv_df, md

    outcomes = outcomes.copy()
    outcomes["asset"] = outcomes["asset"].fillna("UNKNOWN").astype(str).str.upper()
    outcomes["real_return_pct"] = _to_float_series(outcomes["real_return_pct"])

    rows = []
    assets = sorted(set(edge["asset"].dropna().astype(str).str.upper().tolist()) | set(outcomes["asset"].dropna().astype(str).str.upper().tolist()))

    for asset in assets:
        edge_row = edge[edge["asset"] == asset]
        hist_ev = float(edge_row["expected_value_pct"].iloc[0]) if not edge_row.empty and pd.notna(edge_row["expected_value_pct"].iloc[0]) else None
        asset_outcomes = outcomes[outcomes["asset"] == asset]
        paper_trades = int(len(asset_outcomes))
        paper_win_rate = _win_rate(asset_outcomes["real_return_pct"])
        paper_avg = _avg(asset_outcomes["real_return_pct"])
        paper_median = _median(asset_outcomes["real_return_pct"])
        paper_best = float(asset_outcomes["real_return_pct"].max()) if not asset_outcomes["real_return_pct"].dropna().empty else None
        paper_worst = float(asset_outcomes["real_return_pct"].min()) if not asset_outcomes["real_return_pct"].dropna().empty else None
        ev_gap = (paper_avg - hist_ev) if paper_avg is not None and hist_ev is not None else None
        rows.append(
            {
                "asset": asset,
                "historical_expected_value_pct": hist_ev,
                "paper_trades": paper_trades,
                "paper_win_rate_pct": round(paper_win_rate, 2) if paper_win_rate is not None else None,
                "paper_avg_return_pct": round(paper_avg, 4) if paper_avg is not None else None,
                "paper_median_return_pct": round(paper_median, 4) if paper_median is not None else None,
                "paper_best_return_pct": round(paper_best, 4) if paper_best is not None else None,
                "paper_worst_return_pct": round(paper_worst, 4) if paper_worst is not None else None,
                "ev_gap": round(ev_gap, 4) if ev_gap is not None else None,
                "feedback_grade": _grade(paper_trades, paper_avg, hist_ev),
            }
        )

    report = pd.DataFrame(rows).sort_values(["feedback_grade", "asset"], ascending=[True, True]).reset_index(drop=True)

    md_lines = [
        "# Research Feedback Engine",
        "",
        f"Date: {TODAY}",
        "",
        "## Summary",
        "",
    ]

    if report.empty:
        md_lines.append("No feedback rows available.")
    else:
        for _, row in report.iterrows():
            md_lines.append(
                f"- {row['asset']}: grade {row['feedback_grade']} | hist EV {row['historical_expected_value_pct']} | trades {row['paper_trades']} | win rate {row['paper_win_rate_pct']} | avg return {row['paper_avg_return_pct']} | ev gap {row['ev_gap']}"
            )

    md_lines += ["", "## Detail", ""]
    if report.empty:
        md_lines.append("No data.")
    else:
        for _, row in report.iterrows():
            md_lines.append(
                f"- {row['asset']} | hist EV {row['historical_expected_value_pct']} | trades {row['paper_trades']} | win {row['paper_win_rate_pct']} | avg {row['paper_avg_return_pct']} | median {row['paper_median_return_pct']} | best {row['paper_best_return_pct']} | worst {row['paper_worst_return_pct']} | gap {row['ev_gap']} | grade {row['feedback_grade']}"
            )

    md_lines.append("")
    return report, "\n".join(md_lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report, md = build_feedback()
    report.to_csv(OUT_CSV, index=False)
    OUT_MD.write_text(md)
    print(f"Saved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")
    print(md)


if __name__ == "__main__":
    main()
