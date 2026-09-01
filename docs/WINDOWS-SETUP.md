# Running it on Windows 11

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

That stops the scheduler. It does **not** close positions — their stops stay
resting at Alpaca. Close them in TradingView if you want to be flat.

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

## One caveat I can't remove

**These Windows scripts have not been executed on a Windows machine.** I wrote
them on the Mac and cannot run PowerShell or Task Scheduler here to test them.
The Python underneath is the same code that runs today and is covered by 279
passing tests — the risk is in the five `.ps1` files, not in the bot.

Step 5 is the check. If `Start-ScheduledTask` produces a `"status": "ok"` block
in `session.log`, everything is wired correctly. If it doesn't, send me the
output and the error will be in one of those five files.
