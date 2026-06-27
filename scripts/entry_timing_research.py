from pathlib import Path
import sys
import pandas as pd
from lib.edge_metrics import trade_metrics

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from lib.data_loader import load_ohlc
from lib.indicators import rsi

RSI_THRESHOLD = 10
ENTRY_DAYS = [1, 2, 3]
HOLD_DAYS = list(range(1, 11))

FILES = {
    "BTC": "DATASETS/market_raw/BTCUSD_D1.json",
    "SPY": "DATASETS/market_raw/SPYx_USD_D1.json",
    "QQQ": "DATASETS/market_raw/QQQx_USD_D1.json",
    "GLD": "DATASETS/market_raw/GLDx_USD_D1.json",
    "NVDA": "DATASETS/market_raw/NVDAx_USD_D1.json",
}

OUT_FILE = "BACKTESTS/rsi2_entry_timing_matrix.csv"


def detect_episode_starts(df):
    starts = []
    in_episode = False

    for i in range(len(df)):
        oversold = df.loc[i, "rsi2"] < RSI_THRESHOLD

        if oversold and not in_episode:
            starts.append(i)
            in_episode = True

        if not oversold:
            in_episode = False

    return starts


rows = []

for asset, path in FILES.items():
    file_path = Path(path)

    if not file_path.exists():
        print(f"Missing: {path}")
        continue

    df = load_ohlc(path)
    df["rsi2"] = rsi(df["close"], 2)
    df = df.dropna().reset_index(drop=True)

    episode_starts = detect_episode_starts(df)

    for entry_day in ENTRY_DAYS:
        for hold in HOLD_DAYS:
            returns = []

            for start_idx in episode_starts:
                entry_idx = start_idx + entry_day - 1
                exit_idx = entry_idx + hold

                if exit_idx >= len(df):
                    continue

                if entry_idx >= len(df):
                    continue

                entry_price = df.loc[entry_idx, "close"]
                exit_price = df.loc[exit_idx, "close"]

                ret = (exit_price / entry_price - 1) * 100
                returns.append(ret)

            if not returns:
                continue

metrics = trade_metrics(returns)

rows.append(
    {
        "asset": asset,
        "entry_day": entry_day,
        "hold_days": hold,
        **metrics,
    }
)

result = pd.DataFrame(rows)

Path("BACKTESTS").mkdir(exist_ok=True)
result.to_csv(OUT_FILE, index=False)

print("\nRSI2 ENTRY TIMING MATRIX\n")

for asset in result["asset"].unique():
    print(f"\n=== {asset} ===")
    sample = result[result["asset"] == asset]
    pivot = sample.pivot(
        index="entry_day",
        columns="hold_days",
        values="avg_return_pct",
    )
    print(pivot.to_string())

print(f"\nSaved: {OUT_FILE}")