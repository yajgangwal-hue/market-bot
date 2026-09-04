# Running it on Windows 11

## Setup

There is no all-in-one bootstrap script. There was, and Windows Defender
deleted it: a script that installs software with winget, changes power
settings and registers a scheduled task matches its heuristics for malware,
and it was quarantined so thoroughly that `git checkout` could not recreate
the file (*Permission denied*). Fighting that is not worth it - the steps
below are the same work, and Defender leaves them alone.

Run everything in **PowerShell as Administrator**. Paste each line exactly,
with nothing after the final character: a trailing backslash on the winget
line silently skipped the Python install once and every later step then failed
for what looked like a different reason.

**1. Git and Python**

```powershell
winget install -e --id Git.Git
```

```powershell
winget install -e --id Python.Python.3.11
```

**2. Get the code**

```powershell
git clone https://github.com/yajgangwal-hue/market-bot.git C:\market-bot
```

If `git` is not recognized, the install worked but this window is stale -
PowerShell reads PATH only at startup. Close it, open a new Administrator
window, and continue.

**3. Locate the real Python**

Do NOT rely on `python` being on PATH. Windows 11 ships stub launchers named
`python.exe` in `WindowsApps` that only advertise the Microsoft Store, and
they sit ahead of real installs. Find the actual interpreter and use its full
path:

```powershell
$py = (Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe","C:\Program Files\Python3*\python.exe" -EA SilentlyContinue | Select-Object -First 1).FullName; $py; & $py --version
```

That must print a path and `Python 3.11.x`. Anything else means Python is not
installed - go back to step 1.

**4. Build the environment** (2-4 minutes)

```powershell
cd C:\market-bot; & $py -m venv .venv; .\.venv\Scripts\python.exe -m pip install -e ".[ai]"
```

From here on everything uses `.\.venv\Scripts\...`, which are real file
paths, so PATH and the stub stop mattering.

**5. Check the code before trusting it with an account**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -q
```

You want `OK` and 279 tests.

**6. Your Alpaca keys** - use the same paper keys as the Mac, so both machines
see account `PA30S46B79V8` and the balance carries over.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\setup-keys.ps1
```

**7. Start it**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install-session.ps1 -Months 2 -Live
```

**8. Prove it works now, rather than finding out at the open**

```powershell
Start-ScheduledTask -TaskName EventAwareTrader; Start-Sleep 60; Get-Content .\data\session.log -Tail 20
```

You want a block ending `"status": "ok"`.

**9. Stop the machine sleeping.** Settings > System > Power > *When plugged in,
put my device to sleep after* > **Never**. A sleeping machine runs nothing, and
it looks exactly like a market with no signals.

---

Everything below is the manual version, and the reasoning, if you want it.

---

The point of this is that your Mac no longer has to stay awake. A Windows
desktop that's on all day runs the bot instead.

**The Python is identical on both machines.** Only the shell scripts and the
scheduler differ, and Windows versions of those live in `scripts\windows\`.

> **Run it on ONE computer at a time.** Both machines would trade the same
> Alpaca account, and neither knows about the other's positions — you would get
> doubled entries and stops fighting each other. Turn the Mac off (Step 6)
> before starting Windows.

---

## Step 1 — Install Python

Get **Python 3.11** from [python.org/downloads](https://www.python.org/downloads/).

On the first screen of the installer, tick **"Add python.exe to PATH"** before
clicking Install. That one checkbox causes most of the problems people hit
later.

Check it worked — open **PowerShell** (Start menu, type "PowerShell") and run:

```powershell
python --version
```

You should see `Python 3.11.x`. If you see nothing or an error, the PATH box
wasn't ticked — re-run the installer and choose Modify.

---

## Step 2 — Install Git, then get the files

Get **Git for Windows** from [git-scm.com/download/win](https://git-scm.com/download/win)
and accept every default.

Then in PowerShell:

```powershell
cd C:\
git clone https://github.com/yajgangwal-hue/market-bot.git
cd C:\market-bot
```

> Use `C:\market-bot`. **Do not put it in OneDrive** — OneDrive syncs files
> while they're being written and can swap them for placeholders that block
> until downloaded, which will corrupt the bot's state file. The installer
> refuses to run from a OneDrive path for this reason.

The repo is private, so Git will ask you to sign in to GitHub the first time.

---

## Step 3 — Build the environment

```powershell
cd C:\market-bot
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -e ".[ai]"
```

That last line takes a few minutes — it's downloading pandas, numpy and
scikit-learn.

Check it:

```powershell
.\.venv\Scripts\event-aware-trader.exe --help
```

---

## Step 4 — Your Alpaca keys

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\setup-keys.ps1
```

It asks for your Key ID and Secret and stores them in your **Windows user
environment** — not in the project folder, so they can't reach GitHub.

Use the **same paper keys** as the Mac. Both machines then see the same
account, `PA30S46B79V8`, and your balance and history carry over untouched.

> The secret is invisible while you paste it. That's normal. The script prints
> the length back so you can tell the paste registered — paste it **once**.

---

## Step 5 — Run the tests, then start it

Always run the tests first on a new machine. They take about 20 seconds and
catch a broken install immediately:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -q
```

You want `OK` and 279 tests. Then start it:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install-session.ps1 -Months 2 -Live
```

Drop `-Live` if you want it to think without placing orders for a day first.

Prove it works right now rather than waiting until tomorrow:

```powershell
Start-ScheduledTask -TaskName EventAwareTrader
Get-Content C:\market-bot\data\session.log -Tail 20
```

You want a block ending `"status": "ok"`. If you see `FATAL` about API keys,
close PowerShell and open a new one — environment variables only load at
startup.

