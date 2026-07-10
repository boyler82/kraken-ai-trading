from __future__ import annotations

from pathlib import Path
import glob

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "DAILY_REPORTS"
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")

CURRENT_OPPORTUNITY = REPORT_DIR / f"{TODAY}_crypto_opportunity_ranking.csv"
CURRENT_UNIVERSAL = REPORT_DIR / f"{TODAY}_universal_market_scanner.csv"
OUT_CSV = REPORT_DIR / f"{TODAY}_research_score.csv"
OUT_MD = REPORT_DIR / f"{TODAY}_research_score.md"


def _latest_file(pattern: str, current: Path) -> Path:
    if current.exists():
        return current
    files = sorted(glob.glob(str(REPORT_DIR / pattern)))
    if not files:
        raise FileNotFoundError(f"No files found for pattern: {pattern}")
    return Path(files[-1])


def _to_float(value):
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _scale(value: float | None, thresholds: list[tuple[float, float]]) -> float:
    if value is None:
        return 0.0
    score = 0.0
    for threshold, points in thresholds:
        if value >= threshold:
            score = points
            break
    return score


def _expected_value_score(ev: float | None) -> float:
    if ev is None:
        return 0.0
    if ev >= 2.0:
        return 100.0
    if ev >= 1.5:
        return 85.0
    if ev >= 1.0:
        return 70.0
    if ev >= 0.5:
        return 45.0
    if ev > 0:
        return 25.0
    return 0.0


def _profit_factor_score(pf: float | None) -> float:
    if pf is None:
        return 0.0
    if pf >= 2.0:
        return 100.0
    if pf >= 1.8:
        return 90.0
    if pf >= 1.5:
        return 75.0
    if pf >= 1.2:
        return 50.0
    if pf >= 1.0:
        return 25.0
    return 0.0


def _win_rate_score(wr: float | None) -> float:
    if wr is None:
        return 0.0
    if wr >= 60:
        return 100.0
    if wr >= 55:
        return 85.0
    if wr >= 50:
        return 70.0
    if wr >= 45:
        return 45.0
    if wr > 0:
        return 25.0
    return 0.0


def _opportunity_score(score: float | None) -> float:
    if score is None:
        return 0.0
    return max(0.0, min(100.0, score))


def _confidence_score(score: float | None) -> float:
    if score is None:
        return 0.0
    return max(0.0, min(100.0, score))


def _market_bias_score(value: str | None) -> float:
    bias = str(value or "").upper()
    if bias in {"BULL", "BULL_HIGH_VOL"}:
        return 100.0
    if bias in {"BULL_NEUTRAL", "NEUTRAL", "RISK_ON"}:
        return 75.0
    if bias in {"BEAR", "BEAR_HIGH_VOL"}:
        return 35.0
    if bias:
        return 50.0
    return 0.0


def _atr_score(atr_pct: float | None) -> float:
    if atr_pct is None:
        return 0.0
    if atr_pct <= 3:
        return 100.0
    if atr_pct <= 5:
        return 80.0
    if atr_pct <= 8:
        return 55.0
    if atr_pct <= 12:
        return 30.0
    return 15.0


def _status(score: float) -> str:
    if score >= 95:
        return "STRONG_BUY_RESEARCH"
    if score >= 85:
        return "READY_FOR_REVIEW"
    if score >= 70:
        return "WATCH"
    if score >= 50:
        return "WAIT"
    return "IGNORE"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    opp_path = _latest_file("*_crypto_opportunity_ranking.csv", CURRENT_OPPORTUNITY)
    uni_path = _latest_file("*_universal_market_scanner.csv", CURRENT_UNIVERSAL)
    opp = pd.read_csv(opp_path)
    uni = pd.read_csv(uni_path)
    return opp, uni


