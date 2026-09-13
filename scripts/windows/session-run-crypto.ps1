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
# Keys live in the Windows USER environment. A task running under S4U while
# nobody is logged on does not always inherit that - the profile may not be
# loaded - and the failure would look like a credentials problem rather than a
# scheduling one. So if the process environment is missing them, read them from
# the user environment (HKCU) directly and put them into this process, which
# the worker and its python children then inherit.
#
# Values are moved in memory only: never logged, never written to the repo.
foreach ($name in 'APCA_API_KEY_ID', 'APCA_API_SECRET_KEY') {
    if (-not [Environment]::GetEnvironmentVariable($name, 'Process')) {
        $fromUser = [Environment]::GetEnvironmentVariable($name, 'User')
        if ($fromUser) { [Environment]::SetEnvironmentVariable($name, $fromUser, 'Process') }
    }
}
if (-not $env:APCA_API_KEY_ID -or -not $env:APCA_API_SECRET_KEY) {
    Say 'FATAL: APCA_API_KEY_ID / APCA_API_SECRET_KEY are not set (not in this process and not in the user environment). Run scripts\windows\setup-keys.ps1'
    exit 1
}

# ---- is the worker alive? ------------------------------------------------------
# Alive means: a recorded PID, a running process at that PID, AND a heartbeat
# written recently. All three, not just the process existing - a worker that is
# running but stuck (a hung network call, a deadlock) still holds its PID, which
# is exactly the case a bare process check would miss.
$StaleAfter = [Math]::Max(90, $IntervalSeconds * 4)   # generous vs. the 30s cadence

# Enumerate every worker process rather than trusting the pid file alone. If
# the pid file is ever lost or overwritten - the installer used to delete it -
# an orphaned worker would keep trading, invisible to a pid-file-only check,
# alongside whatever replacement got started. Two loops on one account is the
# one outcome this design must never allow, so the launch path below kills
# every worker it finds first.
#
# The match requires the -File argument AND the worker's script name: matching
# the bare name would also match any diagnostic command that merely mentions
# it (including, embarrassingly, the command doing the matching), and this
# process is excluded explicitly for the same reason.
$Workers = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessId -ne $PID -and
                   $_.CommandLine -like '*-File*' -and
                   $_.CommandLine -like '*crypto-loop-worker.ps1*' })

$Fresh = (Test-Path $Heartbeat) -and
         (((Get-Date) - (Get-Item $Heartbeat).LastWriteTime).TotalSeconds -lt $StaleAfter)

if ($Workers.Count -eq 1) {
    if ($Fresh) { exit 0 }                                  # healthy; leave it alone
    # No heartbeat yet, but the process is seconds old: it is still starting,
    # not hung. Restarting here would loop forever on a slow-starting worker.
    $age = ((Get-Date) - $Workers[0].CreationDate).TotalSeconds
    if (-not (Test-Path $Heartbeat) -and $age -lt $StaleAfter) { exit 0 }
    Say "worker pid $($Workers[0].ProcessId) is running but its heartbeat is stale; restarting it"
}
elseif ($Workers.Count -gt 1) {
    Say "found $($Workers.Count) workers running at once; stopping all of them and starting one"
}

foreach ($w in $Workers) { Stop-Process -Id $w.ProcessId -Force -ErrorAction SilentlyContinue }
Remove-Item $PidFile, $Heartbeat -ErrorAction SilentlyContinue

# ---- (re)launch it, detached --------------------------------------------------
if ($Workers.Count -eq 0) { Say 'worker not running; starting it' }
$WorkerArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden',
               '-File', "`"$Worker`"", '-IntervalSeconds', $IntervalSeconds)
if ($Live) { $WorkerArgs += '-Live' }
Start-Process -FilePath 'powershell.exe' -ArgumentList $WorkerArgs -WindowStyle Hidden `
    -WorkingDirectory $Repo | Out-Null
