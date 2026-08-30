#!/bin/bash
# One scheduled cycle during the US session.
#
# Called by launchd every 15 minutes while the market is open. Handles four
# things the plist cannot:
#
#   1. Credentials are read from your shell profile at RUN time, so no API key
#      is ever written into a plist, a crontab, or this repo.
#   2. Self-expiry. The run stops on its own at the date in data/run-until.txt,
#      so a two-month experiment does not quietly become permanent.
#   3. Retraining, once per week, so the model learns from accumulated trades.
#   4. A weekly written assessment of whether the record proves anything.
#
# Usage:  scripts/session-run.sh [--live]
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$REPO/.venv/bin/event-aware-trader"
INTERVAL="15m"
PERIOD="1mo"
EXTRA=()

# launchd starts with a minimal environment; pull in the profile that has the keys.
set +u                                   # a profile may reference unset vars
# shellcheck disable=SC1091
[[ -f "$HOME/.zprofile" ]] && source "$HOME/.zprofile" 2>/dev/null || true
set -u
# .zshrc is deliberately NOT sourced: it is zsh syntax and this runs under
# bash 3.2, and the API keys are written to .zprofile.

while [[ $# -gt 0 ]]; do
  case "$1" in
    --live) EXTRA+=("--live"); shift ;;
    *)      EXTRA+=("$1"); shift ;;
  esac
done

cd "$REPO"
mkdir -p data
LOG="$REPO/data/session.log"
stamp() { date "+%Y-%m-%d %H:%M:%S"; }

# ~1,100 runs over two months, each appending a full JSON result, with the
# audit file read whole into memory on every weekly report. Rotate at 5MB and
# keep one generation.
for f in "$LOG" "$REPO/data/autotrade-audit.jsonl" "$REPO/data/scheduler.log" "$REPO/data/scheduler.err"; do
  if [[ -f "$f" ]] && [[ "$(wc -c < "$f" | tr -d ' ')" -gt 5242880 ]]; then
    mv "$f" "$f.1"
    echo "[$(stamp)] rotated $(basename "$f") at 5MB" >> "$LOG"
  fi
done

# ---- 1. stop when the experiment is over -----------------------------------
if [[ -f data/run-until.txt ]]; then
  UNTIL="$(tr -d '[:space:]' < data/run-until.txt)"
  TODAY="$(date +%Y-%m-%d)"
  # `[[ > ]]` is a lexical compare with no format check. An empty file made
  # every date "greater" and ended the experiment on cycle one; a hand-edited
  # 2026-9-30 compares wrong at the month digit and would never end it at all.
  if [[ ! "$UNTIL" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "[$(stamp)] run-until.txt is not YYYY-MM-DD ('$UNTIL'); ignoring it" >> "$LOG"
  elif [[ "$TODAY" > "$UNTIL" ]]; then
    echo "[$(stamp)] run-until $UNTIL has passed; winding down" >> "$LOG"
    # Write the report BEFORE unloading: `launchctl unload` terminates this
    # very job, so anything after it may never run.
    "$CLI" record --audit-log data/autotrade-audit.jsonl > "data/FINAL-RECORD.json" 2>&1 || true
    echo "[$(stamp)] final record written to data/FINAL-RECORD.json" >> "$LOG"
    # Positions are bracketed at the broker, so their stops survive the
    # scheduler stopping. Say so rather than leaving it to be discovered.
    echo "[$(stamp)] NOTE: any open position stays open at Alpaca with its" >> "$LOG"
    echo "[$(stamp)]       resting stop. Close it in TradingView if you want flat." >> "$LOG"
    launchctl unload "$HOME/Library/LaunchAgents/com.eventawaretrader.session.plist" 2>/dev/null || true
    exit 0
  fi
fi

# ---- 2. refuse to start if it is not safe ----------------------------------
# autotrade fetches its own bars live, so the daily CSVs preflight reads are
# not the data being traded. Refresh them first so the freshness check is
# actually about something current.
for s in SPY QQQ XLK XLE XLF TLT GLD DIA IWM XLV XLP XLU XLI XLB XLY VNQ EFA EEM SLV USO; do
  "$CLI" fetch --symbol "$s" --period 2y --interval 1d --out "data/${s}.csv" >/dev/null 2>&1 || true
done

if ! "$CLI" preflight --interval "$INTERVAL" --max-age-days 4 > data/last-preflight.json 2>&1; then
  echo "[$(stamp)] PREFLIGHT FAILED - no trading this cycle. See data/last-preflight.json" >> "$LOG"
  exit 0
fi

# ---- 3. trade ---------------------------------------------------------------
# No intraday fetch loop here: autotrade calls fetch_yahoo_bars itself, and
# nothing reads data/intraday/. Those 20 requests per cycle - 520 a day on top
# of autotrade's own - were pure waste.

"$CLI" autotrade --interval "$INTERVAL" --period "$PERIOD" ${EXTRA[@]+"${EXTRA[@]}"} >> "$LOG" 2>&1 || \
  echo "[$(stamp)] autotrade returned non-zero" >> "$LOG"

# ---- 4. at the close: report the day, then learn from it -------------------
# The last scheduled cycle of the session is the close. Alpaca's clock is
# authoritative about which one that is, so ask rather than assume.
IS_LAST="$("$CLI" account >/dev/null 2>&1 && python3 - <<'PYEOF' 2>/dev/null || echo no
import json, subprocess, sys
from datetime import datetime, timezone
try:
    from event_aware_trader.broker import AlpacaPaperBroker, BrokerConfig
    c = AlpacaPaperBroker(BrokerConfig.from_environment()).clock()
    nc = datetime.fromisoformat(str(c["next_close"]).replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    print("yes" if (nc - now).total_seconds() <= 960 else "no")
except Exception:
    print("no")
PYEOF
)"

if [[ "$IS_LAST" == "yes" ]]; then
  echo "[$(stamp)] session closing - writing the daily report" >> "$LOG"
  "$CLI" daily-report --out "data/DAILY-REPORT.json" >> "$LOG" 2>&1 || true
  cp "data/DAILY-REPORT.json" "data/reports/$(date +%Y-%m-%d).json" 2>/dev/null || {
    mkdir -p data/reports && cp "data/DAILY-REPORT.json" "data/reports/$(date +%Y-%m-%d).json" 2>/dev/null || true; }
  # Learn from every trade closed today before tomorrow's first decision.
  echo "[$(stamp)] retraining on the record so far" >> "$LOG"
  "$CLI" retrain >> "$LOG" 2>&1 || true
fi

# ---- 5. weekly: the statistical verdict ------------------------------------
# Friday, in the last hour of the session.
# Gating on a specific local hour meant that in any timezone where that hour
# falls outside the converted session window, the retrain never ran at all.
# Gating on the ISO week alone makes it fire on the first Friday cycle,
# whenever that happens to be locally.
if [[ "$(date +%u)" == "5" ]]; then
  if [[ ! -f data/.last-train || "$(date +%Y-%V)" != "$(cat data/.last-train 2>/dev/null)" ]]; then
    echo "[$(stamp)] weekly retrain" >> "$LOG"
    "$CLI" learn --data-dir data --pine tradingview/learned_filter.pine >> "$LOG" 2>&1 || true
    "$CLI" record --audit-log data/autotrade-audit.jsonl > "data/WEEKLY-RECORD.json" 2>&1 || true
    date +%Y-%V > data/.last-train
    echo "[$(stamp)] weekly record written to data/WEEKLY-RECORD.json" >> "$LOG"
  fi
fi
