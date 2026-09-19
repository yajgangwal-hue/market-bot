# Form 4 feasibility gate — Steps 1–7

*2026-09-19. **FORENSIC_NON_PROMOTIONAL.** No economic hypothesis, no
registration, no backtest, no trading rule. No forward return was read
at any point. Production untouched.*

## Branch decision: **C — FORM 4 DATA INSUFFICIENT** *(remediable, not dead)*

The source is technically excellent — better than anything else audited
in this program. It fails the gate on two specific, nameable items, and
both are fixable with bounded work.

---

## 1. Dataset construction

### Acquisition method and request policy, as executed

| | |
|---|---|
| endpoints | `sec.gov/files/company_tickers.json`, `data.sec.gov/submissions/CIK##########.json`, `sec.gov/Archives/edgar/data/{cik}/{acc}/ownership.xml` |
| method | HTTPS GET, read-only, public, **no authentication** |
| User-Agent | the owner-approved contact string, passed via `--contact`, **never hard-coded into the repository** |
| rate | 0.125 s minimum interval = **8 req/s**, held under SEC's stated 10 req/s |
| retries | 3 attempts, linear backoff; 403/404 not retried; every failure recorded |
| provenance | every raw file has a `.meta` twin carrying URL, retrieval timestamp, HTTP status, attempt number |
| separation | `data/form4/raw/` (179 MB, gitignored) is written by the acquirer and only ever **read** by parsers; `data/form4/derived/` (34 MB) holds everything derived |

**Requests issued: 3,094** — 1 ticker map + 171 submissions + 422
shards + 2,500 XML. **Zero retrieval failures.**

### Volume

| | |
|---|---|
| Form 4 / 4-A filings, 2016-01-01 → 2026-09-30 | **130,069** |
| issuers with ≥1 filing | 162 |
| issuers with zero in window | 9 |
| submissions unreadable | 0 |
| amendments (4/A) | 1,281 (**0.98%**) |
| missing `acceptanceDateTime` | **0 (0.00%)** |
| missing `reportDate` | **0 (0.00%)** |

By filing year: 10,988 / 10,817 / 10,948 / 11,233 / 12,055 / 13,118 /
11,814 / 12,267 / 13,521 / 13,142 / 10,166 (2026 partial). **No gaps.**

### A correction to my previous report

Last turn I reported `reportDate` as *"frequently EMPTY — blank in 8 of
12 sampled Form 4s"* and concluded a per-filing XML parse was required
to obtain the transaction date. **That was wrong.** It came from a
WebFetch summarisation that mis-transcribed the table. The raw index
has `reportDate` populated in **130,069 of 130,069**, and the "34-day
lags" I quoted came from the same corrupted reading. The transaction
date is in the index; no XML is needed for timing.

---

## 2. Historical identity — **the first failing item**

| | |
|---|---|
| universe | 230 |
| mapped to a CIK | **171 (74.3%)** |
| unmapped | **59 (25.7%)** |
| mapped issuers with **former names** on record | **98 of 171 (57.3%)** |
| issuers listing **multiple tickers** today | **25** |
| issuers with no ticker | 0 |

**The 59 unmapped are all ETFs** — AGG, QQQ, TLT, the XL\* sector
funds, VTI, and so on. This is not a retrieval failure: **ETFs have no
insiders and cannot file Form 4.** A further 8 mapped names are funds
or LPs (SPY, DIA, MDY, GLD, SLV, DBC, UNG, USO), which is why 9 issuers
show zero filings. So **~29% of the universe is structurally incapable
of carrying this signal, permanently.**

**Identity is not demonstrated for the rest.** Examples from the
issuers' own SEC records:

| ticker | today | formerly |
|---|---|---|
| **ASTS** | AST SpaceMobile | **New Providence Acquisition Corp** — a SPAC |
| APLD | Applied Digital | Applied Blockchain, Inc. |
| ARM | ARM Holdings PLC /UK | Arm Holdings Ltd (pre-IPO) |
| AVGO | Broadcom Inc. | Broadcom Ltd |
| ASML | ASML Holding NV | ASM Lithography Holding NV |

And multi-ticker CIKs are real ambiguity: **BAC's CIK spans 17 tickers**
including preferreds (BML-PG, MER-PK…); GOOG/GOOGL; ASML/ASMLF.

**`company_tickers.json` is a current snapshot.** It cannot say which
ticker a CIK traded under in 2018, and it omits delisted issuers
entirely. Per the brief's instruction not to claim survivorship
completeness unless demonstrated: **it is not demonstrated.**

*In fairness:* the join is CIK→price-series, and a price series follows
the listing, so a SPAC's pre-merger prices and pre-merger Form 4s
describe the same listed entity. The mapping may well be sound. But
"may well be" is not the standard, and the 25 multi-ticker CIKs are an
unresolved ambiguity regardless.

---

## 3. Filing integrity — **passes, and cleanly**

Seeded random sample of **2,500** filings (seed 20260919, drawn
*before* any fetch, so no filing was chosen for looking interesting).
A full parse of all 130,069 is ≈4.5 hours at the rate ceiling and was
deliberately not run.

