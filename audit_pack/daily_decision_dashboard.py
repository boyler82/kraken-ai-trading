from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "DAILY_REPORTS"
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")


def _latest(pattern: str) -> Path | None:
    files = sorted(REPORT_DIR.glob(pattern))
    return files[-1] if files else None


def _today_path(suffix: str) -> Path:
    return REPORT_DIR / f"{TODAY}_{suffix}"


def _load_csv(pattern: str) -> pd.DataFrame:
    path = _today_path(pattern.replace("*_", ""))
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _load_md(pattern: str) -> str:
    path = _today_path(pattern.replace("*_", ""))
    if not path.exists():
        return ""
    return path.read_text()


def _final_decision(portfolio: pd.DataFrame, watchlist: bool) -> tuple[str, str]:
    if not portfolio.empty and "proposed_weight_pct" in portfolio.columns:
        if (portfolio["proposed_weight_pct"].fillna(0) > 0).any():
            return "ACTION_REVIEW", "Portfolio allocation has proposed weight > 0."
    if watchlist:
        return "WAIT_AND_WATCH", "No allocation, but watchlist conditions are active."
    return "WAIT", "No allocation and no active watchlist conditions."


def _current_position(position_manager: pd.DataFrame, exit_planner: pd.DataFrame) -> pd.DataFrame:
    if position_manager.empty:
        return pd.DataFrame(columns=["asset", "current_pnl", "status", "base_target", "optimistic_target"])

    df = position_manager.copy()
    df = df.rename(columns={"unrealized_pnl_value": "current_pnl"})
    if not exit_planner.empty and "asset" in exit_planner.columns:
        targets = exit_planner[["asset", "base_target", "optimistic_target"]].copy()
        df = df.merge(targets, on="asset", how="left")
    else:
        df["base_target"] = None
        df["optimistic_target"] = None
    cols = ["asset", "current_pnl", "status", "base_target", "optimistic_target"]
    return df[cols]


def _top_rows(df: pd.DataFrame, limit: int = 5) -> pd.DataFrame:
    if df.empty:
        return df
    return df.head(limit).copy()


def _signal_exit_calendar() -> pd.DataFrame:
    df = _load_csv("*_signal_exit_calendar.csv")
    if df.empty:
        return df
    if "planned_exit_date" in df.columns:
        df = df.sort_values(["planned_exit_date", "asset"], ascending=[True, True], na_position="last")
    return df.head(5).copy()


def _realized_trades_summary() -> tuple[int, float, float, int] | None:
    df = _load_csv("*_realized_trades.csv")
    if df.empty:
        return None

    trades_count = len(df)
    total_proceeds = pd.to_numeric(df.get("proceeds"), errors="coerce").fillna(0).sum() if "proceeds" in df.columns else 0.0
    total_realized_pnl = pd.to_numeric(df.get("realized_pnl"), errors="coerce").fillna(0).sum() if "realized_pnl" in df.columns else 0.0
    fx_required_count = 0
    if "status" in df.columns:
        fx_required_count = df["status"].astype(str).str.contains("FX_REQUIRED", na=False).sum()
    elif "notes" in df.columns:
        fx_required_count = df["notes"].astype(str).str.contains("FX_REQUIRED", na=False).sum()
    return trades_count, float(total_proceeds), float(total_realized_pnl), int(fx_required_count)


def _research_score_leaders() -> pd.DataFrame:
    df = _load_csv("*_research_score.csv")
    if df.empty:
        return df
    sort_col = "research_score" if "research_score" in df.columns else None
    if sort_col is not None:
        df = df.sort_values([sort_col, "asset"], ascending=[False, True], na_position="last")
    return df.head(5).copy()


def _research_validation_status() -> str:
    md = _load_md("*_research_validation.md")
    if not md:
        return "No research validation available."
    if "No completed paper trades yet." in md:
        return "Research validation: waiting for completed paper trades"
    return "Research validation available."


