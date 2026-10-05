# Does the knowledge base improve the ability to build a better strategy?

*Assessment, 2026-09-23. Read-only with respect to trading: no strategy,
parameter, baseline, benchmark or Clean OOS change; no backtest run; no
registration; no dataset read recorded. Five knowledge-base notes were
corrected or extended during the audit — listed at the end — and the vault
validates after them.*

**Short answer.** The knowledge base does not change profitability and cannot:
it is not in the money path. Its demonstrated value is narrower than "better
research": it makes the prior-trial record, the frozen state and the known
conflicts retrievable in one place, and the repository contains real failures
of exactly that kind. Whether that ever leads to a validated improvement is
**not demonstrated**, because the constraint on this project is evidence and
data, not memory — and with the data that exists, **no new research candidate
is justified**.

---

## Part 1 — The authoritative baseline

### The frozen strategy

Long-only mean reversion over 230 US equities and ETFs: buy when RSI(14) ≤ 35,
the close is above its 200-day average, price ≥ $20, 20-day dollar volume ≥
$50M and ATR/close ≤ 3.5%; fill at the signal bar's own close in the last 20
minutes; exit on a fixed 2.5×ATR stop, RSI(14) ≥ 60, or 20 sessions. Risk 0.5%
per trade, conviction-scaled 0.5–1.5×, 20% notional cap, 12 positions, one per
correlation bucket, three entries a day. Idle cash is parked in SGOV live; a 5%
BTC sleeve is a separate book. Paper account only.
Source: `knowledge/01-frozen/Frozen Strategy.md`, generated values in
`Frozen Parameters.md`, code in `src/event_aware_trader/`.

**Fingerprint:** `da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b`.

### The frozen baseline — decade window 2016-01-04 … 2026-09-04 (10.6639 years)

Source of record: `baseline_metrics` in `docs/phase5-research.jsonl`, dataset
labelled there "decade (contaminated)".

| metric | value |
|---|---:|
| cumulative return | +58.5889% |
| CAGR | 4.4248% |
| annualised volatility | 9.3372% |
| Sharpe (risk-free rate 0; `evaluation._ratio`) | 0.5107 |
| Sortino | 0.7221 |
| maximum drawdown | −12.9824% |
| Calmar | 0.3408 |
| trades | 698 |
| win rate | 51.15% |
| exposure | 44.28% |
| modelled transaction costs | $13,868 on $100,000 |
| idle cash | earns 0% in this figure |

### The benchmark and the comparison

| item | finding | source |
|---|---|---|
| benchmark | SPY | `docs/benchmark-units.md` |
| historical comparison basis | **price vs price.** The decade data has no dividend adjustment on either side: SPY's first close in the research data is 201.0192, the unadjusted 2016-01-04 print, and 201.0192 → 770.19 is the documented 3.8314× | benchmark-units.md; the dataset itself |
| forward (Clean OOS) basis | **total return vs total return**: SPY fetched with `adjustment="all"` | REM-0003; `record_clean_session.py`; fingerprint block `basis_post_2016: total_vs_total` |
| comparison period | 2016-01-04 … 2026-09-04 | benchmark-units.md |
| SPY price return | +283.14% cumulative, 13.42% CAGR | benchmark-units.md |
| SPY total return | 15.00% CAGR, window to 2026-09-14 | EXP-0037 (SPY side only) |
| SPY decade max drawdown / Calmar | −33.8% / 0.45 | EXP-0038 (SPY side only) |
| gap vs SPY price | −224.55 points cumulative; −9.00 CAGR points a year | benchmark-units.md |
| gap vs SPY total return | ≈ −10.6 CAGR points a year (windows end ten days apart; not registered) | derived from the two rows above |

**Is the comparison directly comparable? No.** The baseline holds idle cash at
0% (the live account parks it; no post-correction *decade* figure with the
overlay exists in the ledgers); the strategy pays modelled costs and SPY pays
none; the strategy is invested 44% of the time; the strategy's universe is
today's survivors and SPY is not; and the historical basis omits dividends on
both sides, which understates SPY by 1.3–1.6 CAGR points a year while the
strategy's own forgone dividends are unmeasured.

