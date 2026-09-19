# News as an information source — read-only feasibility

*2026-09-18. **FORENSIC_NON_PROMOTIONAL.** No experiment registered. No
file in `src/` touched. Nothing promoted.*

## Classification: **A — NO EVIDENCE**, and the blocking reason is data, not method

**The archive has no article content.** 11,852 items, and the fields
are `headline, published_at, symbols, source, tier, revised`. Zero
`summary`, zero `content`. Median headline length **13 words**.

Last turn I suggested that reading news *content* was the one honest
version of "make the model smarter", because a language model can read
prose that a gradient booster cannot. **That is not executable on this
data — there is no prose to read.** Correcting my own recommendation
before it costs anything.

And where headlines *can* be tested, the direction is wrong, unstable,
and vanishes under clustering.

---

## 1. Historical coverage

| | |
|---|---|
| items | 11,852 |
| span | 2016-11-07 → 2026-09-04 |
| universe symbols with ≥1 item | 226 of 230 |
| with ≥20 items | 188 |
| with zero | 4 |

Per year: 92 (2016), 678, 910, 599, 656, 1532, 635, 1996, 2084, 1460,
1210 (2026).

## 2. Point-in-time availability

The engine is strict and correct: `Archive.snapshot` admits an item only
when `published_at` is **strictly before** the 15:45 ET decision
timestamp, converted with the DST rule in force that year. A worked case
already in the checkpoint shows five COST stories excluded because they
post-dated the decision — a date-based join would have used all five.

`quality_report` on the live archive:

| property | status |
|---|---|
| available before the decision | **ENFORCED** |
| timestamp reliable | PARTIAL — 11,852/11,852 parse, but vendor time, not source time |
| ingestion/availability timestamp | **ABSENT** |
| source identifiable | PARTIAL — 62.3% name a vendor |
| security correctly associated | **WEAK** — 26.9% tag more than 5 symbols |
| duplication | 414 repeated headlines (3.5%) |
| could contain future knowledge | **RESIDUAL RISK** — 702 (5.9%) revised after publication, stored as today's text against the original timestamp |
| deletions | **UNDETECTABLE** |
| reconstructable historically | PARTIAL |

Three of ten properties are UNVERIFIED or UNVERIFIABLE. The Phase 5
checkpoint already marked this corpus **"UNVERIFIED for point-in-time
trustworthiness and excluded from any performance conclusion"** —
admissible for hypothesis generation only. Nothing found here changes
that.

## 3. Usable trade candidates

Strict rule: published in `[decision − 72h, decision)`.

| | candidates | covered | single-symbol item |
|---|---|---|---|
| all | 5,087 | **2,962 (58.2%)** | **1,915 (37.6%)** |

**Coverage is severely non-stationary:**

| year | candidates | covered |
|---|---|---|
| 2016 | 44 | 52.3% |
| 2018 | 577 | 46.8% |
| **2019** | 376 | **40.2%** |
| 2022 | 289 | 61.9% |
| 2024 | 860 | 62.7% |
| **2025** | 457 | **77.2%** |
| 2026 | 330 | 75.8% |

From 40% to 77%. Any feature calibrated on this history is calibrated
on a corpus whose density nearly doubled, which alone would make it
untransportable forward.

## 4. Winner / loser coverage

Taken trades: 446 of 698 (63.9%) covered.

| | coverage |
|---|---|
| winners | 220/357 = **61.6%** |
| losers | 226/341 = **66.3%** |

A 4.7-point imbalance toward losers. Small, but it runs the direction
that would flatter any "news predicts trouble" reading, and by
chronological third it is 48.0%/59.6% (early), 61.5%/64.3% (middle),
76.1%/74.4% (late) — the imbalance is an artefact of the early, thin
period.

## 5. Duplicates, symbol association, sources

| | |
|---|---|
| duplicate headlines | 414 (3.5%) |
| revised after publication | 702 (5.9%) |
| tier | 100% tier 2; **zero tier-1 primary sources** |
| unattributed | 4,472 (37.7%) |
| single-symbol items | 4,675 (39.4%) |
| items tagging >5 symbols | 26.9% |
| median symbols per item | 2.0 (mean 6.0) |

Only 39.4% of items are about one company. The rest are baskets, and the
first record in the file is *"Why Aren't There More Women In U.S.
Politics?"* tagged AAPL/ACN/FB/IBM/MSFT — which is the tagging quality
problem in one line.

## 6. Does content separate outcomes?

### 6a. On taken trades — already known, already rejected

| group | n | mean $ | median R | win | stop% |
|---|---|---|---|---|---|
| no items | 252 | +$149 | +0.194 | 54.4% | 34.1% |
| items, no keyword | 264 | +$62 | +0.032 | 50.8% | 35.2% |
| adverse > favourable | 63 | −$27 | −0.189 | 46.0% | 42.9% |
| favourable > adverse | 96 | +$91 | +0.031 | 51.0% | 26.0% |
| **earnings headline** | 117 | **−$114** | −0.296 | 41.9% | 41.0% |
| no earnings headline | 581 | +$122 | +0.157 | 53.0% | 32.9% |

This separation is real and is already in the ledger as
`research_evidence`. It is also already **rejected as a portfolio
filter**: vetoing earnings cost −10.8 points, adverse cost −15.1, and
the decisive detail is that the earnings filter (−10.8) was
**indistinguishable from the any-news control (−10.7)**. The separation
was not specific to earnings; it was "trade less".

By chronological third the taken-trade separation is unstable too —
`adverse > favourable` runs −$182, −$57, **+$104**.

### 6b. Strategy-independent — the new test, and the decisive one

Every single-symbol headline about a universe name, forward excess vs
SPY measured from the **first session after publication** (nothing on
the publication day is used). 4,668 usable items — an order of magnitude
more than the 698 taken trades, and free of any selection by the
strategy.

