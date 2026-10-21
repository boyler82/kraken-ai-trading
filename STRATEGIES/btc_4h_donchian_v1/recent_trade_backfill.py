from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "DATASETS" / "BTC_4H_DONCHIAN_V1"
RAW_DIR = DATA_DIR / "raw_trades"
CHECKPOINT_DIR = RAW_DIR / "checkpoints"
REST_PATH = ROOT / "DATASETS" / "BTC_15M" / "BTCUSD_15m_history.csv"
BACKFILL_PATH = DATA_DIR / "BTCUSD_15m_recent_backfill.csv"
OPERATIONAL_PATH = DATA_DIR / "BTCUSD_15m_operational.csv"
REPORT_DIR = ROOT / "RESEARCH" / "BTC_4H_DONCHIAN_V1"
REPORT_MD = REPORT_DIR / "recent_backfill_report.md"
REPORT_CSV = REPORT_DIR / "recent_backfill_report.csv"
TRADES_URL = "https://api.kraken.com/0/public/Trades"
PAIR = "XBTUSD"
INTERVAL = 900
FOUR_HOURS = 14400
REST_SOURCE_PREFIX = "KRAKEN_OHLC_REST"
TRADE_FIELDS = ["timestamp", "price", "volume", "side", "order_type", "misc", "trade_id"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def last_closed_15m(now: datetime | None = None) -> int:
    value = int((now or utc_now()).timestamp())
    return (value // INTERVAL) * INTERVAL - INTERVAL


def parse_day(value: str, end: bool = False) -> int:
    moment = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if end:
        moment += timedelta(days=1)
        return int(moment.timestamp()) - INTERVAL
    return int(moment.timestamp())


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconstruct recent BTC/USD 15m candles from official Kraken trades")
    parser.add_argument("--start", help="UTC start date YYYY-MM-DD")
    parser.add_argument("--end", help="UTC inclusive end date YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rebuild-from-local", action="store_true", help="rebuild only from a matching local raw CSV; never call Kraken")
    parser.add_argument("--allow-shorter-overwrite", action="store_true", help="explicitly bypass the operational regression guard")
    parser.add_argument("--incremental", action="store_true", help="update from the existing operational tail and retain older rows")
    return parser.parse_args()


def requested_window(args: argparse.Namespace) -> tuple[int, int]:
    closed = last_closed_15m()
    end = min(parse_day(args.end, end=True), closed) if args.end else closed
    start = parse_day(args.start) if args.start else end - args.days * 86400 + INTERVAL
    if start > end:
        raise ValueError("start must not be after the last requested closed 15m candle")
    return start, end


def stable_trade_id(values: list[object]) -> str:
    payload = "|".join(str(value) for value in values[:6])
    return hashlib.sha256(payload.encode()).hexdigest()


def request_page(since: int, attempts: int = 7) -> dict:
    query = urllib.parse.urlencode({"pair": PAIR, "since": str(since)})
    errors: list[str] = []
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(f"{TRADES_URL}?{query}", headers={"User-Agent": "btc-4h-donchian-v1-research/1.0"})
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = json.loads(response.read().decode(), parse_float=Decimal)
            if payload.get("error"):
                raise RuntimeError("; ".join(payload["error"]))
            return payload
        except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
            errors.append(f"attempt {attempt + 1}: {type(exc).__name__}: {exc}")
            if attempt + 1 == attempts:
                break
            delay = min(60.0, 2 ** attempt) + random.Random(attempt).random()
            time.sleep(delay)
    raise RuntimeError("Kraken Trades request failed: " + " | ".join(errors))


def extract_page(payload: dict) -> tuple[list[dict[str, str]], int]:
    result = payload.get("result", {})
    pair_key = next((key for key in result if key != "last"), None)
    if pair_key is None or "last" not in result:
        raise ValueError("Unexpected Kraken Trades response")
    rows: list[dict[str, str]] = []
    for trade in result[pair_key]:
        if len(trade) < 6:
            raise ValueError("Malformed trade row returned by Kraken")
        trade_id = str(trade[6]) if len(trade) > 6 and str(trade[6]) else stable_trade_id(trade)
        rows.append({
            "timestamp": str(trade[2]), "price": str(trade[0]), "volume": str(trade[1]),
            "side": str(trade[3]), "order_type": str(trade[4]), "misc": str(trade[5]), "trade_id": trade_id,
        })
    return rows, int(result["last"])


def read_trades(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_atomic(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def read_candles(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def deduplicate_trades(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    unique: dict[str, dict[str, str]] = {}
    for row in rows:
        unique[row["trade_id"]] = row
    result = sorted(unique.values(), key=lambda row: (Decimal(row["timestamp"]), row["trade_id"]))
    return result, len(rows) - len(result)


def local_raw_for_days(days: int) -> tuple[Path, Path, int, int]:
    candidates: list[tuple[int, Path, Path, int, int]] = []
    for checkpoint_path in CHECKPOINT_DIR.glob("BTCUSD_trades_*.json"):
        try:
            checkpoint = json.loads(checkpoint_path.read_text())
            start, end = int(checkpoint["start"]), int(checkpoint["end"])
            raw_path = RAW_DIR / (checkpoint_path.stem + ".csv")
            if raw_path.exists() and end - start + INTERVAL >= days * 86400:
                candidates.append((end, raw_path, checkpoint_path, start, end))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    if not candidates:
        raise FileNotFoundError(f"No local raw/checkpoint pair covers at least {days} days")
    _, raw_path, checkpoint_path, start, end = max(candidates)
    return raw_path, checkpoint_path, start, end


def append_trade_page(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRADE_FIELDS, extrasaction="ignore")
        if needs_header:
            writer.writeheader()
        writer.writerows(rows)
        handle.flush()


def download_trades(start: int, end: int, raw_path: Path, checkpoint_path: Path) -> tuple[list[dict[str, str]], int, bool]:
    existing = read_trades(raw_path)
    checkpoint = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {}
    if checkpoint and not existing:
        # A cursor is useful only together with the pages durably written before it.
        checkpoint = {}
    cursor = int(checkpoint.get("cursor", start * 1_000_000_000))
    cursor = max(cursor, start * 1_000_000_000)
    pages = int(checkpoint.get("pages", 0))
    reached_end = False
    while True:
        payload = request_page(cursor)
        page, next_cursor = extract_page(payload)
        accepted = [row for row in page if start <= int(Decimal(row["timestamp"])) <= end + INTERVAL - 1]
        append_trade_page(raw_path, accepted)
        existing.extend(accepted)
        pages += 1
        max_time = max((Decimal(row["timestamp"]) for row in page), default=Decimal(0))
        reached_end = max_time >= Decimal(end + INTERVAL) or (not page and cursor >= end * 1_000_000_000)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(json.dumps({"cursor": next_cursor, "pages": pages, "start": start, "end": end, "updated_at": utc_now().isoformat()}, indent=2))
        if reached_end:
            break
        if next_cursor <= cursor:
            raise RuntimeError(f"Kraken cursor stopped before requested end: cursor={cursor}, last={next_cursor}")
        cursor = next_cursor
        time.sleep(1.05)
    unique: dict[str, dict[str, str]] = {}
    for row in existing:
        unique[row["trade_id"]] = row
    rows = sorted(unique.values(), key=lambda row: (Decimal(row["timestamp"]), row["trade_id"]))
    first_bucket = (int(Decimal(rows[0]["timestamp"])) // INTERVAL) * INTERVAL if rows else None
    last_bucket = (int(Decimal(rows[-1]["timestamp"])) // INTERVAL) * INTERVAL if rows else None
    reached_end = reached_end and first_bucket == start and last_bucket == end
    write_csv_atomic(raw_path, TRADE_FIELDS, rows)
    return rows, len(existing) - len(rows), reached_end


def reconstruct(trades: list[dict[str, str]], start: int, end: int) -> list[dict[str, str]]:
    buckets: dict[int, list[dict[str, str]]] = {}
    for trade in trades:
        timestamp = int(Decimal(trade["timestamp"]))
        bucket = (timestamp // INTERVAL) * INTERVAL
        if start <= bucket <= end:
            buckets.setdefault(bucket, []).append(trade)
    rows: list[dict[str, str]] = []
    for timestamp in sorted(buckets):
        group = sorted(buckets[timestamp], key=lambda row: (Decimal(row["timestamp"]), row["trade_id"]))
        prices = [Decimal(row["price"]) for row in group]
        volume = sum((Decimal(row["volume"]) for row in group), Decimal(0))
        rows.append({
            "timestamp": str(timestamp), "open": group[0]["price"], "high": str(max(prices)),
            "low": str(min(prices)), "close": group[-1]["price"], "volume": str(volume),
            "trades": str(len(group)), "source": "KRAKEN_TRADES_RECONSTRUCTED",
        })
    return rows


def load_rest(end: int) -> list[dict[str, str]]:
    if not REST_PATH.exists():
        raise FileNotFoundError(f"Current REST OHLC history is missing: {REST_PATH}")
    with REST_PATH.open(newline="") as handle:
        return [
            row for row in csv.DictReader(handle)
            if int(row["timestamp"]) <= end and row.get("source", "").startswith(REST_SOURCE_PREFIX)
        ]


def same_ohlcv(left: dict[str, str], right: dict[str, str]) -> bool:
    return all(Decimal(left[key]) == Decimal(right[key]) for key in ["open", "high", "low", "close", "volume"])


def merge_operational(reconstructed: list[dict[str, str]], rest: list[dict[str, str]], start: int, end: int) -> tuple[list[dict[str, str]], int, int, int]:
    rebuilt = {int(row["timestamp"]): row for row in reconstructed}
    current_rest = {int(row["timestamp"]): row for row in rest if start <= int(row["timestamp"]) <= end}
    identical = sum(same_ohlcv(rebuilt[key], current_rest[key]) for key in rebuilt.keys() & current_rest.keys())
    conflicts = len(rebuilt.keys() & current_rest.keys()) - identical
    # REST owns its recent, completed coverage; reconstructed trades fill older/missing timestamps.
    merged: dict[int, dict[str, str]] = {}
    for timestamp, row in rebuilt.items():
        merged[timestamp] = dict(row)
    for timestamp, row in current_rest.items():
        merged[timestamp] = {**row, "trades": "", "source": row.get("source") or REST_SOURCE_PREFIX}
    rows = [merged[key] for key in sorted(merged)]
    return rows, identical, conflicts, len(current_rest)


def retain_existing_history(existing: list[dict[str, str]], updated: list[dict[str, str]]) -> list[dict[str, str]]:
    merged = {int(row["timestamp"]): dict(row) for row in existing}
    merged.update({int(row["timestamp"]): dict(row) for row in updated})
    return [merged[timestamp] for timestamp in sorted(merged)]


def quality(rows: list[dict[str, str]], start: int, end: int) -> dict[str, object]:
    timestamps = [int(row["timestamp"]) for row in rows]
    duplicates = len(timestamps) - len(set(timestamps))
    off_grid = sum(timestamp % INTERVAL != 0 for timestamp in timestamps)
    nan_values = 0
    ohlc_bounds = 0
    negative_volume = 0
    for row in rows:
        try:
            o, h, low, close, volume = (Decimal(row[key]) for key in ["open", "high", "low", "close", "volume"])
            if any(not value.is_finite() for value in [o, h, low, close, volume]):
                nan_values += 1
                continue
            ohlc_bounds += int(h < max(o, low, close) or low > min(o, h, close))
            negative_volume += int(volume < 0)
        except Exception:
            nan_values += 1
    deltas = [right - left for left, right in zip(timestamps, timestamps[1:])]
    expected = (end - start) // INTERVAL + 1
    covered_timestamps = {timestamp for timestamp in timestamps if start <= timestamp <= end}
    covered = len(covered_timestamps)
    missing = expected - covered
    internal_gaps = [delta // INTERVAL - 1 for delta in deltas if delta > INTERVAL]
    leading_gap = (timestamps[0] - start) // INTERVAL if timestamps else expected
    trailing_gap = (end - timestamps[-1]) // INTERVAL if timestamps else expected
    longest = max([leading_gap, trailing_gap, *internal_gaps], default=0)
    completeness = 100 * covered / expected if expected else 0.0
    segment = 1 if timestamps else 0
    for delta in reversed(deltas):
        if delta != INTERVAL:
            break
        segment += 1
    latest_segment = rows[-segment:] if segment else []
    complete_buckets: dict[int, int] = {}
    for row in latest_segment:
        timestamp = int(row["timestamp"])
        complete_buckets[(timestamp // FOUR_HOURS) * FOUR_HOURS] = complete_buckets.get((timestamp // FOUR_HOURS) * FOUR_HOURS, 0) + 1
    complete_4h = sum(count == 16 for count in complete_buckets.values())
    last_4h_closed = bool(timestamps) and timestamps[-1] + INTERVAL <= last_closed_15m() + INTERVAL
    ma_ready = complete_4h >= 200 and last_4h_closed
    return {
        "first_timestamp": timestamps[0] if timestamps else None, "last_timestamp": timestamps[-1] if timestamps else None,
        "chronological_order": timestamps == sorted(timestamps), "duplicates": duplicates, "off_grid": off_grid,
        "nan_values": nan_values, "ohlc_bound_anomalies": ohlc_bounds, "negative_volume_rows": negative_volume,
        "ohlcv_anomalies": nan_values + ohlc_bounds + negative_volume, "missing_bars": missing,
        "longest_gap_bars": longest, "completeness_pct": completeness, "complete_4h_bars_current_segment": complete_4h,
        "ma200_readiness": "READY" if ma_ready else "WARMING_UP",
    }


def evaluate_status(metrics: dict[str, object], requested_end: int, cursor_reached_requested_end: bool) -> tuple[str, str]:
    last_timestamp = metrics.get("last_timestamp")
    coverage_end_delta = int(last_timestamp) - requested_end if last_timestamp is not None else None
    data_failure = (
        coverage_end_delta is None
        or coverage_end_delta < -INTERVAL
        or metrics["completeness_pct"] != 100
        or metrics["missing_bars"] != 0
        or metrics["duplicates"] != 0
        or metrics["ohlcv_anomalies"] != 0
        or metrics["ma200_readiness"] != "READY"
    )
    if data_failure:
        return "FAIL", ""
    if not cursor_reached_requested_end:
        return (
            "PASS_WITH_WARNINGS",
            "Kraken Trades cursor did not signal the requested end, but the operational dataset covers the complete required range.",
        )
    return "PASS", ""


def coverage_metrics(metrics: dict[str, object], requested_end: int, cursor_warning_reason: str) -> dict[str, object]:
    last_timestamp = metrics.get("last_timestamp")
    return {
        "requested_end_epoch": requested_end,
        "last_timestamp_iso": (
            datetime.fromtimestamp(int(last_timestamp), timezone.utc).isoformat() if last_timestamp is not None else ""
        ),
        "coverage_end_delta_seconds": (
            int(last_timestamp) - requested_end if last_timestamp is not None else ""
        ),
        "cursor_warning_reason": cursor_warning_reason,
    }


def dataset_profile(rows: list[dict[str, str]]) -> dict[str, int | float | None]:
    timestamps = sorted({int(row["timestamp"]) for row in rows})
    complete_4h = 0
    buckets: dict[int, int] = {}
    for timestamp in timestamps:
        bucket = (timestamp // FOUR_HOURS) * FOUR_HOURS
        buckets[bucket] = buckets.get(bucket, 0) + 1
    complete_4h = sum(count == 16 for count in buckets.values())
    first = timestamps[0] if timestamps else None
    last = timestamps[-1] if timestamps else None
    calendar_days = ((last - first + INTERVAL) / 86400) if first is not None and last is not None else 0.0
    return {
        "first_timestamp": first, "last_timestamp": last, "row_count": len(rows),
        "calendar_days": calendar_days, "complete_4h_bars": complete_4h,
    }


def overwrite_guard(previous: list[dict[str, str]], rebuilt: list[dict[str, str]], allow_shorter: bool) -> tuple[bool, str, dict[str, object], dict[str, object]]:
    old = dataset_profile(previous)
    new = dataset_profile(rebuilt)
    if allow_shorter or not previous:
        return True, "BYPASSED_EXPLICITLY" if allow_shorter else "PASS_NO_PREVIOUS_DATASET", old, new
    regressions = []
    if new["row_count"] < old["row_count"]:
        regressions.append("fewer_rows")
    if new["first_timestamp"] > old["first_timestamp"] or new["last_timestamp"] < old["last_timestamp"]:
        regressions.append("shorter_range")
    if new["calendar_days"] < old["calendar_days"]:
        regressions.append("fewer_calendar_days")
    if new["complete_4h_bars"] < old["complete_4h_bars"]:
        regressions.append("fewer_complete_4h_bars")
    if regressions:
        return False, "FAIL_SAFE_NO_OVERWRITE: " + ", ".join(regressions), old, new
    return True, "PASS", old, new


def write_report(metrics: dict[str, object], status: str, dry_run: bool) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    values = {"status": status, "dry_run": dry_run, **metrics}
    with REPORT_CSV.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        writer.writerows(values.items())
    lines = ["# BTC 4H Donchian v1 Recent Trade Backfill", "", f"Status: {status}", "", "PAPER RESEARCH ONLY — LIVE_NOT_AUTHORIZED", ""]
    lines.extend(f"- {key}: {value}" for key, value in values.items() if key != "status")
    lines.extend(["", "## Merge Policy", "", "Reconstructed trades fill missing/older bars. Existing completed Kraken REST OHLC owns overlapping recent timestamps.", "No empty candle is synthesized, forward-filled, or interpolated. The canonical 2019–2024 dataset is not read or modified.", ""])
    REPORT_MD.write_text("\n".join(lines))


def main() -> None:
    args = arguments()
    start, end = requested_window(args)
    local_checkpoint_path = None
    if args.rebuild_from_local:
        raw_path, local_checkpoint_path, start, end = local_raw_for_days(args.days)
    elif args.incremental and OPERATIONAL_PATH.exists():
        existing_for_start = read_candles(OPERATIONAL_PATH)
        if existing_for_start:
            start = max(int(existing_for_start[-1]["timestamp"]), end - args.days * 86400 + INTERVAL)
    label = f"{datetime.fromtimestamp(start, timezone.utc):%Y%m%d}_{datetime.fromtimestamp(end, timezone.utc):%Y%m%d}"
    raw_path = raw_path if args.rebuild_from_local else RAW_DIR / f"BTCUSD_trades_{label}.csv"
    checkpoint_path = local_checkpoint_path or CHECKPOINT_DIR / f"BTCUSD_trades_{label}.json"
    base = {
        "requested_start": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "requested_end": datetime.fromtimestamp(end, timezone.utc).isoformat(),
        "requested_end_epoch": end,
        "raw_trade_path": raw_path,
    }
    if args.dry_run:
        write_report({**base, "raw_trades_downloaded": 0, "note": "dry-run; no network or dataset writes"}, "PASS_WITH_WARNINGS", True)
        print("PASS_WITH_WARNINGS")
        print(f"Dry run: {base['requested_start']} -> {base['requested_end']}")
        print(f"Would save raw trades: {raw_path}")
        return
    try:
        previous_operational = read_candles(OPERATIONAL_PATH)
        old_count = len(read_trades(raw_path))
        if args.rebuild_from_local:
            trades, duplicates_removed = deduplicate_trades(read_trades(raw_path))
            complete = False  # Cursor state is not inferred during an offline rebuild.
        else:
            trades, duplicates_removed, complete = download_trades(start, end, raw_path, checkpoint_path)
        reconstructed = reconstruct(trades, start, end)
        rest = load_rest(end)
        operational, identical, conflicts, rest_count = merge_operational(reconstructed, rest, start, end)
        if args.incremental:
            operational = retain_existing_history(previous_operational, operational)
        metrics = quality(operational, min(start, int(operational[0]["timestamp"])) if operational else start, end)
        status, cursor_warning_reason = evaluate_status(metrics, end, complete)
        may_overwrite, guard_status, previous_profile, rebuilt_profile = overwrite_guard(
            previous_operational, operational, args.allow_shorter_overwrite
        )
        report = {
            **base, "raw_trades_downloaded": max(len(trades) - old_count, 0), "raw_trades_total": len(trades),
            "duplicate_trades_removed": duplicates_removed, "reconstructed_15m_bars": len(reconstructed),
            "rest_bars_merged": rest_count, "identical_overlap_rows": identical, "true_ohlcv_conflicts": conflicts,
            "cursor_reached_requested_end": complete, **metrics,
            **coverage_metrics(metrics, end, cursor_warning_reason),
            "rebuild_mode": "LOCAL_RAW" if args.rebuild_from_local else ("INCREMENTAL" if args.incremental else "NETWORK"),
            "API_calls_made": 0 if args.rebuild_from_local else "not_tracked",
            "raw_source_path": raw_path,
            "previous_operational_rows": previous_profile["row_count"],
            "rebuilt_operational_rows": rebuilt_profile["row_count"],
            "overwrite_guard_status": guard_status,
            "complete_4h_bars": rebuilt_profile["complete_4h_bars"],
            "MA200 readiness": metrics["ma200_readiness"],
        }
        if not may_overwrite:
            write_report(report, "FAIL_SAFE_NO_OVERWRITE", False)
            print("FAIL_SAFE_NO_OVERWRITE")
            print(f"Saved: {REPORT_MD}")
            raise SystemExit(1)
        if status != "FAIL":
            if OPERATIONAL_PATH.exists():
                backup_stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
                backup_path = OPERATIONAL_PATH.with_name(f"{OPERATIONAL_PATH.stem}.backup_{backup_stamp}{OPERATIONAL_PATH.suffix}")
                shutil.copy2(OPERATIONAL_PATH, backup_path)
            write_csv_atomic(BACKFILL_PATH, ["timestamp", "open", "high", "low", "close", "volume", "trades", "source"], reconstructed)
            write_csv_atomic(OPERATIONAL_PATH, ["timestamp", "open", "high", "low", "close", "volume", "trades", "source"], operational)
        write_report(report, status, False)
        print(status)
        print(f"Saved: {raw_path}")
        if status != "FAIL":
            print(f"Saved: {BACKFILL_PATH}")
            print(f"Saved: {OPERATIONAL_PATH}")
        print(f"Saved: {REPORT_MD}")
        if status == "FAIL":
            raise SystemExit(1)
    except Exception as exc:
        write_report({**base, "error": f"{type(exc).__name__}: {exc}"}, "FAIL", False)
        raise


if __name__ == "__main__":
    main()
