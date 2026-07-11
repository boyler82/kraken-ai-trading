from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "DAILY_REPORTS"
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")
OUT_CSV = REPORT_DIR / f"{TODAY}_trade_candidate_dashboard.csv"
OUT_MD = REPORT_DIR / f"{TODAY}_trade_candidate_dashboard.md"


def _load_today(suffix: str) -> pd.DataFrame:
    """Load only the report for TODAY; never carry an older signal forward."""
    path = REPORT_DIR / f"{TODAY}_{suffix}.csv"
    if not path.exists():
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


def _priority(readiness_pct: float) -> str:
    if readiness_pct >= 90:
        return "CRITICAL"
    if readiness_pct >= 75:
        return "HIGH"
    if readiness_pct >= 50:
        return "MEDIUM"
    if readiness_pct >= 25:
        return "LOW"
    return "IGNORE"


def _current_setup_status(row: dict) -> str:
    freshness = str(row.get("data_freshness_status", "FRESH")).upper()
    if freshness and freshness not in {"FRESH", "NAN", "NONE"}:
        return "STALE_DATA"

    rec = str(row.get("recommendation", "")).upper()
    phase = str(row.get("current_phase", "")).upper()
    if rec in {"DAY2_ENTRY", "DAY3_ENTRY", "ENTRY_READY", "BUY", "BUY_NOW"}:
        return "ACTIONABLE"
    if rec == "HISTORICALLY_STRONG_NO_SIGNAL" or row.get("historically_strong_no_signal"):
        return "HISTORICAL_ONLY"
    if rec in {"NO_ACTION", "NO_SIGNAL", ""} or phase in {"NO_SIGNAL", "NO_OVERSOLD"}:
        return "NO_SETUP"
    if "OVERSOLD" in phase or "DAY1" in rec or "DAY2" in rec or "DAY3" in rec:
        return "DEVELOPING"
    return "NO_SETUP"


def _watch_status(row: dict) -> str:
    setup_status = str(row.get("current_setup_status", "")).upper()
    if setup_status in {"NO_SETUP", "HISTORICAL_ONLY", "STALE_DATA"}:
        return setup_status
    if row.get("watch_status"):
        return str(row["watch_status"])
    if str(row.get("bucket", "")).upper() == "ACTIVE_OPPORTUNITY":
        return "ACTIVE_OPPORTUNITY"
    rec = str(row.get("recommendation", "")).upper()
    if "WATCH" in rec:
        return "WATCHLIST"
    if "DAY" in rec:
        return "REVIEW"
    return "UNKNOWN"


def _missing_conditions(row: dict, readiness_pct: float) -> str:
    if str(row.get("current_setup_status", "")).upper() == "HISTORICAL_ONLY":
        return "Waiting for current signal"
    conditions = []
    if str(row.get("bucket", "")).upper() != "ACTIVE_OPPORTUNITY":
        conditions.append("Waiting for signal")
    if "DAY2" in str(row.get("recommendation", "")).upper():
        conditions.append("Waiting for Day 2")
    if "DAY3" in str(row.get("recommendation", "")).upper():
        conditions.append("Waiting for Day 3")
    if _to_float(row.get("confidence_score")) is not None and _to_float(row.get("confidence_score")) <= 70:
        conditions.append("Waiting for confidence > 70")
    if _to_float(row.get("research_score")) is not None and _to_float(row.get("research_score")) <= 70:
        conditions.append("No historical edge")
    mb = str(row.get("market_bias", "")).upper()
    if mb and mb != "BULL":
        conditions.append("Waiting for bull trend")
    if not conditions:
        return "Ready"
    # keep a compact, human-readable list
    uniq = []
    for c in conditions:
        if c not in uniq:
            uniq.append(c)
    return "; ".join(uniq)


def _readiness_pct(row: dict) -> float:
    status = str(row.get("current_setup_status", "NO_SETUP"))
    if status in {"HISTORICAL_ONLY", "NO_SETUP", "STALE_DATA"}:
        return 0.0
    score = 0.0
    if str(row.get("bucket", "")).upper() == "ACTIVE_OPPORTUNITY":
        score += 30
    rec = str(row.get("recommendation", "")).upper()
    if "DAY2" in rec or "DAY3" in rec:
        score += 20
    conf = _to_float(row.get("confidence_score"))
    if conf is not None and conf > 70:
        score += 20
    research = _to_float(row.get("research_score"))
    if research is not None and research > 70:
        score += 15
    if str(row.get("market_bias", "")).upper() == "BULL":
        score += 15
    return min(score, 100.0)


