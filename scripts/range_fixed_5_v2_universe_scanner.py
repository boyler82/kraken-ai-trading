from __future__ import annotations

import argparse
import json
import sqlite3
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd

from range_fixed_5_v2_clock import ClockSafetyError, ClockSafetyGuard
from range_fixed_5_v2_entry import fetch_public_kraken_ticker, validate_public_ticker_quote
from range_fixed_5_v2_snapshot import calculate_from_ohlcv
from range_fixed_5_v2_storage import DB_PATH, load_config, sha256_json
from weekly_consolidation_common import INTRADAY_DIR, get_json
from weekly_consolidation_universe import (
    COINGECKO_URL, KRAKEN_PAIRS_URL, KRAKEN_TICKER_URL,
    build_universe, exclusion_reason, map_pair, parse_coingecko, parse_kraken_pairs,
)


CODE_VERSION = "RANGE_FIXED_5_V2_UNIVERSE_PREVIEW_1.0.0"
LOCAL_UNIVERSE_PATH = Path(__file__).resolve().parents[1] / "DATASETS/universe/weekly_consolidation_universe.json"
PUBLIC_UNIVERSE_SIZE = 150
MAX_UNIVERSE_METADATA_AGE_HOURS = 8.0


def utc(value: Any = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def production_status(db_path: Path = DB_PATH) -> dict[str, Any]:
    uri = f"file:{db_path.resolve()}?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    try:
        counts = {
            label: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for label, table in {
                "decisions": "v2_decision_snapshots", "signals": "v2_signals",
                "quote_attempts": "v2_quote_attempts", "entries": "v2_entry_observations",
                "monitor_events": "v2_monitor_events", "completed_outcomes": "v2_completed_outcomes",
            }.items()
        }
        active = db.execute(
            "SELECT count(*) FROM v2_strategy_manifest WHERE manifest_status='OFFICIAL_COHORT_ACTIVE'"
        ).fetchone()[0]
        return {"cohort_status": "ACTIVE" if active else "INACTIVE", "counts": counts}
    finally:
        db.close()


def load_local_universe(path: Path = LOCAL_UNIVERSE_PATH, observed_at: Any = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads(path.read_text())
    rows = payload.get("assets")
    generated = payload.get("generated_at_utc")
    if not isinstance(rows, list) or not generated:
        raise ValueError("malformed local dynamic universe")
    now = utc(observed_at)
    age = max(0.0, (now - utc(generated)).total_seconds() / 3600)
    return rows, {"source": "LOCAL_DYNAMIC_UNIVERSE", "observed_at": now.isoformat(),
                  "generated_at": utc(generated).isoformat(), "age_hours": age,
                  "fresh": age <= MAX_UNIVERSE_METADATA_AGE_HOURS}


def discover_public_universe(
    getter: Callable[..., Any] = get_json, size: int = PUBLIC_UNIVERSE_SIZE,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    coins = parse_coingecko(getter(COINGECKO_URL, {
        "vs_currency": "usd", "order": "market_cap_desc", "per_page": size,
        "page": 1, "sparkline": "false",
    }), size)
    pairs = parse_kraken_pairs(getter(KRAKEN_PAIRS_URL))
    pair_ids = sorted({mapped["pair_id"] for coin in coins if exclusion_reason(coin) is None
                       for mapped in [map_pair(coin["symbol"], pairs)] if mapped is not None})
    ticker_payload = getter(KRAKEN_TICKER_URL, {"pair": ",".join(pair_ids)})
    if not isinstance(ticker_payload, dict) or ticker_payload.get("error") or not isinstance(ticker_payload.get("result"), dict):
        raise ValueError("malformed Kraken public Ticker response")
    observed = utc(clock()).isoformat()
    rows = build_universe(coins, pairs, ticker_payload["result"], observed)
    return rows, {"source": "PUBLIC_DYNAMIC_UNIVERSE", "observed_at": observed,
                  "generated_at": observed, "age_hours": 0.0, "fresh": True}


def deduplicate_universe(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    by_asset: dict[str, dict[str, Any]] = {}
    pair_owner: dict[str, str] = {}
    ordered = sorted(rows, key=lambda row: (row.get("market_cap_rank") or 10**9, str(row.get("coingecko_id") or "")))
    for row in ordered:
        asset = str(row.get("symbol") or "").upper()
        pair = str(row.get("selected_kraken_pair") or "").upper()
        if asset in by_asset:
            conflicts.append({"asset": asset, "pair": pair or None, "reason": "DUPLICATE_ASSET",
                              "kept_pair": by_asset[asset].get("selected_kraken_pair")})
            continue
        if pair and pair in pair_owner and pair_owner[pair] != asset:
            conflicts.append({"asset": asset, "pair": pair, "reason": "DUPLICATE_PAIR_MAPPING",
                              "kept_asset": pair_owner[pair]})
            continue
        by_asset[asset] = row
        if pair:
            pair_owner[pair] = asset
        selected.append(row)
    return selected, conflicts


def _empty_ohlcv() -> pd.DataFrame:
    return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])


def load_local_ohlcv(pair: str, directory: Path = INTRADAY_DIR) -> tuple[pd.DataFrame, str]:
    path = directory / f"{pair}_1H.csv"
    if not path.exists():
        raise FileNotFoundError(f"MISSING_LOCAL_OHLCV:{path.name}")
    return pd.read_csv(path), str(path)


def preview_entry_quote(
    pair: str, guard: ClockSafetyGuard,
    fetcher: Callable[[str, str], Any] = fetch_public_kraken_ticker,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    endpoint = "https://api.kraken.com/0/public/Ticker"
    guard.check()
    request_started = utc(clock())
    fetched = fetcher(pair, endpoint)
    if isinstance(fetched, tuple) and len(fetched) == 2:
        payload, received_value = fetched
        received = utc(received_value)
    else:
        payload, received = fetched, utc(clock())
    guard.check()
    if received < request_started:
        return {"status": "CLOCK_CHRONOLOGY_ERROR"}
    try:
        quote = validate_public_ticker_quote(payload, pair, 0.75)
    except ValueError as exc:
        return {"status": "PREVIEW_ENTRY_NOT_OBSERVED", "reason": str(exc)}
    ask = quote["best_ask"]
    return {
        "status": "PREVIEW_ENTRY_ONLY", "pair": pair,
        "request_started_at": request_started.isoformat(), "response_received_at": received.isoformat(),
        **quote, "preview_reference_entry": ask, "target_price": ask * 1.05,
        "stop_price": ask * 0.98, "expiry_reference": (received + timedelta(hours=120)).isoformat(),
        "gross_reward_pct": 5.0, "gross_risk_pct": -2.0, "gross_reward_risk_ratio": 2.5,
    }


def run_scan(
    universe_rows: list[dict[str, Any]], universe_metadata: dict[str, Any],
    ohlcv_loader: Callable[[str], tuple[pd.DataFrame, str]] = load_local_ohlcv,
    quote_fetcher: Optional[Callable[[str, str], Any]] = None,
    wall_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    guard: Optional[ClockSafetyGuard] = None,
    component_cutoff_factory: Optional[Callable[[datetime], dict[str, Any]]] = None,
    db_path: Path = DB_PATH,
) -> dict[str, Any]:
    run_guard = guard or ClockSafetyGuard()
    try:
        run_guard.check()
    except ClockSafetyError as exc:
        return {"status": str(exc), "official_cohort": "INACTIVE", "snapshots": [], "opportunities": []}
    production = production_status(db_path)
    if production["cohort_status"] != "INACTIVE":
        raise RuntimeError("PREVIEW_SCANNER_REQUIRES_INACTIVE_COHORT")
    config = load_config()
    manifest = {"manifest_id": "PRE_ACTIVATION_PREVIEW", "config_sha256": sha256_json(config),
                "hypothesis_version": config["hypothesis_version"]}
    rows, conflicts = deduplicate_universe(universe_rows)
    exclusions = []
    snapshots = []
    opportunities = []
    evaluated_assets: set[str] = set()
    for item in rows:
        asset = str(item.get("symbol") or "").upper()
        pair = str(item.get("selected_kraken_pair") or "").upper()
        if item.get("inclusion_status") != "INCLUDED":
            exclusions.append({"asset": asset, "pair": pair or None,
                               "reason": item.get("exclusion_reason") or "NOT_ELIGIBLE_UNIVERSE"})
            continue
        if not universe_metadata.get("fresh"):
            exclusions.append({"asset": asset, "pair": pair, "reason": "UNIVERSE_METADATA_STALE"})
            continue
        if not pair:
            exclusions.append({"asset": asset, "pair": None, "reason": "NO_ACTIVE_KRAKEN_SPOT_PAIR"})
            continue
        if asset in evaluated_assets:
            conflicts.append({"asset": asset, "pair": pair, "reason": "DUPLICATE_CANDIDATE_SUPPRESSED"})
            continue
        evaluated_assets.add(asset)
        try:
            run_guard.check()
            raw, source_path = ohlcv_loader(pair)
            source_error = None
        except (ClockSafetyError, Exception) as exc:
            if isinstance(exc, ClockSafetyError):
                return {"status": str(exc), "official_cohort": "INACTIVE", "snapshots": snapshots,
                        "opportunities": [], "exclusions": exclusions, "mapping_conflicts": conflicts}
            raw, source_path, source_error = _empty_ohlcv(), None, str(exc)
        cutoff = utc(wall_clock())
        component_cutoffs = (component_cutoff_factory(cutoff) if component_cutoff_factory else
                             {name: cutoff.isoformat() for name in ("price", "range", "rqi", "liquidity", "spread", "universe")})
        calculated = calculate_from_ohlcv(
            raw, asset, pair, "1H", cutoff, cutoff,
            float(item.get("kraken_24h_quote_volume") or 0.0),
            float(item.get("bid_ask_spread_pct") if item.get("bid_ask_spread_pct") is not None else 999.0),
            bool(item.get("inclusion_status") == "INCLUDED"), manifest, config,
            market_regime="UNKNOWN", btc_market_state="UNKNOWN", component_cutoffs=component_cutoffs,
        )
        calculated["preview_only"] = True
        calculated["source_path"] = source_path
        if source_error:
            calculated["preview_data_error"] = source_error
        snapshots.append(calculated)
        if calculated["eligible_for_future_signal"]:
            opportunity = {"snapshot": calculated, "entry_preview": None}
            if quote_fetcher is not None:
                try:
                    opportunity["entry_preview"] = preview_entry_quote(pair, run_guard, quote_fetcher, wall_clock)
                except ClockSafetyError as exc:
                    return {"status": str(exc), "official_cohort": "INACTIVE", "snapshots": snapshots,
                            "opportunities": [], "exclusions": exclusions, "mapping_conflicts": conflicts}
            opportunities.append(opportunity)
        try:
            run_guard.check()
        except ClockSafetyError as exc:
            return {"status": str(exc), "official_cohort": "INACTIVE", "snapshots": snapshots,
                    "opportunities": [], "exclusions": exclusions, "mapping_conflicts": conflicts}
    rejection_counts = Counter(
        reason for row in snapshots if not row.get("eligible_for_future_signal")
        for reason in (row.get("eligibility_reasons") or [row.get("eligibility_status")])
    )
    rejection_counts.update(row["reason"] for row in exclusions)
    return {
        "status": "PREVIEW_COMPLETE", "code_version": CODE_VERSION,
        "official_cohort": production["cohort_status"], "production_counts": production["counts"],
        "universe_source": universe_metadata, "assets_discovered": len(universe_rows),
        "eligible_kraken_pairs": sum(row.get("inclusion_status") == "INCLUDED" for row in rows),
        "assets_evaluated": len(snapshots), "eligible_opportunities": len(opportunities),
        "rejected": len(universe_rows) - len(opportunities), "exclusions": exclusions,
        "mapping_conflicts": conflicts, "rejection_reason_distribution": dict(sorted(rejection_counts.items())),
        "snapshots": snapshots, "opportunities": opportunities,
        "safety": {"official_records_written": 0, "orders_placed": 0, "signals_created": 0,
                   "clock_guard_identity": id(run_guard)},
    }


def render_summary(result: dict[str, Any]) -> str:
    lines = [
        "RANGE_FIXED_5_FORWARD_V2 — PRE-ACTIVATION SCAN", "",
        "Status: PREVIEW ONLY", f"Official cohort: {result.get('official_cohort', 'INACTIVE')}", "",
    ]
    if result.get("status") != "PREVIEW_COMPLETE":
        return "\n".join(lines + [f"Clock/status failure: {result.get('status')}", "", "NO ORDERS PLACED", "NO OFFICIAL FORWARD OBSERVATIONS CREATED"])
    lines += [
        "Universe:", f"Assets discovered: {result['assets_discovered']}",
        f"Eligible Kraken pairs: {result['eligible_kraken_pairs']}",
        f"Assets evaluated: {result['assets_evaluated']}",
        f"Eligible opportunities: {result['eligible_opportunities']}", f"Rejected: {result['rejected']}", "",
        f"Duplicate/mapping conflicts: {len(result['mapping_conflicts'])}", "",
        "Top rejection reasons:",
    ]
    for reason, count in sorted(result["rejection_reason_distribution"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {reason}: {count}")
    lines += ["", "EXCLUDED ASSETS", ""]
    if not result["exclusions"]:
        lines.append("- None")
    else:
        lines += [f"- {row['asset']} ({row.get('pair') or 'NO_PAIR'}): {row['reason']}" for row in result["exclusions"]]
    if result["mapping_conflicts"]:
        lines += ["", "MAPPING CONFLICTS", ""]
        lines += [f"- {row['asset']} ({row.get('pair') or 'NO_PAIR'}): {row['reason']}" for row in result["mapping_conflicts"]]
    lines += ["", "OPPORTUNITIES", ""]
    if not result["opportunities"]:
        lines.append("No eligible preview opportunities.")
    for index, item in enumerate(result["opportunities"], 1):
        row, quote = item["snapshot"], item.get("entry_preview")
        lines += [f"{index}. {row['asset']} ({row['pair']})",
                  f"Range: {row['range_low']}–{row['range_high']}",
                  f"Position: {row['range_position_pct']:.2f}%",
                  f"RQI: {row['rqi_score']:.2f} — {row['rqi_classification']}"]
        if quote and quote.get("status") == "PREVIEW_ENTRY_ONLY":
            lines += [f"Reference ask: {quote['preview_reference_entry']}", f"Target: {quote['target_price']}",
                      f"Stop: {quote['stop_price']}", f"Spread: {quote['spread_pct']:.4f}%",
                      f"Expiry reference: {quote['expiry_reference']}"]
        else:
            lines.append("Entry preview: not requested or not observed")
        lines.append("")
    lines += [
        "Research interpretation:",
        "Candidates satisfy the frozen range/RQI/lower-half and data-quality rules at one legal cutoff.",
        "This preview does not establish future profitability.", "",
        "PODSUMOWANIE PO POLSKU", "",
        f"Przeskanowano {result['assets_evaluated']} aktywów z dynamicznego uniwersum. Warunki spełniło: {result['eligible_opportunities']}.",
        "Kandydat przechodzi tylko wtedy, gdy ma ważny zakres, zaakceptowane RQI, cenę w dolnej połowie oraz świeże i płynne dane.",
        "Większość odpada z jawnego powodu wymienionego powyżej. Cel +5% i stop -2% są wyłącznie poziomami badawczymi od obserwowanego asku.",
        "Nie wiemy jeszcze, czy obserwacje V2 będą zyskowne w prawdziwym forwardzie ani jak często będą zależne od wspólnego rynku.", "",
        "NO ORDERS PLACED", "NO OFFICIAL FORWARD OBSERVATIONS CREATED", "RESEARCH ONLY",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only pre-activation RANGE_FIXED_5 V2 universe preview.")
    parser.add_argument("--public-refresh", action="store_true", help="Refresh dynamic universe through public endpoints in memory.")
    parser.add_argument("--preview-entry-quotes", action="store_true", help="Observe public best asks in memory for eligible previews.")
    parser.add_argument("--universe-size", type=int, default=PUBLIC_UNIVERSE_SIZE)
    parser.add_argument("--json", action="store_true", help="Print canonical preview JSON instead of the human report.")
    args = parser.parse_args()
    guard = ClockSafetyGuard()
    guard.check()
    if args.public_refresh:
        rows, metadata = discover_public_universe(size=min(PUBLIC_UNIVERSE_SIZE, max(1, args.universe_size)))
    else:
        rows, metadata = load_local_universe()
    result = run_scan(rows, metadata, quote_fetcher=fetch_public_kraken_ticker if args.preview_entry_quotes else None,
                      guard=guard)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) if args.json else render_summary(result))


if __name__ == "__main__":
    main()
