# SPEC-0001 implementation audit

*Companion to `docs/SPEC-0001-decision-boundary.md` v1.0.0. **Read-only.** No
code changed, no P&L computed, no experiment registered, no live behaviour
altered, clean OOS untouched.*

---

## Governance

| | |
|---|---|
| baseline | **+58.5889000000% / 698** — frozen, untouched |
| fingerprint | `da22011e…c237b` — unchanged |
| MR config | RSI 35/60 · ATR 0.035 · cap 20 · stop 2.5× — unchanged |
| ledger | 23 registrations, 63 declared, chain intact |
| clean OOS | **0 sessions**, opens 2026-10-12 |
| production diff | **none** |
| SPEC-0001 | v1.0.0, published — changes no code |

---

## B. Implementation audit

### B1. Which series each live decision actually sees

| live decision | source | ends at | conforms to SPEC-0001 |
|---|---|---|---|
| entry signal | `daily_bars()` **+ `_with_today()`** (`autotrade.py:1899-1900`) | **D, partial** | **YES** (§4.1) |
| RSI rule exit | `daily_bars()` alone (`:1691`) → `should_exit` (`:1727`) | **D−1** | **NO** (§4.2) |
| time exit | `bars_held` from the same D−1 series (`:1719`) | **D−1** | **NO** (§4.3, §5) |
| in-process stop check | same D−1 series, `bar.low` inside `should_exit` | **D−1** | redundant backstop (C-11); stale but harmless |
| broker protective stop | live tape, GTC resting order | **continuous** | **YES** (§4.4, C-10) |
| daily loss guard | live broker equity vs session opening (`:1496-1497`) | **D, current** | **YES** (§4.6) |
| weekly loss guard | live broker equity vs ISO-week opening (`:1512-1513`) | **D, current** | **YES** (§4.6) |
| cash sufficiency | live broker account | **D, current** | **YES** (§4.6) |
| position / bucket / entries-per-day caps | live broker positions + cycle state | **D, current** | **YES** (§4.6) |
| liquidity floor + participation cap | `series[-20:]` including D's **partial** volume (`:757`) | **D, partial** | **YES**, but see C-9 |

**`_with_today` appears at exactly one call site in `autotrade.py` — line 1900,
the entry path.** Confirmed by grep across the whole file.

The daily CSV refresh (`session-run.ps1` §2) calls
`fetch_alpaca_equity_bars(equities, days=800)` with `include_today` defaulting
**False**, so the files the exit path reads never contain the session in
progress. Confirmed from both directions.

### B2. What happens on each 15-minute cycle

For a position held through session D:

| stage | RSI recomputed? | on which data | `bars_held` recomputed? | stop checked? | exit submittable? |
|---|---|---|---|---|---|
| 09:30 (first cycle) | yes | **through D−1** | yes → **k−1** | broker-resident, continuous | yes |
| 09:45 … 15:45 (each cycle) | yes | **through D−1, unchanged** | yes → **same value** | broker-resident, continuous | yes |
| 16:00 | yes | **through D−1** | **same** | continuous | yes |

**26 cycles, one effective rule-exit decision.** Every cycle re-evaluates an
unchanged series and reaches the same answer. The only state that can change a
position's fate intraday is the broker-resident stop. **Loop frequency ≠
decision frequency.**

Consequence under SPEC-0001 §4.2: a condition first true at D's close is acted
on by the conformant emulator at D's close, and by the current live loop at
**the first cycle of D+1** — one overnight gap later.

### B3. Emulator

| emulator decision | source | conforms |
|---|---|---|
| entry | D's completed bar, fills at D's close (`entry_fill="signal_close"`) | **YES**, via the C-7 complete-bar proxy |
| RSI exit | `closes + [bar.close]` (`portfolio.py:520`), books at `bar.close × (1 − haircut)` (`:653`) | **YES**, via C-7 |
| time exit | `bars_held ≥ 20` (`:652`), `bars_held += 1` per session (`:415`) | **YES** (§5) |
| stop | `bar.low <= stop` (`:503`), `realistic_stop_fills` → open on a gap (`:515`) | **YES**, via C-7 |
| guards | D-close-marked equity vs D-open-marked equity (`:800-804`) | **YES** |
| liquidity / participation | `history[-20:]` including D's **complete** bar (`:984`) | **YES**, but see C-9 |

### B4. Every other rule checked (§5 completeness)

Audited and **conformant**: daily loss guard, weekly loss guard, cash checks,
`max_open_positions`, correlation-bucket cap, `max_entries_per_day`, entry
signal, protective-stop reconciliation (reads live broker state each cycle).

**No second instance of the stale-series defect was found.** The trend-rule
branch (`autotrade.py:1732-1738`) reads `bars_by_symbol` — the cycle's live
15-minute bars — and is therefore *not* stale; it is also **dead code in
production**, because `entry_rule = "mean_reversion"`.

