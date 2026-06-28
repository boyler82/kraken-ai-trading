from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.data_loader import load_ohlc
from lib.indicators import rsi
from lib.statistics import max_drawdown

OUT_FILE = "BACKTESTS/cross_asset_rsi2_costs.csv"

INITIAL_CAPITAL = 10_000
HOLD_DAYS = 3
RSI_THRESHOLD = 10

POSITION_SIZE = 0.05

COST_SCENARIOS = {
    "no_cost": 0.00,
    "low_cost_0.10pct_roundtrip": 0.10,
    "mid_cost_0.25pct_roundtrip": 0.25,
    "high_cost_0.50pct_roundtrip": 0.50,
}

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

        entry = row["close"]
        exit_price = exit_row["close"]

        gross_return_pct = (exit_price / entry - 1) * 100

        trades.append(
            {
                "asset": symbol,
                "entry_date": row["date"],
                "exit_date": exit_row["date"],
                "gross_return_pct": gross_return_pct,
            }
        )

trades_df = pd.DataFrame(trades)

if trades_df.empty:
    print("No trades found.")
    raise SystemExit

trades_df = trades_df.sort_values("entry_date").reset_index(drop=True)

results = []

for scenario, cost_pct in COST_SCENARIOS.items():
    capital = INITIAL_CAPITAL
    equity = []
    net_returns = []

    for _, trade in trades_df.iterrows():
        net_return_pct = trade["gross_return_pct"] - cost_pct
        net_returns.append(net_return_pct)

        capital = capital * (1 + (net_return_pct / 100) * POSITION_SIZE)

        equity.append(capital)

    equity_series = pd.Series(equity)
    net_returns_series = pd.Series(net_returns)

    results.append(
        {
            "scenario": scenario,
            "position_size_pct": POSITION_SIZE * 100,
            "roundtrip_cost_pct": cost_pct,
            "trades": len(trades_df),
            "final_capital": round(capital, 2),
            "total_return_pct": round((capital / INITIAL_CAPITAL - 1) * 100, 2),
            "win_rate_pct": round((net_returns_series > 0).mean() * 100, 2),
            "avg_net_trade_pct": round(net_returns_series.mean(), 2),
            "median_net_trade_pct": round(net_returns_series.median(), 2),
            "worst_net_trade_pct": round(net_returns_series.min(), 2),
            "best_net_trade_pct": round(net_returns_series.max(), 2),
            "max_drawdown_pct": round(max_drawdown(equity_series), 2),
        }
    )

result_df = pd.DataFrame(results)

Path("BACKTESTS").mkdir(exist_ok=True)
result_df.to_csv(OUT_FILE, index=False)

print("\nCROSS ASSET RSI2 COST ANALYSIS\n")
print(result_df.to_string(index=False))

print(f"\nSaved: {OUT_FILE}")
