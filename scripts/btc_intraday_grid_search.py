import json
from pathlib import Path

import pandas as pd

DATA_FILE = "DATASETS/market_raw/BTCUSD_1H.json"
OUT_FILE = "BACKTESTS/btc_intraday_grid_search.csv"

MA_PERIOD = 20
RSI_PERIOD = 6
MAX_HOLD_HOURS = 24

TP_VALUES = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
SL_VALUES = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]


def load_ohlc(path):
    data = json.loads(Path(path).read_text())

    key = [k for k in data.keys() if k != "last"][0]

    df = pd.DataFrame(
        data[key],
        columns=[
            "time",
            "open",
            "high",
            "low",
            "close",
            "vwap",
            "volume",
            "trades",
        ],
    )

    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c])

    df["date"] = pd.to_datetime(df["time"], unit="s")

    return df


def rsi(series, period):
    delta = series.diff()

    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()

    rs = gain / loss

    return 100 - (100 / (1 + rs))


df = load_ohlc(DATA_FILE)

df["ma20"] = df["close"].rolling(MA_PERIOD).mean()
df["rsi6"] = rsi(df["close"], RSI_PERIOD)
df["prev_high"] = df["high"].shift(1)
df["breakout"] = df["close"] > df["prev_high"]

df = df.dropna().reset_index(drop=True)

signals = df[
    (df["breakout"])
    & (df["close"] > df["ma20"])
    & (df["rsi6"] > 60)
].copy()

print(f"\nSignals found: {len(signals)}")

results = []

for tp_pct in TP_VALUES:

    for sl_pct in SL_VALUES:

        trades = []

        for idx, row in signals.iterrows():

            if idx + MAX_HOLD_HOURS >= len(df):
                continue

            entry = row["close"]

            tp_price = entry * (1 + tp_pct / 100)
            sl_price = entry * (1 - sl_pct / 100)

            exit_price = df.loc[idx + MAX_HOLD_HOURS, "close"]

            for j in range(idx + 1, idx + MAX_HOLD_HOURS + 1):

                candle = df.loc[j]

                hit_tp = candle["high"] >= tp_price
                hit_sl = candle["low"] <= sl_price

                if hit_tp and hit_sl:
                    exit_price = sl_price
                    break

                if hit_sl:
                    exit_price = sl_price
                    break

                if hit_tp:
                    exit_price = tp_price
                    break

            ret_pct = (exit_price / entry - 1) * 100

            trades.append(ret_pct)

        trades = pd.Series(trades)

        win_rate = (trades > 0).mean() * 100

        avg_return = trades.mean()

        median_return = trades.median()

        expectancy = avg_return

        results.append(
            {
                "tp_pct": tp_pct,
                "sl_pct": sl_pct,
                "trades": len(trades),
                "win_rate_pct": round(win_rate, 2),
                "avg_return_pct": round(avg_return, 4),
                "median_return_pct": round(median_return, 4),
                "expectancy_pct": round(expectancy, 4),
            }
        )

result_df = pd.DataFrame(results)

result_df = result_df.sort_values(
    by="avg_return_pct",
    ascending=False
)

Path("BACKTESTS").mkdir(exist_ok=True)

result_df.to_csv(
    OUT_FILE,
    index=False
)

print("\nTOP 20\n")

print(
    result_df.head(20).to_string(index=False)
)

print(f"\nSaved: {OUT_FILE}")