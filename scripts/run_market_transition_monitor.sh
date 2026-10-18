#!/bin/bash
set -u

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)" || exit 1
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd -P)" || exit 1
LOG_DIR="$REPO_ROOT/LOGS"
LOG_FILE="$LOG_DIR/market_transition_monitor.log"
RUNTIME_DIR="$REPO_ROOT/RESEARCH_MEMORY/market_transition"
LOCK_DIR="$RUNTIME_DIR/run.lock"
STATUS_FILE="$RUNTIME_DIR/automation_last_run.json"
mkdir -p "$LOG_DIR" "$RUNTIME_DIR" || exit 1

now_iso() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }
START_TIME="$(now_iso)"
RUN_ID="$(date -u '+%Y%m%dT%H%M%SZ')_$$"
RESULT_FILE="$RUNTIME_DIR/monitor_result_$RUN_ID.json"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  LOCK_PID="$(sed -n '1p' "$LOCK_DIR/pid" 2>/dev/null || true)"
  if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
    printf '%s status=SKIPPED_OVERLAP pid=%s\n' "$START_TIME" "$LOCK_PID" >> "$LOG_FILE"
    exit 75
  fi
  rm -f "$LOCK_DIR/pid"
  rmdir "$LOCK_DIR" 2>/dev/null || {
    printf '%s status=LOCK_UNAVAILABLE\n' "$START_TIME" >> "$LOG_FILE"
    exit 75
  }
  mkdir "$LOCK_DIR" 2>/dev/null || exit 75
fi
printf '%s\n' "$$" > "$LOCK_DIR/pid"
cleanup() { rm -f "$LOCK_DIR/pid"; rmdir "$LOCK_DIR" 2>/dev/null || true; }
trap cleanup EXIT INT TERM HUP

VENV=""
for candidate in "$REPO_ROOT/.venv-research" "$REPO_ROOT/.venv" "$REPO_ROOT/venv" "$REPO_ROOT/crypto_quant_research_gateway/.venv"; do
  if [ -x "$candidate/bin/python3" ]; then VENV="$candidate"; break; fi
done

printf '%s status=STARTED market_only=YES\n' "$START_TIME" >> "$LOG_FILE"
if [ -z "$VENV" ]; then
  EXIT_STATUS=78
  FINAL_STATUS=MONITOR_FAILED
  printf '%s error=PYTHON_VIRTUAL_ENVIRONMENT_NOT_FOUND\n' "$(now_iso)" >> "$LOG_FILE"
else
  # shellcheck disable=SC1090
  . "$VENV/bin/activate"
  cd "$REPO_ROOT" || exit 1
  TRIGGER="${MARKET_TRANSITION_TRIGGER:-launchd}"
  python3 scripts/market_transition_run_accounting.py start "$RUN_ID" --at "$START_TIME" --trigger "$TRIGGER" >> "$LOG_FILE" 2>&1
  python3 scripts/refresh_market_transition_data.py >> "$LOG_FILE" 2>&1
  REFRESH_STATUS=$?
  if [ "$REFRESH_STATUS" -ne 0 ]; then
    EXIT_STATUS="$REFRESH_STATUS"
    FINAL_STATUS=MARKET_DATA_REFRESH_FAILED
    printf '%s status=MARKET_DATA_REFRESH_FAILED exit_status=%s\n' "$(now_iso)" "$REFRESH_STATUS" >> "$LOG_FILE"
  else
    python3 scripts/market_transition_monitor.py --result-file "$RESULT_FILE" >> "$LOG_FILE" 2>&1
    EXIT_STATUS=$?
    if [ "$EXIT_STATUS" -ne 0 ]; then
      FINAL_STATUS=MONITOR_FAILED
    else
      FINAL_STATUS="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$RESULT_FILE" 2>/dev/null || printf 'MONITOR_FAILED')"
    fi
  fi
fi
FINISH_TIME="$(now_iso)"
printf '%s status=FINISHED exit_status=%s\n' "$FINISH_TIME" "$EXIT_STATUS" >> "$LOG_FILE"
if [ -n "$VENV" ]; then
  python3 scripts/market_transition_run_accounting.py finish "$RUN_ID" --at "$FINISH_TIME" --status "$FINAL_STATUS" --exit-status "$EXIT_STATUS" --result-file "$RESULT_FILE" >> "$LOG_FILE" 2>&1 || true
fi
rm -f "$RESULT_FILE"
exit "$EXIT_STATUS"
