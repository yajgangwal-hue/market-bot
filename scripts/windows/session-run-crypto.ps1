# One crypto cycle. Crypto trades continuously, so this runs around the clock
# rather than inside the US equity session.
#
# It is a SEPARATE loop from session-run.ps1 on purpose, against the same
# account. The two must not touch each other's positions: a crypto cycle that
# managed an equity position would evaluate it on stale bars at 3am, and worse,
# the protective-stop reconciler cancels any resting sell it does not recognise
# - so it would strip the GTC stop off a stock while the market that could
# replace it is shut. `--asset-class crypto` confines every read, exit and
# re-protection to crypto, and equity cycles are confined the same way.
#
# Usage:  powershell -ExecutionPolicy Bypass -File session-run-crypto.ps1 [-Live]

param([switch]$Live)

$ErrorActionPreference = 'Continue'   # a bad cycle must not kill the schedule

$Repo   = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Python = Join-Path $Repo '.venv\Scripts\python.exe'
$Cli    = Join-Path $Repo '.venv\Scripts\event-aware-trader.exe'
$Log    = Join-Path $Repo 'data\crypto-session.log'

# Separate state file, not a separate audit log. State is read-modify-written
# whole, so two loops sharing one file would lose each other's updates; the
# audit log is append-only and is the trade record, so both write to it.
$StateFile = 'data\autotrade-state-crypto.json'

Set-Location $Repo
New-Item -ItemType Directory -Force -Path (Join-Path $Repo 'data') | Out-Null

function Stamp { (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }
function Say([string]$Message) { "[$(Stamp)] $Message" | Out-File -FilePath $Log -Append -Encoding utf8 }

if (-not (Test-Path $Cli)) {
    Say "FATAL: $Cli not found. Create the venv and run 'pip install -e .' first."
    exit 1
}
if (-not $env:APCA_API_KEY_ID -or -not $env:APCA_API_SECRET_KEY) {
    Say 'FATAL: APCA_API_KEY_ID / APCA_API_SECRET_KEY are not set. Run scripts\windows\setup-keys.ps1'
    exit 1
}

# ---- rotate ------------------------------------------------------------------
foreach ($name in 'crypto-session.log') {
    $file = Join-Path $Repo "data\$name"
    if ((Test-Path $file) -and ((Get-Item $file).Length -gt 5MB)) {
        Move-Item $file "$file.1" -Force
        Say "rotated $name at 5MB"
    }
}

# ---- stop when the experiment is over ----------------------------------------
# Shares run-until.txt with the equity loop: one experiment, one end date.
$UntilFile = Join-Path $Repo 'data\run-until.txt'
if (Test-Path $UntilFile) {
    $Until = (Get-Content $UntilFile -Raw).Trim()
    if ($Until -notmatch '^\d{4}-\d{2}-\d{2}$') {
        Say "run-until.txt is not YYYY-MM-DD ('$Until'); ignoring it"
    }
    elseif ((Get-Date).ToString('yyyy-MM-dd') -gt $Until) {
        Say "run-until $Until has passed; winding down the crypto loop"
        Say 'NOTE: any open crypto position keeps its GTC stop-limit at Alpaca.'
        Unregister-ScheduledTask -TaskName 'EventAwareTraderCrypto' -Confirm:$false `
            -ErrorAction SilentlyContinue
        exit 0
    }
}

# ---- refresh the crypto price files -----------------------------------------
# The mean-reversion rule reads DAILY bars from data/ via daily_bars(), and
# this loop is the only thing running at 3am on a Sunday. Without a refresh
# here the crypto files would go stale the moment the equity session ends on
# Friday, and every weekend cycle would evaluate Friday's prices as though they
# were live - entering on a level that no longer exists and sizing a stop
# against it. The equity loop refreshes them on weekdays; this covers the rest.
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

# ---- no preflight here, deliberately -----------------------------------------
# preflight checks price-file freshness across the WHOLE universe, and equity
# files are correctly stale at 3am on a Sunday. Running it here would block
# every out-of-hours crypto cycle for a reason that has nothing to do with
# crypto. The checks that do matter - credentials present, paper endpoint, CLI
# on disk - are made above and by the broker itself on every call.

# ---- trade -------------------------------------------------------------------
# Interval and period describe the cycle's own bars. The mean-reversion rule
# reads DAILY bars from data/ regardless, via daily_bars(), because its numbers
# are counted in days.
$TradeArgs = @('autotrade', '--asset-class', 'crypto',
               '--interval', '1d', '--period', '2y',
               '--state-file', $StateFile)
if ($Live) { $TradeArgs += '--live' }
& $Cli @TradeArgs 2>&1 | Out-File -FilePath $Log -Append -Encoding utf8
if ($LASTEXITCODE -ne 0) { Say 'crypto autotrade returned non-zero' }
