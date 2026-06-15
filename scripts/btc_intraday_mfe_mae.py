import json
from pathlib import Path
import pandas as pd

DATA_FILE = "DATASETS/market_raw/BTCUSD_1H.json"
OUT_FILE = "BACKTESTS/btc_intraday_mfe_mae.csv"

MA_PERIOD = 20
RSI_PERIOD = 6
LOOKAHEAD = 24

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
df["avg_volume_20"] = df["volume"].rolling(20).mean()
df["volume_expansion"] = df["volume"] > df["avg_volume_20"]

df = df.dropna().reset_index(drop=True)

signals = df[
    (df["breakout"])
    & (df["close"] > df["ma20"])
    & (df["rsi6"] > 60)
].copy()

rows = []

for idx, row in signals.iterrows():
    if idx + LOOKAHEAD >= len(df):
        continue

    entry_price = row["close"]
    future = df.loc[idx + 1 : idx + LOOKAHEAD].copy()

    mfe_pct = (future["high"].max() / entry_price - 1) * 100
    mae_pct = (future["low"].min() / entry_price - 1) * 100
    close_24h_pct = (df.loc[idx + LOOKAHEAD, "close"] / entry_price - 1) * 100

    rows.append({
        "entry_date": row["date"],
        "entry_price": round(entry_price, 2),
        "mfe_24h_pct": round(mfe_pct, 2),
        "mae_24h_pct": round(mae_pct, 2),
        "close_24h_pct": round(close_24h_pct, 2),
    })

result = pd.DataFrame(rows)

summary = pd.DataFrame([{
    "signals": len(result),
    "avg_mfe_24h_pct": round(result["mfe_24h_pct"].mean(), 2),
    "median_mfe_24h_pct": round(result["mfe_24h_pct"].median(), 2),
    "avg_mae_24h_pct": round(result["mae_24h_pct"].mean(), 2),
    "median_mae_24h_pct": round(result["mae_24h_pct"].median(), 2),
    "avg_close_24h_pct": round(result["close_24h_pct"].mean(), 2),
    "median_close_24h_pct": round(result["close_24h_pct"].median(), 2),
    "pct_mfe_gt_1": round((result["mfe_24h_pct"] > 1).mean() * 100, 2),
    "pct_mfe_gt_2": round((result["mfe_24h_pct"] > 2).mean() * 100, 2),
}])

Path("BACKTESTS").mkdir(exist_ok=True)
result.to_csv(OUT_FILE, index=False)

print("\nSUMMARY\n")
print(summary.to_string(index=False))

print("\nSAMPLE TRADES\n")
print(result.tail(10).to_string(index=False))

print(f"\nSaved: {OUT_FILE}")