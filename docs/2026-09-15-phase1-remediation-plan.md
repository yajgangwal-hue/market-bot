# Phase 1: remediation and evaluation hardening — the plan

*2026-09-15. READ-ONLY: no code was modified to produce this. The one thing
actually executed was the leakage auditor against the production corpus
(§4), which reads data and fits a model in memory. Source of truth is
`docs/2026-09-15-forensic-audit.md` plus fresh verification below.*

---

## 1. MINIMUM CHANGES TO MAKE SIMULATOR AND LIVE AGREE

Six mismatches. Ordered by how much each distorts a reported number.

### 1.1 The exit-fill discrepancy (0.65%)
Simulator prices rule exits at `bar.close` (`portfolio.py:442/452/464`).
Live sells the moment the rule fires, on whichever 15-minute cycle that is.
Measured on 155 real exits with 5-minute bars: close beats trigger by
**+0.652%** (10:00 trigger), **+0.289%** (12:30), **+0.120%** (15:00).

**This is a specification ambiguity, not a one-sided bug.** Two defensible
resolutions, and they point opposite ways:

- **(a) Move live to the close.** Aligns live with every validated number;
  worth up to +0.65%/exit. But it *changes live economic behaviour*.
- **(b) Move the simulator to the trigger.** Makes every reported figure
  honest and lower. Changes no live behaviour.

**Recommendation: do (b) first.** Phase 1's rule is that production stays
frozen, and (b) is the only one of the two that respects it. It will lower
the headline CAGR — that is the point. (a) then becomes a separately
measured, separately approved change with a real number attached, rather
than a fix smuggled in as a correctness repair.

### 1.2 Liquidity / ADV participation
`RiskPolicy.max_volume_participation = 0.02` is **passed to the simulator
and never read.** Verified: `portfolio.py` references it **0 times**;
`autotrade.py` **2 times**. The simulator reads exactly three policy fields
(`max_daily_loss`, `max_notional_fraction`, `risk_per_trade`) plus whatever
`position_size` and `evaluate_guard` consume internally.

Worse than absent: the cap is *handed to* the backtest, so it looks enforced.

**Correction to my own audit:** I implied the simulator might also be
skipping buckets, position count and loss guards. It is not —
`evaluate_guard` is called at `portfolio.py:726` and enforces
`max_daily_loss`, `max_weekly_loss`, `max_open_positions` and
`max_per_bucket`. **Liquidity is the only unenforced control.**

### 1.3 Slippage
Flat 4 bps regardless of size, volatility, spread or urgency. Real slippage
widens precisely when this strategy trades — into broad sell-offs that push
many names oversold simultaneously. Optimistic exactly when it matters.
**Missing realism, not a bug.**

### 1.4 Partial fills
Not modelled anywhere (0 references). A 20%-of-equity position is assumed to
fill whole at one price. **Missing realism.**

### 1.5 Latency
Not modelled (0 references). Entry fills at the same bar's close that
generated the signal — zero elapsed time between decision and fill.
Defensible *only* because live trades the last 20 minutes. **Missing
realism, but it is the tightest assumption in the system**: widening the
live entry window silently breaks the equivalence.

### 1.6 Dividends
`portfolio.py` has zero dividend handling; prices are split-adjusted only.
Understates the bot (conservative) but makes bot-vs-SPY-total-return an
apples-to-oranges comparison. **Correctness problem for the benchmark, not
for the strategy.**

### 1.7 Other mismatches found
- **Cash parking is an overlay, not in-sim.** `with_parked_cash` post-
  processes the equity curve. Live actually buys and sells SGOV, which
  consumes cash the entry path could otherwise use. The overlay cannot
  express that interaction.
- **Crypto sleeve is entirely outside the simulator.** No backtest run
  includes it; its contribution is measured separately and bolted on.
- **`market_gate_drawdown`, `mr_take_profit_*`, `near_high_risk_scale`** etc.
  exist in the simulator with no live counterpart. Default-off, so harmless,
  but the two systems' parameter surfaces differ.

---

## 2. CORRECTNESS BUGS vs MISSING REALISM

