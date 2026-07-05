from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "journal" / "project_memory.sqlite"
REPORT_DIR = ROOT / "DAILY_REPORTS"
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")
OUT_CSV = REPORT_DIR / f"{TODAY}_research_validation.csv"
OUT_MD = REPORT_DIR / f"{TODAY}_research_validation.md"


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found: {DB_PATH}")
    return sqlite3.connect(DB_PATH)


def _load_data(conn: sqlite3.Connection) -> pd.DataFrame:
    outcomes = pd.read_sql_query("SELECT * FROM signal_outcomes", conn)
    if outcomes.empty:
        return outcomes
    try:
        signals = pd.read_sql_query(
            """
            SELECT signal_id, asset, recommendation, opportunity_score, confidence_score, expected_value_pct, profit_factor, date
            FROM signals
            """,
            conn,
        )
    except Exception:
        signals = pd.DataFrame()
    if not signals.empty:
        outcomes = outcomes.merge(signals, on="signal_id", how="left", suffixes=("", "_signal"))
    return outcomes


def _to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _bucket(score: float | None) -> str:
    if score is None or pd.isna(score):
        return "UNKNOWN"
    if score < 40:
        return "0-39"
    if score < 60:
        return "40-59"
    if score < 80:
        return "60-79"
    return "80-100"


def _win_rate(series: pd.Series) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return float((valid > 0).mean() * 100)


def _profit_factor(series: pd.Series) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    gains = valid[valid > 0].sum()
    losses = valid[valid < 0].sum()
    if losses == 0:
        return None if gains == 0 else float("inf")
    return float(gains / abs(losses))


def _corr(df: pd.DataFrame, left: str, right: str) -> float | None:
    valid = df[[left, right]].dropna()
    if len(valid) < 2:
        return None
    return float(valid[left].corr(valid[right]))


def build_validation() -> tuple[pd.DataFrame, str]:
    with _connect() as conn:
        df = _load_data(conn)

    if df.empty:
        csv_df = pd.DataFrame(
            [
                {
                    "message": "No completed paper trades yet.",
                }
            ]
        )
        md = "\n".join(
            [
                "# Research Validation Engine",
                "",
                f"Date: {TODAY}",
                "",
                "No completed paper trades yet.",
                "",
            ]
        )
        return csv_df, md

    df = df.copy()
    df["real_return_pct"] = _to_float(df["real_return_pct"])
    for col in ["research_score", "opportunity_score", "confidence_score"]:
        if col in df.columns:
            df[col] = _to_float(df[col])

    # Prefer score from signals table if not already present
    if "research_score" not in df.columns:
        df["research_score"] = pd.NA

    buckets = [("0-39", 0, 39), ("40-59", 40, 59), ("60-79", 60, 79), ("80-100", 80, 100)]
    rows = []
    bucketed = df.copy()
    bucketed["research_bucket"] = bucketed["research_score"].apply(_bucket)
    for label, lo, hi in buckets:
        grp = bucketed[bucketed["research_bucket"] == label]
        returns = grp["real_return_pct"]
        rows.append(
            {
                "section": "RESEARCH_SCORE_BUCKET",
                "bucket": label,
                "trades": int(len(grp)),
                "avg_return_pct": round(_to_float(returns).mean(), 4) if not grp.empty else None,
                "win_rate_pct": round(_win_rate(returns), 2) if _win_rate(returns) is not None else None,
                "profit_factor": round(_profit_factor(returns), 4) if _profit_factor(returns) is not None else None,
            }
        )

    corr_rows = [
        {
            "section": "CORRELATION",
            "metric": "research_score ↔ return_pct",
            "value": round(_corr(df, "research_score", "real_return_pct"), 4) if _corr(df, "research_score", "real_return_pct") is not None else None,
        },
        {
            "section": "CORRELATION",
            "metric": "opportunity_score ↔ return_pct",
            "value": round(_corr(df, "opportunity_score", "real_return_pct"), 4) if _corr(df, "opportunity_score", "real_return_pct") is not None else None,
        },
        {
            "section": "CORRELATION",
            "metric": "confidence_score ↔ return_pct",
            "value": round(_corr(df, "confidence_score", "real_return_pct"), 4) if _corr(df, "confidence_score", "real_return_pct") is not None else None,
        },
    ]

    ranking = (
        bucketed.groupby("research_bucket", dropna=False)["real_return_pct"]
        .agg(["count", "mean"])
        .reset_index()
        .rename(columns={"research_bucket": "bucket", "count": "trades", "mean": "avg_return_pct"})
        .sort_values(["avg_return_pct", "trades"], ascending=[False, False], na_position="last")
    )
    ranking_rows = []
    for _, row in ranking.iterrows():
        ranking_rows.append(
            {
                "section": "RANKING",
                "bucket": row["bucket"],
                "trades": int(row["trades"]),
                "avg_return_pct": round(float(row["avg_return_pct"]), 4) if pd.notna(row["avg_return_pct"]) else None,
            }
        )

    report = pd.DataFrame(rows + corr_rows + ranking_rows)

    md_lines = [
        "# Research Validation Engine",
        "",
        f"Date: {TODAY}",
        "",
        "## Summary",
        "",
    ]
    for _, row in report[report["section"] == "RESEARCH_SCORE_BUCKET"].iterrows():
        md_lines.append(
            f"- {row['bucket']}: trades {row['trades']} | avg return {row['avg_return_pct']} | win rate {row['win_rate_pct']} | profit factor {row['profit_factor']}"
        )
    md_lines += ["", "## Correlations", ""]
    for _, row in report[report["section"] == "CORRELATION"].iterrows():
        md_lines.append(f"- {row['metric']}: {row['value']}")
    md_lines += ["", "## Best Categories", ""]
    if ranking.empty:
        md_lines.append("No ranking data.")
    else:
        for _, row in ranking.iterrows():
            md_lines.append(f"- {row['bucket']}: trades {row['trades']} | avg return {row['avg_return_pct']}")
    md_lines.append("")
    return report, "\n".join(md_lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report, md = build_validation()
    report.to_csv(OUT_CSV, index=False)
    OUT_MD.write_text(md)
    print(f"Saved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")
    print(md)


if __name__ == "__main__":
    main()
