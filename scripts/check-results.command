#!/bin/bash
# Double-click to see how it is doing.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
[[ -f "$HOME/.zprofile" ]] && source "$HOME/.zprofile" || true

echo
echo "=============== ACCOUNT ==============="
./.venv/bin/event-aware-trader account --positions 2>&1 | head -25
echo
echo "=============== THE RECORD ==============="
./.venv/bin/event-aware-trader record 2>&1 | head -40
echo
echo "=============== RECENT ACTIVITY ==============="
tail -15 data/session.log 2>/dev/null || echo "(nothing logged yet)"
echo
echo "Press Return to close."
read -r _
