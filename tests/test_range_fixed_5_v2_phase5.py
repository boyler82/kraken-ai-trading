from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import range_fixed_5_v2_entry as entry
import range_fixed_5_v2_monitor as monitor
from test_range_fixed_5_v2_phase4 import Times, create_ready_signal, ticker


ENTRY = "2026-09-01T12:00:07Z"
EXPIRY = "2026-09-06T12:00:07Z"


def ready(path: Path) -> str:
    _, signal = create_ready_signal(path)
    result = entry.observe_entry(path, signal["signal_id"], lambda *_: (ticker(), ENTRY),
                                 Times("2026-09-01T12:00:06Z"), lambda _: None)
    assert result["status"] == "ENTRY_OBSERVED"
    return signal["signal_id"]


def trade(stamp: str, price: float, sequence: int = 0):
    return {"timestamp": stamp, "price": price, "sequence": sequence, "pair": "TESTUSD"}


def bar(opened: str, closed: str, high: float, low: float):
    return {"open_timestamp": opened, "close_timestamp": closed, "open": 100, "high": high,
            "low": low, "close": 100, "volume": 1}


@pytest.mark.parametrize(("price", "expected"), [(105, "TARGET_HIT"), (98, "STOP_HIT")])
def test_exact_target_only_and_stop_only(tmp_path, price, expected):
    path = tmp_path / "v2.sqlite"; signal = ready(path)
    result = monitor.monitor_observation(path, signal,
        trades=[trade("2026-09-01T13:00:00Z", price)], observed_at="2026-09-01T14:00:00Z")
    assert result["outcome"]["terminal_outcome"] == expected
    assert result["outcome"]["total_fee_pct"] == .4
    assert result["outcome"]["total_slippage_pct"] == 0
    assert result["outcome"]["net_return_pct"] == pytest.approx(result["outcome"]["gross_return_pct"] - .4)


def test_same_bar_ambiguous_is_conservative_stop_first_and_hashed(tmp_path):
    path = tmp_path / "v2.sqlite"; signal = ready(path)
    result = monitor.monitor_observation(path, signal, bars=[bar("2026-09-01T13:00:00Z",
        "2026-09-01T14:00:00Z", 106, 97)], observed_at="2026-09-01T14:01:00Z")
    assert result["outcome"]["terminal_outcome"] == "STOP_HIT"
    db = sqlite3.connect(path)
    payload = json.loads(db.execute("SELECT canonical_payload_json FROM v2_monitor_events WHERE event_type='STOP_HIT'").fetchone()[0])
    assert payload["ambiguity_flag"] == "INTRABAR_ORDER_UNKNOWN"
    assert payload["resolution_policy"] == "CONSERVATIVE_STOP_FIRST"
    assert len(payload["raw_evidence_sha256"]) == 64


def test_exact_trade_ordering_and_pre_entry_exclusion(tmp_path):
    path = tmp_path / "v2.sqlite"; signal = ready(path)
    result = monitor.monitor_observation(path, signal, trades=[
        trade("2026-09-01T12:00:06Z", 98),
        trade("2026-09-01T13:00:00Z", 105, 1),
        trade("2026-09-01T13:00:00Z", 98, 2)], observed_at="2026-09-01T14:00:00Z")
    assert result["outcome"]["terminal_outcome"] == "TARGET_HIT"


def test_bar_overlapping_entry_is_excluded(tmp_path):
    path = tmp_path / "v2.sqlite"; signal = ready(path)
    result = monitor.monitor_observation(path, signal, bars=[bar("2026-09-01T12:00:00Z",
        "2026-09-01T13:00:00Z", 106, 97)], observed_at="2026-09-01T14:00:00Z")
    assert result["status"] == "OPEN"


def test_time_expiry_uses_first_valid_bid_and_costs(tmp_path):
    path = tmp_path / "v2.sqlite"; signal = ready(path)
    result = monitor.monitor_observation(path, signal, bids=[
        {"timestamp": "2026-09-06T12:00:06Z", "best_bid": 200},
        {"timestamp": "2026-09-06T12:00:08Z", "best_bid": 101}],
        entry_slippage_pct=.03, exit_slippage_pct=.04, observed_at="2026-09-06T12:01:00Z")
    outcome = result["outcome"]
    assert outcome["terminal_outcome"] == "TIME_EXIT" and outcome["exit_reference_price"] == 101
    assert outcome["total_slippage_pct"] == pytest.approx(.07)
    assert outcome["total_transaction_cost_pct"] == pytest.approx(.47)