| # | item | classification | why |
|---|---|---|---|
| 1.2 | liquidity cap ignored by simulator | **CORRECTNESS BUG** | a declared control is silently not applied; sim and live can produce different trades from identical inputs |
| 1.6 | dividends absent from benchmark comparison | **CORRECTNESS BUG** (benchmark) | compares ex-dividend bot against cum-dividend index |
| 1.1 | exit fill price | **SPECIFICATION AMBIGUITY** | neither side is "wrong"; they disagree and one must be declared authoritative |
| 1.7 | parking as overlay | **MODELLING GAP** | measurable, bounded, not a defect |
| 1.3 | flat slippage | missing realism | conservative-ish but wrong in the tails |
| 1.4 | partial fills | missing realism | |
| 1.5 | latency | missing realism | |

**Only two are genuine correctness bugs.** Everything else is a known,
documented simplification. That distinction matters because Phase 1 says
"do not change production logic unless required to fix a verified
correctness problem" — and **neither correctness bug requires a production
change.** Both are fixed in the simulator and the benchmark.

---

## 3. IMPLEMENTATION PLAN PER CORRECTNESS BUG

### BUG A — simulator ignores `max_volume_participation`

- **Files:** `src/event_aware_trader/portfolio.py` (sizing call site,
  ~line 720); read-only reference `src/event_aware_trader/risk.py`.
- **Current:** `position_size(equity, entry_ref, stop_ref, sizing_policy,
  costs)` caps by risk budget and 20% notional only.
- **Desired:** additionally cap quantity at
  `policy.max_volume_participation × ADV_shares` for the bar, matching
  `autotrade.py:1850`. If `max_volume_participation is None`, behave exactly
  as today.
- **Why:** a declared risk control that is not applied means every reported
  return may include positions the live bot would have refused. It also
  makes the two systems non-comparable in principle.
- **Tests:**
  1. a thin-volume symbol is capped to 2% of ADV and a liquid one is not;
  2. `None` reproduces today's quantities **exactly** (byte-identical trade
     list on a fixed seed) — this is the regression guard;
  3. the cap uses the **entry bar's** ADV, not a forward window;
  4. a live/sim parity test: same bars, same policy → same quantity from
     `autotrade`'s sizing path and `portfolio`'s.
- **Look-ahead check:** ADV must be computed from bars **strictly up to and
  including the entry bar** — the same `bars[-20:]` slice
  `mean_reversion.evaluate` already uses. Verify by asserting the computed
  ADV is unchanged when future bars are appended to the series.
- **Expected effect:** lowers reported return by an unknown amount. At $100k
  against $50M-ADV names the cap almost never binds, so likely near zero —
  but it must be *measured*, not assumed, and it becomes material as the
  account grows.

### BUG B — benchmark compares ex-dividend against cum-dividend

- **Files:** `src/event_aware_trader/benchmark.py`,
  `scripts/benchmark.py`; data path `data.py` (`adjustment` parameter,
  already exists).
- **Current:** bot returns come from `adjustment="split"` price data; SPY
  comes from `adjustment="all"`. The 30-year SPY total return is an
  **estimate** (~10.3%) presented alongside measured figures.
- **Desired:** see §5. In short — never mix. Price-vs-price for 1996–2026;
  total-vs-total for 2016–2026 only, where both are measured.
- **Why:** it is the headline comparison in every report.
- **Tests:** a test asserting the two legs of any comparison carry the same
  `adjustment`, and that an estimated figure can never be returned from the
  same field as a measured one.
- **Look-ahead check:** none applicable — dividend adjustment is backward-
  looking by construction. But **verify** that `adjustment="all"` does not
  retroactively restate closes in a way that changes *signals*; this is why
  the strategy keeps `split` and only the benchmark uses `all`.

### AMBIGUITY C — exit fill (the 0.65%)

- **Files:** `portfolio.py` exit branch (`bar.close` assignments).
- **Current:** sim assumes close; live sells at trigger.
- **Desired (Phase 1):** add `exit_fill: "close" | "trigger"`, default
  **`"trigger"`** so reported numbers match what live actually does. Keep
  `"close"` available to quantify the gap.
