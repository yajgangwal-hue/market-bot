# Recognized gains and news information — capability audit

> ## ⚠ IDENTIFIER COLLISION — read first
>
> This work was commissioned as "H-0019". **H-0019 is already sealed and
> adjudicated** (`6d04c818…`, commit `8b7ce1a9`, outcome **A**, opportunity
> generation → P3 nomination), as are **H-0020** (`f38dbbaa…`, outcome **C**,
> P3 killed) and **H-0021** (`563d778a…`, give-back anatomy).
>
> **The next free identifier is H-0022**, and that is what this audit is.
> The filename was kept as requested; I recommend renaming it to
> `2026-09-22-h0022-…` so the governance record stays unambiguous.

*Capability audit. **No experiment registered.** No parameter changed, no
counterfactual run, no promotion, no live order, clean OOS untouched.*

---

## Classification: **C — CURRENT ACCOUNTING/NEWS CAPABILITY IS NOT THE BOTTLENECK**

**Recognized gains:** accounting reconciles to machine precision and realised
capital is spendable in the *same session* it is earned. Zero delayed capital,
zero sessions of delay. Definitively not a bottleneck.

**News:** the information *is* structurally independent — 81.25% of news
symbol-days are ones the generator never looks at — but the only economic test
the corpus supports collapses to **t = 0.01**, and the corpus cannot support a
more reliable one. That sub-branch is blocked by **D (data limitation)**, and
§F states the minimum data that would change it.

---

## A. Governance

| check | state |
|---|---|
| baseline | **+58.5889000000% / 698 trades** — reproduced |
| fingerprint | `da22011e…c237b` — **unchanged** |
| RSI entry / max positions / risk / haircut | 35.0 / 12 / 0.005 / 0.652% — unchanged |
| costs | 2.0 bps half-spread + 4.0 bps slippage — unchanged |
| ranker / veto / learned | OFF |
| H-0011 / H-0013 / H-0015 / H-0016 / H-0017 / H-0018 | **frozen, not reopened** |
| H-0018 | remains **B — measurement value exists, economic leverage not established**; MBO branch stays closed |
| broker adapter `dc329bb` | untouched; **not** used as strategy evidence |
| stop-coverage remediation (REM-0007/0008) | separate operational track; **not** strategy evidence |
| BAC sale 2026-09-22 15:30:59 | operational only. Provenance does **not** prove the scheduled loop: the loop logged `hold` at 15:30:26, 33s earlier. Not attributed. |
| clean OOS | **0 sessions**, untouched, opens 2026-10-12 |
| registrations / experiments | 21 / 53 — unchanged |

---

## B. Recognized-gain accounting

### The lifecycle, traced from `portfolio.py`

Production runs `entry_fill = "signal_close"`. Within one session:

| § | step | line | effect on cash |
|---|---|---|---|
| 1 | pending fills | ~389 | `cash -= outlay` — **`next_open` path only; not production** |
| 2 | exits | ~704 | **`cash += proceeds`** |
| 2 | mark-to-market | ~736 | `equity = cash + invested` |
| 3 | entries at the signal close | ~1007 | `if outlay > cash: rejected_for_capacity` |

**Exits credit cash in section 2; entries test cash in section 3 of the same
session.** Recognition is immediate and ordering is favourable.

| Layer | Finding | Evidence |
|---|---|---|
| Trade accounting | **EXACT** | `report.realized_pnl == Σ net_pnl`, gap **0.0000000000** |
| Equity accounting | **EXACT** | `equity == cash + invested`, gap **0.0000000000** |
| Full identity | **EXACT** | `start + realised + unrealised == equity`, gap **1e-10** on $158,588.93 — machine epsilon |
| Cash recognition | **IMMEDIATE** | proceeds credited at exit, same session, before any entry test |
| Capital availability | **CORRECT** | 214 sessions had both an exit and an entry; **310 entries were taken on those sessions**, which is only possible if section-2 proceeds are spendable in section 3 |
| Candidate impact | **NONE attributable to recognition** | of 247 sessions containing a cash rejection, 65 also closed a position — and **$1,252,349 of proceeds had already been credited** on those sessions before the rejection occurred |
| Economic impact | **ZERO** | maximum delayed capital **$0**; delay duration **0 sessions** |

