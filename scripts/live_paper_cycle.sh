#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CONFIG_PATH="${PLOYMARKET_CONFIG:-config/default.toml}"
LOCK_DIR="${TMPDIR:-/tmp}/ploymarket-live-paper-cycle.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "live_paper_cycle | another run is still active, skipping this tick"
  exit 0
fi
trap 'rmdir "$LOCK_DIR"' EXIT

run() {
  local start_seconds=$SECONDS
  local step_name="$1"
  env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache \
    python3 -m ploymarket_sim.cli --config "$CONFIG_PATH" "$@"
  echo "live_paper_timing | step=${step_name} | elapsed_seconds=$((SECONDS - start_seconds))"
}

run btc-price
run paper-run --market-type all
run paper-report
run spread-scan --market-type all
run flow-scan --market-type all --limit 250 --large-trade-usdc 500
