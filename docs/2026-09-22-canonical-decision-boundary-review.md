# Canonical decision-boundary review

*Non-economic architecture/governance review. **No P&L computed**, no
optimisation, no modification to production or the simulator, no registration
manufactured.*

---

## K. Intent status: **INTENT ESTABLISHED**

Four independent repository sources, at three levels of authority, state the
same intended semantics — and **neither implementation currently honours it**.

> **The rule is intended to evaluate using the session in progress, with the
> current price standing in for today's close, and to act when it fires.**

The **emulator is a documented approximation** of that intent (it can only see
the final close on daily bars, and the 0.652% haircut exists precisely to
charge the difference). The **live system is a departure** from it — it reads
the previous session and does not approximate the intent at all.

---

## A. Governance

| | |
|---|---|
| status | non-economic review; **no identifier assigned**, none required |
| ledger | 23 registrations, 63 declared, chain intact — **unchanged** |
| free identifiers | H-0022, H-0025, H-0026 |
| baseline | **+58.5889000000% / 698** — frozen, untouched |
| fingerprint | `da22011e…c237b` — unchanged |
| clean OOS | 0 sessions, untouched, opens **2026-10-12** |
| production diff | **none** |

---

## B. Verified fidelity gap (restated, not re-derived)

| fact | verified at |
|---|---|
| live exit reads `daily_bars(symbol)` with no `_with_today` | `autotrade.py:1691` |
| live exit decided by `should_exit(...)` | `autotrade.py:1727` |
| CSV refresh omits the current session | `session-run.ps1` §2, `include_today` defaults False |
| emulator increments per session | `portfolio.py:415` |
| emulator RSI includes today's close | `portfolio.py:520` |
| emulator books rule exits at today's close | `portfolio.py:653` |
| exit population | stop **239**, reverted **221**, time_exit **238** → rule exits **459/698 = 65.8%** |

---

## C. Evidence for intended semantics, by authority

**Level 1 — explicit strategy specification: ABSENT.** No document in the
repository states the decision boundary as a contract. *This is the gap.*

**Level 2 — sealed experiment specification.** `scripts/h0013_build_features.py:9-15`,
under the H-0013 seal:

> *"Trigger definition by reason, **matching how the live bot would act**:
> `reverted` — first RTH bar whose RSI(14), **recomputed with the current
> price standing in for today's close**, reaches `rsi_exit`; `time_exit` — the
> first RTH bar, the condition is already true at the bell."*

A sealed experiment states, as its model of live behaviour, that the rule
recomputes RSI using today's in-progress price. **The live code does not do
this.**

**Level 3 — production test contracts.**

`tests/test_exit_timing_haircut.py`:

> *"The simulator prices rule exits at the day's close. **The live bot sells
> the moment the rule fires, on whichever 15-minute cycle that is.** … So every
> figure this simulator has produced assumed a fill the bot does not get. On
> daily bars the trigger price does not exist and cannot be reconstructed. The
> haircut therefore CHARGES the measured difference rather than modelling it."*

`tests/test_entry_timing.py`:

> *"inside the window the signal **must include the session in progress**.
> Filling at today's close on yesterday's information would pay the gap's
> price without reading the day that set it — worse than either design"*
> …and…
> *"a window on ENTRIES must never become a window on PROTECTION — **exits and
> the stop reconciler have to keep running all day**"*

**Level 5 — implementation comments.** `autotrade.py:_todays_bars`:

> *"Entering near the close means the signal must include the session it is
> about to close in — **otherwise the rule is still reading yesterday** and the
> whole exercise moves the fill without moving the information."*

**Level 4 — production implementation: DIVERGES** from levels 2, 3 and 5 on
the exit path.

**Corroborating principle**, `tests/test_rule_config_threading.py`: *"the bot
would enter on one rule and exit on another … trading one rule's entries
against the other's exits would measure neither."* The project already treats
entry/exit asymmetry as a defect class.

---

## D. Canonical information-boundary proposal

| decision | latest permissible observation | decision timestamp | execution timestamp | complete or partial | emulator can reproduce | live can reproduce |
|---|---|---|---|---|---|---|
| **Entry** | session D, in progress | last 20 min of D | same instant | **partial** | approximates with D's final close | **yes — implemented** |
| **Rule exit (RSI)** | session D, in progress | the cycle at which the condition first becomes true | same instant, at market | **partial** | approximates with D's final close **+ haircut** | **no — currently reads D−1** |
| **Holding-cap exit** | session D; condition known at the bell | first cycle of the session where the cap is met | same instant, at market | n/a (a count) | yes (`bars_held = k` on D+k) | **no — counts k−1** |
| **Stop** | continuous live tape | on trade at/through the stop | same instant | n/a | approximates with `bar.low` + gap fills | **yes — broker-side GTC** |
| **Live-only overlays** | n/a | operator-invoked | market | n/a | **not represented** | n/a |