Reconciliation: 100,000.00 + 57,559.93 realised + 1,029.00 unrealised =
**158,588.93** = equity. Two positions open at the end.

### The three questions, kept apart

- **A Accounting correctness — YES.** Exact to machine precision.
- **B Capital availability — YES.** Same-session, proven by 310 entries on
  exit sessions.
- **C Economic opportunity — MOOT.** There is no delay to recover. The 65
  rejection-sessions that also closed a position had the proceeds *already
  credited* and were still short. The cash constraint is real, but it is
  **not caused by unrecognised capital.**

*Note, not re-litigated:* `rejected_for_capacity` = **839** while the H-0015
attribution labels **841** rows `cash`. H-0015 already documented the two
strays as `fill ≤ stop_ref`. H-0015 is frozen; carried forward as-is.

**One latent defect, in a non-production path.** The `next_open` fill path
tests cash in section 1, *before* section 2 credits exit proceeds. Under
`entry_fill="next_open"` a same-session exit's capital would **not** be
available. Production does not use that path. Recorded so it is not
rediscovered as a surprise.

---

## C. News inventory — verified, not assumed

Two archives exist and they are different things.

| Property | `data/phase5/news-archive-deep.jsonl` (research) | `data/news/*.jsonl` (live recorder) |
|---|---|---|
| items | **11,852** — confirmed | 8,787 rows over **8 days** |
| span | 2016-11-07 → 2026-09-04 | ingestion 2026-09-15 → 09-22 |
| distinct `item_id` | 11,852 — **0 duplicate ids** (414 duplicate *headlines*, 3.5%) | 2,627 duplicate ids |
| **article bodies** | **0** | **0** |
| symbol tagging | 6,945 distinct symbols; median 2.0/item, **26.9% tag >5** | only **226 of 8,787 (2.6%)** carry any symbol |
| single-symbol universe items | **4,675** | — |
| sources | **100% tier 2, zero tier-1 primary**; 37.7% unattributed | 78% one RSS feed |
| **revised after publication** | **702 (5.9%)** — today's text against the original timestamp | — |
| availability timestamp | **ABSENT** (publication ≠ when a subscriber saw it) | `fetched_at` present |
| deletions | **UNDETECTABLE** | — |
| coverage stationarity | **40.2% (2019) → 77.2% (2025)** — density nearly doubles | n/a |
| survivorship | windows requested for **today's** universe, so a delisted name leaves no gap | same |
| PIT enforcement in code | **SOUND** — `Archive.snapshot` admits only `published_at` strictly before the 15:45 ET decision, with the correct DST rule | `visible_at()` gate exists |

The engine's timestamp enforcement is correct. **The residual risk is in the
corpus, not the code** — and three of ten PIT properties are UNVERIFIED or
UNVERIFIABLE.

---

## D. News information classes

| Class | Frequency | PIT usable? | Incremental information? | Independent? |
|---|---|---|---|---|
| Company-specific, single-symbol | 4,675 items / 1,963 symbol-days | yes, with the caveats above | **no** — see below | **yes**, 81.25% non-overlapping |
| Earnings-tagged | 117 taken trades | yes | separates on taken trades only | **no** — matched by the any-news control |
| Multi-symbol baskets | 26.9% tag >5 symbols | yes | tagging quality too weak to attribute | n/a |
| Market-wide / macro (RSS) | ~8,561 live rows | yes | **no symbol mapping at all** | n/a |
| Duplicated / low-information | 414 repeated headlines | — | by construction none | — |

**Bodies do not exist in either archive.** Median headline length 13 words.
Any language-model premise has no input — stated here because it is the single
most common proposal for this branch.

---

## E. Opportunity overlap — the one genuinely new measurement

Does news surface opportunity the RSI≤35 generator cannot see?

| | count |
|---|---|
| single-symbol universe items | 4,675 |
| distinct (symbol, date) news pairs | **1,963** |
| production-evaluated candidate pairs | 1,539 (698 accepted) |
| news pairs that **are** production candidates | **368 (18.75%)** |
| news pairs on symbol-days the generator **never looked at** | **1,595 (81.25%)** |
| news days / candidate days / overlap | 968 / 682 / 460 |
| **news days with no production candidate anywhere** | **508** |

