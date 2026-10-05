# Research loader and Clean OOS integrity audit

*2026-09-24. Research-infrastructure and governance correction only. No
backtest, no economic experiment, no registration (no hypothesis ID used), no
Clean OOS read or result, no model retrained, refitted or evaluated, no live
trading change. Labels: **confirmed** — verified from code, data or ledgers in
this task; **inferred** — reasoned from repository evidence; **unknown** —
not established.*

> **Update, later on 2026-09-24.** The remaining dependency below — the 22
> class-B scripts of §4.2 — was worked through by the
> [governed research dataset migration](2026-09-24-governed-research-dataset-migration.md):
>
> - all 17 that read decade data now read it through the gate;
> - 3 are intraday-only;
> - 2 are derived-file only.
>
> The classification there is still B. The reason is narrower: H-0014's
> unverified, decade-derived feature cache in the scratchpad. The text below
> is kept as written.
>
> **Later that day:**
>
> - the H-0014 cache was reproduced byte-for-byte and registered;
> - the four intraday stores of retirement criterion 4 were preserved
>   byte-identically — [intraday preservation](datasets/intraday-preservation-2026-09-24.md).
>
> Criterion 4 is now met as far as the scratchpad holds data. H-0014's raw
> 5-minute bars were never retained anywhere.

---

## 17. Classification: **B — PARTIALLY RESTORED**

**Restored (confirmed):** the shared loader `scripts/forensics_regime.py`, and
all 29 scripts that import it, now reach the decade data only through
`research_gate.verify_dataset`. That path is pinned to the dataset hash, is
fail-closed, and has no scratchpad fallback. The 18 governed (class B) runners
among the 29 include every runner of H-0009, H-0010, H-0011, H-0012, H-0013,
H-0015, H-0016, H-0019, H-0020, H-0021 and H-0025.

**Remaining dependency (confirmed):** 22 other class-B scripts, in this
morning's classification, still depend on the scratchpad (§4.2):

- 19 find it with their own temp-directory lookup;
- 1 (`h0014_ic_yearly`) reaches it at import, through `h0014_analyse`;
- 2 (`phase5_fetch_news`, `phase5_news_analysis`) read only derived files in
  `data/phase5/`, which scratchpad-reading scripts wrote.

They are the runners of H-0005 … H-0008, the phase-5 ledger scripts
(including `run_sealed_exits`, the H-0001 … H-0004 executions), the H-0003
audit, and the H-0013, H-0014 and H-0017 pipelines.

A is not claimed: governed runners still depend on the decade scratchpad.

---

## 1. Governance gate — confirmed

No experiment registered and no hypothesis ID used or consumed. No closed
branch reopened. No backtest, economic comparison or Clean OOS inspection.
Nothing in `src/` changed: no strategy behaviour, parameter, emulator,
execution haircut, benchmark methodology or 400-bar window. No forward data
consumed. No live order. Ledger, fingerprint, freeze date and Clean OOS chain
preserved.

## 2. Baseline integrity check — confirmed, before any edit

| check | value | source |
|---|---|---|
| baseline | **+58.5889000000% / 698** | `baseline_metrics`, `docs/phase5-research.jsonl` — read, not rerun |
| dataset-use ledger | **162 rows** | `docs/dataset-uses.jsonl` |
| fingerprint | `da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b` | `forward.frozen_fingerprint()` |
| Clean OOS | **0 sessions**; chain intact; `data/forward-evaluation.jsonl` absent | `forward.load_sessions()`, `verify_chain()` |
| freeze | **2026-09-11**; embargo 20 sessions | `purge.freeze_date`, `purge.embargo_sessions` |
| planned start | **2026-10-12, projected** | Phase 4 protocol §1 |
| `LEARNED_RANKING_ENABLED` | **False** | `live_model.py` |
| `src/`, `tests/` | 0 changed, 0 untracked | `git` |

## 3. The exact loader change — confirmed

`scripts/forensics_regime.py`, and only its data path:

- **Removed:** the module-level
  `SCRATCH = Path(glob.glob(".../scratchpad/deep", recursive=True)[0]).parent`,
  and the `glob` import that only it used.
