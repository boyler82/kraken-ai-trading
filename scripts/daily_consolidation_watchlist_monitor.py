from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from consolidation_range_engine import atr14, breakout_events, completed_4h_bars, position_pct
from weekly_consolidation_common import (
    INTRADAY_DIR, LABELS, ROOT, WATCHLIST_DIR, atomic_write, freshness,
    utc_timestamp, validate_hourly, write_json,
)
from weekly_intraday_market_backfill import update_pair


ZONE_DISPLAY = {
    "LOWER_RANGE": "DÓŁ KONSOLIDACJI — KANDYDAT DO RĘCZNEGO PRZEGLĄDU",
    "OBSERVE": "OBSERWUJ — CZEKAJ NA POWRÓT DO DOLNEJ STREFY",
    "UPPER_RANGE": "GÓRNA CZĘŚĆ KONSOLIDACJI — NIE KUPOWAĆ W STRATEGII RANGE",
    "BELOW_RANGE": "PONIŻEJ KONSOLIDACJI — RYZYKO WYBICIA DOŁEM",
    "ABOVE_RANGE": "POWYŻEJ KONSOLIDACJI — ZAKRES MOŻE BYĆ ZAKOŃCZONY",
    "STALE_DATA": "NIEAKTUALNE DANE — NIE TRAKTOWAĆ JAKO AKTUALNE",
    "INVALID_RANGE": "ZAKRES NIEWAŻNY — NIE TRAKTOWAĆ JAKO AKTUALNĄ OKAZJĘ",
}


def simple_position_zone(position: float | None, freshness_status: str,
                         range_still_valid: bool, confirmed_breakdown: bool) -> dict[str, str]:
    """Map technical monitoring output to the compact, user-facing classification."""
    if position is None or pd.isna(position):
        zone, color = "STALE_DATA", "RED"
    elif position < 0:
        zone, color = "BELOW_RANGE", "RED"
    elif position <= 30:
        zone, color = "LOWER_RANGE", "GREEN"
    elif position <= 50:
        zone, color = "OBSERVE", "YELLOW"
    elif position <= 100:
        zone, color = "UPPER_RANGE", "RED"
    else:
        zone, color = "ABOVE_RANGE", "RED"
    display = ZONE_DISPLAY[zone]
    if not range_still_valid or confirmed_breakdown:
        color = "RED"
    elif str(freshness_status).upper() != "FRESH":
        color = "RED"
    return {"simple_color": color, "simple_zone": zone, "simple_display": display}


def _read_clean_local(pair: str, as_of: Any) -> pd.DataFrame:
    path = INTRADAY_DIR / f"{pair}_1H.csv"
    if not path.exists():
        raise FileNotFoundError(f"no local hourly data for {pair}")
    clean, _ = validate_hourly(pd.read_csv(path), as_of)
    if clean.empty:
        raise ValueError(f"no valid completed hourly candles for {pair}")
    return clean


def refresh_selected_pairs(
    selected: list[dict[str, Any]], as_of: Any,
    updater: Callable[[str, Any], tuple[pd.DataFrame, dict[str, Any]]] = update_pair,
) -> dict[str, dict[str, Any]]:
    """Refresh each selected pair once; a failed update never replaces its local file."""
    cutoff = utc_timestamp(as_of)
    results: dict[str, dict[str, Any]] = {}
    pairs = sorted({str(item["kraken_pair"]) for item in selected if item.get("kraken_pair")})
    for pair in pairs:
        path = INTRADAY_DIR / f"{pair}_1H.csv"
        before = set()
        if path.exists():
            try:
                before = set(pd.to_datetime(pd.read_csv(path, usecols=["timestamp"])["timestamp"], utc=True, errors="coerce").dropna())
            except Exception:
                before = set()
        try:
            clean, quality = updater(pair, cutoff)
            retrieved = utc_timestamp()
            after = set(pd.to_datetime(clean["timestamp"], utc=True, errors="coerce").dropna())
            results[pair] = {
                "bars": clean, "retrieval_timestamp": retrieved.isoformat(),
                "refresh_status": "REFRESH_SUCCEEDED", "rows_added": len(after - before),
                "api_request_status": "SUCCESS", "refresh_failure_reason": None,
                "quality": quality,
            }
        except Exception as exc:
            retrieved = utc_timestamp()
            try:
                old = _read_clean_local(pair, cutoff)
            except Exception:
                old = pd.DataFrame()
            results[pair] = {
                "bars": old, "retrieval_timestamp": retrieved.isoformat(),
                "refresh_status": "REFRESH_FAILED", "rows_added": 0,
                "api_request_status": "FAILED", "refresh_failure_reason": str(exc),
                "quality": {},
            }
    return results