- **Why:** so the headline figure stops describing a system we do not run.
- **Tests:** both modes produce the documented prices on a synthetic bar; the
  default reproduces live behaviour; switching modes changes only exit
  prices and not which trades occur.
- **Look-ahead check:** `"trigger"` must use a price available at the
  decision moment. On daily bars there is no intraday price, so the honest
  proxy is the **same bar's close** — which is what we have. **This means
  the daily simulator cannot faithfully represent trigger fills at all**,
  and the 0.65% must be carried as a documented haircut rather than
  simulated. State that plainly rather than pretending to model it.
- **Production change:** **NONE in Phase 1.**

---

## 4. LEAKAGE AUDITOR AGAINST THE PRODUCTION MONEY PATH — RESULT

It **could** be run without modification. I pointed it at
`data/live-training.jsonl` (the corpus `append_example` writes and
`train_live_model` reads) with `LIVE_FEATURES`:

```
corpus        : 1,531 rows  (1,526 seed_replay, 4 live, 1 untagged)
date span     : 1996-12-05 → 2026-09-15
features      : 16
label balance : 442 wins / 1,531  (28.9%)

test AUC      : 0.5517
trustworthy   : False
alarms        : ['memorisation']

  ok     implausible_score      0.5517 out-of-sample — below the 0.75 bug threshold
  ALARM  memorisation           train 0.9863 vs test 0.5517, gap 0.4346 (alarm at 0.25)
  ok     single_feature         strongest lone feature 'mkt_ret21' at 0.5453
  ok     shuffled_split         shuffled 0.5026 vs chronological 0.5517
```

**What it finds, precisely:**

1. **No look-ahead leakage.** Three of four checks pass. The most diagnostic
   is the shuffle: a shuffled split scores **lower** (0.5026) than the
   chronological one (0.5517). If the model were borrowing the future,
   shuffling would *help*. It hurts. No feature encodes the outcome, and the
   out-of-sample score is in the honest 0.55 band.
2. **Severe memorisation.** Train 0.9863 against test 0.5517 — it fits the
   training set almost perfectly and generalises barely above chance.
3. **This independently confirms EXP-0029** by a different method. That
   experiment found AUC 0.5501 full-fit vs **0.5056** walk-forward and that
   the veto lost money monotonically. Two methods, same verdict: the model
   has no usable generalising signal. **Keeping `live_model_floor = 0.0` is
   correct and is now doubly evidenced.**

**Limitation to state honestly:** this audits the model's *corpus*, which is
the production money path for the learning loop. It does **not** audit the
*rule* — RSI/SMA/ATR are deterministic functions of past bars with no
fitting, so there is nothing for a leakage auditor to find there. The rule's
leakage question is answered by code inspection (§5 of the forensic audit),
not by this tool.

**To make this routine rather than a one-off:** add a `leakage-audit` CLI
command wrapping the above, and run it in the weekly job alongside
`retrain`. Roughly 30 lines. No production behaviour changes.

---

## 5. BENCHMARK METHODOLOGY — THE FIX

**Principle: never compare two legs on different adjustment bases, and never
present an estimate in the same field as a measurement.**

| period | bot leg | SPY leg | status |
|---|---|---|---|
| **1996-01-01 → 2026-09-05** | price return (`split`) | **price return** | **MEASURED** — both ex-dividend, consistent |
| **2016-01-04 → 2026-09-14** | total return (`all`) | **total return** (`all`) | **MEASURED** — both cum-dividend |
| 1996–2026 total return | — | ~10.3% | **ESTIMATED — do not use in a comparison** |
| pre-2016 dividend-adjusted universe data | — | — | **UNAVAILABLE from this machine** |

**Why this and not an estimate:** Alpaca's history starts 2016 and the Yahoo
path fails on a certificate error here. Rather than estimate the 30-year
dividend contribution and compare against it, **restrict the total-return
comparison to the window where both legs are measured**, and run the
thirty-year comparison price-against-price. Both are honest; mixing is not.

