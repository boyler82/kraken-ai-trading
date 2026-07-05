from __future__ import annotations

from pathlib import Path
import glob

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "DAILY_REPORTS"
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")
OUT_CSV = REPORT_DIR / f"{TODAY}_research_consensus.csv"
OUT_MD = REPORT_DIR / f"{TODAY}_research_consensus.md"


def _latest(pattern: str) -> Path | None:
    files = sorted(glob.glob(str(REPORT_DIR / pattern)))
    return Path(files[-1]) if files else None


def _load(pattern: str) -> pd.DataFrame:
    path = _latest(pattern)
    if path is None:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _to_float(value):
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_regime_status() -> str:
    regime = _load("*_research_regime.csv")
    if regime.empty or "metric" not in regime.columns or "value" not in regime.columns:
        return "UNKNOWN"
    lookup = {str(r["metric"]): r["value"] for _, r in regime.iterrows()}
    return str(lookup.get("environment_status", "UNKNOWN"))


def _status_rank(status: str | None) -> int:
    order = {"HIGH_CONVICTION": 3, "MEDIUM_CONVICTION": 2, "LOW_CONVICTION": 1, "IGNORE": 0}
    return order.get(str(status).upper(), -1)


def build_consensus() -> pd.DataFrame:
    trade = _load("*_trade_candidate_dashboard.csv")
    research = _load("*_research_score.csv")
    explain = _load("*_research_explainability.csv")
    evolution = _load("*_research_evolution.csv")
    timeline = _load("*_research_timeline.csv")
    regime = _load("*_research_regime.csv")

    if trade.empty:
        return pd.DataFrame(columns=[
            "asset",
            "readiness_pct",
            "research_score",
            "priority",
            "regime_status",
            "timeline_trend",
            "evolution_status",
            "positive_factors",
            "blocking_conditions",
            "consensus_points",
            "max_points",
            "consensus_pct",
            "consensus_status",
            "final_note",
        ])

    trade = trade.copy()
    trade["asset"] = trade["asset"].astype(str).str.upper()

    research_map = {}
    if not research.empty and "asset" in research.columns:
        research = research.copy()
        research["asset"] = research["asset"].astype(str).str.upper()
        research_map = {r["asset"]: r.to_dict() for _, r in research.iterrows()}

    explain_map = {}
    if not explain.empty and "asset" in explain.columns:
        explain = explain.copy()
        explain["asset"] = explain["asset"].astype(str).str.upper()
        explain_map = {r["asset"]: r.to_dict() for _, r in explain.iterrows()}

    evo_map = {}
    if not evolution.empty and "asset" in evolution.columns:
        evolution = evolution.copy()
        evolution["asset"] = evolution["asset"].astype(str).str.upper()
        evo_map = {r["asset"]: r.to_dict() for _, r in evolution.iterrows()}

    time_map = {}
    if not timeline.empty and "asset" in timeline.columns:
        timeline = timeline.copy()
        timeline["asset"] = timeline["asset"].astype(str).str.upper()
        time_map = {r["asset"]: r.to_dict() for _, r in timeline.iterrows()}

    regime_status = _load_regime_status()

    rows = []
    for _, row in trade.iterrows():
        asset = str(row.get("asset", "")).upper()
        research_row = research_map.get(asset, {})
        explain_row = explain_map.get(asset, {})
        evo_row = evo_map.get(asset, {})
        time_row = time_map.get(asset, {})

        readiness = _to_float(row.get("readiness_pct"))
        research_score = _to_float(row.get("research_score"))
        priority = row.get("priority")
        timeline_trend = time_row.get("trend_status") if time_row else None
        evolution_status = evo_row.get("evolution_status") if evo_row else None
        positive_factors = explain_row.get("positive_factors")
        blocking_conditions = explain_row.get("blocking_conditions")

        points = 0
        if readiness is not None and readiness >= 50:
            points += 1
        if research_score is not None and research_score >= 70:
            points += 1
        if str(priority).upper() in {"MEDIUM", "HIGH", "CRITICAL"}:
            points += 1
        if str(timeline_trend).upper() != "FALLING":
            points += 1
        if str(evolution_status).upper() != "DETERIORATING":
            points += 1
        if regime_status != "DEFENSIVE":
            points += 1
        if "No active signal" in str(blocking_conditions):
            points += 0
        else:
            points += 1

        max_points = 7
        consensus_pct = round(points / max_points * 100, 2)
        has_process_blockers = any(
            blocker in str(blocking_conditions)
            for blocker in ["Waiting for Day2/Day3", "Waiting for BULL market"]
        )
        if consensus_pct >= 85 and not has_process_blockers:
            consensus_status = "HIGH_CONVICTION"
        elif consensus_pct >= 85 and has_process_blockers:
            consensus_status = "MEDIUM_CONVICTION_WATCH"
        elif consensus_pct >= 70:
            consensus_status = "MEDIUM_CONVICTION"
        elif consensus_pct >= 50:
            consensus_status = "LOW_CONVICTION"
        else:
            consensus_status = "IGNORE"

        note_parts = []
        if consensus_pct >= 85 and has_process_blockers:
            note_parts.append("High agreement, but still blocked by process conditions.")
        elif consensus_status in {"HIGH_CONVICTION", "MEDIUM_CONVICTION"}:
            note_parts.append("Aligned across multiple research modules")
        elif consensus_status == "LOW_CONVICTION":
            note_parts.append("Partial agreement with active blockers")
        else:
            note_parts.append("Weak consensus")
        if str(evolution_status).upper() == "NEW":
            note_parts.append("new setup")
        if str(timeline_trend).upper() == "RISING":
            note_parts.append("trend improving")
        if str(timeline_trend).upper() == "FALLING":
            note_parts.append("trend weakening")

        rows.append(
            {
                "asset": asset,
                "readiness_pct": readiness,
                "research_score": research_score,
                "priority": priority,
                "regime_status": regime_status,
                "timeline_trend": timeline_trend,
                "evolution_status": evolution_status,
                "positive_factors": positive_factors,
                "blocking_conditions": blocking_conditions,
                "consensus_points": points,
                "max_points": max_points,
                "consensus_pct": consensus_pct,
                "consensus_status": consensus_status,
                "final_note": "; ".join(note_parts),
            }
        )

    report = pd.DataFrame(rows)
    if report.empty:
        return report

    report = report.sort_values(
        ["consensus_pct", "readiness_pct", "research_score", "asset"],
        ascending=[False, False, False, True],
        na_position="last",
    ).reset_index(drop=True)
    return report


