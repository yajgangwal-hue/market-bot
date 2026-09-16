# Phase 4 acceptance report — clean observation

*2026-09-16. Protocol: `docs/phase4-clean-observation-protocol.md`.
914 tests green. The frozen production path was not touched.*

**This phase produced no performance number, and could not have.** The
embargo has 18 of its 20 sessions still to run. What it produced is the
recording, verification and checkpoint machinery, proven against the live
account on a session that was deliberately **not** recorded.

---

## 1. NUMBER OF ELIGIBLE CLEAN SESSIONS

**0.**

Derived, not asserted. `purge.evaluation_window()` takes the freeze from
the registry and the embargo from the strategy's own holding cap, then
resolves both against the real trading calendar:

| | |
|---|---|
| research freeze | 2026-09-11 (EXP-0017, the last config-changing entry) |
| embargo | 20 sessions (`MeanReversionConfig.max_holding_bars`) |
| sessions elapsed since freeze | 2 — 2026-09-14, 2026-09-15 |
| sessions remaining under embargo | 18 |
| last embargoed session | 2026-10-09 |
| **first clean session** | **2026-10-12** |

## 2. NUMBER SUCCESSFULLY RECORDED

**0.** `data/forward-evaluation.jsonl` holds zero rows and its chain
verifies. Recording zero is the correct outcome: there has been nothing
eligible to record.

## 3. NUMBER REJECTED, AND WHY

**2 invocations, 2 refusals, 1 reason.**

| when | reason |
|---|---|
| 2026-09-16 03:04Z (manual) | embargo has not expired; 2 of 20 sessions elapsed |
| 2026-09-16 03:08Z (scheduled task) | same |

The recorder refuses on ten distinct conditions and names which one
fired: a broken chain, an unexpired embargo, an unresolvable calendar, a
session before the first clean date, a session already recorded, no
completed loop run in the audit log, an unreachable broker, a failed
reconciliation, a fingerprint change, and a duplicate caught at append.

**No field is ever invented.** Where a source is missing the recorder
refuses rather than writing a plausible zero, because a fabricated zero is
indistinguishable from a true one once it is in the record.

## 4. BROKER RECONCILIATION RESULTS

No session has been recorded, so no session has been reconciled. The
machinery was instead **exercised against the live paper account** on
2026-09-15 in a dry pass that wrote nothing. All thirteen checks passed
and none was unverified:

| check | result |
|---|---|
| every position protected | PASS |
| orders within the frozen universe | PASS |
| whole-share equity orders | PASS |
| concentration within the frozen cap | PASS |
| position count within the frozen limit | PASS — 5 held, limit 12 |
| participation limit respected | PASS — measured against real 20-day volume |
| exit reasons recognised | PASS |
| equity reconciles | PASS — 98,976.68 vs 98,976.68, gap 0.00 |
| cash reconciles | PASS — 6,947.28 vs 6,947.28, gap 0.00 |
| transaction costs recorded | PASS |
| dividends recorded | PASS — none paid |
| benchmark matches the session date | PASS |
| decision timestamp coherent | PASS |

Tolerances were fixed in advance in `forward.py`: $1.00 or 1 basis point on
equity and cash, $0.01 on costs and dividends, **exact** on position
counts. Equity is compared both absolutely and relatively because a $1 gap
on $100,000 and a $1 gap on $10 are different claims.

**Two defects were found by that live pass, both in the new verifier.** It
failed the session for trading SGOV "off-universe" and for "fractional"
SGOV and BTC/USD orders. Both were wrong: SGOV is the cash-parking ETF,
deliberately outside the candidate universe, and it is bought notionally
while crypto is fractional by design. Only equity entries are whole-share.
A checker that fails every session teaches the reader to ignore it, so both
exemptions are now explicit and each is covered by a test — including one
asserting a fractional *equity* order still fails.

## 5. DATA-INTEGRITY RESULTS

