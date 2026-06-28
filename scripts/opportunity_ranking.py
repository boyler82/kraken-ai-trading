from pathlib import Path
import sys
import glob
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")

EPISODE_STATUS = f"DAILY_REPORTS/{TODAY}_rsi2_episode_status.csv"
BEST_EDGE = "BACKTESTS/rsi2_best_edge.csv"
MARKET_REGIME = "BACKTESTS/market_regime.csv"

OUT_CSV = f"DAILY_REPORTS/{TODAY}_crypto_opportunity_ranking.csv"
OUT_MD = f"DAILY_REPORTS/{TODAY}_crypto_opportunity_ranking.md"


def latest_episode_status():
    if Path(EPISODE_STATUS).exists():
        return EPISODE_STATUS

    files = sorted(glob.glob("DAILY_REPORTS/*_rsi2_episode_status.csv"))
    if not files:
        raise FileNotFoundError("No RSI2 episode status files found.")
    return files[-1]


def classify_bucket(row):
    phase = str(row.get("current_phase", ""))

    if phase.startswith("OVERSOLD"):
        return "ACTIVE_OPPORTUNITY"
    if phase == "NEAR_OVERSOLD":
        return "WATCHLIST"

    ev = row.get("expected_value_pct", 0)
    pf = row.get("profit_factor", 0)

    if pd.notna(ev) and pd.notna(pf) and ev >= 1.0 and pf >= 1.5:
        return "HISTORICAL_WATCHLIST"

    return "NO_ACTION"


def market_bias(row):
    trend = str(row.get("trend", "UNKNOWN"))
    volatility = str(row.get("volatility", "UNKNOWN"))

    if trend == "BEAR" and volatility == "HIGH":
        return "BEAR_HIGH_VOL"
    if trend == "BEAR":
        return "BEAR"
    if trend == "BULL" and volatility == "HIGH":
        return "BULL_HIGH_VOL"
    if trend == "BULL":
        return "BULL"
    return "UNKNOWN"


def confidence_score(row):
    score = 0

    trades = row.get("trades", 0)
    ev = row.get("expected_value_pct", 0)
    pf = row.get("profit_factor", 0)
    wr = row.get("win_rate_pct", 0)
    median = row.get("median_return_pct", 0)

    if pd.notna(trades):
        if trades >= 100:
            score += 25
        elif trades >= 75:
            score += 20
        elif trades >= 50:
            score += 15

    if pd.notna(ev):
        if ev >= 1.5:
            score += 25
        elif ev >= 1.0:
            score += 20
        elif ev >= 0.5:
            score += 10

    if pd.notna(pf):
        if pf >= 1.8:
            score += 25
        elif pf >= 1.5:
            score += 20
        elif pf >= 1.2:
            score += 10

    if pd.notna(wr):
        if wr >= 60:
            score += 15
        elif wr >= 55:
            score += 10
        elif wr >= 50:
            score += 5

    if pd.notna(median) and median > 0:
        score += 10

    return min(score, 100)


def opportunity_score(row):
    score = 0

    phase = str(row.get("current_phase", ""))
    rsi2 = row.get("rsi2", 100)
    duration = row.get("current_oversold_duration", 0)
    ev = row.get("expected_value_pct", 0)
    pf = row.get("profit_factor", 0)
    trend = str(row.get("trend", "UNKNOWN"))
    volatility = str(row.get("volatility", "UNKNOWN"))

    if phase.startswith("OVERSOLD"):
        score += 40
        if duration == 3:
            score += 25
        elif duration == 2:
            score += 20
        elif duration == 1:
            score += 0
        elif duration >= 4:
            score += 10
    elif phase == "NEAR_OVERSOLD":
        score += 20

    if pd.notna(rsi2):
        if rsi2 < 5:
            score += 15
        elif rsi2 < 10:
            score += 12
        elif rsi2 < 25:
            score += 5

    if pd.notna(ev):
        if ev >= 1.5:
            score += 20
        elif ev >= 1.0:
            score += 15
        elif ev >= 0.5:
            score += 8

    if pd.notna(pf):
        if pf >= 1.8:
            score += 15
        elif pf >= 1.5:
            score += 10
        elif pf >= 1.2:
            score += 5

    if trend == "BEAR" and volatility == "HIGH":
        score += 10
    elif trend == "BEAR" and volatility == "LOW":
        score += 5
    elif trend == "BULL" and volatility == "HIGH":
        score += 5

    return min(score, 100)


