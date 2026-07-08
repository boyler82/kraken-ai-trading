from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.data_loader import load_ohlc  # noqa: E402
from lib.indicators import atr, rsi, sma  # noqa: E402


TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")
REPORT_DIR = ROOT / "DAILY_REPORTS"

FILES = {
    "BTC": "DATASETS/market_raw/BTCUSD_D1.json",
    "ETH": "DATASETS/market_raw/ETHUSD_D1.json",
    "SOL": "DATASETS/market_raw/SOLUSD_D1.json",
    "XRP": "DATASETS/market_raw/XRPUSD_D1.json",
    "ADA": "DATASETS/market_raw/ADAUSD_D1.json",
    "LINK": "DATASETS/market_raw/LINKUSD_D1.json",
    "DOGE": "DATASETS/market_raw/DOGEUSD_D1.json",
    "AVAX": "DATASETS/market_raw/AVAXUSD_D1.json",
    "LTC": "DATASETS/market_raw/LTCUSD_D1.json",
    "SPY": "DATASETS/market_raw/SPYx_USD_D1.json",
    "QQQ": "DATASETS/market_raw/QQQx_USD_D1.json",
    "GLD": "DATASETS/market_raw/GLDx_USD_D1.json",
    "NVDA": "DATASETS/market_raw/NVDAx_USD_D1.json",
    "TSLA": "DATASETS/market_raw/TSLAx_USD_D1.json",
}


def _asset_class(asset: str) -> str:
    if asset in {"BTC", "ETH", "SOL", "XRP", "ADA", "LINK", "DOGE", "AVAX", "LTC"}:
        return "crypto"
    if asset in {"SPY", "QQQ", "GLD"}:
        return "etf"
    if asset in {"NVDA", "TSLA"}:
        return "stock"
    return "other"


def _to_float(value):
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_asset_frame(path_text: str) -> pd.DataFrame | None:
    path = ROOT / path_text
    if not path.exists():
        return None
    df = load_ohlc(path)
    if df.empty:
        return None
    df = df.copy()
    df["rsi2"] = rsi(df["close"], 2)
    df["ma20"] = sma(df["close"], 20)
    df["ma200"] = sma(df["close"], 200)
    df["atr14"] = atr(df, 14)
    df = df.dropna().reset_index(drop=True)
    if df.empty:
        return None
    return df


def _build_row(asset: str, df: pd.DataFrame) -> dict:
    last = df.iloc[-1]
    last_data_date = pd.Timestamp(last["date"]).normalize()
    report_date = pd.Timestamp(TODAY).normalize()
    data_age_days = int((report_date - last_data_date).days)
    if data_age_days <= 2:
        data_freshness_status = "FRESH"
    else:
        data_freshness_status = "STALE"

    close = _to_float(last["close"])
    rsi2 = _to_float(last["rsi2"])
    ma20 = _to_float(last["ma20"])
    ma200 = _to_float(last["ma200"])
    atr14 = _to_float(last["atr14"])
    atr_pct = (atr14 / close * 100) if atr14 is not None and close not in (None, 0) else None
    dist_ma20_pct = ((close / ma20) - 1) * 100 if close is not None and ma20 not in (None, 0) else None
    market_bias = "BULL" if close is not None and ma200 is not None and close > ma200 else "BEAR"

    if rsi2 is not None and rsi2 < 10:
        current_phase = "OVERSOLD"
        recommendation = "WATCH_RESEARCH"
        base_score = 70
    elif rsi2 is not None and rsi2 < 25:
        current_phase = "NEAR_OVERSOLD"
        recommendation = "WATCHLIST"
        base_score = 40
    else:
        current_phase = "NO_SIGNAL"
        recommendation = "NO_ACTION"
        base_score = 0

    opportunity_score = base_score
    if market_bias == "BULL":
        opportunity_score += 10
    if atr_pct is not None and atr_pct <= 5:
        opportunity_score += 5
    opportunity_score = min(opportunity_score, 100)

    confidence_score = 50
    if len(df) >= 200:
        confidence_score += 20
    if market_bias == "BULL":
        confidence_score += 10
    if atr_pct is not None and atr_pct <= 5:
        confidence_score += 10
    confidence_score = min(confidence_score, 100)

    distance_to_signal = rsi2 - 10 if rsi2 is not None else None
    if current_phase == "OVERSOLD":
        reason = "RSI2 below 10"
        next_action = "manual research review"
    elif current_phase == "NEAR_OVERSOLD":
        reason = "RSI2 below 25, waiting for RSI2 < 10"
        next_action = "watch for RSI2 < 10"
    elif current_phase == "NO_SIGNAL" and rsi2 is not None and rsi2 > 80:
        reason = "Overbought / after rebound"
        next_action = "wait"
    else:
        reason = "No statistical setup"
        next_action = "wait"

    asset_class = _asset_class(asset)
    if asset_class in {"etf", "stock"} and data_freshness_status == "STALE":
        recommendation = "STALE_DATA"
        opportunity_score = 0
        confidence_score = 0
        next_action = "refresh external market data"
        reason = "stale external market data"

    return {
        "asset": asset,
        "asset_class": asset_class,
        "date": str(last["date"].date()),
        "last_data_date": last_data_date.strftime("%Y-%m-%d"),
        "data_age_days": data_age_days,
        "data_freshness_status": data_freshness_status,
        "close": round(close, 8) if close is not None else None,
        "rsi2": round(rsi2, 4) if rsi2 is not None else None,
        "ma20": round(ma20, 8) if ma20 is not None else None,
        "ma200": round(ma200, 8) if ma200 is not None else None,
        "dist_ma20_pct": round(dist_ma20_pct, 4) if dist_ma20_pct is not None else None,
        "atr_pct": round(atr_pct, 4) if atr_pct is not None else None,
        "market_bias": market_bias,
        "current_phase": current_phase,
        "recommendation": recommendation,
        "distance_to_signal": round(distance_to_signal, 4) if distance_to_signal is not None else None,
        "reason": reason,
        "next_action": next_action,
        "opportunity_score": opportunity_score,
        "confidence_score": confidence_score,
    }


