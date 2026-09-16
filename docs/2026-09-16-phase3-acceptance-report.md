# Phase 3 acceptance report — forward-evaluation infrastructure

*2026-09-16. Protocol: `docs/phase3-forward-evaluation-protocol.md`.
857 tests green. The production trading path was not touched.*

**This phase produced no performance number, and could not have.** Clean
evaluation has not begun. What it produced is the machinery that will make
the first clean observations trustworthy when they arrive.

---

## 1. THE FROZEN CONFIGURATION

Fingerprint **`da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b`**
— a SHA-256 over the rule, the risk policy, the cost model, the live loop
settings, the production candidate (including the haircut), the embargo
length and the benchmark methodology. Full listing in §1 of the protocol.

It is not a label. `append_session` compares every incoming record against
the current fingerprint and **refuses** on mismatch, so a configuration
change cannot be absorbed silently mid-experiment — it stops the record.

## 2. THE EXACT CLEAN-DATA BOUNDARY

**Research freeze: 2026-09-11**, derived by `purge.freeze_date()` from the
registry as the last entry whose decision was `accepted` or `reverted`
(EXP-0017). Not configured, not chosen. It independently equals
`research.FORWARD_START`, set earlier by a different route.

## 3. EMBARGO COMPLETION

| | |
|---|---|
| embargo | 20 sessions = `MeanReversionConfig.max_holding_bars` |
| sessions elapsed since freeze | 2 |
| both | embargoed |
| **clean evaluation begins** | **after 18 further sessions, ≈ 2026-10-09** |

Approximate because the exact date depends on market holidays and is
resolved from the real trading calendar at the time.

## 4. DATA-ISOLATION ARCHITECTURE

Three independent mechanisms, because each can be circumvented alone:

1. **Type-level refusal.** `CleanObservation` is a distinct frozen
   dataclass. `reject_forward_data` runs at the top of
   `research.production_report` and `research.record_experiment`.
2. **Hash chain.** Every record carries its predecessor's digest.
   `verify_chain` recomputes all links and reports the first break;
   `load_sessions` refuses to return data from a broken chain.
3. **Dataset gate** (Phase 1). `dataset="forward"` requires
   `purpose="forward_gate_evaluation"`.

**Demonstrated against the real entry points, not mocks:**
```
production_report({'A': [clean_observation]})   -> REFUSED
record_experiment(..., {'n': clean_observation}) -> REFUSED
```

**A defect found and fixed during this phase.** The first guard checked
only the top level and a list's items. An observation nested one level
deeper — inside a config dict — walked straight past it and failed later
with a JSON serialisation error. That is a failure but not a *refusal*, and
it would have been no protection at all had the object been serialisable.
The guard now recurses four levels.

## 5. THE APPEND-ONLY EVALUATION RECORD

`data/forward-evaluation.jsonl`, separate from the experiment registry, the
dataset-use log and all contaminated data. Written only by
`forward.append_session`, which refuses a duplicate session and a
fingerprint mismatch.

Each record holds: session date, `as_of` decision timestamp, fingerprint,
universe size, signals, orders, fills, positions held, exposure, cash,
equity, transaction costs, dividends received, strategy return, benchmark
return, exits with reasons, execution discrepancies, data-quality issues.
**Nothing may be backfilled.**

## 6. TESTS PROVING NO LOOK-AHEAD OR CONTAMINATION

**23 tests in `test_forward_isolation.py`**, covering each named property:

| property | test |
|---|---|
| a future price cannot change an earlier signal | ✅ (both a 5× spike and a collapse to $5) |
| a future dividend cannot change an earlier signal | ✅ |
| a future volume cannot change an earlier position size | ✅ (9bn-share bars appended) |
| a future trade cannot change an earlier portfolio decision | ✅ (second symbol added) |
| results cannot enter parameter selection | ✅ (`production_report` refuses) |
| clean data cannot reach experiment routines | ✅ (`record_experiment` refuses) |
| editing a recorded result is detected | ✅ (breaks at the edited index) |
| deleting a record is detected | ✅ |
| a tampered record refuses to load | ✅ |
| a session cannot be recorded twice | ✅ |
| a foreign fingerprint is refused | ✅ |
| the fingerprint moves when a frozen parameter moves | ✅ |

