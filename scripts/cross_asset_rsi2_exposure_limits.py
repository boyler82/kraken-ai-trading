import json
from pathlib import Path
import pandas as pd

OUT_FILE = "BACKTESTS/cross_asset_rsi2_exposure_limits.csv"

INITIAL_CAPITAL = 10_000
HOLD_DAYS = 3
RSI_THRESHOLD = 10
POSITION_SIZE = 0.05
ROUNDTRIP_COST_PCT = 0.25

MAX_ACTIVE_POSITIONS = [3, 5, 8, 12, 9999]

FILES = {
    "BTC": "DATASETS/market_raw/BTCUSD_D1.json",
    "ETH": "DATASETS/market_raw/ETHUSD_D1.json",
    "SPY": "DATASETS/market_raw/SPYx_USD_D1.json",
    "QQQ": "DATASETS/market_raw/QQQx_USD_D1.json",
    "GLD": "DATASETS/market_raw/GLDx_USD_D1.json",
    "NVDA": "DATASETS/market_raw/NVDAx_USD_D1.json",
}


def load_ohlc(path):
    data = json.loads(Path(path).read_text())
    key = [k for k in data.keys() if k != "last"][0]

    df = pd.DataFrame(
        data[key],
        columns=["time", "open", "high", "low", "close", "vwap", "volume", "trades"],
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


signals = []

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

        gross_return_pct = (exit_row["close"] / row["close"] - 1) * 100
        net_return_pct = gross_return_pct - ROUNDTRIP_COST_PCT

        signals.append(
            {
                "asset": symbol,
                "entry_date": row["date"],
                "exit_date": exit_row["date"],
                "gross_return_pct": gross_return_pct,
                "net_return_pct": net_return_pct,
            }
        )

signals_df = pd.DataFrame(signals)

if signals_df.empty:
    print("No signals found.")
    raise SystemExit

signals_df = signals_df.sort_values("entry_date").reset_index(drop=True)

results = []

for max_positions in MAX_ACTIVE_POSITIONS:
    capital = INITIAL_CAPITAL
    equity = []
    active_positions = []
    accepted_trades = []
    skipped_trades = 0

    for _, signal in signals_df.iterrows():
        entry_date = signal["entry_date"]
        exit_date = signal["exit_date"]

        active_positions = [
            pos for pos in active_positions
            if pos["exit_date"] > entry_date
        ]

        if len(active_positions) >= max_positions:
            skipped_trades += 1
            continue

        ret = signal["net_return_pct"] / 100
        capital = capital * (1 + ret * POSITION_SIZE)

        active_positions.append(
            {
                "asset": signal["asset"],
                "entry_date": entry_date,
                "exit_date": exit_date,
            }
        )

        accepted_trades.append(signal)

        equity.append(
            {
                "date": exit_date,
                "capital": capital,
                "active_positions_after_entry": len(active_positions),
            }
        )

    equity_df = pd.DataFrame(equity)
    accepted_df = pd.DataFrame(accepted_trades)

    if accepted_df.empty:
        continue

    returns = accepted_df["net_return_pct"] / 100

    results.append(
        {
            "max_active_positions": (
                "unlimited" if max_positions == 9999 else max_positions
            ),
            "position_size_pct": POSITION_SIZE * 100,
            "roundtrip_cost_pct": ROUNDTRIP_COST_PCT,
            "accepted_trades": len(accepted_df),
            "skipped_trades": skipped_trades,
            "final_capital": round(capital, 2),
            "total_return_pct": round((capital / INITIAL_CAPITAL - 1) * 100, 2),
            "win_rate_pct": round((returns > 0).mean() * 100, 2),
            "avg_net_trade_pct": round(returns.mean() * 100, 2),
            "median_net_trade_pct": round(returns.median() * 100, 2),
            "worst_net_trade_pct": round(returns.min() * 100, 2),
            "best_net_trade_pct": round(returns.max() * 100, 2),
            "max_drawdown_pct": round(max_drawdown(equity_df["capital"]), 2),
        }
    )

result_df = pd.DataFrame(results)

Path("BACKTESTS").mkdir(exist_ok=True)
result_df.to_csv(OUT_FILE, index=False)

print("\nCROSS ASSET RSI2 EXPOSURE LIMITS\n")
print(result_df.to_string(index=False))

print(f"\nSaved: {OUT_FILE}")