- **Added:** `DECADE_DATASET = "decade-2016-2026-split-adjusted-230"` and
  `DECADE_SHA256 = "935fed79…73d4a7"`, and an import of
  `research_gate.verify_dataset`. The scripts directory is appended to
  `sys.path`, so it cannot shadow anything.
- **`load()`:** now calls `verify_dataset(DECADE_DATASET, DECADE_SHA256)` and
  reads only from the path returned. A universe symbol with no file raises
  `FileNotFoundError`. A file that fails to parse now raises: the old
  `except Exception: continue` is gone. The `len(bars) >= 500` population
  filter and the sorted symbol order are unchanged.
- **Unchanged:** the four lines `WINDOW = 400`, `_full = …`, the
  `portfolio_module.mean_reversion_signal` patch and `_conv = {}` are
  byte-identical. They moved from lines 49–52 to 58–61.

**Equivalence without a backtest (confirmed).** The unmodified loader was run
through its old path (the scratchpad), then the new loader through the gate.
Both returned **230 symbols, 582,324 bars**, and an identical digest over
every parsed bar field (`09657e348fde19a2…`), with `WINDOW == 400` and the
patch active. Every importing runner therefore receives byte-identical input.
The loader's universe — `DEFAULT_UNIVERSE` excluding crypto, 230 symbols —
equals the dataset's file set exactly, so the new missing-file check changes
nothing for this dataset.

## 4. Dependency classification — confirmed, static analysis, no runner executed

The classes are those of this morning's preservation record (its §6 and
appendix), applied unchanged: **A** production-relevant, **B** governed
research runner, **C** historical / legacy, **D** ungoverned. The ledgers do
not cite scripts by filename, so the class is the record's own mechanical
rule — for example, "runs, analyses or audits a registered hypothesis". The
registration ledger holds 24 hypotheses; H-0022 is not among them.

### 4.1 The 29 importers of `forensics_regime`

Every one imports `load` from it, and **none carries a scratchpad lookup of
its own** (a search for `scratchpad`, `Temp` and `gettempdir` in all 29 finds
nothing). So every one now resolves decade data through the gate.

| class | count | scripts |
|---|---:|---|
| A production | 0 | — |
| **B governed** | **18** | `analyse_h0009`, `analyse_h0010`, `analyse_h0011`, `h0016_probe_cash`, `h0019_controls`, `h0019_measure`, `h0021_haircut`, `h0021_peaktiming`, `run_h0009`, `run_h0010`, `run_h0011`, `run_h0012`, `run_h0013`, `run_h0015`, `run_h0016`, `run_h0020`, `run_h0021`, `run_h0025` |
| C legacy | 0 | — |
| D ungoverned | 11 | `audit_sizing`, `copy_analyse`, `copy_build_cache`, `forensics_breadth`, `forensics_bucket_capacity`, `forensics_buckets`, `forensics_copy_sources`, `forensics_regime_stability`, `form4_feasibility`, `h0022_gain_recognition` (H-0022 was never registered), `probe_owner_params` |

*Correction to my own interim tally:* a working count earlier in this task put
this at 19 governed and 10 ungoverned. The registration ledger shows that is
wrong: `h0022_gain_recognition` is class D.

### 4.2 Class-B scripts still outside the gate — the remaining dependency

Class B has 42 scripts. The loader and its 18 importers are now gated, and
`register_h0017` has no lookup at all (its only mention of the scratchpad is
a descriptive string). **The other 22 still depend on the scratchpad:**

| how | count | scripts |
|---|---:|---|
| own lookup: first match of `…/scratchpad/deep` | 11 | `audit_h0003`, `h0005_descriptive_27`, `phase5_anatomy`, `phase5_candidates`, `phase5_filters`, `phase5_news_filter`, `run_h0005`, `run_h0006`, `run_h0007`, `run_h0008`, `run_sealed_exits` |
| own lookup: a scratchpad holding ≥ 200 `deep/*.csv` files (some then read only `raw/` or `snapshots/`) | 8 | `h0013_build_features`, `h0014_acquire_snapshots`, `h0014_analyse`, `h0014_validate`, `h0017_acquire`, `h0017_analyse`, `intraday_exits_acquire`, `run_h0014` |
| at import: `from h0014_analyse import …` runs that module's `SCR = scratch()` | 1 | `h0014_ic_yearly` |
| only through derived files: `data/phase5/anatomy-deep.jsonl`, `candidates-deep.jsonl` and `news-archive-deep.jsonl`, written by `phase5_anatomy` and `phase5_candidates`; no lookup of their own | 2 | `phase5_fetch_news`, `phase5_news_analysis` |

