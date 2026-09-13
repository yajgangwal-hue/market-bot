# The crypto loop's actual worker. This is not launched by Task Scheduler
# directly - session-run-crypto.ps1 (the watchdog) launches it detached and
# leaves it running. See that file for why: Task Scheduler's repetition floor
# is one minute, so "every 30 seconds" has to come from a process that loops
# internally rather than from the scheduler relaunching something that often.
#
# It writes its PID and a heartbeat every cycle so the watchdog can tell a
# healthy loop from a dead or hung one. It does NOT re-register or unregister
# any scheduled task itself - the watchdog owns that decision.
#
# Usage:  powershell -File crypto-loop-worker.ps1 [-Live] [-IntervalSeconds 30]

param([switch]$Live, [int]$IntervalSeconds = 30)

$ErrorActionPreference = 'Continue'   # a bad cycle must not kill the loop

$Repo    = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Python  = Join-Path $Repo '.venv\Scripts\python.exe'
$Log     = Join-Path $Repo 'data\crypto-session.log'
$PidFile = Join-Path $Repo 'data\crypto-loop.pid'
$Heartbeat = Join-Path $Repo 'data\crypto-loop.heartbeat'

Set-Location $Repo
New-Item -ItemType Directory -Force -Path (Join-Path $Repo 'data') | Out-Null