**Idle cash.** The bot holds ~74% cash earning bills; SPY buy-and-hold is
fully invested. Three comparisons, each reported separately and never
blended:

1. **Account vs 100% SPY** — the actual choice an owner faces. The bot's
   cash must earn the bill rate (it does, via `with_parked_cash`) or the
   comparison is unfair to the bot.
2. **Volatility-matched SPY** — SPY scaled to the bot's 6.7% vol, with the
   uninvested remainder earning the **same bill rate** the bot's cash earns.
   Today's vol-matched figures assume 0% on the remainder and therefore
   **understate SPY by roughly (1−scale) × 2.30%/yr**; that must be fixed.
3. **Excess-return Sharpe over the actual bill rate** — never rf = 0, which
   flatters a book that is three-quarters cash.

**Required changes:** all in `benchmark.py` / `scripts/benchmark.py`. A test
must assert that a comparison refuses to run when the two legs' adjustment
bases differ, and that estimated values carry an explicit flag.

---

## 6. EVALUATION FRAMEWORK — WHAT IS NEEDED

| capability | today | needed |
|---|---|---|
| chronological train/val/test | **absent** — one window, used for everything | three named, dated, code-enforced spans |
| untouched forward evaluation | **exists**, 3 sessions | keep untouched to 60 |
| walk-forward | partial — `walk_forward_years` slices ONE run of a fixed rule; refitting deliberately raises `NotImplementedError` | per-fold refit harness: one run per fold, fit only on prior data |
| purged validation | **absent** | purge training samples whose label window overlaps the test window |
| embargo | **absent in research** (the leakage auditor has `embargo_days=30`, unused elsewhere) | embargo ≥ holding period (20 sessions) after each test fold |
| CPCV | **absent** | appropriate later; not before a second strategy exists |
| PBO | **never computed** | compute from the registry's own configuration set |
| deflated Sharpe | **exists and is wired** to registry counts | feed it `trial_sharpes` from every sweep, not just one |
| parameter stability surfaces | **absent** — point sweeps only | 2-D neighbourhood grids for the four core parameters |
| experiment tracking | **exists and is good** — 52 experiments, 186 configurations, append-only | enforce *pre*-registration |
| repeated-holdout prevention | **declarative only** — `DATASETS` marks contamination but nothing blocks a run | a hard gate that refuses to score a contaminated set without an explicit override flag |

**The single highest-value addition is the last one.** Everything else
measures how badly we have fooled ourselves; that one stops it happening
again.

**Purge/embargo specifics for this strategy:** average hold is 14.0 days,
cap 20. So a test fold must purge any training trade whose entry-to-exit
window overlaps the fold, and embargo **20 sessions** after it. Without
that, a trade opened before the boundary and closed inside it leaks.

---

## 7. THE 60-SESSION FORWARD GATE

**What gets measured** (all already recorded; no new instrumentation):
- account equity, once per session close, from `broker_equity` in the audit
  log — recorded at the time, not reconstructed
- SPY total return over the identical sessions (`adjustment="all"`)
- per-trade: entry, exit, reason, R multiple, MFE/MAE, captured, gave-back
- realised vs unrealised split
- every external exit reconciled through `trade_reconcile`

**Baseline:** SPY total return over the same sessions, plus the bot's own
in-sample expectation as a *reference only* (not a pass condition).

**Technical failure** — the run is void and the clock restarts:
- any session where the loop did not run or a position was unprotected
- any position closed by a path that produced no training example
- any divergence between recorded and broker-reported equity
- any fill materially outside the modelled cost band

**Inconclusive** (the expected outcome): 60 sessions of a strategy with a
0.53 Sharpe cannot distinguish the hypothesis from noise. At 6.7% annual
vol, 60 sessions ≈ 3.3% standard error on the period return — wider than the
entire annual edge. **60 sessions is a check for technical correctness, not
a verdict on profitability.** Anyone who reads it as the latter has
misunderstood it, and the gate should say so in its own output.

**What may influence development during the 60 sessions:**
- ALLOWED: bug fixes with no economic effect; logging; tests; research on
  *contaminated historical data* explicitly labelled as such; building the
  evaluation framework itself
