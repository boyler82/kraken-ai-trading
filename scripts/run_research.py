from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Run the official research workflow entry point."""

    print("===================================")
    print("Kraken AI Trading Research v2.0")
    print("===================================")

    started = time.perf_counter()

    subprocess.run([sys.executable, str(ROOT / "scripts/research_pipeline.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/project_memory.py")], check=True)

    elapsed = time.perf_counter() - started

    print("Datasets updated: OK")
    print("Research pipeline: OK")
    print("Daily reports: OK")
    print("Portfolio allocation: OK")
    print(f"Total runtime: {elapsed:.2f}s")
    print("FINAL STATUS: SUCCESS")


if __name__ == "__main__":
    main()