## 7. G15 — FREEZE INTEGRITY — **PASS**

Fingerprint computed and stable. Production path diff across all three
phases: **0 lines** over `autotrade.py`, `broker.py`, `crypto_sleeve.py`,
`mean_reversion.py`, `risk.py`, `session-run.ps1`,
`session-run-crypto.ps1`, `crypto-loop-worker.ps1`. A test asserts the
fingerprint changes if the haircut changes, so the check has been shown
capable of failing.

## 8. G16 — DATA ISOLATION — **PASS**

Both real research entry points refuse a `CleanObservation`, including one
nested inside a dict. The chain detects edits and deletions and
`load_sessions` refuses broken data. Limits stated in §4 of the protocol:
detectable, not impossible.

## 9. G17 — REPRODUCIBILITY — **PASS**

A record's digest recomputes exactly from its own recorded payload —
verified — so a session can be regenerated from its inputs without any
information that arrived afterwards. `as_of` pins the decision timestamp
and backfilling is prohibited by protocol.

**Honest limit:** this proves the *record* is reproducible. Proving the
*decision* is reproducible end-to-end requires replaying a live session
from stored bars, which cannot be demonstrated until clean sessions exist.
**UNVERIFIED until then.**

## 10. G18 — NO PREMATURE CONCLUSION — **PASS**

`evaluate_forward` returns a `ForwardVerdict` with exactly two possible
verdicts — `INSUFFICIENT_EVIDENCE` and `MEASURED_NO_CONCLUSION`. **The type
has no member capable of expressing profitability or superiority**, so no
data can cause the code to emit one; `may_conclude` returns `False`
unconditionally. Tested: ten sessions at +3% a day produce a cumulative
+34% and still return `INSUFFICIENT_EVIDENCE`. Annualised statistics are
withheld below 60 sessions.

## 11. FIRST DATE CLEAN EVALUATION CAN BEGIN

**Approximately 2026-10-09** — 18 further trading sessions. Resolved from
the real calendar at the time.

## 12. WHAT WILL AND WILL NOT BE SUFFICIENT

**Sufficient at ≥60 clean sessions — correctness claims:** the loop ran
every session; every position carried a stop; every exit produced a
training example; recorded equity matched the broker; realised costs sat
within the modelled band; no execution discrepancy went unrecorded.

**Not sufficient at any sample this phase can produce:** that the strategy
is profitable; that it beats the S&P 500 on return, Sharpe, Sortino or
drawdown; that the in-sample drawdown advantage persists; that the
parameters are correct.

At ~6–9% annual volatility the standard error of the return over 60
sessions is roughly 3% — larger than the entire annual edge under test. A
good quarter and a bad quarter are equally consistent with the same
strategy. **Profitability requires years.**

---

### MEASURED

857 tests green. Fingerprint `da22011e…`. Freeze 2026-09-11, derived from
the registry and agreeing with `FORWARD_START`. Embargo 20 sessions, read
from the strategy config. 2 sessions elapsed, both embargoed. **0 clean
sessions.** Production diff 0 lines across three phases. All four gates
pass. One real guard defect found and fixed.

### UNCERTAIN

The 0.652% haircut remains a frozen **bound**, not a measurement — ~30
eligible live rule exits are needed. The exact first clean date depends on
holidays. End-to-end decision reproducibility is **UNVERIFIED** until clean
sessions exist. Survivorship remains unquantified under the corrected basis.

### NOT TESTABLE YET

Everything about performance. There are zero clean observations. This phase
deliberately built the measuring instrument before looking at what it will
measure, and the instrument is constructed so that it cannot report a
conclusion it does not have the evidence to support.