def structure_bars():
    rows = []
    base = monitor.utc("2026-09-01T12:00:00Z")
    for index in range(16):
        price = 100 if index < 14 else 88
        rows.append({"timestamp": (base + monitor.timedelta(hours=4 * index)).isoformat(),
                     "open": price, "high": price + 1, "low": price - 1, "close": price, "volume": 1})
    return rows


def test_structure_invalidation_requires_completed_4h_confirmation(tmp_path):
    path = tmp_path / "v2.sqlite"; signal = ready(path)
    incomplete = monitor.monitor_observation(path, signal, completed_4h=structure_bars()[:-1],
                                             observed_at="2026-09-04T00:00:00Z")
    assert incomplete["status"] == "OPEN"
    result = monitor.monitor_observation(path, signal, completed_4h=structure_bars(),
                                         observed_at="2026-09-04T12:01:00Z")
    assert result["outcome"]["terminal_outcome"] == "STRUCTURE_INVALIDATION"
    assert result["outcome"]["exit_timestamp"] == "2026-09-04T04:00:00+00:00"


def test_touch_before_invalidation_wins_by_timestamp(tmp_path):
    path = tmp_path / "v2.sqlite"; signal = ready(path)
    result = monitor.monitor_observation(path, signal, trades=[trade("2026-09-02T00:00:00Z", 105)],
        completed_4h=structure_bars(), observed_at="2026-09-04T12:01:00Z")
    assert result["outcome"]["terminal_outcome"] == "TARGET_HIT"


def test_missing_data_never_fabricates_time_exit(tmp_path):
    path = tmp_path / "v2.sqlite"; signal = ready(path)
    result = monitor.monitor_observation(path, signal,
        bids=[{"timestamp": "2026-09-06T12:00:08Z", "best_bid": 101}], coverage_complete=False,
        data_gap="TRADES_COVERAGE_GAP", observed_at="2026-09-06T12:01:00Z")
    assert result["status"] == "OPEN_DATA_GAP"
    db = sqlite3.connect(path)
    assert db.execute("SELECT count(*) FROM v2_completed_outcomes").fetchone()[0] == 0
    assert json.loads(db.execute("SELECT canonical_payload_json FROM v2_monitor_events").fetchone()[0])["terminal_exit_fabricated"] is False


def test_rerun_idempotent_and_one_outcome_maximum(tmp_path):
    path = tmp_path / "v2.sqlite"; signal = ready(path)
    first = monitor.monitor_observation(path, signal, trades=[trade("2026-09-01T13:00:00Z", 105)],
                                        observed_at="2026-09-01T14:00:00Z")
    second = monitor.monitor_observation(path, signal, trades=[trade("2026-09-01T15:00:00Z", 98)],
                                         observed_at="2026-09-01T16:00:00Z")
    assert first["status"] == "COMPLETED" and second["status"] == "ALREADY_COMPLETED"
    db = sqlite3.connect(path)
    assert db.execute("SELECT count(*) FROM v2_completed_outcomes").fetchone()[0] == 1
    assert db.execute("SELECT count(*) FROM v2_monitor_events WHERE event_type IN ('TARGET_HIT','STOP_HIT')").fetchone()[0] == 1


def tree_hash(path: Path) -> str:
    value = hashlib.sha256()
    for file in sorted(path.rglob("*")):
        if file.is_file(): value.update(str(file.relative_to(ROOT)).encode() + b"\0" + file.read_bytes())
    return value.hexdigest()


@pytest.mark.archive
def test_production_entries_v1_and_safety_surface_unchanged():
    production = ROOT / "FORWARD_RESEARCH/RANGE_FIXED_5_FORWARD_V2/range_fixed_5_forward_v2.sqlite"
    db = sqlite3.connect(production)
    assert db.execute("SELECT count(*) FROM v2_entry_observations").fetchone()[0] == 8
    assert db.execute("SELECT count(*) FROM v2_open_observations").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM v2_completed_outcomes").fetchone()[0] == 8
    assert db.execute("SELECT count(*) FROM v2_monitor_events").fetchone()[0] == 8
    before = tree_hash(ROOT / "PAPER_RESEARCH"), tree_hash(ROOT / "RESEARCH_MEMORY")
    source = (ROOT / "scripts/range_fixed_5_v2_monitor.py").read_text()
    tree = ast.parse(source)
    imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imports |= {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(token in name.lower() for name in imports for token in ("order", "position", "paper", "ccxt", "krakenex"))
    lowered = source.lower()
    assert "/private/" not in lowered and "addorder" not in lowered and "api_key" not in lowered
    assert "simulate" not in lowered and before == (tree_hash(ROOT / "PAPER_RESEARCH"), tree_hash(ROOT / "RESEARCH_MEMORY"))
