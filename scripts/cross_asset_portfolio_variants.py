import json
from pathlib import Path
import pandas as pd

INITIAL_CAPITAL = 10000
POSITION_SIZE = 0.05
HOLD_DAYS = 3
RSI_THRESHOLD = 10
ROUNDTRIP_COST = 0.25

FILES = {
    "BTC": "DATASETS/market_raw/BTCUSD_D1.json",
    "ETH": "DATASETS/market_raw/ETHUSD_D1.json",
    "SPY": "DATASETS/market_raw/SPYx_USD_D1.json",
    "QQQ": "DATASETS/market_raw/QQQx_USD_D1.json",
    "GLD": "DATASETS/market_raw/GLDx_USD_D1.json",
    "NVDA": "DATASETS/market_raw/NVDAx_USD_D1.json",
}

PORTFOLIOS = {
    "ALL": ["BTC", "ETH", "SPY", "QQQ", "GLD", "NVDA"],
    "NO_ETH": ["BTC", "SPY", "QQQ", "GLD", "NVDA"],
    "NO_BTC": ["ETH", "SPY", "QQQ", "GLD", "NVDA"],
    "CRYPTO_ONLY": ["BTC", "ETH"],
    "XSTOCKS_ONLY": ["SPY", "QQQ", "GLD", "NVDA"],
    "BTC_ONLY": ["BTC"],
    "ETH_ONLY": ["ETH"],
}


def load_ohlc(path):
    data = json.loads(Path(path).read_text())
    key = [k for k in data.keys() if k != "last"][0]

    df = pd.DataFrame(
        data[key],
        columns=[
            "time","open","high","low","close",
            "vwap","volume","trades"
        ]
    )

    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c])

    df["date"] = pd.to_datetime(df["time"], unit="s")
    return df


def rsi(series, period=2):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def max_drawdown(series):
    peak = series.cummax()
    dd = series / peak - 1
    return dd.min() * 100


all_signals = []

for asset, path in FILES.items():

    df = load_ohlc(path)

    df["rsi2"] = rsi(df["close"], 2)
    df = df.dropna().reset_index(drop=True)

    for i in range(len(df) - HOLD_DAYS):

        row = df.iloc[i]

        if row["rsi2"] >= RSI_THRESHOLD:
            continue

        exit_row = df.iloc[i + HOLD_DAYS]

        ret = (
            exit_row["close"] / row["close"] - 1
        ) * 100 - ROUNDTRIP_COST

        all_signals.append(
            {
                "asset": asset,
                "entry_date": row["date"],
                "return_pct": ret,
            }
        )

signals = pd.DataFrame(all_signals)

results = []

for portfolio_name, assets in PORTFOLIOS.items():

    subset = signals[
        signals["asset"].isin(assets)
    ].sort_values("entry_date")

    if subset.empty:
        continue

    capital = INITIAL_CAPITAL
    equity = []

    for _, trade in subset.iterrows():

        capital *= (
            1
            + (trade["return_pct"] / 100)
            * POSITION_SIZE
        )

        equity.append(capital)

    eq = pd.Series(equity)

    results.append(
        {
            "portfolio": portfolio_name,
            "assets": len(assets),
            "trades": len(subset),
            "final_capital": round(capital, 2),
            "total_return_pct": round(
                (capital / INITIAL_CAPITAL - 1) * 100,
                2,
            ),
            "avg_trade_pct": round(
                subset["return_pct"].mean(),
                2,
            ),
            "median_trade_pct": round(
                subset["return_pct"].median(),
                2,
            ),
            "max_drawdown_pct": round(
                max_drawdown(eq),
                2,
            ),
        }
    )

result_df = pd.DataFrame(results)

result_df = result_df.sort_values(
    "total_return_pct",
    ascending=False,
)

print("\nPORTFOLIO VARIANTS\n")
print(result_df.to_string(index=False))

Path("BACKTESTS").mkdir(exist_ok=True)

result_df.to_csv(
    "BACKTESTS/cross_asset_portfolio_variants.csv",
    index=False,
)

print(
    "\nSaved: BACKTESTS/cross_asset_portfolio_variants.csv"
)
