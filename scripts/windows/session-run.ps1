# One scheduled cycle during the US session, for Windows 11.
#
# This is a port of scripts/session-run.sh. The Python is identical on both
# platforms - only the shell and the scheduler differ. Keep the two in step:
# every behaviour below exists because something went wrong without it, and
# the reasons are recorded in the bash original.
#
# Usage:  powershell -ExecutionPolicy Bypass -File session-run.ps1 [-Live]

param([switch]$Live)

$ErrorActionPreference = 'Continue'   # a bad cycle must not kill the schedule

$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Python = Join-Path $Repo '.venv\Scripts\python.exe'
$Cli    = Join-Path $Repo '.venv\Scripts\event-aware-trader.exe'
$Log    = Join-Path $Repo 'data\session.log'
# PREFLIGHT ONLY. The trading cycle below deliberately passes NEITHER
# --interval NOR --period, so autotrade takes the CLI defaults (1d, 2y)
# and its effective configuration hashes to the published frozen
# fingerprint da22011e... Passing 15m here made the live config hash to
# 569a8da7... instead, so every clean-OOS observation would have been
# stamped with a configuration the account was not running.
#
# Changing ONLY --interval would have been far worse than leaving it:
# --period 1mo maps to 35 days, which at 1d is about 24 bars against
# strategy.minimum_history of 50 - a threshold that does NOT scale with
# interval. Every symbol would then fail three silent `continue` gates
# (entry, exit management, order placement) and the bot would trade
# nothing without saying so. Both flags had to go together.
#
# Measured before the change, not assumed (scripts/preoos_interval_equivalence.py,
# 2026-09-21): 230/230 symbols passed the gate under BOTH configurations,
# no symbol had fewer than the rule's 215 daily bars, and the candidate
# set was identical - BAC, CVS, KRE, RTX, UNP under each.
$Interval = '15m'

# What the paper account was funded with, so `record` can report a real
# total return instead of 0.000%. Alpaca's JNLC activity is the authority;
# change this only if the account is refunded to a different figure.
$StartingEquity = 100000

# Trade only a slice of the account. The slice compounds: it is this base
# plus every dollar made or lost since $StartingEquity, so profits enlarge
# the book and losses shrink it, with no further intervention.
#
# The cost is coverage. Whole shares are required for a broker-side stop,
# so at a $1,000 slice the 0.5% risk budget floors to zero shares on the
# expensive half of the universe: 48 of 120 symbols remain tradeable,
# median position about $128. Set to $null to trade the whole account.
$CapitalBase = $null

# PowerShell 5.1's > is Out-File with Unicode (UTF-16LE) encoding. Every
# JSON file written that way is unreadable to json.load and displays as
# spaced-out gibberish to anything expecting UTF-8 - which is exactly what
# happened to data\last-preflight.json. -Encoding utf8 is not the fix
# either: in 5.1 it prepends a BOM, and json.loads rejects that as a syntax
# error on line one. Write the bytes explicitly.
function Save-Utf8 {
    param([object]$Content, [string]$Path)
    $text = (@($Content) | ForEach-Object { "$_" }) -join [Environment]::NewLine
    [System.IO.File]::WriteAllText(
        $Path, $text + [Environment]::NewLine,
        (New-Object System.Text.UTF8Encoding $false))
}

Set-Location $Repo
New-Item -ItemType Directory -Force -Path (Join-Path $Repo 'data') | Out-Null