| | |
|---|---|
| retrieval failures | **0** |
| fully reconstructable | **2,498 (99.92%)** |
| no transaction and no holding | 2 |
| amendments in sample | 20 |
| transactions parsed | **8,150** (mean 3.26 per filing, max 50) |
| with a share count | **8,150 (100.0%)** |
| with a price | 7,586 (**93.1%**) |
| non-derivative / derivative | 6,141 / 2,009 |
| acquired / disposed | 2,808 A / 5,342 D |
| direct / indirect | 6,567 D / 1,583 I |

### Transaction-code census — the decisive table

Counted, **not interpreted**. No economic meaning assigned.

| code | count | share |
|---|---|---|
| **S** | 2,886 | **35.41%** |
| **M** | 2,072 | **25.42%** |
| **A** | 1,414 | **17.35%** |
| **F** | 963 | **11.82%** |
| C | 384 | 4.71% |
| J | 160 | 1.96% |
| G | 151 | 1.85% |
| **P** | **65** | **0.80%** |
| D | 47 | 0.58% |
| I, X, Z | 8 | 0.09% |

**M + A + F + C = 59.3% are routine compensation mechanics** — option
exercises, grants, tax withholding, conversions. These are driven by
vesting calendars, not by anyone's view of the price.

**Code P — the open-market purchase, the only code with a
well-established discretionary-signal interpretation — is 0.80%: 65 of
8,150.** Scaled to the population that is roughly **3,400 P
transactions across a decade and 161 names — about 21 per name, or 340
a year across the whole universe.**

---

## 4. Point-in-time validity — **passes**

`acceptanceDateTime` is present on **100%** of filings, to the second,
in UTC. This is a genuine public-availability timestamp — exactly the
property the news archive lacked and was marked UNVERIFIED for.

### Lag: transaction date → acceptance (calendar days)

| p25 | median | p75 | p90 | p99 | mean | max |
|---|---|---|---|---|---|---|
| 1 | **2** | 4 | 4 | 37 | 5.84 | 6,210 |

**63.4% within 2 calendar days, 93.4% within 4.** Only 1.11% beyond 30
days. The 6,210-day maximum is a single pathological filing.

### Time of day (Eastern, DST-aware)

| | count | share |
|---|---|---|
| pre-market (before 09:30) | 4,042 | 3.1% |
| intraday (09:30–15:45) | 16,668 | 12.8% |
| late session (15:45–16:00) | 1,239 | 1.0% |
| **after close (16:00+)** | **108,120** | **83.1%** |

Against the strategy's 15:45 ET entry window:

| | |
|---|---|
| usable **same** session | 20,710 (**15.9%**) |
| usable **next** session or later | 109,359 (**84.1%**) |

A one-session delay, not a blocker, against a ~14-session hold.

### A second correction, to this session's own first run

My first pass reported 30.7% same-session availability. **That was my
bug.** `acceptanceDateTime` is UTC, so a 21:30 ET filing carries the
*following* calendar day's UTC stamp; comparing it against that day's
15:45 ET decision marked ~19,241 after-close filings as same-session.
Converting to Eastern first gives the correct 15.9%, which reconciles
exactly with the time-of-day census.

---

## 5. Information redundancy — **passes, but the result is weaker than it looks**

46,847 filing-days across 161 symbols; 42,013 with a complete feature
state. Features computed incrementally from bars **up to and including**
that session. **No forward return was read.**

| feature | mean WITH filing | mean WITHOUT | Cohen's *d* |
|---|---|---|---|
| distance to 200d SMA | 0.1211 | 0.0764 | **0.187** |
| RSI(14) | 54.47 | 52.56 | 0.153 |
| drawdown from 252d high | −0.1259 | −0.1466 | 0.137 |
| momentum 21d | 0.0376 | 0.0203 | 0.132 |
| ATR fraction | 0.0316 | 0.0310 | 0.027 |
| **relative volume (×ADV)** | 1.0058 | 1.0168 | **−0.022** |
| is an RSI≤35 candidate | 6.81% | 8.14% | −0.049 |

**No feature separates filing days at |d| ≥ 0.2.** Relative volume —
the one most likely to betray an insider event — is essentially zero.
Filing days are marginally *less* likely to be existing candidates.

Classification against the brief's four options: **(1) broadly
independent of the existing information state.**

### Why this passing result does not license a hypothesis

**Independence from OHLCV is necessary, not sufficient.** A random
number generator is also independent of OHLCV. The population tested is
**59.3% calendar-driven compensation mechanics**, and events scheduled
by a vesting calendar are independent of *everything* — including
future returns. The low Cohen's *d* is therefore consistent with two
very different worlds: genuinely new information, or noise.

The test that would discriminate — **redundancy restricted to code P**
— has not been run, because identifying P events requires parsing all
130,069 filings, not 2,500.

---

## 6. Information incrementality

Stated in the form the brief requires:

> **Form 4 introduces one information dimension not represented by the
> existing feature set: a named insider's discretionary open-market
> purchase or sale of their own company's stock, with a
> public-availability timestamp accurate to the second.** Nothing in
> RSI, ATR, momentum, drawdown, price distance, volume, ADV, bucket or
> regime can reconstruct who traded, in which direction, in what size,
> with their own money.