| | |
|---|---|
| chain | intact — every link recomputes |
| records | 0 |
| duplicate sessions | 0 (refused by `append_session`) |
| retroactive edits | none possible undetected; `verify_chain` reports the first break |
| isolation | `CleanObservation` refused by both research entry points |

The four integrity suites are re-run **at every checkpoint**, not once at
the phase start, and their results are printed into the checkpoint report.
Run now: 106 tests, all passing.

```
tests.test_forward_isolation    PASS  Ran 23 tests
tests.test_phase4_observation   PASS  Ran 57 tests
tests.test_purge_embargo        PASS  Ran 21 tests
tests.test_golden_master        PASS  Ran  5 tests
```

## 6. FINGERPRINT HISTORY

**One value, unchanged since Phase 3:**
`da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b`

It is asserted as a literal in `tests/test_phase4_observation.py`, so any
movement in a frozen parameter fails a test that names G23 rather than
letting the evaluation continue under a different configuration. A second
test shows the fingerprint moving when the haircut is changed, so the check
has been demonstrated capable of failing.

## 7. EXECUTION DISCREPANCIES

**None recorded**, because no session has been recorded. The recorder now
runs all thirteen checks on every session and writes their failures into
that session's `execution_discrepancies`, and their unverified checks into
`data_quality_issues`. **A discrepancy is recorded, never corrected.**

The live dry pass did surface two real loop events from 2026-09-15, which
would have been recorded as data-quality issues had the session been
eligible: `unpark_FAILED` and `broker_call_failed`, both an HTTP 403
"insufficient qty available" when unparking SGOV whose shares were already
reserved. The loop retried and the session completed.

## 8. HAIRCUT OBSERVATIONS COLLECTED

**0 paired observations.**

`scripts/haircut_observations.py` collects eligible live rule exits —
`reverted` and `time` only. Stop exits are excluded: their slippage is a
different quantity, and pooling them would flatter whichever is smaller.

Three rule exits exist in the audit log, all from 2026-09-01, and all
predate the loop recording a trigger price alongside the fill. They are
**skipped rather than estimated**: without the decision-time reference
price there is no observation, and inferring one from the proceeds would
measure the fill against itself.

The frozen **0.652%** bound stands unchanged and is not adjusted by this
script. Below ~30 paired exits the sample size is reported and the
distribution is not.

## 9. RAW STRATEGY PERFORMANCE

**Not measured. 0 clean sessions.**

## 10. RAW BENCHMARK PERFORMANCE

**Not measured. 0 clean sessions.** The benchmark is captured per session
from the same day's SPY bar, and a bar from any other date fails the
session's verification.

## 11. CUMULATIVE DIFFERENCE

**Not measured. 0 clean sessions.**

## 12. DRAWDOWN AND VOLATILITY OBSERVATIONS

**Not measured. 0 clean sessions.** The descriptive report is computed only
at Checkpoints C and D, at 60 and 120 sessions.

## 13. INCIDENTS AND PROTOCOL VIOLATIONS

**No protocol violations.** Three incidents, all disclosed:

1. **A documentation error in the Phase 3 report, corrected here.** It gave
   "approximately 2026-10-09" as the date clean evaluation begins.
   2026-10-09 is the *twentieth embargoed* session; the first admissible one
   is the next, **2026-10-12**. The code was always right —
   `evaluation_window` returns `after[horizon]` — and the prose was wrong.
   No date was changed to produce this; the off-by-one was in the sentence.

2. **The recorder's scheduled task registered at interactive-logon scope.**
   S4U registration needs elevation, which this session cannot obtain. The
   consequence is specific and matters: **every weekday the machine is not
   logged on at 16:15 New York, the recorder is skipped and that session
   becomes a permanent hole in the clean record**, since nothing may be
   backfilled. Re-running `scripts/windows/install-clean-recorder.ps1` from
   an elevated PowerShell fixes it. The main trading task is already S4U and
   is unaffected.

