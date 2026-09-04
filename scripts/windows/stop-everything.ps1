# Stop the bot. Right-click -> Run with PowerShell.
#
# This stops the SCHEDULER. It does not close positions, and - important - it
# does not leave them protected either.
#
# Entries go in as bracket orders, so there IS a resting stop at Alpaca, but
# only until the close. Every leg is time_in_force=day: the take-profit limit
# expires at the bell and OCO cancels the stop along with it (measured
# 2026-09-01, both legs gone at 16:01:38 ET, 90 seconds after the close). After
# that the position has no broker-side stop at all, and the software trailing
# stop only runs when a cycle runs - so with the scheduler stopped, nothing is
# watching it.
#
# If you want to be flat, close the position yourself in TradingView or on the
# Alpaca dashboard.

$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Cli  = Join-Path $Repo '.venv\Scripts\event-aware-trader.exe'

Unregister-ScheduledTask -TaskName 'EventAwareTrader' -Confirm:$false -ErrorAction SilentlyContinue
Write-Host 'Scheduled task removed. No further cycles will run.'
Write-Host ''

Write-Host 'Anything still open at the broker:'
& $Cli account --positions 2>&1 | Select-Object -First 25

Write-Host ''
Write-Host 'Those positions stay OPEN and, after the next close, UNPROTECTED:'
Write-Host 'the bracket stop is a day order and does not survive the bell.'
Write-Host 'With the scheduler stopped nothing re-arms it. Close them yourself'
Write-Host 'in TradingView or on the Alpaca dashboard if you want to be flat.'
Write-Host ''
Read-Host 'Press Enter to close'
