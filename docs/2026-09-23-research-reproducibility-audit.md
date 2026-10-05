# Research data reproducibility and Clean OOS integrity audit

*2026-09-23. Non-economic research-infrastructure audit. No backtest, no P&L,
no economic result, no Clean OOS outcome, no dataset-use row, no registration.
The price files were only read; they were not modified, normalised or
rewritten. `src/` untouched.*

---

## K. Final classification: **B — PARTIALLY REPRODUCIBLE**

The decade dataset behind the frozen baseline **is complete and now has a
recorded content identity** — SHA-256
`935fed79de9803f1da2a380c6f3f76ab525b27c5d14830bbea4744a7bf73d4a7` over 230 files.
It cannot be *cryptographically* tied to the runs made before today, because
no checksum was ever recorded until now. It is still **not preserved**: its
only copy is in a temporary session scratchpad. The **thirty-year dataset is
unrecoverable**, so every thirty-year figure in the ledgers is non-reproducible
from retained raw data.

**Clean OOS is intact.** No holdout session has occurred, and nothing has
read, backfilled or recorded one. Three isolation hazards were found; none has
contaminated anything (§E).

---

## A. Governance

| item | finding |
|---|---|
| audit type | non-economic research-infrastructure audit |
| registration | **none required, none created.** Nothing here computes or compares an economic outcome |
| registration ledger | 24 rows, chain intact; latest **H-0025** (2026-09-23, gain-to-loss forensics) |
| corrections to the brief's "known state" | **H-0024** is the registered *intraday capability-gap* audit (outcome B, `economic_comparisons_spent_here: 0`). The *fidelity* audit is a separate, **unregistered** document whose header reads "identifier: none assigned". The latest *registration* is H-0025; the knowledge-base value assessment and this audit are unregistered. H-0022 remains unregistered |
| frozen fingerprint | `da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b` — unchanged |
| baseline ledger reference | `baseline_metrics` in `docs/phase5-research.jsonl` — P5-0001 (2026-09-16) and 27 later rows carry the same values |
| Clean OOS | **0 sessions**; chain intact; embargo 8 of 20 elapsed on 2026-09-23 |

### The frozen baseline, verified against the ledger only (no rerun)

| metric | brief | ledger / governed document | match |
|---|---|---|---|
| cumulative return | +58.5889% | `total_return` 0.585889 | ✓ |
| CAGR | 4.4248% | `cagr` 0.044248 | ✓ |
| volatility | 9.3372% | `annualised_volatility` 0.093372 | ✓ |
| Sharpe | 0.5107 | `sharpe` 0.510651 (zero risk-free rate, `evaluation._ratio`) | ✓ |
| Calmar | 0.3408 | `calmar` 0.340829 | ✓ |
| maximum drawdown | −12.98% | `max_drawdown` −0.129824 | ✓ |
| exposure | 44.28% | `exposure` 0.442794 | ✓ |
| trades | 698 | `trades` 698 | ✓ |
| starting capital | $100,000 | `docs/benchmark-units.md` | ✓ |
| idle cash return | 0% | `docs/benchmark-units.md` | ✓ |
| window | 2016-01-04 … 2026-09-04 | `docs/benchmark-units.md`; the dataset's own first and last timestamps | ✓ |
| dataset | contaminated decade | ledger `dataset`: "decade (contaminated)" | ✓ |

---

## B. Decade dataset

### Availability and completeness

| question | finding |
|---|---|
| do the files exist? | **yes** |
| location | `C:/Users/yajga/AppData/Local/Temp/claude/C--market-bot/ba9a513c-7a3b-43dd-bc7f-dfe8be46d8d9/scratchpad/deep` — a session scratchpad: temporary, not version-controlled |
| copies on the machine | **one.** A recursive search of the user profile and the repository for `SPY.csv` found no other copy. The other price stores found are `scratchpad/snapshots` (H-0014's intraday snapshots) and `C:/market-bot/data` (the live bot's cache: 241 files from 2024-07-15) |
| all 230 present? | **yes: 230 CSV files, no other files, none missing** — the registry's universe is "2016-2026, 230 names" (`research.DATASETS`) |
| sizes | 49,431,888 bytes in total; 52,693 – 238,056 per file |
| row counts | 582,324 bars; 610 – 2,684 per file (33 distinct counts). SPY has **2,684**, the figure `benchmark-units.md` states |
| date ranges | 198 files begin 2016-01-04; the rest begin at later listings. **All 230 end 2026-09-04** |
| schema | **one**: `timestamp,open,high,low,close,volume` in all 230 files (schema SHA-256 recorded in the manifest) |
| timestamps | all parse, all strictly increasing, no duplicate session. Convention: midnight US/Eastern in UTC — `T05:00:00+00:00` in standard time (195,445 bars), `T04:00:00+00:00` in daylight time (386,879) |
| content | price and volume only |
| adjustment | **split-adjusted, not dividend-adjusted.** AAPL's first close is 26.34, which is the unadjusted $105.35 divided by the 2020 4:1 split; NVDA's 0.8092 reflects both splits; SPY's 201.0192 is the unadjusted close |
| line endings | CRLF in all 230 |
| modified since the governed experiments? | **no.** All 230 were written in one batch, 2026-09-08 23:43:15–23:43:18 UTC (the directory was created 23:42:21 UTC), and none has a later modification time. The baseline was first recorded 2026-09-16 |

### Data-quality anomalies — found, not repaired

Across 582,324 bars: no non-positive price and no high/low ordering violation.
Four single-bar spikes that are almost certainly bad vendor prints:

| file | date | print | close |
|---|---|---|---|
| NVDA | 2024-06-10 | high 195.95 | 121.79 |
| MRK | 2021-06-11 | low 15.32 | 76.27 |
| SPY | 2026-02-02 | low 69.005 | 695.41 |
| VZ | 2026-01-08 | low 10.5999 | 40.57 |

Also 1,065 zero-volume bars. The emulator fires stops on `bar.low`, so a bad
low print can trigger a simulated stop. **Whether any governed result was
affected is not determined here.** Answering it means re-examining trades,
which this audit prohibits; it is recorded as an open hazard.

### Content-addressable identity

| field | value |
|---|---|
| dataset ID | `decade-2016-2026-split-adjusted-230` |
| **dataset SHA-256** | **`935fed79de9803f1da2a380c6f3f76ab525b27c5d14830bbea4744a7bf73d4a7`** |
| hash rule | SHA-256 of the UTF-8 text with one line per file, `<file>\t<size>\t<file_sha256>\n`, sorted by file name. It covers file identity only |
| manifest | `docs/datasets/decade-2016-2026.manifest.json` — file, size, SHA-256, rows, first and last timestamp, schema hash per file, plus the provenance above |
| checksum list | `docs/datasets/decade-2016-2026.sha256` — standard `sha256sum` format |
| independent check | `sha256sum -c` run inside the data directory: **all 230 OK** |

To re-verify any copy later:

```bash
sha256sum -c /path/to/market-bot/docs/datasets/decade-2016-2026.sha256
```

Run it from inside the directory that holds the 230 CSV files.

Per-file hashes: Appendix 1.

### Provenance — can the hash be proven to represent the historical baseline?

| evidence | supports the identity? |
|---|---|
| files written 2026-09-08, unmodified since; every governed decade read in `dataset-uses.jsonl` is later (first 2026-09-16 02:24 UTC) | **yes**, by filesystem metadata — not cryptographic |
| the only copy on the machine, and the glob that research scripts use matches exactly it | **yes, today.** Whether another copy existed and was matched earlier cannot be established |
| 230 names; 2,684 SPY bars; window 2016-01-04 … 2026-09-04; SPY 201.0192 → 770.19 (3.8314×, as documented) | **yes** — documented anchors all match |
| split-adjusted basis matches `benchmark-units.md` (`adjustment="split"`) | **yes** |
| the equivalence gate reproduced +58.5889000000% / 698 on these files on 2026-09-23 (the H-0025 run; a verification run at 23:13 UTC) | **functional evidence only** — data differences that alter no trade would pass the same gate |
| an archived checksum or manifest from before today | **none exists** |
| an acquisition script or log | **not in the repository.** `buckets.py`, the first committed user (EXP-0001, committed 22 minutes after the files were written), reads `Path(__file__).with_name("deep")` — the data sat beside scripts run from the scratchpad |
| source | **inferred, not proven**: Alpaca with `adjustment="split"` (`benchmark-units.md`; the 2026-09-08 thirty-year report, "2016, because that is where Alpaca's data starts") |

**Classification: B — DATASET IDENTIFIABLE BUT HISTORICAL IDENTITY NOT FULLY
PROVEN.** The evidence is strong and consistent, but none of it is a checksum
recorded at the time of the historical runs, so A cannot be claimed. A
re-download would not settle it: vendors restate adjusted series.

---

## C. Thirty-year dataset

| question | finding |
|---|---|
| does the raw dataset exist? | **no.** No `long/` directory under any Claude scratchpad; no `SPY.csv` beginning in 1996 anywhere under the user profile or the repository |
| what remains | derived results only: **31 experiments**, **24 phase-5 rows**, 5 registrations that declare thirty-year use (H-0001, H-0002, H-0003, H-0004, H-0007), and 13 recorded reads, all on 2026-09-16 |
| exact universe | recorded as **"1996-2026, 229 names"** (`research.DATASETS`), and each of the 13 reads recorded 229 symbols; the 2026-09-08 report says "today's 230 names". **Which name is absent is not recorded** |
| exact date range | from 1996-01-01 (`thirty_year_test.py`: `FROM = date(1996, 1, 1)`) to the acquisition date, 2026-09-08 by the report — end date not recorded |
| exact source | Yahoo, "with a browser header" (2026-09-08 report). **That acquisition code is not in the repository.** `data.fetch_yahoo_bars` is a generic yfinance fetcher (`auto_adjust=False`), not proven to be the one used |
| exact schema | not recorded; presumably the same CSV layout — UNVERIFIED |
| adjustment basis | UNVERIFIED |
| can it be reconstructed? | approximately, from the same vendor |
| would a reconstruction be the same dataset? | **cannot be established**: no checksum, an unknown missing name, an unknown end date, an unknown adjustment, and vendor restatement |