**Do not use EXP-0037/EXP-0038's strategy figures** (for example "~9.9%
parked"). They are dated 2026-09-14, before EXP-0054 (2026-09-16) recorded that
every earlier figure was overstated by roughly 2.6 points.

**On current numbers the strategy does not win on Calmar either.** 0.3408
against SPY's decade 0.45. It wins on absolute drawdown (−12.98% against
−33.8%) and on volatility. The research-gap inventory's "Calmar 0.75 vs 0.45"
does not match the ledger; its source is unverified (recorded as AMB-6).

### Clean OOS

**0 sessions.** Embargo 8 of 20 sessions elapsed on 2026-09-23; first clean
session projected 2026-10-12, resolved at run time. The recorder's scheduled
task was observed running as S4U on 2026-09-23; the last committed audit still
records NOT READY on that item (CONF-9).

### Evidence classes, kept apart

| class | what it contains | status |
|---|---|---|
| historical research | 187 configurations in `experiments.jsonl`, 64 declared across 24 registrations, 39 phase-5 executions, all on one decade of one survivor universe (plus a thirty-year window) | **contaminated / in-sample** — may reject an idea, never accept one (`research.PURPOSES`) |
| contaminated reads | decade read 149 times, thirty-year 13 times (`dataset-uses.jsonl`, working tree) | recorded |
| Clean OOS | none | **0 sessions** |
| live / paper | 24 entries in `data/autotrade-audit.jsonl`, 2026-09-01 … 2026-09-23 | inside the embargo, paper, not a sample — **not evidence** |

### A reproducibility finding made during Part 1

The decade price data is **not in the repository**. Research scripts find it by
globbing Claude session scratchpads in the OS temp directory
(`scripts/forensics_regime.py`, and at least 17 other scripts). On 2026-09-23
exactly one copy existed; the thirty-year `long/` dataset was **absent**. No
content hash of either price dataset is recorded anywhere. If that directory is
cleaned, the frozen baseline cannot be re-derived and no thirty-year result
can be reproduced.

---

## Part 2 — What the knowledge base changes

The knowledge base changes no trading behaviour. Nothing has yet been
researched *with* it — it is one day old — so most effects cannot be
demonstrated in use.

