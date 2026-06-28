from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.data_loader import load_ohlc
from lib.indicators import atr, rsi

FILES = {
    "BTC": "DATASETS/market_raw/BTCUSD_D1.json",
    "ETH": "DATASETS/market_raw/ETHUSD_D1.json",
    "SPY": "DATASETS/market_raw/SPYx_USD_D1.json",
    "QQQ": "DATASETS/market_raw/QQQx_USD_D1.json",
    "NVDA": "DATASETS/market_raw/NVDAx_USD_D1.json",
    "GLD": "DATASETS/market_raw/GLDx_USD_D1.json",
}

results = []

for symbol, path in FILES.items():
    df = load_ohlc(path)

    df["ma20"] = df["close"].rolling(20).mean()
    df["ma50"] = df["close"].rolling(50).mean()
    df["ma200"] = df["close"].rolling(200).mean()
    df["rsi2"] = rsi(df["close"], 2)
    df["rsi14"] = rsi(df["close"], 14)
    df["atr14"] = atr(df, 14)
    df["dist_ma20_pct"] = (df["close"] / df["ma20"] - 1) * 100

    last = df.iloc[-1]

    score = 0
    if last["rsi2"] < 10:
        score += 2
    if last["close"] < last["ma20"]:
        score += 2
    if last["dist_ma20_pct"] < -2:
        score += 2
    if last["close"] > last["ma200"]:
        score += 2
    if last["rsi14"] < 40:
        score += 1
    if last["volume"] > df["volume"].rolling(20).mean().iloc[-1]:
        score += 1

    results.append({
        "symbol": symbol,
        "date": last["date"].date(),
        "close": round(last["close"], 2),
        "rsi2": round(last["rsi2"], 2),
        "rsi14": round(last["rsi14"], 2),
        "ma20": round(last["ma20"], 2),
        "ma50": round(last["ma50"], 2),
        "ma200": round(last["ma200"], 2),
        "dist_ma20_pct": round(last["dist_ma20_pct"], 2),
        "atr14": round(last["atr14"], 2),
        "score": score,
    })

report = pd.DataFrame(results).sort_values("score", ascending=False)

Path("DAILY_REPORTS").mkdir(exist_ok=True)
today = pd.Timestamp.today().strftime("%Y-%m-%d")

out = Path(f"DAILY_REPORTS/{today}_market_scan.csv")
report.to_csv(out, index=False)

print(report.to_string(index=False))
print(f"\nSaved: {out}")
