# H-0023 — survivorship-complete profitability ceiling audit

*Sealed `8bdbc0e5b7dfb2df0f21b5d30f1f860801d87ac870a0b97ca4157f03cbb30530`
at commit `db93c69c`, before any corrected return was computed. Read-only. No
parameter swept, no signal added, no execution assumption relaxed, nothing
promoted.*

---

## Classification: **D — PIT UNIVERSE CANNOT BE RECONSTRUCTED RELIABLY**

**The corrected economic comparison was not run, and running it would have
been the mistake.** The available delisted population is not a
delisting-complete record — it is a partial subset concentrated in 2018-2022.
A run on it would have corrected the middle of the decade and left both ends
survivor-biased, manufacturing a period-dependent artefact and then presenting
it through the seal's own chronological-thirds requirement as if it were a
finding.

**The +58.5889% remains un-validated against survivorship, and this audit does
not change that number in either direction.**

---

## A. Governance

| check | state |
|---|---|
| H-0023 seal | `8bdbc0e5…30530`, commit `db93c69c` |
| **baseline equivalence** | **+58.5889000000% / 698 — PASS**, re-verified after today's stop-safety commits |
| Sharpe / maxDD / exposure | 0.5107 / −12.9824% / 44.2794% — as stated |
| fingerprint | `da22011e…c237b` — unchanged |
| RSI 35/60 · ATR 0.035 · stop 2.5× · cap 20 | unchanged |
| risk 0.005 · 12 positions · bucket 1 · 3 entries/day · haircut 0.652% | unchanged |
| ranker / veto / learned | OFF |
| H-0011 … H-0021 | frozen, none reopened |
| clean OOS | **0 sessions**, untouched |
| registrations / declared | **22 / 62**, chain intact · thirty-year reads 13 |

---

## B. Two findings that precede the data problem

### B1. EXP-0031 does not bound what it is quoted as bounding — my own correction

Its record reads **`{"universe": "46 ETFs"}`**. The 9.14% → 3.82% comparison
therefore changes the **asset set** as well as the survivorship. It is a
survivorship-free *proxy*, not the same universe made complete, and the two
changes are confounded.

**I cited it in the research-gap inventory as "bounds decade CAGR between
3.82% and 9.14%." That was too generous — it bounds nothing cleanly.** It is
carried here as context only.

### B2. The universe has no reconstructable membership rule

`DEFAULT_UNIVERSE = tuple(CORRELATION_BUCKETS.keys())` — a hand-maintained
dict. `strategy.py` records the September 2026 assembly: *"Selected by the
strategy's OWN floors — $20 minimum price, $50m median daily dollar volume"*,
filtered for 3× funds, bitcoin wrappers and cash-equivalents, and stopped at
roughly the top 200 because *"past 200 the edge decays monotonically."*

Two distinct problems follow, and only the first is survivorship:

1. Membership was drawn from the **2026** cross-section — a survivor set by
   construction.
2. **The size of the list was chosen on measured edge.** That is a *second*
   selection effect layered on top of survivorship, and **no universe
   reconstruction removes it.** It is a property of how the list was built,
   not of which names are in it.

---

## C. What the delisted data actually supports

| property | finding |
|---|---|
| inactive US equities exposed by the vendor | 19,175 |
| on a major exchange (NYSE/NASDAQ/ARCA/AMEX/BATS) | 2,850 |
| with a real ticker pattern `^[A-Z]{1,5}$` | **2,092** (758 are warrants, CVRs, rights, escrows) |
| acquired successfully | 2,153 symbol records, 55.1 MB |
| bars terminate at the delisting date | **YES** — verified: ESRX 2018-12-20, CELG 2019-11-20, RTN 2020-04-02, MYL 2020-11-16, XLNX 2022-02-11 |
| **listing date in the asset record** | **ABSENT** |
| **delisting date in the asset record** | **ABSENT** |
| **delisting reason** | **ABSENT** — an acquisition at a premium and a bankruptcy are indistinguishable |

Applying production's own floors ($20, $50m 20-day ADV) to the decade window:

| population | count | symbol-sessions |
|---|---:|---:|
| eligible at least once | **332** | 110,650 |
| …but **still trading** (last bar ≥ 2026-09-01) | **57** | — |
| …with a ≥90-day gap (**ticker reuse**) | **16** | — |
| **clean, genuinely delisted, no reuse** | **273** | **80,858** |

---

## D. The four defects that force outcome D

### D1. The population is not delisting-complete — 22 of 22 absent

Every one of these would have cleared $20 / $50m ADV comfortably while listed.
**All are absent from the vendor's inactive-asset list:**

| absent | event | absent | event |
|---|---|---|---|
| BXLT | acquired Jun 2016 | CTXS | private Sep 2022 |
| STJ | acquired Jan 2017 | ABMD | acquired Dec 2022 |
| LLTC | acquired Mar 2017 | **SIVB** | **failed Mar 2023** |
| HAR | acquired Mar 2017 | **FRC** | **failed May 2023** |
| MJN | acquired Jun 2017 | ATVI | acquired Oct 2023 |
| RAI | acquired Jul 2017 | VMW | acquired Nov 2023 |
| TWX | acquired Jun 2018 | SGEN | acquired Dec 2023 |
| MON | acquired Jun 2018 | HZNP | acquired Oct 2023 |
| COL | acquired Nov 2018 | SPLK | acquired Mar 2024 |
| CA | acquired Nov 2018 | PXD | acquired May 2024 |
| TWTR | private Oct 2022 | HES | acquired 2024 |

