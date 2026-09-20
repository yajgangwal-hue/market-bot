# H-0011 validation gate — non-promotional

*Run 2026-09-20. No promotion, no new registration, no production change,
no parameter change, no date/symbol/sector/trade subset selected. H-0011 is
treated as frozen throughout.*

## Conclusion: **B — H-0011 REPRODUCIBLE BUT FRAGILE**

The result reproduces bit-identically and the information boundary is clean.
It is **materially concentrated by time** and carries **three implementation
dependencies** severe enough that the sealed statement's central claim is
contradicted by its own trade log. No optimization is proposed.

---

## 0. Sealed specification, recovered from the ledger

Read from `docs/preregistrations.jsonl` via `prereg.load()`, not from memory.

| field | value |
|---|---|
| hypothesis_id | **H-0011** |
| seal | `eeab1b4302e2a5f1faf29d4178ce1cba972e5a018b7000bd867db760e592d1b2` |
| code_commit | `22f2752a4091e70384d840e0cd94cad834bbe9c9` |
| registered_at | 2026-09-20T03:20:01.518349+00:00 |
| kind | confirmatory |
| max_configurations | 3 |
| parameter moved | `run_portfolio.mr_limit_exit` |
| offset | **0.0 (fixed, may not be varied)** |
| patience_sessions | **A=1, B=2, C=3** |
| datasets | decade (development); thirty_year **NOT USED**, stays at 13 |
| chain | intact, 11 registrations |

Acceptance was ALL FIVE of (A) return > baseline + 2 pts, (B) `abs(maxDD)` ≤
14.2806%, (C) largest positive delta ≤ 2.5× second-largest, (D) beats baseline
in ≥ 7 of 11 years and survives leave-one-best-year-out, (E) filled/lapsed
counterfactual net > 2-pt penalty, **with the queue assumption disclosed and a
pass by a margin smaller than that uncertainty recorded as INCONCLUSIVE.**

Measured outcome on record (`docs/phase5/h0011-adjudication.json`):
**INCONCLUSIVE.** All five clauses passed on all three configurations; the
seal's own inconclusive test fired.

---

## 1. Reproduction — **PASS, bit-identical**

The committed cache was set aside and the sealed configuration re-run from
scratch, then diffed against `HEAD:docs/phase5/h0011-cache.json`.

| config | total return | trades | Sharpe | max DD | exposure | costs |
|---|---|---|---|---|---|---|
| BASELINE | 58.5889000000% | 698 | 0.5107 | −12.9824% | 44.2794% | 13,868.03 |
| A patience 1 | 86.3505000000% | 693 | 0.6627 | −13.8938% | 45.1369% | 15,199.40 |
| B patience 2 | 84.9058000000% | 696 | 0.6544 | −12.8724% | 45.3395% | 15,192.42 |
| C patience 3 | 83.9267000000% | 692 | 0.6528 | −12.9067% | 45.2702% | 15,055.63 |

**Discrepancies: 0** — across all metrics, all **2,779 trade rows**, all four
equity curves, exit-reason mixes, fill rates, haircut totals and clause-E
structures. Baseline equivalence reproduced at +58.5889000000% / 698 trades.

## 2. Information boundary — **CLEAN, traced not asserted**

Because offset = 0, the sealed limit level is exactly the trigger close, and
the trigger close is independently recoverable from the *baseline's* matched
`reverted` trade as `exit_price / (F × (1 − haircut))`. That gives a check of
every fill that does not rely on the implementation.

| check | A | B | C |
|---|---|---|---|
| limit_exit trades traced | 160 | 166 | 171 |
| **filled on the SAME bar as the trigger** | **0** | **0** | **0** |
| **filled later than patience allows** | **0** | **0** | **0** |
| open-fill where open < level | 0 | 0 | 0 |
| level-fill at a price ≠ sealed level | 0 | 0 | 0 |
| sessions trigger→fill (min–max) | 1–1 | 1–2 | 1–3 |

