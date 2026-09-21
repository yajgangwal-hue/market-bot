# H-0019 — opportunity generation capability audit

*Sealed `6d04c818…` at commit `8b7ce1a9`, before any measurement. Read-only:
no strategy built, no portfolio constructed, no trade simulated, no parameter
swept, no production change, no promotion.*

---

## Classification: **A — MATERIAL OPPORTUNITY-GENERATION GAP**

One of the five registered probes — **P3, the population the ATR ceiling
rejects** — meets every sealed criterion. It is nominated for a separately
sealed economic experiment, **and nothing else is authorised.**

Four of the five suppressed classes are null or negative once symbol and date
effects are removed. **This is not a finding that the generator is broadly
blind to opportunity.** It is a finding about one boundary.

---

## A. Governance

| check | state |
|---|---|
| H-0019 seal | `6d04c81876cd60a2acacf5a4061802da3ad826fe7ee7240a690632aea26ea4c7` |
| H-0019 registration commit | `8b7ce1a9c45ee22723f65d1ec0e845821630364d` |
| H-0018 seal / report | `215faa17…` · `docs/2026-09-21-h0018-report.md` — present |
| **baseline equivalence** | **+58.5889000000% / 698 — PASS** (re-verified in both passes) |
| fingerprint | `da22011e…c237b` — unchanged |
| RSI 35.0 · trend MA 200 · ATR ceiling 3.5% · stop 2.5× | unchanged |
| bucket 1 · positions 12 · entries/day 3 · risk 0.005 · notional 0.20 · ADV 0.02 | unchanged |
| production haircut | 0.652% — unchanged, and **not used anywhere in this audit** |
| ranker / veto / learned | OFF |
| clean OOS | untouched, 0 sessions, frozen to 2026-10-12 |
| H-0011 / H-0013 / H-0015 / H-0016 / H-0017 / H-0018 | frozen |
| `src/` since the waived `dc329bb` | **0 commits** |
| registrations / chain | **19 / intact** · thirty-year reads **13** |

The broker fix `dc329bb` remains unreverted and enters no calculation here.

## B. The generator, traced from code

`mean_reversion.evaluate` emits `BUY` only when **all** of the following hold,
and `STAND_ASIDE` otherwise:

| # | condition | value |
|---|---|---|
| 1 | `close >= min_price` | 20.0 |
| 2 | 20-day dollar volume ≥ floor | 50,000,000 |
| 3 | `close > SMA(200)` | **uptrend only** |
| 4 | `RSI(14) <= rsi_entry` | **oversold only** |
| 5 | `ATR(14)/close <= max_atr_fraction` | **calm only** |
| 6 | `close - 2.5·ATR > 0` | positive stop |

`action = "BUY" if not reasons`. There is no second action. The function
cannot emit a short, cannot emit a continuation, and never compares one symbol
with another. **The whole generator is a single-symbol, daily-close, long-only
oversold filter.**

So the structural exclusions are facts about the code, not hypotheses:
momentum and continuation (4), everything below its own 200-day (3),
volatility shocks (5), the entire short side (no such action), any
cross-sectional comparison (no such input), any intraday behaviour, any event
behaviour.

**Every indicator below comes from production's own `evaluate()`** — `rsi`,
`trend_ma`, `atr_fraction`, `close` and `stop` are returned on the signal
object whether it says BUY or STAND_ASIDE, so one call per symbol-session
yields the production population and every suppressed population from
identical arithmetic. Nothing was reimplemented.

## C. Sealed measurement

536,324 symbol-sessions scanned across the 230-symbol decade universe;
**487,919** passed price, liquidity and positive-stop. Forward return is
SPY-relative from the decision close, day-collapsed before any t.

| population | obs | days | fwd10 SPY-rel | t (day) | win% |
|---|---:|---:|---:|---:|---:|
| PROD (reference) | 5,081 | 1,282 | +0.0970% | +0.67 | 50.1% |
| P1 discarded half | 20,526 | 2,104 | −0.0350% | +0.20 | 49.2% |
| P2 momentum | 68,848 | 2,354 | +0.1632% | −0.37 | 49.2% |
| **P3 volatility-excluded** | **1,267** | **533** | **+2.4359%** | **+4.35** | **60.1%** |
| P4 cross-sectional | 47,429 | 2,460 | +0.3824% | +5.14 | 50.1% |
| P5 volume shock | 4,507 | 1,629 | +0.1089% | −0.19 | 46.7% |

The probes rank almost exactly in order of their own volatility. **That is
what beta in a rising decade looks like**, and it is the reason the next
section exists.

## D. Validity controls — **not in the seal, and stated as such**

Two rival explanations had to be killed: the probe fires on high-beta names
(symbol effect), or on stressed days the whole market bounced from (date
effect). Both are removed with an additive two-way control — predicted =
grand + (symbol mean − grand) + (date mean − grand) — and the **lift** is what
the probe earned above it.

The symbol and date effects are fitted on the full gate-passing sample,
**including each probe's own observations**, so every probe partly predicts
itself and its lift is understated. That bias runs against a positive finding.
**No control here could turn a null into a nomination** — which is why adding
them after seeing the sealed result is not a probe swap.

