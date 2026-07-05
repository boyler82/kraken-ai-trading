from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "journal" / "project_memory.sqlite"
REPORT_DIR = ROOT / "DAILY_REPORTS"
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")
OUT_CSV = REPORT_DIR / f"{TODAY}_strategy_performance.csv"
OUT_MD = REPORT_DIR / f"{TODAY}_strategy_performance.md"


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found: {DB_PATH}")
    return sqlite3.connect(DB_PATH)


def _read_outcomes(conn: sqlite3.Connection) -> pd.DataFrame:
    try:
        return pd.read_sql_query("SELECT * FROM signal_outcomes", conn)
    except Exception:
        return pd.DataFrame()


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["asset"] = out["asset"].fillna("UNKNOWN").astype(str).str.upper()
    out["recommendation"] = out["recommendation"].fillna("UNKNOWN").astype(str).str.upper()
    out["real_return_pct"] = pd.to_numeric(out.get("real_return_pct"), errors="coerce")
    out["close_date"] = pd.to_datetime(out.get("close_date"), errors="coerce")
    out["month"] = out["close_date"].dt.to_period("M").astype(str)
    return out


def _win_rate(series: pd.Series) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return float((valid > 0).mean() * 100)


def _avg_return(series: pd.Series) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return float(valid.mean())


def _median_return(series: pd.Series) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return float(valid.median())


def _best_trade(df: pd.DataFrame) -> str:
    if df.empty or "real_return_pct" not in df.columns:
        return "N/A"
    valid = df.dropna(subset=["real_return_pct"])
    if valid.empty:
        return "N/A"
    row = valid.sort_values("real_return_pct", ascending=False).iloc[0]
    return f"{row.get('asset', 'N/A')} | {row.get('recommendation', 'N/A')} | {row.get('real_return_pct', 'N/A')}%"


def _worst_trade(df: pd.DataFrame) -> str:
    if df.empty or "real_return_pct" not in df.columns:
        return "N/A"
    valid = df.dropna(subset=["real_return_pct"])
    if valid.empty:
        return "N/A"
    row = valid.sort_values("real_return_pct", ascending=True).iloc[0]
    return f"{row.get('asset', 'N/A')} | {row.get('recommendation', 'N/A')} | {row.get('real_return_pct', 'N/A')}%"


def _recommendation_bucket(rec: str) -> str:
    rec = str(rec).upper()
    if rec in {"DAY1_OBSERVE_ONLY", "DAY2_ENTRY", "DAY3_ENTRY", "WATCHLIST", "NO_ACTION"}:
        return rec
    if rec in {"WATCH_RESEARCH", "WATCH_CLOSELY"}:
        return "WATCHLIST"
    return rec


