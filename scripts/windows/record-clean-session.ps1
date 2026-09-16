# Run the Phase 4 clean-session recorder once, after the US close.
#
# Read-only with respect to trading: it submits no orders and writes nothing
# the strategy reads. It appends at most one row to the clean record, and
# refuses far more often than it records - before the embargo expires, on a
# session already recorded, on a fingerprint change, or when the loop left no
# completed run for the day.
#
# No API key is written here. The recorder reads APCA_API_KEY_ID and
# APCA_API_SECRET_KEY from the user environment at run time, so neither this
# file nor the task definition holds a secret.

$ErrorActionPreference = 'Continue'

$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Log  = Join-Path $Repo 'data\clean-recorder.log'
$Py   = Join-Path $Repo '.venv\Scripts\python.exe'
if (-not (Test-Path $Py)) { $Py = 'python' }

New-Item -ItemType Directory -Force -Path (Join-Path $Repo 'data') | Out-Null

$Stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
Add-Content -Path $Log -Value "--- $Stamp ---" -Encoding utf8

$env:PYTHONPATH = Join-Path $Repo 'src'
$Output = & $Py (Join-Path $Repo 'scripts\record_clean_session.py') 2>&1
$Code = $LASTEXITCODE

$Output | ForEach-Object { Add-Content -Path $Log -Value $_ -Encoding utf8 }
Add-Content -Path $Log -Value "exit $Code" -Encoding utf8

# A non-zero exit is normal for most of this phase: the embargo has not
# expired. It is logged rather than raised so the scheduler does not mark the
# task failed every weekday for a month.
exit 0