**Status: the historical thirty-year results are non-reproducible from
currently retained raw data.** Their records stand unedited and nothing was
deleted. Requirements for a reacquisition, **not performed**, are in §J.

---

## D. Dataset dependencies

**74 scripts depend on a scratchpad price store**: 45 directly, 29 more
through imports (`forensics_regime` and other loader modules). The prior
assessment's "18+" undercounted. `src/` contains **no** temp-directory or
scratchpad lookup, so **production does not depend on any of this.**

| hazard | scripts (direct) | effect |
|---|---:|---|
| glob over the OS temp directory (`Temp/claude/**/scratchpad`) | 29 | finds whatever a session left behind |
| `…recursive=True)[0]` — first match wins | 17 | with two copies, which one is read is not controlled |
| accept any scratchpad whose `deep/` holds **≥ 200** CSVs | 10 | would run silently on a dataset missing up to 30 files |
| `Path(__file__).with_name("deep")` — data beside the script | 8 | **cannot run as committed**: `scripts/deep` does not exist |
| thirty-year `long/` store | 13 | the thirty-year paths **cannot run** |
| load errors skipped silently (`except …: continue`) | 18 | a corrupt or short file drops a symbol without error |
| a 400-bar window monkeypatched onto the emulator's signal (`portfolio.mean_reversion_signal`), in scripts rather than `src/` | 21, plus every importer of `forensics_regime` — including all runners H-0009 … H-0025 | see below |

**The 400-bar patch.** `forensics_regime.py` replaces the emulator's signal
function with one that sees only the last 400 bars. It is not in `src/` and
not documented as part of the baseline, **so the frozen baseline has only ever
been produced with it active.** Its effect on results is **analytically
negligible**, not proven empirically:

- RSI(14) and ATR(14) use Wilder smoothing, whose starting value's influence
  decays by 13/14 per bar — roughly 4×10⁻¹³ after the ~386 bars the window
  leaves;
- the 200-day average, conviction (40 bars) and dollar volume (20 bars) look
  back less than 400.

It is a hidden assumption, not a defect.

**Reproducible today:** 53 scripts, only while the single scratchpad copy
exists; 12 in decade mode only; 8 not at all as committed; 1 (thirty-year
only) not at all. Full table: Appendix 2.

---

## E. Clean OOS integrity

### The boundary

| item | finding | source |
|---|---|---|
| research freeze | 2026-09-11 (EXP-0017) | `purge.freeze_date` |
| embargo | 20 sessions (`max_holding_bars`) | `purge.embargo_sessions` |
| embargo progress | 8 of 20 on 2026-09-23 | the recorder's own output |
| start | **2026-10-12, projected**; resolved at run time by `forward.first_clean_session()` | Phase 4 protocol §1 |
| end | **none defined.** Checkpoints at 1, 20, 60 and 120 sessions; the first performance report is at 60 | Phase 4 protocol §6 |
| currently embargoed? | **yes** | |

### Contamination checks

| check | result |
|---|---|
| has any strategy or research code read a Clean OOS session? | **no — none exists yet.** All 230 research files end 2026-09-04, before the freeze |
| has any feature-generation process consumed one? | **no, not yet.** The learning loop retrained on live outcomes on 2026-09-14, 09-15, 09-21 and 09-22 (embargo period); the model is observe-only and `LEARNED_RANKING_ENABLED = False` |
| has any backfill touched the holdout? | **no.** `data/forward-evaluation.jsonl` does not exist; the recorder refuses sessions before eligibility and never backfills |
| does any experiment artefact contain Clean OOS outcomes? | **no.** No holdout outcome exists to carry. A search of the date-like fields (`date`, `day`, `session`, `cross_date`, `timestamp`, `when`) in `docs/phase5/*.json` found no date after 2026-09-13 |
| has any live or paper process written into a research dataset? | **no.** The research files are unmodified since 2026-09-08; the live bot writes only under `data/` |
| does the knowledge base make Clean OOS performance claims? | **no.** It states 0 sessions and no performance figure |

### Isolation hazards — none has contaminated anything

1. **Two definitions of "clean".** `research.DATASETS["forward"]` declares
   `"window": "paper account from 2026-09-11", "status": "clean"`. The Phase 4
   protocol, which the recorder enforces, admits nothing before the embargo
   ends on the projected 2026-10-12. Embargo-period paper results are **not**
   Clean OOS; the registry entry says they are.
2. **An ungoverned forward read.** `scripts/benchmark.py` measures the paper
   account against SPY from `FORWARD_START` = 2026-09-11, from the audit log,
   outside the recorder and its checkpoints. Run after 2026-10-12, it is the
   early look §6 forbids.
3. **Models trained on the holdout.** The learning loop will keep training on
   live outcomes after 2026-10-12. Any such model has seen holdout data and
   must never be evaluated as a pre-holdout model.
4. **The risk-free convention for holdout reports is unsettled.** The
   fingerprint declares `risk_free 0.0230`; no code consumes it; research
   Sharpe uses zero; the checkpoint script computes no Sharpe. It must be
   settled before checkpoint C.

**Status: Clean OOS integrity is NOT compromised.** D is not warranted.

---

## F. Paper / live separation

| property | finding |
|---|---|
| where | `data/autotrade-audit.jsonl` — gitignored (`/data/*`), outside the research stores |
| volume | 2,571 rows, 2026-09-01 … 2026-09-23; 24 entries |
| identification | every row carries `at` (timestamp) and `dry_run` (all `False`: orders reached the paper broker); 6 rows are flagged `backfilled`; the synthetic test rows of REM-0008 are annotated |
| readers | `autotrade.py` and `cli.py` (operations); `record_clean_session.py` (the recorder, by design, after eligibility); `haircut_observations.py` (Phase 4 §7 — reported beside the frozen haircut, never replacing it); `annotate_audit_contamination.py` (REM-0008); `exit_at_peak.py` (an owner-directed operational tool); **`benchmark.py`** (hazard 2 above) |
| enters historical datasets? | **no evidence it ever has.** The research price stores are separate files, untouched since 2026-09-08. The barrier is convention plus a type check (`forward.reject_forward_data` refuses `CleanObservation` objects); nothing mechanically stops a script from reading the audit log |
| evidence status | operational only — **not evidence, not validation** |

---

## G. Benchmark provenance

| | historical research | Clean OOS |
|---|---|---|
| series | SPY | SPY |
| basis | **price only** — dividends excluded on both sides (the strategy data is split-adjusted only) | **total return**, against the account's actual return |
| window | 2016-01-04 … 2026-09-04 (10.6639 years) | from the first clean session |
| source | Alpaca, `adjustment="split"` (`benchmark-units.md`); the series is `deep/SPY.csv` — 2,684 bars, 201.0192 → 770.19 | Alpaca, `fetch_alpaca_equity_bars(["SPY"], adjustment="all")`, with the split-only series stored alongside (`record_clean_session.py`; REM-0003) |
| declared in the fingerprint | `basis_pre_2016: price_vs_price` | `basis_post_2016: total_vs_total` |
| risk-free | research Sharpe: **0** | declared 0.0230, **not consumed** — unsettled |
| comparable to the strategy's dataset? | **yes on basis** (price vs price); not like-for-like on cash (0%), costs, exposure or survivorship | **yes on basis** (total vs total) |

No SPY performance figure was computed here.

---

## H. Knowledge-base integrity

`scripts/validate_knowledge_base.py`: **PASS** after this audit's edits.

**What was *corrected in the vault* by the value assessment:** the Benchmark
note (it had conflated total and price return), and new entries AMB-4 … AMB-7:
the benchmark-bias sentence, "exposure untested", the Calmar figure, and the
constraint-stage definitions.

**What that assessment *identified* but recorded only in its report:** the
exit-family undercount (54 against ~77), the uncited re-tests (H-0001, H-0010),
H-0017's description of H-0011 (already CONF-3), and H-0021's fill-price
description (already CONF-5).

**This audit's changes to the vault:**

1. The VALIDATED EVIDENCE banner, in the builder, and `Authority Levels` now
   state that every instance to date is in-sample on contaminated data and
   never future performance. Before this, the label could be read as
   validated future performance.
2. `Frozen Baseline` and `Governance Ledgers` carry the dataset identity and
   the thirty-year status.
3. `Clean OOS` carries its duration, the checkpoints and the isolation
   hazards.
4. `Benchmark` records the unsettled risk-free rate.
5. `Research Gaps` gains the missing closed branches, an "untested and not
   open" row, and the holdout rule.
6. `Conflicts and Ambiguities` gains CONF-10 (two definitions of clean) and
   AMB-8 (two ETF controls).

**Checks.**

- The vault does not contradict the ledgers: the validator's authority
  mapping against each ledger passes.
- It separates contaminated evidence from Clean OOS.
- It files H-0022 as unregistered, at INCONCLUSIVE.
- It files H-0024 as a capability audit, at INCONCLUSIVE, which is consistent
  with its registration's zero economic comparisons.
- After correction 1, it does not present contaminated evidence as validated
  future performance.

**Remaining ambiguities:** the open CONF items, AMB-1 … AMB-8, and the two
recorded here:

