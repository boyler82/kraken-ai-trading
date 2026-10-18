from __future__ import annotations

"""Small, public-only market refresh for the transition monitor."""

import argparse
import json
from typing import Any

import pandas as pd

from weekly_consolidation_common import ROOT, UNIVERSE_DIR, atomic_write, get_json, utc_timestamp
from weekly_consolidation_universe import KRAKEN_TICKER_URL
from weekly_intraday_market_backfill import update_pair

STATUS_PATH = ROOT / "RESEARCH_MEMORY" / "market_transition" / "market_data_refresh.json"


def refresh(as_of: Any = None) -> dict[str, Any]:
    now = utc_timestamp(as_of)
    universe_path = UNIVERSE_DIR / "weekly_consolidation_universe.csv"
    if not universe_path.exists():
        raise FileNotFoundError("tracked universe is unavailable")
    universe = pd.read_csv(universe_path)
    included = universe[universe["inclusion_status"] == "INCLUDED"]
    if included.empty:
        raise RuntimeError("tracked universe has no included assets")

    refreshed: list[dict[str, Any]] = []
    for _, item in included.iterrows():
        asset, pair = str(item["symbol"]), str(item["selected_kraken_pair"])
        bars, quality = update_pair(pair, now)
        refreshed.append({"asset": asset, "pair": pair, "rows": len(bars),
                          "latest_completed_bar": bars.iloc[-1]["timestamp"].isoformat(),
                          "freshness_status": quality["freshness_status"]})

    # A single public Ticker request records current public prices operationally.
    # Predictions remain completed-hour-bar observations, so intrabar ticks never
    # masquerade as independent forward-validation samples.
    pairs = ",".join(str(x) for x in included["selected_kraken_pair"])
    ticker = get_json(KRAKEN_TICKER_URL, {"pair": pairs})
    if ticker.get("error") or not isinstance(ticker.get("result"), dict):
        raise RuntimeError("malformed Kraken public Ticker response")
    latest_prices = {key: float(value["c"][0]) for key, value in ticker["result"].items()}
    result = {"status": "OK", "refreshed_at": now.isoformat(), "source_resolution": "1h_completed_bars",
              "source": "KRAKEN_PUBLIC_OHLC_AND_TICKER", "assets": refreshed, "latest_public_prices": latest_prices}
    atomic_write(STATUS_PATH, json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", backup=False)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh public data used by the market transition monitor")
    parser.add_argument("--as-of")
    args = parser.parse_args()
    result = refresh(args.as_of)
    print(f"MARKET DATA REFRESHED | assets {len(result['assets'])} | resolution 1h")


if __name__ == "__main__":
    main()