Data path: the limit level is set from the trigger bar's close at the moment
the RSI rule fires — the same information the baseline's `reverted` exit
already uses to both decide *and* fill. Fill resolution reads only `open` and
`high` of sessions strictly after the order was placed. No revised data (the
CSVs are static history), no post-close information, no future price. Timestamp
conventions are inherited unchanged — H-0011 consumes the same `Bar` objects as
every other path.

One observation, favourable and worth recording: the baseline decides at a
close and fills at that same close, which is an idealisation the 0.652% haircut
exists to correct. **H-0011 is strictly more realistic** — it decides at the
close and fills on a later session.

## 3. Time-split robustness — **the primary fragility**

Yearly delta vs baseline, in points:

| year | A | B | C |
|---|---|---|---|
| 2016 | +0.09 | +0.09 | +0.09 |
| 2017 | +3.08 | +3.07 | +3.38 |
| 2018 | **−0.22** | **−1.25** | **−0.74** |
| 2019 | +2.18 | +2.71 | +2.75 |
| 2020 | +2.50 | +2.55 | +2.53 |
| 2021 | +4.96 | +5.14 | +1.88 |
| 2022 | +0.43 | +0.23 | +0.22 |
| 2023 | +3.93 | +3.18 | +4.27 |
| 2024 | **−0.40** | **−0.66** | **−1.02** |
| 2025 | +0.03 | +1.24 | +1.59 |
| 2026 | +1.23 | +0.78 | +1.14 |

Chronological thirds:

| third | baseline | A | B | C |
|---|---|---|---|---|
| 1 (2016–2019) | +16.43% | +5.68 | +5.01 | +6.02 |
| 2 (2020–2023) | +17.72% | **+13.08** | **+12.14** | **+9.99** |
| **3 (2024–2026)** | +14.46% | **+0.87** | **+1.44** | **+1.79** |

**The effect has all but disappeared in the most recent third.** Third 2 carries
+13.08 points; third 3 carries +0.87 — a 93% decline, in the period most
relevant to forward performance, on a broadly similar baseline return.

Leave-one-out:

| config | best year | ex-best delta | worst year | ex-worst delta |
|---|---|---|---|---|
| A | 2021 (+4.96) | **+16.63** (from +27.32, **−39%**) | 2024 (−0.40) | +27.72 |
| B | 2021 (+5.14) | +15.28 (−41%) | 2018 (−1.25) | +27.58 |
| C | 2023 (+4.27) | +16.77 (−33%) | 2024 (−1.02) | +26.43 |

**No 2025 dependence** — A's 2025 delta is +0.03 and the delta excluding 2025
is +26.26. That specific concern is cleared.

## 4. Concentration — **broad, not trade-picked**

| | A | B | C |
|---|---|---|---|
| matched trades | 637 | 637 | 642 |
| trades with any delta | 619 (97.2%) | 617 (96.9%) | 624 (97.2%) |
| **of those, positive** | **47.0%** | 48.0% | 47.9% |
| top 1 trade | 3.3% of delta | 3.3% | 2.9% |
| top 10 trades | 22.7% | 21.9% | 19.7% |
| top 50 trades (7.8%) | 88.4% | 85.8% | 75.6% |
| contributing symbols | 175 | 175 | 175 |
| top 10 symbols | 43.6% | 43.8% | 38.7% |

Best/worst symbols for A: AAPL +1,861, AZO +1,595, EWT +1,388 / NVDA −655,
ORCL −678, LMT −787. **No outliers were removed.**

This dimension is healthy: the effect is spread over 175 symbols and 619
trades, with no single trade above 3.3%. But note the sign split — **only 47%
of affected trades are positive.** The mechanism is a small positive mean on a
near-coin-flip distribution, not a reliable per-trade gain.

## 5. Baseline-relative decomposition — **the sealed claim is contradicted**

