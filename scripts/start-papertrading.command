#!/bin/bash
# Double-click to start REAL paper trading (fake money, real orders).
#
# Runs every 15 minutes while the US market is open, weekdays, and stops on
# its own after two months. Every trade appears in TradingView because both
# are looking at the same Alpaca account.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

echo
echo "This will place orders in your Alpaca PAPER account."
echo "Fake money. No real money can be reached - the live endpoint is refused."
echo
read -r -p "Type yes to start: " ANSWER
if [[ "$ANSWER" != "yes" ]]; then
  echo "Not started."
  exit 0
fi

bash scripts/install-session.sh --months 2 --live
echo
echo "Running. It stops by itself on $(cat data/run-until.txt 2>/dev/null || echo 'the set date')."
echo "You can close this window."
