from __future__ import annotations

import ast
import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import range_fixed_5_v2_universe_scanner as scanner
import range_fixed_5_v2_storage as storage


@pytest.fixture
def inactive_db(tmp_path):
    path = tmp_path / "inactive_v2.sqlite"
    config = storage.load_config()
    manifest = storage.build_manifest(config, "2026-08-27T00:00:00+00:00")
    storage.initialize_database(path, config, manifest)
    return path


def synthetic_ohlcv(now: datetime) -> pd.DataFrame:
    cutoff = pd.Timestamp(now).floor("4h")
    stamps = pd.date_range(end=cutoff - pd.Timedelta(hours=1), periods=480, freq="1h", tz="UTC")
    index = np.arange(480)
    closes = 105 + 3.4 * np.sin(2 * np.pi * (index - 3) / 48)
    opens = np.r_[closes[0], closes[:-1]]
    return pd.DataFrame({
        "timestamp": stamps, "open": opens, "high": np.maximum(opens, closes) + 0.35,
        "low": np.minimum(opens, closes) - 0.35, "close": closes, "volume": 5000.0,
    })


def included(asset="SYNTH", pair="SYNTHUSD", rank=1):
    return {
        "coingecko_id": asset.lower(), "symbol": asset, "market_cap_rank": rank,
        "selected_kraken_pair": pair, "inclusion_status": "INCLUDED", "exclusion_reason": None,
        "kraken_24h_quote_volume": 2_000_000.0, "bid_ask_spread_pct": 0.1,
    }


def metadata(now, fresh=True):
    return {"source": "TEST_DYNAMIC_UNIVERSE", "observed_at": now.isoformat(),
            "generated_at": now.isoformat(), "age_hours": 0 if fresh else 99, "fresh": fresh}


class AdvancingClock:
    def __init__(self, start):
        self.value = start

    def __call__(self):
        self.value += timedelta(milliseconds=10)
        return self.value


class GuardSpy:
    instances = 0

    def __init__(self):
        GuardSpy.instances += 1
        self.calls = 0

    def check(self):
        self.calls += 1


def ticker(received):
    payload = {"error": [], "result": {"SYNTHUSD": {
        "b": ["99.90", "1", "1"], "a": ["100.00", "1", "1"], "status": "online",
    }}}
    return payload, received


def test_full_preview_success_uses_one_shared_guard_and_writes_no_official_rows(monkeypatch, inactive_db):
    now = datetime.now(timezone.utc)
    raw = synthetic_ohlcv(now)
    before = scanner.production_status(inactive_db)
    guard = GuardSpy()
    seen = []
    original = scanner.preview_entry_quote

    def wrapped(pair, passed_guard, fetcher, wall_clock):
        seen.append(passed_guard)
        return original(pair, passed_guard, fetcher, wall_clock)

    monkeypatch.setattr(scanner, "preview_entry_quote", wrapped)
    wall = AdvancingClock(now)
    result = scanner.run_scan(
        [included()], metadata(now), lambda _: (raw, "synthetic.csv"),
        lambda *_: ticker(wall() + timedelta(milliseconds=10)), wall, guard,
        db_path=inactive_db,
    )
    assert result["status"] == "PREVIEW_COMPLETE"
    assert result["assets_evaluated"] == 1 and result["eligible_opportunities"] == 1
    assert result["opportunities"][0]["entry_preview"]["status"] == "PREVIEW_ENTRY_ONLY"
    assert result["opportunities"][0]["entry_preview"]["target_price"] == 105
    assert result["opportunities"][0]["entry_preview"]["stop_price"] == 98
    assert seen == [guard] and guard.calls >= 5
    assert result["safety"] == {"official_records_written": 0, "orders_placed": 0,
                                "signals_created": 0, "clock_guard_identity": id(guard)}
    assert scanner.production_status(inactive_db) == before


def test_scanner_constructs_exactly_one_guard(monkeypatch, inactive_db):
    now = datetime.now(timezone.utc)
    GuardSpy.instances = 0
    monkeypatch.setattr(scanner, "ClockSafetyGuard", GuardSpy)
    result = scanner.run_scan([], metadata(now), db_path=inactive_db)
    assert result["status"] == "PREVIEW_COMPLETE" and GuardSpy.instances == 1


def test_stale_universe_metadata_fails_closed_before_snapshot(inactive_db):
    now = datetime.now(timezone.utc)
    called = []
    result = scanner.run_scan([included()], metadata(now, fresh=False), lambda _: called.append(1),
                              db_path=inactive_db)
    assert called == [] and result["assets_evaluated"] == 0
    assert result["rejection_reason_distribution"] == {"UNIVERSE_METADATA_STALE": 1}


