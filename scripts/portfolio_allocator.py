from pathlib import Path
import glob
import pandas as pd

TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")

RANKING = f"DAILY_REPORTS/{TODAY}_crypto_opportunity_ranking.csv"
OUT_CSV = f"DAILY_REPORTS/{TODAY}_portfolio_allocation.csv"
OUT_MD = f"DAILY_REPORTS/{TODAY}_portfolio_allocation.md"

MAX_POSITIONS = 3
MAX_TOTAL_ALLOCATION_PCT = 30
MAX_SINGLE_POSITION_PCT = 10
MIN_CONFIDENCE = 70
MIN_OPPORTUNITY = 75


def latest_ranking():
    if Path(RANKING).exists():
        return RANKING

    files = sorted(glob.glob("DAILY_REPORTS/*_crypto_opportunity_ranking.csv"))
    if not files:
        raise FileNotFoundError("No crypto opportunity ranking files found.")

    return files[-1]


def _safe_float(value):
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def allocation_decision(row):
    rec = row.get("recommendation")
    opp = _safe_float(row.get("opportunity_score"))
    conf = _safe_float(row.get("confidence_score"))
    pf = _safe_float(row.get("profit_factor"))
    ev = _safe_float(row.get("expected_value_pct"))
    atr_pct = _safe_float(row.get("atr_pct"))

    if rec in {"DAY1_OBSERVE_ONLY", "WATCH_CLOSELY", "HISTORICALLY_STRONG_NO_SIGNAL"}:
        return 0.0, "NO_ALLOCATION", f"{rec} bucket is not allocatable"

    if opp is None or conf is None:
        return 0.0, "NO_ALLOCATION", "missing opportunity or confidence"

    if opp < MIN_OPPORTUNITY:
        return 0.0, "NO_ALLOCATION", "opportunity below threshold"

    if conf < MIN_CONFIDENCE:
        return 0.0, "NO_ALLOCATION", "confidence below threshold"

    if rec == "MANUAL_REVIEW" and conf < 75:
        return 0.0, "NO_ALLOCATION", "manual review requires confidence >= 75"

    if rec not in {"HIGH_PRIORITY_REVIEW", "MANUAL_REVIEW"}:
        return 0.0, "NO_ALLOCATION", f"{rec} not eligible for allocation"

    score = 0.0
    score += opp * 0.35
    score += conf * 0.25
    score += (pf if pf is not None else 0.0) * 15.0
    score += (ev if ev is not None else 0.0) * 10.0

    if atr_pct is not None:
        score += max(0.0, 20.0 - atr_pct) * 0.5

    if rec == "MANUAL_REVIEW":
        score *= 0.5

    return score, "PENDING", "eligible"


df = pd.read_csv(latest_ranking())

decisions = df.apply(allocation_decision, axis=1, result_type="expand")
decisions.columns = ["raw_weight_score", "_status", "_reason"]
df = pd.concat([df, decisions], axis=1)

eligible = df[df["raw_weight_score"] > 0].copy()

eligible = eligible.sort_values(
    ["raw_weight_score", "opportunity_score", "confidence_score"],
    ascending=[False, False, False],
).head(MAX_POSITIONS)

total_raw = eligible["raw_weight_score"].sum()
if total_raw > 0:
    scale = min(1.0, MAX_TOTAL_ALLOCATION_PCT / total_raw)
    eligible["proposed_weight_pct"] = eligible["raw_weight_score"] * scale
else:
    eligible["proposed_weight_pct"] = 0.0

eligible["proposed_weight_pct"] = eligible["proposed_weight_pct"].clip(
    upper=MAX_SINGLE_POSITION_PCT
)

if eligible["proposed_weight_pct"].sum() > MAX_TOTAL_ALLOCATION_PCT:
    scale = MAX_TOTAL_ALLOCATION_PCT / eligible["proposed_weight_pct"].sum()
    eligible["proposed_weight_pct"] = eligible["proposed_weight_pct"] * scale

df["proposed_weight_pct"] = 0.0
df["allocation_status"] = "NO_ALLOCATION"
df["allocation_reason"] = df["_reason"]

for idx, row in eligible.iterrows():
    df.at[idx, "proposed_weight_pct"] = round(float(row["proposed_weight_pct"]), 2)
    df.at[idx, "allocation_status"] = (
        "ALLOCATE_REVIEW" if row["proposed_weight_pct"] > 0 else "NO_ALLOCATION"
    )
    df.at[idx, "allocation_reason"] = "eligible for allocation"

df["raw_weight_score"] = df["raw_weight_score"].apply(
    lambda x: round(float(x), 2) if pd.notna(x) else None
)
df["proposed_weight_pct"] = df["proposed_weight_pct"].apply(
    lambda x: round(float(x), 2) if pd.notna(x) else None
)
df["allocation_reason"] = df["allocation_reason"].fillna("")

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
    "raw_weight_score",
    "proposed_weight_pct",
    "allocation_status",
    "allocation_reason",
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
lines.append(f"Max positions: {MAX_POSITIONS}")
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
            f"- {row['asset']}: {row['proposed_weight_pct']:.2f}% | {row['recommendation']} | raw {row['raw_weight_score']:.2f} | score {row['opportunity_score']} | confidence {row['confidence_score']} | {row['allocation_reason']}"
        )

Path(OUT_MD).write_text("\n".join(lines))

print("\nPORTFOLIO ALLOCATION\n")
print(df[columns].to_string(index=False))
print(f"\nSaved: {OUT_CSV}")
print(f"Saved: {OUT_MD}")
