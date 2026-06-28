from pathlib import Path
import glob
import pandas as pd

TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")

RANKING = f"DAILY_REPORTS/{TODAY}_crypto_opportunity_ranking.csv"
OUT_CSV = f"DAILY_REPORTS/{TODAY}_portfolio_allocation.csv"
OUT_MD = f"DAILY_REPORTS/{TODAY}_portfolio_allocation.md"

MAX_TOTAL_ALLOCATION_PCT = 30
MAX_SINGLE_POSITION_PCT = 10


def latest_ranking():
    if Path(RANKING).exists():
        return RANKING

    files = sorted(glob.glob("DAILY_REPORTS/*_crypto_opportunity_ranking.csv"))
    if not files:
        raise FileNotFoundError("No crypto opportunity ranking files found.")

    return files[-1]


def allocation_weight(row):
    rec = row["recommendation"]
    opp = row["opportunity_score"]
    conf = row["confidence_score"]

    if rec == "HIGH_PRIORITY_REVIEW" and opp >= 75 and conf >= 70:
        return MAX_SINGLE_POSITION_PCT

    if rec == "MANUAL_REVIEW" and opp >= 70 and conf >= 70:
        return MAX_SINGLE_POSITION_PCT / 2

    return 0


df = pd.read_csv(latest_ranking())

df["proposed_weight_pct"] = df.apply(allocation_weight, axis=1)

active = df[df["proposed_weight_pct"] > 0].copy()

total = active["proposed_weight_pct"].sum()

if total > MAX_TOTAL_ALLOCATION_PCT and total > 0:
    scale = MAX_TOTAL_ALLOCATION_PCT / total
    df["proposed_weight_pct"] = df["proposed_weight_pct"] * scale

df["allocation_status"] = df["proposed_weight_pct"].apply(
    lambda x: "ALLOCATE_REVIEW" if x > 0 else "NO_ALLOCATION"
)

columns = [
    "asset",
    "recommendation",
    "bucket",
    "opportunity_score",
    "confidence_score",
    "current_phase",
    "rsi2",
    "entry_day",
    "hold_days",
    "expected_value_pct",
    "profit_factor",
    "win_rate_pct",
    "proposed_weight_pct",
    "allocation_status",
]

df[columns].to_csv(OUT_CSV, index=False)

lines = []
lines.append("# Portfolio Allocation")
lines.append("")
lines.append(f"Date: {TODAY}")
lines.append("")
lines.append("Research support only. Not an automatic trade instruction.")
lines.append("")
lines.append(f"Max total allocation: {MAX_TOTAL_ALLOCATION_PCT}%")
lines.append(f"Max single position: {MAX_SINGLE_POSITION_PCT}%")
lines.append("")

allocated = df[df["proposed_weight_pct"] > 0]

if allocated.empty:
    lines.append("## Allocation Decision")
    lines.append("")
    lines.append("100% CASH / NO ALLOCATION")
    lines.append("")
    lines.append("Reason: no setup reached allocation threshold.")
else:
    lines.append("## Allocation Candidates")
    lines.append("")
    for _, row in allocated.iterrows():
        lines.append(
            f"- {row['asset']}: {row['proposed_weight_pct']:.2f}% | {row['recommendation']} | score {row['opportunity_score']} | confidence {row['confidence_score']}"
        )

Path(OUT_MD).write_text("\n".join(lines))

print("\nPORTFOLIO ALLOCATION\n")
print(df[columns].to_string(index=False))
print(f"\nSaved: {OUT_CSV}")
print(f"Saved: {OUT_MD}")
