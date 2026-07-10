from __future__ import annotations

from pathlib import Path
import glob

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "DAILY_REPORTS"
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


def _majority_crypto(df: pd.DataFrame) -> str:
    return _majority_bias(df, {"crypto"})


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


def _opportunity_regime(crypto: pd.DataFrame, universal: pd.DataFrame) -> str:
    count = 0
    for df in [crypto, universal]:
        if df.empty or "recommendation" not in df.columns:
            continue
        rec = df["recommendation"].astype(str).str.upper()
        count += int(rec.isin({"WATCH_RESEARCH", "ACTIVE_OPPORTUNITY"}).sum())
    if count >= 3:
        return "ACTIVE"
    if 1 <= count <= 2:
        return "QUIET"
    return "EMPTY"


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
    universal = _load_latest("*_universal_market_scanner.csv")
    crypto = _load_latest("*_crypto_opportunity_ranking.csv")
    backtest_regime = _load_backtest_regime()

    crypto_regime = _majority_crypto(crypto)
    equity_regime = _majority_equity(universal)
    volatility_regime = _volatility_regime(crypto, universal, backtest_regime)
    opportunity_regime = _opportunity_regime(crypto, universal)

    confidence_values = []
    for df in [crypto, universal]:
        if not df.empty and "confidence_score" in df.columns:
            confidence_values.extend(pd.to_numeric(df["confidence_score"], errors="coerce").dropna().tolist())
    avg_conf = float(pd.Series(confidence_values).mean()) if confidence_values else None
    env_score = _environment_score(crypto_regime, equity_regime, volatility_regime, opportunity_regime, avg_conf)
    env_status = _environment_status(env_score)

    rows = [
        {"metric": "crypto_regime", "value": crypto_regime},
        {"metric": "equity_regime", "value": equity_regime},
        {"metric": "volatility_regime", "value": volatility_regime},
        {"metric": "opportunity_regime", "value": opportunity_regime},
        {"metric": "environment_score", "value": env_score},
        {"metric": "environment_status", "value": env_status},
        {"metric": "average_confidence_score", "value": round(avg_conf, 2) if avg_conf is not None else None},
        {"metric": "crypto_count", "value": int(len(crypto)) if not crypto.empty else 0},
        {"metric": "equity_count", "value": int(len(universal[universal["asset_class"].astype(str).str.lower().isin(["etf", "stock"])]) if not universal.empty and "asset_class" in universal.columns else 0)},
    ]

    return pd.DataFrame(rows)


def render_markdown(df: pd.DataFrame) -> str:
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
        "## Research Note",
        "",
        "This regime view combines the latest universal market scanner, crypto opportunity ranking, and optional backtest regime snapshot.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = build_regime()
    df.to_csv(OUT_CSV, index=False)
    OUT_MD.write_text(render_markdown(df))
    print(f"Saved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
