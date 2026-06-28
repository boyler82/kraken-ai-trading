from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.data_loader import load_ohlc
from lib.indicators import rsi

DATA_FILE = "DATASETS/market_raw/BTCUSD_1H.json"
OUT_FILE = "BACKTESTS/btc_intraday_backtest_trigger.csv"

RSI_PERIOD = 6
MA_PERIOD = 20

OVERSOLD_RSI = 30
OVERSOLD_DIST_MA20 = -1.0

TRIGGER_WINDOW = 8

HORIZONS = [1, 3, 6, 12, 24]


df = load_ohlc(DATA_FILE)

df["ma20"] = df["close"].rolling(MA_PERIOD).mean()
df["rsi6"] = rsi(df["close"], RSI_PERIOD)
df["dist_ma20_pct"] = (df["close"] / df["ma20"] - 1) * 100

df["prev_high"] = df["high"].shift(1)
df["reclaim_prev_high"] = df["close"] > df["prev_high"]

df = df.dropna().reset_index(drop=True)

trades = []

for i in range(len(df) - TRIGGER_WINDOW - max(HORIZONS)):

    row = df.iloc[i]

    oversold = (
        row["rsi6"] < OVERSOLD_RSI
        and row["dist_ma20_pct"] < OVERSOLD_DIST_MA20
    )

    if not oversold:
        continue

    trigger_found = False

    for j in range(i + 1, i + TRIGGER_WINDOW + 1):

        trigger_row = df.iloc[j]

        if trigger_row["reclaim_prev_high"]:

            trigger_found = True

            entry_idx = j
            entry_price = trigger_row["close"]
            entry_date = trigger_row["date"]

            trade = {
                "oversold_date": row["date"],
                "entry_date": entry_date,
                "entry_price": round(entry_price, 2),
            }

            for h in HORIZONS:

                exit_price = df.iloc[entry_idx + h]["close"]

                ret_pct = (
                    (exit_price / entry_price) - 1
                ) * 100

                trade[f"ret_{h}h_pct"] = round(ret_pct, 2)

            trades.append(trade)

            break

    if not trigger_found:
        continue

results = pd.DataFrame(trades)

Path("BACKTESTS").mkdir(exist_ok=True)

results.to_csv(OUT_FILE, index=False)

print("\nTRADES FOUND:", len(results))

if len(results) == 0:
    print("No triggered trades found.")
    raise SystemExit

summary = []

for h in HORIZONS:

    col = f"ret_{h}h_pct"

    s = results[col]

    summary.append(
        {
            "horizon_hours": h,
            "trades": len(s),
            "win_rate_pct": round((s > 0).mean() * 100, 2),
            "avg_return_pct": round(s.mean(), 2),
            "median_return_pct": round(s.median(), 2),
            "worst_return_pct": round(s.min(), 2),
            "best_return_pct": round(s.max(), 2),
        }
    )

summary_df = pd.DataFrame(summary)

print("\nSUMMARY\n")
print(summary_df.to_string(index=False))

print(f"\nTrades saved: {OUT_FILE}")