Two small corrections to earlier inventories, recorded rather than rewritten:

- The 2026-09-23 audit listed `phase5_fetch_news` and `phase5_news_analysis`
  as reading `deep` "direct path". They take the dataset *label* "deep" and
  read the derived files above. Those files exist today (gitignored, under
  `data/`), so the two scripts run without the scratchpad, but their inputs
  cannot be regenerated without it.
- The same audit listed `register_h0017` with a "temp glob". It has none.

**Inferred:** migrating their decade path alone would not make most of them
reproducible. Many also need the lost thirty-year data (`long/`) or the
unpreserved intraday stores (`snapshots/`, `raw/`). They are historical
runners of sealed hypotheses, and they matter only if those results are re-run.

### 4.3 Outside class B, for completeness

- **Class A (1), `build_training_seed`:** has its own lookup and built
  `data/big-dataset.jsonl`, the live learner's seed. The seed file's identity
  is pinned by hash in the learned-state snapshot (§9). The scheduled task
  never runs the script.
- **Class D, own lookups (7):** `attribute_entry_signal`, `decompose_timing`,
  `forensics_post_stop`, `intraday_exit_measure`, `intraday_probe`,
  `probe_holding_cap`, `regime_forensics`.
- **Class C:** 13 legacy scripts, several already unable to find their data.
- **Production:** confirmed none. `src/` has no reference to a scratchpad or
  to `gettempdir`. None of the six Python scripts that the PowerShell
  wrappers in `scripts/windows/` call has a scratchpad reference: `benchmark`,
  `preoos_interval_equivalence`, `record_news`, `run_crypto_sleeve`,
  `tradingview_levels` and `record_clean_session`.

## 5. Scratchpad fallback tests — confirmed

The real scratchpad was never altered. It was made unavailable **by
interception** in a separate process: every `open`, `glob`, `stat`, `listdir`
and `scandir` on a scratchpad path raised.

| test | result |
|---|---|
| positive: scratchpad unavailable, preserved dataset available | import and `load()` succeeded: **230 symbols, 582,324 bars**, **0 scratchpad access attempts**; resolved to `data/research/decade-2016-2026-split-adjusted-230` |
| 1 hash failure (a fixture with one byte flipped) | fatal — `DatasetGateError` |
| 2 missing file | fatal |
| 3 unexpected extra file | fatal |
| 4 wrong path | fatal |
| 5 registry redirected to a scratchpad path | fatal — refused as a temporary directory |
| 6 registry hash edited | fatal — the loader pins its own hash |
| 7 a file that does not parse | fatal — `ValueError`, not skipped |
| 8 a universe symbol absent from the resolved directory | fatal — `FileNotFoundError` |

Fixtures were built beside the preserved dataset under `data/research/`, never
under the temp directory, which the gate refuses and which would therefore
have "failed" for the wrong reason. All were deleted, and the governed copy
verified afterwards.

**The one blocked access** during the negative run was an `os.stat` inside
`Path.resolve()`, made by the gate's refusal check in test 5, on the
deliberately injected scratchpad path. That path does not exist, and no data
was read. `resolve()` is kept on purpose: it also catches a durable-looking
path that is really a symlink into the temp directory.

## 6. The 400-bar patch — provenance and preservation

| question | finding | label |
|---|---|---|
| where it is applied | at import of `scripts/forensics_regime.py`, lines 58–61, and in 20 other scripts that define it themselves; not in `src/` — the emulator passes full history | confirmed |
| what it does | the emulator's `mean_reversion_signal` sees `history[-400:]` | confirmed |
| which runners use it | every importer of `forensics_regime` (29) and every script defining it (21) — including every recorded reproduction of +58.5889% / 698 that could be traced | confirmed |
| does the loader change alter its input | **no.** Identical loaded bars (§3), and the patch lines are byte-identical | confirmed |
| rationale | **inferred**: speed. It was first committed on 2026-09-08 (`30a0125`, `thirty_year_test.py`) with no comment. The same day's `buckets.py` documents the cost it avoids: "The signal is O(n^2) per symbol" | inferred |
| effect on results | the already-recorded analytical argument — Wilder smoothing decays by 13/14 per bar — is the only evidence. **Untested**; not re-claimed here | unknown (empirically) |

