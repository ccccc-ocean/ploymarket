#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CONFIG_PATH="${PLOYMARKET_CONFIG:-config/default.toml}"
LOCK_DIR="${TMPDIR:-/tmp}/ploymarket-research-cycle.lock"
source scripts/pipeline_guard.sh
PIPELINE_TIMING_PREFIX="research_cycle"
set +e
pipeline_guard_begin "research_cycle" "$LOCK_DIR"
GUARD_STATUS="$?"
set -e
if [[ "$GUARD_STATUS" -eq 1 ]]; then
  exit 0
fi
if [[ "$GUARD_STATUS" -ne 0 ]]; then
  exit "$GUARD_STATUS"
fi

run() {
  local step_name="$1"
  pipeline_run_step "${PLOYMARKET_RESEARCH_STEP_TIMEOUT_SECONDS:-900}" "$step_name" --config "$CONFIG_PATH" "$@"
}

run backtest --market-type all
run reversal-backtest --market-type price_range_daily
run alignment-report --market-type all
run edge-report --min-samples 30
run strategy-sweep --market-type all --limit 10
run market-type-report
run strike-report
run data-quality
run daily-report