def build_report() -> tuple[pd.DataFrame, str]:
    with _connect() as conn:
        outcomes = _prepare(_read_outcomes(conn))

    if outcomes.empty:
        csv_df = pd.DataFrame([{"section": "GLOBAL", "metric": "message", "value": "No completed paper trades yet."}])
        md = "\n".join(
            [
                "# Strategy Performance Engine",
                "",
                f"Date: {TODAY}",
                "",
                "No completed paper trades yet.",
                "",
            ]
        )
        return csv_df, md

    completed = len(outcomes)
    win_rate = _win_rate(outcomes["real_return_pct"])
    avg_return = _avg_return(outcomes["real_return_pct"])
    median_return = _median_return(outcomes["real_return_pct"])
    total_expectancy = float(outcomes["real_return_pct"].dropna().sum()) if not outcomes["real_return_pct"].dropna().empty else None
    best_trade = _best_trade(outcomes)
    worst_trade = _worst_trade(outcomes)

    rows: list[dict[str, object]] = []
    rows.extend(
        [
            {"section": "GLOBAL", "metric": "completed trades", "value": completed},
            {"section": "GLOBAL", "metric": "win rate", "value": round(win_rate, 2) if win_rate is not None else None},
            {"section": "GLOBAL", "metric": "average return", "value": round(avg_return, 4) if avg_return is not None else None},
            {"section": "GLOBAL", "metric": "median return", "value": round(median_return, 4) if median_return is not None else None},
            {"section": "GLOBAL", "metric": "total expectancy", "value": round(total_expectancy, 4) if total_expectancy is not None else None},
            {"section": "GLOBAL", "metric": "best trade", "value": best_trade},
            {"section": "GLOBAL", "metric": "worst trade", "value": worst_trade},
        ]
    )

    asset_rows = []
    for asset, grp in outcomes.groupby("asset", dropna=False):
        asset_rows.append(
            {
                "section": "PER ASSET",
                "asset": asset,
                "trades": int(len(grp)),
                "win_rate": round(_win_rate(grp["real_return_pct"]), 2) if _win_rate(grp["real_return_pct"]) is not None else None,
                "average_return": round(_avg_return(grp["real_return_pct"]), 4) if _avg_return(grp["real_return_pct"]) is not None else None,
                "median_return": round(_median_return(grp["real_return_pct"]), 4) if _median_return(grp["real_return_pct"]) is not None else None,
                "max_win": float(grp["real_return_pct"].max()) if not grp["real_return_pct"].dropna().empty else None,
                "max_loss": float(grp["real_return_pct"].min()) if not grp["real_return_pct"].dropna().empty else None,
            }
        )

    rec_order = ["DAY1_OBSERVE_ONLY", "DAY2_ENTRY", "DAY3_ENTRY", "WATCHLIST", "NO_ACTION"]
    rec_rows = []
    outcomes["rec_bucket"] = outcomes["recommendation"].map(_recommendation_bucket)
    for rec in rec_order:
        grp = outcomes[outcomes["rec_bucket"] == rec]
        rec_rows.append(
            {
                "section": "PER RECOMMENDATION",
                "recommendation": rec,
                "trades": int(len(grp)),
                "avg_return": round(_avg_return(grp["real_return_pct"]), 4) if not grp.empty else None,
                "win_rate": round(_win_rate(grp["real_return_pct"]), 2) if not grp.empty else None,
            }
        )

    monthly_rows = []
    for month, grp in outcomes.groupby("month", dropna=False):
        if month == "NaT" or pd.isna(month):
            continue
        monthly_rows.append(
            {
                "section": "MONTHLY",
                "month": month,
                "trades": int(len(grp)),
                "win_rate": round(_win_rate(grp["real_return_pct"]), 2) if _win_rate(grp["real_return_pct"]) is not None else None,
                "average_return": round(_avg_return(grp["real_return_pct"]), 4) if _avg_return(grp["real_return_pct"]) is not None else None,
            }
        )

    csv_df = pd.DataFrame(rows + asset_rows + rec_rows + monthly_rows)

    md_lines = [
        "# Strategy Performance Engine",
        "",
        f"Date: {TODAY}",
        "",
        "## Global",
        "",
        f"- completed trades: {completed}",
        f"- win rate: {win_rate:.2f}%" if win_rate is not None else "- win rate: N/A",
        f"- average return: {avg_return:.4f}%" if avg_return is not None else "- average return: N/A",
        f"- median return: {median_return:.4f}%" if median_return is not None else "- median return: N/A",
        f"- total expectancy: {total_expectancy:.4f}%" if total_expectancy is not None else "- total expectancy: N/A",
        f"- best trade: {best_trade}",
        f"- worst trade: {worst_trade}",
        "",
        "## Per Asset",
        "",
    ]

    if asset_rows:
        for row in asset_rows:
            md_lines.append(
                f"- {row['asset']}: trades {row['trades']} | win rate {row['win_rate']} | avg return {row['average_return']} | median return {row['median_return']} | max win {row['max_win']} | max loss {row['max_loss']}"
            )
    else:
        md_lines.append("No asset-level data.")

    md_lines += ["", "## Per Recommendation", ""]
    if rec_rows:
        for row in rec_rows:
            md_lines.append(
                f"- {row['recommendation']}: trades {row['trades']} | avg return {row['avg_return']} | win rate {row['win_rate']}"
            )
    else:
        md_lines.append("No recommendation-level data.")

    md_lines += ["", "## Monthly", ""]
    if monthly_rows:
        for row in monthly_rows:
            md_lines.append(
                f"- {row['month']}: trades {row['trades']} | win rate {row['win_rate']} | average return {row['average_return']}"
            )
    else:
        md_lines.append("No monthly data.")

    md_lines.append("")
    return csv_df, "\n".join(md_lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    csv_df, md = build_report()
    csv_df.to_csv(OUT_CSV, index=False)
    OUT_MD.write_text(md)
    print(f"Saved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")
    print(md)


if __name__ == "__main__":
    main()
