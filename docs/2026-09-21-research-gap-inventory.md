# Research-gap inventory — frozen strategy

*Audit only. Nothing registered, nothing run, no production change, no
parameter touched. Fingerprint `da22011e…c237b` unchanged; clean OOS untouched
and still opening 2026-10-12.*

---

## Verdict

**No research direction currently available with existing data is strong
enough to justify a new experiment.**

The binding constraint on this project is no longer *information*. It is
**evidence**. Every information axis reachable with the data in hand has been
tested — entries, exits, regime, news, cross-section, capacity, cash — and the
failures share two signatures:

1. **Per-trade quality improves, the portfolio gets worse.** P5-0001 through
   P5-0005, EXP-0044, H-0009, H-0015, H-0016 and H-0020 all show it.
2. **Effects inflated by survivorship vanish on a universe that cannot
   delist.** EXP-0027 (+23.6%/yr → −1.5%/yr), EXP-0031 (decade CAGR 9.14 →
   3.82), H-0019 P4, H-0020.

The single highest-decision-value item in this inventory is **category B and
is not a new edge at all**: a point-in-time, delisting-complete universe,
which would tell you how large the existing edge actually is rather than
proposing another one.

### Correction to a figure I gave you earlier

I reported the exit-family DSR burden as "54 prior configurations plus
H-0011." That undercounted. There are **three ledgers**, and the exit family
also occupies the preregistration ledger:

| ledger | exit-family content |
|---|---|
| `experiments.jsonl` | 54 configurations across 12 experiments |
| `preregistrations.jsonl` | H-0001 (6), H-0002 (3), H-0003 (3), H-0004 (2), H-0005 (3), H-0010 (3), H-0011 (3) = **23** |
| `phase5-research.jsonl` | P5-0007 – P5-0010, P5-0015 – P5-0018 are the executions of those |

**The exit family carries ~77 configurations, not 54.** This strengthens the
H-0021 NO NEW CANDIDATE conclusion rather than weakening it — and note
**H-0001's registered mechanism was "a trailing stop that arms only after a
threshold gain," which is precisely the windowed-retracement form I ruled out
as a collision.** It was not merely similar; it was already registered and
already run.

---

## 1. Entry information

**All five orthogonal entry-filter axes have been tested and rejected** in one
sealed phase (P5-0001 – P5-0005), each on the frozen portfolio:

| axis | best configuration | decade Δ | why rejected |
|---|---|---:|---|
| ATR floor (stop inside noise) | 1.25% | **+7.5 pts** | non-monotone across 0.8/1.0/1.25/1.5%; removing 2019 leaves +0.9 |
| Distance above SMA200 | 1.0% margin | −16.5 pts | non-monotone; worse at every threshold |
| Pullback-from-high ("needs a drop") | −2.0% | −1.6 pts | non-monotone; −23.0 at −3.0% |
| Volume ceiling | 2.5× | **+10.1 pts** | monotone, but removing 2018 leaves **−1.1** |
| Composition of the two strongest | ATR 1.0% + margin 2% | −22.4 pts | the composition test failed outright |

The two that improved the decade (+7.5, +10.1) are the instructive ones: both
died on single-year dependence or non-monotonicity. This is the project's most
repeated failure mode and it is why an unused-parameter argument is not
sufficient grounds for research.

**Genuinely new information not yet used at entry** — i.e. not a variant of
RSI, SMA/trend, ATR, dollar volume, pullback-from-high, bucket or regime:

| information | status | note |
|---|---|---|
| Options-implied vol / skew at the decision close | **B** | forward-looking, not derivable from price history. Requires a PIT options vendor |
| Short interest / borrow cost | **B** | not available from the current vendor |
| Earnings surprise, estimate revisions, fundamentals | **B** | not available |
| Insider transactions (Form 4) | **C** | acquired and tested; all \|d\| < 0.2 |
| News / headline categories | **C** | closed decisively — see §5 |
| Index-membership flows | **B/D** | not available; and the universe is large-cap liquid, where flow effects are smallest |

**Indirectly already tested:** anything correlated with volatility (options IV
included) is partially probed by the ATR-floor and ATR-ceiling work
(P5-0001, H-0019 P3, H-0020) — but IV is not ATR, and the distinction is real.

## 2. Exit information