Pool 485,659 observations, grand mean +0.1803%.

| population | raw | predicted | **LIFT** | t (day) | 2016-19 | 2020-23 | 2024-26 |
|---|---:|---:|---:|---:|---:|---:|---:|
| PROD | +0.0970% | −0.0013% | +0.0162% | +0.16 | +0.062% | +0.498% | −0.544% |
| P1 | −0.0350% | −0.1509% | +0.1356% | +2.01 | +0.198% | +0.211% | −0.041% |
| P2 | +0.1632% | +0.1050% | **−0.1479%** | −2.21 | −0.096% | +0.041% | −0.472% |
| **P3** | +2.4359% | +1.0471% | **+0.8513%** | **+2.28** | **+0.346%** | **+0.666%** | **+1.255%** |
| P4 | +0.3824% | +0.3586% | +0.0407% | +0.64 | +0.370% | −0.055% | −0.208% |
| P5 | +0.1089% | +0.3071% | **−0.3797%** | −2.38 | −0.017% | −0.852% | −0.126% |

**P4 collapses.** Its headline +0.3824% at t=+5.14 was almost entirely symbol
and date effects; the lift is +0.0407% at t=+0.64, positive in one third only,
and **negative (−0.1365%) on the ETF subset.** Had I reported §C and stopped,
I would have nominated a cross-sectional reversal factor that does not exist.

**P2 and P5 are negative.** The RSI ceiling and the absence of a volume signal
are both doing real work. P5's headline +0.1089% is worse than useless:
**63.0% of its total came from five observations**, and its median is −0.289%.

**P1 is the subtle one.** Positive lift (+0.1356%, t=+2.01; +0.2547%, t=+3.03
on ETFs) but **negative raw return** (−0.0350%, median −0.024%). Oversold
below the 200-day beats its own symbol-and-date baseline while still losing to
SPY. A long-only bot cannot eat lift. **The trend filter is correct.**

### Concentration — is a mean carried by a handful of rows?

| population | median | trimmed 5% | top-5 share | top symbol | top day |
|---|---:|---:|---:|---:|---:|
| PROD | +0.005% | +0.048% | 22.6% | 1.3% | 1.0% |
| **P3** | **+1.724%** | **+2.144%** | **8.5%** | 3.4% | 1.5% |
| P5 | −0.289% | −0.145% | **63.0%** | 1.2% | 0.9% |

P3's **median is +1.72%** and its trimmed mean is *higher* than its mean. It is
a broad population effect, not five lucky rows.

### Survivorship — the ETF subset, this project's standing control

| population | obs | raw | **LIFT** | t | thirds |
|---|---:|---:|---:|---:|---|
| PROD | 1,497 | +0.0295% | +0.1893% | +1.43 | +0.002 / +0.092 / +0.482 |
| P1 | 8,137 | −0.1702% | +0.2547% | +3.03 | +0.203 / +0.334 / +0.193 |
| **P3** | **99** | +2.2775% | +2.5968% | +2.61 | +1.934 (n=2) / −0.716 / +6.701 |
| P4 | 6,858 | −0.2876% | −0.1365% | −1.30 | +0.062 / −0.468 / +0.212 |

**This control does not clear P3.** 99 observations, one symbol supplying
16.2% of them, one third holding two, and the lift carried by 2024-2026. It is
positive, and it is under-powered. **The survivorship question on P3 is open**,
and §H treats it as the first thing the next experiment must answer.

## E. Is P3 reachable? Production enters at the **next open**

Close-to-close measures a price the bot can never pay. Measured from the
following session's open instead:

| | close → +10 | **next open → +10** | overnight gap | share of move | win rate |
|---|---:|---:|---:|---:|---:|
| PROD | +0.0964% | **+0.0101%** | +0.0848% | **88%** | 50.1% → 48.9% |
| **P3** | +2.4359% | **+1.9242%** | +0.5100% | **21%** | 60.1% → 57.1% |

**P3 survives entry timing** — median +1.3458% from the open, 57.1% win rate.

The PROD row is the more uncomfortable one and is reported because it was
measured: **88% of the production population's fixed-horizon SPY-relative move
happens in the overnight gap**, and from the next open it is +0.0101% with a
*negative* median. This is not a verdict on production — production does not
hold ten fixed days; it exits on RSI ≥ 60, a 20-bar cap or a 2.5-ATR stop, so
the horizon is mismatched. It is consistent with the standing reading that
selection is positive and timing is the drag.

## F. Scale — per-observation return is not per-dollar return

Production sizes off risk, so a high-ATR position gets **less** capital:
`notional = min(0.20, 0.005 / (2.5 · atr_fraction))`. Arithmetic under
production's own sizing formula, ignoring the conviction multiplier, cash,
buckets, slots and the 3/day cap:

| | median ATR frac | mean notional | raw fwd10 | **equity contribution / obs** |
|---|---:|---:|---:|---:|
| PROD | 2.10% | 10.63% | +0.0970% | +0.0007% |
| **P3** | 4.71% | **4.02%** | +2.4359% | **+0.0673%** |

