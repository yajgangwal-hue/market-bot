# Emulator / live exit-path fidelity audit

*Read-only code-path audit. **No economic quantity was computed**, no P&L
claim is attached, nothing was modified. Follows H-0024 (B).*

---

## K. Classification: **B — FIDELITY GAP EXISTS, ECONOMIC IMPACT UNKNOWN**

The live and historical systems do **not** share an information boundary for
rule exits. The divergence is exact, reproducible from source, and affects
**459 of 698 historical exits (65.8%)**.

Not **A**, because the boundary difference is real and located.
Not **C**, because the systems **cannot** be made fully consistent: the
emulator decides *and fills* at the session close, which the live loop can
never do — it decides at 15:45 on a partial bar and fills at market. A
correction narrows the gap; it does not close it.

---

## A. Governance

| check | state |
|---|---|
| identifier | **none assigned** — this is a non-economic fidelity audit, so no registration was manufactured (§1.1). H-0022, H-0025, H-0026 remain free |
| registrations / declared / chain | 23 / 63 / intact — **unchanged** |
| **baseline equivalence** | **+58.5889000000% / 698 — PASS** |
| fingerprint | `da22011e…c237b` — unchanged |
| RSI 35/60 · ATR 0.035 · stop 2.5× · cap 20 · entries/day 3 · positions 12 · risk 0.005 · haircut 0.652% · `mr_limit_exit` None | all verified |
| ranker / veto / learned | OFF |
| H-0014 … H-0024 | frozen; **H-0014, H-0012, H-0013 not re-run** |
| clean OOS | 0 sessions, untouched |
| production diff | **none** |

---

## B. Live entry path — exact boundary

```
Task (every 15 min)
  └ session-run.ps1
      §2 refresh CSVs: fetch_alpaca_equity_bars(equities, days=800)
         → include_today defaults FALSE → files hold bars through D−1
      §4 autotrade --asset-class equity --live
          └ run_once
              entry gate: entry_window_minutes = 20  (last 20 min of session)
              autotrade.py:1899  series = daily_bars(symbol)          → D−1
              autotrade.py:1900  series = _with_today(series, todays) → + D partial
              _todays_bars(): its OWN fetch, days=4, include_today=True
```

| DECISION | DATA SOURCE | LATEST BAR | KNOWABLE AT |
|---|---|---|---|
| live entry | `daily_bars` **+ `_with_today`** | **D, partial** | ≈15:40–16:00 ET on D |

**`_with_today` appears at exactly one call site in `autotrade.py`: line 1900.**

Multiple cycles *can* produce different entry decisions, because the partial
bar changes through the session — but entries are gated to the final 20
minutes, so in practice one or two cycles are eligible.

---

## C. Live exit path — exact boundary, every mechanism

Under `entry_rule="mean_reversion"` (production) the **only** rule-exit
decision is `should_exit(...)` at `autotrade.py:1727`, fed by
`series = daily_bars(symbol)` at **line 1691 — with no `_with_today`**.

`mean_reversion.should_exit` (`:493`) reads `bar = bars[-1]`, i.e. **D−1**:

```python
if stop_is_comparable and bar.low <= stop:          return "stop"      # D−1 low
strength = rsi([b.close for b in bars], 14)
if strength >= config.rsi_exit:                     return "reverted"  # D−1 closes
if bars_held >= config.max_holding_bars:            return "time"
```

| Exit mechanism | Data source | Includes today? | Resolution | Decision timestamp | Executable price | Emulator equivalent |
|---|---|---|---|---|---|---|
| **Broker GTC stop** | live tape at broker | **YES** | continuous | on trade at/through stop | stop, or open on a gap | `bar.low <= stop` (+`realistic_stop_fills`) — **faithful** |
| in-process "stop" | `daily_bars` D−1 | **no** | daily | first cycle of D | market at cycle | redundant with the broker stop; lags it |
| **RSI (`reverted`)** | `daily_bars` D−1 closes | **no** | daily | first cycle of D | market at cycle | emulator uses **D's close** — **diverges** |
| **holding cap (`time`)** | `bars_held` from D−1 series | **no** | daily | first cycle of D | market at cycle | emulator uses **D's close**, and counts one higher — **diverges** |
| peak exit | `exit_at_peak.py` | n/a | manual | operator-invoked | market | **no emulator equivalent** — directed tool, never self-invoked |
| manual / external close | broker feed | n/a | n/a | operator | market | reconstructed by `trade_reconcile`, not modelled |
| protective-stop reconciliation | broker positions/orders | n/a | per cycle | every cycle | n/a | no emulator equivalent |

