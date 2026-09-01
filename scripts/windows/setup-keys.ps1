# Save your Alpaca paper keys into your Windows user environment.
#
# The keys never leave this computer. Nothing is uploaded, and nothing is
# written into the project folder, which is why they cannot end up on GitHub.
#
# Usage:  powershell -ExecutionPolicy Bypass -File setup-keys.ps1

$ErrorActionPreference = 'Stop'

$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
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

$KeyId = (Read-Host 'Paste your API Key ID, then press Enter').Trim()
Write-Host ("   got {0} characters, starting {1}" -f $KeyId.Length, `
    $(if ($KeyId.Length -ge 4) { $KeyId.Substring(0, 4) } else { $KeyId }))
Write-Host ''

# The secret is hidden while typing. That silence caused a real failure on the
# macOS version: with no feedback it is natural to assume the paste did not
# register and paste again, producing a doubled secret and a 401 that looks
# exactly like a wrong key. So the length is echoed back and checked here.
Write-Host 'Now paste your Secret Key and press Enter.'
Write-Host 'IMPORTANT: nothing will appear on screen. Paste ONCE, then press Enter.'
$SecretSecure = Read-Host -AsSecureString
$Secret = ([System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecretSecure))).Trim()
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
