# Research knowledge-architecture audit

*2026-09-24. Governance audit, read-only.*

**Changed:** nothing in production, the strategy, the parameters, the
models, the sealed results or Clean OOS.

**Not done:**
- the calibration — the credential is **not** rotated;
- any vendor request;
- any experiment;
- any knowledge-base restructuring — every fix in §P is **proposed, not
  made**.

**Labels:** **confirmed** — read from committed code, ledgers, preserved
data or system state today; **inferred** — reasoned from that evidence.

**Governing question.** Can the system, after clean validation and realistic
execution, produce risk-adjusted returns competitive with or superior to
SPY? **This audit does not assume it can.** The evidence below leaves that
question open, with the balance of historical evidence against the current
strategy, and only Clean OOS can settle it.

---

## A. Current authoritative production truth

Confirmed; source: `knowledge/02-production/Production Truth.md` (FROZEN)
and scheduled-task state read today.

| topic | truth |
|---|---|
| account | Alpaca **paper** only; `broker.py` refuses the live endpoint |
| entry | long-only mean reversion: price ≥ $20; 20-day dollar volume ≥ $50M; close above its 200-day average; RSI(14) ≤ 35; ATR/close ≤ 3.5%. Filled at the signal bar's close, in the last 20 minutes |
| exit | stop; then RSI(14) ≥ 60; then 20 sessions. No take-profit, trailing, partial, regime or limit exit |
| stop | 2.5 × ATR below the entry close, broker-resident GTC, never moved; coverage reconciled every cycle |
| sizing | 0.5% of equity at risk, scaled 0.5–1.5× by pullback depth; ≤ 20% notional; ≤ 2% of volume; whole shares |
| limits | 12 positions; 1 per correlation bucket; 3 new entries per day; 1.5% daily and 6% weekly loss guards |
| cash | above $2,000, parked in SGOV; 5% of equity reserved for the BTC sleeve (held while BTC is above its 100-day average) |
| inactive | learned ranker (flag off, never consulted); trade veto (flag off); news (print-only); regime (placeholder); shorting (unreachable) |
| schedules | `EventAwareTrader` (S4U) last ran 2026-09-24 13:00 local, result 0. `EventAwareTraderCleanRecorder` (S4U) 13:15, result 0. `EventAwareTraderCrypto` (Interactive), every minute, result 0 |
| fingerprint | `da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b` |

## B. Current frozen baseline

Confirmed; `baseline_metrics` on P5-0001 and P5-0038.

**+58.5889000000% over 698 trades**, on the decade window 2016-01-04 …
2026-09-04 (10.66 years):
- CAGR +4.42%;
- max drawdown −12.98%;
- volatility 9.34%;
- Calmar 0.3408;
- Sharpe 0.5107, at a **zero** risk-free rate (the research convention).

The **standing drawdown ceiling** for candidates is 1.10 × 12.9824% =
**14.2806%**, "not relaxed for any reason".

It is **in-sample on contaminated data**, and runs on a survivorship-biased
universe. It is a reference to reproduce, not validated performance.

## C. Current SPY benchmark definition

Confirmed; `knowledge/01-frozen/Benchmark.md` and the Phase 2 and Phase 3
protocols. There are two bases, and they must never be mixed.

| | historical research (decade) | Clean OOS (from the first clean session) |
|---|---|---|
| SPY series | **price only**, understated by about 1.3–1.6 CAGR points a year | **total return** (`adjustment=all`) |
| strategy side | split-adjusted prices, no dividends, idle cash at 0%, modelled costs | the account's actual return. Headline: the equity sleeve (REM-0005) |
| risk-free | 0 in research Sharpe | **2.30%, fixed** by Phase 3 §1 |
| method | — | Sharpe: daily excess, mean × 252, standard deviation × √252. Sortino: downside deviation against the daily bill rate. CAGR: 365.25 days. The same `metrics()` for both legs — **not implemented in committed code** |
| first comparison | — | checkpoint C: 60 clean sessions after the embargo |

## D. Current performance gap

Historical, in-sample only.

| measure | strategy | SPY | gap |
|---|---|---|---|
| cumulative, decade | +58.59% | +283.14% (price) | −224.55 points |
| CAGR | 4.42% | 13.42% price / 15.00% total return ¹ | −9.00 price / about −10.6 total return |
| max drawdown | −12.98% | −33.8% | the strategy is shallower |
| exposure | invested 44.28% of the time | 100% | — |

¹ The total-return window ends 2026-09-14, ten days later than the others.

