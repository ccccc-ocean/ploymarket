#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

run() {
  env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache \
    python3 -m ploymarket_sim.cli --config config/default.toml "$@"
}

run paper-run --market-type price_target
run paper-report
run btc-price
run alignment-report --market-type price_target
run edge-report --min-samples 30
run replay-backtest --market-type price_target
run data-quality
run daily-report