---

## E. `bars_held` contract

> **`bars_held` = the number of completed trading sessions strictly after the
> entry session, evaluated as of the current session.**

Under `entry_fill="signal_close"` (entry at D's close):

| case | value |
|---|---|
| on session D | 0 |
| on session D+1 | 1 |
| 20-session cap fires | **D+20** |
| weekends / holidays | irrelevant — both systems count **bars**, not calendar days |
| same-session entry and exit | **impossible** — entry occurs in §3, after §2 has run |
| entry during a session (live, ≈15:45) | D is the entry session; counting starts at D+1 |

**The emulator implements this contract** (`portfolio.py:415`).

**The live system does not — but not because it holds a different contract.**
`autotrade.py:1719` computes `sum(1 for bar in series if bar.timestamp.date() > entry_day)`,
which *is* the same definition; it evaluates it against a series ending D−1 and
therefore returns **k−1**. **Correcting the series (Defect 1) makes this
expression return k automatically.** They are one defect, not two — which is
why correcting `bars_held` separately would double-count.

*Legacy note:* the fallback branch (`len(series) - opened_days`,
`autotrade.py:1723-1726`) happens to return **k** and therefore agrees with the
emulator. The comment marks it as retained only for positions opened before the
preferred path existed. Two live branches, differing by one.

---

## F. Option A — Live → Emulator (change the simulator to read D−1)

| | |
|---|---|
| simulator change | rule exits would evaluate RSI on closes through D−1 and the cap on `bars_held = k−1` |
| trades that could change | **all 459 rule exits**, and through them quantities, cash, slots and buckets — H-0011 established that altering one exit changes the later trade set (96.4% of quantities differed; 117 trades differed in existence) |
| frozen baseline | **would necessarily change.** +58.5889000000% / 698 would no longer reproduce |
| fingerprint | `PRODUCTION_CANDIDATE` semantics change ⇒ **fingerprint moves** |
| comparability | every sealed result computed on the current trade path — H-0011 through H-0021 — becomes non-comparable to the new baseline |
| governance required | **a separately registered baseline-redefinition experiment.** Not performable inside this review |
| evidence support | **contradicted** by levels 2, 3 and 5: it would codify "the rule is still reading yesterday", which `_todays_bars` names as the failure mode |

**Not performed.**

## G. Option B — Emulator → Live (correct live toward the intended process)

| | |
|---|---|
| live change | pass `_with_today(series, todays.get(symbol))` into the exit evaluation, as the entry path already does at `:1900` |
| information gained | today's in-progress bar, giving RSI "with the current price standing in for today's close" — exactly H-0013's sealed model |
| decision timestamp | the cycle at which the condition first becomes true, rather than the first cycle of the following session |
| execution vs simulator | simulator books at D's **final close**; live fills **at market at the triggering cycle**. **These remain different** — that difference is what the 0.652% haircut already charges |
| `bars_held` | corrected automatically by the same change (§E) |
| operational risk | the rule could fire on a partial bar that reverses by the close — the emulator would not have exited. A new, smaller discrepancy replaces a larger one |
| classification | **fidelity correction toward documented intent**, not a parameter change. But it alters money-path behaviour and therefore needs its own review |
| frozen baseline | **unchanged.** No simulator change, no fingerprint change |

**Not implemented.**

---

## H. Live-only mechanisms

| mechanism | can close a position? | emulator equivalent | classification |
|---|---|---|---|
| `exit_at_peak.py` | yes, **only for symbols named by the operator** | none | **operational mechanism** — its own header: *"a DIRECTED tool, not a rule… **nothing in the bot calls this on its own**"*, and records that exiting losers early was *"the most destructive change ever measured on this project"* (rescue exit: win rate 53%→67%, CAGR 7.83%→6.41%) |
| per-cycle protective-stop reconciliation | only indirectly, by asserting the stop the rule already chose at `remembered["current"]` | none | **risk-control mechanism** — it does not select a stop level, it maintains one |
| broker-side GTC stop | yes | `bar.low <= stop` + `realistic_stop_fills` | **execution mechanism** — faithful to the emulator |
| external/manual close | yes | reconstructed post-hoc by `trade_reconcile` | **operational mechanism** |

**None of these is a strategy decision.** Live-only does not mean
economically meaningful, and `exit_at_peak.py` is explicitly excluded from the
canonical strategy by its own design note.

---

## I. H-0012 / H-0013 applicability

Neither re-run. Recorded, not rewritten:

> **H-0012 and H-0013 describe historical emulator accounting for the 459 rule
> exits. They do not establish live-system slippage.**

- trigger-to-close movement is **not** automatically slippage;
- the **0.652% haircut must not be presented as live execution cost**;
- live market execution occurs at a different information *and* execution
  boundary.

**A second-order finding worth recording:** H-0013's sealed trigger definition
models the live bot as recomputing RSI *with today's price standing in for
today's close*. The live code does not do that. **H-0013's haircut was
therefore calibrated against an assumed live behaviour that the implementation
does not exhibit.** Its result is not reinterpreted here; the provenance is
simply stated.

Under **Option A**, H-0012 and H-0013 would become non-comparable, because the
459-exit population they measured would no longer be the population the
simulator produces. Under **Option B** they remain exactly as valid as they
are today.

---

## J. Baseline implications

| | requires a new historical experiment? |
|---|---|
| **Option A** | **YES — "This requires a separately registered baseline-redefinition experiment."** It changes the trade path, the baseline and the fingerprint |
| **Option B** | **No.** The simulator, baseline and fingerprint are untouched. It changes live behaviour going forward and needs a money-path review, not a registration |

**A deadline applies to Option B.** The clean forward record opens
**2026-10-12** with 0 sessions. Correcting live *before* that date means the
out-of-sample evaluation measures the intended strategy. Correcting it *after*
would split the forward record across two live behaviours. **That window is
the binding governance constraint here**, and it is 20 days away.

---

## Decision framework (§12) — factual, no scores, no winner

| Criterion | Live → Emulator (A) | Emulator → Live (B) |
|---|---|---|
| Matches explicit strategy specification | none exists | none exists |
| Matches sealed experiment semantics | **no** — contradicts H-0013's trigger model | **yes** |
| Matches existing tests/contracts | **no** — contradicts `test_exit_timing_haircut.py` and `test_entry_timing.py` | **yes** |
| Matches intended information boundary | **no** | **yes** |
| Preserves realistic execution separation | yes | **yes** — the haircut keeps doing its job |
| Requires strategy change | **yes** (redefines the rule) | no (restores the documented rule) |
| Requires simulator change | **yes** | no |
| Changes historical baseline | **yes**, and the fingerprint | **no** |
| Operational implications | none live | changes live exit timing; needs money-path review; **2026-10-12 deadline** |

---

## L. Single next action

**Write an explicit canonical decision-boundary specification — the level-1
artefact that does not exist.**

It is the prerequisite for everything else: a correction review cannot be
conducted against an unwritten contract, and the absence of this document is
the *sole* reason two implementations drifted apart while four repository
sources agreed on the intent. It is non-economic, changes no code, and can be
written immediately from the evidence in §C–§E.

It must state, per decision type, the latest permissible observation, the
decision timestamp, the execution timestamp, and — explicitly — that
**decision equivalence is the target and execution equivalence is not
achievable**, because the emulator books at the close and live fills at
market. That distinction is what the haircut already encodes, and writing it
down is what stops it being re-litigated.

Not the engineering correction: it needs the spec as its target. Not a
baseline-redefinition experiment: that is Option A, which the evidence does
not support.

---

## Final statement

**Canonical boundary, on the strongest available evidence:** on session D the
strategy may use information **through the current moment of session D**, with
the in-progress price standing in for today's close — for entries *and* for
rule exits alike — acting at the cycle on which the condition first becomes
true. Stops remain continuous and broker-resident. `bars_held` is the count of
completed sessions strictly after the entry session, so the 20-session cap
falls on D+20.

**What remains unresolved:** no level-1 artefact records this, so the project
has an established intent with no authoritative statement of it; and the
*degree* to which the emulator's final-close approximation should be treated
as the contract versus a modelling convenience is a judgement only the owner
can fix.

**The single non-economic action required before either implementation is
altered:** write that canonical decision-boundary specification — and do it
inside the 20 days remaining before clean OOS opens on 2026-10-12, because
after that date any live correction splits the forward record across two
behaviours.

---

*Production unchanged: fingerprint `da22011e…c237b`, RSI 35/60, ATR 0.035,
20-bar cap, 2.5× ATR stop, risk 0.005, 12 positions, haircut 0.652%, baseline
+58.5889000000% / 698, clean OOS 0 sessions, 23 registrations, chain intact.
No P&L computed, no code modified, no experiment registered.*
