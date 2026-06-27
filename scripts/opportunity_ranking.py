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


def score_row(row):
    score = 0

    # Historical edge
    best_return = max(
        row.get("avg_ret_day1_hold3_pct", 0),
        row.get("avg_ret_day2_hold3_pct", 0),
        row.get("avg_ret_day3_hold3_pct", 0),
    )

    if best_return >= 2.0:
        score += 35
    elif best_return >= 1.0:
        score += 25
    elif best_return >= 0.5:
        score += 15
    elif best_return > 0:
        score += 5

    # Sample size
    episodes = row.get("episodes", 0)

    if episodes >= 100:
        score += 20
    elif episodes >= 75:
        score += 15
    elif episodes >= 50:
        score += 10

    # Current episode phase
    phase = str(row.get("current_phase", ""))

    if phase.startswith("OVERSOLD_DAY_3"):
        score += 25
    elif phase.startswith("OVERSOLD_DAY_2"):
        score += 20
    elif phase.startswith("OVERSOLD_DAY_1"):
        score += 10
    elif phase == "NEAR_OVERSOLD":
        score += 5

    # Current RSI
    rsi2 = row.get("rsi2", 100)

    if rsi2 < 5:
        score += 10
    elif rsi2 < 10:
        score += 8
    elif rsi2 < 25:
        score += 3

    return min(score, 100)


def best_entry_label(row):
    values = {
        "DAY1": row.get("avg_ret_day1_hold3_pct", None),
        "DAY2": row.get("avg_ret_day2_hold3_pct", None),
        "DAY3": row.get("avg_ret_day3_hold3_pct", None),
    }

    values = {k: v for k, v in values.items() if pd.notna(v)}

    if not values:
        return None, None

    best_day = max(values, key=values.get)
    return best_day, values[best_day]


summary = pd.read_csv(EPISODE_SUMMARY)
status = pd.read_csv(EPISODE_STATUS)

df = status.merge(summary, on="asset", how="left")

best_days = df.apply(best_entry_label, axis=1)
df["best_entry_day"] = [x[0] for x in best_days]
df["best_entry_return_pct"] = [x[1] for x in best_days]

df["opportunity_score"] = df.apply(score_row, axis=1)

df = df.sort_values("opportunity_score", ascending=False)

columns = [
    "asset",
    "opportunity_score",
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
lines.append("## Ranking")
lines.append("")

for _, row in df.iterrows():
    lines.append(f"### {int(row['opportunity_score'])}/100 — {row['asset']}")
    lines.append("")
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

lines.append("## Process Note")
lines.append("")
lines.append("Ranking is research support only. It is not an automatic buy/sell instruction.")
lines.append("High score means the current setup is historically interesting and should be reviewed manually.")
lines.append("")

Path(OUT_MD).write_text("\n".join(lines))

print("\nCRYPTO OPPORTUNITY RANKING\n")
print(df[columns].to_string(index=False))

print(f"\nSaved: {OUT_CSV}")
print(f"Saved: {OUT_MD}")