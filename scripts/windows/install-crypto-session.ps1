# Install the CRYPTO watchdog as a Windows Scheduled Task, running around the
# clock. It does not itself trade every minute - it makes sure
# crypto-loop-worker.ps1 (which trades every $IntervalSeconds, default 30) is
# alive, and relaunches it, detached, if it is not.
#
# Separate from EventAwareTrader, which stays on the US equity session. Crypto
# has no session, so this repeats every minute, every day, indefinitely - and
# stops itself (and unregisters this task) when data\run-until.txt passes, the
# same end date the equity loop uses.
#
# WHY A ONE-MINUTE WATCHDOG AND NOT A 30-SECOND REPEATING TRIGGER. Task
# Scheduler's repetition trigger has a one-minute floor - a sub-minute
# RepetitionInterval is rejected or silently rounded up - so the 30-second
# cadence lives inside crypto-loop-worker.ps1's own loop, not in the scheduler.
# An AtStartup/AtLogOn trigger would let the scheduler launch that loop once
# and be done, but registering either of those trigger types requires an
# elevated (Administrator) PowerShell session on this machine, same as S4U
# below. This design needs neither: it reuses the Daily+Repetition trigger the
# 15-minute version already used successfully without elevation, just at the
# smallest interval Task Scheduler allows.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File install-crypto-session.ps1                          # dry run
#   powershell -ExecutionPolicy Bypass -File install-crypto-session.ps1 -Live                     # places orders
#   powershell -ExecutionPolicy Bypass -File install-crypto-session.ps1 -Live -IntervalSeconds 30 # explicit worker cadence

param([switch]$Live, [int]$IntervalSeconds = 30, [switch]$RequireS4U)

# NOT 'Stop'. Native programs write ordinary progress to stderr, and under
# 'Stop' PowerShell turns that into a terminating NativeCommandError.
$ErrorActionPreference = 'Continue'

$Repo     = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$TaskName = 'EventAwareTraderCrypto'
$Runner   = Join-Path $Repo 'scripts\windows\session-run-crypto.ps1'
$Worker   = Join-Path $Repo 'scripts\windows\crypto-loop-worker.ps1'
$Cli      = Join-Path $Repo '.venv\Scripts\event-aware-trader.exe'

if (-not (Test-Path $Cli)) {
    Write-Error "$Cli not found. Create the venv and run 'pip install -e .' first."
    exit 1
}
if ($Repo -like '*OneDrive*') {
    Write-Error "This folder is inside OneDrive; move it somewhere local, e.g. C:\market-bot."
    exit 1
}
if ($IntervalSeconds -lt 5) {
    Write-Error "IntervalSeconds $IntervalSeconds is too tight - each cycle makes several Alpaca API calls; 5s is the floor."
    exit 1
}

$Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Runner`" -IntervalSeconds $IntervalSeconds"
if ($Live) { $Arguments += ' -Live' }

# No window, ever: conhost --headless gives the script a console that is never
# drawn. -WindowStyle Hidden alone hides a console only after it opens, and an
# Interactive task's console can open in Windows Terminal, which ignores it -
# the owner saw a terminal flash every minute (2026-10-04).
$Conhost = Join-Path $env:WINDIR 'System32\conhost.exe'
$Action = New-ScheduledTaskAction -Execute $Conhost -Argument ("--headless powershell.exe " + $Arguments) -WorkingDirectory $Repo

# Daily rather than weekly, and a 24-hour repetition window rather than 6h30m:
# there is no weekend and no close to work around. One minute is the smallest
# RepetitionInterval Task Scheduler allows - this is a watchdog check, not a
# trade cycle, so it costs almost nothing to run that often.
$Start   = (Get-Date).Date
$Trigger = New-ScheduledTaskTrigger -Daily -At $Start
$Trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $Start `
    -RepetitionInterval (New-TimeSpan -Minutes 1) `
    -RepetitionDuration (New-TimeSpan -Hours 24)).Repetition

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 50)
# 50s, not 14 minutes: this task's Action is the watchdog check, which starts
# or verifies the worker and returns in well under a second, not the worker
# loop itself - the worker runs detached and outside Task Scheduler's control
# once launched, so no ExecutionTimeLimit applies to it.

# S4U, so it runs whether or not anyone is logged on. An interactive-logon task
# would silently skip every slot overnight - which is most of them, for a loop
# whose entire purpose is running out of hours.
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited

# Keep the existing definition before removing it. Registration happens AFTER
# an unregister, so a failure used to leave the account with no crypto task at
# all while this script printed "no existing task was changed" - which is what
# happened here on 2026-09-13 when an AtStartup trigger was refused. Now the
# old definition is restored on the way out.
$PreviousXml = $null
$Existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -ne $Existing) { $PreviousXml = Export-ScheduledTask -TaskName $TaskName }

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$Description = 'Event-aware paper trading bot, CRYPTO watchdog (worker trades every ' + $IntervalSeconds + 's). Alpaca paper account only.'

# S4U is what needs elevation, not the task. Try it, and fall back to a
# logon-scoped task rather than leaving nothing scheduled - but say which one
# was created, loudly, because the difference matters: an Interactive task
# fires ONLY while this user is logged on, so every slot with nobody at the
# keyboard is silently skipped. For a loop whose whole purpose is running
# overnight that is most of them.
$Scope = 'S4U'
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Settings $Settings -Principal $Principal -Description $Description `
    -ErrorAction SilentlyContinue | Out-Null

