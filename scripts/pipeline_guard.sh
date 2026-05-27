#!/usr/bin/env bash

# Shared health and locking helpers for unattended VPS cycles.

PIPELINE_HEALTH_DIR="${PLOYMARKET_HEALTH_DIR:-runtime/data/health}"
PIPELINE_NAME=""
PIPELINE_RUN_ID=""
PIPELINE_LOCK_DIR=""
PIPELINE_CURRENT_STEP="initializing"
PIPELINE_LOCK_ACQUIRED=0

pipeline_health() {
  env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache \
    python3 -m ploymarket_sim.pipeline_health --state-dir "$PIPELINE_HEALTH_DIR" "$@"
}

pipeline_guard_begin() {
  local pipeline="$1"
  local lock_dir="$2"
  local recovery_reason=""
  local now
  now="$(date +%s)"

  mkdir -p "$PIPELINE_HEALTH_DIR"
  if ! mkdir "$lock_dir" 2>/dev/null; then
    if [[ -f "$lock_dir/pid" ]] && kill -0 "$(cat "$lock_dir/pid")" 2>/dev/null; then
      echo "${pipeline} | another run is still active, skipping this tick"
      pipeline_health event --pipeline "$pipeline" --timestamp "$now" \
        --reason "active_lock" --action "skip_tick" --outcome "running"
      return 1
    fi
    rm -f "$lock_dir/pid" "$lock_dir/started_at"
    if ! rmdir "$lock_dir" 2>/dev/null || ! mkdir "$lock_dir" 2>/dev/null; then
      echo "${pipeline} | stale lock could not be recovered: $lock_dir" >&2
      pipeline_health event --pipeline "$pipeline" --timestamp "$now" \
        --reason "stale_lock" --action "remove_lock" --outcome "failed"
      return 2
    fi
    recovery_reason="stale_lock_removed"
    pipeline_health event --pipeline "$pipeline" --timestamp "$now" \
      --reason "stale_lock" --action "remove_lock" --outcome "success"
  fi

  PIPELINE_NAME="$pipeline"
  PIPELINE_RUN_ID="${now}-$$"
  PIPELINE_LOCK_DIR="$lock_dir"
  PIPELINE_LOCK_ACQUIRED=1
  printf '%s\n' "$$" > "$lock_dir/pid"
  printf '%s\n' "$now" > "$lock_dir/started_at"
  if ! pipeline_health start --pipeline "$pipeline" --run-id "$PIPELINE_RUN_ID" \
    --timestamp "$now" --recovery-reason "$recovery_reason"; then
    echo "${pipeline} | could not write pipeline health state" >&2
    rm -f "$lock_dir/pid" "$lock_dir/started_at"
    rmdir "$lock_dir" 2>/dev/null || true
    PIPELINE_LOCK_ACQUIRED=0
    return 2
  fi
  trap 'pipeline_guard_finish $?' EXIT
}

pipeline_guard_step() {
  PIPELINE_CURRENT_STEP="$1"
}

pipeline_guard_finish() {
  local exit_code="$1"
  local now
  trap - EXIT
  if [[ "$PIPELINE_LOCK_ACQUIRED" -eq 1 ]]; then
    now="$(date +%s)"
    pipeline_health finish --pipeline "$PIPELINE_NAME" --run-id "$PIPELINE_RUN_ID" \
      --timestamp "$now" --exit-code "$exit_code" --last-step "$PIPELINE_CURRENT_STEP" || true
    rm -f "$PIPELINE_LOCK_DIR/pid" "$PIPELINE_LOCK_DIR/started_at"
    rmdir "$PIPELINE_LOCK_DIR" 2>/dev/null || true
  fi
  exit "$exit_code"
}

pipeline_run_step() {
  local max_seconds="$1"
  shift
  local start_seconds=$SECONDS
  local step_name="$1"
  pipeline_guard_step "$step_name"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout --signal=TERM --kill-after=15s "${max_seconds}s" \
      env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache \
      python3 -m ploymarket_sim.cli "$@"
  else
    env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache \
      python3 -m ploymarket_sim.cli "$@"
  fi
  echo "${PIPELINE_TIMING_PREFIX:-${PIPELINE_NAME}}_timing | step=${step_name} | elapsed_seconds=$((SECONDS - start_seconds))"
}