def monitor_row(selected: dict[str, Any], hourly: pd.DataFrame, as_of: Any,
                refresh: dict[str, Any] | None = None) -> dict[str, Any]:
    cutoff = utc_timestamp(as_of)
    refresh = refresh or {
        "retrieval_timestamp": cutoff.isoformat(), "refresh_status": "NOT_REQUESTED",
        "rows_added": 0, "api_request_status": "NOT_REQUESTED", "refresh_failure_reason": None,
    }
    if hourly.empty:
        raise ValueError("no valid completed hourly candles")
    low, high = float(selected["range_low"]), float(selected["range_high"])
    latest_1h = hourly.iloc[-1]
    # Keep the public helper compatible with callers that already supply derived 4H bars.
    bars = hourly if "source_count" in hourly.columns else completed_4h_bars(hourly, cutoff, "1H")
    if bars.empty:
        raise ValueError("no completed 4H candles available")
    tolerance = .25 * atr14(bars)
    events = breakout_events(
        bars.tail(10).reset_index(drop=True), low, high,
        tolerance.tail(10).reset_index(drop=True),
    )
    price = float(latest_1h["close"])
    pos = position_pct(price, low, high)
    age, fresh = freshness(latest_1h["timestamp"], cutoff)
    failed = refresh["refresh_status"] == "REFRESH_FAILED"
    if failed:
        fresh = "REFRESH_FAILED_STALE"
    confirmed_above = bool(events["confirmed_above"])
    confirmed_below = bool(events["confirmed_below"])
    false_above = bool(events["false_above"])
    false_below = bool(events["false_below"])
    expired = cutoff.date() > pd.Timestamp(selected["watchlist_expiry_date"]).date()
    below_range = pos < 0
    false_breakdown_recovery = below_range and false_below and not confirmed_below
    valid = not confirmed_above and not confirmed_below and not expired and (not below_range or false_breakdown_recovery)
    status = (
        "BREAKOUT_CONFIRMED" if confirmed_above else
        "BREAKDOWN_CONFIRMED" if confirmed_below else
        "FALSE_BREAKDOWN_RECOVERY" if false_breakdown_recovery else
        "BELOW_RANGE_PENDING_RECOVERY" if below_range else
        "FALSE_BREAKOUT_ABOVE" if false_above else
        "FALSE_BREAKDOWN_BELOW" if false_below else
        "NEAR_RANGE_LOW" if pos <= 20 else
        "NEAR_RANGE_HIGH" if pos >= 80 else "IN_RANGE"
    )
    invalidation = "WATCHLIST_EXPIRED" if expired else "CURRENT_PRICE_BELOW_RANGE_LOW_WITHOUT_FALSE_BREAKDOWN_RECOVERY" if status == "BELOW_RANGE_PENDING_RECOVERY" else status if not valid else None
    recovery = "CLOSE_AT_OR_ABOVE_RANGE_LOW" if below_range else None
    visible_price = None if failed else price
    simple = simple_position_zone(None if failed else pos, fresh, valid, confirmed_below)
    friction_pct = float(selected.get("estimated_total_friction_pct", .6))
    midpoint = float(selected.get("midpoint", (low + high) / 2))
    net_mid = None if failed else ((midpoint / price - 1) * 100 - friction_pct)
    net_high = None if failed else ((high / price - 1) * 100 - friction_pct)
    return {
        **selected, "status": "REFRESH_FAILED_STALE" if failed else status,
        **simple,
        "current_price": visible_price,
        "latest_completed_1h_timestamp": pd.Timestamp(latest_1h["timestamp"]).isoformat(),
        "market_data_timestamp": pd.Timestamp(latest_1h["timestamp"]).isoformat(),
        "current_timestamp": pd.Timestamp(latest_1h["timestamp"]).isoformat(),
        "monitor_report_timestamp": cutoff.isoformat(),
        "retrieval_timestamp": refresh["retrieval_timestamp"],
        "position_pct": None if failed else pos,
        "estimated_net_movement_to_midpoint_pct": net_mid,
        "estimated_net_movement_to_high_pct": net_high,
        "distance_to_lower_pct": None if failed else (price / low - 1) * 100,
        "downside_to_invalidation_pct": None if failed or price <= low else (price / low - 1) * 100,
        "risk_reward_to_midpoint": None if failed or price <= low else net_mid / ((price / low - 1) * 100),
        "risk_reward_to_high": None if failed or price <= low else net_high / ((price / low - 1) * 100),
        "distance_to_upper_pct": None if failed else (high / price - 1) * 100,
        "entered_lower_observation_zone": False if failed else 0 <= pos <= 20,
        "entered_upper_observation_zone": False if failed else 80 <= pos <= 100,
        "false_breakout_above": false_above, "false_breakdown_below": false_below,
        "confirmed_breakout": confirmed_above, "confirmed_breakdown": confirmed_below,
        "range_still_valid": valid, "freshness_age_hours": age,
        "freshness_status": fresh, "refresh_status": refresh["refresh_status"],
        "rows_added": refresh["rows_added"], "api_request_status": refresh["api_request_status"],
        "refresh_failure_reason": refresh["refresh_failure_reason"],
        "invalidation_status": invalidation, "invalidation_reason": invalidation,
        "recovery_condition": recovery,
    }