---

## C. Mismatch inventory

| # | Decision | Canonical boundary (SPEC-0001) | Current live | Current emulator | Match? | Consequence |
|---|---|---|---|---|---|---|
| **1** | **RSI rule exit** | D, in progress; in-progress price as close proxy (§4.2) | **D−1** | D's completed close (C-7 proxy) | **NO — live** | Exit decided one session late. Affects **221 of 698** historical exits |
| **2** | **Time exit / `bars_held`** | k on D+k; cap fires D+20 (§5, C-15) | **k−1**; cap fires D+21 | k; cap fires D+20 | **NO — live** | Holding cap one session late. Affects **238 of 698**. **Same root cause as #1** (C-19) |
| **3** | In-process stop check | continuous, broker-resident (§4.4) | reads D−1 `bar.low` | `bar.low` of D | redundant | Harmless: the broker GTC order is the protection (C-11). Recorded for completeness |
| **4** | Liquidity floor + participation cap | D, in progress (§4.5) | D **partial** volume | D **complete** volume | **asymmetric by C-9** | Emulator is systematically **more permissive**. Measured non-binding: H-0015 found cash the sole first-binding reason among 1,539 evaluated candidates |
| **5** | Entry signal | D, in progress (§4.1) | D partial ✓ | D complete close (C-7 proxy) | **YES** | Proxy difference only; measured and deliberately shipped (EXP-0008/0016) |
| 6 | Stop execution | continuous broker-resident (§4.4) | GTC resting ✓ | `bar.low` + gap fills | **YES** | Faithful |
| 7 | Guards, cash, caps | D, current (§4.6) | live broker state ✓ | D-marked ✓ | **YES** | — |

**Divergent population:** mismatches #1 and #2 together cover
**459 of 698 historical exits = 65.8%**. Mismatch #3 is cosmetic; #4 is
structural but non-binding.

**One implementation defect, not two.** Per C-19, supplying the exit path a
series that includes D makes `autotrade.py:1719` return **k** automatically.
Correcting `bars_held` separately would double-count.

---

## D. H-0013 impact

**H-0013 is preserved unaltered. Its result is not rewritten and not
re-adjudicated.**

| | |
|---|---|
| what its methodology **assumed** | `h0013_build_features.py:9-13`, under seal: *"Trigger definition by reason, **matching how the live bot would act**: `reverted` — first RTH bar whose RSI(14), **recomputed with the current price standing in for today's close**, reaches `rsi_exit`"* — i.e. exactly SPEC-0001 §4.2 |
| what the implementation **actually did** | evaluated RSI on closes through **D−1** and could only act on the first cycle of the following session |
| therefore | **the 0.652% haircut was calibrated against a model of live behaviour the live code did not exhibit** |

### What can and cannot still be inferred

| claim | status |
|---|---|
| the measured **trigger-to-close drift distribution** (0.652% / 0.289% / 0.120% at 10:00 / 12:30 / 15:00) | **still valid** — it is a property of intraday price paths, measured from 5-minute bars, independent of which code reads them |
| the haircut correctly sizes the **emulator's** close-booking error *relative to SPEC-0001 §4.2* | **still valid** — that is the gap it was built to charge |
| the haircut describes what the **current live implementation** experiences | **NOT valid.** Live does not trigger intraday on today's data; it acts at the next session's open on yesterday's signal. Its execution gap is a different quantity |
| the haircut is live slippage or live transaction cost | **never valid** (C-24), and was never claimed |
| **baseline identity** | **unaffected.** The haircut value, the trade path and the fingerprint are untouched |
| **current production behaviour** | **unaffected.** Nothing changed |
| **emulator/live comparability** | **reduced, and now quantified**: the two systems' rule exits are not comparable trade-for-trade because their decision timestamps differ on 459 of 698 exits |

**Flagged clearly, per §7 of the task:** the 0.652% haircut should no longer be
treated as *exact* for the current live implementation. It remains the correct
charge for the emulator against the canonical boundary. If live is brought into
conformance, the haircut becomes the right charge for **both**; if live is left
as-is, the haircut describes the emulator only.

---

## E. Governance classification of the live correction

**Category: FROZEN-STRATEGY IMPLEMENTATION CORRECTION** (SPEC-0001 C-27).

| test | finding |
|---|---|
| Does it change a decision *condition*? | **No.** `rsi_exit` 60, `max_holding_bars` 20, every parameter unchanged (C-3) |
| Does it change a normative SPEC-0001 clause? | **No.** It brings live *into* conformance with v1.0.0 unchanged |
| Does it change the emulator? | **No** |
| Does it change the frozen baseline or fingerprint? | **No** — the simulator is untouched |
| Does it require a baseline-redefinition experiment? | **No.** That is Option A, which the evidence does not support |
| Does it touch the live money path? | **YES** — it changes which session live exits occur on, for ~66% of exits |

