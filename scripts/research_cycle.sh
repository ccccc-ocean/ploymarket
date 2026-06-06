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
run reversal-backtest --market-type above_below_expiry
run alignment-report --market-type all --max-points-per-market "${PLOYMARKET_ALIGNMENT_MAX_POINTS_PER_MARKET:-600}"
run edge-report --min-samples 30
run strategy-sweep --market-type all --limit 10 --candidate-limit "${PLOYMARKET_STRATEGY_SWEEP_CANDIDATE_LIMIT:-2}" --max-points-per-market "${PLOYMARKET_STRATEGY_SWEEP_MAX_POINTS_PER_MARKET:-600}"
run market-type-report
run observation-report --recent-runs "${PLOYMARKET_OBSERVATION_RECENT_RUNS:-288}"
run paper-sample-report --recent-runs "${PLOYMARKET_STRATEGY_REVIEW_RECENT_RUNS:-72}"
run strategy-review --recent-runs "${PLOYMARKET_STRATEGY_REVIEW_RECENT_RUNS:-72}"
run filter-reason-report --recent-runs "${PLOYMARKET_STRATEGY_REVIEW_RECENT_RUNS:-72}"
run blocked-edge-report --recent-runs "${PLOYMARKET_STRATEGY_REVIEW_RECENT_RUNS:-72}"
run touch-below-path-report --recent-runs "${PLOYMARKET_STRATEGY_REVIEW_RECENT_RUNS:-72}"
run live-universe-report --recent-runs "${PLOYMARKET_STRATEGY_REVIEW_RECENT_RUNS:-72}"
run probe-performance-report
run strategy-autotune-report --recent-runs "${PLOYMARKET_STRATEGY_REVIEW_RECENT_RUNS:-72}"
run open-position-report
run side-diagnostics
run strike-report
run data-quality
run daily-report
