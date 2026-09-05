# Install the CRYPTO loop as a Windows Scheduled Task, running around the clock.
#
# Separate from EventAwareTrader, which stays on the US equity session. Crypto
# has no session, so this repeats every 15 minutes, every day, indefinitely -
# and stops itself when data\run-until.txt passes, the same end date the equity
# loop uses.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File install-crypto-session.ps1         # dry run
#   powershell -ExecutionPolicy Bypass -File install-crypto-session.ps1 -Live   # places orders

param([switch]$Live)

# NOT 'Stop'. Native programs write ordinary progress to stderr, and under
# 'Stop' PowerShell turns that into a terminating NativeCommandError.
$ErrorActionPreference = 'Continue'

$Repo     = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$TaskName = 'EventAwareTraderCrypto'
$Runner   = Join-Path $Repo 'scripts\windows\session-run-crypto.ps1'
$Cli      = Join-Path $Repo '.venv\Scripts\event-aware-trader.exe'

if (-not (Test-Path $Cli)) {
    Write-Error "$Cli not found. Create the venv and run 'pip install -e .' first."
    exit 1
}
if ($Repo -like '*OneDrive*') {
    Write-Error "This folder is inside OneDrive; move it somewhere local, e.g. C:\market-bot."
    exit 1
}

$Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Runner`""
if ($Live) { $Arguments += ' -Live' }

$Action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $Arguments -WorkingDirectory $Repo

# Daily rather than weekly, and a 24-hour repetition window rather than 6h30m:
# there is no weekend and no close to work around. Starting at midnight keeps
# the repeat boundary off the equity open, so the two loops are unlikely to
# collide on the same second.
$Start   = (Get-Date).Date
$Trigger = New-ScheduledTaskTrigger -Daily -At $Start
$Trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $Start `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Hours 24)).Repetition

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 14)

# S4U, so it runs whether or not anyone is logged on. An interactive-logon task
# would silently skip every slot overnight - which is most of them, for a loop
# whose entire purpose is running out of hours.
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$Description = 'Event-aware paper trading bot, CRYPTO loop. Alpaca paper account only.'

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
    Write-Host 'script again. Nothing was scheduled, and no existing task was'
    Write-Host 'changed.'
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

$Mode = if ($Live) { '--live (places paper orders)' } else { 'dry run (decides, sends nothing)' }
Write-Host ''
Write-Host "installed: $TaskName"
Write-Host "  mode         : $Mode"
Write-Host '  cadence      : every 15 min, 24/7 - crypto has no session'
Write-Host ("  runs when    : {0}" -f $(if ($Scope -eq 'S4U') { 'always, logged on or not' } else { 'ONLY while you are logged on (not elevated)' }))
Write-Host "  scope        : crypto only; the equity loop is untouched"
Write-Host "  activity log : $Repo\data\crypto-session.log"
Write-Host "  state file   : $Repo\data\autotrade-state-crypto.json"
Write-Host ''
Write-Host 'stop it with:'
Write-Host "  Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
Write-Host ''
Write-Host 'run one cycle now to check it works:'
Write-Host "  Start-ScheduledTask -TaskName $TaskName"
Write-Host "  Get-Content `"$Repo\data\crypto-session.log`" -Tail 20"
