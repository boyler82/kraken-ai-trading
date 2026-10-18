from __future__ import annotations

import ast
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import range_fixed_5_v2_data_coverage as coverage


NOW = datetime(2026, 9, 1, 12, 30, tzinfo=timezone.utc)


def rows(start="2026-08-01T00:00:00Z", count=720):
    stamps = pd.date_range(start=start, periods=count, freq="1h", tz="UTC")
    return pd.DataFrame({"timestamp": stamps, "open": 100.0, "high": 101.0,
                         "low": 99.0, "close": 100.0, "volume": 10.0})


def test_missing_dataset_has_explicit_root_cause(tmp_path):
    result = coverage.diagnose_dataset("MISS", "MISSUSD", NOW, tmp_path)
    assert result["root_cause"] == "NO_LOCAL_DATA"
    assert result["expected_minimum_completed_4h_bars"] == 44


def test_existing_file_is_not_complete_without_actual_usable_bars(tmp_path):
    rows(count=40).to_csv(tmp_path / "SHORTUSD_1H.csv", index=False)
    result = coverage.diagnose_dataset("SHORT", "SHORTUSD", NOW, tmp_path)
    assert result["root_cause"] == "INSUFFICIENT_HISTORY"
    assert result["usable_completed_4h_bars"] < 44


def test_diagnostics_detect_duplicates_invalid_nonmonotonic_and_gaps(tmp_path):
    frame = rows(count=220)
    frame = frame.drop(index=[30, 31])
    duplicate = frame.iloc[[20]].copy()
    invalid = frame.iloc[[21]].copy(); invalid["high"] = 1
    combined = pd.concat([frame.iloc[::-1], duplicate, invalid], ignore_index=True)
    combined.to_csv(tmp_path / "BADUSD_1H.csv", index=False)
    result = coverage.diagnose_dataset("BAD", "BADUSD", NOW, tmp_path)
    assert result["duplicate_timestamps"] >= 1
    assert result["malformed_rows"] >= 1
    assert result["non_monotonic_timestamps"] is True
    assert result["missing_expected_1h_bars"] >= 2


def test_valid_dataset_with_nonapplicable_feature_is_classified_other(tmp_path):
    frame = rows(start="2026-08-02T12:00:00Z", count=720)
    frame.to_csv(tmp_path / "VALIDUSD_1H.csv", index=False)
    decision = {"asset": "VALID", "pair": "VALIDUSD", "eligibility_status": "NOT_ELIGIBLE_DATA_INCOMPLETE",
                "reference_close": 100, "atr14": 1, "range_low": 99, "range_high": 101,
                "range_position_pct": 50, "rqi_score": None, "rqi_classification": "NOT_APPLICABLE",
                "freshness_status": "FRESH"}
    result = coverage.audit_incomplete({"snapshots": [decision]}, NOW, tmp_path)[0]
    assert result["root_cause"] == "OTHER" and result["status"] == "NON_DATA_FEATURE_INCOMPLETE"
    assert result["missing_v2_features"] == ["rqi_score"]


def test_public_backfill_preserves_merges_sorts_and_deduplicates(tmp_path):
    existing = rows(start="2026-08-30T00:00:00Z", count=24)
    existing.to_csv(tmp_path / "TESTUSD_1H.csv", index=False)
    incoming = rows(start="2026-08-30T20:00:00Z", count=60)
    ohlc_rows = []
    for _, row in incoming.iterrows():
        ohlc_rows.append([int(row.timestamp.timestamp()), row.open, row.high, row.low, row.close,
                          row.close, row.volume, 1])
    payload = {"error": [], "result": {"TESTUSD": ohlc_rows, "last": int(incoming.iloc[-1].timestamp.timestamp())}}
    result = coverage.backfill_pair("TESTUSD", NOW, tmp_path, lambda *_: payload, max_requests=2)
    saved = pd.read_csv(tmp_path / "TESTUSD_1H.csv")
    stamps = pd.to_datetime(saved["timestamp"], utc=True)
    assert result["status"] == "BACKFILLED"
    assert stamps.is_monotonic_increasing and not stamps.duplicated().any()
    assert pd.Timestamp("2026-08-30T00:00:00Z") in set(stamps)


def test_coverage_gate_boundaries():
    def summary(pairs, incomplete):
        scan = {"eligible_kraken_pairs": pairs, "eligible_opportunities": 0,
                "rejection_reason_distribution": {}, "snapshots": [
                    {"eligibility_status": "NOT_ELIGIBLE_DATA_INCOMPLETE"} for _ in range(incomplete)
                ]}
        diagnostics = [{"status": "DATASET_DEFICIENT", "root_cause": "INSUFFICIENT_HISTORY"}
                       for _ in range(incomplete)]
        return coverage.coverage_summary(scan, diagnostics)
    assert summary(100, 10)["gate"] == "GREEN"
    assert summary(100, 11)["gate"] == "YELLOW"
    assert summary(100, 21)["gate"] == "RED"


def test_coverage_module_has_no_private_or_execution_path():
    source = (ROOT / "scripts/range_fixed_5_v2_data_coverage.py").read_text()
    tree = ast.parse(source)
    imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imports |= {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(token in name.lower() for name in imports for token in
                   ("order", "position", "paper", "trading", "krakenex", "ccxt"))
    lowered = source.lower()
    assert "/private/" not in lowered and "addorder" not in lowered and "cancelorder" not in lowered
    assert "append_activation_manifest" not in lowered and "insert into v2_" not in lowered
