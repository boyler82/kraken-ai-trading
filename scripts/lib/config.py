import json
from pathlib import Path

CONFIG_PATH = Path("config/assets.json")


def get_assets(group="research"):
    with open(CONFIG_PATH) as f:
        config = json.load(f)

    return config[group]


def symbol_to_file(symbol):
    return f"DATASETS/market_raw/{symbol}_D1.json"