if ($null -eq (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    if ($RequireS4U) {
        Write-Host ''
        Write-Host 'FAILED: -RequireS4U was given and the S4U registration was refused.'
        Write-Host 'That means this PowerShell is not elevated. Nothing was left in a'
        Write-Host 'half-changed state - the previous task is restored below.'
        if ($PreviousXml) {
            Register-ScheduledTask -TaskName $TaskName -Xml $PreviousXml -Force `
                -ErrorAction SilentlyContinue | Out-Null
            Write-Host 'Previous task definition restored.'
        }
        exit 1
    }
    $Scope = 'Interactive'
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
        -Settings $Settings -Description $Description `
        -ErrorAction SilentlyContinue | Out-Null
}

# Register-ScheduledTask with an S4U principal needs elevation, and under
# $ErrorActionPreference = 'Continue' a denial is a warning the script would
# otherwise print "installed" straight over the top of. Verify the task is
# actually there before claiming anything - a scheduler that only looks
# installed is the failure this project has already had twice.
$Registered = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $Registered) {
    Write-Host ''
    Write-Host "FAILED: $TaskName was not registered."
    Write-Host 'Registering an S4U task requires elevation. Open PowerShell as'
    Write-Host 'Administrator (right-click > Run as administrator) and run this'
    Write-Host 'script again.'
    if ($PreviousXml) {
        Register-ScheduledTask -TaskName $TaskName -Xml $PreviousXml -Force `
            -ErrorAction SilentlyContinue | Out-Null
        if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
            Write-Host 'The previous task definition has been restored, so the bot keeps'
            Write-Host 'running on its old schedule.'
        } else {
            Write-Host 'WARNING: the previous task could NOT be restored either. There is'
            Write-Host 'currently no crypto task registered - re-run this script.'
        }
    }
    exit 1
}

if ($Scope -eq 'Interactive') {
    Write-Host ''
    Write-Host '================================================================'
    Write-Host ' REGISTERED, BUT ONLY WHILE YOU ARE LOGGED ON.'
    Write-Host ''
    Write-Host ' Running this without Administrator meant an S4U task could not'
    Write-Host ' be created, so it was registered against your interactive logon'
    Write-Host ' instead. It will NOT run while you are logged out or the machine'
    Write-Host ' is at the lock screen after a restart - which for an overnight'
    Write-Host ' loop is most of the hours it exists to cover.'
    Write-Host ''
    Write-Host ' To upgrade, re-run this in an Administrator PowerShell. It will'
    Write-Host ' replace this task with an S4U one that runs regardless.'
    Write-Host '================================================================'
}

# Only now that a task is definitely registered: clear the old worker out.
# This used to run at the top of the script, which meant a registration that
# failed had already killed the live worker and deleted its pid/heartbeat -
# punishing a failed install with an outage it did not need to cause. The
# watchdog would have healed it within the minute, but there is no reason to
# take the gap at all.
#
# A stale stop marker or pid/heartbeat must not make the fresh worker look
# already-running, and any worker left over from a previous installation must
# go: reinstalling should never leave two loops trading the same account.
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*crypto-loop-worker*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
foreach ($leftover in 'crypto-loop.stopped', 'crypto-loop.pid', 'crypto-loop.heartbeat') {
    Remove-Item (Join-Path $Repo "data\$leftover") -ErrorAction SilentlyContinue
}

# Run the watchdog once now. AtStartup/AtLogOn were rejected above (they need
# elevation) so nothing fires until the task's own trigger reaches the next
# minute boundary - without this, the new cadence would sit idle for up to a
# minute rather than taking effect immediately.
Start-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

$Mode = if ($Live) { '--live (places paper orders)' } else { 'dry run (decides, sends nothing)' }
Write-Host ''
Write-Host "installed: $TaskName"
Write-Host "  mode         : $Mode"
Write-Host "  cadence      : trades every ${IntervalSeconds}s, 24/7 - a persistent worker, kept alive by a 1-min watchdog"
Write-Host ("  runs when    : {0}" -f $(if ($Scope -eq 'S4U') { 'always, logged on or not' } else { 'ONLY while you are logged on (not elevated)' }))
Write-Host '  recovery     : the watchdog restarts the worker within a minute if it crashes or hangs'
Write-Host "  scope        : crypto only; the equity loop is untouched"
Write-Host "  activity log : $Repo\data\crypto-session.log"
Write-Host "  state file   : $Repo\data\autotrade-state-crypto.json"
Write-Host ''
Write-Host 'stop it with:'
Write-Host "  Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
Write-Host "  Get-Content `"$Repo\data\crypto-loop.pid`" | ForEach-Object { Stop-Process -Id `$_ -Force }"
Write-Host ''
Write-Host 'watch it working now:'
Write-Host "  Get-Content `"$Repo\data\crypto-session.log`" -Tail 20 -Wait"
