#!/bin/bash
# Double-click to start the PRACTICE run.
#
# The bot thinks through real decisions every 15 minutes while the US market
# is open, but places no orders at all. Use this for a day or two before
# letting it trade, so you can see what it would have done.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$REPO"

echo
echo "Starting PRACTICE mode - decisions only, no orders."
echo
bash scripts/install-session.sh --months 2
echo
echo "Running. Check on it any time by double-clicking scripts/check-results.command"
echo "You can close this window."