def build_research_score() -> pd.DataFrame:
    opp, uni = load_inputs()

    opp_cols = {
        "asset",
        "expected_value_pct",
        "profit_factor",
        "win_rate_pct",
        "opportunity_score",
        "confidence_score",
        "market_bias",
        "atr_pct",
        "current_phase",
        "recommendation",
        "bucket",
    }
    uni_cols = {
        "asset",
        "close",
        "rsi2",
        "ma20",
        "ma200",
        "dist_ma20_pct",
        "atr_pct",
        "market_bias",
        "current_phase",
        "recommendation",
        "opportunity_score",
        "confidence_score",
    }

    opp = opp[[c for c in opp.columns if c in opp_cols]].copy()
    uni = uni[[c for c in uni.columns if c in uni_cols]].copy()

    merged = pd.merge(uni, opp, on="asset", how="outer", suffixes=("_uni", "_opp"))

    rows = []
    for _, row in merged.iterrows():
        asset = row.get("asset")
        expected_value = _to_float(row.get("expected_value_pct"))
        profit_factor = _to_float(row.get("profit_factor"))
        win_rate = _to_float(row.get("win_rate_pct"))
        opp_score_raw = _to_float(row.get("opportunity_score_opp"))
        if opp_score_raw is None:
            opp_score_raw = _to_float(row.get("opportunity_score_uni"))
        conf_score_raw = _to_float(row.get("confidence_score_opp"))
        if conf_score_raw is None:
            conf_score_raw = _to_float(row.get("confidence_score_uni"))
        market_bias = row.get("market_bias_opp")
        if pd.isna(market_bias) or market_bias in (None, ""):
            market_bias = row.get("market_bias_uni")
        atr_pct = _to_float(row.get("atr_pct_opp"))
        if atr_pct is None:
            atr_pct = _to_float(row.get("atr_pct_uni"))

        ev_score = _expected_value_score(expected_value)
        pf_score = _profit_factor_score(profit_factor)
        wr_score = _win_rate_score(win_rate)
        opp_score = _opportunity_score(opp_score_raw)
        conf_score = _confidence_score(conf_score_raw)
        bias_score = _market_bias_score(market_bias)
        atr_score = _atr_score(atr_pct)

        research_score = (
            ev_score * 0.25
            + pf_score * 0.20
            + wr_score * 0.15
            + opp_score * 0.15
            + conf_score * 0.10
            + bias_score * 0.10
            + atr_score * 0.05
        )

        rows.append(
            {
                "asset": asset,
                "research_score": round(research_score, 2),
                "status": _status(research_score),
                "expected_value_pct": expected_value,
                "expected_value_score": round(ev_score, 2),
                "profit_factor": profit_factor,
                "profit_factor_score": round(pf_score, 2),
                "win_rate_pct": win_rate,
                "win_rate_score": round(wr_score, 2),
                "opportunity_score": opp_score_raw,
                "opportunity_score_component": round(opp_score, 2),
                "confidence_score": conf_score_raw,
                "confidence_score_component": round(conf_score, 2),
                "market_bias": market_bias,
                "market_bias_score": round(bias_score, 2),
                "atr_pct": atr_pct,
                "atr_score": round(atr_score, 2),
                "current_phase": row.get("current_phase_opp") if pd.notna(row.get("current_phase_opp")) else row.get("current_phase_uni"),
                "recommendation": row.get("recommendation_opp") if pd.notna(row.get("recommendation_opp")) else row.get("recommendation_uni"),
                "bucket": row.get("bucket"),
            }
        )

    report = pd.DataFrame(rows)
    if report.empty:
        return report

    report = report.sort_values(["research_score", "asset"], ascending=[False, True]).reset_index(drop=True)
    report.insert(0, "rank", range(1, len(report) + 1))
    return report[
        [
            "rank",
            "asset",
            "research_score",
            "status",
            "expected_value_pct",
            "expected_value_score",
            "profit_factor",
            "profit_factor_score",
            "win_rate_pct",
            "win_rate_score",
            "opportunity_score",
            "opportunity_score_component",
            "confidence_score",
            "confidence_score_component",
            "market_bias",
            "market_bias_score",
            "atr_pct",
            "atr_score",
            "current_phase",
            "recommendation",
            "bucket",
        ]
    ]


def render_markdown(report: pd.DataFrame) -> str:
    lines = [
        "# Research Score Engine",
        "",
        f"Date: {TODAY}",
        "",
        "Research only. No strategy changes. No pipeline changes.",
        "",
        "## Ranked Assets",
        "",
    ]

    if report.empty:
        lines.append("No assets found.")
        return "\n".join(lines)

    for _, row in report.iterrows():
        lines.append(
            f"- #{int(row['rank'])} {row['asset']} | score {row['research_score']} | {row['status']} | EV {row['expected_value_pct']} | PF {row['profit_factor']} | WR {row['win_rate_pct']} | Opp {row['opportunity_score']} | Conf {row['confidence_score']} | Bias {row['market_bias']} | ATR {row['atr_pct']}"
        )

    lines += [
        "",
        "## Status Bands",
        "",
        "- 95-100 = STRONG_BUY_RESEARCH",
        "- 85-94 = READY_FOR_REVIEW",
        "- 70-84 = WATCH",
        "- 50-69 = WAIT",
        "- <50 = IGNORE",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = build_research_score()
    report.to_csv(OUT_CSV, index=False)
    OUT_MD.write_text(render_markdown(report))
    print(f"Saved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")
    if not report.empty:
        print(report.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
