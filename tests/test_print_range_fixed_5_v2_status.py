from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import print_range_fixed_5_v2_status as reporter
from test_range_fixed_5_v2_foundation import activate


def test_status_is_time_derived_and_read_only(tmp_path):
    path = tmp_path / "v2.sqlite"
    activate(path)
    before = path.read_bytes()
    clock = lambda: {"status": "SAFE"}
    pre = reporter.render(path, datetime(2026, 8, 31, tzinfo=timezone.utc), clock)
    post = reporter.render(path, datetime(2026, 9, 1, tzinfo=timezone.utc), clock)
    assert "Activation: ACTIVATED" in pre
    assert "  PRE_COHORT" in pre
    assert "  COLLECTING" in post
    assert "Decisions: 0" in pre and "Trading capability: DISABLED" in pre
    assert path.read_bytes() == before