def test_mixed_component_cutoffs_produce_timestamp_illegal_snapshot(inactive_db):
    now = datetime.now(timezone.utc)
    raw = synthetic_ohlcv(now)

    def mixed(cutoff):
        values = {name: cutoff.isoformat() for name in ("price", "range", "rqi", "liquidity", "spread", "universe")}
        values["spread"] = (cutoff - timedelta(hours=1)).isoformat()
        return values

    result = scanner.run_scan([included()], metadata(now), lambda _: (raw, "synthetic.csv"),
                              wall_clock=AdvancingClock(now), component_cutoff_factory=mixed,
                              db_path=inactive_db)
    assert result["assets_evaluated"] == 1 and result["eligible_opportunities"] == 0
    assert result["snapshots"][0]["eligibility_status"] == "NOT_ELIGIBLE_TIMESTAMP_ILLEGAL"


def test_duplicate_assets_and_pairs_are_suppressed(inactive_db):
    now = datetime.now(timezone.utc)
    raw = synthetic_ohlcv(now)
    rows = [included("SYNTH", "SYNTHUSD", 1), included("SYNTH", "OTHERUSD", 2),
            included("OTHER", "SYNTHUSD", 3)]
    result = scanner.run_scan(rows, metadata(now), lambda _: (raw, "synthetic.csv"),
                              wall_clock=AdvancingClock(now), db_path=inactive_db)
    assert result["assets_evaluated"] == 1
    assert {item["reason"] for item in result["mapping_conflicts"]} == {"DUPLICATE_ASSET", "DUPLICATE_PAIR_MAPPING"}


def test_explicit_universe_exclusions_are_reported_without_evaluation(inactive_db):
    now = datetime.now(timezone.utc)
    excluded = {**included("USDT", "", 3), "inclusion_status": "EXCLUDED",
                "exclusion_reason": "STABLECOIN_OR_FIAT_PEG"}
    result = scanner.run_scan([excluded], metadata(now), db_path=inactive_db)
    assert result["assets_evaluated"] == 0
    assert result["exclusions"] == [{"asset": "USDT", "pair": None, "reason": "STABLECOIN_OR_FIAT_PEG"}]


def test_missing_ohlcv_is_an_immutable_in_memory_incomplete_decision(inactive_db):
    now = datetime.now(timezone.utc)
    result = scanner.run_scan([included()], metadata(now),
                              lambda _: (_ for _ in ()).throw(FileNotFoundError("missing")),
                              wall_clock=AdvancingClock(now), db_path=inactive_db)
    assert result["snapshots"][0]["eligibility_status"] == "NOT_ELIGIBLE_DATA_INCOMPLETE"
    assert result["snapshots"][0]["preview_only"] is True
    assert result["eligible_opportunities"] == 0


def test_local_universe_age_is_explicit(tmp_path):
    now = datetime.now(timezone.utc)
    path = tmp_path / "universe.json"
    path.write_text(__import__("json").dumps({"generated_at_utc": (now - timedelta(hours=9)).isoformat(), "assets": []}))
    _, info = scanner.load_local_universe(path, now)
    assert info["age_hours"] == 9 and info["fresh"] is False


def test_scanner_source_has_no_activation_private_or_execution_capability():
    source = (ROOT / "scripts/range_fixed_5_v2_universe_scanner.py").read_text()
    tree = ast.parse(source)
    imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imports |= {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(token in name.lower() for name in imports for token in
                   ("order", "position", "paper", "trading", "krakenex", "ccxt"))
    lowered = source.lower()
    assert "append_activation_manifest" not in lowered and "/private/" not in lowered
    assert "addorder" not in lowered and "cancelorder" not in lowered
    assert "insert into v2_" not in lowered and "update v2_" not in lowered


@pytest.mark.archive
def test_preview_preserves_production_database_and_v1_stores(inactive_db):
    production = ROOT / "FORWARD_RESEARCH/RANGE_FIXED_5_FORWARD_V2/range_fixed_5_forward_v2.sqlite"
    stores = [ROOT / "PAPER_RESEARCH", ROOT / "RESEARCH_MEMORY"]

    def digest(path):
        if path.is_file():
            return hashlib.sha256(path.read_bytes()).hexdigest()
        values = [(str(file.relative_to(ROOT)), hashlib.sha256(file.read_bytes()).hexdigest())
                  for file in sorted(path.rglob("*")) if file.is_file()]
        return hashlib.sha256(repr(values).encode()).hexdigest()

    before = [digest(production), *(digest(path) for path in stores)]
    scanner.run_scan([], metadata(datetime.now(timezone.utc)), db_path=inactive_db)
    after = [digest(production), *(digest(path) for path in stores)]
    assert after == before


def test_human_summary_contains_preview_and_polish_disclaimers(inactive_db):
    now = datetime.now(timezone.utc)
    result = scanner.run_scan([], metadata(now), db_path=inactive_db)
    text = scanner.render_summary(result)
    assert "PREVIEW ONLY" in text and "PODSUMOWANIE PO POLSKU" in text
    assert "NO ORDERS PLACED" in text and "NO OFFICIAL FORWARD OBSERVATIONS CREATED" in text


@pytest.mark.archive
def test_preview_refuses_activated_production_database():
    with pytest.raises(RuntimeError, match="PREVIEW_SCANNER_REQUIRES_INACTIVE_COHORT"):
        scanner.run_scan([], metadata(datetime.now(timezone.utc)))
