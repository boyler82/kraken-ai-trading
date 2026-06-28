from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.data_loader import load_ohlc
from lib.indicators import atr, rsi
from lib.statistics import max_drawdown

DATA_FILE = "DATASETS/market_raw/ETHUSD_D1.json"
OUT_FILE = "BACKTESTS/eth_walk_forward_matrix.csv"

INITIAL_CAPITAL = 10_000
HOLDING_DAYS = 3
RSI_THRESHOLD = 10

SPLITS = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]
def run_backtest(sample, atr_threshold):
    capital = INITIAL_CAPITAL
    trades = []
    equity = []

    i = 0

    while i < len(sample) - HOLDING_DAYS:
        row = sample.iloc[i]

        signal = (
            row["rsi2"] < RSI_THRESHOLD
            and row["close"] > row["ma200"]
            and row["atr_pct"] > atr_threshold
        )

        if not signal:
            equity.append(capital)
            i += 1
            continue

        exit_row = sample.iloc[i + HOLDING_DAYS]

        entry = row["close"]
        exit_price = exit_row["close"]

        ret = exit_price / entry - 1
        capital = capital * (1 + ret)

        trades.append(ret * 100)
        equity.append(capital)

        i += HOLDING_DAYS

    trades_series = pd.Series(trades)
    equity_series = pd.Series(equity)

    if trades_series.empty:
        return {
            "trades": 0,
            "return_pct": 0.0,
            "win_rate_pct": None,
            "avg_trade_pct": None,
            "median_trade_pct": None,
            "max_dd_pct": None,
        }

    return {
        "trades": len(trades_series),
        "return_pct": round((capital / INITIAL_CAPITAL - 1) * 100, 2),
        "win_rate_pct": round((trades_series > 0).mean() * 100, 2),
        "avg_trade_pct": round(trades_series.mean(), 2),
        "median_trade_pct": round(trades_series.median(), 2),
        "max_dd_pct": round(max_drawdown(equity_series), 2),
    }


df = load_ohlc(DATA_FILE)

df["rsi2"] = rsi(df["close"], 2)
df["ma200"] = df["close"].rolling(200).mean()
df["atr14"] = atr(df, 14)
df["atr_pct"] = df["atr14"] / df["close"] * 100

df = df.dropna().reset_index(drop=True)

rows = []

for split in SPLITS:
    split_idx = int(len(df) * split)

    train = df.iloc[:split_idx].copy().reset_index(drop=True)
    test = df.iloc[split_idx:].copy().reset_index(drop=True)

    atr_threshold = train["atr_pct"].median()

    train_result = run_backtest(train, atr_threshold)
    test_result = run_backtest(test, atr_threshold)

    rows.append(
        {
            "split": split,
            "atr_threshold_train": round(atr_threshold, 2),

            "train_trades": train_result["trades"],
            "train_return_pct": train_result["return_pct"],
            "train_win_rate_pct": train_result["win_rate_pct"],
            "train_avg_trade_pct": train_result["avg_trade_pct"],
            "train_median_trade_pct": train_result["median_trade_pct"],
            "train_max_dd_pct": train_result["max_dd_pct"],

            "test_trades": test_result["trades"],
            "test_return_pct": test_result["return_pct"],
            "test_win_rate_pct": test_result["win_rate_pct"],
            "test_avg_trade_pct": test_result["avg_trade_pct"],
            "test_median_trade_pct": test_result["median_trade_pct"],
            "test_max_dd_pct": test_result["max_dd_pct"],
        }
    )

result = pd.DataFrame(rows)

Path("BACKTESTS").mkdir(exist_ok=True)
result.to_csv(OUT_FILE, index=False)

print("\nETH WALK-FORWARD MATRIX\n")
print(result.to_string(index=False))

print(f"\nSaved: {OUT_FILE}")
