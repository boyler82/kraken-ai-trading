from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.data_loader import load_ohlc
from lib.indicators import rsi

DATA_FILE = "DATASETS/market_raw/BTCUSD_1H.json"
OUT_FILE = "BACKTESTS/btc_intraday_momentum_backtest.csv"

MA_PERIOD = 20
RSI_PERIOD = 6
HORIZONS = [1, 3, 6, 12, 24]

df = load_ohlc(DATA_FILE)

df["ma20"] = df["close"].rolling(MA_PERIOD).mean()
df["rsi6"] = rsi(df["close"], RSI_PERIOD)
df["dist_ma20_pct"] = (df["close"] / df["ma20"] - 1) * 100
df["prev_high"] = df["high"].shift(1)
df["breakout"] = df["close"] > df["prev_high"]
df["avg_volume_20"] = df["volume"].rolling(20).mean()
df["volume_expansion"] = df["volume"] > df["avg_volume_20"]

df = df.dropna().reset_index(drop=True)

setups = {
    "breakout_above_ma20": (
        (df["breakout"])
        & (df["close"] > df["ma20"])
    ),
    "breakout_above_ma20_rsi60": (
        (df["breakout"])
        & (df["close"] > df["ma20"])
        & (df["rsi6"] > 60)
    ),
    "breakout_above_ma20_volume": (
        (df["breakout"])
        & (df["close"] > df["ma20"])
        & (df["volume_expansion"])
    ),
    "strong_momentum": (
        (df["breakout"])
        & (df["close"] > df["ma20"])
        & (df["rsi6"] > 60)
        & (df["volume_expansion"])
    ),
}

rows = []

for setup_name, mask in setups.items():
    signals = df[mask].copy()

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

        rows.append({
            "setup": setup_name,
            "horizon_hours": h,
            "signals": len(s),
            "win_rate_pct": round((s > 0).mean() * 100, 2),
            "avg_return_pct": round(s.mean() * 100, 2),
            "median_return_pct": round(s.median() * 100, 2),
            "worst_return_pct": round(s.min() * 100, 2),
            "best_return_pct": round(s.max() * 100, 2),
        })

result = pd.DataFrame(rows)

Path("BACKTESTS").mkdir(exist_ok=True)
result.to_csv(OUT_FILE, index=False)

print(result.to_string(index=False))
print(f"\nSaved: {OUT_FILE}")
