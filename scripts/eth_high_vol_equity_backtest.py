from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.data_loader import load_ohlc
from lib.indicators import atr, rsi
from lib.statistics import max_drawdown

DATA_FILE = "DATASETS/market_raw/ETHUSD_D1.json"
OUT_FILE = "BACKTESTS/eth_high_vol_equity_backtest.csv"
SUMMARY_FILE = "BACKTESTS/eth_high_vol_equity_summary.csv"

INITIAL_CAPITAL = 10_000
RISK_FRACTION = 1.0
HOLDING_DAYS = 3
RSI_THRESHOLD = 10
df = load_ohlc(DATA_FILE)

df["rsi2"] = rsi(df["close"], 2)
df["ma200"] = df["close"].rolling(200).mean()
df["atr14"] = atr(df, 14)
df["atr_pct"] = df["atr14"] / df["close"] * 100

df = df.dropna().reset_index(drop=True)

split_idx = int(len(df) * 0.7)
train = df.iloc[:split_idx].copy().reset_index(drop=True)
test = df.iloc[split_idx:].copy().reset_index(drop=True)

atr_median = train["atr_pct"].median()

capital = INITIAL_CAPITAL
equity = []
trades = []

i = 0

while i < len(test) - HOLDING_DAYS:
    row = test.iloc[i]

    high_vol = row["atr_pct"] > atr_median

    signal = (
        row["rsi2"] < RSI_THRESHOLD
        and row["close"] > row["ma200"]
        and high_vol
    )

    if not signal:
        equity.append(
            {
                "date": row["date"],
                "capital": capital,
                "trade_return_pct": 0.0,
                "signal": False,
            }
        )
        i += 1
        continue

    entry_price = row["close"]
    exit_row = test.iloc[i + HOLDING_DAYS]
    exit_price = exit_row["close"]

    trade_return = exit_price / entry_price - 1
    capital = capital * (1 + trade_return * RISK_FRACTION)

    trades.append(
        {
            "entry_date": row["date"],
            "exit_date": exit_row["date"],
            "entry_price": round(entry_price, 2),
            "exit_price": round(exit_price, 2),
            "rsi2": round(row["rsi2"], 2),
            "ma200": round(row["ma200"], 2),
            "atr_pct": round(row["atr_pct"], 2),
            "atr_median": round(atr_median, 2),
            "return_pct": round(trade_return * 100, 2),
            "capital_after": round(capital, 2),
        }
    )

    equity.append(
        {
            "date": exit_row["date"],
            "capital": capital,
            "trade_return_pct": trade_return * 100,
            "signal": True,
        }
    )

    i += HOLDING_DAYS

trades_df = pd.DataFrame(trades)
equity_df = pd.DataFrame(equity)

if trades_df.empty:
    print("No trades found.")
    raise SystemExit

returns = trades_df["return_pct"] / 100

summary = pd.DataFrame(
    [
        {
            "model": "ETH_D1_RSI2_MA200_HIGH_VOL",
            "trades": len(trades_df),
            "final_capital": round(capital, 2),
            "total_return_pct": round((capital / INITIAL_CAPITAL - 1) * 100, 2),
            "win_rate_pct": round((returns > 0).mean() * 100, 2),
            "avg_trade_pct": round(returns.mean() * 100, 2),
            "median_trade_pct": round(returns.median() * 100, 2),
            "worst_trade_pct": round(returns.min() * 100, 2),
            "best_trade_pct": round(returns.max() * 100, 2),
            "max_drawdown_pct": round(max_drawdown(equity_df["capital"]), 2),
            "atr_median_pct": round(atr_median, 2),
        }
    ]
)

Path("BACKTESTS").mkdir(exist_ok=True)

trades_df.to_csv(OUT_FILE, index=False)
summary.to_csv(SUMMARY_FILE, index=False)

print("\nSUMMARY\n")
print(summary.to_string(index=False))

print("\nTRADES\n")
print(trades_df.to_string(index=False))

print(f"\nSaved: {OUT_FILE}")
print(f"Saved: {SUMMARY_FILE}")
