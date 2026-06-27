from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.data_loader import load_ohlc
from lib.indicators import rsi
from lib.config import get_assets, symbol_to_file

RSI_THRESHOLD = 10
NEAR_THRESHOLD = 25
HOLD_DAYS = 3

ASSETS = get_assets("crypto")

FILES = {
    symbol.replace("USD", ""): symbol_to_file(symbol)
    for symbol in ASSETS
}
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")

OUT_EPISODES = "BACKTESTS/rsi2_oversold_episodes.csv"
OUT_SUMMARY = "BACKTESTS/rsi2_oversold_episode_summary.csv"
OUT_DAILY = f"DAILY_REPORTS/{TODAY}_rsi2_episode_status.csv"


def detect_episodes(asset, df):
    episodes = []
    in_episode = False
    start_idx = None
    episode_number = 0

    for i in range(len(df)):
        is_oversold = df.loc[i, "rsi2"] < RSI_THRESHOLD

        if is_oversold and not in_episode:
            in_episode = True
            start_idx = i
            episode_number += 1

        episode_ended = in_episode and (not is_oversold or i == len(df) - 1)

        if episode_ended:
            end_idx = i - 1 if not is_oversold else i

            start_row = df.loc[start_idx]
            end_row = df.loc[end_idx]
            duration = end_idx - start_idx + 1

            entry_day_1 = start_row["close"]
            exit_day_1_idx = min(start_idx + HOLD_DAYS, len(df) - 1)
            ret_day1_hold3 = (df.loc[exit_day_1_idx, "close"] / entry_day_1 - 1) * 100

            ret_day2_hold3 = None
            if duration >= 2:
                entry_day_2 = df.loc[start_idx + 1, "close"]
                exit_day_2_idx = min(start_idx + 1 + HOLD_DAYS, len(df) - 1)
                ret_day2_hold3 = (
                    df.loc[exit_day_2_idx, "close"] / entry_day_2 - 1
                ) * 100

            ret_day3_hold3 = None
            if duration >= 3:
                entry_day_3 = df.loc[start_idx + 2, "close"]
                exit_day_3_idx = min(start_idx + 2 + HOLD_DAYS, len(df) - 1)
                ret_day3_hold3 = (
                    df.loc[exit_day_3_idx, "close"] / entry_day_3 - 1
                ) * 100

            after_episode_idx = min(end_idx + 1, len(df) - 1)
            after_episode_price = df.loc[after_episode_idx, "close"]
            exit_after_idx = min(after_episode_idx + HOLD_DAYS, len(df) - 1)
            ret_after_episode_hold3 = (
                df.loc[exit_after_idx, "close"] / after_episode_price - 1
            ) * 100

            episodes.append(
                {
                    "asset": asset,
                    "episode_id": f"{asset}_{episode_number}",
                    "start_date": start_row["date"].date(),
                    "end_date": end_row["date"].date(),
                    "duration_days": duration,
                    "start_close": round(start_row["close"], 2),
                    "end_close": round(end_row["close"], 2),
                    "min_close": round(df.loc[start_idx:end_idx, "close"].min(), 2),
                    "max_close": round(df.loc[start_idx:end_idx, "close"].max(), 2),
                    "start_rsi2": round(start_row["rsi2"], 2),
                    "end_rsi2": round(end_row["rsi2"], 2),
                    "min_rsi2": round(df.loc[start_idx:end_idx, "rsi2"].min(), 2),
                    "ret_day1_hold3_pct": round(ret_day1_hold3, 2),
                    "ret_day2_hold3_pct": (
                        None if ret_day2_hold3 is None else round(ret_day2_hold3, 2)
                    ),
                    "ret_day3_hold3_pct": (
                        None if ret_day3_hold3 is None else round(ret_day3_hold3, 2)
                    ),
                    "ret_after_episode_hold3_pct": round(ret_after_episode_hold3, 2),
                }
            )

            in_episode = False
            start_idx = None

    return episodes


def current_episode_status(asset, df):
    last = df.iloc[-1]
    current_rsi = last["rsi2"]

    duration = 0
    episode_start_date = None
    episode_start_close = None
    episode_drawdown_pct = None

    if current_rsi < RSI_THRESHOLD:
        idx = len(df) - 1

        while idx >= 0 and df.loc[idx, "rsi2"] < RSI_THRESHOLD:
            duration += 1
            idx -= 1

        episode_start_idx = len(df) - duration
        episode_start = df.loc[episode_start_idx]

        current_phase = f"OVERSOLD_DAY_{duration}"
        episode_start_date = episode_start["date"].date()
        episode_start_close = episode_start["close"]
        episode_drawdown_pct = (last["close"] / episode_start_close - 1) * 100

    elif current_rsi < NEAR_THRESHOLD:
        current_phase = "NEAR_OVERSOLD"

    else:
        current_phase = "NO_OVERSOLD"

    return {
        "asset": asset,
        "date": last["date"].date(),
        "close": round(last["close"], 2),
        "rsi2": round(current_rsi, 2),
        "current_phase": current_phase,
        "current_oversold_duration": duration,
        "episode_start_date": episode_start_date,
        "episode_start_close": (
            None if episode_start_close is None else round(episode_start_close, 2)
        ),
        "episode_drawdown_pct": (
            None if episode_drawdown_pct is None else round(episode_drawdown_pct, 2)
        ),
    }


all_episodes = []
daily_status = []

for asset, path in FILES.items():
    file_path = Path(path)

    if not file_path.exists():
        print(f"Missing: {path}")
        continue

    df = load_ohlc(file_path)
    df["rsi2"] = rsi(df["close"], 2)
    df = df.dropna().reset_index(drop=True)

    all_episodes.extend(detect_episodes(asset, df))
    daily_status.append(current_episode_status(asset, df))

episodes_df = pd.DataFrame(all_episodes)
daily_df = pd.DataFrame(daily_status)

summary_rows = []

for asset, sample in episodes_df.groupby("asset"):
    summary_rows.append(
        {
            "asset": asset,
            "episodes": len(sample),
            "avg_duration_days": round(sample["duration_days"].mean(), 2),
            "median_duration_days": round(sample["duration_days"].median(), 2),
            "max_duration_days": int(sample["duration_days"].max()),
            "avg_ret_day1_hold3_pct": round(sample["ret_day1_hold3_pct"].mean(), 2),
            "avg_ret_day2_hold3_pct": round(
                sample["ret_day2_hold3_pct"].dropna().mean(), 2
            ),
            "avg_ret_day3_hold3_pct": round(
                sample["ret_day3_hold3_pct"].dropna().mean(), 2
            ),
            "avg_ret_after_episode_hold3_pct": round(
                sample["ret_after_episode_hold3_pct"].mean(), 2
            ),
        }
    )

summary_df = pd.DataFrame(summary_rows)

Path("BACKTESTS").mkdir(exist_ok=True)
Path("DAILY_REPORTS").mkdir(exist_ok=True)

episodes_df.to_csv(OUT_EPISODES, index=False)
summary_df.to_csv(OUT_SUMMARY, index=False)
daily_df.to_csv(OUT_DAILY, index=False)

print("\nRSI2 OVERSOLD EPISODE SUMMARY\n")
print(summary_df.to_string(index=False))

print("\nCURRENT RSI2 EPISODE STATUS\n")
print(daily_df.to_string(index=False))

print(f"\nSaved: {OUT_EPISODES}")
print(f"Saved: {OUT_SUMMARY}")
print(f"Saved: {OUT_DAILY}")