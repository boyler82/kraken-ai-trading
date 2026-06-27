import json
from pathlib import Path

import pandas as pd


def load_ohlc(path):
    data = json.loads(Path(path).read_text())
    key = [k for k in data.keys() if k != "last"][0]

    df = pd.DataFrame(
        data[key],
        columns=[
            "time",
            "open",
            "high",
            "low",
            "close",
            "vwap",
            "volume",
            "trades",
        ],
    )

    for col in ["open", "high", "low", "close", "vwap", "volume", "trades"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["date"] = pd.to_datetime(df["time"], unit="s")

    return df