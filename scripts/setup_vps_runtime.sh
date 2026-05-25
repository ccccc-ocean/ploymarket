#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p runtime/cache/http runtime/data logs
sed \
  -e 's#directory = ".cache/http"#directory = "runtime/cache/http"#' \
  -e 's#sqlite_path = "data/ploymarket.sqlite"#sqlite_path = "runtime/data/ploymarket.sqlite"#' \
  -e 's#output_dir = "data"#output_dir = "runtime/data"#' \
  config/default.toml > config/vps.local.toml

echo "vps_runtime | config=config/vps.local.toml | output=runtime/data | cache=runtime/cache/http"
