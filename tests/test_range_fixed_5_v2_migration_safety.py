from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import range_fixed_5_v2_storage as storage


def tree_hashes(path: Path) -> dict[str, str]:
    return {
        str(file.relative_to(ROOT)): hashlib.sha256(file.read_bytes()).hexdigest()
        for file in sorted(path.rglob("*")) if file.is_file()
    }


def test_v2_initialization_preserves_all_v1_research_stores():
    before = {
        "PAPER_RESEARCH": tree_hashes(ROOT / "PAPER_RESEARCH"),
        "RESEARCH_MEMORY": tree_hashes(ROOT / "RESEARCH_MEMORY"),
    }
    with TemporaryDirectory() as directory:
        temp_root = Path(directory)
        (temp_root / "config").mkdir()
        source_config = ROOT / "config/range_fixed_5_forward_v2.json"
        (temp_root / "config/range_fixed_5_forward_v2.json").write_bytes(source_config.read_bytes())
        storage.initialize_foundation(temp_root)
    after = {
        "PAPER_RESEARCH": tree_hashes(ROOT / "PAPER_RESEARCH"),
        "RESEARCH_MEMORY": tree_hashes(ROOT / "RESEARCH_MEMORY"),
    }
    assert after == before