**Decomposition** (`docs/phase5/timing-decomposition.json`; the H-0007
report). Market exposure while held: **+$95,566**. Selection: **+$23,836**.
Timing: **−$61,842**:
- **entries:** the entry gap is −$6,913, against $6,917 of modelled spread,
  so entries are clean;
- **exits:** the exit gap is −$54,858, and **82% of it is the deliberately
  conservative 0.652% haircut**. H-0008 found the haircut, if anything, too
  low at the adverse tail;
- **costs:** $13,868 modelled; SPY pays none.

**Survivorship** makes the true gap wider, by an unknown amount (§L).

**No matched risk-adjusted comparison exists for the current baseline.**
The pre-correction figures (EXP-0037 and EXP-0038) mix bases, and a
zero-rate Sharpe cannot be compared with SPY at 2.30%. The KB has no
automatic flag for this (§O).

## E. Current evidence quality

**Every result is historical and in-sample.**
- The six VALIDATED EVIDENCE items — EXP-0014, EXP-0015, EXP-0016, H-0017,
  H-0019, H-0021 — are all in-sample, and three of them are forensic
  classifications, not rules.
- They rest on one survivorship-biased decade dataset, now preserved and
  hash-verified.
- The thirty-year dataset is lost: 31 EXP rows, 24 P5 rows and 5
  registrations cannot be re-derived from raw data.

**Multiple testing is heavy.** About 77 exit configurations; seven regime
families; 26 RSI/stop variants in one experiment.

**Reproducibility:**
- the decade path is fully gated;
- the four intraday stores are preserved;
- H-0014's raw 5-minute bars were never retained.

**Clean OOS:** 0 sessions.

## F. Current research bottleneck

**The strategy's bottleneck is signal quality.**
- Win rate 51.2%; edge-to-noise ratio 0.0776.
- Capacity, buckets, the ATR ceiling and cash are ruled out (H-0016, H-0020,
  EXP-0025, bucket forensics).

**The largest arithmetic gap term is exposure.**
- Only 44% invested, and every lever tried to raise it failed on drawdown,
  volatility or quality (H-0006, EXP-0028, EXP-0046, H-0016, H-0020).

**The research programme's bottleneck is evidence and data.**
- Every axis reachable with existing data has been tested on one
  contaminated dataset.
- What remains needs data the project does not have: a survivorship-free
  universe, options, short interest, fundamentals, news bodies.
- The source is the 2026-09-23 value assessment, Parts 6–7, re-verified.

**Implication for the goal (inferred).** The evidence does not show a
pathway to SPY-competitive returns through tuning this strategy. A
competitive system, if one exists, would need either:
- evidence that the true edge is larger than the conservative modelling
  shows — live exit drift, Clean OOS; or
- a genuinely new, orthogonal information source validated on
  survivorship-safe data.

## G. Current exit evidence

**Closed families** (the "Do Not Re-Research" register):

| family | tests | result |
|---|---|---|
| trailing stops | EXP-0036, H-0001, P5-0007 | rejected |
| fixed take-profit | EXP-0049/0050, H-0002, P5-0008/0014, H-0010 | conflicting ledgers (AMB/CONF); return falls as the target tightens |
| breakeven lock | H-0003, H-0005 | SPIKE (non-monotone), rejected |
| partial exits | H-0004 | rejected |
| RSI exit level | EXP-0023, EXP-0006 | rejected |
| holding period | EXP-0019, EXP-0024 | rejected |
| regime-conditioned exits | EXP-0036, EXP-0051/0052 | rejected / measured |
| stop width | EXP-0022, H-0010 | rejected |
| give-back | H-0021 (A: the population exists) and H-0025 (weak) | closed twice |
| execution | H-0008 rejected; H-0011/12/13 inconclusive; H-0017 A (narrowed); H-0018 B | — |

**Give-back facts:** 81.2% of +2% crossers go on to a higher executable
gain, and the ATR at crossing is *positively* associated with the outcome
(IC +0.199, 3/3 thirds).

**Post-stop behaviour:** +0.339% is **B — INCONCLUSIVE**. The confidence
interval spans zero, it reverses by 20 sessions, and removing 5 of 128
symbols flips its sign. **It is not a lead.**

**The only family never tested as a rule: volatility-triggered exits.** Its
causal rationale is contradicted by H-0025 (higher volatility predicts a
*better* outcome), and the family already carries about 77 configurations.

**EXP-0048's "exit at the high" is a hindsight ceiling.** It is never a
recommendation.

## H. Current regime evidence

