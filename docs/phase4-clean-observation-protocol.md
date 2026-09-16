# Phase 4 — clean observation protocol

*Effective 2026-09-16. Written before any clean observation exists, which
is the only time a protocol can be written honestly: rules chosen after
seeing the data are not rules.*

The purpose of this phase is to observe the frozen strategy on genuinely
unseen data **without allowing the observations to change the experiment**.
Nothing in this document produces a verdict, and the machinery it describes
is built so that it cannot.

---

## 1. WHEN RECORDING BEGINS

Derived from the real trading calendar at run time, never hard-coded.
`forward.first_clean_session()` asks `purge.evaluation_window()`, which
takes the freeze date from the experiment registry and the embargo length
from the strategy's own holding cap.

| | |
|---|---|
| research freeze | **2026-09-11** — the registry's last config-changing entry (EXP-0017) |
| embargo | **20 sessions** — `MeanReversionConfig.max_holding_bars` |
| sessions elapsed since freeze | **2** (2026-09-14, 2026-09-15) |
| sessions remaining under embargo | **18** |
| last embargoed session | 2026-10-09 |
| **first clean session** | **2026-10-12**, projected |

**A correction to the Phase 3 report.** That report gave "approximately
2026-10-09" as the date clean evaluation begins. 2026-10-09 is the
*twentieth embargoed* session; the first session admissible as evidence is
the one after it. The code was always right — `evaluation_window` returns
`after[horizon]`, which is the twenty-first — and the prose was wrong. The
projected date assumes no market holiday intervenes, and none falls in this
window; the recorder resolves the true date from the calendar regardless.

Sessions before that date are refused by the recorder, not filtered later.
**Nothing is backfilled**: a session the recorder did not capture stays a
hole in the record, counted and named.

## 2. WHAT IS RECORDED

One `CleanObservation` per clean session, appended once. Session date,
decision timestamp, fingerprint, universe size, signals, orders, fills,
positions held, **per-name position sizes**, exposure, cash, equity,
transaction costs, dividends received, strategy return, benchmark return,
exits with reasons, execution discrepancies, data-quality issues.

**Every field is traced to a source.** Signals and exits come from the
loop's own audit log; orders, fills, fees and dividends from the broker's
activity feeds; equity, cash and positions from the account; the benchmark
from the same day's bar. **Where a source is missing the recorder refuses
rather than writing a zero** — a fabricated zero is indistinguishable from
a true one once it is in the record.

The recorder runs **separately from the trading loop**, deliberately.
`session-run.ps1` and `autotrade.py` are in the frozen set, so wiring the
recorder into them would break the freeze it exists to protect.

## 3. PER-SESSION VERIFICATION

`verify_session.verify()` runs eleven checks against the broker and the
frozen rules: protection on every position, orders within the universe,
whole-share orders, concentration cap, position-count limit, participation
limit, recognised exit reasons, equity reconciliation, cash reconciliation,
transaction costs, dividends, benchmark date, decision-timestamp coherence.

Each returns **PASS, FAIL or UNVERIFIED**. The third state is the point: a
check that could not run must not report health. An UNVERIFIED check does
not fail a session, but it is counted and named, so a session verified
mostly by UNVERIFIED cannot be mistaken for a clean one.

**A discrepancy is reported and never corrected.** Adjusting a recorded
figure so it agrees with the broker destroys the only evidence that
something upstream is wrong.

**One protection check is stricter than it looks.** Alpaca reserves shares
against *any* resting sell, so a bracket's take-profit limit leg makes a
position look covered. It protects nothing on the way down.
`forward.is_protective()` counts only an order with a stop.

## 4. RECONCILIATION TOLERANCES (G20)

Documented in advance, in `forward.py`, not chosen when a gap appears.

| field | tolerance |
|---|---|
| equity | $1.00 **or** 1 basis point, whichever is satisfied |
| cash | $1.00 or 1 basis point |
| positions held | **exact** |
| transaction costs | $0.01 against the broker's fee feed |
| dividends | $0.01 against the broker's dividend feed |

