from __future__ import annotations

from pathlib import Path
import glob

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "DAILY_REPORTS"
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")
OUT_CSV = REPORT_DIR / f"{TODAY}_research_explainability.csv"
OUT_MD = REPORT_DIR / f"{TODAY}_research_explainability.md"


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


def _as_list_text(items: list[str]) -> str:
    uniq = []
    for item in items:
        if item and item not in uniq:
            uniq.append(item)
    return "; ".join(uniq) if uniq else "None"


def _positive_factors(row: dict) -> list[str]:
    factors = []
    if str(row.get("watch_status", "")).upper() == "ACTIVE_OPPORTUNITY":
        factors.append("ACTIVE_OPPORTUNITY")
    conf = _to_float(row.get("confidence_score"))
    if conf is not None and conf >= 70:
        factors.append("confidence >= 70")
    research = _to_float(row.get("research_score"))
    if research is not None and research >= 70:
        factors.append("research_score >= 70")
    pf = _to_float(row.get("profit_factor"))
    if pf is not None and pf >= 1.5:
        factors.append("profit_factor >= 1.5")
    ev = _to_float(row.get("expected_value_pct"))
    if ev is not None and ev > 1:
        factors.append("expected_value_pct > 1")
    if str(row.get("market_bias", "")).upper() == "BULL":
        factors.append("market_bias BULL")
    return factors


def _negative_factors(row: dict) -> list[str]:
    factors = []
    mb = str(row.get("market_bias", "")).upper()
    if mb and mb != "BULL":
        factors.append(f"market_bias {mb}")
    conf = _to_float(row.get("confidence_score"))
    if conf is not None and conf < 70:
        factors.append("confidence < 70")
    research = _to_float(row.get("research_score"))
    if research is not None and research < 70:
        factors.append("research_score < 70")
    rec = str(row.get("recommendation", "")).upper()
    if rec.endswith("DAY1_OBSERVE_ONLY") or rec == "DAY1_OBSERVE_ONLY":
        factors.append("DAY1 only")
    if not row.get("research_score") or pd.isna(row.get("research_score")):
        factors.append("missing historical edge")
    if str(row.get("watch_status", "")).upper() != "ACTIVE_OPPORTUNITY":
        factors.append("no active signal")
    return factors


def _blocking_conditions(row: dict) -> list[str]:
    blocks = []
    rec = str(row.get("recommendation", "")).upper()
    if "DAY2" in rec or "DAY3" in rec:
        blocks.append("Waiting for Day2/Day3")
    elif rec == "DAY1_OBSERVE_ONLY":
        blocks.append("Waiting for Day2/Day3")
    conf = _to_float(row.get("confidence_score"))
    if conf is not None and conf < 70:
        blocks.append("Waiting for confidence >= 70")
    if str(row.get("market_bias", "")).upper() != "BULL":
        blocks.append("Waiting for BULL market")
    if row.get("research_score") is None or pd.isna(row.get("research_score")):
        blocks.append("Missing historical edge")
    if str(row.get("watch_status", "")).upper() != "ACTIVE_OPPORTUNITY":
        blocks.append("No active signal")
    return blocks


def _summary(row: dict, blocks: list[str], positives: list[str], negatives: list[str]) -> str:
    if not positives and blocks:
        return f"{row.get('asset')} is not ready: " + ", ".join(blocks[:3])
    if blocks:
        return f"{row.get('asset')} has partial readiness with blockers: " + ", ".join(blocks[:2])
    return f"{row.get('asset')} is ready."


def build_explainability() -> pd.DataFrame:
    candidates = _load("*_trade_candidate_dashboard.csv")
    research = _load("*_research_score.csv")
    crypto = _load("*_crypto_opportunity_ranking.csv")
    universal = _load("*_universal_market_scanner.csv")

    if candidates.empty:
        return pd.DataFrame(columns=[
            "asset",
            "readiness_pct",
            "priority",
            "research_score",
            "recommendation",
            "current_phase",
            "positive_factors",
            "negative_factors",
            "blocking_conditions",
            "explanation_summary",
        ])

    research_map = {}
    if not research.empty and "asset" in research.columns:
        for _, row in research.iterrows():
            research_map[str(row["asset"]).upper()] = row.to_dict()

    rows = []
    for _, cand in candidates.iterrows():
        asset = str(cand.get("asset", "")).upper()
        combined = cand.to_dict()

        for source in [crypto, universal]:
            if source.empty or "asset" not in source.columns:
                continue
            hit = source[source["asset"].astype(str).str.upper() == asset]
            if not hit.empty:
                src = hit.iloc[0].to_dict()
                for key in ["recommendation", "current_phase", "market_bias", "expected_value_pct", "profit_factor", "opportunity_score", "confidence_score"]:
                    if pd.isna(combined.get(key)) and key in src:
                        combined[key] = src.get(key)
                if pd.isna(combined.get("asset_class")) and "asset_class" in src:
                    combined["asset_class"] = src.get("asset_class")

        if asset in research_map:
            src = research_map[asset]
            combined["research_score"] = src.get("research_score")
            if pd.isna(combined.get("recommendation")):
                combined["recommendation"] = src.get("recommendation")
            if pd.isna(combined.get("current_phase")):
                combined["current_phase"] = src.get("current_phase")
            if pd.isna(combined.get("market_bias")):
                combined["market_bias"] = src.get("market_bias")
            if pd.isna(combined.get("expected_value_pct")):
                combined["expected_value_pct"] = src.get("expected_value_pct")
            if pd.isna(combined.get("profit_factor")):
                combined["profit_factor"] = src.get("profit_factor")

        pos = _positive_factors(combined)
        neg = _negative_factors(combined)
        blocks = _blocking_conditions(combined)
        rows.append(
            {
                "asset": asset,
                "readiness_pct": _to_float(combined.get("readiness_pct")),
                "priority": combined.get("priority"),
                "research_score": _to_float(combined.get("research_score")),
                "recommendation": combined.get("recommendation"),
                "current_phase": combined.get("current_phase"),
                "positive_factors": _as_list_text(pos),
                "negative_factors": _as_list_text(neg),
                "blocking_conditions": _as_list_text(blocks),
                "explanation_summary": _summary(combined, blocks, pos, neg),
            }
        )

    report = pd.DataFrame(rows)
    if report.empty:
        return report

    report = report.sort_values(["readiness_pct", "research_score", "asset"], ascending=[False, False, True], na_position="last").reset_index(drop=True)
    return report


def render_markdown(report: pd.DataFrame) -> str:
    lines = [
        "# Research Explainability Engine",
        "",
        f"Date: {TODAY}",
        "",
        "## Top Explanations",
        "",
    ]
    if report.empty:
        lines.append("No candidates available.")
        lines.append("")
        return "\n".join(lines)

    for _, row in report.head(10).iterrows():
        lines.append(
            f"- {row['asset']} | readiness {row['readiness_pct']} | priority {row['priority']} | positives {row['positive_factors']} | negatives {row['negative_factors']} | blockers {row['blocking_conditions']} | {row['explanation_summary']}"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = build_explainability()
    report.to_csv(OUT_CSV, index=False)
    OUT_MD.write_text(render_markdown(report))
    print(f"Saved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")
    if not report.empty:
        print(report.to_string(index=False))
    else:
        print("No candidates available.")


if __name__ == "__main__":
    main()
