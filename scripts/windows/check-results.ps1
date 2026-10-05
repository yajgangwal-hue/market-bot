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
Write-Host '=============== TODAY ==============='
# The question this answers is "why was TradingView empty when I looked?".
# A session with no entries and a session that never ran produce an identical
# broker panel, and at roughly one trade per 51 sessions the quiet one is
# overwhelmingly the likely answer. Say which it was, in words, rather than
# leaving an empty screen to be interpreted.
$ReportFile = Join-Path $Repo 'data\DAILY-REPORT.json'
if (-not (Test-Path $ReportFile)) {
    Write-Host 'No daily report yet - one is written at the close of each session.'
} else {
    try {
        $Day = Get-Content $ReportFile -Raw -Encoding UTF8 | ConvertFrom-Json
        Write-Host ("session         : {0}" -f $Day.session)
        Write-Host ("cycles run      : {0}" -f $Day.cycles_run)
        Write-Host ("opened / closed : {0} / {1}" -f $Day.opened_today, $Day.closed_today)
        Write-Host ("held overnight  : {0}" -f $Day.positions_held_overnight)
        if ($Day.opened_today -eq 0 -and $Day.positions_held_overnight -eq 0) {
            Write-Host ''
            Write-Host 'Nothing traded and nothing is open, so an empty Positions tab'
            Write-Host 'in TradingView is CORRECT, not a fault. Past trades live under'
            Write-Host 'the History / Orders tab - Positions only ever shows what is'
            Write-Host 'open right now.'
            if ($Day.closest_candidates) {
                Write-Host ''
                Write-Host ("Nearest misses (the gate is {0}):" -f $Day.score_gate)
                $Day.closest_candidates | Select-Object -First 3 | ForEach-Object {
                    Write-Host ("  {0,-6} scored {1}, short by {2}" -f `
                        $_.symbol, $_.score, $_.short_by)
                }
            }
        }
    } catch {
        Write-Host ("Could not read {0}: {1}" -f $ReportFile, $_.Exception.Message)
    }
}

Write-Host ''
Write-Host '=============== ACCOUNT ==============='
& $Cli account --positions 2>&1 | Select-Object -First 25

Write-Host ''
Write-Host '=============== THE RECORD ==============='
& $Cli record 2>&1 | Select-Object -First 40

Write-Host ''
Write-Host '=============== +0.5% / -0.2% RULE vs THE BOT ==============='
# Tracked on paper only (owner's choice 2026-09-27) - no order is ever placed
# for it. Reads the audit log; the full position list is in the daily report
# and in scripts/tight_exit_compare.py without --brief.
& (Join-Path $Repo '.venv\Scripts\python.exe') 'scripts/tight_exit_compare.py' --brief 2>&1 |
    Select-Object -First 25

Write-Host ''
Write-Host '=============== RECENT ACTIVITY ==============='
$Log = Join-Path $Repo 'data\session.log'
if (Test-Path $Log) { Get-Content $Log -Tail 15 } else { Write-Host '(nothing logged yet)' }

Write-Host ''
Read-Host 'Press Enter to close'