The seal states: *"the entry rule, the stop, the holding cap and the sizing are
all untouched, so any change in return can only come from how the same exits
are filled."*

| | A | B | C |
|---|---|---|---|
| common trades | 637 | 637 | 642 |
| **byte-identical trades** | **18 (2.8%)** | 20 (3.1%) | 18 (2.8%) |
| entry price identical | **637 (100%)** | 100% | 100% |
| **quantity identical** | **23 (3.6%)** | 25 (3.9%) | 23 (3.6%) |
| exit date identical | 454 (71.3%) | 452 (71.0%) | 455 (70.9%) |
| trades added | 56 | 59 | 50 |
| trades dropped | 61 | 61 | 56 |

Delta sources (A):

| source | delta | n |
|---|---|---|
| **directly armed exits** | **+$47,073** | 183 |
| **knock-on on other trades** | **−$19,062** | 436 |
| trades ADDED baseline never took | +$14,646 | 56 |
| trades DROPPED baseline took | −$15,079 | 61 |
| sum | +$27,578 | |

**Entry timing is genuinely unchanged (100% identical entry prices).** But
**position size differs on 96.4% of trades**, and 117 trades differ in
existence. Holding a position one extra session changes the capital and bucket
path, which changes sizing and which candidates are taken.

**40% of the direct gain is given back as knock-on damage to unrelated
trades**, and the added/dropped pair (+$14,646 / −$15,079) very nearly cancels
— **by coincidence, not by construction.** Clause E's counterfactual matches on
(symbol, entry date) and therefore silently excludes all 117 of those trades.
The clause measured the mechanism; it did not measure the portfolio.

## 6. Capacity and interaction dependencies

Recorded as future research questions. **Nothing was changed to test them.**

| dependency | finding |
|---|---|
| **12-position cap** | **NOT binding.** Max concurrent positions is 9 in every configuration; 0 sessions at ≥11. The added/dropped trades do **not** come from this cap. |
| **bucket cap = 1** | **Likely coupled.** 29 buckets in use, top bucket carries 67 trades. With a cap of 1, holding a name one extra session denies its bucket — the plausible source of the 117 added/dropped trades. |
| **0.652% haircut** | **HARD DEPENDENCY. 78–85% of the net gain is the avoided haircut** ($22,899 of $28,012 for A). The code itself calls this constant "an uncertainty adjustment, not an observed price," resting on 155 measured exits and **three logged live rule exits.** |
| **20-session hold** | **ACTIVE.** 283 of 693 trades (41%) reach bar 20, and the first H-0011 run breached to bar 21. The mechanism collides with this cap routinely. |
| **candidate ordering** | Coupled — ordering decides which of the 117 added/dropped trades are taken. |
| **rsi_entry = 35.0** | Coupled indirectly: it sets how many positions exist to generate `reverted` triggers. |
| **risk contract** | Coupled — sizing differs on 96.4% of trades via the equity path. |

## 7. Effect size, equivalent forms

| | A | B | C |
|---|---|---|---|
| total return delta (pts) | +27.76 | +26.32 | +25.34 |
| **CAGR delta (pts)** | **+1.59** | +1.52 | +1.46 |
| Sharpe delta | +0.1521 | +0.1437 | +0.1421 |
| max DD delta (pts) | +0.91 | −0.11 | −0.08 |
| **exposure delta (pts)** | **+0.86** | +1.06 | +0.99 |
| win rate delta (pts) | −0.06 | −0.28 | −0.28 |
| profit factor delta | +0.076 | +0.070 | +0.069 |
| cost delta | +$1,331 | +$1,324 | +$1,188 |
| hold delta (days) | +0.33 | +0.32 | +0.34 |
| **$ per armed order** | **+$140** | +$137 | +$153 |
| $ per trade (all) | +$40 | +$40 | +$45 |
| **bps of avg notional per armed order** | **+85** | +83 | +92 |

