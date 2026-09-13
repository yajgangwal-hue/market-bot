# The crypto watchdog. Fires every minute from Task Scheduler and makes sure
# crypto-loop-worker.ps1 - the actual 24/7 loop - is alive; if it is, this does
# nothing and exits in well under a second.
#
# WHY A WATCHDOG AND NOT THE LOOP ITSELF. Two designs were tried for the
# 2026-09-13 move from a 15-minute cadence to 30 seconds:
#
#   1. Task Scheduler repeats this script every 30 seconds directly. Rejected:
#      the repetition trigger has a documented one-minute floor - a sub-minute
#      RepetitionInterval is rejected or silently rounded up.
#   2. This script IS a persistent `while ($true) { ...; Start-Sleep 30 }` loop,
#      started once by an AtStartup/AtLogOn trigger. Rejected: registering
#      EITHER of those trigger types requires an elevated (Administrator)
#      PowerShell session on this machine, even for a plain per-user task, and
#      this needed to work right now without asking for elevation.
#
# So: the loop lives in a separate script (crypto-loop-worker.ps1) launched
# DETACHED and left running, and this watchdog - on the same Daily+1-minute-
# repetition trigger already proven to register without elevation - checks
# once a minute that it is still alive and relaunches it if not. A worker that
# hangs (not crashed, just stuck) is caught the same way a crash is: its
# heartbeat file goes stale and the watchdog kills and restarts it, which is
# what Task Scheduler's own ExecutionTimeLimit used to do for the old
# one-cycle-per-firing design.
#
# Usage:  powershell -ExecutionPolicy Bypass -File session-run-crypto.ps1 [-Live] [-IntervalSeconds 30]

param([switch]$Live, [int]$IntervalSeconds = 30)

$ErrorActionPreference = 'Continue'

$Repo    = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Worker  = Join-Path $Repo 'scripts\windows\crypto-loop-worker.ps1'
$Cli     = Join-Path $Repo '.venv\Scripts\event-aware-trader.exe'
$Log     = Join-Path $Repo 'data\crypto-session.log'
$PidFile = Join-Path $Repo 'data\crypto-loop.pid'
$Heartbeat = Join-Path $Repo 'data\crypto-loop.heartbeat'
$StoppedFile = Join-Path $Repo 'data\crypto-loop.stopped'

Set-Location $Repo
New-Item -ItemType Directory -Force -Path (Join-Path $Repo 'data') | Out-Null

function Stamp { (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }
function Say([string]$Message) { "[$(Stamp)] $Message" | Out-File -FilePath $Log -Append -Encoding utf8 }

# ---- the worker decided the experiment is over -------------------------------
# It drops this marker itself before exiting (see crypto-loop-worker.ps1). Once
# it's here, stop relaunching and stop the minute-by-minute watchdog firings too.
if (Test-Path $StoppedFile) {
    Unregister-ScheduledTask -TaskName 'EventAwareTraderCrypto' -Confirm:$false -ErrorAction SilentlyContinue
    exit 0
}

if (-not (Test-Path $Cli)) {
    Say "FATAL: $Cli not found. Create the venv and run 'pip install -e .' first."
    exit 1
}
if (-not $env:APCA_API_KEY_ID -or -not $env:APCA_API_SECRET_KEY) {
    Say 'FATAL: APCA_API_KEY_ID / APCA_API_SECRET_KEY are not set. Run scripts\windows\setup-keys.ps1'
    exit 1
}

# ---- is the worker alive? ------------------------------------------------------
# Alive means: a recorded PID, a running process at that PID, AND a heartbeat
# written recently. All three, not just the process existing - a worker that is
# running but stuck (a hung network call, a deadlock) still holds its PID, which
# is exactly the case a bare process check would miss.
$StaleAfter = [Math]::Max(90, $IntervalSeconds * 4)   # generous vs. the 30s cadence
$Healthy = $false
if (Test-Path $PidFile) {
    $WorkerPid = (Get-Content $PidFile -Raw).Trim()
    $Process = Get-Process -Id $WorkerPid -ErrorAction SilentlyContinue
    if ($Process -and $Process.ProcessName -eq 'powershell') {
        if ((Test-Path $Heartbeat) -and
            ((Get-Date) - (Get-Item $Heartbeat).LastWriteTime).TotalSeconds -lt $StaleAfter) {
            $Healthy = $true
        }
        elseif (-not $Healthy) {
            Say "worker pid $WorkerPid is running but its heartbeat is stale; stopping it"
            Stop-Process -Id $WorkerPid -Force -ErrorAction SilentlyContinue
        }
    }
}

if ($Healthy) { exit 0 }

# ---- (re)launch it, detached --------------------------------------------------
Say 'worker not found or unhealthy; starting it'
$WorkerArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden',
               '-File', "`"$Worker`"", '-IntervalSeconds', $IntervalSeconds)
if ($Live) { $WorkerArgs += '-Live' }
Start-Process -FilePath 'powershell.exe' -ArgumentList $WorkerArgs -WindowStyle Hidden `
    -WorkingDirectory $Repo | Out-Null
