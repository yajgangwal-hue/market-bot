# Stop the bot. Right-click -> Run with PowerShell.
#
# This stops the SCHEDULER. It does not close positions, and it does leave them
# protected - but not managed.
#
# Every cycle rests a standalone GTC sell-stop under each position, so the stop
# survives both the close and this scheduler being unregistered. It sits at
# Alpaca until it fills or is replaced.
#
# What stops is the ratchet. That stop is only raised behind a rising price by
# a running cycle, so once this is unregistered it stays frozen at its last
# level. Protection, yes; a trailing stop, no.
#
# (Before 3c054d5 this was worse: entries relied on the bracket alone, whose
# legs are time_in_force=day, so the take-profit expired at the bell and OCO
# cancelled the stop with it. Measured 2026-09-01, both legs gone at 16:01:38
# ET and two positions sat overnight naked. If this machine has not pulled that
# commit, that is still the behaviour.)
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
Write-Host 'Those positions stay OPEN, and they keep their stops: each carries a'
Write-Host 'standalone GTC sell-stop at Alpaca that survives both the close and this'
Write-Host 'scheduler stopping. What stops is the ratchet - nothing raises the stop'
Write-Host 'behind a rising price any more, so it sits frozen at its last level.'
Write-Host 'Close them in TradingView or on the Alpaca dashboard if you want to be flat.'
Write-Host ''
Read-Host 'Press Enter to close'
