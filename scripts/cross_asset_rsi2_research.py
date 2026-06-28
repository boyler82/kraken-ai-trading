from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.data_loader import load_ohlc
from lib.indicators import rsi

HOLD_DAYS = 3
RSI_THRESHOLD = 10

FILES = {
    "BTC": "DATASETS/market_raw/BTCUSD_D1.json",
    "ETH": "DATASETS/market_raw/ETHUSD_D1.json",
    "SPY": "DATASETS/market_raw/SPYx_USD_D1.json",
    "QQQ": "DATASETS/market_raw/QQQx_USD_D1.json",
    "GLD": "DATASETS/market_raw/GLDx_USD_D1.json",
    "NVDA": "DATASETS/market_raw/NVDAx_USD_D1.json",
}


rows = []

for symbol, file_path in FILES.items():

    path = Path(file_path)

    if not path.exists():
        print(f"Missing: {file_path}")
        continue

    df = load_ohlc(file_path)

    df["rsi2"] = rsi(df["close"], 2)
    df = df.dropna().reset_index(drop=True)

    returns = []

    for i in range(len(df) - HOLD_DAYS):

        row = df.iloc[i]

        if row["rsi2"] >= RSI_THRESHOLD:
            continue

        entry = row["close"]
        exit_price = df.iloc[i + HOLD_DAYS]["close"]

        trade_return = (exit_price / entry - 1) * 100

        returns.append(trade_return)

    if len(returns) == 0:
        continue

    s = pd.Series(returns)

    expectancy = s.mean()

    rows.append(
        {
            "asset": symbol,
            "signals": len(s),
            "win_rate_pct": round((s > 0).mean() * 100, 2),
            "avg_return_pct": round(s.mean(), 2),
            "median_return_pct": round(s.median(), 2),
            "worst_return_pct": round(s.min(), 2),
            "best_return_pct": round(s.max(), 2),
            "expectancy_pct": round(expectancy, 2),
        }
    )

report = pd.DataFrame(rows)

if not report.empty:
    report = report.sort_values(
        "expectancy_pct",
        ascending=False,
    )

Path("BACKTESTS").mkdir(exist_ok=True)

out_file = "BACKTESTS/cross_asset_rsi2_research.csv"

report.to_csv(out_file, index=False)

print("\nCROSS ASSET RSI2 RESEARCH\n")
print(report.to_string(index=False))

print(f"\nSaved: {out_file}")