**SIVB and FRC are the two 2023 bank failures — precisely the catastrophic
losers that survivorship bias exists to hide.** Their absence is not a detail;
it is the specific population the audit was commissioned to recover.

### D2. The coverage hole is systematic, not random

Delisting year of the 273 clean names:

```
2018: 19   2019: 63   2020: 52   2021: 68   2022: 58
2023:  1   2024:  2   2025:  7   2026:  3     2016-2017: 0
```

**Zero before 2018. Effectively nothing after 2022.** Adding these names would
survivorship-correct the middle third of the decade and leave the first and
last thirds uncorrected. The seal requires chronological thirds and the 2-of-3
rule — and under this population that machinery would faithfully report a
middle-third effect that is **entirely an artefact of vendor coverage**.

### D3. The `inactive` flag is unreliable

**57 of the 332 eligible names are still trading** — COR, LHX, MTCH, VXX, CZR,
IR, P, INFO, UN, AMTD, JOYY, APC among them. L3Harris and Match Group are not
delisted. Conversely **COHR sits in the curated universe and is flagged
inactive** while trading through 2026-09-21. The flag cannot be used as a
delisting indicator in either direction.

### D4. Ticker reuse would fabricate securities

Sixteen eligible symbols carry gaps of 1,850–2,483 days inside their bar
series — BID, APC, ULTI, THOR, AHL, MB, BITA, UN, SEMG, PS. A single symbol's
history is two different companies concatenated. INFO is the clearest: eligible
through 2022-03-24 when IHS Markit was acquired, with bars resuming to
2026-09-21 under a different issuer. **Using such a series would create a
phantom security with a fabricated price path** — a worse contamination than
the survivorship it was meant to remove.

---

## E. Why no corrected return is reported

The seal permits outcome D precisely for this. Running the comparison would
have produced a headline number that is:

- corrected for 2018-2022 and uncorrected for 2016-2017 and 2023-2026;
- missing every large bankruptcy and every large acquisition outside that window;
- contaminated by 57 non-delistings and 16 phantom price series;
- and dependent on a terminal-value assumption for delistings whose *reason*
  the data does not record.

**That number would have been more misleading than the biased baseline it was
meant to correct**, because it would carry the authority of a correction. The
required comparison table in §17 of the directive is therefore deliberately
left unfilled; filling it would be manufacturing attribution.

---

## F. The profitability ceiling, stated at the level the evidence supports

| ceiling | value | status |
|---|---|---|
| **Historical backtest ceiling** | **+58.5889%** decade, Sharpe 0.5107, maxDD −12.9824%, exposure 44.28% | measured, reproduced today |
| **Survivorship-corrected ceiling** | **UNKNOWN** | not reconstructable with available data |
| **Strategy capability** | 698 trades, 44.28% exposure; selection positive, timing the drag | established across H-0013–H-0021 |
| **Future profitability** | **UNKNOWN and not predicted** | clean OOS opens 2026-10-12, 0 sessions |

**The honest statement: the +58.5889% should be treated as an upper estimate
of unknown inflation.** Its direction is known — survivorship inflates — but
its magnitude is not bounded by anything this project currently holds. The
46-ETF proxy (EXP-0031) is suggestive and confounded; it is not a bound.

---

## G. Next step (§19, outcome D)

**The minimum data required**, in order of necessity:

1. A **delisting-complete security master** with listing and delisting dates —
   CRSP, Refinitiv, Norgate or equivalent. The vendor in use does not have one
   and its `inactive` flag is not a substitute.
2. **Delisting reason and terminal value** — acquisition consideration versus
   bankruptcy. Without it, terminal value is an assumption and every corrected
   return inherits it.
3. **Point-in-time symbol mapping** so a reused ticker resolves to two
   securities rather than one.

**Is obtaining it justified?** The direction of the bias is already known and
the size of the affected population is now measured: 273 eligible names and
80,858 symbol-sessions from a *partial* record, against 487,919 gate-passing
sessions in the curated universe. A complete record would plausibly be larger
still. That is not a rounding error, and it sits underneath **every** economic
number this project has produced.

Against that: it is a licensing purchase, not an engineering task, and it
would not create an edge — it would resize the one already measured. It is
recorded as the highest-value data acquisition available, with the decision
left to the owner.

**Until then, no further economic search should treat +58.5889% as a
validated baseline.** That is the operative consequence of this audit.

---

## Production status

Fingerprint `da22011e…c237b` unchanged · RSI 35/60 · ATR 0.035 · 20-bar cap ·
2.5× ATR stop · risk 0.005 · 12 positions · bucket 1 · 3 entries/day · haircut
0.652% · ranker/veto/learned OFF · benchmark unchanged · no leverage · clean
OOS untouched at 0 sessions, opening 2026-10-12 · 22 registrations, 62 declared
configurations, chain intact · thirty-year reads 13 · **no corrected return
computed, nothing promoted, no live order, no performance claim.**
