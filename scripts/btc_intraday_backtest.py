import json
from pathlib import Path
import pandas as pd

DATA_FILE = "DATASETS/market_raw/BTCUSD_1H.json"
OUT_FILE = "BACKTESTS/btc_intraday_backtest.csv"

RSI_PERIOD = 6
MA_PERIOD = 20

OVERSOLD_RSI = 30
OVERSOLD_DIST_MA20 = -1.0

HORIZONS = [1, 3, 6, 12, 24]


def load_ohlc(path):
    data = json.loads(Path(path).read_text())
    key = [k for k in data.keys() if k != "last"][0]

    df = pd.DataFrame(
        data[key],
        columns=["time", "open", "high", "low", "close", "vwap", "volume", "trades"],
    )

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
df["dist_ma20_pct"] = (df["close"] / df["ma20"] - 1) * 100

df = df.dropna().reset_index(drop=True)

signals = df[
    (df["rsi6"] < OVERSOLD_RSI)
    & (df["dist_ma20_pct"] < OVERSOLD_DIST_MA20)
].copy()

rows = []

for h in HORIZONS:
    returns = []

    for idx, row in signals.iterrows():
        future_idx = idx + h

        if future_idx >= len(df):
            continue

        ret = df.loc[future_idx, "close"] / row["close"] - 1
        returns.append(ret)

    if not returns:
        continue

    s = pd.Series(returns)

    rows.append(
        {
            "setup": f"RSI6<{OVERSOLD_RSI} & dist_ma20<{OVERSOLD_DIST_MA20}%",
            "timeframe": "1H",
            "horizon_hours": h,
            "signals": len(s),
            "win_rate_pct": round((s > 0).mean() * 100, 2),
            "avg_return_pct": round(s.mean() * 100, 2),
            "median_return_pct": round(s.median() * 100, 2),
            "worst_return_pct": round(s.min() * 100, 2),
            "best_return_pct": round(s.max() * 100, 2),
        }
    )

result = pd.DataFrame(rows)

Path("BACKTESTS").mkdir(exist_ok=True)
result.to_csv(OUT_FILE, index=False)

print(result.to_string(index=False))
print(f"\nSaved: {OUT_FILE}")