def _failure_row(item: dict[str, Any], cutoff: pd.Timestamp, refresh: dict[str, Any], exc: Exception) -> dict[str, Any]:
    reason = refresh.get("refresh_failure_reason") or str(exc)
    return {
        **item, "status": "REFRESH_FAILED_STALE", "current_price": None,
        **simple_position_zone(None, "REFRESH_FAILED_STALE", False, False),
        "position_pct": None, "distance_to_lower_pct": None, "distance_to_upper_pct": None,
        "estimated_net_movement_to_midpoint_pct": None,
        "estimated_net_movement_to_high_pct": None,
        "downside_to_invalidation_pct": None, "risk_reward_to_midpoint": None,
        "risk_reward_to_high": None, "recovery_condition": None,
        "range_still_valid": False, "freshness_status": "REFRESH_FAILED_STALE",
        "freshness_age_hours": None, "monitor_report_timestamp": cutoff.isoformat(),
        "market_data_timestamp": None, "latest_completed_1h_timestamp": None,
        "retrieval_timestamp": refresh.get("retrieval_timestamp"),
        "refresh_status": "REFRESH_FAILED", "rows_added": 0,
        "api_request_status": "FAILED", "refresh_failure_reason": reason,
        "invalidation_status": reason, "invalidation_reason": reason,
    }


def monitor(as_of: Any = None, updater: Callable | None = None) -> list[dict[str, Any]]:
    cutoff = utc_timestamp(as_of)
    path = WATCHLIST_DIR / "consolidation_weekly_watchlist.json"
    if not path.exists():
        return []
    selected = json.loads(path.read_text()).get("watchlist", [])
    refreshed = refresh_selected_pairs(selected, cutoff, updater or update_pair)
    rows = []
    for item in selected:
        result = refreshed.get(str(item.get("kraken_pair")), {})
        try:
            rows.append(monitor_row(item, result.get("bars", pd.DataFrame()), cutoff, result))
        except Exception as exc:
            rows.append(_failure_row(item, cutoff, result, exc))
    base = ROOT / "DAILY_REPORTS" / f"{cutoff:%Y-%m-%d}_consolidation_watchlist_monitor"
    atomic_write(base.with_suffix(".csv"), pd.DataFrame(rows).to_csv(index=False))
    write_json(base.with_suffix(".json"), {"generated_at_utc": cutoff.isoformat(), "labels": LABELS, "candidates": rows})
    lines = ["# Consolidation Watchlist Monitor", "", f"Report timestamp: {cutoff.isoformat()}", "", *LABELS, ""]
    lines += [f"- #{r['rank']} {r['asset']} | {r['simple_color']} {r['simple_zone']} | market {r.get('market_data_timestamp') or 'n/a'} | price {r.get('current_price') if r.get('current_price') is not None else 'n/a'} | freshness {r['freshness_status']} | refresh {r['refresh_status']}" for r in rows] if rows else ["Weekly watchlist unavailable or empty."]
    atomic_write(base.with_suffix(".md"), "\n".join(lines) + "\n")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of")
    args = parser.parse_args()
    print(f"Monitored: {len(monitor(args.as_of))}")


if __name__ == "__main__":
    main()
