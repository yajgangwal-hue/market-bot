# One command that sets the whole thing up on a fresh Windows 11 machine.
#
# Installs Python and Git if missing, clones the repo, builds the environment,
# runs the tests, asks for your Alpaca keys, stops the machine sleeping, then
# registers the schedule and proves it works by running one cycle.
#
# Run it in PowerShell (Run as Administrator, so winget and powercfg work):
#
#   irm https://raw.githubusercontent.com/yajgangwal-hue/market-bot/main/scripts/windows/bootstrap.ps1 | iex
#
# or, if you already have the folder:
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\windows\bootstrap.ps1

param(
    [string]$InstallPath = 'C:\market-bot',
    [int]$Months = 2,
    [switch]$SkipPowerSettings
)

$ErrorActionPreference = 'Stop'

function Step($n, $text) { Write-Host ''; Write-Host "=== $n. $text ===" -ForegroundColor Cyan }
function Ok($text)       { Write-Host "    OK  $text" -ForegroundColor Green }
function Warn($text)     { Write-Host "    !!  $text" -ForegroundColor Yellow }
function Die($text)      { Write-Host "    XX  $text" -ForegroundColor Red; exit 1 }

Write-Host ''
Write-Host '==========================================='
Write-Host '  Event-aware trading bot - Windows setup'
Write-Host '==========================================='
Write-Host '  Paper trading only. No real money is used.'

# Pull PATH changes made by installers into THIS session, so a freshly
# installed python is findable without reopening the window.
function Update-PathFromRegistry {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user    = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
}

# ---- 1. Python --------------------------------------------------------------
Step 1 'Python'
$Python = $null
foreach ($candidate in 'python', 'python3', 'py') {
    $found = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($found) {
        $version = & $found.Source --version 2>&1
        if ($version -match 'Python 3\.(9|1[0-9])') { $Python = $found.Source; break }
    }
}
if (-not $Python) {
    Warn 'Python 3 not found - installing it with winget (this takes a minute)'
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Die 'winget is missing. Install Python 3.11 from python.org, tick "Add python.exe to PATH", then run this again.'
    }
    winget install --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
    Update-PathFromRegistry
    foreach ($candidate in 'python', 'python3') {
        $found = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($found) { $Python = $found.Source; break }
    }
    if (-not $Python) {
        Die 'Python installed but is not on PATH yet. Close PowerShell, open a new one, and run this again.'
    }
}
Ok "$Python ($(& $Python --version 2>&1))"

# ---- 2. Git -----------------------------------------------------------------
Step 2 'Git'
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Warn 'Git not found - installing it with winget'
    winget install --id Git.Git --silent --accept-package-agreements --accept-source-agreements
    Update-PathFromRegistry
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Die 'Git installed but is not on PATH yet. Close PowerShell, open a new one, and run this again.'
}
Ok (git --version)

# ---- 3. the code ------------------------------------------------------------
Step 3 "Code into $InstallPath"
if ($InstallPath -like '*OneDrive*') {
    Die "$InstallPath is inside OneDrive. Sync placeholders corrupt the bot's state file. Use C:\market-bot."
}
if (Test-Path (Join-Path $InstallPath '.git')) {
    Write-Host '    folder already exists - updating it instead'
    Push-Location $InstallPath
    git pull --ff-only
    Pop-Location
} else {
    Write-Host '    GitHub will ask you to sign in - the repo is private.'
    git clone https://github.com/yajgangwal-hue/market-bot.git $InstallPath
}
if (-not (Test-Path (Join-Path $InstallPath 'pyproject.toml'))) { Die 'clone failed' }
Set-Location $InstallPath
Ok $InstallPath

# ---- 4. the environment -----------------------------------------------------
Step 4 'Python environment (a few minutes)'
$VenvPython = Join-Path $InstallPath '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) { & $Python -m venv (Join-Path $InstallPath '.venv') }
& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install -e ".[ai]" --quiet
if ($LASTEXITCODE -ne 0) { Die 'pip install failed - see the output above' }
Ok 'dependencies installed'

