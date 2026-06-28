from pathlib import Path
import sys

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.config import get_assets, symbol_to_file
from lib.data_loader import load_ohlc

OUT = "BACKTESTS/market_regime.csv"


def atr(df, period=14):
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.rolling(period).mean()


rows = []

for symbol in get_assets("crypto"):

    asset = symbol.replace("USD", "")

    path = symbol_to_file(symbol)

    if not Path(path).exists():
        continue

    df = load_ohlc(path)

    df["ma50"] = df["close"].rolling(50).mean()
    df["ma200"] = df["close"].rolling(200).mean()

    df["atr14"] = atr(df)

    df["volatility_pct"] = df["atr14"] / df["close"] * 100

    last = df.iloc[-1]

    trend = "SIDEWAYS"

    if pd.notna(last["ma200"]):

        if last["close"] > last["ma200"]:
            trend = "BULL"

        elif last["close"] < last["ma200"]:
            trend = "BEAR"

    volatility = "LOW"

    if pd.notna(last["volatility_pct"]):

        if last["volatility_pct"] > 5:
            volatility = "HIGH"

    rows.append(
        {
            "asset": asset,
            "date": last["date"].date(),
            "close": round(last["close"], 2),
            "ma50": round(last["ma50"], 2),
            "ma200": round(last["ma200"], 2),
            "trend": trend,
            "volatility": volatility,
            "atr_pct": round(last["volatility_pct"], 2),
        }
    )

result = pd.DataFrame(rows)

Path("BACKTESTS").mkdir(exist_ok=True)

result.to_csv(OUT, index=False)

print("\nMARKET REGIME\n")

print(result.to_string(index=False))

print(f"\nSaved: {OUT}")