---

## Step 6 — Turn the Mac off

On the Mac, so the two don't trade the same account:

```bash
launchctl unload ~/Library/LaunchAgents/com.eventawaretrader.session.plist
```

Any position already open stays open at Alpaca with its stop resting there. The
Windows machine picks it up on its next cycle, because both read the same
account.

---

## Checking on it

Right-click `scripts\windows\check-results.ps1` → **Run with PowerShell**.

It shows whether the task is alive *first*, then the account, then the record.
That order is deliberate: a bot that never ran and a genuinely quiet day
produce the same empty log, and on the Mac that ambiguity hid a dead scheduler
for a full trading day.

| What you see | What it means |
|---|---|
| `last result : 0` | Healthy |
| `last result : 267011` | Task never ran |
| `state : Ready`, `next run` in the future | Normal between cycles |
| `Scheduled task NOT installed` | Step 5 didn't finish |

## Stopping it

Right-click `scripts\windows\stop-everything.ps1` → **Run with PowerShell**.

That stops the scheduler. It does **not** close positions — but it does leave
them protected.

> Every cycle rests a standalone **GTC** sell-stop under each position. A GTC
> order survives the close and survives this scheduler being unregistered, so
> the stop stays at Alpaca until it fills or is replaced.
>
> What stops is the **ratchet**. That stop is only raised behind a rising price
> by a running cycle, so once the scheduler is off it freezes at its last
> level. You are protected, not managed.
>
> This was not always true. Before the fix, entries relied on the bracket
> alone, whose legs are `time_in_force=day` — the take-profit expired at the
> bell and OCO cancelled the stop with it. Measured 2026-09-01, both legs gone
> at 16:01:38 ET and two positions overnight with nothing behind them.
>
> **Close positions yourself in TradingView if you want to be flat.**

---

## Sleep settings

The whole reason for moving is that the machine stays on. Set:

**Settings → System → Power → Screen and sleep → "When plugged in, put my
device to sleep after" → Never.**

Leaving the screen turning off is fine. Sleep is what stops the bot.

---

## Differences from the Mac worth knowing

| | macOS | Windows |
|---|---|---|
| Scheduler | launchd, 130 calendar entries | Task Scheduler, one task repeating every 15 min |
| Keys stored in | `~/.zprofile` | Windows user environment |
| Protected folders | Desktop/Documents/Downloads are blocked for background jobs | No such restriction — but avoid OneDrive |
| Hung cycle | had to be bounded in code | also killed by the task's 14-minute limit |

That last row is a genuine improvement. Task Scheduler can enforce a time
limit per run and refuse to start a second copy, so a hung cycle gets killed
before the next one is due. On macOS a single stuck cycle silently ate 15 of
26 slots in one session, which is the failure that made this port worth doing.

---

## The caveat that used to be here is gone

These scripts were written on the Mac and shipped untested. They have now run:
on 2026-09-03 the Windows task completed a full session — 26 cycles, every one
`"status": "ok"`, `LastTaskResult 0`, zero missed runs. Step 5 remains the
check to run on any fresh machine.

---

## Moving between machines loses the trade history

The account lives at Alpaca, so **balances and open positions carry over
untouched**, and TradingView shows the same history from either computer. The
audit log does not: `data\autotrade-audit.jsonl` is local to whichever machine
placed the orders, and `record` is computed from it. A freshly moved machine
therefore reports `NO_TRADES_YET` over an account that visibly holds closed
trades, and every statistic is drawn from a fraction of the evidence.

Rebuild it from the broker after any move:

```powershell
.\.venv\Scripts\event-aware-trader.exe backfill-audit --dry-run
```

```powershell
.\.venv\Scripts\event-aware-trader.exe backfill-audit
```

It reads Alpaca's fill activities, cuts them into round trips where the
position actually opened and flattened — not per order, since one exit arrives
as several partial fills — and subtracts the REG/TAF/CAT fees so the total
agrees with account equity rather than being about a dollar optimistic. The
missing rows are merged in timestamp order. Re-running it is safe: a trade the
log already covers is skipped, not duplicated.

---


## If something goes wrong

**`'git' is not recognized`** (or `'python' is not recognized`) right after
installing it. The install worked; the window is stale. PowerShell reads PATH
only at startup. Either run the refresh line above, or close PowerShell and
open a new one as Administrator. This is the single most common stumble in
this whole setup.

**`Python was not found; run without arguments to install from the Microsoft
Store`.** That `python.exe` is not Python. Windows 11 ships stub launchers in
`%LOCALAPPDATA%\Microsoft\WindowsApps` whose only job is to advertise the
Store, and they sit ahead of real installs on PATH. bootstrap.ps1 now ignores
anything under `WindowsApps` and looks for a real interpreter instead, so
update the repo (`cd C:\market-bot; git pull`) and run it again. You can also
switch the stubs off under **Settings > Apps > Advanced app settings > App
execution aliases**, but you do not need to.

**`git clone` asks for a username and password and rejects them.** GitHub
stopped accepting account passwords over HTTPS. Let the browser sign-in window
handle it, or install GitHub CLI (`winget install GitHub.cli`), run `gh auth
login`, and clone again.

**`FATAL: APCA_API_KEY_ID ... are not set`** in session.log. The keys were
saved to your user environment but the running window predates them. Close
PowerShell, open a new one, and run bootstrap again - it skips everything
already done.

**The task shows `last result : 267011`.** That means it has never actually
run. Start it once by hand with `Start-ScheduledTask -TaskName
EventAwareTrader` and read `data\session.log`.
