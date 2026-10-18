from __future__ import annotations

from pathlib import Path
import glob

import pandas as pd
from lib.universe import report_dir


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = report_dir()
BACKTESTS_DIR = ROOT / "BACKTESTS"
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")
OUT_CSV = REPORT_DIR / f"{TODAY}_research_regime.csv"
OUT_MD = REPORT_DIR / f"{TODAY}_research_regime.md"


def _latest(pattern: str) -> Path | None:
    files = sorted(glob.glob(str(REPORT_DIR / pattern)))
    return Path(files[-1]) if files else None


def _load_csv(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _load_latest(pattern: str) -> pd.DataFrame:
    return _load_csv(_latest(pattern))


def _load_current_or_latest(suffix: str) -> pd.DataFrame:
    current = REPORT_DIR / f"{TODAY}_{suffix}.csv"
    if current.exists():
        return _load_csv(current)
    return _load_latest(f"*_{suffix}.csv")


def _load_backtest_regime() -> pd.DataFrame:
    path = BACKTESTS_DIR / "market_regime.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _majority_bias(df: pd.DataFrame, asset_classes: set[str]) -> str:
    if df.empty or "market_bias" not in df.columns or "asset_class" not in df.columns:
        return "MIXED"
    subset = df[df["asset_class"].astype(str).str.lower().isin({c.lower() for c in asset_classes})]
    if subset.empty:
        return "MIXED"
    bias = subset["market_bias"].astype(str).str.upper()
    bull = int((bias == "BULL").sum())
    bear = int((bias.str.contains("BEAR")).sum())
    if bull > bear:
        return "BULL"
    if bear > bull:
        return "BEAR"
    return "MIXED"


def _bias_counts(df: pd.DataFrame, asset_classes: set[str]) -> tuple[int, int, int]:
    if df.empty or "market_bias" not in df.columns:
        return 0, 0, 0
    subset = df
    if "asset_class" in df.columns:
        subset = df[
            df["asset_class"].astype(str).str.lower().isin(
                {c.lower() for c in asset_classes}
            )
        ]
    bias = subset["market_bias"].astype(str).str.upper()
    bull = int((bias == "BULL").sum())
    bear = int(bias.str.contains("BEAR").sum())
    return bull, bear, int(len(subset) - bull - bear)


def _majority_crypto(df: pd.DataFrame) -> str:
    bull, bear, _ = _bias_counts(df, {"crypto"})
    if bull > bear:
        return "BULL"
    if bear > bull:
        return "BEAR"
    return "MIXED"


def _majority_equity(df: pd.DataFrame) -> str:
    return _majority_bias(df, {"etf", "stock"})


def _volatility_regime(*dfs: pd.DataFrame) -> str:
    atrs = []
    for df in dfs:
        if df.empty or "atr_pct" not in df.columns:
            continue
        atrs.extend(pd.to_numeric(df["atr_pct"], errors="coerce").dropna().tolist())
    if not atrs:
        return "UNKNOWN"
    median_atr = float(pd.Series(atrs).median())
    if median_atr < 3:
        return "LOW"
    if median_atr <= 6:
        return "NORMAL"
    return "HIGH"


def _opportunity_regime(
    crypto: pd.DataFrame,
    universal: pd.DataFrame,
    candidates: pd.DataFrame | None = None,
) -> str:
    count = _current_opportunity_count(crypto, universal, candidates)
    if count >= 3:
        return "ACTIVE"
    if 1 <= count <= 2:
        return "QUIET"
    return "EMPTY"


def _current_opportunity_count(
    crypto: pd.DataFrame,
    universal: pd.DataFrame,
    candidates: pd.DataFrame | None = None,
) -> int:
    """Count current reporting opportunities without changing their source signals."""
    if (
        candidates is not None
        and not candidates.empty
        and {"asset", "current_setup_status"}.issubset(candidates.columns)
    ):
        status = candidates["current_setup_status"].astype(str).str.upper()
        return int(
            candidates.loc[
                status.isin({"ACTIONABLE", "DEVELOPING"}), "asset"
            ]
            .astype(str)
            .str.upper()
            .nunique()
        )

    assets: set[str] = set()
    if not crypto.empty:
        if "bucket" in crypto.columns:
            mask = crypto["bucket"].astype(str).str.upper().isin(
                {"ACTIVE_OPPORTUNITY", "WATCHLIST"}
            )
        elif "recommendation" in crypto.columns:
            rec = crypto["recommendation"].astype(str).str.upper()
            mask = rec.str.contains("DAY", na=False) | rec.isin(
                {"WATCH_CLOSELY", "MANUAL_REVIEW"}
            )
        else:
            mask = pd.Series(False, index=crypto.index)
        if "asset" in crypto.columns:
            assets.update(crypto.loc[mask, "asset"].astype(str).str.upper())

    if not universal.empty and "recommendation" in universal.columns:
        rec = universal["recommendation"].astype(str).str.upper()
        mask = rec.isin({"WATCHLIST", "WATCH_RESEARCH", "ACTIVE_OPPORTUNITY"})
        if "data_freshness_status" in universal.columns:
            mask &= (
                universal["data_freshness_status"]
                .astype(str)
                .str.upper()
                .eq("FRESH")
            )
        if "asset" in universal.columns:
            assets.update(universal.loc[mask, "asset"].astype(str).str.upper())
    return len(assets)


def _median_atr(*dfs: pd.DataFrame) -> float | None:
    values = []
    for df in dfs:
        if not df.empty and "atr_pct" in df.columns:
            values.extend(
                pd.to_numeric(df["atr_pct"], errors="coerce").dropna().tolist()
            )
    return float(pd.Series(values).median()) if values else None


def _rank_opportunities(
    crypto: pd.DataFrame,
    universal: pd.DataFrame,
    research: pd.DataFrame,
    candidates: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Display source scores in rank order; do not create or alter a signal."""
    if (
        candidates is not None
        and not candidates.empty
        and {"asset", "current_setup_status"}.issubset(candidates.columns)
    ):
        current = candidates[
            candidates["current_setup_status"]
            .astype(str)
            .str.upper()
            .isin({"ACTIONABLE", "DEVELOPING"})
        ].copy()
        if current.empty:
            return pd.DataFrame()
        keep = [
            c
            for c in [
                "asset",
                "opportunity_score",
                "confidence_score",
                "research_score",
                "recommendation",
                "current_setup_status",
            ]
            if c in current.columns
        ]
        ranked = current[keep].copy()
        ranked["source"] = "trade_candidate_dashboard"
        ranked["opportunity_score"] = pd.to_numeric(
            ranked.get("opportunity_score"), errors="coerce"
        )
        ranked["confidence_score"] = pd.to_numeric(
            ranked.get("confidence_score"), errors="coerce"
        )
        ranked = ranked.sort_values(
            ["opportunity_score", "confidence_score"],
            ascending=[False, False],
            na_position="last",
        ).reset_index(drop=True)
        ranked.insert(0, "opportunity_rank", range(1, len(ranked) + 1))
        return ranked

    frames = []
    for source_name, df in (("crypto", crypto), ("universal", universal)):
        if df.empty or "asset" not in df.columns:
            continue
        cols = [
            c
            for c in [
                "asset",
                "opportunity_score",
                "confidence_score",
                "recommendation",
                "bucket",
                "data_freshness_status",
            ]
            if c in df.columns
        ]
        frame = df[cols].copy()
        frame["source"] = source_name
        frames.append(frame)
    if not frames:
        return pd.DataFrame()

    ranked = pd.concat(frames, ignore_index=True)
    ranked["asset"] = ranked["asset"].astype(str).str.upper()
    ranked["opportunity_score"] = pd.to_numeric(
        ranked.get("opportunity_score"), errors="coerce"
    )
    ranked["confidence_score"] = pd.to_numeric(
        ranked.get("confidence_score"), errors="coerce"
    )
    ranked = ranked.sort_values(
        ["opportunity_score", "confidence_score"],
        ascending=[False, False],
        na_position="last",
    ).drop_duplicates("asset", keep="first")

    if not research.empty and {"asset", "research_score"}.issubset(research.columns):
        scores = research[["asset", "research_score"]].copy()
        scores["asset"] = scores["asset"].astype(str).str.upper()
        ranked = ranked.merge(scores.drop_duplicates("asset"), on="asset", how="left")
    else:
        ranked["research_score"] = pd.NA
    ranked.insert(0, "opportunity_rank", range(1, len(ranked) + 1))
    return ranked.reset_index(drop=True)


def _environment_score(crypto_regime: str, equity_regime: str, volatility_regime: str, opportunity_regime: str, avg_conf: float | None) -> int:
    score = 0
    if equity_regime == "BULL":
        score += 25
    if crypto_regime == "BULL":
        score += 25
    if volatility_regime in {"LOW", "NORMAL"}:
        score += 20
    if opportunity_regime == "ACTIVE":
        score += 20
    if avg_conf is not None and avg_conf >= 70:
        score += 10
    return min(score, 100)


def _environment_status(score: int) -> str:
    if score >= 80:
        return "FAVORABLE"
    if score >= 60:
        return "SELECTIVE"
    if score >= 40:
        return "CAUTIOUS"
    return "DEFENSIVE"


def build_regime() -> pd.DataFrame:
    universal = _load_current_or_latest("universal_market_scanner")
    crypto = _load_current_or_latest("crypto_opportunity_ranking")
    candidates = _load_current_or_latest("trade_candidate_dashboard")
    backtest_regime = _load_backtest_regime()

    crypto_regime = _majority_crypto(crypto)
    equity_regime = _majority_equity(universal)
    volatility_regime = _volatility_regime(crypto, universal, backtest_regime)
    opportunity_regime = _opportunity_regime(crypto, universal, candidates)

    confidence_values = []
    for df in [crypto, universal]:
        if not df.empty and "confidence_score" in df.columns:
            confidence_values.extend(pd.to_numeric(df["confidence_score"], errors="coerce").dropna().tolist())
    avg_conf = float(pd.Series(confidence_values).mean()) if confidence_values else None
    env_score = _environment_score(crypto_regime, equity_regime, volatility_regime, opportunity_regime, avg_conf)
    env_status = _environment_status(env_score)

    crypto_bull, crypto_bear, crypto_mixed = _bias_counts(crypto, {"crypto"})
    equity_bull, equity_bear, equity_mixed = _bias_counts(
        universal, {"etf", "stock"}
    )
    median_atr = _median_atr(crypto, universal, backtest_regime)
    opportunity_count = _current_opportunity_count(crypto, universal, candidates)

    rows = [
        {"metric": "crypto_regime", "value": crypto_regime},
        {"metric": "crypto_bull_count", "value": crypto_bull},
        {"metric": "crypto_bear_count", "value": crypto_bear},
        {"metric": "crypto_mixed_count", "value": crypto_mixed},
        {"metric": "equity_regime", "value": equity_regime},
        {"metric": "equity_bull_count", "value": equity_bull},
        {"metric": "equity_bear_count", "value": equity_bear},
        {"metric": "equity_mixed_count", "value": equity_mixed},
        {"metric": "volatility_regime", "value": volatility_regime},
        {"metric": "median_atr_pct", "value": round(median_atr, 2) if median_atr is not None else None},
        {"metric": "opportunity_regime", "value": opportunity_regime},
        {"metric": "current_opportunity_count", "value": opportunity_count},
        {"metric": "environment_score", "value": env_score},
        {"metric": "environment_status", "value": env_status},
        {"metric": "average_confidence_score", "value": round(avg_conf, 2) if avg_conf is not None else None},
        {"metric": "crypto_count", "value": int(len(crypto)) if not crypto.empty else 0},
        {"metric": "equity_count", "value": int(len(universal[universal["asset_class"].astype(str).str.lower().isin(["etf", "stock"])]) if not universal.empty and "asset_class" in universal.columns else 0)},
    ]

    return pd.DataFrame(rows)


def render_markdown(
    df: pd.DataFrame, opportunity_ranking: pd.DataFrame | None = None
) -> str:
    lookup = {row["metric"]: row["value"] for _, row in df.iterrows()}
    lines = [
        "# Research Regime Engine",
        "",
        f"Date: {TODAY}",
        "",
        f"Crypto regime: {lookup.get('crypto_regime', 'UNKNOWN')}",
        f"Equity regime: {lookup.get('equity_regime', 'UNKNOWN')}",
        f"Volatility regime: {lookup.get('volatility_regime', 'UNKNOWN')}",
        f"Opportunity regime: {lookup.get('opportunity_regime', 'UNKNOWN')}",
        f"Environment score: {lookup.get('environment_score', 'N/A')}",
        f"Environment status: {lookup.get('environment_status', 'N/A')}",
        "",
        "## Regime Classification",
        "",
        f"- Crypto: {lookup.get('crypto_regime', 'UNKNOWN')} "
        f"(bull {lookup.get('crypto_bull_count', 0)}, bear {lookup.get('crypto_bear_count', 0)}, other {lookup.get('crypto_mixed_count', 0)})",
        f"- Equities: {lookup.get('equity_regime', 'UNKNOWN')} "
        f"(bull {lookup.get('equity_bull_count', 0)}, bear {lookup.get('equity_bear_count', 0)}, other {lookup.get('equity_mixed_count', 0)})",
        f"- Volatility: {lookup.get('volatility_regime', 'UNKNOWN')} "
        f"(median ATR {lookup.get('median_atr_pct', 'N/A')}%)",
        f"- Opportunity environment: {lookup.get('opportunity_regime', 'UNKNOWN')} "
        f"({lookup.get('current_opportunity_count', 0)} current ranked opportunities)",
        "",
        "## Opportunity Ranking",
        "",
    ]
    if opportunity_ranking is None or opportunity_ranking.empty:
        lines.append("No opportunity ranking available.")
    else:
        for _, row in opportunity_ranking.iterrows():
            lines.append(
                f"- #{int(row['opportunity_rank'])} {row['asset']} | "
                f"opportunity {row.get('opportunity_score')} | "
                f"confidence {row.get('confidence_score')} | "
                f"research {row.get('research_score')} | "
                f"recommendation {row.get('recommendation')} | "
                f"source {row.get('source')}"
            )
    lines += [
        "",
        "## Research Note",
        "",
        "This regime view combines the latest universal market scanner, crypto opportunity ranking, and optional backtest regime snapshot.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = build_regime()
    ranking = _rank_opportunities(
        _load_current_or_latest("crypto_opportunity_ranking"),
        _load_current_or_latest("universal_market_scanner"),
        _load_current_or_latest("research_score"),
        _load_current_or_latest("trade_candidate_dashboard"),
    )
    df.to_csv(OUT_CSV, index=False)
    OUT_MD.write_text(render_markdown(df, ranking))
    print(f"Saved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
