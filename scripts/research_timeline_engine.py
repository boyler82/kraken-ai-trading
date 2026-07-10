from __future__ import annotations

from pathlib import Path
import glob

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "DAILY_REPORTS"
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")
OUT_CSV = REPORT_DIR / f"{TODAY}_research_timeline.csv"
OUT_MD = REPORT_DIR / f"{TODAY}_research_timeline.md"


def _load_snapshot(path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()
    date_text = Path(path).name.split("_trade_candidate_dashboard.csv")[0]
    df = df.copy()
    df["snapshot_date"] = date_text
    return df


def _trend_status(observations: int, readiness_change: float | None) -> str:
    if observations == 1:
        return "NEW"
    if readiness_change is None or pd.isna(readiness_change):
        return "STABLE"
    if readiness_change >= 15:
        return "RISING"
    if readiness_change <= -15:
        return "FALLING"
    return "STABLE"


def build_timeline() -> pd.DataFrame:
    files = sorted(glob.glob(str(REPORT_DIR / "*_trade_candidate_dashboard.csv")))
    if not files:
        return pd.DataFrame(columns=[
            "asset",
            "first_seen_date",
            "last_seen_date",
            "observations",
            "latest_readiness_pct",
            "previous_readiness_pct",
            "readiness_change",
            "max_readiness_pct",
            "min_readiness_pct",
            "latest_research_score",
            "max_research_score",
            "latest_priority",
            "latest_recommendation",
            "latest_current_phase",
            "trend_status",
        ])

    snapshots = [df for df in (_load_snapshot(p) for p in files) if not df.empty]
    if not snapshots:
        return pd.DataFrame(columns=[
            "asset",
            "first_seen_date",
            "last_seen_date",
            "observations",
            "latest_readiness_pct",
            "previous_readiness_pct",
            "readiness_change",
            "max_readiness_pct",
            "min_readiness_pct",
            "latest_research_score",
            "max_research_score",
            "latest_priority",
            "latest_recommendation",
            "latest_current_phase",
            "trend_status",
        ])

    all_df = pd.concat(snapshots, ignore_index=True)
    all_df["asset"] = all_df["asset"].astype(str).str.upper()
    all_df["snapshot_date"] = pd.to_datetime(all_df["snapshot_date"], errors="coerce")
    all_df["readiness_pct"] = pd.to_numeric(all_df["readiness_pct"], errors="coerce")
    all_df["research_score"] = pd.to_numeric(all_df["research_score"], errors="coerce")

    rows = []
    for asset, grp in all_df.sort_values(["snapshot_date", "asset"]).groupby("asset", dropna=False):
        grp = grp.sort_values("snapshot_date")
        observations = int(len(grp))
        latest = grp.iloc[-1]
        previous = grp.iloc[-2] if observations > 1 else None
        readiness_change = None
        if previous is not None and pd.notna(latest.get("readiness_pct")) and pd.notna(previous.get("readiness_pct")):
            readiness_change = float(latest["readiness_pct"]) - float(previous["readiness_pct"])
        rows.append(
            {
                "asset": asset,
                "first_seen_date": grp.iloc[0]["snapshot_date"].strftime("%Y-%m-%d"),
                "last_seen_date": grp.iloc[-1]["snapshot_date"].strftime("%Y-%m-%d"),
                "observations": observations,
                "latest_readiness_pct": float(latest["readiness_pct"]) if pd.notna(latest["readiness_pct"]) else None,
                "previous_readiness_pct": float(previous["readiness_pct"]) if previous is not None and pd.notna(previous["readiness_pct"]) else None,
                "readiness_change": round(readiness_change, 4) if readiness_change is not None else None,
                "max_readiness_pct": float(grp["readiness_pct"].max()) if not grp["readiness_pct"].dropna().empty else None,
                "min_readiness_pct": float(grp["readiness_pct"].min()) if not grp["readiness_pct"].dropna().empty else None,
                "latest_research_score": float(latest["research_score"]) if pd.notna(latest["research_score"]) else None,
                "max_research_score": float(grp["research_score"].max()) if not grp["research_score"].dropna().empty else None,
                "latest_priority": latest.get("priority"),
                "latest_recommendation": latest.get("recommendation"),
                "latest_current_phase": latest.get("current_phase"),
                "trend_status": _trend_status(observations, readiness_change),
            }
        )

    report = pd.DataFrame(rows)
    if report.empty:
        return report

    report = report.sort_values(["latest_readiness_pct", "latest_research_score", "asset"], ascending=[False, False, True], na_position="last").reset_index(drop=True)
    return report


def render_markdown(report: pd.DataFrame) -> str:
    lines = [
        "# Research Timeline Engine",
        "",
        f"Date: {TODAY}",
        "",
        "## Rising Setups",
        "",
    ]

    if report.empty:
        lines.append("No timeline data available.")
        lines.append("")
        return "\n".join(lines)

    rising = report[report["trend_status"] == "RISING"]
    falling = report[report["trend_status"] == "FALLING"]
    stable_active = report[report["trend_status"].isin(["STABLE", "NEW"])].copy()

    if rising.empty:
        lines.append("No rising setups.")
    else:
        for _, row in rising.iterrows():
            lines.append(
                f"- {row['asset']} | change {row['readiness_change']} | latest {row['latest_readiness_pct']} | priority {row['latest_priority']} | rec {row['latest_recommendation']}"
            )

    lines += ["", "## Falling Setups", ""]
    if falling.empty:
        lines.append("No falling setups.")
    else:
        for _, row in falling.iterrows():
            lines.append(
                f"- {row['asset']} | change {row['readiness_change']} | latest {row['latest_readiness_pct']} | priority {row['latest_priority']} | rec {row['latest_recommendation']}"
            )

    lines += ["", "## Stable / Active Setups", ""]
    if stable_active.empty:
        lines.append("No stable or active setups.")
    else:
        for _, row in stable_active.iterrows():
            lines.append(
                f"- {row['asset']} | status {row['trend_status']} | latest {row['latest_readiness_pct']} | previous {row['previous_readiness_pct']} | change {row['readiness_change']} | priority {row['latest_priority']}"
            )

    lines += ["", "## Full Timeline Summary", ""]
    for _, row in report.iterrows():
        lines.append(
            f"- {row['asset']} | first {row['first_seen_date']} | last {row['last_seen_date']} | obs {row['observations']} | latest {row['latest_readiness_pct']} | prev {row['previous_readiness_pct']} | change {row['readiness_change']} | max {row['max_readiness_pct']} | min {row['min_readiness_pct']} | trend {row['trend_status']}"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = build_timeline()
    report.to_csv(OUT_CSV, index=False)
    OUT_MD.write_text(render_markdown(report))
    print(f"Saved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")
    if not report.empty:
        print(report.to_string(index=False))
    else:
        print("No timeline data available.")


if __name__ == "__main__":
    main()
