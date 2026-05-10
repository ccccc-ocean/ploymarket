#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

LABEL="com.ploymarket.research-cycle"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
PROJECT_DIR="$(pwd)"
INTERVAL_SECONDS="${1:-1800}"

mkdir -p "$HOME/Library/LaunchAgents" "$PROJECT_DIR/logs"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PROJECT_DIR}/scripts/research_cycle.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${PROJECT_DIR}</string>
  <key>StartInterval</key>
  <integer>${INTERVAL_SECONDS}</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${PROJECT_DIR}/logs/research_cycle.out.log</string>
  <key>StandardErrorPath</key>
  <string>${PROJECT_DIR}/logs/research_cycle.err.log</string>
</dict>
</plist>
PLIST

launchctl unload "$PLIST" >/dev/null 2>&1 || true
launchctl load "$PLIST"

echo "installed ${LABEL}"
echo "plist=${PLIST}"
echo "interval_seconds=${INTERVAL_SECONDS}"
echo "logs=${PROJECT_DIR}/logs"
echo "check: launchctl list | grep ${LABEL}"
