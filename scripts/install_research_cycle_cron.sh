#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PROJECT_DIR="$(pwd)"
SCHEDULE="${1:-*/10 * * * *}"
CONFIG_PATH="${2:-config/vps.local.toml}"
BEGIN_MARKER="# BEGIN ploymarket-research-cycle"
END_MARKER="# END ploymarket-research-cycle"

mkdir -p logs
CURRENT="$(crontab -l 2>/dev/null || true)"
FILTERED="$(
  printf '%s\n' "$CURRENT" | awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
    $0 == begin { managed = 1; next }
    $0 == end { managed = 0; next }
    !managed { print }
  '
)"

{
  printf '%s\n' "$FILTERED"
  printf '%s\n' "$BEGIN_MARKER"
  printf '%s cd %s && PLOYMARKET_CONFIG=%s %s/scripts/research_cycle.sh >> %s/logs/research_cycle.out.log 2>> %s/logs/research_cycle.err.log\n' \
    "$SCHEDULE" "$PROJECT_DIR" "$CONFIG_PATH" "$PROJECT_DIR" "$PROJECT_DIR" "$PROJECT_DIR"
  printf '%s\n' "$END_MARKER"
} | crontab -

echo "research_cycle_cron | schedule=$SCHEDULE | config=$CONFIG_PATH | logs=$PROJECT_DIR/logs"
