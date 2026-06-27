from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")

EPISODE_SUMMARY = "BACKTESTS/rsi2_oversold_episode_summary.csv"
EPISODE_STATUS = f"DAILY_REPORTS/{TODAY}_rsi2_episode_status.csv"

OUT_CSV = f"DAILY_REPORTS/{TODAY}_crypto_opportunity_ranking.csv"
OUT_MD = f"DAILY_REPORTS/{TODAY}_crypto_opportunity_ranking.md"


def best_entry_label(row):
    values = {
        "DAY1": row.get("avg_ret_day1_hold3_pct"),
        "DAY2": row.get("avg_ret_day2_hold3_pct"),
        "DAY3": row.get("avg_ret_day3_hold3_pct"),
    }

    values = {k: v for k, v in values.items() if pd.notna(v)}

    if not values:
        return None, None

    best_day = max(values, key=values.get)
    return best_day, values[best_day]


def classify_bucket(row):
    phase = str(row.get("current_phase", ""))

    if phase.startswith("OVERSOLD"):
        return "ACTIVE_OPPORTUNITY"

    if phase == "NEAR_OVERSOLD":
        return "WATCHLIST"

    best_return = row.get("best_entry_return_pct", 0)

    if pd.notna(best_return) and best_return >= 1.5:
        return "HISTORICAL_WATCHLIST"

    return "NO_ACTION"


def confidence_score(row):
    score = 0

    episodes = row.get("episodes", 0)
    best_return = row.get("best_entry_return_pct", 0)

    if episodes >= 100:
        score += 35
    elif episodes >= 75:
        score += 25
    elif episodes >= 50:
        score += 15

    if pd.notna(best_return):
        if best_return >= 2.0:
            score += 35
        elif best_return >= 1.0:
            score += 25
        elif best_return >= 0.5:
            score += 15
        elif best_return > 0:
            score += 5

    avg_duration = row.get("avg_duration_days", 0)

    if pd.notna(avg_duration):
        if 1.5 <= avg_duration <= 3.0:
            score += 20
        elif avg_duration > 0:
            score += 10

    return min(score, 100)


def opportunity_score(row):
    score = 0

    phase = str(row.get("current_phase", ""))
    rsi2 = row.get("rsi2", 100)
    duration = row.get("current_oversold_duration", 0)
    best_return = row.get("best_entry_return_pct", 0)

    if phase.startswith("OVERSOLD"):
        score += 40

        if duration == 2:
            score += 20
        elif duration == 3:
            score += 25
        elif duration >= 4:
            score += 10
        elif duration == 1:
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

    if pd.notna(best_return):
        if best_return >= 2.0:
            score += 20
        elif best_return >= 1.0:
            score += 15
        elif best_return >= 0.5:
            score += 8

    return min(score, 100)


def recommendation(row):
    bucket = row["bucket"]
    opp = row["opportunity_score"]
    conf = row["confidence_score"]

    if bucket == "ACTIVE_OPPORTUNITY" and opp >= 75 and conf >= 70:
        return "HIGH_PRIORITY_REVIEW"

    if bucket == "ACTIVE_OPPORTUNITY":
        return "MANUAL_REVIEW"

    if bucket == "WATCHLIST":
        return "WATCH_CLOSELY"

    if bucket == "HISTORICAL_WATCHLIST":
        return "HISTORICALLY_STRONG_NO_SIGNAL"

    return "NO_ACTION"


def load_inputs():
    if not Path(EPISODE_SUMMARY).exists():
        raise FileNotFoundError(f"Missing {EPISODE_SUMMARY}")

    if not Path(EPISODE_STATUS).exists():
        raise FileNotFoundError(f"Missing {EPISODE_STATUS}")

    summary = pd.read_csv(EPISODE_SUMMARY)
    status = pd.read_csv(EPISODE_STATUS)

    return summary, status


def build_ranking():
    summary, status = load_inputs()

    df = status.merge(summary, on="asset", how="left")

    best_days = df.apply(best_entry_label, axis=1)
    df["best_entry_day"] = [x[0] for x in best_days]
    df["best_entry_return_pct"] = [x[1] for x in best_days]

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

    df = df.sort_values(
        ["bucket_order", "opportunity_score", "confidence_score"],
        ascending=[True, False, False],
    )

    return df


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
        "current_oversold_duration",
        "episodes",
        "avg_duration_days",
        "best_entry_day",
        "best_entry_return_pct",
        "avg_ret_day1_hold3_pct",
        "avg_ret_day2_hold3_pct",
        "avg_ret_day3_hold3_pct",
    ]

    df[columns].to_csv(OUT_CSV, index=False)

    lines = []
    lines.append("# Crypto Opportunity Ranking")
    lines.append("")
    lines.append(f"Date: {TODAY}")
    lines.append("")
    lines.append("Ranking is research support only. It is not an automatic buy/sell instruction.")
    lines.append("")

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
            lines.append(f"- Episodes: {row['episodes']}")
            lines.append(f"- Avg episode duration: {row['avg_duration_days']} days")
            lines.append(f"- Best historical entry: {row['best_entry_day']}")
            lines.append(f"- Best entry avg return: {row['best_entry_return_pct']}%")
            lines.append(f"- Day1 avg return: {row['avg_ret_day1_hold3_pct']}%")
            lines.append(f"- Day2 avg return: {row['avg_ret_day2_hold3_pct']}%")
            lines.append(f"- Day3 avg return: {row['avg_ret_day3_hold3_pct']}%")
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