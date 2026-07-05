from __future__ import annotations

from pathlib import Path
import glob

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "DAILY_REPORTS"
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")
OUT_CSV = REPORT_DIR / f"{TODAY}_research_evolution.csv"
OUT_MD = REPORT_DIR / f"{TODAY}_research_evolution.md"


def _latest_two(pattern: str) -> tuple[Path | None, Path | None]:
    files = sorted(glob.glob(str(REPORT_DIR / pattern)))
    if not files:
        return None, None
    if len(files) == 1:
        return Path(files[-1]), None
    return Path(files[-1]), Path(files[-2])


def _load(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _priority_rank(priority: str | None) -> int:
    order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "IGNORE": 0}
    return order.get(str(priority).upper(), -1)


def _evolution_status(readiness_delta: float | None, new: bool, removed: bool) -> str:
    if new:
        return "NEW"
    if removed:
        return "REMOVED"
    if readiness_delta is None or pd.isna(readiness_delta):
        return "STABLE"
    if readiness_delta >= 15:
        return "IMPROVING"
    if readiness_delta <= -15:
        return "DETERIORATING"
    return "STABLE"


def build_evolution() -> pd.DataFrame:
    latest_path, prev_path = _latest_two("*_trade_candidate_dashboard.csv")
    latest = _load(latest_path)
    previous = _load(prev_path)

    if latest.empty:
        return pd.DataFrame(columns=[
            "asset",
            "readiness_today",
            "readiness_previous",
            "readiness_delta",
            "research_score_delta",
            "opportunity_score_delta",
            "confidence_score_delta",
            "priority_change",
            "evolution_status",
        ])

    if previous.empty:
        rows = []
        for _, row in latest.iterrows():
            rows.append(
                {
                    "asset": row.get("asset"),
                    "readiness_today": row.get("readiness_pct"),
                    "readiness_previous": None,
                    "readiness_delta": None,
                    "research_score_delta": None,
                    "opportunity_score_delta": None,
                    "confidence_score_delta": None,
                    "priority_change": "NEW",
                    "evolution_status": "NEW",
                }
            )
        return pd.DataFrame(rows).sort_values(["readiness_today", "asset"], ascending=[False, True], na_position="last").reset_index(drop=True)

    latest = latest.copy()
    previous = previous.copy()
    latest["asset"] = latest["asset"].astype(str).str.upper()
    previous["asset"] = previous["asset"].astype(str).str.upper()

    merged = latest.merge(
        previous[[
            "asset",
            "readiness_pct",
            "research_score",
            "opportunity_score",
            "confidence_score",
            "priority",
        ]],
        on="asset",
        how="outer",
        suffixes=("_today", "_previous"),
        indicator=True,
    )

    rows = []
    for _, row in merged.iterrows():
        asset = row.get("asset")
        new = row["_merge"] == "left_only"
        removed = row["_merge"] == "right_only"

        readiness_today = row.get("readiness_pct_today")
        readiness_previous = row.get("readiness_pct_previous")
        research_today = row.get("research_score_today")
        research_previous = row.get("research_score_previous")
        opp_today = row.get("opportunity_score_today")
        opp_previous = row.get("opportunity_score_previous")
        conf_today = row.get("confidence_score_today")
        conf_previous = row.get("confidence_score_previous")
        pri_today = row.get("priority_today")
        pri_previous = row.get("priority_previous")

        readiness_delta = None
        if pd.notna(readiness_today) and pd.notna(readiness_previous):
            readiness_delta = float(readiness_today) - float(readiness_previous)

        rows.append(
            {
                "asset": asset,
                "readiness_today": readiness_today if pd.notna(readiness_today) else None,
                "readiness_previous": readiness_previous if pd.notna(readiness_previous) else None,
                "readiness_delta": round(readiness_delta, 4) if readiness_delta is not None else None,
                "research_score_delta": round(float(research_today) - float(research_previous), 4) if pd.notna(research_today) and pd.notna(research_previous) else None,
                "opportunity_score_delta": round(float(opp_today) - float(opp_previous), 4) if pd.notna(opp_today) and pd.notna(opp_previous) else None,
                "confidence_score_delta": round(float(conf_today) - float(conf_previous), 4) if pd.notna(conf_today) and pd.notna(conf_previous) else None,
                "priority_change": (
                    "NEW"
                    if new
                    else "REMOVED"
                    if removed
                    else f"{pri_previous} -> {pri_today}"
                ),
                "evolution_status": _evolution_status(readiness_delta, new, removed),
            }
        )

    report = pd.DataFrame(rows)
    if report.empty:
        return report

    report = report.sort_values(
        ["evolution_status", "readiness_delta", "readiness_today", "asset"],
        ascending=[True, False, False, True],
        na_position="last",
    ).reset_index(drop=True)
    return report


def render_markdown(report: pd.DataFrame, latest_path: Path | None, prev_path: Path | None) -> str:
    lines = [
        "# Research Evolution Engine",
        "",
        f"Date: {TODAY}",
        "",
        f"Latest snapshot: {latest_path.name if latest_path else 'None'}",
        f"Previous snapshot: {prev_path.name if prev_path else 'None'}",
        "",
        "## Top Improving",
        "",
    ]

    if report.empty:
        lines.append("No trade candidate snapshots available.")
        lines.append("")
        return "\n".join(lines)

    improving = report[report["evolution_status"] == "IMPROVING"].sort_values(["readiness_delta", "readiness_today"], ascending=[False, False])
    deteriorating = report[report["evolution_status"] == "DETERIORATING"].sort_values(["readiness_delta", "readiness_today"], ascending=[True, False])
    stable_high = report[(report["evolution_status"] == "STABLE") & (report["readiness_today"].fillna(0) >= 50)].sort_values(["readiness_today", "research_score_delta"], ascending=[False, False])

    if improving.empty:
        lines.append("No improving setups.")
    else:
        for _, row in improving.head(10).iterrows():
            lines.append(
                f"- {row['asset']} | readiness delta {row['readiness_delta']} | research delta {row['research_score_delta']} | opp delta {row['opportunity_score_delta']} | conf delta {row['confidence_score_delta']} | {row['evolution_status']}"
            )

    lines += ["", "## Top Deteriorating", ""]
    if deteriorating.empty:
        lines.append("No deteriorating setups.")
    else:
        for _, row in deteriorating.head(10).iterrows():
            lines.append(
                f"- {row['asset']} | readiness delta {row['readiness_delta']} | research delta {row['research_score_delta']} | opp delta {row['opportunity_score_delta']} | conf delta {row['confidence_score_delta']} | {row['evolution_status']}"
            )

    lines += ["", "## Stable High-Readiness Assets", ""]
    if stable_high.empty:
        lines.append("No stable high-readiness assets.")
    else:
        for _, row in stable_high.head(10).iterrows():
            lines.append(
                f"- {row['asset']} | readiness {row['readiness_today']} | research {row['readiness_delta']} | priority {row['priority_change']}"
            )

    lines += ["", "## Research Note", "", "Evolution compares the latest candidate dashboard against the previous available snapshot. NEW and REMOVED assets are tracked explicitly. ", ""]
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    latest_path, prev_path = _latest_two("*_trade_candidate_dashboard.csv")
    report = build_evolution()
    report.to_csv(OUT_CSV, index=False)
    OUT_MD.write_text(render_markdown(report, latest_path, prev_path))
    print(f"Saved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")
    if not report.empty:
        print(report.to_string(index=False))
    else:
        print("No trade candidate snapshots available.")


if __name__ == "__main__":
    main()
