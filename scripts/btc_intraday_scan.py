from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.data_loader import load_ohlc
from lib.indicators import rsi

DATA_FILE = "DATASETS/market_raw/BTCUSD_1H.json"

LOOKBACK_HOURS = 48
TRIGGER_WINDOW = 8

OVERSOLD_RSI = 30
OVERSOLD_DIST_MA20 = -1.0


def score_row(row, avg_volume):
    score = 0

    if row["rsi6"] < OVERSOLD_RSI:
        score += 2

    if row["dist_ma20_pct"] < OVERSOLD_DIST_MA20:
        score += 2

    if row["reclaim_prev_high"]:
        score += 2

    if row["close"] > row["ma20"]:
        score += 1

    if row["volume"] > avg_volume:
        score += 1

    return score


df = load_ohlc(DATA_FILE)

df["ma20"] = df["close"].rolling(20).mean()
df["rsi6"] = rsi(df["close"], 6)
df["dist_ma20_pct"] = (df["close"] / df["ma20"] - 1) * 100
df["prev_high"] = df["high"].shift(1)
df["reclaim_prev_high"] = df["close"] > df["prev_high"]
df["avg_volume_20"] = df["volume"].rolling(20).mean()

df = df.dropna().reset_index(drop=True)

last = df.iloc[-1]
current_score = score_row(last, last["avg_volume_20"])

current_status = "NO SETUP"

if current_score >= 6:
    current_status = "INTRADAY CANDIDATE"
elif current_score >= 4:
    current_status = "WATCH"

current_report = {
    "symbol": "BTCUSD",
    "timeframe": "1H",
    "date": str(last["date"]),
    "close": round(last["close"], 2),
    "rsi6": round(last["rsi6"], 2),
    "ma20": round(last["ma20"], 2),
    "dist_ma20_pct": round(last["dist_ma20_pct"], 2),
    "reclaim_prev_high": bool(last["reclaim_prev_high"]),
    "score": current_score,
    "status": current_status,
}

print("\nCURRENT STATUS\n")
print(pd.DataFrame([current_report]).to_string(index=False))


recent = df.tail(LOOKBACK_HOURS).copy()
recent_signals = []

for idx, row in recent.iterrows():
    oversold = (
        row["rsi6"] < OVERSOLD_RSI
        and row["dist_ma20_pct"] < OVERSOLD_DIST_MA20
    )

    if not oversold:
        continue

    future = df.loc[idx + 1 : idx + TRIGGER_WINDOW].copy()

    if future.empty:
        continue

    trigger_rows = future[future["reclaim_prev_high"]]

    if trigger_rows.empty:
        trigger_date = None
        trigger_price = None
        max_move_pct = None
        max_adverse_pct = None
        triggered = False
    else:
        trigger = trigger_rows.iloc[0]
        triggered = True
        trigger_date = trigger["date"]
        trigger_price = trigger["close"]

        after_trigger = df.loc[
            trigger_rows.index[0] : trigger_rows.index[0] + TRIGGER_WINDOW
        ].copy()

        max_move_pct = (
            after_trigger["high"].max() / trigger_price - 1
        ) * 100

        max_adverse_pct = (
            after_trigger["low"].min() / trigger_price - 1
        ) * 100

    recent_signals.append(
        {
            "oversold_date": row["date"],
            "oversold_close": round(row["close"], 2),
            "rsi6": round(row["rsi6"], 2),
            "dist_ma20_pct": round(row["dist_ma20_pct"], 2),
            "triggered": triggered,
            "trigger_date": trigger_date,
            "trigger_price": None if trigger_price is None else round(trigger_price, 2),
            "max_move_pct": None if max_move_pct is None else round(max_move_pct, 2),
            "max_adverse_pct": None if max_adverse_pct is None else round(max_adverse_pct, 2),
        }
    )


Path("DAILY_REPORTS").mkdir(exist_ok=True)

today = pd.Timestamp.today().strftime("%Y-%m-%d")

current_out = Path(f"DAILY_REPORTS/{today}_btc_intraday_current.csv")
pd.DataFrame([current_report]).to_csv(current_out, index=False)

signals_out = Path(f"DAILY_REPORTS/{today}_btc_intraday_recent_signals.csv")

if recent_signals:
    signals_df = pd.DataFrame(recent_signals)
    signals_df.to_csv(signals_out, index=False)

    print("\nRECENT OVERSOLD EVENTS / TRIGGERS\n")
    print(signals_df.sort_values("oversold_date", ascending=False).to_string(index=False))
    print(f"\nSaved: {signals_out}")
else:
    pd.DataFrame(
        columns=[
            "oversold_date",
            "oversold_close",
            "rsi6",
            "dist_ma20_pct",
            "triggered",
            "trigger_date",
            "trigger_price",
            "max_move_pct",
            "max_adverse_pct",
        ]
    ).to_csv(signals_out, index=False)

    print("\nNo oversold events in last 48h")

print(f"Saved: {current_out}")
