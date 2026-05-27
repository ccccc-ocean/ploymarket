#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CONFIG_PATH="${PLOYMARKET_CONFIG:-config/default.toml}"
source scripts/pipeline_guard.sh

recover_pipeline() {
  local pipeline="$1"
  local max_success_age="$2"
  local max_running_age="$3"
  local command="$4"
  local check_output=""
  local reason=""
  local now=""

  if check_output="$(pipeline_health check --pipeline "$pipeline" \
    --max-success-age-seconds "$max_success_age" \
    --max-running-age-seconds "$max_running_age")"; then
    echo "watchdog | $check_output | action=none"
    return 0
  fi

  echo "watchdog | $check_output | action=retry"
  reason="$(printf '%s\n' "$check_output" | sed -n 's/.*reason=\([^ |]*\).*/\1/p')"
  now="$(date +%s)"
  pipeline_health event --pipeline "$pipeline" --timestamp "$now" \
    --reason "${reason:-unhealthy}" --action "retry" --outcome "started"
  if PLOYMARKET_CONFIG="$CONFIG_PATH" "$command"; then
    pipeline_health event --pipeline "$pipeline" --timestamp "$(date +%s)" \
      --reason "${reason:-unhealthy}" --action "retry" --outcome "success"
    return 0
  fi
  pipeline_health event --pipeline "$pipeline" --timestamp "$(date +%s)" \
    --reason "${reason:-unhealthy}" --action "retry" --outcome "failed"
  return 1
}

mkdir -p "${PLOYMARKET_HEALTH_DIR:-runtime/data/health}" logs
status=0
recover_pipeline "live_paper_cycle" "${PLOYMARKET_LIVE_MAX_SUCCESS_AGE_SECONDS:-600}" \
  "${PLOYMARKET_LIVE_MAX_RUNNING_AGE_SECONDS:-240}" "${PLOYMARKET_LIVE_COMMAND:-scripts/live_paper_cycle.sh}" || status=1
recover_pipeline "research_cycle" "${PLOYMARKET_RESEARCH_MAX_SUCCESS_AGE_SECONDS:-7200}" \
  "${PLOYMARKET_RESEARCH_MAX_RUNNING_AGE_SECONDS:-3600}" "${PLOYMARKET_RESEARCH_COMMAND:-scripts/research_cycle.sh}" || status=1
exit "$status"
