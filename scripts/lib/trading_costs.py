from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "trading_costs.json"


def load_trading_costs() -> dict:
    with CONFIG_PATH.open() as handle:
        return json.load(handle)


def default_fee_pct() -> float:
    return float(load_trading_costs().get("default_fee_pct", 0.0))


def round_trip_fee_pct() -> float:
    return default_fee_pct() * 2