def build_market_scanner() -> pd.DataFrame:
    rows = []
    for asset, path_text in FILES.items():
        if asset == "TSLA" and not (ROOT / path_text).exists():
            continue
        df = _load_asset_frame(path_text)
        if df is None:
            continue
        rows.append(_build_row(asset, df))

    report = pd.DataFrame(rows)
    if report.empty:
        return report

    report = report.sort_values(["opportunity_score", "confidence_score"], ascending=[False, False]).reset_index(drop=True)
    report.insert(0, "rank", range(1, len(report) + 1))
    return report[
        [
            "rank",
            "asset",
            "asset_class",
            "date",
            "last_data_date",
            "data_age_days",
            "data_freshness_status",
            "close",
            "rsi2",
            "ma20",
            "ma200",
            "dist_ma20_pct",
            "atr_pct",
            "market_bias",
            "current_phase",
            "recommendation",
            "distance_to_signal",
            "reason",
            "next_action",
            "opportunity_score",
            "confidence_score",
        ]
    ]


def render_report(report: pd.DataFrame) -> str:
    lines = [
        "# Universal Market Scanner",
        "",
        f"Date: {TODAY}",
        "",
        "Research-only note: this ranking is for statistical review only.",
        "",
        "## Top Opportunities",
        "",
    ]

    if report.empty:
        lines.append("No assets found.")
    else:
        for _, row in report.head(10).iterrows():
            lines.append(
                f"### #{int(row['rank'])} {row['asset']} | Opp {row['opportunity_score']} | Conf {row['confidence_score']}"
            )
            lines.append("")
            lines.append(f"- Asset class: {row['asset_class']}")
            lines.append(f"- Recommendation: {row['recommendation']}")
            lines.append(f"- Phase: {row['current_phase']}")
            lines.append(f"- Last data date: {row['last_data_date']}")
            lines.append(f"- Data age days: {row['data_age_days']}")
            lines.append(f"- Data freshness status: {row['data_freshness_status']}")
            lines.append(f"- Close: {row['close']}")
            lines.append(f"- RSI2: {row['rsi2']}")
            lines.append(f"- MA20: {row['ma20']}")
            lines.append(f"- MA200: {row['ma200']}")
            lines.append(f"- Dist MA20 %: {row['dist_ma20_pct']}")
            lines.append(f"- ATR %: {row['atr_pct']}")
            lines.append(f"- Market bias: {row['market_bias']}")
            lines.append(f"- Distance to signal: {row['distance_to_signal']}")
            lines.append(f"- Reason: {row['reason']}")
            lines.append(f"- Next action: {row['next_action']}")
            lines.append("")

    lines.append("## Full Ranking")
    lines.append("")
    if report.empty:
        lines.append("No assets found.")
    else:
        for _, row in report.iterrows():
            lines.append(
                f"- #{int(row['rank'])} {row['asset']} | {row['asset_class']} | {row['recommendation']} | Opp {row['opportunity_score']} | Conf {row['confidence_score']} | Close {row['close']} | Data age {row['data_age_days']} | Freshness {row['data_freshness_status']} | ATR {row['atr_pct']} | Bias {row['market_bias']} | Dist {row['distance_to_signal']} | Reason {row['reason']} | Next {row['next_action']}"
            )

    lines.append("")
    lines.append("Research-only note: no strategy changes and no execution logic.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = build_market_scanner()

    csv_out = REPORT_DIR / f"{TODAY}_universal_market_scanner.csv"
    md_out = REPORT_DIR / f"{TODAY}_universal_market_scanner.md"

    report.to_csv(csv_out, index=False)
    md_out.write_text(render_report(report))

    print("\nUNIVERSAL MARKET SCANNER\n")
    print(report.to_string(index=False) if not report.empty else "No assets found.")
    print(f"\nSaved: {csv_out}")
    print(f"Saved: {md_out}")


if __name__ == "__main__":
    main()