**Rule-design problems: exhausted.** ~77 configurations. Stop width
(EXP-0022), RSI exit region (EXP-0023), holding cap in both directions
(EXP-0019, EXP-0024), trailing stops (EXP-0036, H-0001), breakeven locks
(H-0003, H-0005 — classified **SPIKE**, a threshold artefact), scaling out
(H-0004, EXP-0036), take profits fixed and regime-varying (H-0002, EXP-0049 –
EXP-0052), tighter-stop-plus-target (H-0010), resting limit exits (H-0011 → B,
fragile). H-0021 closed the last lead.

**Daily-bar resolution problems**, i.e. what remains but cannot be answered
with daily data:

| open question | why daily bars cannot answer it |
|---|---|
| Where inside the cap window the executable peak sits | H-0021: peaks are diffuse (23/26/18/32% by quarter). Locating one needs the intraday path |
| Whether a rule-exit fill can beat the session close without hindsight | EXP-0048's ceiling used the day high and said so; H-0011 tried a limit and came back fragile |
| Whether the 190 queue-unresolved exits filled | H-0017: unresolvable in L1; H-0018: the whole economic span is a validated modelling charge |

**These are measurement questions with known low or negative economic value**,
not open opportunities. H-0018 already priced the largest of them.

## 3. Intraday information

Prior evidence, not re-run: **H-0014** measured intraday incremental
information at **≈ +0.006 IC** over a fitted daily baseline. **H-0017**
established that full-universe quote acquisition is infeasible and that the
vendor exposes no depth (`/v2/stocks/{sym}/book` → 404, no MBO at any tier).
**EXP-0007** rejected trading intraday swings inside a held position.

| unresolved question | minimum resolution needed | classification |
|---|---|---|
| Can a rule locate the cap-window peak in real time? | 1–5 min bars, full universe, full decade | **B** — and H-0014 caps the expected value near zero |
| Did the 190 hypothetical limit orders fill? | MBO / depth-of-book from a commercial feed | **B**, and **H-0018 already ruled the answer economically worthless** |
| Is the entry fill improvable within the session? | 1-min bars at the entry window | **C** — EXP-0008/EXP-0016/EXP-0017 covered this; signal-close fill shipped |

**Interesting but currently untestable** and, unusually, *already priced*: the
intraday branch is the one place where the cost of finding out has been
measured and is high while the measured information content is ≈ +0.006 IC.

## 4. Market-regime information

**P5-0022 is decisive and contradicts the intuitive direction.** The frozen
strategy annualises **+3.74% when SPY is above its 200-day and +9.81% when
below**; **−1.23% in calm volatility and +7.40% in stressed**. It
**underperforms SPY in every regime state**, and the timing drag is roughly
constant across regimes.

Rejected downstream of that: regime entry gates (EXP-0042/EXP-0043),
near-high abstention (EXP-0044), volatility-percentile abstention (H-0007,
family REJECTED), volatility targeting and regime filters (EXP-0009),
regime-tilted position size (EXP-0045/EXP-0047), regime exits (EXP-0036),
regime-varying take profits (EXP-0051/EXP-0052).

**Nothing genuinely unanswered remains** that uses the same information. A new
regime hypothesis would need a materially different *information source*, not
a different threshold on SPY versus its own averages — and none is available.

## 5. News / event information

**Closed, and closed by the cleanest control in the project.**

P5-0006 found the largest per-trade separation of that phase: 117 trades taken
into an earnings headline returned **−$13,395** against **+$70,955** from the
other 581, with a higher stop rate. It then failed at portfolio level — and the
decisive detail is the control:

> the earnings filter (**−10.8 points**) is indistinguishable from the
> **any-news control (−10.7 points)**

The separation was **not about news content at all.** It was about removing
trades. Any filter that removes a similar number performs the same. P5-0011,
P5-0012 and P5-0013 all made the account worse and deepened drawdown.
EXP-0040/EXP-0041 separately rejected the product-launch hypothesis
(buy-the-rumour-sell-the-news: +5.11% in the 30 sessions *before*, −0.58% on
the day +1).

The recorder (`news.py`, 7 sources, point-in-time with `fetched_at` and a
`visible_at()` gate) is correctly built and correctly *not* in the money path.
**Its existence is not a reason to research it.** Classification **C**.

