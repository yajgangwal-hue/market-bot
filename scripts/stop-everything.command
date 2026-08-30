#!/bin/bash
# Double-click to stop the bot. Open positions are NOT closed - do that in
# TradingView or the Alpaca dashboard if you want to be flat.
set -euo pipefail
PLIST="$HOME/Library/LaunchAgents/com.eventawaretrader.session.plist"
launchctl unload "$PLIST" 2>/dev/null && echo "Stopped." || echo "It was not running."
echo
echo "Any open positions are still open. Close them in TradingView if you want."
echo "Press Return to close."
read -r _
