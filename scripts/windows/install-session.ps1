# Install the paper-trading experiment as a Windows Scheduled Task.
#
# One task, triggered weekdays at the local time the US market opens, repeating
# every 15 minutes for 6h30m. That is simpler than the macOS version, which
# needs 130 separate calendar entries because launchd has no repetition.
#
# No API key is written into the task. session-run.ps1 reads them from your
# user environment at run time, so the task definition holds no secrets.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File install-session.ps1                # dry run
#   powershell -ExecutionPolicy Bypass -File install-session.ps1 -Live          # places orders
#   powershell -ExecutionPolicy Bypass -File install-session.ps1 -Months 2 -Live

param(
    [int]$Months = 2,
    [switch]$Live
)

# NOT 'Stop'. Native programs write ordinary progress to stderr - git clone,
# pip, winget all do - and under 'Stop' PowerShell turns that into a
# terminating NativeCommandError. A Microsoft Store python stub killed this
# script on line one that way. Failure is detected explicitly below via
# $LASTEXITCODE and Die, which is accurate; stderr is not.
$ErrorActionPreference = 'Continue'

$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$TaskName = 'EventAwareTrader'
$Runner   = Join-Path $Repo 'scripts\windows\session-run.ps1'
$Cli      = Join-Path $Repo '.venv\Scripts\event-aware-trader.exe'

if (-not (Test-Path $Cli)) {
    Write-Error "$Cli not found. Create the venv and run 'pip install -e .' first."
    exit 1
}

# Windows does not restrict background tasks from reading any user folder, so
# the macOS Desktop problem does not apply here. Refuse OneDrive-backed paths
# instead: file locking and on-demand placeholders both break a running job.
if ($Repo -like '*OneDrive*') {
    Write-Error @"
This folder is inside OneDrive:
  $Repo
OneDrive syncs files while they are being written and can replace them with
placeholders that block until downloaded, which will corrupt the state file.
Move the folder somewhere local, for example C:\market-bot, and run this again.
"@
    exit 1
}

# ---- the US session in this machine's local time ----------------------------
$Eastern = [System.TimeZoneInfo]::FindSystemTimeZoneById('Eastern Standard Time')
$Today   = Get-Date
$NyOpen  = [datetime]::new($Today.Year, $Today.Month, $Today.Day, 9, 30, 0, [DateTimeKind]::Unspecified)
$OpenUtc = [System.TimeZoneInfo]::ConvertTimeToUtc($NyOpen, $Eastern)
$Open    = $OpenUtc.ToLocalTime()

Write-Host ("US session 09:30-16:00 New York = {0} local, repeating 15 min for 6h30m" -f $Open.ToString('HH:mm'))

# ---- stop date, read by session-run.ps1 on every cycle ----------------------
New-Item -ItemType Directory -Force -Path (Join-Path $Repo 'data') | Out-Null
$Until = (Get-Date).AddDays(31 * $Months).ToString('yyyy-MM-dd')
$Until | Out-File -FilePath (Join-Path $Repo 'data\run-until.txt') -Encoding ascii -NoNewline
Write-Host "will stop on $Until"

# ---- build the task ---------------------------------------------------------
$Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Runner`""
if ($Live) { $Arguments += ' -Live' }

# No window, ever, even if the task falls back to an interactive logon:
# conhost --headless gives the script a console that is never drawn
# (2026-10-04, the owner saw terminal windows flash).
$Conhost = Join-Path $env:WINDIR 'System32\conhost.exe'
$Action = New-ScheduledTaskAction -Execute $Conhost -Argument ("--headless powershell.exe " + $Arguments) -WorkingDirectory $Repo

# A weekly trigger carries the weekday restriction; the repetition has to be
# grafted on from a one-off trigger, which is the documented way to get both.
$Trigger = New-ScheduledTaskTrigger -Weekly `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At $Open
$Trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $Open `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Hours 6 -Minutes 30)).Repetition

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 14)

# MultipleInstances IgnoreNew plus a 14-minute limit is the pair that matters:
# a cycle that hangs is killed before the next one is due, so one bad fetch
# cannot silently eat the rest of the session the way it did on macOS.

# Register-ScheduledTask with no -Principal defaults to an interactive logon:
# the task only fires while this user is actively logged on. This machine is
# not logged in all day, so every 15-minute slot during a session where nobody
# is sitting at the keyboard is silently skipped - the task shows up "Ready"
# and healthy with zero evidence anything was missed except a rising
# NumberOfMissedRuns. S4U runs as this user, whether logged on or not, and
# needs no stored password.
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Settings $Settings -Principal $Principal `
    -Description 'Event-aware paper trading bot. Alpaca paper account only.' | Out-Null

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

$Mode = if ($Live) { '--live (places paper orders)' } else { 'dry run (decides, sends nothing)' }
Write-Host ''
Write-Host "installed: $TaskName"
Write-Host "  mode         : $Mode"
Write-Host "  cadence      : every 15 min, weekdays, $($Open.ToString('HH:mm')) for 6h30m"
Write-Host "  stops on     : $Until"
Write-Host "  activity log : $Repo\data\session.log"
Write-Host "  daily report : $Repo\data\DAILY-REPORT.json"
Write-Host ''
Write-Host 'stop early with:'
Write-Host "  Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
Write-Host ''
Write-Host 'run one cycle right now to check it works:'
Write-Host "  Start-ScheduledTask -TaskName $TaskName"
Write-Host "  Get-Content `"$Repo\data\session.log`" -Tail 20"
