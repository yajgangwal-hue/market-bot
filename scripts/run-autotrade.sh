#!/bin/bash
# Wrapper for one scheduled autotrade cycle.
#
# Credentials are read from the environment at RUN time, never written into a
# plist or a crontab. Put the two exports in ~/.zprofile so both your shell and
# a scheduled job pick them up:
#
#     export APCA_API_KEY_ID=...
#     export APCA_API_SECRET_KEY=...
#
# Usage:  scripts/run-autotrade.sh [--interval 1d] [--live]
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$REPO/.venv/bin/event-aware-trader"

# A scheduled job starts with a minimal environment, so pull in the profile
# that holds the keys before checking for them.
set +u                                   # a profile may reference unset vars
# shellcheck disable=SC1091
[[ -f "$HOME/.zprofile" ]] && source "$HOME/.zprofile" 2>/dev/null || true
set -u
# .zshrc is deliberately NOT sourced: it is zsh syntax and this runs under
# bash 3.2, and the API keys are written to .zprofile.

INTERVAL="1d"
PERIOD="2y"
EXTRA=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --interval) INTERVAL="$2"; shift 2 ;;
    --live)     EXTRA+=("--live"); shift ;;
    *)          EXTRA+=("$1"); shift ;;
  esac
done

case "$INTERVAL" in
  1d)  PERIOD="2y"  ;;
  1h)  PERIOD="3mo" ;;
  15m|30m|5m) PERIOD="1mo" ;;
esac

if [[ ! -x "$CLI" ]]; then
  echo "error: $CLI not found. Create the venv and run 'pip install -e .' first." >&2
  exit 1
fi

if [[ -z "${APCA_API_KEY_ID:-}" || -z "${APCA_API_SECRET_KEY:-}" ]]; then
  echo "error: APCA_API_KEY_ID / APCA_API_SECRET_KEY are not set." >&2
  echo "       Add them to ~/.zprofile so scheduled runs inherit them." >&2
  exit 1
fi

mkdir -p "$REPO/data"
cd "$REPO"

# Append rather than overwrite: the run history is the point.
"$CLI" autotrade --interval "$INTERVAL" --period "$PERIOD" ${EXTRA[@]+"${EXTRA[@]}"} \
  >> "$REPO/data/autotrade.log" 2>> "$REPO/data/autotrade.err"
