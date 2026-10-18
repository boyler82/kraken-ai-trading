from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "universe.json"


def load_universe_config() -> dict:
    with CONFIG_PATH.open() as handle:
        return json.load(handle)


def active_assets() -> list[str]:
    config = load_universe_config()
    mode = os.environ.get("KRAKEN_UNIVERSE", config.get("mode", "full_crypto"))
    if mode not in {"full_crypto", "btc_only"}:
        raise ValueError(f"Unsupported universe: {mode}")
    return [str(asset).upper() for asset in config[mode]]


def is_asset_enabled(asset) -> bool:
    return str(asset).upper() in set(active_assets())


def report_dir() -> Path:
    return ROOT / "DAILY_REPORTS" / ("BTC_ONLY" if os.environ.get("KRAKEN_UNIVERSE") == "btc_only" else "")


def backtest_dir() -> Path:
    return ROOT / "BACKTESTS" / ("BTC_ONLY" if os.environ.get("KRAKEN_UNIVERSE") == "btc_only" else "")


def project_memory_db() -> Path:
    name = "project_memory_btc_only.sqlite" if os.environ.get("KRAKEN_UNIVERSE") == "btc_only" else "project_memory.sqlite"
    return ROOT / "journal" / name
