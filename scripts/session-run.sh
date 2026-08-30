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

# ---- 1. stop when the experiment is over -----------------------------------
if [[ -f data/run-until.txt ]]; then
  UNTIL="$(tr -d '[:space:]' < data/run-until.txt)"
  TODAY="$(date +%Y-%m-%d)"
  if [[ "$TODAY" > "$UNTIL" ]]; then
    echo "[$(stamp)] run-until $UNTIL has passed; unloading the scheduler" >> "$LOG"
    launchctl unload "$HOME/Library/LaunchAgents/com.eventawaretrader.session.plist" 2>/dev/null || true
    "$CLI" record --audit-log data/autotrade-audit.jsonl > "data/FINAL-RECORD.json" 2>&1 || true
    echo "[$(stamp)] final record written to data/FINAL-RECORD.json" >> "$LOG"
    exit 0
  fi
fi

# ---- 2. refuse to start if it is not safe ----------------------------------
if ! "$CLI" preflight --interval "$INTERVAL" --max-age-days 3 > data/last-preflight.json 2>&1; then
  echo "[$(stamp)] PREFLIGHT FAILED - no trading this cycle. See data/last-preflight.json" >> "$LOG"
  exit 0
fi

# ---- 3. refresh data, then trade -------------------------------------------
for s in SPY QQQ XLK XLE XLF TLT GLD DIA IWM XLV XLP XLU XLI XLB XLY VNQ EFA EEM SLV USO; do
  "$CLI" fetch --symbol "$s" --period "$PERIOD" --interval "$INTERVAL" \
    --out "data/intraday/${s}_${INTERVAL}.csv" >/dev/null 2>&1 || true
done

"$CLI" autotrade --interval "$INTERVAL" --period "$PERIOD" ${EXTRA[@]+"${EXTRA[@]}"} >> "$LOG" 2>&1 || \
  echo "[$(stamp)] autotrade returned non-zero" >> "$LOG"

# ---- 4. weekly: retrain, and write down what the record proves -------------
# Friday, in the last hour of the session.
if [[ "$(date +%u)" == "5" && "$(date +%H)" == "12" ]]; then
  if [[ ! -f data/.last-train || "$(date +%Y-%V)" != "$(cat data/.last-train 2>/dev/null)" ]]; then
    echo "[$(stamp)] weekly retrain" >> "$LOG"
    "$CLI" learn --data-dir data --pine tradingview/learned_filter.pine >> "$LOG" 2>&1 || true
    "$CLI" record --audit-log data/autotrade-audit.jsonl > "data/WEEKLY-RECORD.json" 2>&1 || true
    date +%Y-%V > data/.last-train
    echo "[$(stamp)] weekly record written to data/WEEKLY-RECORD.json" >> "$LOG"
  fi
fi