3. **Two false failures in the new verifier**, found by running it against
   the live account and fixed — see §4. Worth stating plainly: they were
   found because the verifier was run against reality rather than only
   against fixtures.

## 14. G19 — CLEAN-SESSION INTEGRITY — **PASS (vacuously, and by test)**

No observation has been accepted, so no accepted observation violates the
rules. The enforcement is tested: a foreign fingerprint is refused, a
duplicate session is refused, an edited record breaks the chain at the
edited index, a tampered record refuses to load, and a clean observation is
refused by `production_report`. Eligibility is derived from the calendar —
a test removes one session as a holiday and asserts the first clean date
moves.

## 15. G20 — BROKER RECONCILIATION — **PASS**

Tolerances documented in advance. Reconciliation demonstrated against the
live account with a 0.00 gap on equity and cash, and tested to fail on a
real gap, on a position-count difference of one, and on unrecorded fees and
dividends. A test asserts reconciliation **does not mutate** the recorded
figures.

## 16. G21 — DECISION-TIME INTEGRITY — **PASS, with one limit stated**

Structurally: no future price, volume, dividend or trade can alter an
earlier decision — five tests, re-run at every checkpoint. Per session: the
decision timestamp must not precede its session nor lie in the future, the
benchmark bar must carry the session's own date, and participation is
measured against volume from bars **strictly before** the session, because
the session's own volume is not known when the order is sized.

**Limit:** proving the *decision* reproducible end-to-end requires replaying
a live session from stored bars, which cannot be done until clean sessions
exist. **UNVERIFIED until then**, as in Phase 3.

## 17. G22 — EVALUATION CONTINUITY — **PASS**

The evaluation has not been stopped, restarted or altered. `continuity()`
compares eligible sessions against recorded ones and names every gap; a
missing session is reported, never filled. A session recorded before
eligibility is flagged separately. Both are tested, as is the case that
matters now: an empty record before eligibility is **not** an error.

## 18. G23 — NO STRATEGY MODIFICATION — **PASS**

Zero lines changed across the frozen set since the Phase 1 baseline
(`1b7603d`), verified by diff:

```
autotrade.py  broker.py  crypto_sleeve.py  mean_reversion.py  risk.py
session-run.ps1  session-run-crypto.ps1  crypto-loop-worker.ps1
```

This is why the recorder is a **separate** program with its own scheduled
task rather than a hook in the trading loop: wiring it in would have broken
the freeze it exists to protect. The dividend feed is read inline in the
recorder for the same reason, rather than added as a method to `broker.py`.

---

### MEASURED

914 tests green. Fingerprint `da22011e…`, unchanged. Freeze 2026-09-11,
derived. Embargo 20 sessions, read from the rule. **2 elapsed, 18 remain, 0
clean sessions, 0 recorded, 2 refusals.** Frozen-path diff 0 lines. Thirteen
verification checks passing against the live account with a 0.00
reconciliation gap. All five gates pass.

### UNCERTAIN

The 0.652% haircut remains a frozen **bound**, not a measurement — 0 of ~30
paired exits collected. The first clean date, 2026-10-12, assumes no
unscheduled market closure. End-to-end decision reproducibility stays
UNVERIFIED until clean sessions exist. Survivorship is still unquantified.
The recorder's task scope means a session can be missed if the machine is
logged off.

### NOT TESTABLE YET

Everything about performance. There are **zero clean observations**, and
this report contains no verdict on whether the strategy is profitable or
capable of outperforming the S&P 500 — not because the answer is
unfavourable, but because no evidence bearing on it exists yet.

At ~6–9% annual volatility the standard error of the return over 60
sessions is roughly 3%, larger than the entire annual edge under test. A
good quarter and a bad quarter are equally consistent with the same
strategy. **Profitability takes years to establish, and the instrument
built here is designed so that it cannot report a conclusion it has not
earned.**