- FORBIDDEN: any parameter change justified by the forward record; any
  strategy accepted on the forward record; peeking at cumulative excess
  return to decide what to work on next

**Exactly when it becomes contaminated:** the moment any forward observation
changes a decision. Reading it is safe; *acting* on it spends it. If a
parameter is changed because of what the forward record showed, those
sessions are contaminated for that parameter's family and the count
restarts. This should be enforced by requiring a registry entry naming the
forward window before any change that cites it.

---

## 8. SHOULD PRODUCTION STAY FROZEN? — YES

**Freeze the economic behaviour.** Nothing in Phase 1 requires changing
which trades happen, at what size, or at what price.

**Safe to change now (no economic effect):**
- simulator: liquidity cap, `exit_fill` mode, dividend handling for research
- benchmark methodology (reporting only)
- the entire evaluation framework (research only)
- `leakage-audit` CLI + weekly invocation
- logging, tests, documentation
- **already done and correctly classified as a correctness fix:** the second
  stop-reconcile pass after entries (a position opened at 15:48 had no
  overnight stop; MDY, $19,425, found naked on 2026-09-15). That changed
  risk behaviour, not economic behaviour — it adds protection that was
  always intended.

**NOT safe, defer with a number attached:**
- moving live exits to the close (+0.65%/exit) — real money, real behaviour
  change, belongs in Phase 2 with its own registry entry
- enabling any take-profit variant
- enabling the model veto

---

## 9. REMAINING DISCREPANCIES BETWEEN THE FOUR ENVIRONMENTS

**A backtester** (`portfolio.py`) · **B live** (`autotrade.py` + broker) ·
**C research** (`research.py` + scratch harnesses) · **D evaluation**
(`benchmark.py`, `record.py`, `evaluation.py`)

| # | discrepancy | A | B | C | D |
|---|---|---|---|---|---|
| 1 | liquidity cap (2% ADV) | **ignored** | enforced | inherits A | n/a |
| 2 | exit fill price | close | trigger | inherits A | n/a |
| 3 | dividends | none | real (paid into account) | none | SPY leg has them |
| 4 | cash parking | overlay only | real SGOV trades | overlay | included |
| 5 | crypto sleeve | **absent** | live, 5% | absent | included in account equity |
| 6 | entry window | implicit in `signal_close` | explicit 20 min | inherits A | n/a |
| 7 | reserved_fraction (5%) | **absent** | enforced | absent | implicit |
| 8 | fractional shares | policy-driven | forced whole | forced whole | n/a |
| 9 | slippage | flat 4 bps | real fills | flat | n/a |
| 10 | research-only params | 6 exist | none | uses them | n/a |
| 11 | learning loop | **absent** | every exit | absent | n/a |
| 12 | news recording | absent | every cycle | absent | absent |

**The most consequential are 1, 3, 5 and 7.** Items 5 and 7 together mean no
backtest has ever represented the actual portfolio: the real account runs a
5% crypto sleeve funded from a 5% reserve the simulator does not model.
**Every historical figure describes an equity-only book that does not
exist.**

---

## 10. PRIORITISED ROADMAP

### CRITICAL — before evaluating any new strategy

| item | evidence |
|---|---|
| **C1. Liquidity cap into the simulator** | `portfolio.py` reads `max_volume_participation` 0 times; `autotrade.py` 2 times. A declared control silently unapplied. |
| **C2. `exit_fill="trigger"` as the reported default** | 155 exits on 5-min bars: close beats trigger by 0.652%/0.289%/0.120%. Reported returns describe a system we do not run. |
| **C3. Benchmark adjustment consistency** | bot on `split`, SPY on `all`; the 30-year SPY total return is an estimate sitting beside measured figures. |
| **C4. Contaminated-dataset hard gate** | `DATASETS` declares contamination; nothing enforces it. 37 decade touches, 30 thirty-year. |
| **C5. Model the reserve + sleeve, or state the scope** | simulator has neither; the live account has both. Every backtest describes a different portfolio. |

### HIGH — before serious strategy research

