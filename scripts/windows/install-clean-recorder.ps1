# Install the Phase 4 clean-session recorder as a Windows Scheduled Task.
#
# One run per weekday, 15 minutes after the US close, so the loop's last cycle
# (16:00 ET) has finished and the account has settled. The recorder decides
# for itself whether the session is eligible; scheduling it now means the
# record starts on the first clean day without anyone remembering to start it.
#
# SEPARATE FROM THE TRADING TASK, deliberately. session-run.ps1 is in the
# frozen set for the duration of the observation period and must show an empty
# diff (G23), so the recorder cannot be wired into it.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File install-clean-recorder.ps1

$ErrorActionPreference = 'Continue'

$Repo     = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$TaskName = 'EventAwareTraderCleanRecorder'
$Runner   = Join-Path $Repo 'scripts\windows\record-clean-session.ps1'

if (-not (Test-Path $Runner)) {
    Write-Error "$Runner not found."
    exit 1
}

# 16:15 New York, expressed in this machine's local time.
$Eastern = [System.TimeZoneInfo]::FindSystemTimeZoneById('Eastern Standard Time')
$Today   = Get-Date
$NyAfter = [datetime]::new($Today.Year, $Today.Month, $Today.Day, 16, 15, 0, [DateTimeKind]::Unspecified)
$AfterUtc = [System.TimeZoneInfo]::ConvertTimeToUtc($NyAfter, $Eastern)
$At      = $AfterUtc.ToLocalTime()

Write-Host ("16:15 New York = {0} local" -f $At.ToString('HH:mm'))

$Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Runner`""
# No window, ever, even if the task falls back to an interactive logon:
# conhost --headless gives the script a console that is never drawn
# (2026-10-04, the owner saw terminal windows flash).
$Conhost = Join-Path $env:WINDIR 'System32\conhost.exe'
$Action = New-ScheduledTaskAction -Execute $Conhost -Argument ("--headless powershell.exe " + $Arguments) -WorkingDirectory $Repo

$Trigger = New-ScheduledTaskTrigger -Weekly `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At $At

# StartWhenAvailable matters more here than for the trading loop. A missed
# recorder run is a permanent HOLE in the clean record - nothing may be
# backfilled - so a run delayed by a sleeping machine is strictly better than
# a run skipped.
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# S4U runs as this user whether or not anyone is logged on, which is what a
# once-a-day recorder needs. Registering it requires elevation. If that is
# refused, fall back to an interactive-logon task and SAY SO - an interactive
# task silently skips every day the machine is not logged on, and each skip is
# a hole in the record that cannot be filled later.
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Settings $Settings -Principal $Principal `
    -Description 'Phase 4 clean-session recorder. Read-only; places no orders.' `
    -ErrorAction SilentlyContinue | Out-Null

$Registered = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$Scope = 'S4U (runs whether or not you are logged on)'

if ($null -eq $Registered) {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
        -Settings $Settings `
        -Description 'Phase 4 clean-session recorder. Read-only; places no orders.' `
        -ErrorAction SilentlyContinue | Out-Null
    $Registered = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    $Scope = 'Interactive logon - RUNS ONLY WHILE YOU ARE LOGGED ON'
}

if ($null -eq $Registered) {
    Write-Host ''
    Write-Host "FAILED: $TaskName was not registered. Nothing was scheduled."
    exit 1
}

Write-Host ''
Write-Host "installed: $TaskName"
Write-Host "  runs    : weekdays $($At.ToString('HH:mm')) local"
Write-Host "  scope   : $Scope"
Write-Host "  log     : $Repo\data\clean-recorder.log"
Write-Host ''
if ($Scope -like 'Interactive*') {
    Write-Host 'WARNING: every weekday this machine is not logged on at that'
    Write-Host 'time, the recorder is skipped and that session becomes a'
    Write-Host 'permanent hole in the clean record. To fix it, run this script'
    Write-Host 'again from an elevated PowerShell (right-click > Run as'
    Write-Host 'administrator).'
    Write-Host ''
}
Write-Host 'check it now (it will refuse until the embargo expires):'
Write-Host "  Start-ScheduledTask -TaskName $TaskName"
Write-Host "  Get-Content `"$Repo\data\clean-recorder.log`" -Tail 20"
