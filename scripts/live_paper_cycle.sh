#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CONFIG_PATH="${PLOYMARKET_CONFIG:-config/default.toml}"
LOCK_DIR="${TMPDIR:-/tmp}/ploymarket-live-paper-cycle.lock"
source scripts/pipeline_guard.sh
PIPELINE_TIMING_PREFIX="live_paper"
set +e
pipeline_guard_begin "live_paper_cycle" "$LOCK_DIR"
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
  pipeline_run_step "${PLOYMARKET_LIVE_STEP_TIMEOUT_SECONDS:-90}" "$step_name" --config "$CONFIG_PATH" "$@"
}

run btc-price
run paper-run --market-type all
run paper-report
run strategy-review --recent-runs "${PLOYMARKET_LIVE_STRATEGY_REVIEW_RECENT_RUNS:-72}"
run filter-reason-report --recent-runs "${PLOYMARKET_LIVE_STRATEGY_REVIEW_RECENT_RUNS:-72}"
run blocked-edge-report --recent-runs "${PLOYMARKET_LIVE_STRATEGY_REVIEW_RECENT_RUNS:-72}"
run touch-below-path-report --recent-runs "${PLOYMARKET_LIVE_STRATEGY_REVIEW_RECENT_RUNS:-72}"
run live-universe-report --recent-runs "${PLOYMARKET_LIVE_STRATEGY_REVIEW_RECENT_RUNS:-72}"
run probe-performance-report
run strategy-autotune-report --recent-runs "${PLOYMARKET_LIVE_STRATEGY_REVIEW_RECENT_RUNS:-72}"
run open-position-report --live-quotes
run spread-scan --market-type all
run flow-scan --market-type all --limit 250 --large-trade-usdc 500