### A governance gap this exposes

**The fingerprint cannot detect this class of change.** `frozen_fingerprint()`
hashes `MeanReversionConfig`, `RiskPolicy`, `CostModel`, eight
`AutoTradeConfig` fields, `PRODUCTION_CANDIDATE`, the embargo and the benchmark
block. **None of these encodes which series a decision path reads.** Live could
be corrected — or could drift further — with the fingerprint unchanged
throughout. SPEC-0001 conformance therefore has to be asserted by audit, not by
digest.

### Approval required before implementation

1. **Explicit owner approval** of the live money-path change (C-27).
2. A **money-path review** of the single joint change to `autotrade.py:1691`
   and the series feeding `:1719` — they must move together (C-19).
3. **Regression evidence**: the full suite, plus a test pinning SPEC-0001 §4.2
   and §5 so the boundary cannot silently drift again.
4. A **dry-run verification** that the corrected path produces the expected
   `bars_held = k` and that no other decision shifts.
5. A **remediation-ledger entry** (`docs/remediations.jsonl`), not an
   experiment registration — it changes no parameter and no historical result.

**I have not implemented it and am not requesting implicit approval here.**

---

## F. Clean-OOS implications

Clean OOS opens **2026-10-12** with **0 sessions**. The date is not moved.

| scenario | consequence |
|---|---|
| correction approved and applied **before 2026-10-12** | the forward record measures **one stable, conformant implementation** from session 1. **No new clean validation period is needed** — the correction becomes part of the frozen candidate's implementation, and the fingerprint is unchanged |
| correction applied **after OOS begins** | the record spans **two different live behaviours**. A **new clean validation period would be required**, because the sessions before and after are not the same experiment |
| correction **declined** | the forward record measures a live system that does not implement the intended rule. That is a legitimate choice, but it must be recorded in SPEC-0001 as a **known, accepted non-conformance**, or SPEC-0001 must be amended — and amending a normative clause is a strategy semantics change (C-26) |

**The boundary must be frozen — decided either way and written down — before
2026-10-12.** Not the code necessarily; the *decision*. Today is 2026-09-22, so
that is **20 days**.

---

## G. STOP-SAFETY STATUS — separate track

*Reported separately from the exit-timing question, and not mixed with it.
This is the previously authorised protective-stop remediation.*

| | |
|---|---|
| status | **implemented, committed, verified** (REM-0007, REM-0008) |
| code | `broker.order(id)` authoritative fill lookup; `_settled_position_quantity`; `_verify_stop_coverage`; `status` exposed on `open_orders` |
| tests | **21 regression tests** reproducing the 219/229 race; full suite **1234 OK** |
| live verification, today | **4 of 4 eligible equity positions fully protected, zero uncovered shares** |

```
BAC  held=151  resting_stop=151  fully_protected  uncovered=0.0
CVS  held=124  resting_stop=124  fully_protected  uncovered=0.0
UNP  held=48   resting_stop=48   fully_protected  uncovered=0.0
VZ   held=174  resting_stop=174  fully_protected  uncovered=0.0
```

Note that **BAC has been re-entered at 151 shares** since the original defect
and is now fully covered — the fix is working on fresh entries in the very
symbol that exposed it.

### Remaining stop-safety exposure, unchanged and still open

| path | status |
|---|---|
| cancel-before-submit window | **TEMPORARILY EXPOSED** — Alpaca reserves shares against any resting sell, so the old order must go first. `PATCH /v2/orders/{id}` could remove the window; flagged, **not implemented** |
| stop rejection | **DETECTED** in the same cycle; repair at the next cycle (≤15 min intraday) |
| crash / restart spanning the close | **TEMPORARILY EXPOSED** — the DAY bracket expires at the bell |
| **crypto (BTC)** | **no broker-resident stop at all** — managed by the 30-second worker. Does **not** satisfy the invariant. Separate future safety project, unchanged, no authorisation sought |

**This track is independent of SPEC-0001** and neither blocks nor is blocked by
the exit-timing decision.

---

## Summary

SPEC-0001 v1.0.0 is published as the level-1 artefact that did not exist.
Against it, **the emulator conforms** (via the documented complete-bar proxy,
C-7) and **the live implementation does not**, on rule exits and the holding
cap — one defect with one correction, covering 65.8% of historical exits.
H-0013's result stands; what changes is that its haircut is now known to be
calibrated against assumed rather than observed live semantics, and must not be
called exact for the live path. The correction is a frozen-strategy
implementation correction requiring owner approval, and **the decision must be
frozen before 2026-10-12** so clean OOS measures one implementation.