**Regime conditioning has not improved expected returns in any test:**
- regime filter (EXP-0009) — rejected;
- regime exits (EXP-0036) — rejected;
- down-market gate (EXP-0042/0043) — **reversed**: down-market entries do
  better;
- near-high skip (EXP-0044) — rejected;
- regime size tilt (EXP-0045/0047) — worse on both axes;
- low-volatility abstention (H-0007) — rejected.

**P5-0022:** the strategy annualises +3.74% with SPY above its 200-day
average and +9.81% below, and it "underperforms SPY in EVERY regime state".
The timing drag is roughly constant across regimes.

Regime changes **exposure**, not edge. In production it is only a
placeholder.

## I. Current news evidence

- **Launch-day buying** (EXP-0040/0041) — rejected.
- **Every news entry filter** (P5-0011 … 0013) made the account worse. The
  earnings filter was indistinguishable from an any-news control.
- **The earnings-headline separation** (P5-0006) — inconclusive.
- **The economic test is data-blocked** (H-0022's D): it needs article
  bodies, true availability timestamps and revision provenance.
- **Live:** news is collected but print-only.

## J. Current ML / model status

**Live ranker:**
- UNPROVEN; never consulted (`LEARNED_RANKING_ENABLED = False`,
  `live_model_floor = 0.0`);
- promotion requires a record naming the exact model;
- it is **retrained at every session close**. The latest was
  2026-09-24T19:45:53Z (SHA-256 `e8986dcd…`).

**Trade veto:**
- UNPROVEN; `LEARNED_VETO_ENABLED = False` is its **only** barrier, because
  its trainer labels it `USABLE_AS_VETO` itself.

**Evidence:** EXP-0029 rejected the veto. It loses money monotonically, and
its AUC of 0.5501 on the full fit falls to 0.5056 walk-forward — it predicts
nothing out of sample.

**Governance gaps:**
- retrains are absent from `model-lineage.jsonl` (3 rows, the latest
  2026-09-16) and from the audit log;
- neither switch is in the fingerprint;
- the pre-Clean-OOS snapshot exists (`docs/model-state/…`), and the live
  ranker file has changed since it was taken.

## K. Current data gaps

| gap | status |
|---|---|
| thirty-year dataset | lost |
| survivorship-free, point-in-time universe | unavailable (H-0023: D) |
| H-0014 raw 5-minute bars | never retained |
| acquisition code of the 239 stop-exit sessions and of the SPY store | unknown |
| H-0008 intraday store | gone |
| news archive | an external pull, unpreserved and unhashed |
| `data/phase5/` derived files | unhashed |
| options, short interest, fundamentals with restatement history | absent |
| strategy-side dividends | not modelled |
| vendor feed | never explicit (inferred SIP) |
| off-machine backup of research data | none |
| **vendor access** | **blocked until the exposed credential is rotated** |

## L. Current survivorship limitation

- **The universe** is 230 of **today's** survivors.
- **The pre-correction bound** (EXP-0031, measured): on the survivorship
  control, the main rule's CAGR falls **9.14% → 3.82%** (decade) and
  **5.66% → 2.24%** (thirty years). It stays positive in both halves.
- **The true size is unknown.** H-0023 (D) found the point-in-time universe
  cannot be reconstructed reliably.
- **Consequence:** every universe-wide historical result is inflated by an
  unknown amount. **Any new signal must pass the ETF-subset control.** The
  project's own record has a "23.6%/yr" book that became −1.5% there.

## M. Current Clean OOS status

| item | state |
|---|---|
| clean sessions | **0**, chain intact |
| freeze / embargo | 2026-09-11 / 20 sessions |
| first clean session | projected **2026-10-12** |
| checkpoints | A = 1, B = 20 (integrity only), **C = 60** (the first performance report, about early January 2027), D = 120. No end date |
| recorder | S4U, ran today with result 0 |
| `benchmark.py` | guarded: reports nothing before 60 clean sessions |
| unresolved before C | the rf-2.30% metrics implementation; the learned switches outside the fingerprint; retrains outside lineage |

## N. Current knowledge-base strengths

All confirmed by the validator: 8 checks, deterministic, PASS today.

- **Explicit, machine-readable authority** on every note: 10 levels.
  Counts: FROZEN 8, VALIDATED EVIDENCE 6, MEASUREMENT 12, INCONCLUSIVE 24,
  REJECTED 75, REMEDIATION 9, OPEN QUESTION 1, NORMATIVE 3, NAVIGATION 12.
- **"NOT A PRODUCTION RULE"** is enforced on every non-frozen result (119
  notes).
- **Production Truth may not link a REJECTED, INCONCLUSIVE, MEASUREMENT or
  HISTORICAL note.**
- **Anchored citations:** 428 verbatim quotations anchor-checked; 32 code
  citations symbol-checked; every H/EXP/P5/REM identifier resolves; generated
  notes must equal their builder output.
- **The "Do Not Re-Research" register:** 22 areas, each with ledger
  outcomes, configuration counts and data scope. It explicitly marks what was
  **never** tested.
- **Other registers:** conflicts and ambiguities; dataset registry, gate and
  manifests; a twelve-rule agent protocol.

## O. Knowledge-base weaknesses

Against the requested architecture:

| requested | exists? | gap |
|---|---|---|
| 00 governance: Home, Agent Instructions, Authority Levels, Provenance | yes | — |
| Research Constitution, Production Change Rules, Experiment Lifecycle, Evidence Standards | **scattered** across the Agent Instructions rules, SPEC-0001 C-26/27 and the registrations (110% ceiling, both halves or thirds, 2-point complexity penalty, `max_configurations`) | no single normative statement |
| 01 frozen (strategy, parameters, fingerprint, baseline, benchmark, Clean OOS) | yes | — |
| 02 production (truth, non-conformances, safeguards) | yes | runtime, risk and exposure rules folded into Production Truth. The hand-written snapshot is dated 2026-09-23, and freshness is not machine-checked against `src/` commits |
| 03 research: index, hypotheses, experiments | yes (generated) | **no model registry** (§J); no research-dependency map; the evidence map is thin |
| 04 results by class | as authority labels | adequate. Grouping is not needed if the labels are enforced |
| 05 do-not-research | yes | **no per-area reopening conditions** |
| 06 open questions | one note | **not the required structure**: hypothesis, rationale, data, leakage, sample size, preregistration, success and failure criteria, production eligibility, closing evidence. The structured table lives in a doc (the 2026-09-23 assessment, Part 5), not in the KB |
| 07 data | Datasets note and registry | **no permitted or forbidden uses; no survivorship status; incomplete timestamp conventions**. Derived and live datasets (`data/phase5/`, live training, trade examples, news) are not registered or hashed |
| 08 models | **absent** | — |
| 09 decision system | SPEC-0001 plus Production Truth | **no stage-by-stage pipeline** with inputs, outputs, allowed information and leakage risks |
| 10 benchmarks | the Benchmark note | **no separate metric definitions; no automatic incompatible-comparison flag** |

**Other weaknesses:**
- **Missing evidence.** The **performance-gap decomposition** (§D) and the
  two recurring failure signatures — "per-trade quality improves, the
  portfolio gets worse" and survivorship inflation — are **not in the KB**.
- **Unregistered forensic passes** (post-stop, breadth, bucket, regime
  forensics) appear only through the Reports Catalogue. An agent could cite
  their numbers without the classification.
- **Missing validator checks:**
  - a dataset with no hash;
  - a model with no lineage;
  - an experiment with no preregistration;
  - an unauthorised dataset or a permitted-use violation;
  - a Clean OOS result used in development;
  - a stale production document;
  - an incompatible benchmark comparison;
  - an unsourced numeric claim in hand-written notes.

  Quotations are checked only when they are quoted.
- **Nothing is committed:** the vault and all of today's governance work
  (38 working-tree entries).

## P. Required governance fixes

**Proposed, not made.** Each needs authorization. In priority order:

1. **The owner rotates the exposed Alpaca credential.** It blocks all
   vendor work.
2. **Commit** the knowledge base and today's governance work: the dataset
   gate, registry, manifests, migration and preservation records. The owner
   decides.
3. **The Clean OOS metrics.** Implement the frozen method (rf 2.30%) as a
   research-side script before checkpoint C, and test it on synthetic data
   only.
4. **Model governance:**
   - append a lineage row for every retrain (dataset hash, model hash, code
     commit, example count, metrics, deployment status);
   - have every checkpoint verify both learned switches.

   Moving the switches into the fingerprint or removing the trainer's
   self-labelling touches `src/`. That needs owner approval and a money-path
   review, and must not change the fingerprint mid-phase unless it is
   treated as a defect.
5. **Validator extensions** (fail-closed, deterministic):
   - dataset hash;
   - model lineage;
   - preregistration seal;
   - dataset permitted use (from new registry fields);
   - Clean OOS isolation (no research output derived from
     `forward-evaluation.jsonl`);
   - production-document staleness (the snapshot versus the last `src/`
     commit);
   - benchmark comparisons carrying declared basis, period, dividends, rf,
     costs, cash and exposure;
   - unsourced numeric claims in hand-written notes.
6. **Consolidate, rather than add, notes:**
   - one normative **Research Constitution**: evidence standards, lifecycle,
     production-change rules, drawdown ceiling, thirds, complexity penalty,
     Clean OOS use;
   - a generated **Model Registry**;
   - a generated **Decision Pipeline** from SPEC-0001;
   - **benchmark metric definitions** split from the Benchmark note;
   - **reopening conditions** added to every closed area;
   - **structured open questions**;
   - **the gap decomposition and failure signatures** as a MEASUREMENT note;
   - **registry fields** for permitted and forbidden use, survivorship and
     timestamp convention.
7. **A machine-readable research scoreboard**, generated from the ledgers:
   baseline → candidate → incremental return, risk, Sharpe/Sortino,
   drawdown, turnover, costs, exposure, uncertainty, regime and thirds
   stability, OOS status, reproducibility, promotion.
   - **"unknown" is written where a ledger never recorded a field.**
   - **No single score.**
8. **A documented opportunity-review procedure.** It excludes rejected,
   duplicate, contaminated, data-blocked and equivalently tested ideas, and
   outputs candidates only. It is never auto-run.

## Q. Highest-information-value open research areas

Ranked by expected information value × plausible economic impact × ability
to validate cleanly. **None is authorised by this list.**

| rank | area | why | constraint |
|---|---|---|---|
| 1 | **Clean OOS accumulation** under the frozen fingerprint | the only uncontaminated evidence; can falsify the strategy | protect it; no redesign against it |
| 2 | **A survivorship-free universe** (data licensing) | measures the true edge; EXP-0031 suggests historical figures may be roughly halved | the owner's licensing decision; measures rather than improves |
| 3 | **Live exit drift against the 0.652% haircut** (Phase 4 §7) | 82% of the timing drag is this modelling charge; live exits measure it cleanly | measurement beside the frozen bound, never replacing it during the phase |
| 4 | **The Clean OOS benchmark implementation** | no valid SPY comparison is possible without it | engineering, not research |
| 5 | **Orthogonal new information**: options implied volatility and skew, short interest, point-in-time fundamentals, news bodies with availability timestamps | the only untested signal classes | all data-blocked; each needs survivorship-safe, point-in-time data and preregistration |
| — | **The exposure deficit** | the largest gap term | **no candidate exists**: every tested lever is closed. Open as a problem, not as a hypothesis |

**Not open:**
- exit families (§G), regime (§H) and news filters (§I);
- the ML veto (EXP-0029), crypto (EXP-0003/0032–0035) and shorting;
- intraday information (H-0014 B: an IC increment of about +0.006);
- volatility-triggered exits (the rationale is contradicted).

## R. Exact next authorized action

**Owner action.**
1. Regenerate the Alpaca **paper** API keys in the Alpaca dashboard; this
   revokes the exposed pair.
2. Run `scripts\windows\setup-keys.ps1` and enter the new keys **at its
   prompts, never in chat**.
3. Tell me it is done.

**Then, and only then, I will:**
1. re-verify: names present, and `HKCU\Environment` written after
   2026-09-19T18:47:20Z;
2. get your confirmation;
3. run **only** the 12-session calibration (plan Revision 2, §R2.1:
   A1/A2, fixed sample rule, stop after classification).

## S. What must not be done

- **No vendor requests** until the credential is rotated and verified.
- **No full reacquisition** without an A calibration **and** its own
  authorization.
- **No H-0014 analysis or IC; no performance statistic.**
- **No change to sealed results, seals, registrations or preserved
  datasets.**
- **Never label reacquired data as the original H-0014 raw data.**
- **No strategy, parameter, execution or benchmark change** during the
  Clean OOS phase.
- **No inspection of Clean OOS results before checkpoint C, and no
  redesign against them.**
- **Nothing reaches the money path because a research note or an AI finds
  it promising.**
- **No reopening a closed family under a new name.** Carry its
  configurations into the multiple-testing burden.
- **No parameter sweeps; no best-of selection after results.**
- **No "beat SPY" claim without a matched comparison** (same period,
  dividends, risk-free rate, costs, cash, exposure).
- **No model enters production on training scores.** "Predicts something"
  is not "improves executable returns".
- **No credential value** printed, logged, stored or put into the knowledge
  base.