## 7. Clean OOS methodology state

**Risk-free rate: CONFIRMED — the governing protocol fixes it. This corrects
earlier records.** The Phase 3 protocol, §1 "THE FROZEN CONFIGURATION"
(commit `7958f45`, 2026-09-15), reads: "Benchmark methodology: Phase 2,
unmodified — price-vs-price before 2016, total-vs-total after; strategy
dividends as cash, never reinvested; rf = 2.30%; 365.25-day annualisation."
The Phase 2 acceptance report (`docs/2026-09-16-phase2-acceptance-report.md`,
its methodology table and §6) defines that method in full:

| element | frozen convention |
|---|---|
| risk-free rate | **2.30%** — the "measured mean 3-month bill", "never 0" |
| Sharpe | daily returns; mean × 252; standard deviation × √252; excess over the 2.30% bill |
| Sortino | the same excess numerator; downside deviation against the daily bill rate |
| CAGR annualisation | 365.25 calendar days, both legs |
| dividends | strategy: credited as cash on the ex-date, not reinvested; SPY: reinvested total return |
| cash | the strategy's idle cash earns the actual bill rate |
| both legs | the same `metrics()` function |

Phase 2 derived 2.30% as the "measured mean 3-month bill over the window",
meaning its 1996–2026 historical window. Phase 3 then froze the resulting
**number**, 2.30%, for the forward evaluation (confirmed wording).
Substituting a bill rate realized inside the Clean OOS window would therefore
be a methodology change, which Phase 4 §5 forbids during the phase
(inferred).

The fingerprint's `risk_free: 0.0230` **is this declaration.** The
2026-09-23 reproducibility audit and the preservation record of this morning
(§8) called the rate "unsettled" or a decision still to make. **That was
wrong**: the decision was made on 2026-09-15.

What is genuinely missing is **implementation, not a decision**:

- no code consumes `risk_free`;
- `scripts/phase4_checkpoint.py` computes no Sharpe;
- the `metrics()` implementation the Phase 2 report names was **not
  committed**. Commit `173afad` contains only the report and ledger rows, and
  no such function was found in the repository or the scratchpad root. The
  scratchpad's own `benchmark.py` (2026-09-12) is an earlier price-only
  comparison. Where the Phase 2 code lives is **unknown**.

**Decision owner:** none needed for the rate. Implementing the frozen
methodology before checkpoint C is an engineering task, which must follow the
table above exactly.

The zero-rate Sharpe of the frozen *historical baseline* (0.5107) is a
research-emulator convention (`evaluation._ratio`), and it is not the Clean
OOS convention.

**Benchmark — confirmed.** Clean OOS is total return against total return: SPY
with `adjustment="all"` (`record_clean_session.py`; REM-0003); the fingerprint
declares `basis_post_2016 = total_vs_total`. The historical decade comparison
remains price-only against price-only. The two stay separate.

**Checkpoint — confirmed.** Phase 4 §6: A at 1, B at 20 (integrity only), **C
at 60 clean sessions** (the first descriptive performance report), D at 120.
Clean sessions are counted only in the recorder's clean record, which begins
after the 20-session embargo (projected 2026-10-12). **Sixty clean sessions,
not sixty sessions after 2026-09-11.**

## 8. `benchmark.py` — the holdout hazard, and the correction made

**How it worked before (confirmed):**

- `FORWARD_START = 2026-09-11`, from `research.py`;
- it read equity from the paper audit log from that date and fetched SPY
  (`adjustment="all"`);
- `forward_record(account, closes, FORWARD_START)` kept every common day on or
  after the start, and `sessions` counted all of them;
- `judgeable` meant `sessions >= MINIMUM_SESSIONS` (60), in
  `src/event_aware_trader/benchmark.py`;
- it used no risk-free rate: a plain excess return;
- its output went to stdout.

**Where it runs (newly confirmed):** `scripts/windows/session-run.ps1` runs
it **at every session close** of the live trading task and writes its output
to `data\BENCHMARK.txt` and the session log. From 2026-10-12 the scheduled
task itself would therefore have written holdout performance to a file daily,
with the 20 embargo sessions counted as forward sessions — an automatic early
look. The step is print-only and cannot affect a trade.