Read the last row against the **65.2 bps sealed haircut**. The per-order effect
is 83–92 bps where 65.2 bps is the haircut being escaped; the remainder is the
price move from the extra session.

**A correction to the H-0011 report's framing.** That report said "57–59% of
the gain is price move." That figure is the *gross filled-trade* gain. On the
**net**, after lapses and knock-on, **78–85% is the avoided haircut** — the
price move is largely competed away. Both numbers are correct against different
denominators; the net figure is the decision-relevant one, and it makes the
haircut dependency worse, not better.

Economically meaningful vs noise: the **CAGR delta of +1.59 points** and the
**Sharpe delta of +0.15** are meaningful in size. The **win-rate delta
(−0.06 to −0.28 pts)** and **max-DD delta (−0.11 to +0.91 pts)** are not
distinguishable from fluctuation and should not be cited as effects.

## 8. Evidence provenance

| analysis | classification |
|---|---|
| clauses A–E, gradient, leave-one-best-year-out, filled/lapsed counterfactual, fill-rate disclosure, holding-cap check | **pre-registered evidence** (named in the seal) |
| exact reproduction and trade-level diff | **permitted diagnostic** (verification, adds no acceptance criterion) |
| information-boundary trace | **permitted diagnostic** |
| chronological thirds, ex-worst-year, 2025 dependence, trade/symbol concentration, decomposition, capacity dependencies, equivalent effect sizes | **permitted diagnostic — retrospective, NOT acceptance evidence** |
| queue-adverse floor and haircut sensitivity | **pre-registered evidence** — clause E explicitly required both |

**No retrospective diagnostic has been promoted into an acceptance criterion.**
The sealed verdict remains INCONCLUSIVE and is unchanged by this gate. The
Section 3–6 diagnostics explain *why* it is fragile; they did not set the
verdict.

---

## Conclusion — B, and the specific fragilities

**Reproduces exactly. Boundary clean. Not robust enough for follow-on
registration.** Four fragilities, in order of severity:

1. **The sealed causal claim does not hold.** Position size differs on 96.4% of
   trades and 117 trades differ in existence. The direct mechanism earns
   +$47,073; knock-on on unrelated trades gives back −$19,062. It is a
   portfolio-path effect, not the isolated execution effect the seal describes.
2. **Time concentration.** Third 3 (2024–2026) contributes +0.87 points against
   third 2's +13.08. Removing the best year costs 33–41% of the delta.
3. **78–85% of the net gain is the 0.652% haircut** — a constant the codebase
   labels an uncertainty adjustment, not a measurement, resting on three logged
   live rule exits.
4. **The queue-adverse floor**, already on record: +$2,997 / −$2,909 / +$168
   against a $2,000 penalty, with the ordering inverting.

Per the instruction, **no optimization is proposed and no follow-on hypothesis
is offered.** Fragilities 1 and 3 would each have to be resolved by measurement
— an exposure- and path-controlled design, and live fill/trigger-time data —
before any follow-on could be defensible.

## Final governance report

| check | state |
|---|---|
| production fingerprint | `da22011e…c237b` — **UNCHANGED** |
| `rsi_entry` | **35.0** |
| `rsi_exit` / stop / hold / risk / bps | 60.0 / 2.5 / 20 / 0.005 / 6.0 |
| learned ranker | **OFF** (`LEARNED_RANKING_ENABLED = False`) |
| learned veto | **OFF** |
| `mr_limit_exit` default | **None — production path off** |
| clean OOS | **untouched** |
| forward evaluation | frozen until 2026-10-12, untouched |
| production files modified | **none** |
| new economic registration | **none created** |
| promotion candidate | **none created** |
| H-0011 | **frozen — spec, parameters and verdict unchanged** |
| registrations / chain | 11 / intact |
| thirty-year reads | **13 → 13 (+0)** |
| decade reads | 112 → 116 (+4: the reproduction, permitted) |
| evidence classified by provenance | **yes, §8** |