`should_exit` returns `"time"`; the emulator labels the same event
`"time_exit"` (`portfolio.py:654`). Cosmetic, but it breaks a naive log join.

---

## D. Emulator path — exact boundary

```
for stamp in timeline:                       # one iteration per session D
    todays_bars = {s: bar(D)}
    §2 manage open positions against today's range        (:409)
        position.bars_held += 1                           (:415)
        stop:      bar.low <= position.stop               (:503)
                   realistic_stop_fills → bar.open if gapped (:515)
        reverted:  closes = [history closes] + [bar.close] (:520)
                   exit at bar.close × (1 − 0.652%)        (:653)
        time_exit: bars_held >= 20 → bar.close × (1 − haircut) (:652)
```

**The emulator uses D's completed bar before deciding.** RSI includes D's
close; the exit is booked at D's close.

---

## E. The boundary, stated precisely

> **Live RSI exit on session D uses closes through D−1 and executes at market
> on D.**
> **Emulator RSI exit on session D evaluates RSI including D's close and books
> the exit at D's close.**

Therefore a condition that first becomes true at D's close is acted on by the
emulator **at D's close**, and by the live loop **at the first cycle of D+1**.
The two actions are separated by **exactly one overnight gap plus the opening
minutes**. The same holds for the holding cap.

---

## F. `bars_held` — the counting audit

| | convention | value on session D+k |
|---|---|---|
| emulator | `position.bars_held += 1` per session with a bar (`:415`) | **k** |
| live | `sum(1 for bar in series if bar.timestamp.date() > entry_day)`, `series` ends D−1 (`:1719`) | **k − 1** |

**Live `bars_held` is exactly one lower than the emulator's on the same
calendar session.** The emulator's 20-session cap fires on D+20; live's
`bars_held` first reaches 20 on D+21.

Sub-cases checked: entry-day bar excluded from the live series while forming
(documented at `should_exit:516-521`); weekends and holidays are handled
identically because both count *bars*, not calendar days; a position entered
and exited on the same session cannot occur under `signal_close` (the entry
happens in §3, after §2 has run). **No second discrepancy found beyond the
off-by-one.**

---

## G. Comparison table

| Decision | Emulator | Live | Same information? | Same timestamp? | Same action possible? |
|---|---|---|---|---|---|
| Entry | D's **complete** close | D's **partial** bar ≈15:45 | **No** — partial vs final close | approximately | yes |
| Stop | `bar.low(D) <= stop` | broker GTC on live tape | **Yes** in effect | **Yes** | yes |
| RSI exit | RSI incl. **D's close** | RSI through **D−1** | **No** | **No** — one session late | yes, later |
| Holding-cap exit | `bars_held = k` at D | `bars_held = k−1` at D | **No** | **No** — one session late | yes, later |
| Peak exit | **absent** | operator-invoked tool | **No** | n/a | **no emulator equivalent** |
| Broker reconciliation | **absent** | every cycle | **No** | n/a | **no emulator equivalent** |

---

## H. Historical divergence population — counts only, no P&L

From the frozen baseline's 698 trades:

| exit reason | trades | share | live/emulator decision timestamp |
|---|---:|---:|---|
| `stop` | **239** | 34.2% | **same** — broker GTC models `bar.low` faithfully |
| `reverted` | **221** | 31.7% | **differs by one session** |
| `time_exit` | **238** | 34.1% | **differs by one session** |
| **rule exits total** | **459** | **65.8%** | **differs** |

**459 of 698 historical exits (65.8%) carry a decision timestamp the live
system could not have reproduced.** Stated as a population count. Converting
it into P&L requires a counterfactual this audit is forbidden to run.

---

## I. H-0012 / H-0013 applicability

Neither was re-run; only provenance was established from their sealed text.

| | scope, from the seal |
|---|---|
| **H-0012** | *"The ONLY change is the recorded exit price of **reverted and time_exit** trades"*, against *"the measured **459-exit** trigger-to-close distribution"* |
| **H-0013** | *"only the recorded exit price changes, analytically, on the frozen trade path with entries, quantities, ordering, slots, signals and exits all held fixed"* |

**Both describe the EMULATOR's historical rule-exit accounting. Neither
describes the live loop.**