# ---- 5. prove the code works before trusting it with an account -------------
Step 5 'Tests'
& $VenvPython -m unittest discover -s tests -t . -q 2>&1 | Select-Object -Last 3
if ($LASTEXITCODE -ne 0) { Die 'tests failed - do not run the bot until this is understood' }
Ok 'all tests pass'

# ---- 6. keys ----------------------------------------------------------------
Step 6 'Alpaca paper keys'
if ($env:APCA_API_KEY_ID -and $env:APCA_API_SECRET_KEY) {
    Ok 'keys already set in this environment'
} else {
    Write-Host '    You need to paste these yourself - they are credentials, so'
    Write-Host '    they are never stored in the project or sent anywhere.'
    & powershell -ExecutionPolicy Bypass -File (Join-Path $InstallPath 'scripts\windows\setup-keys.ps1')
    if ($LASTEXITCODE -ne 0) { Die 'key setup did not complete' }
    Update-PathFromRegistry
    $env:APCA_API_KEY_ID     = [Environment]::GetEnvironmentVariable('APCA_API_KEY_ID', 'User')
    $env:APCA_API_SECRET_KEY = [Environment]::GetEnvironmentVariable('APCA_API_SECRET_KEY', 'User')
}

# ---- 7. stop the machine sleeping -------------------------------------------
Step 7 'Power settings'
if ($SkipPowerSettings) {
    Warn 'skipped - if this machine sleeps, the bot stops trading'
} else {
    # Sleep is the single most common reason a scheduled bot goes quiet, so
    # this is set deliberately rather than left to be discovered.
    powercfg /change standby-timeout-ac 0
    powercfg /change hibernate-timeout-ac 0
    powercfg /change monitor-timeout-ac 15
    Ok 'will not sleep on mains power (screen still turns off after 15 min)'
}

# ---- 8. schedule ------------------------------------------------------------
Step 8 'Schedule'
& powershell -ExecutionPolicy Bypass -File (Join-Path $InstallPath 'scripts\windows\install-session.ps1') -Months $Months -Live
if ($LASTEXITCODE -ne 0) { Die 'could not register the scheduled task' }

# ---- 9. prove the whole chain works right now -------------------------------
Step 9 'Proving it works - running one cycle now'
Start-ScheduledTask -TaskName 'EventAwareTrader'
$log = Join-Path $InstallPath 'data\session.log'
$deadline = (Get-Date).AddMinutes(6)
$done = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 10
    $state = (Get-ScheduledTask -TaskName 'EventAwareTrader').State
    if ($state -ne 'Running') { $done = $true; break }
}

Write-Host ''
if ($done -and (Test-Path $log)) {
    $tail = Get-Content $log -Tail 30 -ErrorAction SilentlyContinue
    if ($tail -match '"status": "ok"') {
        Write-Host '==========================================='  -ForegroundColor Green
        Write-Host '  WORKING. Nothing else for you to do.'        -ForegroundColor Green
        Write-Host '  It trades weekdays and stops on its own.'    -ForegroundColor Green
        Write-Host '==========================================='  -ForegroundColor Green
    } elseif ($tail -match 'FATAL') {
        Warn 'the cycle reported FATAL - here are the last lines:'
        $tail | Select-Object -Last 10
    } else {
        Warn 'the cycle finished but did not report ok - last lines:'
        $tail | Select-Object -Last 10
    }
} else {
    Warn 'the first cycle is still running. Check in a few minutes with:'
    Write-Host "    Get-Content $log -Tail 20"
}

Write-Host ''
Write-Host 'Check on it any time:'
Write-Host "    powershell -ExecutionPolicy Bypass -File $InstallPath\scripts\windows\check-results.ps1"
Write-Host 'Stop it:'
Write-Host "    powershell -ExecutionPolicy Bypass -File $InstallPath\scripts\windows\stop-everything.ps1"