function Stamp { (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }
function Say([string]$Message) { "[$(Stamp)] $Message" | Out-File -FilePath $Log -Append -Encoding utf8 }

# Same user-environment recovery as the watchdog, because this can also be
# started by hand. Normally the watchdog has already done it and this is a
# no-op - the worker inherits its environment. Values move in memory only:
# never logged, never written to the repo.
foreach ($name in 'APCA_API_KEY_ID', 'APCA_API_SECRET_KEY') {
    if (-not [Environment]::GetEnvironmentVariable($name, 'Process')) {
        $fromUser = [Environment]::GetEnvironmentVariable($name, 'User')
        if ($fromUser) { [Environment]::SetEnvironmentVariable($name, $fromUser, 'Process') }
    }
}
if (-not $env:APCA_API_KEY_ID -or -not $env:APCA_API_SECRET_KEY) {
    Say 'FATAL: worker has no API keys (not in this process and not in the user environment); not starting'
    exit 1
}

$PID | Out-File -FilePath $PidFile -Encoding ascii -Force
Say "worker starting, pid $PID, interval ${IntervalSeconds}s, live=$Live"

while ($true) {

    (Get-Date).ToString('o') | Out-File -FilePath $Heartbeat -Encoding ascii -Force

    # ---- rotate --------------------------------------------------------------
    foreach ($name in 'crypto-session.log') {
        $file = Join-Path $Repo "data\$name"
        if ((Test-Path $file) -and ((Get-Item $file).Length -gt 5MB)) {
            Move-Item $file "$file.1" -Force
            Say "rotated $name at 5MB"
        }
    }

    # ---- stop when the experiment is over -------------------------------------
    # Shares run-until.txt with the equity loop: one experiment, one end date.
    # Exiting here ends the whole worker process. It does not touch the
    # scheduled task - the watchdog would otherwise just relaunch it within a
    # minute - so it also drops a stop file the watchdog checks before relaunch.
    $UntilFile = Join-Path $Repo 'data\run-until.txt'
    if (Test-Path $UntilFile) {
        $Until = (Get-Content $UntilFile -Raw).Trim()
        if ($Until -notmatch '^\d{4}-\d{2}-\d{2}$') {
            Say "run-until.txt is not YYYY-MM-DD ('$Until'); ignoring it"
        }
        elseif ((Get-Date).ToString('yyyy-MM-dd') -gt $Until) {
            Say "run-until $Until has passed; stopping the crypto worker for good"
            Say 'NOTE: any open crypto position keeps its GTC stop-limit at Alpaca.'
            'stopped' | Out-File -FilePath (Join-Path $Repo 'data\crypto-loop.stopped') -Encoding ascii -Force
            Remove-Item $PidFile -ErrorAction SilentlyContinue
            exit 0
        }
    }

    # ---- refresh the crypto price files ---------------------------------------
    # The mean-reversion rule reads DAILY bars from data/ via daily_bars(), and
    # this loop is the only thing running at 3am on a Sunday. Without a refresh
    # here the crypto files would go stale the moment the equity session ends on
    # Friday, and every weekend cycle would evaluate Friday's prices as though
    # they were live. The staleness check is a cheap mtime comparison, so doing
    # it every cycle (now every 30s, not every 15min) costs nothing - the actual
    # network fetch still only fires once every 6 hours per symbol.
    $Refresh = @'
import time
from pathlib import Path
from event_aware_trader.data import fetch_alpaca_crypto_bars, price_file, save_bars
from event_aware_trader.strategy import CRYPTO_UNIVERSE

STALE_SECONDS = 6 * 3600      # tighter than the equity loop's 20h: crypto moves
now = time.time()             # overnight and there is no close to wait for
refreshed = failed = 0
for symbol in CRYPTO_UNIVERSE:
    path = price_file(Path("data"), symbol)
    if path.exists() and (now - path.stat().st_mtime) <= STALE_SECONDS:
        continue
    try:
        save_bars(path, fetch_alpaca_crypto_bars(symbol))
        refreshed += 1
    except Exception as error:
        failed += 1
        print("crypto refresh failed for {0}: {1}".format(symbol, error))
if refreshed or failed:
    print("refreshed {0} crypto files, {1} failed".format(refreshed, failed))
'@
    $Refresh | & $Python - 2>&1 | Out-File -FilePath $Log -Append -Encoding utf8
    if ($LASTEXITCODE -ne 0) {
        Say 'crypto price refresh failed (non-fatal; the cycle will use what is on disk)'
    }

    # ---- no preflight here, deliberately --------------------------------------
    # preflight checks price-file freshness across the WHOLE universe, and
    # equity files are correctly stale at 3am on a Sunday. Running it here would
    # block every out-of-hours crypto cycle for a reason that has nothing to do
    # with crypto. The checks that do matter - credentials present, paper
    # endpoint, CLI on disk - are made by the watchdog before launch and by the
    # broker on every call.

    # ---- trade -----------------------------------------------------------------
    # THE SLEEVE, not `autotrade --asset-class crypto`.
    #
    # This ran the mean-reversion rule over the ten crypto pairs until 2026-09-12.
    # That is the strategy this project REJECTED, on 2026-09-08, after testing
    # mean reversion, trend following, breakout and cross-sectional momentum on
    # both Alpaca history and a decade of verified Yahoo data. Every family lost
    # money, and the reason was structural rather than a bad parameter: sizing by
    # risk budget over stop distance gives an asset with 4-13% daily range a
    # position too small to matter. On top of that the shipped rule cannot fire on
    # crypto at all - the measured result was ZERO trades - so scheduling it would
    # have bought either losses or nothing.
    #
    # What was validated is the ALLOCATION: hold BTC while BTC is above its own
    # 100-day average, nothing otherwise, at 5% of equity. Correlation with the
    # equity book is +0.035, which is what lets a 42%-volatility asset be added
    # while drawdown goes DOWN (-14.1% to -13.5%) rather than up.
    #
    # Sub-minute polling does not make this allocation trade more, or better - a
    # 100-day trend flips at most a few times a month. What it buys is a faster
    # reaction to freed-up equity cash (seconds instead of up to 15 minutes) and
    # nothing else; the target-based `plan()` recomputes from scratch each cycle,
    # so running it 30x more often is idempotent, not 30x more active.
    #
    # The two must never both run. The sleeve holds BTC as an allocation with no
    # stop; the autotrade crypto path would see that position, rest a protective
    # stop under it, and exit it on its own rule - two books fighting over one
    # holding.
    $SleeveArgs = @((Join-Path $Repo 'scripts/run_crypto_sleeve.py'))
    if ($Live) { $SleeveArgs += '--live' }
    & $Python @SleeveArgs 2>&1 | Out-File -FilePath $Log -Append -Encoding utf8
    if ($LASTEXITCODE -ne 0) { Say 'crypto sleeve returned non-zero' }

    Start-Sleep -Seconds $IntervalSeconds
}