- **Two ETF controls.** `research.DATASETS["etf_subset"]` is "46 broad ETFs";
  H-0019 and H-0020 built a 67-ETF control by keyword match and recorded the
  reads under dataset `decade`. Both are subsets of the same 230 files.
- **The bad-print hazard** in §B.

---

## I. Research-gap inventory

Checked against the brief's list. The vault's `Research Gaps` now reflects it,
with one correction.

| branch | status | evidence |
|---|---|---|
| RSI threshold direction | closed | H-0009, EXP-0006, EXP-0023 |
| sizing | closed | EXP-0046, EXP-0021, EXP-0001, EXP-0045 → EXP-0047 |
| capacity | closed | H-0015, H-0016, H-0020, EXP-0025, bucket and regime forensics |
| regime filters | closed | EXP-0009, EXP-0042 … 0047, H-0007, P5-0022 |
| news, as currently available | closed | EXP-0041, P5-0011 … 0013, H-0022 (unregistered) |
| Form 4 | closed | the Form 4 study; research-gap inventory row 5 |
| copy trading | closed | "H-COPY is not justified" (feasibility, unregistered) |
| NBBO / queue branch | closed | H-0017, H-0018 |
| the existing intraday economic hypothesis | closed | H-0014 (via H-0024), H-0011, EXP-0007 |
| exposure levers already tested | closed | EXP-0009, EXP-0028, H-0006, EXP-0046 |
| **volatility-triggered exits** | **correction: never adjudicated — never registered or run as a rule.** Not open either: H-0025's evidence points against the mechanism, and the exit family carries ~77 configurations | |
| volatility-based exposure | closed | EXP-0009 (volatility targeting), H-0007 (entry abstention) |
| survivorship-complete universe | data-limited | H-0023 (D) |
| full news text with point-in-time availability | data-limited | H-0022 |
| options information | data-limited | inventory row 2 |
| short interest | data-limited | inventory row 3 |
| point-in-time fundamentals | data-limited | inventory row 4 |
| true out-of-sample profitability; persistence of the current signal; live exit economics; validation of any new strategy | holdout-limited | Clean OOS; Phase 4 §7 |

Nothing speculative was added.

---

## J. Future experiment admission standard

### The minimum before any future economic test may run

