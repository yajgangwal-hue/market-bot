# Stop the bot. Right-click -> Run with PowerShell.
#
# This stops the SCHEDULER. It does not close positions: every entry is sent as
# a bracket order, so its stop is resting at Alpaca and stays there whether or
# not this computer is on. If you want to be flat, close the position yourself
# in TradingView or on the Alpaca dashboard.

$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Cli  = Join-Path $Repo '.venv\Scripts\event-aware-trader.exe'

Unregister-ScheduledTask -TaskName 'EventAwareTrader' -Confirm:$false -ErrorAction SilentlyContinue
Write-Host 'Scheduled task removed. No further cycles will run.'
Write-Host ''

Write-Host 'Anything still open at the broker:'
& $Cli account --positions 2>&1 | Select-Object -First 25

Write-Host ''
Write-Host 'Those positions stay open with their resting stops at Alpaca.'
Write-Host 'Close them in TradingView if you want to be flat.'
Write-Host ''
Read-Host 'Press Enter to close'