Risk-based sizing cuts P3's capital by 2.6×, and it is still ~96× production's
contribution per observation.

**The tempting next line is a decade total, and it must not be believed.**
Summing gives +85.22 points for P3 and +3.66 for PROD, but that sum is not a
portfolio: PROD's 5,081 observations at 10-day holds imply ~19.5 concurrent
positions at 10.63% each — **207% of equity, which is impossible**, and
precisely why production takes 698 of those 5,081. The sum is recorded here
only so that it is on the record as rejected.

## G. Composition of P3

132 distinct symbols. Broad, but back-loaded and survivorship-exposed:

`2016:6 · 2017:35 · 2018:42 · 2019:33 · 2020:88 · 2021:152 · 2022:177 ·
2023:98 · 2024:205 · 2025:306 · 2026:125`

**Half the population sits in 2024-2026; 2016-2019 holds 116 observations.**

| cohort | n | mean | median |
|---|---:|---:|---:|
| in the universe since 2016-01-04 | 936 | +1.921% | +1.709% |
| listed later | 331 | +3.891% | +2.222% |

The effect is roughly twice as large in later-listed names — but it persists
at +1.921% in the full-decade cohort, so it is not confined to recent IPOs.
**That does not resolve survivorship**: membership of the 230 was decided in
2026, so a 2017 high-ATR name that collapsed is absent from both cohorts.

## H. Adjudication against the sealed criteria

| sealed requirement for A | P3 |
|---|---|
| structurally absent from the generator | **yes** — condition 5 makes it impossible to emit; registered as a structural exclusion in the seal |
| fires often enough to matter | **yes** — 1,267 obs / 533 days ≈ 127 a year, against production's 70 trades a year |
| material against the standing reference | **yes** — +2.4359% raw, +1.9242% from the reachable entry, +0.8513% lift after controls |
| clears a realistic round-trip cost | **yes** — 12 bps by the project's own cost model; clears at 25 and 50 bps too |
| holds in ≥ 2 of 3 chronological thirds | **yes** — raw +1.385 / +1.261 / +3.579; lift positive in all three, though **none individually significant** |
| independent of the production signal | **yes** — 0.0% symbol-session overlap (mutually exclusive by construction), daily-return correlation +0.150; on days production had no candidate at all, +2.466% (n=186) |

**Outcome A is reached.** I record that I would have preferred to argue P3 out
of it — it is the same behaviour class as production with one parameter
boundary inverted, not a new class the architecture cannot represent. But I
sealed "volatility shocks (rule 5)" as a structural exclusion *before* seeing
any result, and the rule that forbids reclassifying after the fact cuts in
both directions.

### What A does **not** mean

1. **This is a parameter question wearing a capability costume.** No new input,
   no new data, no architectural change is needed to represent P3 — only a
   different value of `max_atr_fraction`. Twelve of twelve parameter
   experiments in this programme have been rejected.
2. **Survivorship is unresolved** (§D, §G) and is the largest single threat.
3. **Drawdown.** P3 *is* the high-volatility population. The 110% ceiling of
   **14.2806% is never loosened**, and the owner's standing preference is lower
   drawdown. Risk-based sizing shrinks these positions automatically (§F),
   which helps, but the ceiling is the binding constraint on this branch.
4. **Portfolio competition.** H-0015 and H-0016 showed slots, buckets, the
   3/day cap and cash all bind. P3 candidates would compete with production's
   own, so **no portfolio-level gain is implied by any figure above.**
5. **The 10-day horizon is not production's exit rule**, and no cost model,
   haircut, fill or participation cap has been applied to anything here.

### The other four classes

**Opportunity generation is not broadly the bottleneck.** Momentum and volume
shocks are negative after controls; cross-sectional ranking collapses to noise;
the discarded half of the trend filter has positive lift but negative raw
return and is unusable long-only. The generator's filters are, on this
evidence, mostly correct — the trend filter and the RSI ceiling both earn
their place.

## I. Next step — outcome A, per the registered rule

Exactly one class is nominated: **P3, the ATR-ceiling-rejected population.**
A **separately sealed** economic experiment may be *designed*; nothing is
authorised to run, and no parameter moves. Its design must be built to
falsify, and must lead with:

- a **survivorship-resistant** construction, since the ETF control (99 obs)
  does not clear it and the standing thirty-year rule exists for this reason;
- **drawdown as a primary metric, not a footnote** — the 14.2806% ceiling
  binds this branch harder than any other;
- **portfolio-level** measurement, because H-0011 showed trade-level sums do
  not survive contact with cash, buckets and slots;
- the **production exit rule**, not a fixed horizon;
- full execution assumptions, which this audit deliberately applied to nothing.

**Nothing is promoted. No parameter changed. No experiment registered here.**

## Governance end state

`src/` unchanged since `dc329bb` (broker adapter only, waived) · fingerprint
unchanged · ATR ceiling still 3.5% · haircut 0.652% unchanged ·
H-0011/H-0013/H-0015/H-0016/H-0017/H-0018 frozen · no promotion · no live
brokerage order placed by this audit · clean OOS untouched · **19
registrations, chain intact** · thirty-year reads **13**.
