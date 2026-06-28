from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.data_loader import load_ohlc
from lib.indicators import rsi, sma

FILES = {
    "BTC": "DATASETS/market_raw/BTCUSD_D1.json",
    "ETH": "DATASETS/market_raw/ETHUSD_D1.json",
}

results = []

for symbol, path in FILES.items():
    df = load_ohlc(path)

    df["rsi2"] = rsi(df["close"], 2)
    df["ma200"] = sma(df["close"], 200)

    for horizon in [1, 3, 5, 10]:
        df[f"ret_{horizon}d"] = df["close"].shift(-horizon) / df["close"] - 1

    datasets = {
        "RSI2<10": df[df["rsi2"] < 10],
        "RSI2<10 & AboveMA200": df[(df["rsi2"] < 10) & (df["close"] > df["ma200"])],
        "RSI2<10 & BelowMA200": df[(df["rsi2"] < 10) & (df["close"] < df["ma200"])],
    }

    for name, sample in datasets.items():
        for horizon in [1, 3, 5, 10]:
            r = sample[f"ret_{horizon}d"].dropna()

            if len(r) == 0:
                continue

            results.append(
                {
                    "symbol": symbol,
                    "setup": name,
                    "horizon": horizon,
                    "signals": len(r),
                    "win_rate_pct": round((r > 0).mean() * 100, 2),
                    "avg_return_pct": round(r.mean() * 100, 2),
                    "median_return_pct": round(r.median() * 100, 2),
                    "worst_pct": round(r.min() * 100, 2),
                    "best_pct": round(r.max() * 100, 2),
                }
            )

out = pd.DataFrame(results)

Path("BACKTESTS").mkdir(exist_ok=True)

outfile = "BACKTESTS/rsi2_ma200_results.csv"

out.to_csv(outfile, index=False)

print(out.to_string(index=False))
print()
print(f"Saved: {outfile}")
