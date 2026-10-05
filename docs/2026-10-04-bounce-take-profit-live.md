# Implemented: take profit at the bounce price, the entry-date fix, and no more flashing window

*2026-10-04. The owner's instructions:*

- *"ok now implement everything into the bot";*
- *"also on my computer the terminal in the same time interval just flashes
  on my screen so stop that from happening".*

*Live from the next equity cycle (Monday 2026-10-05). Nothing is committed.
No broker call was made: the exposed key is still unrotated.*

## What "everything" covered, and what it did not

| Item | Done? | Why |
|---|---|---|
| Take profit at the bounce price (EXP-0057) | **yes** | the one research result that applies to the live bot (H-0038, then a portfolio check, below) |
| Entry-date fix (REM-0010) | **yes** | a defect: the 20-session time limit fired one session early |
| No flashing window | **yes** | the crypto watchdog opened a visible console every minute |
| Day-trading systems (H-0032–H-0036), shorting (H-0027–H-0029), +0.5%/−0.2% (H-0030), all-in (H-0031) | **no** | every one lost money or failed its sealed test; putting them live would cost money |
| Rotating the Alpaca key | **no** | a credential; the owner does it |

## 1. EXP-0057: the take profit is the bounce price

**What changed:**

- **The take profit is now the bounce price.** That is the close that would
  put RSI(14) at 60 — exactly where the strategy's own "bounce is done" sale
  fires.
  - It is computed from the completed sessions (`indicators.bounce_price`),
    so it is fixed for the whole session and moves once a day.
  - It replaces the fixed 2.5 × entry ATR target of EXP-0055.
- **It rests at Alpaca** as the take-profit half of the same OCO order as the
  stop (EXP-0056). Each morning the reconciler moves that order to the new
  level: once a session, never within one.
- **Never below the market.** A level at or below the broker's price means
  the bounce is already done, so the bot sells instead of resting a limit
  that would fill at once. A refused order would pause broker take profits for
  every position that day.
- **Unchanged:**
  - the stop (2.5 ATR, resting);
  - the RSI exit and the 20-session limit, which still take precedence;
  - the 15-minute backstop check.
- **New positions** get no fixed target. The next cycle sets the session's
  bounce price; until then the entry's own bracket, and after it the plain
  stop, protect them.
- **The learner** now replays trades with the bounce price as the target and
  steps only the stop.
- **TradingView and the `adaptive-exits` command** show the bounce price and
  say where it comes from.
- **Reversible:** `take_profit_mode="atr"` restores EXP-0055/56 exactly.

### The evidence

- **H-0038, trade by trade** (698 decade trades, replay matching 698/698
  real exits):

  | Take profit | R a trade |
  |---|---:|
  | Bounce price | +0.144 |
  | 2.5 ATR | +0.115 |
  | Difference | +0.029 (t 1.64) |

  The difference was positive in both halves and under every exit-cost
  assumption, but short of the sealed t ≥ 2: NO DIFFERENCE SHOWN.
- **Portfolio level** (`scripts/exp0057_portfolio_diagnostic.py`, decade,
  purpose `diagnostic`). The frozen baseline reproduced exactly (+58.5889%,
  698 trades), and the 2.5-ATR row reproduced EXP-0055's own disclosure:

  | Take profit | 0.652% exit cost | 0.3% exit cost |
  |---|---|---|
  | None (frozen) | +58.6%, 4.43%/yr, Sharpe 0.511, −12.98% | +93.5%, 6.40%/yr, Sharpe 0.710, −12.87% |
  | 2.5 ATR (live until now) | +67.2%, 4.95%/yr, Sharpe 0.591, −12.59% | +78.8%, 5.61%/yr, Sharpe 0.663, −11.97% |
  | **Bounce price (now live)** | **+79.2%, 5.63%/yr, Sharpe 0.637, −12.35%** | **+97.3%, 6.59%/yr, Sharpe 0.736, −12.26%** |

**How to read it:**

- **Against the take profit it replaces,** the bounce price is ahead under
  both cost assumptions: +12.0 and +18.5 points over the decade, with about
  the same worst drawdown.
- **The old fixed target was worse than none** at the 0.3% cost: +78.8%
  against +93.5%.
- **Against no take profit** the bounce price is also ahead: +20.6 and +3.8
  points.
- **Some of that is execution, not signal.** A resting limit avoids the
  simulated cost of a market sale: $30,477 of the 0.652% charge. Net of that
  it trails the frozen exit by about $10,000; it sells at the same level, so
  the difference is execution timing.
