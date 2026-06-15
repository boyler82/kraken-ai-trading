import json
from pathlib import Path
import pandas as pd

DATA_FILE = "DATASETS/market_raw/BTCUSD_1H.json"
OUT_FILE = "BACKTESTS/btc_intraday_tp_sl_backtest.csv"

MA_PERIOD = 20
RSI_PERIOD = 6

TP_PCT = 1.0
SL_PCT = -1.5
MAX_HOLD_HOURS = 24

def load_ohlc(path):
    data = json.loads(Path(path).read_text())
    key = [k for k in data.keys() if k != "last"][0]
    df = pd.DataFrame(data[key], columns=[
        "time", "open", "high", "low", "close", "vwap", "volume", "trades"
    ])
    for c in ["open", "high", "low", "close", "vwap", "volume"]:
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

trades = []

for idx, row in signals.iterrows():
    if idx + MAX_HOLD_HOURS >= len(df):
        continue

    entry_price = row["close"]
    tp_price = entry_price * (1 + TP_PCT / 100)
    sl_price = entry_price * (1 + SL_PCT / 100)

    outcome = "TIME_EXIT"
    exit_price = df.loc[idx + MAX_HOLD_HOURS, "close"]
    exit_date = df.loc[idx + MAX_HOLD_HOURS, "date"]

    for j in range(idx + 1, idx + MAX_HOLD_HOURS + 1):
        candle = df.loc[j]

        hit_tp = candle["high"] >= tp_price
        hit_sl = candle["low"] <= sl_price

        if hit_tp and hit_sl:
            outcome = "SL_FIRST_ASSUMED"
            exit_price = sl_price
            exit_date = candle["date"]
            break

        if hit_sl:
            outcome = "SL"
            exit_price = sl_price
            exit_date = candle["date"]
            break

        if hit_tp:
            outcome = "TP"
            exit_price = tp_price
            exit_date = candle["date"]
            break

    ret_pct = (exit_price / entry_price - 1) * 100

    trades.append({
        "entry_date": row["date"],
        "entry_price": round(entry_price, 2),
        "exit_date": exit_date,
        "exit_price": round(exit_price, 2),
        "outcome": outcome,
        "return_pct": round(ret_pct, 2),
    })

result = pd.DataFrame(trades)

summary = pd.DataFrame([{
    "trades": len(result),
    "tp_pct": TP_PCT,
    "sl_pct": SL_PCT,
    "max_hold_hours": MAX_HOLD_HOURS,
    "win_rate_pct": round((result["return_pct"] > 0).mean() * 100, 2),
    "avg_return_pct": round(result["return_pct"].mean(), 2),
    "median_return_pct": round(result["return_pct"].median(), 2),
    "worst_return_pct": round(result["return_pct"].min(), 2),
    "best_return_pct": round(result["return_pct"].max(), 2),
    "tp_hits": int((result["outcome"] == "TP").sum()),
    "sl_hits": int((result["outcome"].isin(["SL", "SL_FIRST_ASSUMED"])).sum()),
    "time_exits": int((result["outcome"] == "TIME_EXIT").sum()),
}])

Path("BACKTESTS").mkdir(exist_ok=True)
result.to_csv(OUT_FILE, index=False)

print("\nSUMMARY\n")
print(summary.to_string(index=False))

print("\nOUTCOMES\n")
print(result["outcome"].value_counts().to_string())

print("\nSAMPLE TRADES\n")
print(result.tail(10).to_string(index=False))

print(f"\nSaved: {OUT_FILE}")