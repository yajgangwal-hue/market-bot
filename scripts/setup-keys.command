#!/bin/bash
# Double-click this file to save your Alpaca paper keys.
#
# It asks for the two codes and writes them into ~/.zprofile, which is the
# file your Mac reads when a Terminal starts. The secret is typed blind - you
# will not see characters as you type it, which is normal.
#
# The keys never leave this computer. Nothing is uploaded, and nothing is
# written into the project folder, which is why they cannot end up on GitHub.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
PROFILE="$HOME/.zprofile"

echo
echo "==============================================="
echo " Alpaca paper-trading key setup"
echo "==============================================="
echo
echo "Get these from alpaca.markets -> Paper Trading -> API Keys."
echo "If you have ever pasted them into a chat or a message,"
echo "click Regenerate there first and use the new ones."
echo

read -r -p "Paste your API Key ID, then press Return: " KEY_ID
KEY_ID="$(echo -n "$KEY_ID" | tr -d '[:space:]')"
echo "   got ${#KEY_ID} characters, starting ${KEY_ID:0:4}"
echo

# The secret is hidden while typing. That silence made an earlier version of
# this script fail badly: with no feedback, it is natural to assume the paste
# did not register and paste again, producing a secret several times too long
# and a 401 that looks like a wrong key. So the length is echoed back, and an
# implausible length is rejected here rather than by Alpaca.
echo "Now paste your Secret Key and press Return."
echo "IMPORTANT: nothing will appear on screen. Paste ONCE, then press Return."
read -r -s SECRET
SECRET="$(echo -n "$SECRET" | tr -d '[:space:]')"
echo "   got ${#SECRET} characters, starting ${SECRET:0:2}"
echo

if [[ -z "$KEY_ID" || -z "$SECRET" ]]; then
  echo "One of them was empty. Nothing was saved. Run this again."
  exit 1
fi

if [[ ${#KEY_ID} -lt 15 || ${#KEY_ID} -gt 30 ]]; then
  echo "That Key ID is ${#KEY_ID} characters; Alpaca's are around 20."
  echo "Nothing was saved. Run this again and paste just the Key ID."
  exit 1
fi

if [[ ${#SECRET} -lt 30 || ${#SECRET} -gt 60 ]]; then
  echo "That Secret is ${#SECRET} characters; Alpaca's are around 40."
  if [[ ${#SECRET} -gt 60 ]]; then
    echo "It looks like it was pasted more than once - easy to do when the"
    echo "screen shows nothing back."
  fi
  echo "Nothing was saved. Run this again and paste the Secret ONCE."
  exit 1
fi

if [[ "${KEY_ID:0:2}" == "AK" ]]; then
  echo "That is a LIVE key (starts with AK). This project is paper-only."
  echo "Use the keys from the Paper Trading section instead. Nothing was saved."
  exit 1
fi

# Drop any previous copy so the file does not collect stale keys.
if [[ -f "$PROFILE" ]]; then
  cp "$PROFILE" "$PROFILE.backup-$(date +%Y%m%d%H%M%S)"
  grep -v 'APCA_API_KEY_ID\|APCA_API_SECRET_KEY' "$PROFILE" > "$PROFILE.tmp" || true
  mv "$PROFILE.tmp" "$PROFILE"
fi

{
  echo ""
  echo "# Alpaca paper trading keys"
  echo "export APCA_API_KEY_ID=$KEY_ID"
  echo "export APCA_API_SECRET_KEY=$SECRET"
} >> "$PROFILE"

chmod 600 "$PROFILE"

export APCA_API_KEY_ID="$KEY_ID"
export APCA_API_SECRET_KEY="$SECRET"

echo "Saved to $PROFILE (readable only by you)."
echo
echo "Checking the connection..."
echo

if "$REPO/.venv/bin/event-aware-trader" account; then
  echo
  echo "==============================================="
  echo " Connected. You can close this window."
  echo " Next: double-click scripts/start-practice.command"
  echo "==============================================="
else
  echo
  echo "==============================================="
  echo " That did not connect."
  echo " Most likely the codes were swapped, or they are"
  echo " LIVE keys instead of PAPER keys. Check on"
  echo " alpaca.markets and run this again."
  echo "==============================================="
  exit 1
fi
