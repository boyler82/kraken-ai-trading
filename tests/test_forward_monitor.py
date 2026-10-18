from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import forward_monitor as monitor
import run_daily_quant_system as daily_quant


def registry(path: Path, *, name: str = monitor.STRATEGY_ID, opens: int = 0, digest: str = "frozen") -> Path:
    path.write_text(json.dumps({
        "trading_capability": "DISABLED",
        "entries": [{
            "strategy_name": "RANGE_FIXED_5", "forward_experiment_name": name,
            "governance_state": "COLLECTING", "frozen_strategy_spec_hash": digest,
            "activated_at": "2026-01-01T00:00:00Z", "open_outcomes": opens,
            "trading_capability": "DISABLED",
        }],
    }))
    return path


def frozen(digest: str = "frozen") -> dict:
    return {"base_config_sha256": digest}


def test_wrapper_is_executable_and_uses_repository_venv():
    wrapper = ROOT / "forward-monitor"
    assert wrapper.exists() and os.access(wrapper, os.X_OK)
    source = wrapper.read_text()
    assert '.venv-research/bin/python' in source
    assert 'exec "$PYTHON" "$ROOT_DIR/scripts/forward_monitor.py"' in source


def test_zero_open_is_verified_read_only_noop(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(monitor, "verify_frozen", lambda _: called.append("verified") or frozen())
    monkeypatch.setattr(monitor, "open_entries", lambda _: [])
    output = monitor.run(registry(tmp_path / "registry.json"), tmp_path / "db",
                         execute=lambda **_: pytest.fail("must not execute"),
                         refresh=lambda **_: pytest.fail("must not refresh"))
    assert called == ["verified"]
    assert "open observations: 0\naction: NONE\nstatus: SAFE" in output


def test_open_resolution_refresh_and_idempotent_rerun(tmp_path, monkeypatch):
    state = {"open": [{"signal_id": "s"}], "executions": 0, "refreshes": 0}
    monkeypatch.setattr(monitor, "verify_frozen", lambda _: frozen())
    monkeypatch.setattr(monitor, "open_entries", lambda _: list(state["open"]))
    def execute(**_):
        state["executions"] += 1
        state["open"] = []
        return {"status": "OFFICIAL_MONITOR_COMPLETE", "trading_capability": "DISABLED"}
    def refresh(**_): state["refreshes"] += 1
    path = registry(tmp_path / "registry.json", opens=1)
    output = monitor.run(path, tmp_path / "db", execute=execute, refresh=refresh)
    assert "resolved observations: 1" in output and state == {"open": [], "executions": 1, "refreshes": 1}
    registry(path, opens=0)
    monitor.run(path, tmp_path / "db", execute=execute, refresh=refresh)
    assert state["executions"] == 1


def test_incomplete_evidence_and_hash_mismatch_abort(tmp_path, monkeypatch):
    path = registry(tmp_path / "registry.json", opens=1)
    monkeypatch.setattr(monitor, "open_entries", lambda _: [{"signal_id": "s"}])
    monkeypatch.setattr(monitor, "verify_frozen", lambda _: frozen())
    with pytest.raises(RuntimeError, match="INSUFFICIENT_PUBLIC_MARKET_EVIDENCE"):
        monitor.run(path, tmp_path / "db", execute=lambda **_: (_ for _ in ()).throw(
            RuntimeError("INSUFFICIENT_PUBLIC_MARKET_EVIDENCE_ABORT")))
    monkeypatch.setattr(monitor, "verify_frozen", lambda _: frozen("changed"))
    with pytest.raises(RuntimeError, match="FROZEN_HASH_MISMATCH"):
        monitor.run(path, tmp_path / "db")


def test_unsupported_active_experiment_fails_closed(tmp_path):
    with pytest.raises(RuntimeError, match="UNSUPPORTED_ACTIVE_EXPERIMENT"):
        monitor.run(registry(tmp_path / "registry.json", name="UNKNOWN"), tmp_path / "db")


@pytest.mark.archive
def test_daily_attention_is_read_only():
    before = hashlib.sha256(monitor.DB_PATH.read_bytes()).hexdigest()
    attention = daily_quant.forward_attention({"open_observations": 2}, daily_quant.utc("2026-09-06T00:00:00Z"))
    assert attention["required_command"] == "./forward-monitor"
    assert hashlib.sha256(monitor.DB_PATH.read_bytes()).hexdigest() == before


def test_no_private_kraken_or_trading_capability():
    sources = "\n".join((ROOT / name).read_text().lower() for name in (
        "forward-monitor", "scripts/forward_monitor.py", "scripts/resolve_range_fixed_5_v2_expired.py"))
    ast.parse((ROOT / "scripts/forward_monitor.py").read_text())
    assert "/private/" not in sources and "addorder" not in sources and "cancelorder" not in sources
    assert "trading_capability" in sources and "disabled" in sources