function Stamp { (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }
function Say([string]$Message) { "[$(Stamp)] $Message" | Out-File -FilePath $Log -Append -Encoding utf8 }

if (-not (Test-Path $Cli)) {
    Say "FATAL: $Cli not found. Create the venv and run 'pip install -e .' first."
    exit 1
}

# Credentials come from the USER environment, set once by setup-keys.ps1.
# Nothing is written into the task definition or into this repo.
if (-not $env:APCA_API_KEY_ID -or -not $env:APCA_API_SECRET_KEY) {
    Say 'FATAL: APCA_API_KEY_ID / APCA_API_SECRET_KEY are not set. Run scripts\windows\setup-keys.ps1'
    exit 1
}

# ---- 0. rotate logs ---------------------------------------------------------
# ~1,100 runs over two months, each appending a full JSON result.
foreach ($name in 'session.log', 'autotrade-audit.jsonl', 'scheduler.log', 'scheduler.err') {
    $file = Join-Path $Repo "data\$name"
    if ((Test-Path $file) -and ((Get-Item $file).Length -gt 5MB)) {
        Move-Item $file "$file.1" -Force
        Say "rotated $name at 5MB"
    }
}

# ---- 1. stop when the experiment is over ------------------------------------
$UntilFile = Join-Path $Repo 'data\run-until.txt'
if (Test-Path $UntilFile) {
    $Until = (Get-Content $UntilFile -Raw).Trim()
    # A string compare with no format check ended the experiment on cycle one
    # when the file was empty. Validate the shape before trusting it.
    if ($Until -notmatch '^\d{4}-\d{2}-\d{2}$') {
        Say "run-until.txt is not YYYY-MM-DD ('$Until'); ignoring it"
    }
    elseif ((Get-Date).ToString('yyyy-MM-dd') -gt $Until) {
        Say "run-until $Until has passed; winding down"
        $final = & $Cli record --audit-log data\autotrade-audit.jsonl `
            --account $StartingEquity 2>&1
        Save-Utf8 $final (Join-Path $Repo 'data\FINAL-RECORD.json')
        Say 'final record written to data\FINAL-RECORD.json'
        Say 'NOTE: any open position stays open at Alpaca, and it keeps its stop.'
        Say '      Each cycle rests a standalone GTC sell-stop under every position,'
        Say '      so protection survives both the close and this scheduler stopping.'
        Say '      What stops is the RATCHET: nothing raises that stop behind a'
        Say '      rising price any more, so it sits at its last level until filled.'
        Say '      Close it in TradingView if you want to be flat.'
        Unregister-ScheduledTask -TaskName 'EventAwareTrader' -Confirm:$false `
            -ErrorAction SilentlyContinue
        exit 0
    }
}

# ---- 2. refresh the daily CSVs preflight reads ------------------------------
# One batched call, not one process per symbol. The per-symbol version sat for
# 35 minutes once Yahoo began answering 429, and a cycle that overruns its slot
# makes the scheduler skip the ones behind it. Bounded by budget_seconds.
$Refresh = @'
import time
from pathlib import Path
from event_aware_trader.data import (
    fetch_alpaca_crypto_bars, fetch_alpaca_equity_bars, price_file, save_bars)
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto

STALE_SECONDS = 20 * 3600
now = time.time()
stale = []
for symbol in sorted(DEFAULT_UNIVERSE):
    path = price_file(Path("data"), symbol)
    if not path.exists() or (now - path.stat().st_mtime) > STALE_SECONDS:
        stale.append(symbol)

# Alpaca for both, which is also the venue the orders go to. Yahoo was the
# equity source and was replaced on 2026-09-06 for three measured reasons: it
# served partial sessions (all 59 files with an incoherent final bar were
# Yahoo's, all 110 Alpaca ones were clean), it served unadjusted splits (a
# 9.92x fake crash in AVGO), and it had stopped answering at all. Alpaca also
# takes a hundred symbols per request instead of one, so the rate-limit
# batching Yahoo needed is gone.
equities = [s for s in stale if not is_crypto(s)]
crypto = [s for s in stale if is_crypto(s)]

refreshed = failed = 0
if equities:
    try:
        bars = fetch_alpaca_equity_bars(equities, days=800)
        for symbol, series in bars.items():
            # A short series would overwrite good history with a stub and
            # push the symbol below the rule's minimum_history.
            if len(series) >= 260:
                save_bars(price_file(Path("data"), symbol), series)
                refreshed += 1
        failed += len(equities) - refreshed
    except Exception as error:
        failed += len(equities)
        print("equity refresh failed: {0}".format(error))
for symbol in crypto:
    try:
        save_bars(price_file(Path("data"), symbol),
                  fetch_alpaca_crypto_bars(symbol))
        refreshed += 1
    except Exception as error:
        failed += 1
        print("crypto refresh failed for {0}: {1}".format(symbol, error))
if stale:
    print("refreshed {0} of {1} stale daily files, {2} failed".format(
        refreshed, len(stale), failed))
'@
$Refresh | & $Python - 2>&1 | Out-File -FilePath $Log -Append -Encoding utf8
if ($LASTEXITCODE -ne 0) {
    Say 'daily CSV refresh failed (non-fatal; autotrade fetches its own bars)'
}

# ---- 3. refuse to trade if preflight says it is not safe --------------------
$preflight = & $Cli preflight --interval $Interval --max-age-days 4 2>&1
Save-Utf8 $preflight (Join-Path $Repo 'data\last-preflight.json')
if ($LASTEXITCODE -ne 0) {
    Say 'PREFLIGHT FAILED - no trading this cycle. See data\last-preflight.json'
    exit 0
}

# ---- 4. trade ---------------------------------------------------------------
# --asset-class equity, so this loop never touches a crypto position or
# cancels a crypto stop. The crypto loop in session-run-crypto.ps1 is
# confined the same way. Two schedules, one account, no overlap.
#
# NO --interval AND NO --period. The CLI defaults (1d, 2y) are the
# fingerprinted configuration; see the note beside $Interval above.
$TradeArgs = @('autotrade', '--asset-class', 'equity')
if ($null -ne $CapitalBase) {
    $TradeArgs += @('--capital-base', $CapitalBase,
                    '--capital-baseline', $StartingEquity)
}
if ($Live) { $TradeArgs += '--live' }
& $Cli @TradeArgs 2>&1 | Out-File -FilePath $Log -Append -Encoding utf8
if ($LASTEXITCODE -ne 0) { Say 'autotrade returned non-zero' }

# ---- 4a. record news for subsequent decisions, point-in-time ---------------
# Keep this network fetch after the current orders so it cannot delay a
# decision inside the narrow end-of-session entry window. The next cycle's
# audit can use only headlines already fetched by its decision timestamp.
# Headlines are review context and do not affect the strategy or its orders.
& $Python (Join-Path $Repo 'scripts/record_news.py') 2>&1 |
    Out-File -FilePath $Log -Append -Encoding utf8
if ($LASTEXITCODE -ne 0) { Say 'news recording failed (non-fatal)' }

# ---- 4b. refresh the TradingView levels file -------------------------------
# Pine Script cannot read this machine, so the levels a chart shows have to be
# baked into the indicator and regenerated whenever a position opens or
# closes. Non-fatal on purpose: a charting convenience must never be able to
# stop the trading loop.
try {
    & $Python (Join-Path $Repo 'scripts/tradingview_levels.py') 2>&1 |
        Out-File -FilePath $Log -Append -Encoding utf8
} catch {
    Say 'tradingview level refresh failed (non-fatal; charting only)'
}

# ---- 5. at the close: report the day, then learn from it --------------------
# Alpaca's clock decides which cycle is the last one, rather than assuming.
# This MUST be the venv interpreter: on macOS this line once called the system
# python, which has never had the package installed, so the import failed, the
# except swallowed it, and the daily report never ran on any day.
$CloseCheck = @'
from datetime import datetime, timezone
import sys
try:
    from event_aware_trader.broker import AlpacaPaperBroker, BrokerConfig
    c = AlpacaPaperBroker(BrokerConfig.from_environment()).clock()
    nc = datetime.fromisoformat(str(c["next_close"]).replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    print("yes" if (nc - now).total_seconds() <= 960 else "no")
except Exception as exc:
    print("close-check failed: {0}: {1}".format(type(exc).__name__, exc), file=sys.stderr)
    print("no")
'@
# Do NOT just take the last line of a merged stream. If the check throws, it
# prints a diagnostic on stderr AND "no" on stdout, and the interleaving of a
# merged stream is not guaranteed - so "the last line" could be the error text,
# which is neither "yes" nor "no" and would silently skip the daily report.
# That exact class of bug hid the report on macOS for the whole deployment.
# Select the answer explicitly and log everything else.
$CloseOut = $CloseCheck | & $Python - 2>&1 | ForEach-Object { $_.ToString() }
$CloseOut | Where-Object { $_ -notmatch '^(yes|no)$' } |
    Out-File -FilePath $Log -Append -Encoding utf8
$IsLast = $CloseOut | Where-Object { $_ -match '^(yes|no)$' } | Select-Object -Last 1
if (-not $IsLast) { Say 'close-check produced no yes/no answer; treating as not-last' }

if ($IsLast -eq 'yes') {
    Say 'session closing - writing the daily report'
    & $Cli daily-report --out (Join-Path $Repo 'data\DAILY-REPORT.json') 2>&1 |
        Out-File -FilePath $Log -Append -Encoding utf8
    $ReportDir = Join-Path $Repo 'data\reports'
    New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
    Copy-Item (Join-Path $Repo 'data\DAILY-REPORT.json') `
        (Join-Path $ReportDir ("{0}.json" -f (Get-Date).ToString('yyyy-MM-dd'))) `
        -ErrorAction SilentlyContinue
    # The account against SPY's TOTAL return over the identical window, every
    # session close. Flagged NOT A FINDING until sixty sessions. Print-only:
    # a failure here cannot affect a trade. Forward slashes in the path, as
    # everywhere a backslash once became a carriage return.
    Say 'benchmark: the account against SPY total return'
    $Bench = & (Join-Path $Repo '.venv\Scripts\python.exe') (Join-Path $Repo 'scripts/benchmark.py') 2>&1
    $Bench | Out-File -FilePath (Join-Path $Repo 'data\BENCHMARK.txt') -Encoding utf8
    $Bench | Out-File -FilePath $Log -Append -Encoding utf8
    Say 'retraining on the record so far'
    & $Cli retrain 2>&1 | Out-File -FilePath $Log -Append -Encoding utf8
    # EXP-0055: the adaptive exits' learning rule. It runs after trading has
    # ended for the day, decides for itself whether an evaluation is due (at
    # most every 5 sessions, and only on 20+ finished trades), and writes
    # data\adaptive-exits.json. A failure here cannot affect a trade.
    Say 'adaptive exits: learning check'
    & $Cli adaptive-exits --learn 2>&1 | Out-File -FilePath $Log -Append -Encoding utf8
}

# ---- 6. weekly: the statistical verdict -------------------------------------
# Gate on the ISO week alone, so it fires on the first Friday cycle whatever
# the local hour happens to be.
if ((Get-Date).DayOfWeek -eq 'Friday') {
    $Marker = Join-Path $Repo 'data\.last-train'
    $Cal = [System.Globalization.CultureInfo]::InvariantCulture.Calendar
    $Week = '{0}-{1:00}' -f (Get-Date).Year, $Cal.GetWeekOfYear(
        (Get-Date), [System.Globalization.CalendarWeekRule]::FirstFourDayWeek,
        [System.DayOfWeek]::Monday)
    $Seen = if (Test-Path $Marker) { (Get-Content $Marker -Raw).Trim() } else { '' }
    if ($Seen -ne $Week) {
        Say 'weekly retrain'
        & $Cli learn --data-dir data --pine tradingview\learned_filter.pine 2>&1 |
            Out-File -FilePath $Log -Append -Encoding utf8
        $weekly = & $Cli record --audit-log data\autotrade-audit.jsonl `
            --account $StartingEquity 2>&1
        Save-Utf8 $weekly (Join-Path $Repo 'data\WEEKLY-RECORD.json')
        $Week | Out-File -FilePath $Marker -Encoding ascii -NoNewline
        Say 'weekly record written to data\WEEKLY-RECORD.json'
    }
}
