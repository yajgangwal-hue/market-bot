# Save your Alpaca paper keys into your Windows user environment.
#
# The keys never leave this computer. Nothing is uploaded, and nothing is
# written into the project folder, which is why they cannot end up on GitHub.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File setup-keys.ps1
#   powershell -ExecutionPolicy Bypass -File setup-keys.ps1 -KeyId PK... -Secret abc...

param(
    [string]$KeyId,
    [string]$Secret
)

# NOT 'Stop'. Native programs write ordinary progress to stderr - git clone,
# pip, winget all do - and under 'Stop' PowerShell turns that into a
# terminating NativeCommandError. A Microsoft Store python stub killed this
# script on line one that way. Failure is detected explicitly below via
# $LASTEXITCODE and Die, which is accurate; stderr is not.
$ErrorActionPreference = 'Continue'

$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Cli  = Join-Path $Repo '.venv\Scripts\event-aware-trader.exe'

Write-Host ''
Write-Host '==============================================='
Write-Host ' Alpaca paper-trading key setup'
Write-Host '==============================================='
Write-Host ''
Write-Host 'Get these from alpaca.markets -> Paper Trading -> API Keys.'
Write-Host 'If you have ever pasted them into a chat or a message,'
Write-Host 'click Regenerate there first and use the new ones.'
Write-Host ''

if (-not $KeyId) { $KeyId = (Read-Host 'Paste your API Key ID, then press Enter') }
$KeyId = "$KeyId".Trim()
Write-Host ("   got {0} characters, starting {1}" -f $KeyId.Length, `
    $(if ($KeyId.Length -ge 4) { $KeyId.Substring(0, 4) } else { $KeyId }))
Write-Host ''

# The secret used to be read with -AsSecureString, so nothing appeared while
# pasting. That is good practice for a password on a shared machine and bad
# practice here: with no feedback there is no way to tell a successful paste
# from a failed one, and it blocked setup outright. This is a PAPER trading
# key on your own machine, so it is shown. Clear the window afterwards if you
# would rather it not sit in the scrollback.
if (-not $Secret) {
    Write-Host 'Now paste your Secret Key and press Enter.'
    Write-Host '(It WILL be visible, so you can check the paste worked.)'
    $Secret = (Read-Host 'Secret')
}
$Secret = "$Secret".Trim()
Write-Host ("   got {0} characters, starting {1}" -f $Secret.Length, `
    $(if ($Secret.Length -ge 2) { $Secret.Substring(0, 2) } else { $Secret }))
Write-Host ''

if (-not $KeyId -or -not $Secret) {
    Write-Host 'One of them was empty. Nothing was saved. Run this again.'
    exit 1
}
if ($KeyId.Length -lt 15 -or $KeyId.Length -gt 30) {
    Write-Host "That Key ID is $($KeyId.Length) characters; Alpaca's are around 20."
    Write-Host 'Nothing was saved. Run this again and paste just the Key ID.'
    exit 1
}
if ($Secret.Length -lt 30 -or $Secret.Length -gt 60) {
    Write-Host "That Secret is $($Secret.Length) characters; Alpaca's are around 40."
    if ($Secret.Length -gt 60) {
        Write-Host 'It looks like it was pasted more than once - easy to do when the'
        Write-Host 'screen shows nothing back.'
    }
    Write-Host 'Nothing was saved. Run this again and paste the Secret ONCE.'
    exit 1
}
if ($KeyId.StartsWith('AK')) {
    Write-Host 'That is a LIVE key (starts with AK). This project is paper-only.'
    Write-Host 'Use the keys from the Paper Trading section instead. Nothing was saved.'
    exit 1
}

# 'User' scope persists across reboots and is inherited by Scheduled Tasks.
[Environment]::SetEnvironmentVariable('APCA_API_KEY_ID', $KeyId, 'User')
[Environment]::SetEnvironmentVariable('APCA_API_SECRET_KEY', $Secret, 'User')

# Also set them for THIS window, so the check below works without reopening.
$env:APCA_API_KEY_ID = $KeyId
$env:APCA_API_SECRET_KEY = $Secret

Write-Host 'Saved to your Windows user environment (not to any file in this project).'
Write-Host ''
Write-Host 'Checking the connection...'
Write-Host ''

& $Cli account
if ($LASTEXITCODE -eq 0) {
    Write-Host ''
    Write-Host '==============================================='
    Write-Host ' Connected. You can close this window.'
    Write-Host ' Next: install-session.ps1'
    Write-Host '==============================================='
} else {
    Write-Host ''
    Write-Host '==============================================='
    Write-Host ' That did not connect.'
    Write-Host ' Most likely the codes were swapped, or they are'
    Write-Host ' LIVE keys instead of PAPER keys. Check on'
    Write-Host ' alpaca.markets and run this again.'
    Write-Host '==============================================='
    exit 1
}