def recommendation(row):
    bucket = row["bucket"]
    opp = row["opportunity_score"]
    conf = row["confidence_score"]
    duration = row.get("current_oversold_duration", 0)

    if bucket == "ACTIVE_OPPORTUNITY" and duration == 1:
        return "DAY1_OBSERVE_ONLY"

    if bucket == "ACTIVE_OPPORTUNITY" and duration in [2, 3] and opp >= 75 and conf >= 70:
        return "HIGH_PRIORITY_REVIEW"

    if bucket == "ACTIVE_OPPORTUNITY":
        return "MANUAL_REVIEW"

    if bucket == "WATCHLIST":
        return "WATCH_CLOSELY"

    if bucket == "HISTORICAL_WATCHLIST":
        return "HISTORICALLY_STRONG_NO_SIGNAL"

    return "NO_ACTION"


def build_ranking():
    status = pd.read_csv(latest_episode_status())
    edge = pd.read_csv(BEST_EDGE)

    df = status.merge(edge, on="asset", how="left")

    if Path(MARKET_REGIME).exists():
        regime = pd.read_csv(MARKET_REGIME)
        df = df.merge(
            regime[["asset", "trend", "volatility", "atr_pct"]],
            on="asset",
            how="left",
        )
    else:
        df["trend"] = "UNKNOWN"
        df["volatility"] = "UNKNOWN"
        df["atr_pct"] = None

    df["market_bias"] = df.apply(market_bias, axis=1)
    df["bucket"] = df.apply(classify_bucket, axis=1)
    df["confidence_score"] = df.apply(confidence_score, axis=1)
    df["opportunity_score"] = df.apply(opportunity_score, axis=1)
    df["recommendation"] = df.apply(recommendation, axis=1)

    bucket_order = {
        "ACTIVE_OPPORTUNITY": 1,
        "WATCHLIST": 2,
        "HISTORICAL_WATCHLIST": 3,
        "NO_ACTION": 4,
    }

    df["bucket_order"] = df["bucket"].map(bucket_order).fillna(99)

    return df.sort_values(
        ["bucket_order", "opportunity_score", "confidence_score"],
        ascending=[True, False, False],
    )


def save_outputs(df):
    columns = [
        "asset",
        "bucket",
        "recommendation",
        "opportunity_score",
        "confidence_score",
        "current_phase",
        "rsi2",
        "close",
        "trend",
        "volatility",
        "market_bias",
        "atr_pct",
        "entry_day",
        "hold_days",
        "trades",
        "win_rate_pct",
        "expected_value_pct",
        "profit_factor",
        "avg_return_pct",
        "median_return_pct",
        "worst_return_pct",
        "best_return_pct",
        "current_oversold_duration",
    ]

    df[columns].to_csv(OUT_CSV, index=False)

    lines = [
        "# Crypto Opportunity Ranking",
        "",
        f"Date: {TODAY}",
        "",
        "Research support only. Not an automatic buy/sell instruction.",
        "",
    ]

    for bucket in ["ACTIVE_OPPORTUNITY", "WATCHLIST", "HISTORICAL_WATCHLIST", "NO_ACTION"]:
        sample = df[df["bucket"] == bucket]
        lines.append(f"## {bucket}")
        lines.append("")

        if sample.empty:
            lines.append("None")
            lines.append("")
            continue

        for _, row in sample.iterrows():
            lines.append(
                f"### {row['asset']} — Opportunity {int(row['opportunity_score'])}/100 | Confidence {int(row['confidence_score'])}/100"
            )
            lines.append("")
            lines.append(f"- Recommendation: {row['recommendation']}")
            lines.append(f"- Phase: {row['current_phase']}")
            lines.append(f"- RSI2: {row['rsi2']}")
            lines.append(f"- Close: {row['close']}")
            lines.append(f"- Trend: {row['trend']}")
            lines.append(f"- Volatility: {row['volatility']}")
            lines.append(f"- Market bias: {row['market_bias']}")
            lines.append(f"- ATR %: {row['atr_pct']}")

            if pd.notna(row.get("entry_day")) and pd.notna(row.get("hold_days")):
                lines.append(
                    f"- Best setup: Day {int(row['entry_day'])} / Hold {int(row['hold_days'])} days"
                )
            else:
                lines.append("- Best setup: N/A")

            lines.append(
                f"- Trades: {int(row['trades'])}"
                if pd.notna(row.get("trades"))
                else "- Trades: N/A"
            )
            lines.append(f"- Win rate: {row.get('win_rate_pct', 'N/A')}%")
            lines.append(f"- Expected value: {row.get('expected_value_pct', 'N/A')}%")
            lines.append(f"- Profit factor: {row.get('profit_factor', 'N/A')}")
            lines.append(f"- Median return: {row.get('median_return_pct', 'N/A')}%")
            lines.append("")

    Path(OUT_MD).write_text("\n".join(lines))

    print("\nCRYPTO OPPORTUNITY RANKING\n")
    print(df[columns].to_string(index=False))

    print(f"\nSaved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")


def main():
    df = build_ranking()
    save_outputs(df)


if __name__ == "__main__":
    main()