**The hazard, reproduced on synthetic data:** 21 embargo readings plus only 45
clean sessions gave `sessions = 66` and `judgeable = True`.

**The correction (the only change to this script):** the forward section now
takes its window and its count from the **Phase 4 clean record**
(`forward.load_sessions()` after `verify_chain()`).

- 0 clean sessions → a message, no data read.
- Fewer than 60 → the count only, no figure, and a pointer to checkpoint C.
- 60 or more → the unchanged comparison, over the clean window only.
- A broken chain → refused (`ForwardWindowRefused`).

`FORWARD_START` is no longer used. The IN-SAMPLE section is **byte-identical**
(it still prints pre-correction figures, as recorded earlier; untouched).
`src/` is unchanged.

**Tested on synthetic sessions**, with network and audit-log readers as
tripwires:

| case | result |
|---|---|
| the real clean record today (0 sessions) | nothing computed |
| 59 clean sessions | suppressed, nothing read |
| the 45-clean-session case above | suppressed |
| 60 clean sessions | window starts 2026-10-12, 60 sessions, embargo excluded, judgeable |
| broken chain | refused |

No tripwire fired. Run under the live session's interpreter today, it printed
"0 clean sessions recorded…" and nothing else in the forward section.

**Remaining (inferred):** from 60 clean sessions, the script's comparison is
the whole paper account, including the BTC sleeve, against SPY. The Phase 4
headline is the equity sleeve (REM-0005). That is a pre-existing difference of
basis, recorded here, not changed.

**Recorded, not changed (confirmed wording):** at 60 clean sessions the record
prints `src`'s pre-existing `judgeable` label. Phase 3 §8 still rules that
beating "the S&P 500 on return, Sharpe, Sortino or drawdown" does not count as
evidence "at any sample this phase can produce". At checkpoint C the
comparison is descriptive, and `judgeable` means only that the minimum sample
is met.

## 9. Learned-model state — the pre-Clean-OOS snapshot

Recorded in `docs/model-state/pre-clean-oos-2026-09-24.json` (read-only:
hashes, counts and timestamps; no labels or outcomes). Recorded at
2026-09-24T16:46:25Z; SHA-256 `f479d5074190b5c6…`. The trade examples'
information cutoff was added after the first write, and removing it
reproduces the first write's hash, `c9f7a4803464675d…`. **There are two
learned models, not one.**

| | live ranking model | trade veto model |
|---|---|---|
| file | `data/live-model.json` — SHA-256 `15c1ad0bb7b01754…` | `data/trade-model.json` — SHA-256 `a13ac28640b37cbe…` |
| status | **UNPROVEN**; `usable` **False**; not promoted; identity `8d9590dc0285d736` | **UNPROVEN**; `is_usable` **False** |
| last written | 2026-09-23T19:45:53Z | 2026-09-18T13:36:05Z (weekly, ISO week 2026-38) |
| training data | `data/live-training.jsonl` (1,537 rows, SHA-256 `71fb9a80d8a5649a…`) plus the seed `data/big-dataset.jsonl` (1,526 rows) — 3,063 examples | `data/trade-examples.jsonl` (26,425 rows), regenerated weekly from the live price cache |
| information cutoff | decision time (`at`) ≤ 2026-09-21T19:30Z; latest outcome recorded 2026-09-22T15:45:23Z | decision date (`as_of`) ≤ 2026-09-15T04:00Z; labels from the price cache as of the 2026-09-18 run |
| kill switch | `LEARNED_RANKING_ENABLED = False` | `LEARNED_VETO_ENABLED = False` |
| deployment rule | the flag **and** an explicit promotion record naming this exact model (`docs/model-promotions.jsonl`, absent). "A training process must never be able to promote its own output." A retrain changes the identity and cannot self-promote | the flag **and** `status == "USABLE_AS_VETO"` — a status **the trainer sets itself** from its own metrics (`trade_learning.py:362`). Only the flag prevents deployment |
| in the frozen fingerprint | **no** | **no** |

**Confirmed:** neither model can influence a trade today. The live ranker
cannot self-authorize. The trade model *can* label itself deployable on a
weekly retrain, but cannot veto while its flag is off. Neither switch is
fingerprinted, so a change to either would not make the recorder refuse a
session. Each is visible only as a change to `src/`.

