from pathlib import Path

import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

sys.path.append(str(ROOT / "scripts"))

from lib.data_loader import load_ohlc

from lib.indicators import rsi, sma

FILES = {
    "BTC": "DATASETS/market_raw/BTCUSD_D1.json",
    "SPY": "DATASETS/market_raw/SPYx_USD_D1.json",
    "QQQ": "DATASETS/market_raw/QQQx_USD_D1.json",
    "GLD": "DATASETS/market_raw/GLDx_USD_D1.json",
    "NVDA": "DATASETS/market_raw/NVDAx_USD_D1.json",
}

MODEL = {
    "name": "Cross Asset RSI2 v1 — NO_ETH",
    "status": "PROMISING_RESEARCH",
    "condition": "RSI2 < 10",
    "exit": "3 days",
    "position_size_pct": 5.0,
    "roundtrip_cost_pct": 0.25,
    "historical_trades": 484,
    "historical_total_return": 8.43,
    "historical_avg_trade": 0.34,
    "historical_median_trade": 0.42,
    "historical_max_drawdown": -2.15,
}


rows = []

for symbol, file_path in FILES.items():
    df = load_ohlc(file_path)

    df["rsi2"] = rsi(df["close"], 2)
    df["ma20"] = sma(df["close"], 20)
    df["dist_ma20_pct"] = (df["close"] / df["ma20"] - 1) * 100

    df = df.dropna().reset_index(drop=True)

    last = df.iloc[-1]

    signal = last["rsi2"] < 10
    near_signal = last["rsi2"] < 25

    rows.append(
        {
            "asset": symbol,
            "date": str(last["date"].date()),
            "close": round(last["close"], 2),
            "rsi2": round(last["rsi2"], 2),
            "ma20": round(last["ma20"], 2),
            "dist_ma20_pct": round(last["dist_ma20_pct"], 2),
            "signal": bool(signal),
            "suggested_position_size_pct": MODEL["position_size_pct"] if signal else 0,
            "decision": "SIGNAL" if signal else "NO SIGNAL",
            "near_signal": bool(near_signal),
        }
    )

report = pd.DataFrame(rows)
signals = report[report["signal"] == True].copy()
near_signals = report[
    (report["near_signal"] == True)
    & (report["signal"] == False)
].copy()

today = pd.Timestamp.today().strftime("%Y-%m-%d")

Path("DAILY_REPORTS").mkdir(exist_ok=True)

csv_out = Path(f"DAILY_REPORTS/{today}_portfolio_decision_engine.csv")
md_out = Path(f"DAILY_REPORTS/{today}_portfolio_decision_engine.md")

report.to_csv(csv_out, index=False)

lines = []
lines.append("# Portfolio Decision Engine")
lines.append("")
lines.append(f"Date: {today}")
lines.append("")
lines.append("## Model")
lines.append("")
lines.append(f"- Name: {MODEL['name']}")
lines.append(f"- Status: {MODEL['status']}")
lines.append(f"- Condition: {MODEL['condition']}")
lines.append(f"- Exit: {MODEL['exit']}")
lines.append(f"- Position size: {MODEL['position_size_pct']}% per signal")
lines.append(f"- Roundtrip cost assumption: {MODEL['roundtrip_cost_pct']}%")
lines.append("")
lines.append("## Historical Research")
lines.append("")
lines.append(f"- Trades: {MODEL['historical_trades']}")
lines.append(f"- Total return: {MODEL['historical_total_return']}%")
lines.append(f"- Average trade: {MODEL['historical_avg_trade']}%")
lines.append(f"- Median trade: {MODEL['historical_median_trade']}%")
lines.append(f"- Max drawdown: {MODEL['historical_max_drawdown']}%")
lines.append("")
lines.append("## Current Signals")
lines.append("## Watchlist Near Signal")
lines.append("")

if near_signals.empty:
    lines.append("No markets near signal today.")
else:
    for _, row in near_signals.iterrows():
        lines.append(f"### {row['asset']}")
        lines.append("")
        lines.append(f"- Decision: **WATCH**")
        lines.append(f"- Close: {row['close']}")
        lines.append(f"- RSI(2): {row['rsi2']}")
        lines.append(f"- Distance from MA20: {row['dist_ma20_pct']}%")
        lines.append("")
lines.append("")

if signals.empty:
    lines.append("No active portfolio signals today.")
else:
    for _, row in signals.iterrows():
        lines.append(f"### {row['asset']}")
        lines.append("")
        lines.append(f"- Decision: **SIGNAL**")
        lines.append(f"- Close: {row['close']}")
        lines.append(f"- RSI(2): {row['rsi2']}")
        lines.append(f"- Distance from MA20: {row['dist_ma20_pct']}%")
        lines.append(f"- Suggested position size: {row['suggested_position_size_pct']}%")
        lines.append("")

lines.append("## Full Market Scan")
lines.append("")

for _, row in report.iterrows():
    lines.append(
        f"- {row['asset']}: {row['decision']} | Close: {row['close']} | RSI2: {row['rsi2']} | Dist MA20: {row['dist_ma20_pct']}%"
    )

lines.append("")
lines.append("## Process Note")
lines.append("")
lines.append("- This is a research model, not a production strategy.")
lines.append("- ETH is excluded from this portfolio variant due to weaker portfolio contribution.")
lines.append("- Manual risk review is required before any trade.")
lines.append("- This report is analytical, not financial advice.")
lines.append("")

md_out.write_text("\n".join(lines))

print("\nPORTFOLIO DECISION ENGINE\n")
print(report.to_string(index=False))

print(f"\nActive signals: {len(signals)}")
print(f"Saved: {csv_out}")
print(f"Saved: {md_out}")