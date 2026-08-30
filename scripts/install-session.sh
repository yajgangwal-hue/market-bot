#!/bin/bash
# Install the two-month paper-trading experiment.
#
# Creates a launchd job that runs scripts/session-run.sh every 15 minutes
# while the US market is open, on weekdays only, and stops itself after the
# date written into data/run-until.txt.
#
# No API key is written into the plist. session-run.sh reads them from your
# shell profile when it runs, so the scheduler file contains no secrets.
#
# Usage:
#   bash scripts/install-session.sh            # dry run - decides but sends nothing
#   bash scripts/install-session.sh --live     # actually places paper orders
#   bash scripts/install-session.sh --months 2 --live
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.eventawaretrader.session"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
MONTHS=2
LIVE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --months) MONTHS="$2"; shift 2 ;;
    --live)   LIVE="--live"; shift ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ ! -x "$REPO/.venv/bin/event-aware-trader" ]]; then
  echo "error: .venv/bin/event-aware-trader not found." >&2
  echo "       Create the venv and run 'pip install -e .' first." >&2
  exit 1
fi

# The market runs 09:30-16:00 New York. Convert to this Mac's local clock so
# the schedule is right regardless of where you are.
read -r OPEN_H OPEN_M CLOSE_H CLOSE_M <<<"$(python3 - <<'PY'
from datetime import datetime
from zoneinfo import ZoneInfo
ny = ZoneInfo("America/New_York")
today = datetime.now(ny).date()
o = datetime(today.year, today.month, today.day, 9, 30, tzinfo=ny).astimezone()
c = datetime(today.year, today.month, today.day, 16, 0, tzinfo=ny).astimezone()
print(o.hour, o.minute, c.hour, c.minute)
PY
)"
echo "US session 09:30-16:00 New York = ${OPEN_H}:$(printf %02d "$OPEN_M")-${CLOSE_H}:$(printf %02d "$CLOSE_M") on this Mac"

mkdir -p "$HOME/Library/LaunchAgents" "$REPO/data" "$REPO/data/intraday"

# Stop date, read by session-run.sh on every cycle.
python3 - "$MONTHS" > "$REPO/data/run-until.txt" <<'PY'
import sys
from datetime import date, timedelta
print((date.today() + timedelta(days=31 * int(sys.argv[1]))).isoformat())
PY
echo "will stop on $(cat "$REPO/data/run-until.txt")"

{
  cat <<HEAD
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$REPO/scripts/session-run.sh</string>
HEAD
  [[ -n "$LIVE" ]] && echo "    <string>--live</string>"
  cat <<MID
  </array>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>StandardOutPath</key><string>$REPO/data/scheduler.log</string>
  <key>StandardErrorPath</key><string>$REPO/data/scheduler.err</string>
  <key>StartCalendarInterval</key><array>
MID
  python3 - "$OPEN_H" "$OPEN_M" "$CLOSE_H" "$CLOSE_M" <<'PY'
import sys
oh, om, ch, cm = (int(a) for a in sys.argv[1:5])
start, end = oh * 60 + om, ch * 60 + cm
for weekday in range(1, 6):                 # Monday..Friday
    for minute in range(start, end, 15):    # every 15 minutes while open
        print("    <dict><key>Weekday</key><integer>%d</integer>"
              "<key>Hour</key><integer>%d</integer>"
              "<key>Minute</key><integer>%d</integer></dict>"
              % (weekday, minute // 60, minute % 60))
PY
  echo "  </array></dict></plist>"
} > "$PLIST"

chmod +x "$REPO/scripts/session-run.sh"
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo
echo "installed: $LABEL"
echo "  mode        : ${LIVE:-DRY RUN (decides but sends nothing)}"
echo "  cadence     : every 15 min, weekdays, while the market is open"
echo "  stops on    : $(cat "$REPO/data/run-until.txt")"
echo "  activity log: $REPO/data/session.log"
echo "  weekly report: $REPO/data/WEEKLY-RECORD.json"
echo "  final report : $REPO/data/FINAL-RECORD.json"
echo
echo "stop early with:  launchctl unload $PLIST"