def build_dashboard() -> pd.DataFrame:
    crypto = _load_today("crypto_opportunity_ranking")
    universal = _load_today("universal_market_scanner")
    research = _load_today("research_score")

    sources = []
    if not crypto.empty:
        c = crypto.copy()
        c["source"] = "crypto"
        sources.append(c)
    if not universal.empty:
        u = universal.copy()
        u["source"] = "universal"
        sources.append(u)
    if not research.empty:
        r = research.copy()
        r["source"] = "research"
        sources.append(r)

    if not sources:
        return pd.DataFrame(columns=[
            "asset", "asset_class", "research_score", "opportunity_score", "confidence_score", "recommendation", "current_phase", "market_bias", "expected_value_pct", "profit_factor", "watch_status", "current_setup_status", "readiness_pct", "missing_conditions", "priority"
        ])

    assets = sorted(set().union(*[set(df["asset"].astype(str).str.upper()) for df in sources if "asset" in df.columns]))
    rows = []
    for asset in assets:
        row: dict[str, object] = {"asset": asset}
        # Historical metrics may come from research, but current state is applied below.
        for df in [research, crypto, universal]:
            if df.empty or "asset" not in df.columns:
                continue
            hit = df[df["asset"].astype(str).str.upper() == asset]
            if hit.empty:
                continue
            src = hit.iloc[0].to_dict()
            if "asset_class" in src and pd.notna(src.get("asset_class")):
                row["asset_class"] = src.get("asset_class")
            if pd.isna(row.get("research_score")) and "research_score" in src:
                row["research_score"] = _to_float(src.get("research_score"))
            if pd.isna(row.get("opportunity_score")) and "opportunity_score" in src:
                row["opportunity_score"] = _to_float(src.get("opportunity_score"))
            if pd.isna(row.get("confidence_score")) and "confidence_score" in src:
                row["confidence_score"] = _to_float(src.get("confidence_score"))
            if pd.isna(row.get("recommendation")) and "recommendation" in src:
                row["recommendation"] = src.get("recommendation")
            if pd.isna(row.get("current_phase")) and "current_phase" in src:
                row["current_phase"] = src.get("current_phase")
            if pd.isna(row.get("market_bias")) and "market_bias" in src:
                row["market_bias"] = src.get("market_bias")
            if pd.isna(row.get("expected_value_pct")) and "expected_value_pct" in src:
                row["expected_value_pct"] = _to_float(src.get("expected_value_pct"))
            if pd.isna(row.get("profit_factor")) and "profit_factor" in src:
                row["profit_factor"] = _to_float(src.get("profit_factor"))
            if "bucket" in src and pd.notna(src.get("bucket")):
                row["bucket"] = src.get("bucket")

        # The universal scanner is authoritative when it explicitly reports no
        # current setup. Otherwise the richer same-day crypto state may be used.
        scanner_hit = universal[universal["asset"].astype(str).str.upper() == asset] if not universal.empty and "asset" in universal.columns else pd.DataFrame()
        crypto_hit = crypto[crypto["asset"].astype(str).str.upper() == asset] if not crypto.empty and "asset" in crypto.columns else pd.DataFrame()
        scanner = scanner_hit.iloc[0].to_dict() if not scanner_hit.empty else {}
        crypto_now = crypto_hit.iloc[0].to_dict() if not crypto_hit.empty else {}
        research_hit = research[research["asset"].astype(str).str.upper() == asset] if not research.empty and "asset" in research.columns else pd.DataFrame()
        research_now = research_hit.iloc[0].to_dict() if not research_hit.empty else {}
        row["historically_strong_no_signal"] = str(research_now.get("recommendation", "")).upper() == "HISTORICALLY_STRONG_NO_SIGNAL"
        scanner_rec = str(scanner.get("recommendation", "")).upper()
        scanner_phase = str(scanner.get("current_phase", "")).upper()
        current = scanner if scanner_rec in {"NO_ACTION", "NO_SIGNAL"} or scanner_phase == "NO_SIGNAL" else (crypto_now or scanner)
        for key in ["recommendation", "current_phase", "market_bias", "opportunity_score", "confidence_score", "bucket"]:
            if key in current and pd.notna(current.get(key)):
                row[key] = current.get(key)
        if scanner and pd.notna(scanner.get("data_freshness_status")):
            row["data_freshness_status"] = scanner.get("data_freshness_status")

        row.setdefault("asset_class", "unknown")
        row.setdefault("research_score", None)
        row.setdefault("opportunity_score", None)
        row.setdefault("confidence_score", None)
        row.setdefault("recommendation", None)
        row.setdefault("current_phase", None)
        row.setdefault("market_bias", None)
        row.setdefault("expected_value_pct", None)
        row.setdefault("profit_factor", None)
        row.setdefault("bucket", None)
        row.setdefault("data_freshness_status", None)

        row["current_setup_status"] = _current_setup_status(row)

        readiness_pct = _readiness_pct(row)
        row["readiness_pct"] = round(readiness_pct, 2)
        row["priority"] = _priority(readiness_pct)
        row["watch_status"] = _watch_status(row)
        row["missing_conditions"] = _missing_conditions(row, readiness_pct)
        rows.append(row)

    report = pd.DataFrame(rows)
    if report.empty:
        return report

    for col in ["research_score", "opportunity_score", "confidence_score", "expected_value_pct", "profit_factor"]:
        if col in report.columns:
            report[col] = pd.to_numeric(report[col], errors="coerce")

    report = report.sort_values(
        ["readiness_pct", "research_score", "expected_value_pct", "confidence_score"],
        ascending=[False, False, False, False],
        na_position="last",
    ).reset_index(drop=True)
    return report[
        [
            "asset",
            "asset_class",
            "research_score",
            "opportunity_score",
            "confidence_score",
            "recommendation",
            "current_phase",
            "market_bias",
            "expected_value_pct",
            "profit_factor",
            "watch_status",
            "current_setup_status",
            "readiness_pct",
            "missing_conditions",
            "priority",
        ]
    ]


def render_markdown(report: pd.DataFrame) -> str:
    lines = [
        "# Trade Candidate Dashboard",
        "",
        f"Date: {TODAY}",
        "",
        "Research only. No execution logic.",
        "",
        "## Top Candidates",
        "",
    ]
    if report.empty:
        lines.append("No candidates available.")
    else:
        for _, row in report.iterrows():
            lines.append(
                f"- {row['asset']} | setup {row['current_setup_status']} | class {row['asset_class']} | readiness {row['readiness_pct']} | priority {row['priority']} | research {row['research_score']} | opp {row['opportunity_score']} | conf {row['confidence_score']} | rec {row['recommendation']} | phase {row['current_phase']} | bias {row['market_bias']} | ev {row['expected_value_pct']} | pf {row['profit_factor']} | watch {row['watch_status']} | missing {row['missing_conditions']}"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = build_dashboard()
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
