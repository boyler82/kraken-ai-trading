import json
from pathlib import Path
import pandas as pd

DATA_FILE = "DATASETS/market_raw/ETHUSD_D1.json"
OUT_FILE = "BACKTESTS/eth_walk_forward_trades.csv"
SUMMARY_FILE = "BACKTESTS/eth_walk_forward_summary.csv"

INITIAL_CAPITAL = 10_000
HOLDING_DAYS = 3
RSI_THRESHOLD = 10
TRAIN_RATIO = 0.7


def load_ohlc(path):
    data = json.loads(Path(path).read_text())
    key = [k for k in data.keys() if k != "last"][0]

    df = pd.DataFrame(
        data[key],
        columns=["time", "open", "high", "low", "close", "vwap", "volume", "trades"],
    )

    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c])

    df["date"] = pd.to_datetime(df["time"], unit="s")
    return df


def rsi(series, period=2):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def atr(df, period=14):
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.rolling(period).mean()


def max_drawdown(equity_series):
    peak = equity_series.cummax()
    dd = equity_series / peak - 1
    return dd.min() * 100


def run_backtest(sample, atr_threshold, label):
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
            equity.append(
                {
                    "date": row["date"],
                    "capital": capital,
                    "signal": False,
                    "segment": label,
                }
            )
            i += 1
            continue

        exit_row = sample.iloc[i + HOLDING_DAYS]

        entry_price = row["close"]
        exit_price = exit_row["close"]

        ret = exit_price / entry_price - 1
        capital = capital * (1 + ret)

        trades.append(
            {
                "segment": label,
                "entry_date": row["date"],
                "exit_date": exit_row["date"],
                "entry_price": round(entry_price, 2),
                "exit_price": round(exit_price, 2),
                "rsi2": round(row["rsi2"], 2),
                "ma200": round(row["ma200"], 2),
                "atr_pct": round(row["atr_pct"], 2),
                "atr_threshold": round(atr_threshold, 2),
                "return_pct": round(ret * 100, 2),
                "capital_after": round(capital, 2),
            }
        )

        equity.append(
            {
                "date": exit_row["date"],
                "capital": capital,
                "signal": True,
                "segment": label,
            }
        )

        i += HOLDING_DAYS

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity)

    if trades_df.empty:
        return trades_df, {
            "segment": label,
            "trades": 0,
            "final_capital": capital,
            "total_return_pct": 0.0,
            "win_rate_pct": None,
            "avg_trade_pct": None,
            "median_trade_pct": None,
            "worst_trade_pct": None,
            "best_trade_pct": None,
            "max_drawdown_pct": None,
        }

    returns = trades_df["return_pct"] / 100

    summary = {
        "segment": label,
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

    return trades_df, summary


df = load_ohlc(DATA_FILE)

df["rsi2"] = rsi(df["close"], 2)
df["ma200"] = df["close"].rolling(200).mean()
df["atr14"] = atr(df, 14)
df["atr_pct"] = df["atr14"] / df["close"] * 100

df = df.dropna().reset_index(drop=True)

split_idx = int(len(df) * TRAIN_RATIO)

train = df.iloc[:split_idx].copy().reset_index(drop=True)
test = df.iloc[split_idx:].copy().reset_index(drop=True)

atr_threshold_train = train["atr_pct"].median()

train_trades, train_summary = run_backtest(
    train,
    atr_threshold_train,
    "TRAIN",
)

test_trades, test_summary = run_backtest(
    test,
    atr_threshold_train,
    "TEST",
)

all_trades = pd.concat([train_trades, test_trades], ignore_index=True)
summary = pd.DataFrame([train_summary, test_summary])

Path("BACKTESTS").mkdir(exist_ok=True)

all_trades.to_csv(OUT_FILE, index=False)
summary.to_csv(SUMMARY_FILE, index=False)

print("\nETH WALK-FORWARD TEST")
print(f"\nTrain ratio: {TRAIN_RATIO}")
print(f"ATR threshold from TRAIN only: {round(atr_threshold_train, 2)}%")
print("")

print(summary.to_string(index=False))

print(f"\nSaved: {OUT_FILE}")
print(f"Saved: {SUMMARY_FILE}")