| area | requirement | exists today? |
|---|---|---|
| **dataset identity** | dataset ID; dataset SHA-256; a per-file manifest; source; acquisition date; universe; date range; adjustment basis | **partial** — the decade manifest now exists; registrations and dataset-use rows carry only a free-text dataset name |
| | the runner verifies every file against the manifest **before computing** and refuses on any mismatch or a count ≠ manifest | **no** — runners glob a temp directory and accept ≥ 200 files |
| | the data sits in a durable location, not a session scratchpad | **no** |
| **information boundary** | the point-in-time cutoff per SPEC-0001; feature availability timestamps; no read of any session after the research freeze (checkable from the manifest's last timestamps) | SPEC-0001 yes; the freeze-date check is not automated |
| **benchmark** | the exact SPY series and its basis (price vs total return) named; the matching window; the risk-free convention named | basis documented; risk-free unsettled |
| **experiment identity** | registration, seal, code commit, configuration, the equivalence gate at +58.5889% / 698 | **yes** |
| **holdout protection** | the Clean OOS boundary and embargo; no holdout read before registration; no paper/live operational record used as research data; forward performance only through Phase 4 checkpoints | boundary enforced by the recorder; `research.DATASETS["forward"]` and `benchmark.py` contradict it (§E) |

### The smallest governance addition

**One rule, added to the registration procedure:** *a registration's
`datasets` entry must name a dataset ID and SHA-256 from `docs/datasets/`, and
the runner must verify every file against that manifest before computing
anything.*

It needs no schema change, because `datasets` is already free text. The
verification is a future, separately approved change to the runners' shared
loader. It is **not implemented here**.

### If the thirty-year dataset is ever reacquired — documented, not performed

| requirement | value |
|---|---|
| universe | the 229 names of the recorded reads — the absent name must first be identified |
| range | 1996-01-01 onward, fixed end date recorded |
| source | Yahoo, with the adjustment basis chosen and recorded |
| schema | the decade schema |
| manifest | per-file SHA-256 and a dataset hash at acquisition |
| status | a **new** dataset, never presented as the original: the historical thirty-year results remain non-reproducible |

---

## Single next action

**Preserve the exact decade dataset.** Copy the 230 files byte-for-byte out of
the temporary scratchpad to a durable location, and verify the copy against
`docs/datasets/decade-2016-2026.sha256`. Until that is done, the frozen
baseline's only source can disappear with a temp-directory clean-up.

---

## Final statement

**No.** The research program can now **identify** the exact decade dataset
behind the frozen baseline: SHA-256
`935fed79de9803f1da2a380c6f3f76ab525b27c5d14830bbea4744a7bf73d4a7`, a
provenance class-B link to the historical runs. But its only copy is in a
temporary directory, and the thirty-year dataset behind 31 experiments, 24
phase-5 rows and 5 registrations is **gone**. **Clean OOS is genuinely
untouched**: 0 sessions, none read, three isolation hazards recorded and none
realised.

**The single smallest corrective action required before any new economic
experiment is allowed to run:** preserve a byte-identical copy of the 230-file
decade dataset outside the temporary scratchpad, verified against
`docs/datasets/decade-2016-2026.sha256`.

---

*Production changes: **NONE**. `src/`, strategy, simulator, risk, sizing,
execution, haircut, universe, benchmark, Clean OOS and every frozen result are
unchanged. No H-0009 … H-0024 rerun; no historical report replaced.*

---

## Appendix 1 — per-file identity of the decade dataset

Identical to `docs/datasets/decade-2016-2026.manifest.json`, which is the machine-readable record.

| file | bytes | rows | first | last | SHA-256 |
|---|---:|---:|---|---|---|
| AAOI.csv | 218260 | 2684 | 2016-01-04 | 2026-09-04 | `6171cc36a1021a803059fcf4800aeec4f345884f4506739dafc43da6b2ac7064` |
| AAPL.csv | 232793 | 2684 | 2016-01-04 | 2026-09-04 | `401948493ea2d3723c43a6c33f225736f2663f9b7778411c619aacf032e6a319` |
| ABBV.csv | 229366 | 2684 | 2016-01-04 | 2026-09-04 | `9d84bc93e58939192abf42ae552b101d5991d8105b423a0bb4e4fa2490ad061f` |
| ABT.csv | 228747 | 2684 | 2016-01-04 | 2026-09-04 | `9e3981af5d1f46341abaa15260edc034baedf8a54c33ca5b9bd02cfff5bf7cbe` |
| ACN.csv | 233494 | 2684 | 2016-01-04 | 2026-09-04 | `8149e0c162ec8bed711fe1977c50659ed8baaac7a5c5887b729bdd8177a40330` |
| ADBE.csv | 232944 | 2684 | 2016-01-04 | 2026-09-04 | `4b275bc266990536db46c7c93f9682275bd117ee60095b986323c02d59432580` |
| ADI.csv | 230371 | 2684 | 2016-01-04 | 2026-09-04 | `e3774fe2eb9ffeb99df602bd0ec75d67b6ec710a76c485480529d00198252d7d` |
| AGG.csv | 230540 | 2684 | 2016-01-04 | 2026-09-04 | `f81a9e18f4330abcd3b2500571c021435f9cc2fb961da009291d389dfc4492a9` |
| ALAB.csv | 52693 | 618 | 2024-03-20 | 2026-09-04 | `9e18cb8f37cb4e53ea1348ebaefeae8004d080a10180ea6c5739f549fd121f48` |
| AMAT.csv | 229083 | 2684 | 2016-01-04 | 2026-09-04 | `dbab72bc302a1bbf4e1cb83a0f7b8a9e92223d6fe396cfb173a3e772bb5d9e7e` |
| AMD.csv | 228662 | 2684 | 2016-01-04 | 2026-09-04 | `97e9350750853840b3c75332563263fc47ba0032f8cda3f3a258a7d115fd9f8c` |
| AMGN.csv | 233564 | 2684 | 2016-01-04 | 2026-09-04 | `8952d609cc260abfb9c1cad58e19de8c841d1d112a284b422ec226395b727891` |
| AMZN.csv | 232215 | 2684 | 2016-01-04 | 2026-09-04 | `d229339986855a05ee246679db7b1d3337554575cf1660d14a035ba61c1bf891` |
| ANET.csv | 223960 | 2684 | 2016-01-04 | 2026-09-04 | `d4ea068550bf98a128a04c264e946eede5c59d6f15e5136d3150b80a5a52bd7b` |
| APH.csv | 222701 | 2684 | 2016-01-04 | 2026-09-04 | `337a0f02f5bee13eecce8a262c2db8790df09b9932346a1b8caafd2dc5570945` |
| APLD.csv | 88767 | 1103 | 2022-04-13 | 2026-09-04 | `ee4bcbd06db4bd8bf3eb402199beaf13c8b39bbbba33f4ab2d851dd134483232` |
| APP.csv | 114452 | 1355 | 2021-04-15 | 2026-09-04 | `3e73d654dec0b6b08c20889de5d5ccc3dcff463398c970cd2a24bb00fadf9664` |
| ARM.csv | 64703 | 747 | 2023-09-14 | 2026-09-04 | `d6b955c97ca8778ad32910e4f0367c754f8e39df20818022c5b1a77550eb2c8e` |
| ASML.csv | 232628 | 2684 | 2016-01-04 | 2026-09-04 | `794c84f1c04756c439ed4e0760b45d8314adfe50e2bfdb38e99a5bb63544e430` |
| ASTS.csv | 138919 | 1719 | 2019-11-01 | 2026-09-04 | `edfc43369147c36035ef6292dde679af7dc693c6575be4713e5e1086eeabaf60` |
| AVGO.csv | 228245 | 2684 | 2016-01-04 | 2026-09-04 | `44897a0d7a3d7177a8d99eb88567792d710512fe9afc33f257704aa75cb89452` |
| AXP.csv | 230644 | 2684 | 2016-01-04 | 2026-09-04 | `fbcf4f08a5ed4f10ff37ab262a408ba87033967d6eff6e372816642dc35afedc` |
| AXTI.csv | 211092 | 2684 | 2016-01-04 | 2026-09-04 | `c2ad3cc76ef66ff8c5d013069572ce6a235e4affe3b5edf970b683922af39e97` |
| AZO.csv | 238056 | 2684 | 2016-01-04 | 2026-09-04 | `d2c0d6375b75bc41eb3b85e0b1047abe608325605f83ab2a784fd342ef1a5a5c` |
| BA.csv | 234179 | 2684 | 2016-01-04 | 2026-09-04 | `101e374a5f49cb3c75c9f44f5c39f88f3cd6555d662ff0beeaf7f4d05de15eaf` |
| BABA.csv | 232447 | 2684 | 2016-01-04 | 2026-09-04 | `54b7b51d1a14796425e6c1263043f1a6d67f4a23f134f30a8eb1e28085cd61ee` |
| BAC.csv | 225794 | 2684 | 2016-01-04 | 2026-09-04 | `15fc1cb9783b43ec823422f821ad4847dede1c4fea6775d98796bf49e53ffff7` |
| BE.csv | 169228 | 2040 | 2018-07-25 | 2026-09-04 | `a9d5bc6149f54e03376748bc9aa87a7a062bf964ac88bfabb653c6d631c0d97b` |
| BKNG.csv | 227477 | 2684 | 2016-01-04 | 2026-09-04 | `7a3252f9999ac35d74a297cbe8559acef614d8fff3784b8f53387e263e202924` |
| BLK.csv | 232555 | 2684 | 2016-01-04 | 2026-09-04 | `4798e448e0f6f62fc03f4f6589ee00c5c6f3b951a09f80dfa488295424a5f3e0` |
| BND.csv | 222932 | 2684 | 2016-01-04 | 2026-09-04 | `fcbe7059564b9b8951c58a812ec1276cbd282204826a3cd18e5557c31fed0f93` |
| BRK-B.csv | 233622 | 2684 | 2016-01-04 | 2026-09-04 | `2586c171dd845aff3e1888129da6dca7d201dfe37c4369da5b1e925ad0e24045` |
| BSX.csv | 224216 | 2684 | 2016-01-04 | 2026-09-04 | `0913e52ba1dc60d31a19938d3dfb091128a32c62e27cf5a60ff51d8e92910ccb` |
| BX.csv | 227014 | 2684 | 2016-01-04 | 2026-09-04 | `f307dd716ab026d6e16f4e9f20e0a640e6f55654046d9f276de9b02d7b3ec478` |
| C.csv | 226182 | 2684 | 2016-01-04 | 2026-09-04 | `f99a9f2af0feed4cc540baaa13a152043f8bd98ade76470f0e62e22d0a7539d9` |
| CAT.csv | 232255 | 2684 | 2016-01-04 | 2026-09-04 | `940e8491b720186de85aca65b4bfe39eddc005089df85b1508878ac981aec908` |
| CDNS.csv | 228852 | 2684 | 2016-01-04 | 2026-09-04 | `46d8aaa1eab48366784904ea63b3d4314f4d5cb51b4875b11856d886ea0b30b7` |
| CEG.csv | 98746 | 1152 | 2022-02-02 | 2026-09-04 | `c9d78f568bdaa85c6c81fc26fa6ac085e8357c9f2beb43db91241beceb1ec0f2` |
| CIEN.csv | 223651 | 2684 | 2016-01-04 | 2026-09-04 | `2cb9238937f9f175c973958e4642a9f450e03aa0104a55130ade09b3f3f0d77d` |
| CLS.csv | 219044 | 2684 | 2016-01-04 | 2026-09-04 | `cec32bdc6be0c965dce07adee8625d5ca800875a6736a564fd87d8e341061d66` |
| CME.csv | 232855 | 2684 | 2016-01-04 | 2026-09-04 | `31132d1ee2f34111f51a71b7753cf8bd8d5c97cd21bdde12a21fcd7d1d2e7b67` |
| COF.csv | 228305 | 2684 | 2016-01-04 | 2026-09-04 | `c5b31bce8c02dced3664f1e9ef4b6558d76ee0e82bef7a6a05293627ec5faee7` |
| COHR.csv | 223099 | 2684 | 2016-01-04 | 2026-09-04 | `9a8bef1c8a39f066fe9da5bc3d4d988a7fbdd427f05d29cbb42bd389b06f2f4b` |
| COIN.csv | 117090 | 1356 | 2021-04-14 | 2026-09-04 | `6507e81cb1f2ae0128ad7009c9836bc2d0e40f6a22eb9be43bf9a4d076749651` |
| COP.csv | 226572 | 2684 | 2016-01-04 | 2026-09-04 | `a8c4cd64b9407562c7c3ebbf76c7d3e4208428631b9e5b8542a089aa38e73f07` |
| COST.csv | 233904 | 2684 | 2016-01-04 | 2026-09-04 | `b908dffa7621707a7f4b1147e37db852218f81f99d99e249efd10b6c47cc8ed5` |
| CRDO.csv | 96705 | 1156 | 2022-01-27 | 2026-09-04 | `bfed67f67ebc28582bcd82b0ac600fab93500f97b5d8258f4e8ef87f57aa5f26` |
| CRM.csv | 232141 | 2684 | 2016-01-04 | 2026-09-04 | `62d258df34271b093283982179cbec53d522172f445cce44dbfba895a2eb77b5` |
| CRWD.csv | 153741 | 1819 | 2019-06-12 | 2026-09-04 | `2a5f840acd51491b21e170559f02edd888e3c1d3b5018e0e5213a0e73280f5d0` |
| CSCO.csv | 225796 | 2684 | 2016-01-04 | 2026-09-04 | `0c6cfbed11ee3c0d341f69cd05e2c1bfe387abc8967db85f89ae7e47de7ae05f` |
| CVNA.csv | 193241 | 2352 | 2017-04-28 | 2026-09-04 | `1b535314ab626d272a7854f786740c50d526363bb5126bb18671168c1826e415` |
| CVS.csv | 224365 | 2684 | 2016-01-04 | 2026-09-04 | `47e0f2d0ba88d9de24b676dd0ce4d11e4075a16bc880af921a1957262bef5255` |
| CVX.csv | 232889 | 2684 | 2016-01-04 | 2026-09-04 | `347678ec5b06273975950fbea186ae13135580c796e1a1d31eba3106aa77490f` |
| DASH.csv | 123677 | 1441 | 2020-12-09 | 2026-09-04 | `7f33a7b70c18ae52198d0ededb1584c4e6e0e95bc26e382c1dd5b4063bfce338` |
| DBC.csv | 221991 | 2684 | 2016-01-04 | 2026-09-04 | `26774bb0629135e60e22622d700176c689785505f7900a2516ff80e64a44180d` |
| DDOG.csv | 149504 | 1750 | 2019-09-19 | 2026-09-04 | `fbc26b88b784e3c9e496f8aae1fc13436e508a2944ec696d745d313371ae6fd1` |
| DE.csv | 232436 | 2684 | 2016-01-04 | 2026-09-04 | `bc6662073414e2db928dc33252dd61b21d0a5aa2f0b5290cfdedb956285a9c1f` |
| DELL.csv | 162915 | 1932 | 2018-12-28 | 2026-09-04 | `6b779a5c63e775a528c8adba9caa3f245eaede1effd6a0c9520b51a64b1e2c6c` |
| DHR.csv | 231194 | 2684 | 2016-01-04 | 2026-09-04 | `4be9a7c9b1555b2608456382fc8f2086b94e5c40c182b19fb5c7d22e575530a2` |
| DIA.csv | 233616 | 2684 | 2016-01-04 | 2026-09-04 | `51841688b2322cf5e826dc1fa9975ac6834aa39d8527d3dc2b314fd8019abb9f` |
| DIS.csv | 231638 | 2684 | 2016-01-04 | 2026-09-04 | `6ec4dac46ab15c70dfe249e69e321665bcebb44701ab15dfe11192b9883c6876` |
| EEM.csv | 225626 | 2684 | 2016-01-04 | 2026-09-04 | `9b3a91bd2f3b06c21aea652de4214643948d4d667b7e708c59aa4834f6ec4d14` |
| EFA.csv | 225839 | 2684 | 2016-01-04 | 2026-09-04 | `6e4567784c6c3ae7dbef48d8f624751aca896d23a54fa0eb36bc76b719ee3a26` |
| ETN.csv | 228902 | 2684 | 2016-01-04 | 2026-09-04 | `95171c9373ebb41424b7a9586b682ab26226fb6f369d8c02194621a1ac951f46` |
| EWG.csv | 222614 | 2684 | 2016-01-04 | 2026-09-04 | `d2297b902035b0888bbde43114e4a54987001e92ce241e93707d727b8cc9752b` |
| EWJ.csv | 223285 | 2684 | 2016-01-04 | 2026-09-04 | `bee470f151d57353a2d04cbc0597e4aa9115d0cfc0fef855ad48bed92dc3fa6e` |
| EWT.csv | 223095 | 2684 | 2016-01-04 | 2026-09-04 | `bf09b9226fbb87e914af49232c039716c736aa2ec99caf16f9edce141f86c010` |
| EWU.csv | 222511 | 2684 | 2016-01-04 | 2026-09-04 | `286e46e50e95df6da86d18ab690969eb2f9cc365aac3c5d367e235c5c782ddf6` |
| EWY.csv | 223654 | 2684 | 2016-01-04 | 2026-09-04 | `be7b397e82eb6fcfc81862dae45439e19ac6ac5a996d9fadc3ad9cd0a082b3f1` |
| EWZ.csv | 225460 | 2684 | 2016-01-04 | 2026-09-04 | `6ab207522337c5db5333347f163be2d10353dc709ffd926f363678e8fce19483` |
| FCX.csv | 224512 | 2684 | 2016-01-04 | 2026-09-04 | `99e90a163a7a933199eaeabbfb1c066a153bd9616ae45a7393610b8c186c770d` |
| FIX.csv | 224887 | 2684 | 2016-01-04 | 2026-09-04 | `5ec61632e14fe809d953c843de793a6d1799145208352123b8979949caee0109` |
| FTNT.csv | 221881 | 2684 | 2016-01-04 | 2026-09-04 | `acda9827a17ee6dd7de75d758471586fa867ae96021e55c4bbea1ac3016dbaa7` |
| FXI.csv | 225445 | 2684 | 2016-01-04 | 2026-09-04 | `db4f922aac700e2f5141b12d33740359f19a548cbbc40895ca8e283232710e22` |
| GDX.csv | 225766 | 2684 | 2016-01-04 | 2026-09-04 | `c94696079ed4d5ebc813bf092050ec481f8b4b03312f6900eb5c47abfcef611d` |
| GDXJ.csv | 217830 | 2602 | 2016-05-02 | 2026-09-04 | `4911e78c049885fc78edd8715302934505ac88c8a37ce32b3785f771f4f50564` |
| GE.csv | 230286 | 2684 | 2016-01-04 | 2026-09-04 | `675a8c6691a01509aad9edfb79599e38968e68a36463f2f93016991159e6e575` |
| GEV.csv | 53366 | 610 | 2024-04-02 | 2026-09-04 | `f4f4f2b5b28ce5cfa429eb62567d4e90e1a2155c3c297d603a7e7d9ee8f94914` |
| GILD.csv | 225071 | 2684 | 2016-01-04 | 2026-09-04 | `2d9e8b88f14ab37069f36e519c783835afb8bde7a24e5c227c9ccf85aca00a31` |
| GLD.csv | 234427 | 2684 | 2016-01-04 | 2026-09-04 | `498aca8fd2c945c5529928af65b720efc083c6d345ea405e125e6a87a45cbbbb` |
| GLW.csv | 223820 | 2684 | 2016-01-04 | 2026-09-04 | `c9da3dafa7cc1b8921e76a9d9af1be7cea70edfd6796056ee820cafd5ac49454` |
| GOOG.csv | 230714 | 2684 | 2016-01-04 | 2026-09-04 | `d15c1f5a9a11c9f7a3cfd30569caaadf0a31af0a741887d80a9daf302d97ab17` |
| GOOGL.csv | 230722 | 2684 | 2016-01-04 | 2026-09-04 | `3398a8dc8dc6aa6e9afa96ec79593a0dac81e684618e6ae505066d44cc21dfd4` |
| GS.csv | 233820 | 2684 | 2016-01-04 | 2026-09-04 | `68f7fbfe0dcb9faa4ca376db2fd5ce3c2588c4d194f448bc49d3aad896d17619` |
| HD.csv | 233629 | 2684 | 2016-01-04 | 2026-09-04 | `f9675b9e1eb7801978cd80e17b3b010aaa63efcf05ac38f41c82cafab2bb177b` |
| HON.csv | 233328 | 2684 | 2016-01-04 | 2026-09-04 | `c2fdd5990a7cab5cf438631f0af2c5772a84b388c334bc5f00035030e9f2f759` |
| HOOD.csv | 106968 | 1282 | 2021-07-29 | 2026-09-04 | `dd3c5c81ca390310dde1dfe2c4d7fad3579448d78deb0f2730f739b2de000684` |
| HPE.csv | 223881 | 2684 | 2016-01-04 | 2026-09-04 | `7074118e899b74b6c0e9a548f3a5a8005bb4a8b7defe497df50a7dc036b84c7f` |
| HYG.csv | 225279 | 2684 | 2016-01-04 | 2026-09-04 | `157d9f9f8108a0a6f1f291f3c67ff600a93c6d56cea7606149a7fb0029f5c043` |
| IBB.csv | 231919 | 2684 | 2016-01-04 | 2026-09-04 | `fcfd82c2f81fcb76e6f0764f040e4b4159cc34f70cc934e118ca1306fccf2ea4` |
| IBM.csv | 233682 | 2684 | 2016-01-04 | 2026-09-04 | `5c44480f6f797b96cfc79eccc693be9b86789cb253485fe7f2b6a78fa4f2526e` |
| IEF.csv | 229846 | 2684 | 2016-01-04 | 2026-09-04 | `099e9b24f695083136123810f1239a1394a173247ac12afb8a0be70139f762df` |
| IEFA.csv | 223700 | 2684 | 2016-01-04 | 2026-09-04 | `9bf22f7c8d6c136b35e34d0930284730ef2437a787fbe951a03a372017dd2798` |
| IEMG.csv | 224271 | 2684 | 2016-01-04 | 2026-09-04 | `2d77a5a166594165e05edf394b5938919c43cd2cce792d7ee318637e465115bf` |
| IGV.csv | 223644 | 2684 | 2016-01-04 | 2026-09-04 | `fd603383b8c64383373f9b6065d1be8475001bb843594e74bf40dea592b3aa26` |
| INDA.csv | 222883 | 2684 | 2016-01-04 | 2026-09-04 | `7940d413cbce810d6ad41a0d7104524c2dc66dc8d57ee9f7e28e5018b17c161d` |
| INTC.csv | 225939 | 2684 | 2016-01-04 | 2026-09-04 | `89529851147e9a650ac8628ccb2f23d0f9999fb0b397c48e59a79e1c429bd4d8` |
| INTU.csv | 233054 | 2684 | 2016-01-04 | 2026-09-04 | `76e0806f1985d50f1c07b85e55a8d8a38a60c3befa6d5dc7b5da1ca07ae106ea` |
| IONQ.csv | 116804 | 1425 | 2021-01-04 | 2026-09-04 | `1b3ac479e7ea226345355d147f396254f76361884d8ac9a53f73ed257bd4e3db` |
| IREN.csv | 97410 | 1204 | 2021-11-17 | 2026-09-04 | `d99e43dc56d2da8d7940c92c5e63bc986961d3692912d2b0fa077564aab02253` |
| ISRG.csv | 232058 | 2684 | 2016-01-04 | 2026-09-04 | `a6a7c553ec99304a50ea8dc6e075d5cfedd3c6ed92b7176960cdb8b6be4960b8` |
| ITB.csv | 224404 | 2684 | 2016-01-04 | 2026-09-04 | `9a29030bdc95284b4c5692b3c348b3480e07d84cccaf9bbb33b529de8eb95be3` |
| IVV.csv | 233712 | 2684 | 2016-01-04 | 2026-09-04 | `4be368b45e211ac214a66569ee223d821c52bee3b3721be4b0d589a6782f3083` |
| IWM.csv | 236159 | 2684 | 2016-01-04 | 2026-09-04 | `82c5a4d1f033c11f709532296453bb8738129b6e69c68a76937432ede742e0e7` |
| IYR.csv | 224949 | 2684 | 2016-01-04 | 2026-09-04 | `e2cce775448faabe0b9b7261948abbebb166a428db4b19f95ac30dbace6b87b6` |
| JNJ.csv | 234006 | 2684 | 2016-01-04 | 2026-09-04 | `a6f7a2380fa5d2cb23f4916a9cb22b61524bc5f17edec2a8f3f725bd99ab6911` |
| JPM.csv | 232919 | 2684 | 2016-01-04 | 2026-09-04 | `cc52d516035c9d10eb8f14796e8a960146c83eb532e213eee17dd0b9316aa0e1` |
| KLAC.csv | 223746 | 2684 | 2016-01-04 | 2026-09-04 | `3f627c96f9a5423cf46c12de45e7b4e4a270d8d5166f7e56390050ecb0cab028` |
| KO.csv | 225142 | 2684 | 2016-01-04 | 2026-09-04 | `4eaf26d2ff5db7596d823e1d01e3c5011d1689e073df23da71828de87eb5f078` |
| KRE.csv | 223959 | 2684 | 2016-01-04 | 2026-09-04 | `b0aa6393b964d980199565d7f67eb3aa6bb2c5d2f01900cca912c2aa2d93c2b1` |
| LIN.csv | 171448 | 1971 | 2018-10-31 | 2026-09-04 | `decaa7e16b5dd37c1157a587775e6031e9cb838b142ca400124fcef97426e291` |
| LITE.csv | 223314 | 2684 | 2016-01-04 | 2026-09-04 | `467bc870f688c88d5f72d19b7a1da6d46358f1626ae5ed2b286de2a42a146045` |
| LLY.csv | 231625 | 2684 | 2016-01-04 | 2026-09-04 | `731d8ee25c6aa855fdebf9c812e3539559a78331794a76f3f0434ddf737f3d1d` |
| LMT.csv | 232861 | 2684 | 2016-01-04 | 2026-09-04 | `ea2dc2f15aca31ba8e95c9c5df3de449a32fbce5d1b46cc6d49ddafcc22f546d` |
| LOW.csv | 230490 | 2684 | 2016-01-04 | 2026-09-04 | `b4295207010abc5b60cb3965eabe6d4af0070d3131296f4aee88e40c4de42350` |
| LQD.csv | 235226 | 2684 | 2016-01-04 | 2026-09-04 | `8536dfb2bae9b367f36eaa3b295387f5c7f75db547dc9489023f77a141a5103c` |
| LRCX.csv | 225335 | 2684 | 2016-01-04 | 2026-09-04 | `474e9032d32d83613dff8045efbaa19be6f80e87d0948753dccb6d92f09d174c` |
| MA.csv | 232857 | 2684 | 2016-01-04 | 2026-09-04 | `89129951803629c11a16fbb95ebba2a7efc1053eee8496905be8fd94be0a923d` |
| MCD.csv | 233596 | 2684 | 2016-01-04 | 2026-09-04 | `b80636d53991519a43dfd49a19d3dcc8cb9bb971b489983f4fe8b3e83ec88237` |
| MCHP.csv | 223155 | 2684 | 2016-01-04 | 2026-09-04 | `5b1c206f40adc322593edb282d1644c255bf0c4db610596d0cdeeca04686a2be` |
| MCK.csv | 232515 | 2684 | 2016-01-04 | 2026-09-04 | `0e8746cef47eef7f5a23d43c89b0d77251568b52f3c7696ed1c9c756b168dc32` |
| MDLZ.csv | 223401 | 2684 | 2016-01-04 | 2026-09-04 | `1cad46fb566fd0223ba360bee42daccfad2ff278c288dc51d047e5cc04d9f776` |
| MDT.csv | 225624 | 2684 | 2016-01-04 | 2026-09-04 | `757b4a2d85230554884c0393a8b5987717c22b58cc32531b31ecd2d306f1db6c` |
| MDY.csv | 232028 | 2684 | 2016-01-04 | 2026-09-04 | `175df25eeda80768965e2d5a97b9ca793d0ea52ffc23ac27b22a35b63bdcb26f` |
| MELI.csv | 236423 | 2684 | 2016-01-04 | 2026-09-04 | `04bee783ecfd8c3f2030ed13cc0fd7688c3f3048a035110f371bdcb4edef69a7` |
| META.csv | 235972 | 2684 | 2016-01-04 | 2026-09-04 | `648737a61e05927ff4fe386642e72b56f38f27b371b29446dfff7899f10af2e4` |
| MPC.csv | 227073 | 2684 | 2016-01-04 | 2026-09-04 | `ffa8dbd69556ab36fe0ce74cd45ac182dce35b77bc81db22c5d269af180a3cd7` |
| MPWR.csv | 230161 | 2684 | 2016-01-04 | 2026-09-04 | `11541f5d2e890c51fbe5cd2a33b9ec8bcec549aae3d6b965cf038b4604a28c20` |
| MRK.csv | 227095 | 2684 | 2016-01-04 | 2026-09-04 | `09350e5c3bfe241d0d8a724c45821ea5985aaf123f5100c10f519206eff97aa5` |
| MRVL.csv | 224456 | 2684 | 2016-01-04 | 2026-09-04 | `00f7b3df6c9bb933dff9bf32b0934dee43de31fd6e6d7125988df4df5ee8cca4` |
| MS.csv | 226368 | 2684 | 2016-01-04 | 2026-09-04 | `618099969677e498ecf7d3a2d5cf1dedb6f5098f7a85814454601cffe215d885` |
| MSFT.csv | 233755 | 2684 | 2016-01-04 | 2026-09-04 | `26c983d671eda98026e7dc0eb3a1046ddbafae86ad059add912281649a7c6d01` |
| MSTR.csv | 225250 | 2684 | 2016-01-04 | 2026-09-04 | `200a0ccfdeee8ccfb199f09f59450104015e3151d2cecbe67d82e4726f86ceac` |
| MU.csv | 227409 | 2684 | 2016-01-04 | 2026-09-04 | `db16afd6ae681824a138bf9051fb88a79399fe1b8b7499bed3712f1127f79261` |
| NBIS.csv | 216478 | 2641 | 2016-01-04 | 2026-09-04 | `4ce0259a628b569d1d99d077c0563a51850a72a69f86fc16d56511ee4ad355fe` |
| NEE.csv | 223768 | 2684 | 2016-01-04 | 2026-09-04 | `6a32f63e6bffe340fb8286c3ce92a6b78cf34a495406764cbc16e424a26adc09` |
| NEM.csv | 224098 | 2684 | 2016-01-04 | 2026-09-04 | `486a4e4f26c070e20fea60d738dcb1a8ee8e37ebfb1007b8b339035b93fed5d5` |
| NET.csv | 148182 | 1754 | 2019-09-13 | 2026-09-04 | `2c10cfd6e7f81319521063211ac7fe435e83c6bbe03ab8b3964dce07d66bc5db` |
| NFLX.csv | 226155 | 2684 | 2016-01-04 | 2026-09-04 | `580033f8f1aaff22720b561bce2e8ca37305dd6d5b6c82defaacff9dd8a6e36f` |
| NKE.csv | 227255 | 2684 | 2016-01-04 | 2026-09-04 | `849d46c666f25399d67a04b20c5a9c9267505fe069fee6037d1373bb99d196a5` |
| NOW.csv | 228146 | 2684 | 2016-01-04 | 2026-09-04 | `5572f2704fc589349187bb805454cc4e982ad372e2afa937230590c942457e62` |
| NVDA.csv | 225993 | 2684 | 2016-01-04 | 2026-09-04 | `b8e7816e2585159e3bad217498806bb2037b4182120201f8172ce4679703ef45` |
| NXPI.csv | 231385 | 2684 | 2016-01-04 | 2026-09-04 | `b1852762575299ba6421d529701af597977472673c0d8fdb2adb7e5d4fda45d4` |
| OIH.csv | 223854 | 2602 | 2016-05-02 | 2026-09-04 | `ca9fb9919bf717caae2827078cfacc4c6aa733f6c95329e162bfaee73a17ffda` |
| ON.csv | 222912 | 2684 | 2016-01-04 | 2026-09-04 | `44369e966f872634a158ba1f1400d4febfda80e62a4dbd5fce2b6068738c5b21` |
| ORCL.csv | 227803 | 2684 | 2016-01-04 | 2026-09-04 | `c18c4f8bb251c75b546b1021e881a533da75700e023b8cf60f62c0635be4f1d3` |
| PANW.csv | 226854 | 2684 | 2016-01-04 | 2026-09-04 | `4ee3c334674287a1616043f699e9521233fd544784657052a99d1c24c8463179` |
| PDBC.csv | 221914 | 2684 | 2016-01-04 | 2026-09-04 | `e00754c55ae5fd943cf32ef635931a1eb1547c316a732b8a1eb96e2dd259110f` |
| PEP.csv | 233450 | 2684 | 2016-01-04 | 2026-09-04 | `bd2c40add272d02140c945d08a3555c5accd98e1fb9810d216424faefcd8afe3` |
| PFE.csv | 225514 | 2684 | 2016-01-04 | 2026-09-04 | `30ddb4e10172b92ff9dbdfe24aa82b08d0e71f6b876585aa59ffe5f03be389cd` |
| PG.csv | 231016 | 2684 | 2016-01-04 | 2026-09-04 | `ecd684962519a0cd82949b7405d7e218710073662d7262fdfb10697fe099cc25` |
| PLTR.csv | 125736 | 1490 | 2020-09-30 | 2026-09-04 | `0e6986fc4814bbb1f433581894ac571b8d30973541e54e2207010b67e6d01f01` |
| PM.csv | 227374 | 2684 | 2016-01-04 | 2026-09-04 | `fb2a1b2fc6bce618a1978fc5bef5c173c4c8967f0a622bf39dc32c2bff863158` |
| PWR.csv | 226944 | 2684 | 2016-01-04 | 2026-09-04 | `e61229b1b01e373b90b8ee0c9178370508821aebefb874ce1ed0f8822a2375c3` |
| PYPL.csv | 227176 | 2684 | 2016-01-04 | 2026-09-04 | `e846d706c8c7874c640c32e91caa03a3ce4500197e39ca1ec1fd4929fe123214` |
| QCOM.csv | 230112 | 2684 | 2016-01-04 | 2026-09-04 | `0a5daa2e84680318f91b063ef583e944f07e04ec7bfb01ed0c4317a08a6566d8` |
| QQQ.csv | 236257 | 2684 | 2016-01-04 | 2026-09-04 | `a1661c04be5950187821d4652e4ec0ef0de693a52acf503a7ade6ad18e4f5144` |
| QQQM.csv | 128195 | 1481 | 2020-10-13 | 2026-09-04 | `5909cdfe7967b1274670745bdf7e88248ff95ce3f77256cacce7e4ea3422f965` |
| RCL.csv | 228629 | 2684 | 2016-01-04 | 2026-09-04 | `509f8b26e2a71fbe8c53bb0556b99096044dd4c3397131188385e03c91f60418` |
| RDDT.csv | 53117 | 617 | 2024-03-21 | 2026-09-04 | `4ad7edadea67dce125b043c132ddaf7cc00d44edb02e704a2821c2795d3faab5` |
| RKLB.csv | 118144 | 1451 | 2020-11-24 | 2026-09-04 | `8296719fb0d7e175bd629ae369a0c9d55af2faea21a0962825fe557b683518f6` |
| RSP.csv | 230453 | 2684 | 2016-01-04 | 2026-09-04 | `93ef94dfeb4b2a1c0d1e89867a458880840b6f814c1d2810bf2c1f9c895ca81f` |
| RTX.csv | 229886 | 2684 | 2016-01-04 | 2026-09-04 | `aac23962d428fa81b8684b312ec5ce936c69e578d9387f094993e21eda69ee30` |
| SBUX.csv | 225845 | 2684 | 2016-01-04 | 2026-09-04 | `4bc11f1d39358d37f82c0c790a3675615a46788947928c8e1b55a0221b035e92` |
| SCHD.csv | 223540 | 2684 | 2016-01-04 | 2026-09-04 | `2391344b06afdcee6b55c216b06f2d9b6eb208191b3b8ce13a88232dccb651cc` |
| SCHW.csv | 223934 | 2684 | 2016-01-04 | 2026-09-04 | `e7b66d71f1cd99e23b80f34bef9a48a2b33294666d73d033f5739357015cdb43` |
| SHOP.csv | 225807 | 2684 | 2016-01-04 | 2026-09-04 | `2cff341821b01000a10f61a8b62b7390f9db90a28c963087ba263c854423111b` |
| SHW.csv | 232330 | 2684 | 2016-01-04 | 2026-09-04 | `d7ca643629d4fbbbbaffc87897df74611226811d5d7770619b6bf0dc6681844b` |
| SHY.csv | 222607 | 2684 | 2016-01-04 | 2026-09-04 | `3f640483f39de7774df6576eb1363072008a2b306a5ad4bc10b8be3adba729a5` |
| SLB.csv | 224339 | 2684 | 2016-01-04 | 2026-09-04 | `ef8dc6800665a26d6814ed6fd4b3cd041abb748441aab04fc6bf08892660f66f` |
| SLV.csv | 224807 | 2684 | 2016-01-04 | 2026-09-04 | `e24c69b98417492804ecb7d67fd0440692fb77877aaa63df411ff7435d4a756a` |
| SMCI.csv | 214596 | 2684 | 2016-01-04 | 2026-09-04 | `bb522e885a1769842ad879af7eccc740feaf2b29bf61ba7345474d68a36eb00a` |
| SMH.csv | 229262 | 2684 | 2016-01-04 | 2026-09-04 | `b4ff929f6d30cbe365a40ea2d282f2619c23162ec3299bd70c642e2e149dea81` |
| SNOW.csv | 130660 | 1500 | 2020-09-16 | 2026-09-04 | `dffb2fa319c5e733500b3fead86b80914b0bf729e84481732b54c928bc9a61a5` |
| SNPS.csv | 229169 | 2684 | 2016-01-04 | 2026-09-04 | `74b4f49dee044bc62463c11244341f1d109d80a0fb202c26475f85ee8abef78f` |
| SOXX.csv | 228722 | 2684 | 2016-01-04 | 2026-09-04 | `9b672e9a15bf342f8af8331714541fe0e62e00dfc655defe2b652ff70b4a4a08` |
| SPGI.csv | 232604 | 2684 | 2016-01-04 | 2026-09-04 | `a3573f8e7a5766df5b645c94d841c1888bac2eb8f856c4b72106b435ef179b87` |
| SPOT.csv | 183720 | 2119 | 2018-04-03 | 2026-09-04 | `1805881a1f5dba96a39b5dec225946b91b9832f7fa0e6cbe650cd2a30fa864c2` |
| SPY.csv | 236810 | 2684 | 2016-01-04 | 2026-09-04 | `d049a6e599f299dc4fd5a45219126d2c177e6d51e34f1ff17974e9d84c0a12ae` |
| SPYM.csv | 221470 | 2684 | 2016-01-04 | 2026-09-04 | `fafa4b597f7d9d74e3fcbee28545d5b822822549b3c932210c102dd8f648a004` |
| STX.csv | 224965 | 2684 | 2016-01-04 | 2026-09-04 | `5e06f5dff2d770bd44e3c9978500f0f2583237f73150984496aa4e0fa2c1f583` |
| SYK.csv | 232827 | 2684 | 2016-01-04 | 2026-09-04 | `8329008a15058d6b2746c240e33c54c38c8d564a9ff50309c914009f1e7136f1` |
| T.csv | 225539 | 2684 | 2016-01-04 | 2026-09-04 | `e552c2fbf65a3edf7d6d66b34f3242883e94d533bc0b901d144d8750cc68a936` |
| TER.csv | 227199 | 2684 | 2016-01-04 | 2026-09-04 | `8c511729ae73a5e605dfe6d90d8324dc03b69146de668d15e0488d5d81392e65` |
| TIP.csv | 233075 | 2684 | 2016-01-04 | 2026-09-04 | `6ec7ba7c8cd9d93219d82e458beee3c27e739bb7b2626cfc4613c382b8939c0e` |
| TJX.csv | 225495 | 2684 | 2016-01-04 | 2026-09-04 | `a079b215e35907a842f698aa515137a2fd70e1517acbb43800c4a48226178992` |
| TLT.csv | 232223 | 2684 | 2016-01-04 | 2026-09-04 | `d66327e8374fc2c3b87f7cd7199d8f0e41293bbd253aae9e8a9f9142cdd676f7` |
| TMO.csv | 233289 | 2684 | 2016-01-04 | 2026-09-04 | `926f4f1a7e6e7bf83912f51d3e584ccb4ef0cd4369dcbd2de6e330770152aeb5` |
| TMUS.csv | 229207 | 2684 | 2016-01-04 | 2026-09-04 | `75e7fd56f33872e23534b9970b4f673cc3d04a4244003a42a3e2a614fb2aaad4` |
| TSLA.csv | 232838 | 2684 | 2016-01-04 | 2026-09-04 | `9d89182b6b77fcefd9cf2d4c29d2c40ef064570becdbcf9ac10711c7a903c1da` |
| TSM.csv | 228239 | 2684 | 2016-01-04 | 2026-09-04 | `26944dd6adf6893b14d4356d9d5cc652481c82af15d387f3ba97375e860168da` |
| TXN.csv | 231458 | 2684 | 2016-01-04 | 2026-09-04 | `5b184201ce6d0d471264d6a85cdac3c4046b454a20cfcf013514fa2b0dbce487` |
| UBER.csv | 154576 | 1841 | 2019-05-10 | 2026-09-04 | `039e15a795e6032c8f0e73bd8b0ef346b7c505121b777a8725c8eea487f31b5c` |
| UNG.csv | 224505 | 2684 | 2016-01-04 | 2026-09-04 | `fb6aefb71b3426da06e7ac9949a21edf06b6daf66fe0defd0a857987adc0841b` |
| UNH.csv | 233719 | 2684 | 2016-01-04 | 2026-09-04 | `e4bd8d5294586d99fb0411feb4bc6cf50333480a3384476f2387e309e28aa398` |
| UNP.csv | 232677 | 2684 | 2016-01-04 | 2026-09-04 | `829d667af8953073b85420e88abd11cb586859c9ea3fffb884b486e51430701d` |
| UPS.csv | 232299 | 2684 | 2016-01-04 | 2026-09-04 | `5e8f167628c3ed179518154d64dbe419f3a9b9e858badce8bad600cad4b8a7cf` |
| USO.csv | 224518 | 2684 | 2016-01-04 | 2026-09-04 | `c64779cbed80839bd094ea0bdbf812ef73e62634ec5e4eefb8d2c5b9a659edf4` |
| V.csv | 232691 | 2684 | 2016-01-04 | 2026-09-04 | `5b86c21a8b2700e848e221bcbb13824d32dd2771acc0b6f6a72280a0993adbd9` |
| VCIT.csv | 222620 | 2684 | 2016-01-04 | 2026-09-04 | `b3c55c3c6c2cb5ca0109f5e53e3359f95ef3e6da0d21a4269c38a0e2978fa6f9` |
| VEA.csv | 224076 | 2684 | 2016-01-04 | 2026-09-04 | `215d0dc0810659d84c13a946224e37c8efe6b01074819dee4f95bb7ab269488f` |
| VLO.csv | 227866 | 2684 | 2016-01-04 | 2026-09-04 | `9927616eb79af64c918f6ad529e09f16b5ec1e2469d9b6eb85a5745851894bf7` |
| VNQ.csv | 223902 | 2684 | 2016-01-04 | 2026-09-04 | `4b01ea68df7122ad1cb544fadb0c7680f01f927b4b44dd870f0480e017ab9e88` |
| VOO.csv | 233679 | 2684 | 2016-01-04 | 2026-09-04 | `7b8cf80c315ac693540552004a394873fc4ff8e169bd2f0b9ef782a1f031bac2` |
| VRT.csv | 169254 | 2037 | 2018-07-30 | 2026-09-04 | `e24713a9f54ef9ab24cc2eca7c10c16849e7b291a6702434b89f93da37d61b91` |
| VST.csv | 196659 | 2344 | 2017-05-10 | 2026-09-04 | `785406e5b5ca228b85ac05a4f929025c31a970e37f36d25a9b216d43bb3a271b` |
| VTI.csv | 233444 | 2684 | 2016-01-04 | 2026-09-04 | `6915d1cf6b784a35109082806d8cf322d6dadb733500cfe585be3588c3ff7c0b` |
| VWO.csv | 224385 | 2684 | 2016-01-04 | 2026-09-04 | `f50923ace2fd2b1e7b5e02e5985960b210a8a28c59bc5398dec25fc3df217d88` |
| VZ.csv | 225393 | 2684 | 2016-01-04 | 2026-09-04 | `f61edee16edced3bf4c40feb1d039b3ec982922c1d303eadba9406eec32b983a` |
| WDAY.csv | 231892 | 2684 | 2016-01-04 | 2026-09-04 | `bdf038c47b2b35a457586be9428dfcbc5877996fc100f0584e00c9b6fd5efbf7` |
| WDC.csv | 224034 | 2684 | 2016-01-04 | 2026-09-04 | `3cc0fa34579352f3b35094742459cbf448e8c6eb655da7c685e1aaa23de9a31d` |
| WELL.csv | 225127 | 2684 | 2016-01-04 | 2026-09-04 | `f27b8bdf7fe1189c4a621622d87f0b3537538f5eee98f3cd626742dccd52829c` |
| WFC.csv | 225429 | 2684 | 2016-01-04 | 2026-09-04 | `47d44ad76e55f92d43fcdc5a8dd54096ae9b24e3409a5b9cf4084850e466c145` |
| WMT.csv | 226558 | 2684 | 2016-01-04 | 2026-09-04 | `a991cf9647c76746eea9dc6b033717fbb2a3d40677e6016a8dbac7dd75ca5fd9` |
| XBI.csv | 226240 | 2684 | 2016-01-04 | 2026-09-04 | `84ec455d876fd505b61284cf4e31db3fcccad87ace795c1e7a1acf3056a34f6e` |
| XHB.csv | 224830 | 2684 | 2016-01-04 | 2026-09-04 | `d01c7d20f2f69e0c1164e7ccf06a6f37702aa2910c245a624d6a13f3d6022bec` |
| XLB.csv | 224433 | 2684 | 2016-01-04 | 2026-09-04 | `7ad9e4cbbfed2e1a731bdbff9b2ea6fa1137519d012bcbba09d665900ac32bf5` |
| XLC.csv | 172932 | 2065 | 2018-06-19 | 2026-09-04 | `bbee574dd67fe77547711b6e79440386d274963c31c75ac5ad4b0e2d48568d80` |
| XLE.csv | 225567 | 2684 | 2016-01-04 | 2026-09-04 | `8f5c19c5cd0338223f5fe4ede6ee9a89e558985cd84a7b6fefd6466f1085cdca` |
| XLF.csv | 225658 | 2684 | 2016-01-04 | 2026-09-04 | `7536bbe49e567823f47f08dde99c2ec9f57d552478115cec41b294cbba86141d` |
| XLI.csv | 228590 | 2684 | 2016-01-04 | 2026-09-04 | `95c1d8ff75acfcf545e6d5d972f67db7227f53986489f8d2c7b80f59ba41d67b` |
| XLK.csv | 227662 | 2684 | 2016-01-04 | 2026-09-04 | `70da6336e8c7d2b832fae4fadbba9eef606cc575ef612f23186dff0a35a2f779` |
| XLP.csv | 224618 | 2684 | 2016-01-04 | 2026-09-04 | `da74c4f01881cffb2e6fc59969f6761532c3e8b52aab9f52a02e891eb2ae679e` |
| XLRE.csv | 222454 | 2684 | 2016-01-04 | 2026-09-04 | `8aa289af04266da11baa3a9c2d160bcfc13c7be21e293e5aad5ab2b7a6a6d81c` |
| XLU.csv | 225489 | 2684 | 2016-01-04 | 2026-09-04 | `3325c3da83514ff0453a116e34abb11f5d488cc524dfd90cffe31e2497f131a3` |
| XLV.csv | 230412 | 2684 | 2016-01-04 | 2026-09-04 | `a2675535586892f15dec50028e211fa4b5fd3c1565465db39dcb2dac8eda56d3` |
| XLY.csv | 225828 | 2684 | 2016-01-04 | 2026-09-04 | `618bc550db8afc672802122410b9c5601a26e12f7b17031a1901baac72a04d5e` |
| XOM.csv | 229098 | 2684 | 2016-01-04 | 2026-09-04 | `772bfd5c3b0b9027fdad8a6bb57f1bd0469774450981df289c03a710c393b878` |
| XOP.csv | 231372 | 2684 | 2016-01-04 | 2026-09-04 | `1186e5f3eab65e155bd7198b523088478dbad8e747c9f00f45cfdd94d1ecab68` |
| XRT.csv | 222998 | 2684 | 2016-01-04 | 2026-09-04 | `f0f2ba522459e6a3eb33002efe7ddd37f89d328f1ebdb511680b75a86c07f423` |

## Appendix 2 — scripts that depend on a scratchpad price store

Direct references and dependencies inherited by import. "Reproducible today" describes whether the script can find its data now, not whether its historical result would repeat.

| script | store | lookup and hazards | reproducible today? |
|---|---|---|---|
| `analyse_h0009.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `analyse_h0010.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `analyse_h0011.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `attribute_entry_signal.py` | deep | temp glob [0]; silent skip; 400-bar patch | yes, while the scratchpad copy exists |
| `audit_h0003.py` | deep/long | temp glob [0]; silent skip; 400-bar patch | decade mode only - thirty-year absent |
| `audit_sizing.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `buckets.py` | deep | beside script | NO - scripts/deep does not exist |
| `build_training_seed.py` | deep/long | temp glob; silent skip; 400-bar patch | decade mode only - thirty-year absent |
| `copy_analyse.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `copy_build_cache.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `decompose_timing.py` | deep | temp glob [0]; silent skip; 400-bar patch | yes, while the scratchpad copy exists |
| `entry_latency_test.py` | deep | beside script | NO - scripts/deep does not exist |
| `exposure_levers_test.py` | deep/long | direct path | decade mode only - thirty-year absent |
| `forensics_breadth.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `forensics_bucket_capacity.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `forensics_buckets.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `forensics_copy_sources.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `forensics_post_stop.py` | deep | temp glob [0]; silent skip; 400-bar patch | yes, while the scratchpad copy exists |
| `forensics_regime.py` | deep | temp glob [0]; silent skip; 400-bar patch | yes, while the scratchpad copy exists |
| `forensics_regime_stability.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `form4_feasibility.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `h0005_descriptive_27.py` | deep | temp glob [0]; silent skip; 400-bar patch | yes, while the scratchpad copy exists |
| `h0013_build_features.py` | deep | temp glob >=200 files | yes, while the scratchpad copy exists |
| `h0014_acquire_snapshots.py` | deep/snapshots | temp glob >=200 files | yes, while the scratchpad copy exists |
| `h0014_analyse.py` | deep/snapshots | temp glob >=200 files | yes, while the scratchpad copy exists |
| `h0014_ic_yearly.py` | deep/snapshots | direct path | yes, while the scratchpad copy exists |
| `h0014_validate.py` | deep/snapshots | temp glob >=200 files | yes, while the scratchpad copy exists |
| `h0016_probe_cash.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `h0017_acquire.py` | deep | temp glob >=200 files | yes, while the scratchpad copy exists |
| `h0017_analyse.py` | deep | temp glob >=200 files | yes, while the scratchpad copy exists |
| `h0019_controls.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `h0019_measure.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `h0021_haircut.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `h0021_peaktiming.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `h0022_gain_recognition.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `intraday_exit_measure.py` | deep | temp glob >=200 files | yes, while the scratchpad copy exists |
| `intraday_exits_acquire.py` | deep | temp glob >=200 files | yes, while the scratchpad copy exists |
| `intraday_probe.py` | deep | temp glob >=200 files | yes, while the scratchpad copy exists |
| `invert_signal_test.py` | deep | beside script | NO - scripts/deep does not exist |
| `overnight_control_test.py` | deep | beside script | NO - scripts/deep does not exist |
| `overnight_decomposition.py` | deep | beside script; 400-bar patch | NO - scripts/deep does not exist |
| `overnight_persistence_test.py` | deep | beside script | NO - scripts/deep does not exist |
| `phase5_anatomy.py` | deep/long | temp glob [0]; silent skip; 400-bar patch | decade mode only - thirty-year absent |
| `phase5_candidates.py` | deep/long | temp glob [0]; silent skip | decade mode only - thirty-year absent |
| `phase5_fetch_news.py` | deep | direct path | yes, while the scratchpad copy exists |
| `phase5_filters.py` | deep/long | temp glob [0]; silent skip; 400-bar patch | decade mode only - thirty-year absent |
| `phase5_news_analysis.py` | deep | direct path | yes, while the scratchpad copy exists |
| `phase5_news_filter.py` | deep/long | temp glob [0]; silent skip; 400-bar patch | decade mode only - thirty-year absent |
| `probe_holding_cap.py` | deep | temp glob [0]; silent skip; 400-bar patch | yes, while the scratchpad copy exists |
| `probe_owner_params.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `regime_forensics.py` | deep | temp glob [0]; silent skip; 400-bar patch | yes, while the scratchpad copy exists |
| `register_h0017.py` |  | temp glob | yes, while the scratchpad copy exists |
| `retune_sweep.py` | deep | beside script; 400-bar patch | NO - scripts/deep does not exist |
| `run_h0005.py` | deep | temp glob [0]; silent skip; 400-bar patch | yes, while the scratchpad copy exists |
| `run_h0006.py` | deep | temp glob [0]; silent skip; 400-bar patch | yes, while the scratchpad copy exists |
| `run_h0007.py` | deep/long | temp glob [0]; silent skip; 400-bar patch | decade mode only - thirty-year absent |
| `run_h0008.py` | deep | temp glob [0]; silent skip; 400-bar patch | yes, while the scratchpad copy exists |
| `run_h0009.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `run_h0010.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `run_h0011.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `run_h0012.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `run_h0013.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `run_h0014.py` | deep/snapshots | temp glob >=200 files | yes, while the scratchpad copy exists |
| `run_h0015.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `run_h0016.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `run_h0020.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `run_h0021.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `run_h0025.py` | deep | via forensics_regime | yes, while the scratchpad copy exists |
| `run_sealed_exits.py` | deep/long | temp glob [0]; silent skip; 400-bar patch | decade mode only - thirty-year absent |
| `short_book_sim.py` | deep/long | direct path | decade mode only - thirty-year absent |
| `short_mirror_test.py` | deep | beside script | NO - scripts/deep does not exist |
| `stop_check.py` | deep/long | 400-bar patch | decade mode only - thirty-year absent |
| `thirty_year_test.py` | long | 400-bar patch | NO - thirty-year data absent |
| `trend_filter_test.py` | deep/long | direct path | decade mode only - thirty-year absent |

