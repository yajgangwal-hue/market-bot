# Adaptive volatility exits — the owner's change, recorded as EXP-0055

*2026-09-28. **This is a strategy change, made on the owner's explicit
instruction:*

> "do what i said, an implient so that the bot can set its own take profits and
> stop losses based on the volitality and that it can get better at knowing
> where to set that with time"

*The research evidence is against it: EXP-0050, and H-0026, where the
take-profit level learned from the strategy's own trades was "none". It is
recorded with evidence `contradictory`. The frozen configuration changed, so
the forward evaluation restarts.*

## What the bot does now

- **Every position gets two levels.** A stop k_sl × ATR below its entry and a
  take profit k_tp × ATR above it. ATR is the stock's own 14-day average daily
  range at entry, so a jumpy stock gets wider levels than a calm one. Both
  multiples start at 2.5: the stop where it has always been, the target at 1R.
- **The stop is unchanged.** It still rests at the broker.
- **The take profit is checked every cycle.** It is compared against the
  broker's own mark: market value ÷ shares, not the previous close. A position
  at or above its level is sold through `close_out`, the same
  cancel-the-stop-then-close path as every other exit.
- **The existing exits keep precedence.** The stop, the bounce exit (RSI ≥ 60)
  and the 20-session cap all take precedence over the take profit.
- **Levels are entry-time facts.** A new position records its take profit at
  entry. The seven positions open on 2026-09-28 get theirs once, at the first
  cycle, from the stop they were opened with. Levels are never moved
  afterwards, even when the learned multiple changes.
- **It learns.** After each close,
  `event-aware-trader adaptive-exits --learn` runs; it is called from
  `session-run.ps1`, after trading has ended. At most once every 20 sessions it
  replays every finished trade under the levels in force and one step either
  way (target ±0.5 ATR, stop ±0.25 ATR) on the bot's own price files. It moves
  one step, inside the bounds of 1.5–6.0 ATR for the target and 2.0–3.5 ATR for
  the stop, only when that neighbour would have earned more per unit of risk
  on at least 100 trades. The gain must be:
  - above 3 standard errors;
  - above 0.05 R;
  - positive in both the older and the newer half of the record.

  Every evaluation is kept in `data/adaptive-exits.json`.

The levels for the positions open on 2026-09-28 are set at the next cycle.
They are shown here from each entry reference; the bot uses the broker's
average fill:

| | stop | take profit |
|---|---:|---:|
| BAC | 53.20 (−5.8%) | 59.81 (+5.8%) |
| CVS | 81.71 (−6.6%) | 93.21 (+6.6%) |
| IWM | 273.19 (−3.2%) | 291.06 (+3.2%) |
| MDY | 647.13 (−2.6%) | 681.83 (+2.6%) |
| SCHD | 32.49 (−2.4%) | 34.13 (+2.4%) |
| UNP | 254.77 (−5.5%) | 284.38 (+5.5%) |
| VZ | 43.61 (−5.8%) | 48.98 (+5.8%) |

## What it is expected to do — the disclosure

One run, purpose `diagnostic` (no accept/reject; the owner had decided): the
frozen strategy plus a take profit at 2.5 ATR, on the decade.

| | frozen | with the take profit |
|---|---:|---:|
| total return | +58.59% | +67.21% |
| CAGR | 4.42% | 4.95% |
| max drawdown | −12.98% | −12.59% |
| trades | 698 | 756 |
| win rate | 51.1% | 55.6% |
| profitable years | 10 of 11 | 8 of 11 |
| exits | stop 239, bounce 221, time 238 | stop 240, **take profit 331**, bounce 10, time 175 |

**How to read it:**

- **Gains are recognised sooner and more often.** A take-profit exit's median
  is +5.49% after 8 sessions; a bounce exit's is +6.81% after 13.
