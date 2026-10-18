from __future__ import annotations

import argparse
import time
from typing import Any

from daily_momentum_breakout_radar import run as run_momentum
from run_daily_consolidation_scan import prepare_market_data, run as run_consolidation
from weekly_consolidation_common import LABELS, ROOT, atomic_write, utc_timestamp, write_json

SUMMARY_DIR = ROOT / "DAILY_REPORTS" / "DAILY_MARKET_OPPORTUNITY"


def run(as_of: Any = None, universe_size: int = 150, selection_size: int = 4,
        no_network: bool = False, reuse_existing_data: bool = False,
        refresh_universe: bool = False, dry_run: bool = False) -> dict[str, Any]:
    started = time.perf_counter(); cutoff = utc_timestamp(as_of)
    prepared = prepare_market_data(cutoff, universe_size, no_network, reuse_existing_data, refresh_universe, dry_run)
    consolidation = run_consolidation(cutoff, universe_size, selection_size, no_network,
                                      reuse_existing_data, refresh_universe, dry_run, prepared)
    momentum = run_momentum(consolidation["universe"], consolidation["rows"], cutoff, dry_run)
    relevant = [r for r in momentum if r["momentum_stage"] != "NO_MOMENTUM"][:5]
    result = {
        "generated_at_utc": cutoff.isoformat(), "labels": LABELS,
        "universe_size": consolidation["universe_size_returned"],
        "kraken_mapped_assets": consolidation["kraken_mapped_assets"],
        "fresh_data_assets": consolidation["fresh_data_assets"],
        "daily_consolidation_candidates": consolidation["watchlist_assets"],
        "momentum_candidates": [r["asset"] for r in relevant],
        "ada_like_movements": [r["asset"] for r in momentum if r.get("movement_alert")],
        "consolidation_to_breakout_transitions": [r["asset"] for r in momentum if r.get("consolidation_transition")],
        "checkpoint_resume": consolidation["checkpoint_resume"],
        "execution_duration_seconds": time.perf_counter() - started,
    }
    if not dry_run:
        SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
        base = SUMMARY_DIR / f"{cutoff:%Y-%m-%d}_daily_market_opportunity_summary"
        write_json(base.with_suffix(".json"), result)
        lines = ["# Daily Market Opportunity Summary", "", *LABELS, "", f"Universe: {result['universe_size']}", f"Kraken mapped: {result['kraken_mapped_assets']}", f"Fresh data: {result['fresh_data_assets']}", "", "## Daily Consolidation", "", *(f"- {a}" for a in result["daily_consolidation_candidates"]), "", "## Momentum", "", *(f"- {a}" for a in result["momentum_candidates"])]
        atomic_write(base.with_suffix(".md"), "\n".join(lines)+"\n")
        write_json(SUMMARY_DIR / "latest_daily_market_opportunity_summary.json", result, backup=False)
        atomic_write(SUMMARY_DIR / "latest_daily_market_opportunity_summary.md", base.with_suffix(".md").read_text(), backup=False)
    return result


def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("--as-of"); p.add_argument("--universe-size",type=int,default=150); p.add_argument("--selection-size",type=int,default=4); p.add_argument("--no-network",action="store_true"); p.add_argument("--reuse-existing-data",action="store_true"); p.add_argument("--refresh-universe",action="store_true"); p.add_argument("--dry-run",action="store_true"); a=p.parse_args()
    result=run(a.as_of,a.universe_size,a.selection_size,a.no_network,a.reuse_existing_data,a.refresh_universe,a.dry_run)
    print(f"Daily market opportunity scan complete | universe {result['universe_size']} | mapped {result['kraken_mapped_assets']} | consolidation {len(result['daily_consolidation_candidates'])} | momentum {len(result['momentum_candidates'])}")


if __name__ == "__main__": main()