def build_dashboard() -> tuple[pd.DataFrame, str]:
    daily_summary_md = _load_md("*_daily_research_summary.md")
    crypto = _load_csv("*_crypto_opportunity_ranking.csv")
    universal = _load_csv("*_universal_market_scanner.csv")
    portfolio = _load_csv("*_portfolio_allocation.csv")
    position_manager = _load_csv("*_position_manager.csv")
    exit_planner = _load_csv("*_exit_planner.csv")
    signal_exit_calendar = _signal_exit_calendar()
    realized_trades_summary = _realized_trades_summary()
    research_score_leaders = _research_score_leaders()
    research_validation_status = _research_validation_status()

    watchlist = False
    if not crypto.empty and "recommendation" in crypto.columns:
        watchlist = crypto["recommendation"].astype(str).str.contains("WATCH", na=False).any()
    if not universal.empty and "recommendation" in universal.columns:
        watchlist = watchlist or universal["recommendation"].astype(str).str.contains("WATCH", na=False).any()

    final_decision, final_reason = _final_decision(portfolio, watchlist)
    current_position = _current_position(position_manager, exit_planner)
    top_crypto = _top_rows(crypto, 5)
    top_universal = _top_rows(universal, 5)

    dashboard_rows = []
    dashboard_rows.append({"section": "FINAL DECISION", "key": "decision", "value": final_decision})
    dashboard_rows.append({"section": "FINAL DECISION", "key": "reason", "value": final_reason})

    if not current_position.empty:
        for _, row in current_position.iterrows():
            dashboard_rows.append(
                {
                    "section": "CURRENT POSITION",
                    "key": str(row["asset"]),
                    "value": f"P/L={row['current_pnl']} | status={row['status']} | base={row['base_target']} | optimistic={row['optimistic_target']}",
                }
            )
    else:
        dashboard_rows.append({"section": "CURRENT POSITION", "key": "none", "value": "No open positions"})

    if not top_crypto.empty:
        for _, row in top_crypto.iterrows():
            dashboard_rows.append(
                {
                    "section": "TOP CRYPTO OPPORTUNITIES",
                    "key": str(row.get("asset")),
                    "value": f"Opp={row.get('opportunity_score')} | Conf={row.get('confidence_score')} | Rec={row.get('recommendation')}",
                }
            )
    if not top_universal.empty:
        for _, row in top_universal.iterrows():
            dashboard_rows.append(
                {
                    "section": "TOP UNIVERSAL OPPORTUNITIES",
                    "key": str(row.get("asset")),
                    "value": f"Opp={row.get('opportunity_score')} | Conf={row.get('confidence_score')} | Rec={row.get('recommendation')}",
                }
            )

    if not portfolio.empty:
        allocation_status = "ALLOCATE_REVIEW" if (portfolio["proposed_weight_pct"].fillna(0) > 0).any() else "100% NO ALLOCATION"
    else:
        allocation_status = "100% NO ALLOCATION"
    dashboard_rows.append({"section": "PORTFOLIO ALLOCATION", "key": "status", "value": allocation_status})

    watch_assets = []
    if not crypto.empty and "recommendation" in crypto.columns:
        watch_assets.extend(crypto.loc[crypto["recommendation"].astype(str).str.contains("WATCH", na=False), "asset"].astype(str).tolist())
    if not universal.empty and "recommendation" in universal.columns:
        watch_assets.extend(universal.loc[universal["recommendation"].astype(str).str.contains("WATCH", na=False), "asset"].astype(str).tolist())
    watch_assets = sorted(set(watch_assets))
    if watch_assets:
        for asset in watch_assets:
            dashboard_rows.append({"section": "WATCHLIST", "key": asset, "value": "WATCH"})
    else:
        dashboard_rows.append({"section": "WATCHLIST", "key": "none", "value": "No watchlist assets."})

    if not signal_exit_calendar.empty:
        for _, row in signal_exit_calendar.iterrows():
            dashboard_rows.append(
                {
                    "section": "SIGNAL EXIT CALENDAR",
                    "key": str(row.get("asset")),
                    "value": f"planned_exit_date={row.get('planned_exit_date')} | days_to_exit={row.get('days_to_exit')} | status={row.get('status')}",
                }
            )
    else:
        dashboard_rows.append(
            {
                "section": "SIGNAL EXIT CALENDAR",
                "key": "none",
                "value": "No open positions",
            }
        )

    if realized_trades_summary is None:
        dashboard_rows.append(
            {
                "section": "REALIZED TRADES",
                "key": "none",
                "value": "No realized trades recorded.",
            }
        )
    else:
        trades_count, total_proceeds, total_realized_pnl, fx_required_count = realized_trades_summary
        dashboard_rows.append(
            {
                "section": "REALIZED TRADES",
                "key": "summary",
                "value": f"trades_count={trades_count} | total_proceeds={total_proceeds} | total_realized_pnl={total_realized_pnl} | FX_REQUIRED_trades_count={fx_required_count}",
            }
        )

    if not research_score_leaders.empty:
        for _, row in research_score_leaders.iterrows():
            dashboard_rows.append(
                {
                    "section": "RESEARCH SCORE LEADERS",
                    "key": str(row.get("asset")),
                    "value": f"research_score={row.get('research_score')} | status={row.get('status')} | recommendation={row.get('recommendation')} | expected_value_pct={row.get('expected_value_pct')} | profit_factor={row.get('profit_factor')}",
                }
            )
    else:
        dashboard_rows.append(
            {
                "section": "RESEARCH SCORE LEADERS",
                "key": "none",
                "value": "No research score available.",
            }
        )

    dashboard_rows.append({"section": "RESEARCH VALIDATION", "key": "status", "value": research_validation_status})

    dashboard_rows.append({"section": "PROCESS NOTE", "key": "note", "value": "Research only. No automatic trades."})

    dashboard = pd.DataFrame(dashboard_rows)
    dashboard.insert(0, "date", TODAY)
    return dashboard, final_decision


