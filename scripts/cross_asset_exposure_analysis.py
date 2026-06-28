from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.data_loader import load_ohlc
from lib.indicators import rsi

OUT_FILE = "BACKTESTS/cross_asset_exposure_analysis.csv"
SUMMARY_FILE = "BACKTESTS/cross_asset_exposure_summary.csv"

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
positions = []

for symbol, file_path in FILES.items():
    path = Path(file_path)

    if not path.exists():
        print(f"Missing: {file_path}")
        continue

    df = load_ohlc(path)
    df["rsi2"] = rsi(df["close"], 2)
    df = df.dropna().reset_index(drop=True)

    for i in range(len(df) - HOLD_DAYS):
        row = df.iloc[i]

        if row["rsi2"] >= RSI_THRESHOLD:
            continue

        entry_date = row["date"]
        exit_date = df.iloc[i + HOLD_DAYS]["date"]

        positions.append(
            {
                "asset": symbol,
                "entry_date": entry_date,
                "exit_date": exit_date,
            }
        )

positions_df = pd.DataFrame(positions)

if positions_df.empty:
    print("No positions found.")
    raise SystemExit

all_dates = pd.date_range(
    start=positions_df["entry_date"].min(),
    end=positions_df["exit_date"].max(),
    freq="D",
)

daily_rows = []

for date in all_dates:
    active = positions_df[
        (positions_df["entry_date"] <= date)
        & (positions_df["exit_date"] > date)
    ]

    daily_rows.append(
        {
            "date": date,
            "active_positions": len(active),
            "active_assets": ",".join(sorted(active["asset"].unique())),
        }
    )

daily_df = pd.DataFrame(daily_rows)

summary = pd.DataFrame(
    [
        {
            "total_positions": len(positions_df),
            "days_analyzed": len(daily_df),
            "avg_active_positions": round(daily_df["active_positions"].mean(), 2),
            "median_active_positions": round(daily_df["active_positions"].median(), 2),
            "max_active_positions": int(daily_df["active_positions"].max()),
            "days_with_0_positions": int((daily_df["active_positions"] == 0).sum()),
            "days_with_1_position": int((daily_df["active_positions"] == 1).sum()),
            "days_with_2_positions": int((daily_df["active_positions"] == 2).sum()),
            "days_with_3_positions": int((daily_df["active_positions"] == 3).sum()),
            "days_with_4plus_positions": int((daily_df["active_positions"] >= 4).sum()),
        }
    ]
)

Path("BACKTESTS").mkdir(exist_ok=True)

daily_df.to_csv(OUT_FILE, index=False)
summary.to_csv(SUMMARY_FILE, index=False)

print("\nCROSS ASSET EXPOSURE ANALYSIS\n")
print(summary.to_string(index=False))

print("\nTOP EXPOSURE DAYS\n")
print(
    daily_df.sort_values("active_positions", ascending=False)
    .head(20)
    .to_string(index=False)
)

print(f"\nSaved: {OUT_FILE}")
print(f"Saved: {SUMMARY_FILE}")