- **The +8.6 points is not evidence of a better strategy.** Take-profit exits
  pay no simulated rule-exit haircut (0.652%), and the take profits avoided
  $37,856 of it. Net of that, the change is −$29,230: H-0010's clause E, again.
  The live truth lies between the two figures, depending on how much the bot
  really loses by selling at the moment a rule fires: H-0008 and H-0012 put it
  at 0.2–0.6%.

## Why the learning is so strict

It was measured by simulation before deployment, on worlds of 20 or 100
trades:

- **Why a loose rule fails.** The paired R difference between two exit levels
  is badly skewed. A wider target usually wins a little and occasionally loses
  a lot, and a small sample rarely contains the losses.
- **The first rule tried learned nothing.** It was 1–2 standard errors on 20
  trades. It moved on pure noise in 59% of evaluations, and with a real edge
  moved the right way in only 42%.
- **The shipped rule on pure noise:** it moves in 7.2% of evaluations.
- **The shipped rule with a real +0.05 ATR/day edge:** it moves the right way
  in 11.0% of evaluations and the wrong way in 5.2%.

The bot trades about 70 times a year, so its first possible move is more than
a year away. Even then, a single move is weak evidence. Learning where to put
exits is slow here because the evidence is thin, not because the rule is
timid.

## Governance

- **Ledger.** `docs/experiments.jsonl` has EXP-0055, `accepted`, family
  `exits`, evidence `contradictory`. EXP-0053 does not exist.
  `research.record_experiment` numbers new rows by row count, so it would have
  issued a duplicate EXP-0054. The row was written with the next free
  identifier instead; the helper is unchanged, because it is H-0026's sealed
  code.
- **Freeze.** It moved from 2026-09-11 to **2026-09-28**. The embargo is 20
  sessions, so the **first clean session is 2026-10-27**, not 2026-10-12.
  Nothing is lost: 0 clean sessions had been recorded under the old freeze.
- **Fingerprint.** The old one was `da22011e…c237b`; the new one is
  **`da857ab7b85e20f9e458b769f1d587f0b59eba5c8686e9a0b9c002480f542a8c`**.
  - The fingerprint covers `AdaptiveExitConfig`, the procedure. The multiples
    it learns are not in it, because learning them is the procedure.
  - The fingerprint is re-pinned, with its history, in:
    - `tests/test_phase4_observation.py`, where G23 said "stop, investigate,
      and restart" and did;
    - `tests/test_spec0001_exit_boundary.py`;
    - `scripts/phase4_checkpoint.py`;
    - `scripts/preoos_dry_run.py`.
  - Research scripts that pin `da22011e` are unchanged: their sealed results
    were produced under it.
- **The research candidate is unchanged.** `research.PRODUCTION_CANDIDATE` has
  no take profit, so every sealed result still reproduces (+58.5889% / 698).
  Live now differs from it by the adaptive exits, a declared divergence.
- **Code.**
  - New: `src/event_aware_trader/adaptive_exits.py`.
  - `autotrade.py`:
    - the config field;
    - levels read once per cycle;
    - `_entry_rule` for the learned stop multiple;
    - the take-profit check after `should_exit`;
    - the level recorded at entry and in every hold row.
  - `forward.py`: `adaptive_exits` added to the fingerprint.
  - `daily_report.py`: the take profit shown per position; rule exits labelled
    by their logged `exit_reason`.
  - `cli.py`: the `adaptive-exits` command.
  - `session-run.ps1`: the learning call after the close.
- **Tests.** `tests/test_adaptive_exits.py` (20) and
  `tests/test_adaptive_exits_live.py` (9, through `run_once`). The full suite
  is 1,342 OK. It was run with every network call blocked and counted: zero
  attempts, so no test ever reaches Alpaca.
- **Owner's standing rule.** The exposed Alpaca key has not been rotated. This
  change was made on the owner's direct instruction. It adds no new use of the
  key; the bot's own cycles already use it.

## Turning it off

Set `adaptive_exits=None` on `AutoTradeConfig`. That is itself a
configuration change: it moves the fingerprint again and restarts the
evaluation again.
