from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.data_loader import load_ohlc
from lib.indicators import rsi
from lib.statistics import max_drawdown

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
                "exit_date": exit_row["date"],
                "return_pct": ret,
            }
        )

signals = pd.DataFrame(all_signals)

results = []

for portfolio_name, assets in PORTFOLIOS.items():

    subset = signals[
        signals["asset"].isin(assets)
    ].sort_values("entry_date").reset_index(drop=True)

    if subset.empty:
        continue

    events = []

    for trade_id, trade in subset.iterrows():
        events.append(
            {
                "date": trade["entry_date"],
                "kind": "entry",
                "trade_id": trade_id,
            }
        )
        events.append(
            {
                "date": trade["exit_date"],
                "kind": "exit",
                "trade_id": trade_id,
            }
        )

    events_df = pd.DataFrame(events).sort_values(
        ["date", "kind"],
        ascending=[True, False],
    ).reset_index(drop=True)

    cash = INITIAL_CAPITAL
    equity_rows = []
    open_positions = {}

    for _, event in events_df.iterrows():
        trade = subset.loc[event["trade_id"]]

        if event["kind"] == "entry":
            allocation = cash * POSITION_SIZE
            if allocation <= 0:
                continue

            cash -= allocation
            open_positions[event["trade_id"]] = {
                "allocation": allocation,
                "asset": trade["asset"],
                "entry_date": trade["entry_date"],
            }
            equity_rows.append(
                {
                    "date": event["date"],
                    "capital": cash + sum(
                        pos["allocation"] for pos in open_positions.values()
                    ),
                }
            )
            continue

        position = open_positions.pop(event["trade_id"], None)
        if position is None:
            continue

        ret = trade["return_pct"] / 100
        cash += position["allocation"] * (1 + ret)
        equity_rows.append(
            {
                "date": event["date"],
                "capital": cash + sum(
                    pos["allocation"] for pos in open_positions.values()
                ),
            }
        )

    capital = cash + sum(pos["allocation"] for pos in open_positions.values())
    eq = pd.Series([row["capital"] for row in equity_rows])

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
