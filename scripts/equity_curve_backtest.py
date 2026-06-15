import json
from pathlib import Path
import pandas as pd

OUT_FILE = "BACKTESTS/equity_curve_backtest.csv"
SUMMARY_FILE = "BACKTESTS/equity_curve_summary.csv"

INITIAL_CAPITAL = 10_000
RISK_FRACTION = 1.0

FILES = {
    "BTC": "DATASETS/market_raw/BTCUSD_D1.json",
    "ETH": "DATASETS/market_raw/ETHUSD_D1.json",
}

MODELS = {
    "BTC": {
        "name": "BTC_D1_RSI2",
        "rsi_threshold": 10,
        "holding_days": 3,
        "requires_above_ma200": False,
    },
    "ETH": {
        "name": "ETH_D1_RSI2_MA200",
        "rsi_threshold": 10,
        "holding_days": 3,
        "requires_above_ma200": True,
    },
}


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

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col])

    df["date"] = pd.to_datetime(df["time"], unit="s")
    return df


def rsi(series, period=2):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def max_drawdown(equity_series):
    peak = equity_series.cummax()
    dd = equity_series / peak - 1
    return dd.min() * 100


all_trades = []
summaries = []

for symbol, path in FILES.items():
    df = load_ohlc(path)
    model = MODELS[symbol]

    df["rsi2"] = rsi(df["close"], 2)
    df["ma200"] = df["close"].rolling(200).mean()
    df = df.dropna().reset_index(drop=True)

    capital = INITIAL_CAPITAL
    equity = []

    i = 0

    while i < len(df) - model["holding_days"]:
        row = df.iloc[i]

        signal = row["rsi2"] < model["rsi_threshold"]

        if model["requires_above_ma200"]:
            signal = signal and row["close"] > row["ma200"]

        if not signal:
            equity.append(
                {
                    "symbol": symbol,
                    "model": model["name"],
                    "date": row["date"],
                    "capital": capital,
                    "trade_return_pct": 0.0,
                    "signal": False,
                }
            )
            i += 1
            continue

        entry_price = row["close"]
        exit_row = df.iloc[i + model["holding_days"]]
        exit_price = exit_row["close"]

        trade_return = exit_price / entry_price - 1
        capital = capital * (1 + trade_return * RISK_FRACTION)

        all_trades.append(
            {
                "symbol": symbol,
                "model": model["name"],
                "entry_date": row["date"],
                "exit_date": exit_row["date"],
                "entry_price": round(entry_price, 2),
                "exit_price": round(exit_price, 2),
                "return_pct": round(trade_return * 100, 2),
                "capital_after": round(capital, 2),
            }
        )

        equity.append(
            {
                "symbol": symbol,
                "model": model["name"],
                "date": exit_row["date"],
                "capital": capital,
                "trade_return_pct": trade_return * 100,
                "signal": True,
            }
        )

        i += model["holding_days"]

    equity_df = pd.DataFrame(equity)

    trades_df = pd.DataFrame(
        [t for t in all_trades if t["symbol"] == symbol]
    )

    if trades_df.empty:
        continue

    returns = trades_df["return_pct"] / 100

    summaries.append(
        {
            "symbol": symbol,
            "model": model["name"],
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
    )

Path("BACKTESTS").mkdir(exist_ok=True)

trades_out = pd.DataFrame(all_trades)
summary_out = pd.DataFrame(summaries)

trades_out.to_csv(OUT_FILE, index=False)
summary_out.to_csv(SUMMARY_FILE, index=False)

print("\nSUMMARY\n")
print(summary_out.to_string(index=False))

print(f"\nSaved: {OUT_FILE}")
print(f"Saved: {SUMMARY_FILE}")