And the loop closes on itself: H-0012's 459-exit population **is exactly the
459 rule exits identified in §H as the divergent set.** The 0.652% haircut
models *trigger-to-close drift* — the interval between a rule triggering and
the emulator booking it at that session's close. **The live system has no such
interval**: it triggers on D−1's close and fills at market on D. The haircut's
semantics therefore do not transfer to live execution, and it must not be
quoted as live slippage or live cost.

---

## J. Defects — documented, **not fixed**

### Defect 1 — exit path omits today's bar

- **File/function/line:** `src/event_aware_trader/autotrade.py`, `run_once`, **line 1691**
- **Observed:** `series = daily_bars(symbol)` — series ends D−1
- **Expected for fidelity:** the entry path's treatment at line 1900, `_with_today(series, todays.get(symbol))`
- **Why it matters:** the live rule exit is structurally blind to the session it is trading in; the emulator is not
- **Category:** **A — information-boundary mismatch**
- **Minimum correction:** pass the same `_with_today(...)` series into the exit evaluation. **Residual gap remains**: a 15:45 partial close is not the 16:00 close.

### Defect 2 — `bars_held` off by one

- **File/line:** `autotrade.py:1719-1726`
- **Observed:** counts completed bars strictly after entry from a series ending D−1 → `k − 1`
- **Expected:** the emulator's `k` (`portfolio.py:415`)
- **Why it matters:** the 20-session cap fires one session later live than in every backtest
- **Category:** **A**, consequent on Defect 1
- **Minimum correction:** count today's in-progress session once it is included, or add one when the entry-day convention requires it. Must be changed **together with** Defect 1 or it double-counts.

### Defect 3 — exit-reason label mismatch

- **Observed:** `mean_reversion.should_exit` returns `"time"`; `portfolio.py:654` records `"time_exit"`
- **Category:** cosmetic; breaks log reconciliation between the two systems
- **Minimum correction:** one string.

### Also recorded, not a defect

The live system has two mechanisms with **no emulator counterpart**:
operator-invoked `exit_at_peak.py`, and per-cycle protective-stop
reconciliation. Neither is modelled historically. They are not defects — they
are live-only machinery — but they mean the emulator is not a complete
description of live behaviour even after Defects 1–3 are corrected.

---

## §12 classification of each discrepancy

| discrepancy | A information | B frequency | C execution |
|---|---|---|---|
| exit reads D−1 vs D | **✓** | | |
| `bars_held` off by one | **✓** | | |
| stop: continuous broker vs once-per-bar | | **✓** | |
| 26 cycles, one effective rule-exit decision | | **✓** | |
| emulator books at D's close × (1−0.652%); live fills at market on D+1 | | | **✓** |
| entry: partial bar vs final close | **✓** | | |

---

## L. One next action

**Perform a narrowly defined engineering correction review of Defects 1 and 2,
together, as a single change.**

Not "close the branch": the gap is real and sits under 65.8% of historical
exits. Not a new economic experiment: this audit produced no economic quantity
and §14 forbids inventing one; and any change to live exit timing alters money-
path behaviour, so it needs its own review and — if it changes historical
results — its own registration.

The review must decide one question before any code moves: **which system is
the reference?** Either live is corrected toward the emulator (act on D's
partial bar), or the emulator is corrected toward live (evaluate rule exits on
D−1). These are opposite changes with opposite consequences, and the second
would alter the frozen baseline and therefore the fingerprint. **I have not
chosen, because that is a governance decision, not an engineering one.**

---

## Final statement

**No — the current emulator does not faithfully represent the information and
decision process used by the live system.** They agree on entries to within a
partial-versus-final close, and they agree on stops. They disagree on **every
rule exit**: the emulator evaluates RSI and the holding cap including the
current session's close and books the fill at that close, while the live loop
evaluates both on data through the previous session and fills at market one
session later — a difference of exactly one overnight gap, across **459 of 698
historical exits**, compounded by a `bars_held` off-by-one that delays the
20-session cap by a further session.

**The single smallest action required before another profitability experiment
can be trusted is the joint correction review of `autotrade.py:1691` and
`autotrade.py:1719-1726`, beginning with the governance decision of which
system is the reference.** Until that is settled, any economic result produced
by the emulator describes a decision process the live bot does not run.

---

*Production unchanged: fingerprint `da22011e…c237b`, RSI 35/60, ATR 0.035,
20-bar cap, 2.5× ATR stop, risk 0.005, 12 positions, haircut 0.652%, clean OOS
0 sessions, 23 registrations, chain intact, thirty-year reads 13. No live
order, no modification, no P&L claim.*