| item | evidence |
|---|---|
| H1. Purge + 20-session embargo in any refit harness | avg hold 14.0 days, cap 20; no purging exists |
| H2. Per-fold-refit walk-forward | `walk_forward_years` raises `NotImplementedError` for refits |
| H3. `leakage-audit` as a scheduled command | auditor exists; was invoked only by its own test until today |
| H4. Parameter stability surfaces | "clean peak at 2.5 ATR" rests on five points, no neighbourhood |
| H5. Pre-registration enforced | registry supports it; discipline is manual |
| H6. Trial Sharpes recorded on every sweep | only the 09-13 exit sweep has them; DSR swings 0.993 → 0.53 on that input |

### MEDIUM

M1 PBO from the registry · M2 dividends in the simulator (+0.5–0.8 pts,
conservative today) · M3 volatility/size-dependent slippage · M4 partial
fills · M5 vol-matched SPY earning the bill rate on its uninvested remainder

### LOW — do not spend time yet

L1 CPCV (needs a second strategy first) · L2 latency modelling (the 20-min
window makes it near-irrelevant) · L3 market impact (immaterial at $100k) ·
L4 streaming architecture (Phase 3; do C2 on the 15-minute loop first)

---

## FINAL QUESTION

### What the bot will have after Phase 1 that it does not have today

1. **A simulator that produces the same trades as the live bot** from the
   same inputs — liquidity cap applied, exit fills matching live, the
   reserve and sleeve either modelled or explicitly scoped out. Today the
   two can disagree and nothing detects it.
2. **Reported numbers that describe the system actually running.** Expect
   them to be *lower*. That is the deliverable.
3. **A benchmark that compares like with like**, with measured, estimated
   and unavailable values visibly separated and a test that refuses to mix
   adjustment bases.
4. **A mechanical barrier to holdout reuse** — the first thing in this
   project that *prevents* self-deception rather than documenting it after
   the fact.
5. **Purge/embargo and per-fold refitting**, so a tuned component can be
   evaluated without leaking across the boundary.
6. **A routine leakage audit** on the production corpus, not a unit test.
7. **Parameter stability surfaces** distinguishing a robust plateau from a
   fitted spike.
8. **A forward record with a defined gate** and explicit rules for what may
   influence development while it accrues.

### What will still be missing before a multi-strategy, continuously monitoring, market-adaptive system is responsible

1. **A second source of edge.** Everything above is measurement
   infrastructure. After Phase 1 there is still exactly **one** signal, one
   direction, one timeframe. Diversification cannot be tested because there
   is nothing to diversify with.
2. **Any uncontaminated data on which to accept something.** 60 sessions is
   a correctness check, not a verdict — at 6.7% vol the standard error over
   that window exceeds the entire annual edge. Accepting a *new strategy*
   honestly needs years of forward data, or a genuinely untouched historical
   window that does not currently exist.
3. **Streaming input and an event loop.** Everything is REST polling;
   `run_once` is a ~1,000-line batch function assuming a cold start.
   Continuous monitoring needs websockets, in-memory state, a decision
   throttle and process supervision — a rewrite of the live path, not an
   extension.
4. **Regime adaptation that works.** A classifier exists and the live rule
   ignores it. Two attempts to use regime (gating, sizing) were rejected on
   both axes. There is currently **no evidence** any regime adaptation helps
   this strategy.
5. **A news signal with measurable content.** The corpus is 2 days old and
   the one tested thesis was the wrong half of the trade. Months of
   point-in-time data are required before it can even be tested.
6. **Capacity analysis.** Nothing establishes what the strategy can hold
   before its own impact erodes the edge — which determines whether any of
   this scales beyond a $100k paper account.
7. **Operational maturity.** S4U is still not applied to the crypto task
   (needs elevation); there is no alerting, no dead-man's switch, and the
   watchdog pattern is not generalised.

**The honest summary:** Phase 1 buys the ability to *believe measurements*.
It buys no return — it will reduce the reported figures. Everything on the
"still missing" list is gated behind it, because without it, any of those
additions would be evaluated with the same instruments that produced a
0.9863 training AUC and a 0.5517 real one.
