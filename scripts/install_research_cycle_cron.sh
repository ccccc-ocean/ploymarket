#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PROJECT_DIR="$(pwd)"
LIVE_SCHEDULE="${1:-*/5 * * * *}"
RESEARCH_SCHEDULE="${2:-17 * * * *}"
CONFIG_PATH="${3:-config/vps.local.toml}"
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
  printf '%s cd %s && PLOYMARKET_CONFIG=%s %s/scripts/live_paper_cycle.sh >> %s/logs/live_paper_cycle.out.log 2>> %s/logs/live_paper_cycle.err.log\n' \
    "$LIVE_SCHEDULE" "$PROJECT_DIR" "$CONFIG_PATH" "$PROJECT_DIR" "$PROJECT_DIR" "$PROJECT_DIR"
  printf '%s cd %s && PLOYMARKET_CONFIG=%s %s/scripts/research_cycle.sh >> %s/logs/research_cycle.out.log 2>> %s/logs/research_cycle.err.log\n' \
    "$RESEARCH_SCHEDULE" "$PROJECT_DIR" "$CONFIG_PATH" "$PROJECT_DIR" "$PROJECT_DIR" "$PROJECT_DIR"
  printf '%s cd %s && PLOYMARKET_CONFIG=%s %s/scripts/watchdog_cycle.sh >> %s/logs/watchdog_cycle.out.log 2>> %s/logs/watchdog_cycle.err.log\n' \
    '2-57/5 * * * *' "$PROJECT_DIR" "$CONFIG_PATH" "$PROJECT_DIR" "$PROJECT_DIR" "$PROJECT_DIR"
  printf '%s\n' "$END_MARKER"
} | crontab -

echo "research_cycle_cron | live_schedule=$LIVE_SCHEDULE | research_schedule=$RESEARCH_SCHEDULE | watchdog_schedule=2-57/5 * * * * | config=$CONFIG_PATH | logs=$PROJECT_DIR/logs"
