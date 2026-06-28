from pathlib import Path
import glob
import pandas as pd

TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")

RANKING = f"DAILY_REPORTS/{TODAY}_crypto_opportunity_ranking.csv"
OUT = f"DAILY_REPORTS/{TODAY}_daily_research_summary.md"


def latest_ranking():
    if Path(RANKING).exists():
        return RANKING

    files = sorted(glob.glob("DAILY_REPORTS/*_crypto_opportunity_ranking.csv"))
    if not files:
        raise FileNotFoundError("No opportunity ranking files found.")

    return files[-1]


df = pd.read_csv(latest_ranking())

active = df[df["bucket"] == "ACTIVE_OPPORTUNITY"]
high = df[df["recommendation"] == "HIGH_PRIORITY_REVIEW"]
observe = df[df["recommendation"].isin(["DAY1_OBSERVE_ONLY", "MANUAL_REVIEW", "WATCH_CLOSELY"])]
historical = df[df["bucket"] == "HISTORICAL_WATCHLIST"]

lines = []
lines.append("# Daily Crypto Research Summary")
lines.append("")
lines.append(f"Date: {TODAY}")
lines.append("")
lines.append("Research support only. Not financial advice.")
lines.append("")

lines.append("## Market Action Summary")
lines.append("")

if not high.empty:
    lines.append("High-priority setups require manual review:")
    for _, row in high.iterrows():
        lines.append(
            f"- {row['asset']}: {row['recommendation']} | score {row['opportunity_score']} | confidence {row['confidence_score']}"
        )
else:
    lines.append("No high-priority setup confirmed.")

lines.append("")

if not active.empty:
    lines.append("## Active RSI2 Oversold Signals")
    lines.append("")
    for _, row in active.iterrows():
        lines.append(f"### {row['asset']}")
        lines.append(f"- Phase: {row['current_phase']}")
        lines.append(f"- Recommendation: {row['recommendation']}")
        lines.append(f"- RSI2: {row['rsi2']}")
        lines.append(f"- Best setup: Day {row.get('entry_day', 'N/A')} / Hold {row.get('hold_days', 'N/A')}")
        lines.append(f"- EV: {row.get('expected_value_pct', 'N/A')}%")
        lines.append(f"- PF: {row.get('profit_factor', 'N/A')}")
        lines.append(f"- WR: {row.get('win_rate_pct', 'N/A')}%")
        lines.append("")
else:
    lines.append("## Active RSI2 Oversold Signals")
    lines.append("")
    lines.append("None")
    lines.append("")

if not observe.empty:
    lines.append("## Observe / Watch")
    lines.append("")
    for _, row in observe.iterrows():
        lines.append(f"- {row['asset']}: {row['recommendation']} | {row['current_phase']}")
    lines.append("")

if not historical.empty:
    lines.append("## Historical Leaders Without Current Signal")
    lines.append("")
    for _, row in historical.iterrows():
        lines.append(
            f"- {row['asset']}: EV {row.get('expected_value_pct', 'N/A')}%, PF {row.get('profit_factor', 'N/A')}, WR {row.get('win_rate_pct', 'N/A')}%"
        )
    lines.append("")

lines.append("## Process Rule")
lines.append("")
lines.append("Day1 oversold signals are observation-only unless entry timing aligns with historical best setup.")
lines.append("")

Path(OUT).write_text("\n".join(lines))

print(f"Saved: {OUT}")
print("\nDAILY SUMMARY\n")
print("\n".join(lines[:40]))