> **What is substantially redundant or uninformative:** 59.3% of
> transactions are grants, option exercises, tax withholding and
> conversions, scheduled by vesting calendars. And the large majority
> of the 35.41% coded S are sales, of which an unmeasured portion are
> automatic 10b5-1 plan sales or the sale leg of an
> exercise-and-sell — liquidity events, not views. **The 10b5-1 flag
> exists in the filing footnotes and was not parsed.**

> **What is unavailable at the decision timestamp:** nothing material.
> 84.1% of filings are usable only from the next session, which is a
> lag, not an absence.

> **How much usable data remains:** ~3,400 code-P transactions over the
> decade across 161 names (~21 per name), from a universe of which ~29%
> can never contribute at all.

---

## 7. Branch decision: **C — FORM 4 DATA INSUFFICIENT**

Measured against the brief's own criteria for **A**, which requires all
six to pass:

| criterion | verdict |
|---|---|
| historical identity mapping reliable | **FAIL — not demonstrated.** 57.3% former names, 25 multi-ticker CIKs, current-snapshot mapping, delisted issuers absent |
| coverage sufficient | partial — 71% of universe; ~29% structurally excluded as ETFs |
| timestamps valid | **PASS** — 100% present, to the second |
| transaction reconstruction | **PASS** — 99.92% fully reconstructable |
| latency compatible | **PASS** — median 2 days; next-session usable |
| information genuinely distinct | **UNPROVEN for the subset that matters.** Aggregate independence holds, but the aggregate is dominated by calendar-driven events; code-P redundancy untested |

Two of six fail. **A is unavailable by definition.** **B** does not fit
either — the data is not shown to be redundant; it is shown to be
independent in a way that does not discriminate signal from noise.

**This is a remediable C, not a dead source.** The technical quality is
the best of any information source audited in this program: zero
retrieval failures, zero missing timestamps, 99.92% reconstructable,
survivorship-complete filings, and a true availability timestamp.

### Exact missing evidence

1. **Point-in-time identity mapping.** Demonstrate that each CIK's
   filings can be attached to the correct security at the filing's
   availability time, resolving the 25 multi-ticker CIKs and the
   business-identity changes (the ASTS SPAC case is the sharp one). A
   negative result here closes the branch outright.
2. **Code-P redundancy.** Parse all 130,069 filings (~4.5 h at 8 req/s),
   isolate the ~3,400 discretionary open-market purchases, and re-run
   the redundancy test on **that subset alone**. Also parse the 10b5-1
   footnote flag so plan-driven sales can be separated from
   discretionary ones.
3. **Power check.** With ~3,400 events, establish in advance what
   effect size is detectable, and whether ~21 events per name supports
   anything beyond a pooled test.

Each can close the branch on its own, and none requires a registration.
**I am not proposing an economic hypothesis, because the brief's
criteria for A are not met.**

---

## 8. If A — not reached

No economic hypothesis is proposed. No registration design is offered.

---

## 9. Governance

| check | result |
|---|---|
| frozen fingerprint | `da22011e…c237b` — **unchanged** |
| production source | **unchanged**; `src/` working tree clean |
| `rsi_entry` | **35.0** |
| bucket cap / max positions | 1 / 12 |
| `risk_per_trade` | 0.005 |
| learned ranker / veto | `False` / `False` |
| exit haircut / drawdown ceiling | 0.652% / 14.2806% — unchanged |
| clean OOS | **untouched** |
| registrations | **9, chain intact — none created** |
| promotion candidates | **none** |
| ledger | 35 experiments, 104 configurations — unchanged |
| thirty-year reads | **13** |
| decade reads | 94 — unchanged by this work |
| trading results from Form 4 | **none generated** |
| tests | **1,201 passing** |
| raw vs derived | separate trees; raw gitignored, read-only to parsers |
| reproducibility | seed 20260919, provenance and retrieval timestamp on every record |

### Credential hygiene

The exposed Alpaca **paper** secret is treated as compromised.
`scripts/windows/setup-keys.ps1` exists, but rotation requires new keys
generated in the Alpaca dashboard, which I cannot do and did not
attempt — no live-brokerage action was taken. **Rotation requested,
pending owner action.** Key presence was verified by name only; no
value was read, printed or logged anywhere in this work.

## Artefacts

- `scripts/form4_acquire.py` (stages: map / submit / index)
- `scripts/form4_feasibility.py` (steps 4, 6, 7)
- `scripts/form4_sample_xml.py` (step 3, seeded sample)
- **`docs/phase5/form4/`** — the durable evidence, committed:
  `ticker_cik.json`, `form4_index.json`, `xml_sample_census.json`,
  `xml_sample_meta.json`, `submission_failures.json`
- `data/form4/derived/form4_rows.jsonl` — 35 MB index of all 130,069
  filings; gitignored under the repo's standing `/data/*` rule,
  regenerable by `form4_acquire.py index`
- `docs/phase5/form4-feasibility.json`
- `data/form4/raw/` — 179 MB, gitignored, regenerable, provenance retained
