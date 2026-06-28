from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.config import get_assets, symbol_to_file
from lib.data_loader import load_ohlc
from lib.indicators import rsi
from lib.edge_metrics import trade_metrics

RSI_THRESHOLD = 10
ENTRY_DAYS = [1, 2, 3]
HOLD_DAYS = list(range(1, 11))

OUT_FILE = "BACKTESTS/rsi2_edge_database.csv"


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


def calculate_asset_edge(asset, path):
    if not Path(path).exists():
        print(f"Missing: {path}")
        return []

    df = load_ohlc(path)
    df["rsi2"] = rsi(df["close"], 2)
    df = df.dropna().reset_index(drop=True)

    episode_starts = detect_episode_starts(df)

    rows = []

    for entry_day in ENTRY_DAYS:
        for hold_days in HOLD_DAYS:
            returns = []

            for start_idx in episode_starts:
                entry_idx = start_idx + entry_day - 1
                exit_idx = entry_idx + hold_days

                if entry_idx >= len(df) or exit_idx >= len(df):
                    continue

                entry_price = df.loc[entry_idx, "close"]
                exit_price = df.loc[exit_idx, "close"]

                returns.append((exit_price / entry_price - 1) * 100)

            metrics = trade_metrics(returns)

            rows.append(
                {
                    "asset": asset,
                    "entry_day": entry_day,
                    "hold_days": hold_days,
                    **metrics,
                }
            )

    return rows


def build_edge_database():
    rows = []

    for symbol in get_assets("crypto"):
        asset = symbol.replace("USD", "")
        path = symbol_to_file(symbol)
        rows.extend(calculate_asset_edge(asset, path))

    return pd.DataFrame(rows)


def main():
    result = build_edge_database()

    Path("BACKTESTS").mkdir(exist_ok=True)
    result.to_csv(OUT_FILE, index=False)

    print("\nRSI2 EDGE DATABASE\n")
    print(result.sort_values("expected_value_pct", ascending=False).head(20).to_string(index=False))
    print(f"\nSaved: {OUT_FILE}")


if __name__ == "__main__":
    main()