**News is structurally independent.** Four in five news symbol-days are
invisible to the generator, and 508 news days contain no production candidate
at all. On *information* grounds this is a genuine opportunity-generation
class.

**And it has no measured economic content.** The prior feasibility study
(`docs/2026-09-18-news-feasibility.md`, classified **A — NO EVIDENCE**) already
measured exactly this strategy-independent population — 4,668 single-symbol
universe headlines, forward excess vs SPY from the first session after
publication, nothing from the publication day used:

- **the direction runs backwards**: favourable − adverse at 10 sessions =
  **−0.704%**;
- **the sign flips across thirds**: −0.934% / **+0.709%** / −1.243%;
- **day-collapsed, everything collapses**: adverse **t = 0.01**, favourable
  t = −0.86, none t = −0.96.

Adverse headlines at t = 0.01 is as close to exactly zero as a result gets.
I did not re-run it, and I am not re-running it.

---

## F. Economic leverage, by level

| Level | Recognized gains | News |
|---|---|---|
| **Accounting value** | **Confirmed exact** — identities to 1e-10 | n/a |
| **Information value** | none to add; nothing is unrecorded | **YES** — 81.25% of news symbol-days are outside the generator's view |
| **Decision value** | **none** — capital is already available in time | **NOT ESTABLISHED** — day-collapsed t = 0.01 |
| **Execution value** | none | none — no body text, no intraday mapping |
| **Portfolio value** | **none** — the 65 coincident rejection-sessions already had $1.25m credited | **NOT ESTABLISHED**; and P5-0011/12/13 showed the earnings filter (−10.8 pts) was indistinguishable from the any-news control (−10.7 pts) — it was "trade less", not "news" |
| **Economic value** | **ZERO, and bounded exactly** | **NOT ESTABLISHED, and not establishable on this corpus** |

### Why the levels must not be skipped

News clears **information value** and fails at **decision value**. That is
precisely the trap §17 exists to prevent: an independent information source is
not an edge. Conversely recognized gains clears **accounting value**
perfectly and has no information to add — an accounting difference is not an
alpha source, and here there isn't even a difference.

---

## Prioritisation (§21)

| criterion | Recognized gains | News |
|---|---|---|
| demonstrated capability gap | **none** (exact, same-session) | information gap real (81.25%) |
| economic leverage | **$0, bounded** | zero measured (t = 0.01) |
| independence | n/a | high |
| data quality | perfect (internal) | **poor** — no bodies, 5.9% revised, no availability stamp, deletions invisible |
| PIT integrity | n/a | code sound, **corpus unverifiable** |
| frequency | n/a | adequate |
| stability | n/a | **sign flips across thirds** |
| ability to test cleanly | fully | **no** — coverage 40%→77% makes any calibration untransportable |

Neither branch justifies an economic experiment. Recognized gains is closed on
positive proof; news is closed on measured nullity plus a corpus that cannot
support a better test.

---

## Next step (§24, outcome C)

**Move to the next genuinely unresolved capability gap.** Both branches close.

Recorded so the news branch is not reopened on the same data: the **minimum**
that would change it is (1) article **bodies**, (2) a true **availability**
timestamp distinct from publication, (3) a corpus with **stationary coverage**
and (4) **deletion/revision provenance**. Items 1–2 are vendor-licensing
questions, not engineering ones. Whether acquiring them is justified is a
separate decision, and on the evidence above the expected value is low.

Per the standing inventory, the highest-value remaining item is still
**category B and not a new edge**: a delisting-complete point-in-time universe,
which would size the existing edge rather than propose another one
(EXP-0031 bounds decade CAGR between **3.82%** and **9.14%**).

---

## Production status

Fingerprint `da22011e…c237b` unchanged · RSI 35/60 · ATR ceiling 0.035 ·
20-bar cap · 2.5× ATR stop · risk 0.005 · buckets, sizing, cash rules, haircut
0.652% — all unchanged. News remains **outside the money path** (zero imports
in `autotrade`, `portfolio`, `mean_reversion`, `strategy`, `risk`, `broker`).
Clean OOS untouched, 0 sessions, 2026-10-12. Registrations 21, declared 60,
experiments 53, chain intact, thirty-year reads 13. **No experiment
registered. Nothing promoted. No performance claim made.**
