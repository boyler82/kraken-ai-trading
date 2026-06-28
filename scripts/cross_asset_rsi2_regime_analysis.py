from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.data_loader import load_ohlc
from lib.indicators import rsi

HOLD_DAYS = 3
RSI_THRESHOLD = 10

OUT_FILE = "BACKTESTS/cross_asset_rsi2_regime_analysis.csv"

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
    df["ma200"] = df["close"].rolling(200).mean()

    df = df.dropna().reset_index(drop=True)

    trades = []

    for i in range(len(df) - HOLD_DAYS):
        row = df.iloc[i]

        if row["rsi2"] >= RSI_THRESHOLD:
            continue

        exit_price = df.iloc[i + HOLD_DAYS]["close"]
        ret_pct = (exit_price / row["close"] - 1) * 100

        regime = "ABOVE_MA200" if row["close"] > row["ma200"] else "BELOW_MA200"

        trades.append(
            {
                "asset": symbol,
                "regime": regime,
                "return_pct": ret_pct,
            }
        )

    trades_df = pd.DataFrame(trades)

    if trades_df.empty:
        continue

    for regime, sample in trades_df.groupby("regime"):
        s = sample["return_pct"]

        rows.append(
            {
                "asset": symbol,
                "regime": regime,
                "signals": len(s),
                "win_rate_pct": round((s > 0).mean() * 100, 2),
                "avg_return_pct": round(s.mean(), 2),
                "median_return_pct": round(s.median(), 2),
                "worst_return_pct": round(s.min(), 2),
                "best_return_pct": round(s.max(), 2),
            }
        )

report = pd.DataFrame(rows)

if not report.empty:
    report = report.sort_values(["asset", "avg_return_pct"], ascending=[True, False])

Path("BACKTESTS").mkdir(exist_ok=True)

report.to_csv(OUT_FILE, index=False)

print("\nCROSS ASSET RSI2 REGIME ANALYSIS\n")
print(report.to_string(index=False))

print(f"\nSaved: {OUT_FILE}")
