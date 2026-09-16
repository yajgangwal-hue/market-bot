# Phase 3 — forward evaluation protocol

*Effective 2026-09-16. This protocol is written BEFORE the clean evidence
exists, deliberately: rules chosen after seeing the data are not rules.*

---

## 1. THE FROZEN CONFIGURATION

Fingerprint: **`da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b`**

Computed by `forward.frozen_fingerprint()` as a SHA-256 over every frozen
parameter. If any of them moves, the fingerprint moves, and
`append_session` refuses every subsequent record.

**Entry rule:** RSI(14) ≤ 35; close > SMA(200); close ≥ $20; 20-day ADV ≥
$50M; ATR(14)/close ≤ 3.5%; warm-up 200 days.
**Exit rule:** RSI(14) ≥ 60, or a 2.5-ATR stop, or 20 sessions.
**Sizing:** 0.5% risk per trade; 20% per name; conviction 0.5–1.5×;
concentration re-clamped after conviction; 2% ADV participation.
**Risk limits:** 12 positions; one per correlation bucket; 1.5% daily and 6%
weekly loss guards; whole shares live.
**Universe:** 230 US equities/ETFs, fixed. 10 crypto pairs configured, BTC
only traded.
**Execution assumptions:** market orders; 2 bps half-spread + 4 bps
slippage one-way, both sides; $0 commission; gapped stops fill at the open.
**Haircut:** `rule_exit_timing_haircut = 0.00652`, frozen.
**Cash:** SGOV above a $2,000 floor and above the 5% crypto reserve.
**Crypto:** 5% BTC while above its 100-day average.
**Benchmark methodology:** Phase 2, unmodified — price-vs-price before
2016, total-vs-total after; strategy dividends as cash, never reinvested;
rf = 2.30%; 365.25-day annualisation.
**Embargo:** 20 sessions, read from `max_holding_bars`.
**Evaluation dates:** freeze 2026-09-11; clean evaluation begins after 20
post-freeze sessions.

## 2. THE CLEAN-DATA BOUNDARY

| | |
|---|---|
| research freeze | **2026-09-11** (EXP-0017, the last config-changing entry) |
| embargo | 20 sessions |
| sessions elapsed | 2, both embargoed |
| **clean evaluation begins** | **after 18 further sessions — approximately 2026-10-09** |

The freeze date is *derived* from the registry by `purge.freeze_date`, not
configured. Approximately, because the exact date depends on market
holidays and is resolved from the actual trading calendar at the time.

## 3. WHAT IS RECORDED, AND WHEN

One `CleanObservation` per clean session, appended once: session date,
decision timestamp (`as_of`), config fingerprint, universe size, signals,
orders, fills, positions held, exposure, cash, equity, transaction costs,
dividends received, strategy return, benchmark return, exits with reasons,
execution discrepancies, data-quality issues.

**Nothing may be backfilled.** `as_of` is the decision timestamp; a value
unavailable then does not belong in that record. A session recorded once
cannot be recorded again — `append_session` raises.

## 4. DATA-ISOLATION ARCHITECTURE

Three independent mechanisms, because any one of them can be circumvented:

1. **Type-level refusal.** Clean sessions are `CleanObservation`, not
   dicts. `reject_forward_data` is called at the top of
   `research.production_report` and `research.record_experiment` and
   recurses four levels into dicts and sequences, so an observation nested
   in a config dict is caught rather than reaching JSON serialisation.
2. **Hash chain.** Each record carries the digest of its predecessor.
   Editing or deleting any record breaks every link after it, and
   `verify_chain` reports the *first* break. `load_sessions` refuses to
   return data from a broken chain, so a caller that receives rows has rows
   nobody edited.
3. **Dataset gate.** `dataset="forward"` is accepted only with
   `purpose="forward_gate_evaluation"` (Phase 1), so a diagnostic peek
   cannot quietly spend the clean record.

**Honest limits.** The chain makes tampering *detectable*, not impossible —
nothing in a local file can be made impossible. The type refusal stops the
front door, not someone deliberately converting an observation to a dict
first. Both raise the cost from silent to loud, which is the achievable
goal.

## 5. PROHIBITIONS DURING THE EVALUATION

No parameter tuning. No feature additions. No change to entry, exit,
holding, sizing, limits, universe, execution assumptions, haircut,
benchmark methodology, evaluation dates or embargo length. No configuration
selected on forward results. **No stopping because results are unfavourable
and no restarting because they are favourable.**

**If a production bug is found:** do not silently fix and continue. Record
it separately; determine whether it affects the frozen evaluation; if it
does, **stop and restart** the evaluation with a new fingerprint. The
fingerprint check enforces this mechanically — a session produced under a
changed configuration is refused, not quietly filed.

## 6. HAIRCUT MEASUREMENT (frozen meanwhile)

The 0.652% bound stays in force for comparability. Eligible live rule exits
(`reverted` and `time_exit`) are logged with their trigger time and
realised fill. At **~30 eligible exits**, the empirical distribution is
measured and reported as a separate experiment. **Historical results are not
restated** when the measured value differs — a frozen bound that moves
retroactively is not a bound.

## 7. SURVIVORSHIP MEASUREMENT (separate, quarantined)

Survivorship is not "fixed" by choosing a kinder universe. If delisted
constituents can be obtained without touching the frozen strategy, the
effect is quantified as its own registered experiment on contaminated data.
**Its result never enters the clean evaluation** and never adjusts a forward
number.

## 8. WHAT WILL AND WILL NOT COUNT AS EVIDENCE

**Will count, at ≥60 clean sessions:** that the loop ran every session;
that every position carried a stop; that every exit produced a training
example; that recorded equity matched the broker; that realised costs sat
inside the modelled band; that no execution discrepancy went unrecorded.
**These are correctness claims and 60 sessions can settle them.**

**Will not count, at any sample this phase can produce:** that the strategy
is profitable; that it beats the S&P 500 on return, Sharpe, Sortino or
drawdown; that the in-sample drawdown advantage persists; that the
parameters are right.

**Why.** At the strategy's ~6–9% annual volatility, the standard error of
the return over 60 sessions is roughly 3%, which exceeds the entire annual
edge being tested. A favourable quarter and an unfavourable quarter are
both consistent with the same underlying strategy. **Establishing
profitability requires years, and no amount of engineering shortens that.**

`evaluate_forward` returns a `ForwardVerdict` whose type has no member
capable of expressing profitability or superiority. The refusal is
structural, not a threshold that can be lowered.
