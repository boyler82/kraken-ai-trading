from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from research_pipeline import STEPS


ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "logs" / "latest_run.log"
STATUS_PATH = ROOT / "logs" / "latest_research_run.json"
PACKET_PATH = ROOT / "DAILY_REPORTS" / "ANALYST_PACKET" / "latest_analyst_decision_packet.md"


def _tail(text: str, count: int = 20) -> list[str]:
    return [line for line in text.splitlines() if line.strip()][-count:]


def _write_status(status: str, completed: list[str], failed: list[dict], warnings: int) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        log_path = str(LOG_PATH.relative_to(ROOT))
    except ValueError:
        log_path = str(LOG_PATH)
    STATUS_PATH.write_text(json.dumps({
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "pipeline_status": status,
        "module_count": len(STEPS),
        "completed_modules": completed,
        "failed_modules": failed,
        "warnings_count": warnings,
        "log_path": log_path,
    }, indent=2) + "\n")


def _quiet_run(command: list[str], name: str, env: dict[str, str], log) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write(f"\n===== {name} =====\n")
    log.write(result.stdout or "")
    log.flush()
    return result


def run_quiet(env: dict[str, str]) -> int:
    completed: list[str] = []
    failed: list[dict] = []
    warnings = 0
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("w") as log:
        update = _quiet_run(["bash", str(ROOT / "scripts/update_crypto_data.sh")], "update_crypto_data", env, log)
        warnings += sum("warning" in line.lower() for line in (update.stdout or "").splitlines())
        if update.returncode:
            failed.append({"module": "update_crypto_data", "return_code": update.returncode})
            _write_status("FAILED", completed, failed, warnings)
            print("FAILED MODULE: update_crypto_data")
            print(f"RETURN CODE: {update.returncode}")
            print("FINAL LOG LINES:")
            print("\n".join(_tail(update.stdout or "")))
            print(f"LOG PATH: {LOG_PATH}")
            return update.returncode
        for index, step in enumerate(STEPS, 1):
            name = Path(step).stem
            result = _quiet_run([sys.executable, str(ROOT / step)], name, env, log)
            warnings += sum("warning" in line.lower() for line in (result.stdout or "").splitlines())
            if result.returncode:
                failed.append({"module": name, "return_code": result.returncode})
                _write_status("FAILED", completed, failed, warnings)
                print(f"FAILED MODULE: {name}")
                print(f"RETURN CODE: {result.returncode}")
                print("FINAL LOG LINES:")
                print("\n".join(_tail(result.stdout or "")))
                print(f"LOG PATH: {LOG_PATH}")
                return result.returncode
            completed.append(name)
            print(f"[{index}/{len(STEPS)}] {name}: OK")
    _write_status("SUCCESS", completed, failed, warnings)
    print("Research pipeline: SUCCESS")
    print(f"Modules: {len(completed)}/{len(STEPS)}")
    print(f"Warnings: {warnings}")
    print("Analyst packet:")
    print(PACKET_PATH)
    return 0


def run_verbose(env: dict[str, str]) -> int:
    print("===================================")
    print("Kraken AI Trading Research v2.0")
    print("===================================")
    update = subprocess.run(["bash", str(ROOT / "scripts/update_crypto_data.sh")], cwd=ROOT, env=env)
    if update.returncode:
        return update.returncode
    pipeline = subprocess.run([sys.executable, str(ROOT / "scripts/research_pipeline.py")], cwd=ROOT, env=env)
    return pipeline.returncode


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", choices=["full_crypto", "btc_only"], default="full_crypto")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--quiet", action="store_true", help="Capture module output and print compact progress (default).")
    mode.add_argument("--verbose", action="store_true", help="Stream existing detailed module output.")
    parser.add_argument("--print-packet", action="store_true", help="Print the latest packet after a successful run.")
    args = parser.parse_args()
    env = os.environ.copy(); env["KRAKEN_UNIVERSE"] = args.universe
    code = run_verbose(env) if args.verbose else run_quiet(env)
    if code == 0 and args.print_packet:
        if PACKET_PATH.exists():
            sys.stdout.write(PACKET_PATH.read_text())
        else:
            print(f"Packet unavailable: {PACKET_PATH}", file=sys.stderr)
            code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
