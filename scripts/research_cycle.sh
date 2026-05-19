#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

LOCK_DIR="${TMPDIR:-/tmp}/ploymarket-research-cycle.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "research_cycle | another run is still active, skipping this tick"
  exit 0
fi
trap 'rmdir "$LOCK_DIR"' EXIT

run() {
  env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache \
    python3 -m ploymarket_sim.cli --config config/default.toml "$@"
}

run btc-price
run backtest --market-type price_target
run paper-run --market-type price_target
run paper-report
run alignment-report --market-type price_target
run edge-report --min-samples 30
run strategy-sweep --market-type price_target --limit 10
run data-quality
run daily-report
