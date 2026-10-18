from __future__ import annotations

"""Read-only historical report for immutable market-transition predictions."""

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
MEMORY = ROOT / "RESEARCH_MEMORY" / "market_transition"
PREDICTIONS = MEMORY / "predictions"
MISSING_OBSERVATIONS = MEMORY / "missing_observations"


def parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp is not a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp has no timezone")
    return parsed.astimezone(timezone.utc)


def _utc_now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return current.astimezone(timezone.utc)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("top-level JSON value is not an object")
    return value


def load_history(
    prediction_dir: Path = PREDICTIONS,
    *,
    hours: float = 24,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Load timestamped snapshots in the inclusive UTC window, fail-soft."""
    if hours <= 0:
        raise ValueError("hours must be greater than zero")
    end = _utc_now(now)
    start = end - timedelta(hours=hours)
    snapshots: list[dict[str, Any]] = []
    warnings: list[str] = []
    for path in prediction_dir.glob("*.json") if prediction_dir.exists() else []:
        try:
            item = _read_json(path)
            timestamp = parse_timestamp(item.get("timestamp"))
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            warnings.append(f"{path.name}: {type(exc).__name__}: {exc}")
            continue
        if start <= timestamp <= end:
            copy = dict(item)
            copy["_prediction_timestamp"] = timestamp
            copy["_source_file"] = path.name
            snapshots.append(copy)
    snapshots.sort(key=lambda item: (item["_prediction_timestamp"], item["_source_file"]))
    return snapshots, warnings


def load_missing_observations(
    directory: Path = MISSING_OBSERVATIONS,
    *,
    hours: float = 24,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    end = _utc_now(now)
    start = end - timedelta(hours=hours)
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for path in directory.glob("*.json") if directory.exists() else []:
        try:
            item = _read_json(path)
            expected = parse_timestamp(item.get("expected_timestamp"))
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            warnings.append(f"missing/{path.name}: {type(exc).__name__}: {exc}")
            continue
        if start <= expected <= end and item.get("status") == "MISSING_SCHEDULED_OBSERVATION":
            rows.append(item)
    return rows, warnings


def _nested(item: dict[str, Any], *keys: str) -> Any:
    value: Any = item
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _text(value: Any) -> str:
    return "N/A" if value is None or value == "" else str(value)


def _number(value: Any, decimals: int = 1) -> str:
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def _percent(value: Any) -> str:
    rendered = _number(value)
    return rendered if rendered == "N/A" else rendered + "%"


def _state(item: dict[str, Any]) -> str:
    return _text(item.get("market_state"))


def _market_timestamp_value(item: dict[str, Any]) -> Any:
    """Read the canonical field, with the legacy location used by old snapshots."""
    return item.get("market_data_timestamp") or _nested(item, "data_quality", "latest_bar_timestamp")


def independent_observations(snapshots: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse records whose market-observation identity can be established.

    Hashless legacy records without a market timestamp are deliberately excluded.
    Returned representatives carry private reporting metadata; inputs are untouched.
    """
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in snapshots:
        identity = item.get("market_data_hash")
        if identity not in (None, ""):
            key = ("HASH", str(identity))
        else:
            market_timestamp = _market_timestamp_value(item)
            if market_timestamp in (None, ""):
                continue
            try:
                normalized = parse_timestamp(market_timestamp).isoformat()
            except ValueError:
                continue
            key = ("LEGACY_TIMESTAMP", normalized)
        groups.setdefault(key, []).append(item)

    result: list[dict[str, Any]] = []
    for (identity_type, identity), records in groups.items():
        representative = dict(records[0])
        representative["_identity_type"] = identity_type
        representative["_observation_identity"] = identity
        representative["_observation_records"] = records
        representative["_observation_states"] = sorted({_state(row) for row in records})
        result.append(representative)
    result.sort(key=lambda item: (item["_prediction_timestamp"], item.get("_source_file", "")))
    return result


def collapsed_states(states: Iterable[str]) -> list[str]:
    result: list[str] = []
    for state in states:
        if not result or result[-1] != state:
            result.append(state)
    return result


def _duplicate_hashes(snapshots: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(item["market_data_hash"]) for item in snapshots if item.get("market_data_hash"))
    return {key: count for key, count in counts.items() if count > 1}


def _legacy_timestamp_counts(snapshots: Iterable[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in snapshots:
        market_timestamp = _market_timestamp_value(item)
        if item.get("market_data_hash") or not market_timestamp:
            continue
        try:
            counts[parse_timestamp(market_timestamp).isoformat()] += 1
        except ValueError:
            continue
    return counts


def _observation_timestamp(item: dict[str, Any]) -> datetime | None:
    value = _market_timestamp_value(item)
    try:
        return parse_timestamp(value)
    except ValueError:
        return None


def _safe_market_timestamp(value: Any) -> datetime | None:
    try:
        return parse_timestamp(value)
    except ValueError:
        return None


def _state_durations(observations: list[dict[str, Any]]) -> tuple[dict[str, timedelta], int]:
    """Approximate durations between consecutive, distinct market timestamps."""
    durations: dict[str, timedelta] = defaultdict(timedelta)
    timed = [(timestamp, item) for item in observations if (timestamp := _observation_timestamp(item)) is not None]
    timed.sort(key=lambda pair: pair[0])
    intervals = 0
    for (timestamp, item), (next_timestamp, _) in zip(timed, timed[1:]):
        if next_timestamp > timestamp and len(item["_observation_states"]) == 1:
            durations[item["_observation_states"][0]] += next_timestamp - timestamp
            intervals += 1
    return dict(durations), intervals


def _render_observation(item: dict[str, Any]) -> list[str]:
    states = item["_observation_states"]
    records = item["_observation_records"]
    lines = [
        f"market_data_timestamp: {_text(_market_timestamp_value(item))}",
        f"state: {states[0] if len(states) == 1 else ', '.join(states)}",
        f"prediction timestamp: {item['_prediction_timestamp'].isoformat()}",
        f"identity type: {item['_identity_type']}",
        f"predictions_for_observation: {len(records)}",
    ]
    if len(states) > 1:
        lines.extend(["STATE_CONFLICT_WITHIN_SAME_MARKET_OBSERVATION", f"recorded states: {', '.join(states)}"])
    return lines


def _render_snapshot(item: dict[str, Any], duplicate_hashes: dict[str, int]) -> list[str]:
    timestamp = item["_prediction_timestamp"].isoformat()
    market_timestamp = item.get("market_data_timestamp") or _nested(item, "data_quality", "latest_bar_timestamp")
    leaders = item.get("rs_leaders") if isinstance(item.get("rs_leaders"), list) else []
    leader_names = [_text(row.get("asset")) for row in leaders[:3] if isinstance(row, dict)]
    identity = item.get("market_data_hash")
    hash_label = "LEGACY — NO MARKET_DATA_HASH" if not identity else str(identity)
    if identity in duplicate_hashes:
        hash_label += f" [DUPLICATE x{duplicate_hashes[str(identity)]}]"
    return [
        f"{timestamp} | {_state(item)}",
        f"Market data: {_text(market_timestamp)}",
        f"BTC: 1H {_text(_nested(item, 'btc_structure_1h', 'trend'))} | 4H {_text(_nested(item, 'btc_structure_4h', 'trend'))}",
        f"Evidence: C{_text(item.get('continuation_evidence'))} / Corr{_text(item.get('correction_evidence'))} / N{_text(item.get('neutral_evidence'))}",
        f"Breadth: EMA20 {_percent(_nested(item, 'breadth', 'above_ema20_pct'))} | EMA50 {_percent(_nested(item, 'breadth', 'above_ema50_pct'))} | {_text(_nested(item, 'breadth_delta', 'classification'))}",
        f"Sell pressure: 4H {_text(_nested(item, 'sell_pressure', '4h', 'classification'))} {_number(_nested(item, 'sell_pressure', '4h', 'ratio'), 2)} | 12H {_text(_nested(item, 'sell_pressure', '12h', 'classification'))} {_number(_nested(item, 'sell_pressure', '12h', 'ratio'), 2)}",
        f"Retention: {_percent(item.get('breakout_retention_pct'))} | Pullback: {_percent(item.get('median_pullback_depth_pct'))}",
        f"RS: {', '.join(leader_names) if leader_names else 'N/A'}",
        f"market_data_hash: {hash_label}",
    ]


def render_history(
    snapshots: list[dict[str, Any]],
    *,
    hours: float = 24,
    now: datetime | None = None,
    missing: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
) -> str:
    end = _utc_now(now)
    observations = independent_observations(snapshots)
    states = [item["_observation_states"][0] if len(item["_observation_states"]) == 1 else "STATE_CONFLICT_WITHIN_SAME_MARKET_OBSERVATION" for item in observations]
    changes = collapsed_states(states)
    duplicates = _duplicate_hashes(snapshots)
    legacy_timestamps = _legacy_timestamp_counts(snapshots)
    modern_count = sum(item["_identity_type"] == "HASH" for item in observations)
    legacy_grouped_count = sum(item["_identity_type"] == "LEGACY_TIMESTAMP" for item in observations)
    unknown_count = sum(
        not item.get("market_data_hash") and (
            not _market_timestamp_value(item)
            or _safe_market_timestamp(_market_timestamp_value(item)) is None
        )
        for item in snapshots
    )
    duplicate_modern_count = sum(count - 1 for count in duplicates.values())
    duplicate_legacy_count = sum(count - 1 for count in legacy_timestamps.values() if count > 1)
    lines = [f"MARKET TRANSITION HISTORY — LAST {hours:g}H", ""]
    lines.extend(["RAW PREDICTION TIMELINE:", ""])
    if snapshots:
        for item in snapshots:
            lines.extend(_render_snapshot(item, duplicates))
            lines.append("")
    else:
        lines.extend(["No predictions recorded in this window.", ""])
    lines.extend(["INDEPENDENT OBSERVATION TIMELINE:", ""])
    if observations:
        for item in observations:
            lines.extend(_render_observation(item))
            lines.append("")
    else:
        lines.extend(["NONE", ""])
    lines.extend(["TRANSITION TIMELINE:", " → ".join(states) if states else "NONE", "", "STATE CHANGES:", " → ".join(changes) if changes else "NONE", "", "SUMMARY:"])
    lines.append(f"Predictions in window: {len(snapshots)}")
    lines.append(f"Independent market observations: {len(observations)}")
    lines.append(f"Modern hash-identified observations: {modern_count}")
    lines.append(f"Legacy timestamp-grouped observations: {legacy_grouped_count}")
    lines.append(f"Legacy independence unknown: {unknown_count}")
    lines.append(f"Duplicate modern hashes: {duplicate_modern_count}")
    lines.append(f"Duplicate legacy market timestamps: {duplicate_legacy_count}")
    if duplicates:
        lines.append("Duplicate modern hash details: " + ", ".join(f"{key} (x{count})" for key, count in sorted(duplicates.items())))
    lines.append(f"Missing scheduled observations: {len(missing) if missing is not None else 'UNAVAILABLE'}")
    raw_shares = Counter(_state(item) for item in snapshots)
    lines.append("RAW PREDICTION SHARE:")
    if snapshots:
        for state in sorted(raw_shares):
            lines.append(f"  {state}: {raw_shares[state] / len(snapshots) * 100:.1f}% ({raw_shares[state]}/{len(snapshots)})")
    else:
        lines.append("  NONE")
    shares = Counter(states)
    lines.append("INDEPENDENT OBSERVATION SHARE:")
    if observations:
        for state in sorted(shares):
            lines.append(f"  {state}: {shares[state] / len(observations) * 100:.1f}% ({shares[state]}/{len(observations)})")
    else:
        lines.append("  NONE")
    durations, duration_intervals = _state_durations(observations)
    if duration_intervals:
        lines.append("OBSERVED STATE DURATION APPROXIMATION:")
        for state in sorted(durations):
            lines.append(f"  {state}: {durations[state].total_seconds() / 3600:.2f}h")
    else:
        lines.append("INSUFFICIENT_INDEPENDENT_TIMESTAMPS_FOR_DURATION_ESTIMATE")
    lines.append(f"State transitions: {max(0, len(changes) - 1)}")
    lines.append(f"Latest state: {states[-1] if states else 'NONE'}")
    freshness = None
    if observations:
        latest = observations[-1]
        market_timestamp = latest.get("market_data_timestamp") or _nested(latest, "data_quality", "latest_bar_timestamp")
        try:
            freshness = max(0.0, (end - parse_timestamp(market_timestamp)).total_seconds() / 3600)
        except ValueError:
            freshness = None
    lines.append(f"Latest data freshness: {freshness:.2f}h" if freshness is not None else "Latest data freshness: UNAVAILABLE")
    if unknown_count:
        lines.extend(["", "WARNING:", "LEGACY_OBSERVATION_INDEPENDENCE_UNCERTAIN"])
    if warnings:
        lines.extend(["", f"WARNINGS ({len(warnings)} malformed/partial files):", *[f"- {warning}" for warning in warnings]])
    return "\n".join(lines)


def build_report(
    *, hours: float = 24, now: datetime | None = None,
    prediction_dir: Path = PREDICTIONS, missing_dir: Path = MISSING_OBSERVATIONS,
) -> str:
    current = _utc_now(now)
    snapshots, warnings = load_history(prediction_dir, hours=hours, now=current)
    missing, missing_warnings = load_missing_observations(missing_dir, hours=hours, now=current)
    return render_history(snapshots, hours=hours, now=current, missing=missing, warnings=warnings + missing_warnings)


def main() -> None:
    parser = argparse.ArgumentParser(description="Print immutable market-transition prediction history")
    parser.add_argument("--hours", type=float, default=24, help="UTC lookback window in hours (default: 24)")
    args = parser.parse_args()
    if args.hours <= 0:
        parser.error("--hours must be greater than zero")
    print(build_report(hours=args.hours))


if __name__ == "__main__":
    main()