- **Evidence "weak".** These are the data the strategy was built on, so they
  describe the change rather than prove it. The forward record from
  2026-11-02 is the real test.

## 2. REM-0010: the entry-date fix

- **What was wrong.** From about 2026-09-22 each new position was dated with
  the cycle's last bar. On daily bars that is the previous session's, so the
  20-session limit fired one session early (D+19, against SPEC-0001 C-16's
  D+20).
- **The fix.** New positions are dated with the broker's clock
  (`autotrade._entry_stamp`).
- **The open positions were repaired** from their own audit-log entry times.
  The state was backed up first (`data/autotrade-state.backup-before-REM-0010.json`)
  and a `state_repair` event was logged. Their time limits move to the right
  session:

| Position | Was | Now |
|---|---|---|
| VZ | Oct 19 | **Oct 20** |
| IWM | Oct 20 | **Oct 21** |
| SCHD | Oct 20 | **Oct 21** |
| MDY | Oct 21 | **Oct 22** |
| SCHW | Oct 28 | **Oct 29** |
| CVS, UNP | Oct 19 | Oct 19 (already right) |

## 3. The flashing window

**The cause.** The crypto watchdog task (`EventAwareTraderCrypto`) runs every
minute, around the clock.

- Creating it as a background (S4U) task needs Administrator rights, so the
  installer had fallen back to an Interactive task: it ran on the desktop.
- `-WindowStyle Hidden` only hides a console after it appears, and on Windows
  11 the console can open in Windows Terminal, which ignores the flag.
- The equity and recorder tasks already ran in the background and never
  showed a window.

**The fix.**

- **The task.** It now starts through `conhost.exe --headless`, which gives
  the script a console that is never drawn. The schedule, account, script and
  arguments are unchanged.
- **The worker.** The watchdog starts it the same way.
- **The installers.** All three now register tasks that way, so a reinstall
  cannot bring the window back.

**Checks.**

- The next run (16:04) succeeded (result 0), and the crypto worker's heartbeat
  stayed fresh.
- The old task definition is saved at
  `data/EventAwareTraderCrypto-task-backup-2026-10-04.xml`.

**Optional.** Running `scripts\windows\install-crypto-session.ps1 -Live
-RequireS4U` once from an Administrator PowerShell makes the crypto task a
background task that also runs while logged off.

## 4. Monday's first cycle: what to check

**In `data/autotrade-audit.jsonl`:**

- **The orders move.** For each position, one `sell_order_canceled` followed
  by one `protective_stop_placed` with `order_class: oco`, whose
  `take_profit` is that morning's bounce price.
- **Later cycles leave them alone.** The same day, no further cancels.
- **Possible refusal.** `protective_oco_FAILED` would mean Alpaca refused the
  OCO. The plain stop then goes back in the same cycle.

**Expected levels.** Computed from Friday's 3:45 pm prices, so the real ones
will shift with Friday's close:

| Position | Bounce price |
|---|---:|
| UNP | 290.39 |
| MDY | 687.97 |
| IWM | 293.49 |
| VZ | 49.79 |
| CVS | 95.72 |
| SCHD | 34.40 |
| SCHW | 108.55 |

**TradingView** shows the new levels once the generated script is re-pasted
(`tradingview/live-levels.pine`, rewritten every cycle).

## Governance

- **Fingerprint** `ab33087c…` → `448170c3364935560663048c59647dfb5b204c6e6c724ce603f0d61c476e0f29`,
  re-pinned in its four guards.
- **Freeze** 2026-10-04 (EXP-0057). The first clean session is still
  2026-11-02, because a Sunday freeze is followed by the same sessions as a
  Saturday one.
- **Ledgers:** EXP-0057 in `docs/experiments.jsonl` (accepted, evidence
  "weak"); REM-0010 in `docs/remediations.jsonl` (chain intact).
- **Tests:**
  - 20 new tests in `tests/test_bounce_take_profit.py`;
  - older take-profit tests pinned to the `"atr"` mode they were written for;
  - SPEC A2 isolated from the take profit (adaptive exits off, with a note).
- **Files changed:**
  - core: `indicators.py`, `adaptive_exits.py`, `autotrade.py`,
    `portfolio.py` (research switch, off by default), `cli.py`;
  - scripts: `scripts/tradingview_levels.py`, the three installers and
    `session-run-crypto.ps1`;
  - new scripts: `scripts/repair_entry_stamps.py` and
    `scripts/exp0057_portfolio_diagnostic.py`.