| direction | n | excess 5s | excess 10s | win@10 | excess 20s | t@10 |
|---|---|---|---|---|---|---|
| adverse | 238 | +0.021% | +0.397% | 50.4% | +0.099% | 1.58 |
| favourable | 408 | −0.130% | **−0.308%** | 43.9% | +0.309% | −1.49 |
| none | 4,016 | −0.094% | −0.042% | 36.7% | −0.055% | −0.66 |

**favourable minus adverse at 10 sessions: −0.704%.** The keyword
direction runs **backwards** — "bullish" headlines are followed by
*worse* relative performance than "bearish" ones.

And it does not hold:

| third | favourable − adverse @10s |
|---|---|
| early (2016-11 → 2021-09) | −0.934% |
| **middle (2021-09 → 2024-04)** | **+0.709%** |
| late (2024-04 → 2026-08) | −1.243% |

**The sign flips.**

Then the test that settles it. These 4,668 items cluster on days and
across names; treating them as independent inflates everything.
Collapsed to one observation per session:

| direction | days | mean @10s | SE | **t** |
|---|---|---|---|---|
| adverse | 165 | +0.005% | 0.312% | **0.01** |
| favourable | 259 | −0.212% | 0.247% | **−0.86** |
| none | 885 | −0.133% | 0.138% | **−0.96** |

**Everything collapses to nothing.** Adverse headlines at t = 0.01 is as
close to exactly zero as a result gets.

## 7. Look-ahead risk, stated

The engine's timestamp enforcement is sound and I found no violation.
The residual risks are in the *corpus*, not the code:

1. **702 revised items (5.9%)** carry today's text against the original
   timestamp. The revision may contain knowledge the original did not.
2. **No availability timestamp.** Publication ≠ when a subscriber saw it.
3. **Deleted stories are invisible**, so the archive is survivorship-
   filtered in a way that cannot be measured.
4. **Windows were requested for today's universe**, so a delisted name
   leaves no gap.

## 8. Why this is A, not B

1. **There is no content to read.** Headline-only, 13 median words. The
   language-model premise has no input.
2. The keyword direction is **backwards** on the largest clean sample.
3. It **flips sign** across chronological thirds.
4. Day-collapsed it is **t ≈ 0** for every direction.
5. Coverage **nearly doubles** across the sample, so even a real effect
   would not transport.
6. The corpus is **already excluded from performance conclusions** by
   prior governance, and nothing here earns it back.
7. The one separation that exists on taken trades was already tested at
   portfolio level and was **indistinguishable from "trade less"**.

This is A for *this archive*. A corpus with article bodies, tier-1
sources, and event timestamps is a different question — but that is a
**data-acquisition problem**, not a modelling one, and it should not be
opened until someone is prepared to pay for and validate such a feed.

## 9. Governance

| check | result |
|---|---|
| frozen fingerprint | `da22011e…c237b` — **unchanged** |
| production source | **unchanged**; `src/` clean |
| `rsi_entry` / bucket cap / max positions | **35.0 / 1 / 12 — unchanged** |
| learned ranker / veto | `False` / `False` |
| model `.usable` / `is_promoted` | `False` / `False` |
| exit haircut | **0.652% unchanged** |
| 110% drawdown ceiling | **unchanged** |
| clean OOS | **untouched** |
| registrations | 8, chain intact — **none added** |
| promotion candidates | **none** |
| ledger | 30 experiments, 91 configurations — unchanged |
| thirty-year reads | **13** |
| decade reads | 80 — **this pass added none** (archive + cached candidates only) |
| tests | **1,191 passing** |

## 10. Where the next dollar of research should go

Per the directive's own rule — expected improvement × probability real ×
capital affected — news is now closed and the ranking changes.

**Not futures, and here is why.** This is a *cross-sectional single-name*
mean-reversion strategy: it buys individual oversold equities and ranks
them against each other. Index futures cannot express that — there are
no single-stock futures in this dataset, and ES/NQ would be a different
strategy wearing this one's name. The stated futures rationale is lower
execution friction, but the entry gap is already **−$6,913 against
$6,917 of modelled spread** on $50M+ ADV names: execution friction on
entry is essentially just the spread, and there is nothing there to
recover. Futures would be a new strategy, and it should be justified as
one rather than as an implementation of this.

**The largest unexplained fact in the whole body of work** is from the
breadth pass: the band the strategy actually trades, RSI ≤ 35, has
**+0.095% excess at 10 sessions against a dividend artefact of
+0.052%** — approximately **zero measurable edge**. The +58.59% decade
return decomposes to market +$95,566, selection +$23,836, timing
−$61,842. The strategy is mostly beta at 44% exposure, and its entry
signal is placed on a variable (`RSI` depth) the codebase already
records as noise.

So the next investigation is the one the breadth pass already named,
and it is now first by economic weight:

**Slot competition at RSI ≤ 40 — descriptive, read-only.** Of the 13,215
additional name-days in the (35, 40] hump, how many would actually win a
slot under *completely unchanged* capacity rules — same bucket cap, same
12-position cap, same 3-per-day cap, same sizing, same stops? This asks
whether a larger pool improves *selection within existing slots* rather
than adding trades, which is where the last three passes all say the
real constraint lives. It affects the entry decision on every session,
it needs no new data, and it converts the strongest surviving lead into
something registrable.

It must carry the disclosure that the 35–40 region was chosen after
seeing a seven-band table on this decade, and the 110% ceiling applies
unchanged.

## Artefacts

- `docs/phase5/news-feasibility.json`
- inputs: `data/phase5/news-archive-deep.jsonl` (11,852),
  `data/phase5/news-features-deep.jsonl` (698)