## 6. Universe / cross-sectional information

**Closed twice, independently.**

- **EXP-0025** ranked candidates by overnight persistence, conviction and
  oversold depth: "0.58-pt spread, **ordering flips between windows**" —
  noise. (It also found the simulator had been allocating alphabetically.)
- **H-0019 P4** tested cross-sectional reversal directly: headline +0.3824%,
  t = +5.14 — and after the symbol+date control, **+0.0407%, t = +0.64**,
  positive in one third of three and **negative on the ETF subset**.

**Yes — H-0019's P4 result closes this avenue**, and it closes it in the most
useful way: it shows the apparent cross-sectional edge was beta and calendar.
Peer/sector relative strength is the same family and would face the same
control. ATR/P3 is closed by H-0020 and is not revisited.

## 7. Portfolio construction — the exact frozen funnel

From H-0015's sealed attribution (`seal 82c55dd2…`), on candidates that
reached evaluation:

| stage | count | share |
|---|---:|---:|
| candidates evaluated | **1,539** | 100% |
| accepted → trades | **698** | 45.35% |
| **rejected: cash** | **841** | **54.65%** |

Cash is the sole binder at the evaluation stage. Guard-level rejections
(buckets, position count, 3-per-day) resolve earlier; H-0015 measured the
entry cap as binding on **1.79% of sessions**.

**But capacity is not the bottleneck, and this is established three ways:**

- **H-0016**: the cash-denied candidates had **higher raw** and **worse
  SPY-relative** returns. The constraint refuses the worse names.
- **H-0020**: adding a disjoint candidate class produced **crowding, not
  addition** — 940 trades available, 795 taken, ~145 production trades
  displaced, return −16.9 pts, drawdown +6.9 pts.
- **EXP-0025**: allocation *order* among competing candidates is noise.

**The largest bottleneck is signal quality, not capacity, timing, correlation
blocking, cash or position limits.** The strategy underperforms SPY in every
regime state (P5-0022) with a win rate of 51.2% and an edge/noise ratio of
0.0776. More slots for the same signal is not an improvement — H-0020 measured
exactly that and it cost 16.9 points.

## 8. Validation limitations — "unknown" vs "negative evidence"

| limitation | status | quantified? |
|---|---|---|
| **Survivorship** | **NEGATIVE EVIDENCE, quantified** | EXP-0031: decade CAGR **9.14 → 3.82**, thirty-year **5.66 → 2.24**, positive in both halves. The edge is real; its size is inflated |
| **No point-in-time constituents** | **UNKNOWN** | all 230 symbols trade through 2026-09 — **zero delistings**. No PIT dataset exists in the project or from the vendor |
| **Benchmark** | **NEGATIVE EVIDENCE** | no configuration beats SPY on total return. SPY decade TR 15.00% vs price 13.42%. The strategy wins on drawdown only (Calmar 0.75 vs 0.45 decade) |
| **Data resolution** | **priced** | H-0014 ≈ +0.006 IC; H-0017 acquisition infeasible |
| **Experiment reuse** | **KNOWN AND LARGE** | ≥187 configurations in the experiment registry, 60 declared across 21 preregistrations, 39 phase-5 executions — all on one decade of one survivor universe |
| **Clean OOS** | **UNKNOWN — structurally** | **0 sessions.** Opens 2026-10-12. Nothing historical can substitute |

The distinction the directive asks for matters most here: **survivorship is
negative evidence** (measured, edge shrinks but survives), whereas **the true
PIT-universe magnitude and the forward performance are genuinely unknown.**

---

## Final table

