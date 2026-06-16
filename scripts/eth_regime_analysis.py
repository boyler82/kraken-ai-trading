import json
from pathlib import Path
import pandas as pd

DATA_FILE = "DATASETS/market_raw/ETHUSD_D1.json"
OUT_FILE = "BACKTESTS/eth_regime_analysis.csv"

RSI_THRESHOLD = 10
HOLDING_DAYS = 3


def load_ohlc(path):
    data = json.loads(Path(path).read_text())
    key = [k for k in data.keys() if k != "last"][0]

    df = pd.DataFrame(
        data[key],
        columns=["time", "open", "high", "low", "close", "vwap", "volume", "trades"],
    )

    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c])

    df["date"] = pd.to_datetime(df["time"], unit="s")
    return df


def rsi(series, period=2):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def atr(df, period=14):
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.rolling(period).mean()


df = load_ohlc(DATA_FILE)

df["rsi2"] = rsi(df["close"], 2)
df["ma200"] = df["close"].rolling(200).mean()
df["atr14"] = atr(df, 14)
df["atr_pct"] = df["atr14"] / df["close"] * 100

df = df.dropna().reset_index(drop=True)

atr_median = df["atr_pct"].median()

df["regime_ma200"] = df["close"].apply(lambda x: "ABOVE_MA200")  # placeholder
df.loc[df["close"] < df["ma200"], "regime_ma200"] = "BELOW_MA200"

df["regime_volatility"] = df["atr_pct"].apply(
    lambda x: "HIGH_VOL" if x > atr_median else "LOW_VOL"
)

df["signal"] = df["rsi2"] < RSI_THRESHOLD

trades = []

for i in range(len(df) - HOLDING_DAYS):
    row = df.iloc[i]

    if not row["signal"]:
        continue

    exit_row = df.iloc[i + HOLDING_DAYS]

    ret_pct = (exit_row["close"] / row["close"] - 1) * 100

    trades.append(
        {
            "entry_date": row["date"],
            "entry_price": round(row["close"], 2),
            "exit_date": exit_row["date"],
            "exit_price": round(exit_row["close"], 2),
            "return_pct": round(ret_pct, 2),
            "regime_ma200": row["regime_ma200"],
            "regime_volatility": row["regime_volatility"],
            "atr_pct": round(row["atr_pct"], 2),
        }
    )

trades_df = pd.DataFrame(trades)

results = []

for group_name in ["regime_ma200", "regime_volatility"]:
    for regime, sample in trades_df.groupby(group_name):
        s = sample["return_pct"]

        results.append(
            {
                "group": group_name,
                "regime": regime,
                "trades": len(sample),
                "win_rate_pct": round((s > 0).mean() * 100, 2),
                "avg_return_pct": round(s.mean(), 2),
                "median_return_pct": round(s.median(), 2),
                "worst_return_pct": round(s.min(), 2),
                "best_return_pct": round(s.max(), 2),
            }
        )

summary = pd.DataFrame(results)

Path("BACKTESTS").mkdir(exist_ok=True)

summary.to_csv(OUT_FILE, index=False)

print("\nETH REGIME ANALYSIS\n")
print(summary.to_string(index=False))

print(f"\nSaved: {OUT_FILE}")