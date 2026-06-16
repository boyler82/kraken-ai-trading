import json
from pathlib import Path
import pandas as pd

DATA_FILE = "DATASETS/market_raw/ETHUSD_D1.json"
OUT_FILE = "BACKTESTS/eth_walk_forward_matrix.csv"

INITIAL_CAPITAL = 10_000
HOLDING_DAYS = 3
RSI_THRESHOLD = 10

SPLITS = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]


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
    if equity_series.empty:
        return None

    peak = equity_series.cummax()
    dd = equity_series / peak - 1
    return dd.min() * 100


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