from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.data_loader import load_ohlc
from lib.indicators import rsi
from lib.statistics import max_drawdown

OUT_FILE = "BACKTESTS/cross_asset_rsi2_portfolio_trades.csv"
SUMMARY_FILE = "BACKTESTS/cross_asset_rsi2_portfolio_summary.csv"

INITIAL_CAPITAL = 10_000
HOLD_DAYS = 3
RSI_THRESHOLD = 10
POSITION_SIZE = 0.05
ROUNDTRIP_COST_PCT = 0.25

FILES = {
    "BTC": "DATASETS/market_raw/BTCUSD_D1.json",
    "ETH": "DATASETS/market_raw/ETHUSD_D1.json",
    "SPY": "DATASETS/market_raw/SPYx_USD_D1.json",
    "QQQ": "DATASETS/market_raw/QQQx_USD_D1.json",
    "GLD": "DATASETS/market_raw/GLDx_USD_D1.json",
    "NVDA": "DATASETS/market_raw/NVDAx_USD_D1.json",
}
trades = []

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

        exit_row = df.iloc[i + HOLD_DAYS]

        entry_price = row["close"]
        exit_price = exit_row["close"]

        ret = exit_price / entry_price - 1

        trades.append(
            {
                "asset": symbol,
                "entry_date": row["date"],
                "exit_date": exit_row["date"],
                "entry_price": round(entry_price, 2),
                "exit_price": round(exit_price, 2),
                "rsi2": round(row["rsi2"], 2),
                "return_pct": round(ret * 100, 2),
            }
        )

trades_df = pd.DataFrame(trades)

if trades_df.empty:
    print("No trades found.")
    raise SystemExit

trades_df = trades_df.sort_values("entry_date").reset_index(drop=True)

events = []

for trade_id, trade in trades_df.reset_index().iterrows():
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
    trade = trades_df.loc[event["trade_id"]]

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
                "asset": trade["asset"],
                "capital": cash + sum(
                    pos["allocation"] for pos in open_positions.values()
                ),
                "return_pct": 0.0,
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
            "asset": trade["asset"],
            "capital": cash + sum(
                pos["allocation"] for pos in open_positions.values()
            ),
            "return_pct": trade["return_pct"],
        }
    )

capital = cash + sum(pos["allocation"] for pos in open_positions.values())
equity_df = pd.DataFrame(equity_rows)

returns = trades_df["return_pct"] / 100

summary = pd.DataFrame(
    [
        {
            "model": "Cross Asset RSI2 Mean Reversion",
            "assets": ",".join(FILES.keys()),
            "trades": len(trades_df),
            "final_capital": round(capital, 2),
            "total_return_pct": round((capital / INITIAL_CAPITAL - 1) * 100, 2),
            "win_rate_pct": round((returns > 0).mean() * 100, 2),
            "avg_trade_pct": round(returns.mean() * 100, 2),
            "median_trade_pct": round(returns.median() * 100, 2),
            "worst_trade_pct": round(returns.min() * 100, 2),
            "best_trade_pct": round(returns.max() * 100, 2),
            "max_drawdown_pct": round(max_drawdown(equity_df["capital"]), 2),
        }
    ]
)

Path("BACKTESTS").mkdir(exist_ok=True)

trades_df.to_csv(OUT_FILE, index=False)
summary.to_csv(SUMMARY_FILE, index=False)

print("\nCROSS ASSET RSI2 PORTFOLIO BACKTEST\n")
print(summary.to_string(index=False))

print("\nASSET CONTRIBUTION\n")
asset_summary = (
    trades_df.groupby("asset")["return_pct"]
    .agg(
        trades="count",
        avg_return_pct="mean",
        median_return_pct="median",
        worst_return_pct="min",
        best_return_pct="max",
    )
    .reset_index()
)

asset_summary["avg_return_pct"] = asset_summary["avg_return_pct"].round(2)
asset_summary["median_return_pct"] = asset_summary["median_return_pct"].round(2)
asset_summary["worst_return_pct"] = asset_summary["worst_return_pct"].round(2)
asset_summary["best_return_pct"] = asset_summary["best_return_pct"].round(2)

print(asset_summary.to_string(index=False))

print(f"\nSaved: {OUT_FILE}")
print(f"Saved: {SUMMARY_FILE}")
