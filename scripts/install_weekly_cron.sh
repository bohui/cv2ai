#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHEDULE="${1:-0 9 * * 1}"
LOG_DIR="${CV2AI_REPORT_DIR:-$HOME/.cv2ai-reports}"
LOG_FILE="$LOG_DIR/cv2ai-weekly.log"
COMMAND="$SCRIPT_DIR/cv2ai_weekly.sh >> \"$LOG_FILE\" 2>&1"
ENTRY="$SCHEDULE $COMMAND"

mkdir -p "$LOG_DIR"

current_cron="$(mktemp)"
new_cron="$(mktemp)"
trap 'rm -f "$current_cron" "$new_cron"' EXIT

crontab -l > "$current_cron" 2>/dev/null || true

if grep -F "$SCRIPT_DIR/cv2ai_weekly.sh" "$current_cron" >/dev/null; then
  echo "CV2AI weekly cron entry already exists:"
  grep -F "$SCRIPT_DIR/cv2ai_weekly.sh" "$current_cron"
  exit 0
fi

{
  cat "$current_cron"
  printf '%s\n' "$ENTRY"
} > "$new_cron"

crontab "$new_cron"
echo "Installed CV2AI weekly cron entry:"
echo "$ENTRY"