## 10. Retrain audit — the learning loop, traced

**Live ranker:** closed trade → training example → retrain → model file.

1. Every closed position becomes a training example through
   `live_model.append_example`. A rule exit does so inside `run_once`
   (`autotrade.py:1821`), and an exit by a stop, a tool or the owner in
   `_learn_from_external_exits` (`autotrade.py:864`).
2. That appends a row to `data/live-training.jsonl` with `at` = the
   **decision time**, when the features were knowable, and `outcome_at`
   recorded separately.
3. A retrain then runs:
   - **in-cycle** (`_retrain_now`), logged to the audit log: 2026-09-14,
     09-15, 09-21 and 09-22;
   - **session close** (`session-run.ps1` → `cli retrain`, which adds the
     seed), logged **only to `data/session.log`**: **15 runs**,
     2026-09-03 … 2026-09-23 12:45:52 local (19:45:52Z).
4. The retrain writes `data/live-model.json` with status `UNPROVEN`.
5. Nothing reaches the model-lineage ledger.

**Trade model:** every Friday, `session-run.ps1` runs `cli learn`, which calls
`train_trade_model` and writes `data/trade-model.json` and
`tradingview/learned_filter.pine`. It is logged to `data/session.log` (3 runs;
last 2026-09-18).

**Correction, recorded rather than hidden.** The 2026-09-23 audit listed four
retrains (the audit log's). The preservation record this morning added "a
further retrain at 2026-09-23 19:45:53 UTC". Both were incomplete: session-close
retrains run **every session**, and the 19:45:53Z one is simply the latest. It
**is** recorded, in `data/session.log`, as "retraining on the record so far"
→ `"status": "retrained"`, `"model_status": "UNPROVEN"`. `docs/model-lineage.jsonl`
has 3 rows, the latest trained 2026-09-16; **no live retrain since then is
in the lineage ledger** (confirmed gap). No lineage row was appended by this
task: `ModelRecord` needs train, validate and test intervals, hyperparameters
and an evaluation that are not recorded for these retrains, and writing them
would be inference in a hash-chained ledger.

| requirement | finding |
|---|---|
| rows keyed by information time | **confirmed** — `at` is the decision time; `outcome_at` is separate |
| no Clean OOS outcome can enter training | **not met, by protocol design.** From 2026-10-12 every exit becomes a training example, and the weekly job reads holdout price bars. Both protocols require this as a correctness claim: "every exit produced a training example" (Phase 3 §8; Phase 4 §9). The learning loop must therefore **not** be disabled, and the isolation boundary is on deployment and evaluation instead (below) |
| information cutoff recorded | **in the snapshot**, for the pre-OOS models; not by the retrains themselves |
| retrain events auditable | **partially** — in-cycle in the audit log; session-close and weekly only in `data/session.log`; none in lineage |
| a retrain cannot silently become deployable | **confirmed for the live ranker.** For the trade model: the retrain *can* set `USABLE_AS_VETO`; only `LEARNED_VETO_ENABLED = False` blocks it |
| `LEARNED_RANKING_ENABLED = False` authoritative | **confirmed** — checked inside `usable`, the single property the live loop consults |

**The isolation boundary that must hold throughout Clean OOS:**

1. `LEARNED_RANKING_ENABLED` and `LEARNED_VETO_ENABLED` stay `False`, and
   every checkpoint verifies both.
2. Any model whose training rows include `at` on or after the first clean
   session, or trade examples or price bars from that date on, is
   holdout-exposed. It must never be evaluated on Clean OOS or treated as a
   pre-holdout model.
3. The pre-holdout reference is the snapshot above. A final snapshot at the
   last embargoed session (projected 2026-10-09) would bring it up to the
   boundary.

## 11. Scratchpad retirement criteria

| # | criterion | status |
|---|---|---|
| 1 | all decade-data consumers resolve through the verified dataset | **not met** — 22 governed scripts outside the gate (§4.2), plus class A, C and D scripts with their own lookups |
| 2 | no governed runner imports the scratchpad decade path | **not met** — 20 of the 22 locate it (19 themselves, 1 at import); the other 2 read files derived from it |
| 3 | the verified dataset passes its hash gate | **met** |
| 4 | the H-0013 / H-0014 / H-0017 intraday payloads preserved, or those experiments permanently treated as non-reproducible | **not met** — `raw/` 2.22 GB and `snapshots/` 3.03 GB are scratchpad-only; a separate task |
| 5 | no ungoverned import still requires the scratchpad | **not met** — class C and D scripts with their own lookups |
| 6 | a controlled failure test proves no fallback | **met for the shared loader** (§5) |
| 7 | removal has no impact on production | **met** — nothing in `src/` or the live scheduled scripts reads the scratchpad |

**Do not remove the scratchpad.**

## 12. Tests performed — infrastructure and governance only

| suite | result |
|---|---|
| dataset gate: valid dataset; flipped byte; missing file; wrong path; the real scratchpad path; eight registration forms (well-formed plus seven malformed) | **13 / 13** |
| loader: identical input through old and new paths; resolves with the scratchpad unavailable (0 access attempts); 8 fail-closed cases | **all pass** |
| Clean OOS guard (`benchmark.py`): 0 / 59 / 45-with-embargo / 60 clean sessions; broken chain; the live interpreter | **all pass**; no tripwire, no forward data, no result |
| learned model: both switches `False`; both models `UNPROVEN` and not usable; forged "usable" labels still not deployable | **6 / 6** |
| learned model: latest retrain represented | **2 of 4 records** — session log yes, snapshot yes; **lineage no, audit log no** (the gap in §10) |
| governance, re-checked after every edit: fingerprint `da22011e…`; clean record 0 sessions, chain intact; freeze 2026-09-11, embargo 20; the registration, remediation, model-lineage, experiment and phase-5 ledgers byte-identical to HEAD; dataset-uses 162 rows; `src/` and `tests/` 0 changes; both flags `False`; all five learned-state files still match the snapshot | **unchanged** |
| datasets, after every edit: the preserved copy and the scratchpad copy each 230 / 230 against the checksum list; `research_gate.py --audit` | **PASS** |
| knowledge base: rebuilt and validated (150 notes, 428 quotations, 32 code citations) | **PASS** |

## 13. Files changed

| file | change |
|---|---|
| `scripts/forensics_regime.py` | data path through the gate; fail-closed load (§3). Tracked; modified |
| `scripts/benchmark.py` | Clean OOS guard on the forward section (§8). Tracked; modified |
| `docs/model-state/pre-clean-oos-2026-09-24.json` | **new** — the learned-state snapshot |
| `docs/2026-09-24-research-loader-and-clean-oos-integrity-audit.md` | **new** — this report |
| `docs/2026-09-24-dataset-preservation-and-research-gate.md` | a dated correction block added under its header (§4.2, §7 and §10 here); the original text kept |
| `docs/datasets/decade-2016-2026.md`, `docs/datasets/README.md` | the loader status: gated, and what is not |
| `knowledge/` | notes updated from these facts; rebuilt and validated |

## 14. Files intentionally untouched

`src/`, including the emulator, `research.DATASETS`,
`event_aware_trader/benchmark.py`, `live_model.py` and `trade_learning.py`;
`tests/`; the preserved dataset files; the scratchpad; every ledger
(dataset-uses 162 rows, registrations 24, remediations 9, model lineage 3);
the manifests; the frozen fingerprint; the in-sample section of
`benchmark.py`; the 22 other governed runners; `tradingview/live-levels.pine`,
which the live session rewrites; and the pre-existing `docs/dataset-uses.jsonl`
row.

## 15. Remaining blockers

1. **22 governed scripts still depend on the scratchpad** (§4.2): 19 locate
   it themselves, 1 at import, and 2 read only files that scratchpad readers
   derived.
2. **The Clean OOS risk-adjusted metrics have no committed implementation.**
   The frozen method (rf 2.30%, ×252 / √252 excess, 365.25-day CAGR) must be
   implemented before checkpoint C.
3. **Retrains are not in the lineage ledger**, and session-close and weekly
   retrains are not in the audit log.
4. **Two unfingerprinted kill switches** guard holdout-exposed retraining
   models. The trade model can label itself deployable; only its flag stops
   it.
5. **The intraday payloads** of H-0013, H-0014 and H-0017 remain
   scratchpad-only.
