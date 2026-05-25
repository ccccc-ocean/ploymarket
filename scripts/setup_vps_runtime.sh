#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p runtime/cache/http runtime/data logs
sed \
  -e '/^\[cache\]/,/^\[/{ s/^enabled = true$/enabled = false/; s/^ttl_seconds = 900$/ttl_seconds = 0/; s/^stale_if_error = true$/stale_if_error = false/; }' \
  -e '/^\[storage\]/,/^\[/{ s/^fresh_market_ttl_seconds = 900$/fresh_market_ttl_seconds = 0/; }' \
  -e 's#directory = ".cache/http"#directory = "runtime/cache/http"#' \
  -e 's#sqlite_path = "data/ploymarket.sqlite"#sqlite_path = "runtime/data/ploymarket.sqlite"#' \
  -e 's#output_dir = "data"#output_dir = "runtime/data"#' \
  config/default.toml > config/vps.local.toml

echo "vps_runtime | config=config/vps.local.toml | output=runtime/data | http_cache=disabled | live_market_fallback=disabled"