def render_markdown(report: pd.DataFrame) -> str:
    regime_status = _load_regime_status()
    lines = [
        "# Research Consensus Engine",
        "",
        f"Date: {TODAY}",
        "",
        f"Environment status: {regime_status}",
        "",
        "## Top Consensus Candidates",
        "",
    ]
    if report.empty:
        lines.append("No consensus data available.")
    else:
        top = report[report["consensus_status"].astype(str).str.contains("HIGH_CONVICTION|MEDIUM_CONVICTION", na=False)].head(10)
        if top.empty:
            lines.append("No high or medium conviction candidates.")
        else:
            for _, row in top.iterrows():
                lines.append(
                    f"- {row['asset']} | consensus {row['consensus_pct']} | status {row['consensus_status']} | readiness {row['readiness_pct']} | research {row['research_score']} | priority {row['priority']} | note {row['final_note']}"
                )
    lines += ["", "## Low Consensus / Ignore", ""]
    if report.empty:
        lines.append("No consensus data available.")
    else:
        low = report[report["consensus_status"].isin(["LOW_CONVICTION", "IGNORE"])]
        if low.empty:
            lines.append("No low consensus assets.")
        else:
            for _, row in low.iterrows():
                lines.append(
                    f"- {row['asset']} | consensus {row['consensus_pct']} | status {row['consensus_status']} | readiness {row['readiness_pct']} | research {row['research_score']} | priority {row['priority']} | note {row['final_note']}"
                )
    lines += ["", "## Research Note", "", "Consensus aggregates readiness, research score, evolution, timeline, and regime context. It is a research overlay only.", ""]
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = build_consensus()
    report.to_csv(OUT_CSV, index=False)
    OUT_MD.write_text(render_markdown(report))
    print(f"Saved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")
    if not report.empty:
        print(report.to_string(index=False))
    else:
        print("No consensus data available.")


if __name__ == "__main__":
    main()