| # | effect | classification | evidence |
|---|---|---|---|
| 1 | research deduplication | **plausible but unproven** | `Do Not Re-Research` groups every ledger's items by area in one table. The repository's worst deduplication failure (Part 3, #3) was a three-ledger split — exactly what that grouping removes. Not yet used on a new hypothesis |
| 2 | hypothesis generation | **no meaningful effect** | it indexes existing information and creates none. Part 10 finds no candidate with or without it |
| 3 | rejection of already-tested ideas | **plausible but unproven** | the map lists what was tested and what it showed; it states that rejected is not "impossible" |
| 4 | prevention of repeated failed experiments | **plausible but unproven** | the uncited re-tests in Part 3 (#1, #2) would have appeared on the same page as their predecessors. That is a counterfactual |
| 5 | identification of genuine gaps | **demonstrated, narrowly** | building and auditing it surfaced two things not previously recorded as gaps: volatility-triggered exits were **never tested as a rule**, and the research data sits outside version control. The gap register otherwise inherits the 2026-09-21 inventory |
| 6 | preservation of implementation knowledge | **demonstrated** | `Frozen Parameters` is generated from the code with declaration lines, and the validator fails if it drifts; `Production Truth` states the live stop behaviour from code, which exposed a stale "ratchet" comment in `stop-everything.ps1` |
| 7 | prevention of misunderstandings | **detection demonstrated; prevention unproven; one negative instance** | 9 conflicts and 7 ambiguities recorded with both sides quoted. But the vault's own first Benchmark note said "SPY, on total return" without qualification — a misunderstanding of exactly the EXP-0037 kind — and it survived validation until this audit. Paraphrase is not machine-checked; only quotations are |
| 8 | prevention of research-to-production contamination | **no meaningful effect** | the controls live in code — `reject_forward_data`, the dataset gate, the fingerprint refusal, preregistration. The vault documents them and enforces none of them |
| 9 | reproducibility | **no meaningful effect on research reproducibility; demonstrated in exposing a risk** | the vault itself is reproducible (builder, validator, 398 checked quotations). Research reproducibility is set by the seals, runners and data — and the data is the weak point it exposed |
| 10 | future agents understanding the strategy | **plausible, partly tested** | Part 11: 8 of 10 questions answered accurately from the vault as built, 9 of 10 after today's correction. The test is not independent — the same agent built the vault |

**Negative or limiting effects, stated plainly:** it is a second place facts
live, so it can go stale (hand-written notes are snapshots); its authority
classification is an interpretive layer (for example H-0017 at VALIDATED
EVIDENCE despite a label discrepancy, H-0016 at REJECTED); a "do not
re-research" map can deter legitimate re-examination if read as a ban; and
maintenance is a recurring cost.

---

## Part 3 — Did the knowledge base address problems that actually happened?

Every incident below is verified in the repository. "Would it have prevented
it" is a counterfactual and is labelled as one.

| # | incident | kind | how it was found | would the vault have prevented it? |
|---|---|---|---|---|
| 1 | H-0001 registered a trailing stop citing no prior experiment; EXP-0036 had tested trailing stops three days earlier | failed to identify a related experiment | research-gap inventory, 2026-09-21 | **would have surfaced it** — both sit in one row group. The re-test on the corrected emulator may itself have been legitimate; the missing citation was not |
| 2 | H-0010 tested a take profit citing none of EXP-0049/0050 or H-0002 | same | this audit | **would have surfaced it** |
| 3 | the exit family's multiple-testing burden was stated as 54 configurations; the true count is ~77, because the family spans three ledgers. A mechanism considered in H-0021's design "was already registered and already run" | duplication; failed identification | the inventory corrected itself | **the strongest case** — the cross-ledger grouping and per-row configuration counts address it directly |
| 4 | H-0017 called H-0011 "rejected"; H-0011's own record is INCONCLUSIVE | misunderstood a prior result | building the vault | **would have surfaced it** — the H-0011 note quotes its decision |
| 5 | H-0021 described its next-open price as what the frozen mechanism assumes; the frozen mechanism fills at the signal close | implementation vs research confusion | H-0025 | **would have surfaced it** — `Frozen Parameters` shows `entry_fill = 'signal_close'` read from code |
| 6 | "The 8.55% benchmark quoted all week was price return" (EXP-0037) | benchmark misunderstanding | self-corrected | **not reliably** — the vault's first Benchmark note repeated a version of this error |
| 7 | P5-0008 recorded the highest-return configuration instead of the one that passed (corrected by P5-0014) | recording error | P5-0014 | no — ledger-writing error |
| 8 | H-0011's first run breached the 20-bar cap and was discarded | implementation defect | in-run check | no |
| 9 | the simulator credited rule exits a close they never got; earlier figures overstated ~2.6 points (EXP-0054) | implementation vs research | Phase 1 audit | no — code. The vault now caveats 48 of 53 experiment notes |
| 10 | the emulator's RSI exit saw today's close and the live loop did not | implementation vs research | H-0024 → fidelity audit | no at the time; now recorded (SPEC-0001, REM-0009) |
| 11 | the runner passed `--interval 15m`; the fingerprint hashed defaults (REM-0001) | implementation | governance audit | no |
| 12 | H-0022 filed under an H-0019 filename, never registered | naming/provenance | the report itself | **plausibly** — the index shows the next free identifier |
| 13 | EXP-0053 missing, referenced nowhere | numbering | building the vault | no — recorded only |
| 14 | README, START-HERE, GO-LIVE and `stop-everything.ps1` describe a strategy that is not the frozen one | stale documentation | building the vault | flagged now. **No evidence** that any research acted on them |
| 15 | the inventory's "Calmar 0.75 vs 0.45" does not match the ledger's 0.3408 | stale number | this audit | **no, as built** — the vault's baseline page did not list Calmar until today |
| 16 | H-0015 found the code contradicted its sealed methodology | code vs methodology | the §14 gate | no |
| 17 | unit tests wrote synthetic rows into the live audit log (REM-0008) | test hygiene | audit | no |
| 18 | research data outside version control; thirty-year data absent | provenance | this audit | no — detected, not preventable by documentation |

**Quantified.** 18 incidents. **9** are information-retrieval failures of the
kind a vault addresses (#1–6, #12, #14, #15); of those, **7** would have been
visible in it (#1–5, #12, #14), **1** it repeated (#6) and **1** it lacked (#15).
**9** are code, recording, test or infrastructure defects that no documentation
prevents (#7–11, #13, #16–18).

**What none of them did:** change a production decision. Every
information-retrieval failure cost trials, time or accounting accuracy; none
put a worse rule into the money path. The one incident that did affect live
behaviour (#10) was an implementation defect, found by an audit, not by memory.
So the vault's counterfactual value is in **trial accounting and error
prevention**, not in recovered profit.

---

## Part 4 — The indirect chain

*better research memory → better hypothesis selection → fewer wasted
experiments → greater probability of discovering a valid improvement*

**Proven by the repository**

- Research-memory failures occurred (Part 3, #1–5).
- The exit family's multiple-testing burden was undercounted by ~23
  configurations because it spans three ledgers; the vault enumerates them.
- The trial record is large and all of it is on one contaminated dataset.
- No accepted configuration change since the 2026-09-11 freeze; every
  hypothesis since has been non-promotional.
- The inventory's own verdict: "No research direction currently available with
  existing data is strong enough to justify a new experiment", and "The binding
  constraint on this project is no longer *information*. It is **evidence**."

**Plausible, not measured**

- Accurate prior-trial counts give honest multiple-testing hurdles, so fewer
  false discoveries reach validation.
- Fewer redundant experiments limit trial-count inflation, which preserves the
  chance that a genuinely new, preregistered test can clear its hurdle.

**Unknown**

- Whether any valid improvement exists to be found.
- Whether new data (options surfaces, a survivorship-free universe, news
  bodies) holds any edge.
- Whether Clean OOS will confirm even the baseline's edge.

**The chain breaks at its last link.** Memory reduces waste; it does not add
information. The repository's own account of the constraint — evidence and
data — is something a knowledge base cannot supply.

---

## Part 5 — Areas that are genuinely still open

No ranking. Listed in the order of `Research Gaps.md`. None is a proposal.

| area | prior research | why not closed | required data | information boundary | survivorship | leakage risk | validation | Clean OOS required? | could affect |
|---|---|---|---|---|---|---|---|---|---|
| survivorship-free universe | EXP-0031 (bounded, pre-correction), H-0023 (D) | the point-in-time universe could not be reconstructed | delisting-complete security master; delisting reason and terminal value; point-in-time symbol mapping (H-0023 §G) | membership as of each date | this *is* the survivorship question | terminal-value assumptions | a registered re-measurement of the baseline | no — it measures history, and would resize the baseline rather than change the rule | the measured edge, not the rule |
| news information | EXP-0040/0041, P5-0006, P5-0011 … 0013, H-0022 | the economic test is data-blocked (H-0022: "D (data limitation)") | article bodies; a true availability timestamp; stationary coverage; revision provenance | availability time, not publication time (SPEC-0001 C-12, C-13) | news coverage of delisted names | revised text, hindsight labels | preregistration, leakage-controlled walk-forward | yes, for any money-path use | return or drawdown |
| options-implied volatility / skew at entry | none direct; ATR work is adjacent | no data | point-in-time options vendor | surface as of the decision time | options history of dead names | surface timestamps, stale quotes | preregistration, thirds, ETF control | yes | return or drawdown |
| short interest / borrow | none | no data | point-in-time short-interest feed | publication lag (biweekly) | delisted coverage | publication-date leakage | preregistration | yes | return or drawdown |
| fundamentals / revisions | none | no data | point-in-time fundamentals with restatement history | as-reported values only | delisted coverage | restatement leakage, noted as severe | preregistration | yes | return or drawdown |
| forward persistence | the entire historical record | only time answers it | elapsed sessions | SPEC-0001 | live universe | none by construction | Clean OOS protocol | **it is** Clean OOS | both |
| live exit drift vs the 0.652% haircut | H-0008, H-0012, H-0013 | needs live rule exits | live trigger and fill prices | as recorded | — | — | reported beside the frozen bound, never replacing it (Phase 4 §7) | yes | measured cost only |
| gain-to-loss share over time | H-0025 | unsettled across thirds (14.3% / 23.2% / 24.4%) | forward sessions | — | — | — | monitoring only | yes | nothing until measured |

**Untested but not open.** Two things the vault shows were never tested as
rules, which are nevertheless not open:

- **Volatility-triggered exits.** No ledger row registers one. But the only
  relevant measurement points the other way — H-0025 found crossing-time
  ATR/price has a *positive* association with outcome — and the exit family
  already carries ~77 configurations. Untested is not the same as promising.
- **Raising exposure.** H-0018 calls it untested, but idle cash in the index
  failed its drawdown and volatility clauses (H-0006) and was 3× worse
  risk-adjusted (EXP-0028); raising risk per trade was worse (EXP-0046); and
  H-0016 found cash refuses the *worse* candidates (AMB-5).

---

## Part 6 — The gap to SPY

The arithmetic: 4.42% CAGR against 13.42% (SPY price) or ≈15.0% (SPY total
return).

### The decomposition that exists

The post-correction split of the baseline's realised profit over its 698
trades:

- "The +58.59% decade return decomposes to market +$95,566, selection +$23,836,
  timing −$61,842. The strategy is mostly beta at 44% exposure" —
  `docs/2026-09-18-news-feasibility.md`.
- The committed data behind it: `docs/phase5/timing-decomposition.json` —
  buy-and-hold of the selected names over each holding period $119,330, entry
  gap −$6,913, exit gap −$54,858, realised $57,560. Its timing total (−$61,771)
  differs from the report's (−$61,842) by $71; both sum to the realised figure.

### Each proposed source, against the evidence

| source | finding | status |
|---|---|---|
| **market exposure / beta** | the positions earned +$95,566 from market moves while held, invested 44.28% of the time; SPY buy-and-hold earned +283% of capital. Beta 0.205 in EXP-0037 (thirty-year, pre-correction) | **supported as the arithmetically largest source** |
| entry selection | +$23,836 over the decade — positive, small. The raw RSI ≤ 35 band shows ≈ zero forward excess once SPY's missing dividends are accounted for (breadth forensics, INCONCLUSIVE) | **supported: positive but small** |
| entry timing | fixed by EXP-0016 (73.6% of return is overnight, EXP-0005); residual entry gap −$6,913 | minor residual |
| exit timing | exit gap −$54,858; recomputed from the committed JSON, 82.2% of the timing total is the 0.652% haircut — a modelling charge that H-0008 found is, if anything, too *low*. Give-back is not actionable (H-0021, H-0025) | **large in dollars, mostly a deliberate cost assumption, not a demonstrated recoverable loss** |
| cash drag | the baseline earns 0% on idle cash; the live overlay added +1.49 CAGR points in a pre-correction measurement (EXP-0014) | real, partly offset live; the current decade figure with overlay is not in the ledgers |
| portfolio constraints | the 12-position cap never binds; cash refuses the worse candidates (H-0016); adding a candidate class crowded out production trades and cost 16.9 points (H-0020) | **not supported as a cause** |
| correlation buckets | "refusing duplicated risk" (bucket forensics, A — no evidence) | **not supported** |
| liquidity restrictions | the ATR-ceiling population added nothing (H-0020, C) | **not supported** |
| universe construction / survivorship | 230 of today's survivors. Survivorship inflates the strategy (EXP-0031, pre-correction bound); size unmeasurable (H-0023, D) | **supported in direction — it widens the true gap — size unknown** |
| transaction costs | $13,868 modelled over the decade; SPY pays none | **supported as a contributor** |
| missing dividends | the historical basis omits them on both sides: SPY is understated by 1.3–1.6 CAGR points a year; the strategy's own forgone dividends are not measured | **supported for SPY; strategy side unverified** |
| regime behaviour | underperforms SPY in every regime state (P5-0022); regime cannot address the timing drag | **not a cause; the gap is everywhere** |
| opportunity generation | "the rule never finds more than ~10 simultaneous candidates" (EXP-0046); a generator gap exists (H-0019, A) but its one nominated class failed (H-0020, C) | **related to exposure; no validated way to add opportunities** |

**What the evidence supports.** The gap to SPY is dominated by exposure: a
long-only strategy invested 44% of the time, with a small positive selection
edge, cannot track an index that is invested all the time. Every lever tried
for more exposure failed on drawdown, volatility or quality. **What it does
not support:** that capacity, buckets, liquidity rules or regime cause the gap,
or that exit timing hides recoverable profit.

---

## Part 7 — The bottleneck

**Verified from the authoritative record, not assumed.** The research-gap
inventory states: "The largest bottleneck is signal quality, not capacity,
timing, correlation blocking, cash or position limits", with a 51.2% win rate
and an edge/noise ratio of 0.0776, and capacity ruled out three ways (H-0016,
H-0020, EXP-0025). Corroborated by: bucket forensics (A — no evidence), the
12-position cap never binding (regime forensics), "12 of 12 signal/parameter
experiments rejected — exhausted" (H-0018), and the breadth pass.

**One refinement.** At the level of the research programme, the inventory's own
first finding is that the binding constraint is **evidence**: every axis
reachable with existing data has been tested on one contaminated dataset.
Signal quality is the bottleneck of the *strategy*; evidence and data are the
bottleneck of *improving* it.

**Does the vault make signal-quality work easier without re-testing closed
mechanisms? Yes, in three specific ways, and no further:**

1. It puts every closed signal-side avenue in one place, each with its data
   scope: entry filters (P5-0001 … 0005), RSI thresholds (EXP-0006, EXP-0023,
   H-0009), cross-sectional ranking (EXP-0025, H-0019 P4), regime (seven
   families), news (EXP-0041, P5-0011 … 0013, H-0022), shorting, crypto and
   the learned veto.
2. It shows that what remains on the signal side needs **new data** — options,
   short interest, fundamentals, news bodies — so an agent learns quickly that
   the answer is not in the existing dataset.
3. It records the survivorship and reproducibility limits that bound any new
   signal test.

It does **not** yet record the two recurring failure signatures the inventory
identified — "Per-trade quality improves, the portfolio gets worse" and effects
inflated by survivorship — as first-class concepts, and the Form 4 study has no
area of its own in the map. Both are documentation gaps.

---

## Part 8 — What would prove an improvement

A claim that a change improves profitability needs **all** of the following.
Each is taken from a governed source.

| requirement | standard | source |
|---|---|---|
| benchmark period | the strategy's own evaluation window, fixed before results are seen | benchmark-units.md, rule 2 |
| starting capital | $100,000 | benchmark-units.md |
| universe | identical definition — and survivorship handled identically, with the ETF-subset control where registered (for example H-0020's "powered at >= 65 trades AND positive") | registrations; EXP-0031 |
| execution | the production candidate unchanged: signal-close fill, the 0.652% rule-exit haircut, realistic stop fills | `research.PRODUCTION_CANDIDATE` |
| costs | `CostModel`: 2 bps half-spread plus 4 bps slippage | `risk.py` |
| information boundary | SPEC-0001; every price labelled executable or hindsight | SPEC-0001; H-0025 |
| preregistration | sealed before any outcome is computed; `max_configurations` binding; prior configurations carried into the multiple-testing burden | `modelgov/prereg.py`; inventory |
| out of sample | contaminated data can reject but never accept; acceptance needs Clean OOS | `research.PURPOSES`; Phase 4 protocol |
| drawdown | at most 110% of the baseline's: 14.2806%, never relaxed | H-0011 and later registrations |
| materiality | more than the standing 2-point complexity penalty, net of costs | registrations |
| stability | holds in at least 2 of 3 chronological thirds | registrations |
| risk-adjusted metrics | Sharpe, Sortino and Calmar with the risk-free convention named; units always named | benchmark-units.md; EXP-0038 |
| **never** | raw CAGR alone; SPY as an optimisation target; a benchmark change that moves the gap | benchmark-units.md, rules 3–4 |

The vault states these in pieces across several notes but has **no single page
for them** — a documentation gap.

---

## Part 9 — SPY outperformance

**Can the knowledge base itself make the bot outperform SPY? No.** It is not
read by the money path and changes no decision.

**Can it improve the development process in a way that could eventually
produce a validated strategy competitive with SPY?** It can improve the
**process** — honest trial counts, fewer uncited re-tests, a correct frozen
reference, preserved boundaries — and the repository shows failures of exactly
that kind. But the evidence does **not** support a pathway to SPY-competitive
performance through this strategy as it stands: every configuration tested
trails SPY on total return, the gap is dominated by an exposure deficit that
every tested lever failed to close within drawdown limits, and the remaining
avenues need data the project does not have. The vault is necessary hygiene
for any future pathway. It is not itself one.

---

## Part 10 — The highest-value next research question

Each open area from Part 5, against the required properties:

| area | fails on |
|---|---|
| survivorship-free universe | adequate data — not available; and it measures rather than improves |
| options, short interest, fundamentals, news bodies | adequate data — not available |
| intraday peak location / queue resolution | value capped near zero (H-0014, +0.006 IC); queue span ruled a validated charge (H-0018); inside the most-explored family |
| volatility-triggered exits | the causal rationale is contradicted by H-0025; the family carries ~77 configurations |
| raising exposure | closed by H-0006, EXP-0028, EXP-0046 and H-0016 |
| forward persistence, live haircut drift | already mandated by the Clean OOS protocol; not a new question |

**NO NEW RESEARCH CANDIDATE JUSTIFIED.**

The highest-value next steps are not research questions:

1. **Make the research data reproducible**: record a content hash of the
   decade dataset and keep a durable, versioned copy; recover or rebuild the
   thirty-year dataset. Without this, no historical result — old or new — can
   be independently re-derived.
2. Let Clean OOS accumulate under the frozen fingerprint.
3. The owner's decision on a survivorship-free universe — a licensing
   question, recorded as the highest-value data acquisition by the inventory,
   H-0022 and H-0023.

---

## Part 11 — A new agent, using only the vault

| # | question | answer from the vault | accurate? |
|---|---|---|---|
| 1 | what does it trade? | long-only US equities and ETFs (230), plus a separate 5% BTC sleeve; Alpaca paper — `Production Truth` | yes |
| 2 | entries? | RSI(14) ≤ 35 above the 200-day average, price, liquidity and ATR filters; signal-close fill in the last 20 minutes — `Production Truth`, `Frozen Strategy` | yes |
| 3 | exits? | a fixed 2.5×ATR stop never moved, RSI ≥ 60, 20 sessions; no take profit, trailing or other exit — same pages | yes |
| 4 | what is rejected? | `Do Not Re-Research`, with the take-profit conflict flagged and volatility exits marked never tested | yes |
| 5 | what is unanswered? | `Research Gaps`: data-limited, new-data and OOS-dependent items; no candidate with existing data | yes |
| 6 | what is contaminated? | the decade and thirty-year datasets — can reject, never accept — `Frozen Baseline`, `Agent Instructions` | yes |
| 7 | what is Clean OOS? | 0 sessions, projected start 2026-10-12 — `Clean OOS` | yes |
| 8 | what must happen before production changes? | preregistration, Clean OOS, owner approval and a money-path review — `Agent Instructions` (C-26, C-27) | yes |
| 9 | the SPY comparison? | **as built: wrong.** The Benchmark note said "SPY, on total return", gave no numbers or period, and pointed to EXP-0037/0038, whose strategy figures are stale. **Corrected today**: now gives both bases, the window and the numbers | no → yes |
| 10 | what is credible evidence? | assembled from `Agent Instructions`, `Clean OOS`, `Frozen Baseline` and the registrations; no single page | partly |

**Result:** 8 of 10 accurate as built, 9 of 10 after correction, 1 partial.
This is evidence of usefulness for orientation, with a real error caught only by
this audit. The grader built the vault, so the test is not independent.

---

## Part 12 — Conclusion

### CURRENT PROFITABILITY EVIDENCE

In-sample only. On the contaminated decade window 2016-01-04 … 2026-09-04, the
frozen strategy returned +58.5889% cumulative, 4.4248% CAGR, Sharpe 0.5107
(risk-free rate 0), volatility 9.34%, maximum drawdown −12.98%, Calmar 0.3408,
over 698 trades, with idle cash at 0%. The survivor universe inflates it by an
unmeasurable amount (H-0023). **No Clean OOS evidence exists** (0 sessions).
Live paper activity (24 entries since 2026-09-01) is not evidence.

### SPY COMPARISON

Decade window 2016-01-04 … 2026-09-04. On the historical price-only basis: SPY
+283.14% cumulative, 13.42% CAGR, against the strategy's +58.59% and 4.42% — a
gap of −9.00 CAGR points a year. Against SPY total return (15.00% CAGR, window
to 2026-09-14): about −10.6 points a year. SPY's decade drawdown was −33.8% and
its Calmar 0.45, against the strategy's −12.98% and 0.34. The strategy trails
on return, Sharpe and Calmar, and leads only on absolute drawdown and
volatility. The forward record uses SPY total return. The comparison is not
like-for-like: idle cash at 0%, costs on one side only, 44% exposure,
survivorship, and dividends omitted on both sides.

### DOES THE KNOWLEDGE BASE CHANGE PROFITABILITY?

**NO.** It is not in the money path and changes no decision. Any indirect
effect on future profitability is **not demonstrated**.

### HOW IT COULD AFFECT FUTURE PROFITABILITY

Only indirectly, and only through mechanisms the repository shows failing
before:

- honest multiple-testing accounting — the exit family was undercounted by ~23
  configurations across three ledgers;
- fewer uncited re-tests (H-0001, H-0010);
- fewer misreadings of prior results (H-0017's account of H-0011; H-0021's
  execution assumption);
- a correct frozen reference and preserved information boundaries.

These reduce wasted trials and false discoveries. They cannot create edge, and
the repository identifies evidence and data — not memory — as the constraint.

### CURRENT RESEARCH BOTTLENECK

For the strategy: **signal quality** — a small positive selection edge
(+$23,836 over the decade; win rate 51.15%; edge/noise 0.0776) beneath a
return that is mostly market exposure at 44%. Capacity, buckets, liquidity
rules and regime are ruled out by H-0016, H-0020, EXP-0025 and the bucket and
regime forensics. For the programme: **evidence** — every axis testable with
existing data has been tested on one contaminated survivor dataset, that
dataset is not under version control, and Clean OOS has not begun.

### LEGITIMATE OPEN RESEARCH AREAS

All are data-limited or OOS-dependent; none is testable now with existing data:

- a survivorship-free point-in-time universe (to resize the edge, not change
  the rule);
- news with bodies and true availability timestamps;
- options-implied volatility and skew;
- short interest;
- point-in-time fundamentals;
- forward persistence, the live haircut drift and the gain-to-loss share over
  time — all through Clean OOS.

### HIGHEST-VALUE NEXT STEP

**NO NEW RESEARCH CANDIDATE JUSTIFIED.** The highest-value step is not
research: make the research data reproducible — a content hash and a durable
versioned copy of the decade dataset, and recovery of the thirty-year dataset —
then let Clean OOS accumulate. Whether to buy a survivorship-free universe is
the owner's decision.

### WHAT WOULD PROVE AN IMPROVEMENT

Preregistration before any outcome, with prior configurations carried into the
multiple-testing burden. On top of that, the same:

- window, fixed in advance;
- $100,000 starting capital;
- universe definition, survivorship treatment and ETF-subset control;
- production execution (signal-close fill, 0.652% haircut, realistic stops);
- `CostModel`;
- SPEC-0001 information boundary.

The change must then:

- exceed the 2-point complexity penalty net of costs;
- stay within a maximum drawdown of 14.2806%;
- hold in 2 of 3 chronological thirds;
- be judged on Sharpe, Sortino and Calmar with the risk-free convention named.

Contaminated data may only reject a change; acceptance requires Clean OOS.
Never raw CAGR alone, and never a comparison chosen or tuned against SPY after
the results are seen.

### PRODUCTION CHANGES

**NONE.**

---

## Knowledge-base corrections made during this audit

Documentation only; the vault validates after them.

1. `01-frozen/Benchmark.md` — **corrected an error**: it had said "SPY, on
   total return" without qualification. It now separates the historical
   price-vs-price basis from the forward total-vs-total basis, and gives the
   window and the numbers.
2. `01-frozen/Frozen Baseline.md` — added CAGR, volatility, Calmar, the Sharpe
   convention, the 0% cash basis and the reproducibility risk.
3. `07-sources/Governance Ledgers.md` — added the datasets and their location
   outside version control.
4. `05-open-questions/Research Gaps.md` — added the reproducibility risk.
5. `06-evidence/Conflicts and Ambiguities.md` — added:
   - AMB-4: which way the benchmark biases point;
   - AMB-5: whether exposure is "untested";
   - AMB-6: the unverified Calmar 0.75;
   - AMB-7: two definitions of which constraint rejects candidates.
