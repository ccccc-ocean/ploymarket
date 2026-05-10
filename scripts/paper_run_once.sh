#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache \
  python3 -m ploymarket_sim.cli --config config/default.toml paper-run --market-type price_target
