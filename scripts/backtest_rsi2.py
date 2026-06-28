from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.data_loader import load_ohlc
from lib.indicators import rsi

FILES = {
    "BTC": "DATASETS/market_raw/BTCUSD_D1.json",
    "ETH": "DATASETS/market_raw/ETHUSD_D1.json",
}

rows = []

for symbol, path in FILES.items():
    df = load_ohlc(path)
    df["rsi2"] = rsi(df["close"], 2)

    for horizon in [1, 3, 5, 10]:
        df[f"ret_{horizon}d"] = df["close"].shift(-horizon) / df["close"] - 1

    signals = df[df["rsi2"] < 10].copy()

    for horizon in [1, 3, 5, 10]:
        r = signals[f"ret_{horizon}d"].dropna()
        rows.append(
            {
                "symbol": symbol,
                "condition": "RSI2 < 10",
                "horizon": f"{horizon}d",
                "signals": len(r),
                "win_rate_pct": round((r > 0).mean() * 100, 2),
                "avg_return_pct": round(r.mean() * 100, 2),
                "median_return_pct": round(r.median() * 100, 2),
                "worst_return_pct": round(r.min() * 100, 2),
                "best_return_pct": round(r.max() * 100, 2),
            }
        )

result = pd.DataFrame(rows)

Path("BACKTESTS").mkdir(exist_ok=True)
out = Path("BACKTESTS/rsi2_backtest_results.csv")
result.to_csv(out, index=False)

print(result.to_string(index=False))
print(f"\nSaved: {out}")