def render_markdown(dashboard: pd.DataFrame, final_decision: str) -> str:
    lines = [
        "# Daily Decision Dashboard",
        "",
        f"Date: {TODAY}",
        "",
        "## FINAL DECISION",
        "",
        f"- {final_decision}",
        "",
    ]

    final_rows = dashboard[dashboard["section"] == "FINAL DECISION"]
    for _, row in final_rows.iterrows():
        lines.append(f"- {row['key']}: {row['value']}")
    lines.append("")

    lines.append("## CURRENT POSITION")
    lines.append("")
    for _, row in dashboard[dashboard["section"] == "CURRENT POSITION"].iterrows():
        lines.append(f"- {row['key']}: {row['value']}")
    lines.append("")

    lines.append("## TOP CRYPTO OPPORTUNITIES")
    lines.append("")
    for _, row in dashboard[dashboard["section"] == "TOP CRYPTO OPPORTUNITIES"].iterrows():
        lines.append(f"- {row['key']}: {row['value']}")
    lines.append("")

    lines.append("## TOP UNIVERSAL OPPORTUNITIES")
    lines.append("")
    for _, row in dashboard[dashboard["section"] == "TOP UNIVERSAL OPPORTUNITIES"].iterrows():
        lines.append(f"- {row['key']}: {row['value']}")
    lines.append("")

    lines.append("## PORTFOLIO ALLOCATION")
    lines.append("")
    for _, row in dashboard[dashboard["section"] == "PORTFOLIO ALLOCATION"].iterrows():
        lines.append(f"- {row['key']}: {row['value']}")
    lines.append("")

    lines.append("## WATCHLIST")
    lines.append("")
    for _, row in dashboard[dashboard["section"] == "WATCHLIST"].iterrows():
        lines.append(f"- {row['key']}: {row['value']}")
    lines.append("")

    lines.append("## SIGNAL EXIT CALENDAR")
    lines.append("")
    signal_exit_rows = dashboard[dashboard["section"] == "SIGNAL EXIT CALENDAR"]
    if signal_exit_rows.empty or (len(signal_exit_rows) == 1 and signal_exit_rows.iloc[0]["value"] == "No open signal exits scheduled."):
        lines.append("No open signal exits scheduled.")
    else:
        for _, row in signal_exit_rows.iterrows():
            lines.append(f"- {row['key']}: {row['value']}")
    lines.append("")

    lines.append("## REALIZED TRADES")
    lines.append("")
    realized_rows = dashboard[dashboard["section"] == "REALIZED TRADES"]
    if realized_rows.empty or (len(realized_rows) == 1 and realized_rows.iloc[0]["value"] == "No realized trades recorded."):
        lines.append("No realized trades recorded.")
    else:
        for _, row in realized_rows.iterrows():
            lines.append(f"- {row['value']}")
    lines.append("")

    lines.append("## RESEARCH SCORE LEADERS")
    lines.append("")
    research_score_rows = dashboard[dashboard["section"] == "RESEARCH SCORE LEADERS"]
    if research_score_rows.empty or (len(research_score_rows) == 1 and research_score_rows.iloc[0]["value"] == "No research score available."):
        lines.append("No research score available.")
    else:
        for _, row in research_score_rows.iterrows():
            lines.append(f"- {row['key']}: {row['value']}")
    lines.append("")

    lines.append("## RESEARCH VALIDATION")
    lines.append("")
    validation_rows = dashboard[dashboard["section"] == "RESEARCH VALIDATION"]
    if validation_rows.empty:
        lines.append("No research validation available.")
    else:
        for _, row in validation_rows.iterrows():
            lines.append(f"- {row['value']}")
    lines.append("")

    lines.append("## PROCESS NOTE")
    lines.append("")
    for _, row in dashboard[dashboard["section"] == "PROCESS NOTE"].iterrows():
        lines.append(f"- {row['value']}")
    lines.append("")
    lines.append("Research only. No automatic trades.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    dashboard, final_decision = build_dashboard()
    csv_out = REPORT_DIR / f"{TODAY}_daily_decision_dashboard.csv"
    md_out = REPORT_DIR / f"{TODAY}_daily_decision_dashboard.md"
    dashboard.to_csv(csv_out, index=False)
    md_out.write_text(render_markdown(dashboard, final_decision))

    print("\nDAILY DECISION DASHBOARD\n")
    print(dashboard.to_string(index=False))
    print(f"\nSaved: {csv_out}")
    print(f"Saved: {md_out}")


if __name__ == "__main__":
    main()
