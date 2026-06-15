import json
from pathlib import Path
import pandas as pd

FILES = {
    "BTC": "DATASETS/market_raw/BTCUSD_D1.json",
    "ETH": "DATASETS/market_raw/ETHUSD_D1.json",
}

MODELS = {
    "BTC": {
        "model": "BTC D1 RSI2 Mean Reversion",
        "condition": "RSI2 < 10",
        "exit": "3 days",
        "historical_win_rate": 60.95,
        "historical_avg_return": 0.59,
        "historical_median_return": 0.83,
        "historical_worst_return": -10.52,
        "requires_above_ma200": False,
    },
    "ETH": {
        "model": "ETH D1 RSI2 + MA200",
        "condition": "RSI2 < 10 and Close > MA200",
        "exit": "3 days",
        "historical_win_rate": 55.00,
        "historical_avg_return": 1.05,
        "historical_median_return": 1.14,
        "historical_worst_return": -8.09,
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


def confidence_label(model, signal_active):
    if not signal_active:
        return "NONE"

    avg = model["historical_avg_return"]
    win = model["historical_win_rate"]

    if avg >= 1.0 and win >= 55:
        return "MEDIUM"

    if avg >= 0.5 and win >= 58:
        return "MEDIUM"

    return "LOW"


rows = []

for symbol, path in FILES.items():
    df = load_ohlc(path)

    df["rsi2"] = rsi(df["close"], 2)
    df["ma200"] = df["close"].rolling(200).mean()

    df = df.dropna().reset_index(drop=True)

    last = df.iloc[-1]
    model = MODELS[symbol]

    above_ma200 = last["close"] > last["ma200"]

    signal_active = last["rsi2"] < 10

    if model["requires_above_ma200"]:
        signal_active = signal_active and above_ma200

    decision = "SIGNAL" if signal_active else "NO SIGNAL"

    rows.append(
        {
            "symbol": symbol,
            "date": str(last["date"].date()),
            "close": round(last["close"], 2),
            "rsi2": round(last["rsi2"], 2),
            "ma200": round(last["ma200"], 2),
            "above_ma200": bool(above_ma200),
            "decision": decision,
            "model": model["model"],
            "condition": model["condition"],
            "exit": model["exit"],
            "historical_win_rate": model["historical_win_rate"],
            "historical_avg_return": model["historical_avg_return"],
            "historical_median_return": model["historical_median_return"],
            "historical_worst_return": model["historical_worst_return"],
            "confidence": confidence_label(model, signal_active),
        }
    )

report = pd.DataFrame(rows)

today = pd.Timestamp.today().strftime("%Y-%m-%d")

Path("DAILY_REPORTS").mkdir(exist_ok=True)

csv_out = Path(f"DAILY_REPORTS/{today}_decision_engine.csv")
md_out = Path(f"DAILY_REPORTS/{today}_decision_engine.md")

report.to_csv(csv_out, index=False)

lines = []
lines.append(f"# Daily Decision Engine")
lines.append("")
lines.append(f"Date: {today}")
lines.append("")
lines.append("## Summary")
lines.append("")

for _, row in report.iterrows():
    lines.append(f"### {row['symbol']}")
    lines.append("")
    lines.append(f"- Decision: **{row['decision']}**")
    lines.append(f"- Close: {row['close']}")
    lines.append(f"- RSI(2): {row['rsi2']}")
    lines.append(f"- MA200: {row['ma200']}")
    lines.append(f"- Above MA200: {row['above_ma200']}")
    lines.append(f"- Model: {row['model']}")
    lines.append(f"- Condition: {row['condition']}")
    lines.append(f"- Exit: {row['exit']}")
    lines.append(f"- Historical win rate: {row['historical_win_rate']}%")
    lines.append(f"- Historical avg return: {row['historical_avg_return']}%")
    lines.append(f"- Historical median return: {row['historical_median_return']}%")
    lines.append(f"- Historical worst return: {row['historical_worst_return']}%")
    lines.append(f"- Confidence: {row['confidence']}")
    lines.append("")

lines.append("## Process Note")
lines.append("")
lines.append("No trade should be considered without active signal and risk review.")
lines.append("This report is analytical, not financial advice.")
lines.append("")

md_out.write_text("\n".join(lines))

print(report.to_string(index=False))
print(f"\nSaved: {csv_out}")
print(f"Saved: {md_out}")