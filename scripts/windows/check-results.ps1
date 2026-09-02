# See how it is doing. Right-click -> Run with PowerShell.

$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Cli  = Join-Path $Repo '.venv\Scripts\event-aware-trader.exe'
Set-Location $Repo

Write-Host ''
Write-Host '=============== IS IT ALIVE? ==============='
# Check this FIRST. A bot that never ran and a quiet market produce the same
# empty log, and on macOS that ambiguity hid a dead scheduler for a full day.
$Task = Get-ScheduledTask -TaskName 'EventAwareTrader' -ErrorAction SilentlyContinue
if ($null -eq $Task) {
    Write-Host 'Scheduled task NOT installed. Run install-session.ps1'
} else {
    $Info = Get-ScheduledTaskInfo -TaskName 'EventAwareTrader'
    Write-Host ("state          : {0}" -f $Task.State)
    Write-Host ("last run       : {0}" -f $Info.LastRunTime)
    Write-Host ("last result    : {0}  (0 = healthy)" -f $Info.LastTaskResult)
    Write-Host ("next run       : {0}" -f $Info.NextRunTime)
}

Write-Host ''
Write-Host '=============== ACCOUNT ==============='
& $Cli account --positions 2>&1 | Select-Object -First 25

Write-Host ''
Write-Host '=============== THE RECORD ==============='
& $Cli record 2>&1 | Select-Object -First 40

Write-Host ''
Write-Host '=============== RECENT ACTIVITY ==============='
$Log = Join-Path $Repo 'data\session.log'
if (Test-Path $Log) { Get-Content $Log -Tail 15 } else { Write-Host '(nothing logged yet)' }

Write-Host ''
Read-Host 'Press Enter to close'