Equity is compared both absolutely and relatively because a $1 gap on
$100,000 and a $1 gap on $10 are different claims. Counts have no tolerance:
there is no sensible margin on *how many positions do we hold*.

## 5. PROHIBITIONS

No change to parameters, RSI thresholds, SMA periods, ATR limits, holding
periods, sizing, risk limits, universe, indicators, the haircut, benchmark
methodology, evaluation dates or embargo length. No configuration selected
on forward results. **No stopping because results are unfavourable and no
restarting because they are favourable.**

A poor clean result is evidence. A good clean result is not permission to
optimise.

**If a production defect is found:** record it separately, determine whether
it invalidates the frozen evaluation, and stop and restart with a new
fingerprint if it does. The fingerprint check enforces this mechanically —
a session produced under a changed configuration is refused, not filed.

## 6. CHECKPOINTS

`scripts/phase4_checkpoint.py`. A checkpoint below its threshold is **not
produced**: an early report on a thin sample is precisely how an experiment
gets stopped on a convenient quarter.

| | sessions | scope |
|---|---|---|
| **A** | 1 | confirm the embargo genuinely expired and the first observation is clean |
| **B** | 20 | infrastructure and data integrity only — no performance interpretation |
| **C** | 60 | correctness acceptance plus a descriptive performance report |
| **D** | 120 | repeat the descriptive report and compare stability |

Every report separates **MEASURED**, **ASSUMED**, **UNCERTAIN** and
**UNSUPPORTED BY THIS EVIDENCE**. The isolation suites are re-run at each
checkpoint and their results printed into the report, so data integrity is
established at the checkpoint rather than remembered from the phase start.

## 7. HAIRCUT MEASUREMENT

`scripts/haircut_observations.py` collects eligible live rule exits —
`reverted` and `time` only. A `stop` exit is excluded: its slippage is a
different quantity, and pooling them would flatter whichever is smaller.

The frozen **0.652%** bound does not move during this phase. Below ~30
paired exits the sample size is reported and the distribution is not. When
the sample arrives, the observed median, mean, percentiles and range are
reported **beside** the frozen bound, never in place of it: historical
results are not restated, and replacing the bound would be a separately
reviewed methodological change.

**Current count: 0.** Exits logged before the loop recorded a trigger price
are skipped rather than guessed at.

## 8. THE GATES

| | claim | how it can fail |
|---|---|---|
| **G19** | every accepted observation satisfies the fingerprint, timestamp, append-only and isolation rules | a foreign fingerprint, a duplicate session, an edited record, a clean observation reaching research |
| **G20** | recorded equity, positions, cash, fills and costs reconcile within the documented tolerances | any field outside tolerance; counts differing at all |
| **G21** | no clean decision depends on information available only after its decision timestamp | `as_of` in the future or before its session; a benchmark bar from another day |
| **G22** | the evaluation is not stopped, restarted or altered because of observed performance | a missing eligible session; a session recorded before eligibility |
| **G23** | the frozen strategy and benchmark methodology are unchanged | the fingerprint moving from `da22011e…` |

**A failed gate stops acceptance and requires investigation. The gates are
not modified to make a failure disappear.** Each is tested in both
directions: `tests/test_phase4_observation.py` contains, for every gate, at
least one test that makes it fail — a gate never seen to fail has not been
shown to be a gate.

## 9. WHAT THIS PHASE CAN AND CANNOT SETTLE

**Can, at ≥60 clean sessions — correctness:** the loop ran every session;
every position carried a stop; every exit produced a training example;
recorded equity matched the broker; costs sat inside the modelled band; no
execution discrepancy went unrecorded; the fingerprint held; isolation held.

**Cannot, at any sample this phase can produce:** that the strategy is
profitable; that it beats the S&P 500 on return, Sharpe, Sortino or
drawdown; that the in-sample drawdown advantage persists; that the
parameters are correct.

At ~6–9% annual volatility the standard error of the return over 60
sessions is roughly 3% — larger than the entire annual edge under test. A
good quarter and a bad quarter are equally consistent with the same
strategy. **Establishing profitability takes years, and no amount of
engineering shortens that.**