| # | Research direction | Information required | Already tested? | Prior experiment(s) | Testable now? | Expected decision value | Main leakage / selection risk | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | Entry filters on ATR / trend margin / pullback / volume | none — existing | **yes, all five** | P5-0001…P5-0005 | yes | none | single-year dependence; per-trade↑ portfolio↓ | **C** |
| 2 | Options-implied vol & skew at entry | PIT options surfaces, decade, 230 names | no | partially probed by ATR work | **no** | **medium** — genuinely new, not price-derived | vendor PIT integrity; survivorship in the same universe | **B** |
| 3 | Short interest / borrow | PIT short-interest feed | no | — | no | low–medium | biweekly staleness; crowding proxy overlaps volatility | **B** |
| 4 | Fundamentals / estimate revisions | PIT fundamentals with restatement history | no | — | no | low | restatement leakage is severe and classic | **B** |
| 5 | Insider (Form 4) | already acquired | **yes** | Form 4 study, all \|d\| < 0.2 | yes | none | — | **C** |
| 6 | Exit rule redesign (any family) | none | **yes, ~77 cfg** | EXP-0019/22/23/24/36/48/49/50/51/52, H-0001…H-0005, H-0010, H-0011, H-0021 | yes | none | DSR burden alone disqualifies | **C** |
| 7 | Cap-window peak location in real time | 1–5 min bars, full universe, decade | feasibility yes | H-0014, H-0017, H-0021 | **no** | **low** — H-0014 caps it at ≈ +0.006 IC | overfitting the intraday path; acquisition cost | **B** |
| 8 | Queue resolution / MBO | commercial depth feed | feasibility yes | H-0017, H-0018 | no | **none** — span is a validated charge | treating a modelling charge as return | **C** |
| 9 | Regime gating / sizing / exits | none | **yes, 7 families** | P5-0022, EXP-0009/42/43/44/45/47, H-0007, EXP-0036/51/52 | yes | none | regime is 3 states on 1 decade — trivially overfittable | **C** |
| 10 | News / event as entry filter | already recorded | **yes, decisively** | P5-0006, P5-0011…P5-0013, EXP-0040/0041 | yes | none | **any-news control matched the earnings filter** | **C** |
| 11 | Cross-sectional ranking / relative strength | none | **yes, twice** | EXP-0025, H-0019 P4 | yes | none | beta + calendar masquerading as alpha | **C** |
| 12 | ATR ceiling / P3 | none | **yes** | H-0019, H-0020 | — | none | closed; not revisited | **C** |
| 13 | Portfolio capacity / cash / slots | none | **yes, three ways** | H-0015, H-0016, H-0020 | yes | none | crowding mistaken for addition | **C** |
| 14 | Candidate allocation order | none | **yes** | EXP-0025 | yes | none | ordering flips between windows | **C** |
| 15 | Idle-cash deployment | none | **yes, three ways** | EXP-0014 (accepted), EXP-0028, H-0006 | yes | none | — | **C** |
| 16 | **PIT, delisting-complete universe** | survivorship-free equity dataset with dead tickers | partially bounded | EXP-0031, EXP-0027, H-0020 | **no** | **HIGHEST** — sizes the existing edge instead of proposing a new one | substituting today's constituents backwards (explicitly forbidden) | **B** |
| 17 | Forward clean-OOS evidence | elapsed time | n/a | forward clock | **no** | **HIGH** | none — but it cannot be accelerated | **E** |
| 18 | Shorting / inverse signal | none | **yes, 4 experiments** | EXP-0011/12/13/26 | yes | none | the rule has no directional edge (EXP-0012) | **C** |
| 19 | Crypto sleeve expansion | none | **yes, 6 experiments** | EXP-0003/15/32/33/34/35 | yes | none | spreads at real cost | **C** |
| 20 | Learned-model veto | none | **yes** | EXP-0029, live walk-forward | yes | none | veto lost money monotonically | **C** |

**Category A: empty.** I could not construct a direction that is both testable
with existing data and genuinely novel. Saying so is the finding.

## What I would do instead of a new experiment

1. **Wait.** The clean forward record opens **2026-10-12** and is the only
   uncontaminated evidence this project will ever get. Nothing in the
   inventory outranks it, and no historical experiment can substitute.
2. **If budget is ever spent on data, spend it on #16, not on a new edge.**
   A delisting-complete universe converts the largest *unknown* into a number.
   EXP-0031 bounds the decade CAGR between 3.82% (ETF proxy) and 9.14%
   (survivor universe) — that 5.3-point range is wider than any effect this
   project has ever proposed to add.

## Governance

Nothing registered — **21 registrations, declared configurations 60, chain
intact**. No economic configuration spent. Thirty-year reads **13**. Frozen
fingerprint `da22011e…c237b`, ATR ceiling 0.035, RSI 35/60, 20-bar cap, 2.5×
ATR stop, sizing, buckets, cash rules, broker and learned models — all
unchanged. Clean OOS untouched, 0 sessions, opens 2026-10-12. No live trading
change.
