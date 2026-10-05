# Decade dataset preservation, and the research dataset gate

*2026-09-24. Follows the research reproducibility audit of 2026-09-23, which
this task treats as authoritative. Governance and provenance only: no economic
experiment, no backtest, no P&L, no Clean OOS read, no registration, no
dataset-use row. `src/`, `tests/`, the strategy, the emulator, the benchmark
and every historical result are unchanged.*

> **Corrections, added later on 2026-09-24.** The original text below is
> kept unchanged; these entries supersede it. Details are in
> [the loader and Clean OOS integrity audit](2026-09-24-research-loader-and-clean-oos-integrity-audit.md).
>
> 1. **§8 is wrong: the risk-free rate is not an open decision.** The Phase 3
>    protocol, §1 "THE FROZEN CONFIGURATION" (commit `7958f45`, 2026-09-15),
>    freezes "rf = 2.30%" as part of the Phase 2 benchmark methodology. The
>    Phase 2 acceptance report defines it as "never 0". What is missing is the
>    committed implementation, not the decision.
> 2. **§2 item 1 and §6 are superseded:** `scripts/forensics_regime.py` now
>    loads through `research_gate.verify_dataset`, and fails closed with no
>    scratchpad fallback. 22 other class-B scripts still depend on the
>    scratchpad.
> 3. **The retrain "at 2026-09-23 19:45:53 UTC" was not a one-off.** The live
>    ranking model is retrained at every session close (`session-run.ps1` →
>    `cli retrain`), logged only to `data/session.log`. That one is simply the
>    latest.
> 4. **Appendix:** `phase5_fetch_news` and `phase5_news_analysis` read
>    derived files in `data/phase5/`, not the scratchpad directly;
>    `register_h0017` has no temp-directory lookup.
> 5. **§6 and the appendix, class B — later still that day:**
>    - All 17 remaining class-B scripts that read decade data now load it
>      through the gate
>      ([migration record](2026-09-24-governed-research-dataset-migration.md)).
>    - The intraday stores stay scratchpad-only, now found by one
>      allow-listed lookup.
>    - The appendix's "can it find its data today?" column is superseded for
>      class B.
>    - One decade-derived file remains outside the gate: H-0014's daily-feature
>      cache in the scratchpad (migration record §14.1).
> 6. **§2 item 2, the intraday data — later still that day:**
>    - `raw/intraday-exits`, `raw/intraday-spy`, `snapshots/` and
>      `raw/h0017-micro` are preserved byte-identically and registered
>      ([intraday preservation](datasets/intraday-preservation-2026-09-24.md)).
>    - That is input data only; no experiment was re-run.
>    - The H-0014 feature cache that the correction above calls unverified
>      had by then been reproduced and registered
>      ([datasheet](datasets/h0014-daily-features.md)).

---

## 1. The decade dataset is preserved, byte-identical

| check | result |
|---|---|
| source verified before copying | 230 of 230 files match `docs/datasets/decade-2016-2026.sha256`; dataset hash `935fed79…73d4a7` |
| destination | `data/research/decade-2016-2026-split-adjusted-230/` (did not exist before; refused if it had) |
| copy method | `shutil.copy2` — bytes plus original modification times (2026-09-08 23:43:15–18 UTC), the acquisition-time provenance |
| copy verified | 230 files, no extra, none missing, no per-file mismatch; dataset hash `935fed79de9803f1da2a380c6f3f76ab525b27c5d14830bbea4744a7bf73d4a7` |
| independent re-verification | GNU `sha256sum -c` passes for all 230; the dataset hash, recomputed with coreutils (`stat` plus `sha256sum`) alone, is identical |
| content | 582,324 bars; every file ends 2026-09-04 |
| source after copying | re-verified identical; modification times unchanged |
| protection | copied files marked read-only |

**Durability.** No code path deletes or prunes `data/` subdirectories. The
only deletions found are `preoos_dry_run.py`'s own `mkdtemp()` directory and
three named crypto marker files. The location follows the repository's
convention for raw research data (`data/form4/raw/`, `data/phase5/`), so it is
**gitignored** (`/data/*`). It survives temp-directory clean-up but is **not
version-controlled and has no off-machine backup**. Whether to back it up —
Git LFS, an archive, or another disk — is the owner's decision. The tracked
checksum list makes any backup verifiable.

## 2. The scratchpad copy — NOT safe to remove yet

It was left intact, as instructed. Two reasons it must stay for now, neither
of which the verified copy removes:

1. **An import-time dependency.** `scripts/forensics_regime.py` resolves its
   data with `glob(".../scratchpad/deep", recursive=True)[0]` at **module
   level**. With no match that raises `IndexError`, so the module cannot even
   be imported. 29 scripts import it, including every runner H-0009 … H-0025
   and the baseline equivalence gate. Removing the scratchpad today would
   break all of them. No importer uses its `SCRATCH` variable directly, so the
   fix is confined to that one file (§6).
2. **Other data with no other copy.** The same scratchpad holds `raw/` (980
   files, 2.22 GB: `intraday-exits`, `intraday-spy`, `intraday-probe`,
   `h0017-micro`) and `snapshots/` (230 files, 3.03 GB). These are the only
   copies of the raw intraday payloads behind H-0013, H-0014 and H-0017, whose
   reports record them as scratchpad-only. This task preserved only the decade
   dataset.

## 3. CONF-10 — why paper results from 2026-09-11 are labelled "clean"

**Root cause.** `research.FORWARD_START = date(2026, 9, 11)` and
`DATASETS["forward"] = {"status": "clean", …}` arrived on **2026-09-13** in
commit `17a9c80` ("The research firewall: …"). The comment beside them defines
the term: "Everything the account records from here on is the only data no
experiment has seen". **"Clean" meant *unseen*.**

Two days later, on 2026-09-15, Phase 3 (`7958f45`) and P7/P8 (`dac3a1c`)
introduced the purge and embargo. In `purge.py`'s own words: "even a trade
opened entirely after the freeze can be tainted … so 20 sessions after the
freeze are set aside before the evaluation period begins". It also records
that the freeze date "independently coincides with `research.FORWARD_START`".
From then on, **clean meant *unseen and past the embargo***. The
`DATASETS` entry was never updated.

**Consequence: no contamination.** The Phase 4 recorder enforces the embargo,
and the dataset gate already refuses to score `forward` data for any purpose
except `forward_gate_evaluation`, recording each use. But anyone reading the
registry, and `scripts/benchmark.py`, uses the older meaning.

**Naming distinction, now in `docs/datasets/`** (`README.md`, `registry.json`):

| class | covers |
|---|---|
| **historical in-sample** | all research datasets |
| **paper operational** | everything the paper account records from 2026-09-11, including the 20 embargo sessions |
| **Clean OOS** | only recorder-accepted sessions, from `forward.first_clean_session()`, projected 2026-10-12 |

`research.DATASETS` itself is in `src/` and was **not** changed. Renaming or
splitting its `forward` entry is a separately approved change. Nothing
historical is reclassified as Clean OOS.

## 4. `scripts/benchmark.py` — the forward-performance hazard

**What it does.** It prints to the screen and writes nothing. Its FORWARD
section:

1. reads the paper account's daily equity from `data/autotrade-audit.jsonl`,
   from `FORWARD_START` (2026-09-11);
2. fetches SPY total return (`adjustment="all"`);
3. prints the excess return.

It never refers to the embargo, `first_clean_session()` or the Phase 4
checkpoints. Its "finding" threshold, `benchmark.MINIMUM_SESSIONS = 60` in
`src/event_aware_trader/benchmark.py`, counts sessions **from 2026-09-11**.

**The exact risk.** Run on or after 2026-10-12, it prints Clean OOS
performance **immediately** — mixed with the 20 embargo sessions and labelled
only "not a finding". It would call the record judgeable after about 40 clean
sessions, whereas Phase 4's first performance checkpoint (C) comes at 60
clean sessions and the protocol states that "A checkpoint below its threshold
is not produced".

It cannot contaminate the recorder's data. It *can* give someone an
unscheduled early look at the holdout — the failure the checkpoints exist to
prevent.

**Separately:** its IN-SAMPLE section prints hard-coded figures that predate
the 2026-09-16 emulator correction (for example "candidate + parked cash
9.87%"). They are not current.

**Smallest control — proposed, not implemented, methodology unchanged.** The
FORWARD section should end its window at the last embargoed session. Any
sessions on or after `forward.first_clean_session()` should be reported only
through `scripts/phase4_checkpoint.py` at its thresholds. That is a
few-line guard in one script. Until it exists, the rule is: **do not run
`benchmark.py` on or after 2026-10-12.**

## 5. The learning loop

**How it consumes outcomes** (`autotrade.py`, `live_model.py`):

1. Each live position closed by a stop, a tool or the owner becomes a
   training example appended to `data/live-training.jsonl`, dated by its
   **entry** (`decision_at`).
2. That triggers `_retrain_now`, a full refit.
3. Retrains also run at session close (`cli retrain`, whose seed defaults to
   `data/big-dataset.jsonl`) and weekly.

After 2026-10-12, every such example is a **holdout outcome**.

**Correction to the 2026-09-23 audit.** That audit listed the retrains the
audit log records: 2026-09-14, 09-15, 09-21 and 09-22. The model file,
`data/live-model.json`, shows a later retrain at **2026-09-23 19:45:53 UTC**
through a path the audit log does not record. The list was incomplete; that
report is left as written, and this is the correction.

**Can it contaminate the Clean OOS evaluation of the frozen strategy? Not
while the following holds.** A model can influence trading only if its status
is `USABLE`. That requires test AUC ≥ 0.53 **and**
`live_model.LEARNED_RANKING_ENABLED` (line 320); the flag is `False`, so every
retrain writes `UNPROVEN`. The current model is `UNPROVEN`.

The code's own docstring records that the model once *was* in the money path,
through candidate sorting. **`LEARNED_RANKING_ENABLED` is not covered by the
frozen fingerprint**: `config_digest` includes `live_model_floor` but not this
flag. So flipping it would not make the recorder refuse a session.

**The isolation boundary that must exist before Clean OOS begins.** This is a
specification; it is not implemented.

1. **`LEARNED_RANKING_ENABLED` stays `False` for the whole evaluation**, and
   every Phase 4 checkpoint verifies it. The pre-OOS audit already verified it
   off, and the checkpoints re-run the isolation suites.
2. **Any model trained on examples with `decision_at` on or after the first
   clean session is holdout-exposed.** It must never be evaluated on Clean OOS.
   The architecture to enforce this already exists: examples carry
   `decision_at`, and `purge.py` classifies observations as `pre_freeze`,
   `straddling`, `embargoed` or `clean`.
3. **A pre-holdout snapshot is needed if the model is ever to be evaluated.**
   Hash-record `data/live-training.jsonl` and `data/live-model.json` as of the
   last embargoed session, since the model-lineage ledger has no row for any
   live retrain after 2026-09-16.

## 6. The 74 scratchpad-dependent scripts, classified

The rules are mechanical, and every row is in the table at the end.

| class | count | rule |
|---|---:|---|
| **A** production-relevant | 1 | feeds the live system: `build_training_seed.py` (the learner's default seed) |
| **B** research-runner relevant | 42 | runs, analyses or audits a *registered* hypothesis; writes phase-5 ledger rows; or is the shared loader they depend on |
| **C** historical / legacy | 13 | experiment scripts of the pre-registration ledger era (up to 2026-09-15) |
| **D** irrelevant to governed research | 18 | unregistered forensics, feasibility and probes — including H-0022, which was never registered |

**The minimum set that must be corrected before a *future* governed experiment
can run reproducibly: one file, `scripts/forensics_regime.py`.** It is the
only loader shared by the registration-era runners, and it carries all three
hazards that bear on new work:

- the temp-directory glob, first match;
- the import-time failure of §2;
- the silent `except …: continue` skip in `load()`.

The correction is **proposed, not made**:

- resolve the data path through
  `research_gate.verify_dataset("decade-2016-2026-split-adjusted-230")`;
- make a load error fatal;
- leave the 400-bar window exactly as it is (§7).

New runners should call the gate directly.

**Reproducing *historical* results** would additionally need the other B
loaders corrected — `run_h0005` … `run_h0008`, `run_sealed_exits`,
`phase5_*`, `audit_h0003`, `h0005_descriptive_27`, and the ≥ 200-file
`_scratch()` helpers of H-0013, H-0014 and H-0017. H-0013, H-0014 and H-0017
also need their unpreserved intraday stores (§2). Classes C and D do not block
governed research. Eight C scripts cannot run as committed.

## 7. The 400-bar signal window

| question | answer |
|---|---|
| where | `WINDOW = 400` and `portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-WINDOW:], c)` in 21 scripts, including `scripts/forensics_regime.py`, and so in everything that imports it. **Not in `src/`**; the emulator itself passes full history (`portfolio.py`: `mean_reversion_signal(symbol, history[symbol], mr_cfg)`) |
| origin | first committed 2026-09-08 in `scripts/thirty_year_test.py` (`30a0125`), with no explanatory comment |
| why | **inferred** as speed. The same day's `buckets.py` documents the cost: "The signal is O(n^2) per symbol - every bar rebuilds the close list and re-smooths RSI and ATR from the start of the series", about half an hour per decade run. The thirty-year run has roughly 7,500 bars a symbol |
| which baseline runs used it | **every recorded reproduction of +58.5889% / 698 that could be traced.** The phase-5 scripts that first wrote `baseline_metrics` (`phase5_filters.py` among them), `run_sealed_exits.py`, `run_h0005` … `run_h0008`, and every importer of `forensics_regime` (`run_h0009` … `run_h0025`). No record of the baseline computed without it was found |
| evidence that the effect is negligible | **analytical, not empirical.** RSI(14) and ATR(14) use Wilder smoothing (`indicators.rsi`, `indicators.wilder_atr`), whose starting value's influence decays by 13/14 per bar — about 4×10⁻¹³ after the roughly 386 bars the window leaves. The 200-day average, conviction (40 bars), dollar volume (20 bars) and `minimum_history` (215) all look back less than 400 |
| must future reproduction preserve it? | **Yes.** The +58.5889000000% figure, to ten decimals, was produced with it. Whether the equivalence gate (tolerance 5×10⁻⁷) would pass without it is analytically expected but **unverified** — testing it needs a baseline rerun, which is prohibited here |

## 8. The Clean OOS risk-free rate — a decision to make before 2026-10-12

| source | convention |
|---|---|
| frozen baseline Sharpe 0.5107 | 0 (`evaluation._ratio`) |
| `stats.sharpe_ratio` default | 0 |
| EXP-0038, `benchmark.py`'s risk-adjusted table | the 3-month bill — "2.30% mean 1996-2026" (2.25% for 2016–2026) |
| frozen fingerprint | declares `risk_free: 0.0230` inside the benchmark block — **no code consumes it** |
| `scripts/phase4_checkpoint.py` | computes no Sharpe |
| available series | `data/tbill.csv` (tracked) — the daily 3-month bill rate |

**The decision.** Which risk-free convention will Clean OOS risk-adjusted
metrics use — 0, the declared constant 0.0230, or the realized bill rate over
the evaluation window — and will SPY's figures use the same?

**It must be recorded before any Clean OOS outcome exists**, which in practice
means before 2026-10-12, because:

- Phase 4 §5 prohibits changing benchmark methodology during the phase;
- the declared rate sits **inside the frozen fingerprint**, so changing that
  constant would move the fingerprint and the recorder would refuse sessions.

No rate is chosen here. The first report that requires the decision is
checkpoint C, at 60 clean sessions.

## 9. Clean OOS — untouched

| item | status |
|---|---|
| clean sessions | **0**; chain intact; `data/forward-evaluation.jsonl` does not exist |
| research freeze | **2026-09-11** (`purge.freeze_date`) |
| embargo | 20 sessions; 8 elapsed on 2026-09-23 (the recorder's latest output) |
| planned start | **2026-10-12, projected**, resolved at run time by `forward.first_clean_session()` |
| holdout data consumed | **none** — no holdout session has occurred; the preserved dataset ends 2026-09-04 |
| READY? | **not declared.** Preserving the dataset does not make Clean OOS ready; §4, §5 and §8 are open |

## 10. Governance changes made by this task

| file | change |
|---|---|
| `data/research/decade-2016-2026-split-adjusted-230/` | **new** — the preserved dataset (gitignored) |
| `docs/datasets/registry.json` | **new** — dataset identities, the rule, the three evidence classes |
| `docs/datasets/README.md` | **new** — the rule, the evidence classes, what is not covered |
| `docs/datasets/decade-2016-2026.md` | **new** — the datasheet, including the four quality warnings |
| `docs/datasets/thirty-year-1996-2026.md` | **new** — the lost-dataset record, its dependent results and the reacquisition requirements |
| `scripts/research_gate.py` | **new** — `verify_dataset`, `check_registration` and `audit`. Negative-tested on throwaway copies: a flipped byte, a missing file, an extra file, a wrong dataset hash, a lost dataset, an unknown ID, a mismatched requested hash, a temporary-directory path and missing registration fields were all refused |
| `docs/datasets/decade-2016-2026.manifest.json`, `.sha256` | **unchanged** since 2026-09-23 |

The knowledge base was updated from these sources and rebuilt.

---

## Appendix — classification of the 74 scripts
| class | script | store | why this class | can it find its data today? |
|---|---|---|---|---|
| A | `build_training_seed.py` | deep/long | builds data/big-dataset.jsonl, the default seed of the live learner (`cli retrain --seed`) | decade mode only - thirty-year absent |
| B | `analyse_h0009.py` | deep | runs, analyses or audits registered hypothesis H-0009 | yes, while the scratchpad copy exists |
| B | `analyse_h0010.py` | deep | runs, analyses or audits registered hypothesis H-0010 | yes, while the scratchpad copy exists |
| B | `analyse_h0011.py` | deep | runs, analyses or audits registered hypothesis H-0011 | yes, while the scratchpad copy exists |
| B | `audit_h0003.py` | deep/long | runs, analyses or audits registered hypothesis H-0003 | decade mode only - thirty-year absent |
| B | `forensics_regime.py` | deep | shared loader imported by 29 scripts, including every runner H-0009 … H-0025 | yes, while the scratchpad copy exists |
| B | `h0005_descriptive_27.py` | deep | runs, analyses or audits registered hypothesis H-0005 | yes, while the scratchpad copy exists |
| B | `h0013_build_features.py` | deep | runs, analyses or audits registered hypothesis H-0013 | yes, while the scratchpad copy exists |
| B | `h0014_acquire_snapshots.py` | deep/snapshots | runs, analyses or audits registered hypothesis H-0014 | yes, while the scratchpad copy exists |
| B | `h0014_analyse.py` | deep/snapshots | runs, analyses or audits registered hypothesis H-0014 | yes, while the scratchpad copy exists |
| B | `h0014_ic_yearly.py` | deep/snapshots | runs, analyses or audits registered hypothesis H-0014 | yes, while the scratchpad copy exists |
| B | `h0014_validate.py` | deep/snapshots | runs, analyses or audits registered hypothesis H-0014 | yes, while the scratchpad copy exists |
| B | `h0016_probe_cash.py` | deep | runs, analyses or audits registered hypothesis H-0016 | yes, while the scratchpad copy exists |
| B | `h0017_acquire.py` | deep | runs, analyses or audits registered hypothesis H-0017 | yes, while the scratchpad copy exists |
| B | `h0017_analyse.py` | deep | runs, analyses or audits registered hypothesis H-0017 | yes, while the scratchpad copy exists |
| B | `h0019_controls.py` | deep | runs, analyses or audits registered hypothesis H-0019 | yes, while the scratchpad copy exists |
| B | `h0019_measure.py` | deep | runs, analyses or audits registered hypothesis H-0019 | yes, while the scratchpad copy exists |
| B | `h0021_haircut.py` | deep | runs, analyses or audits registered hypothesis H-0021 | yes, while the scratchpad copy exists |
| B | `h0021_peaktiming.py` | deep | runs, analyses or audits registered hypothesis H-0021 | yes, while the scratchpad copy exists |
| B | `intraday_exits_acquire.py` | deep | acquired the raw intraday payloads H-0013 uses | yes, while the scratchpad copy exists |
| B | `phase5_anatomy.py` | deep/long | writes or feeds phase-5 ledger rows | decade mode only - thirty-year absent |
| B | `phase5_candidates.py` | deep/long | writes or feeds phase-5 ledger rows | decade mode only - thirty-year absent |
| B | `phase5_fetch_news.py` | deep | writes or feeds phase-5 ledger rows | yes, while the scratchpad copy exists |
| B | `phase5_filters.py` | deep/long | writes or feeds phase-5 ledger rows | decade mode only - thirty-year absent |
| B | `phase5_news_analysis.py` | deep | writes or feeds phase-5 ledger rows | yes, while the scratchpad copy exists |
| B | `phase5_news_filter.py` | deep/long | writes or feeds phase-5 ledger rows | decade mode only - thirty-year absent |
| B | `register_h0017.py` |  | runs, analyses or audits registered hypothesis H-0017 | yes, while the scratchpad copy exists |
| B | `run_h0005.py` | deep | runs, analyses or audits registered hypothesis H-0005 | yes, while the scratchpad copy exists |
| B | `run_h0006.py` | deep | runs, analyses or audits registered hypothesis H-0006 | yes, while the scratchpad copy exists |
| B | `run_h0007.py` | deep/long | runs, analyses or audits registered hypothesis H-0007 | decade mode only - thirty-year absent |
| B | `run_h0008.py` | deep | runs, analyses or audits registered hypothesis H-0008 | yes, while the scratchpad copy exists |
| B | `run_h0009.py` | deep | runs, analyses or audits registered hypothesis H-0009 | yes, while the scratchpad copy exists |
| B | `run_h0010.py` | deep | runs, analyses or audits registered hypothesis H-0010 | yes, while the scratchpad copy exists |
| B | `run_h0011.py` | deep | runs, analyses or audits registered hypothesis H-0011 | yes, while the scratchpad copy exists |
| B | `run_h0012.py` | deep | runs, analyses or audits registered hypothesis H-0012 | yes, while the scratchpad copy exists |
| B | `run_h0013.py` | deep | runs, analyses or audits registered hypothesis H-0013 | yes, while the scratchpad copy exists |
| B | `run_h0014.py` | deep/snapshots | runs, analyses or audits registered hypothesis H-0014 | yes, while the scratchpad copy exists |
| B | `run_h0015.py` | deep | runs, analyses or audits registered hypothesis H-0015 | yes, while the scratchpad copy exists |
| B | `run_h0016.py` | deep | runs, analyses or audits registered hypothesis H-0016 | yes, while the scratchpad copy exists |
| B | `run_h0020.py` | deep | runs, analyses or audits registered hypothesis H-0020 | yes, while the scratchpad copy exists |
| B | `run_h0021.py` | deep | runs, analyses or audits registered hypothesis H-0021 | yes, while the scratchpad copy exists |
| B | `run_h0025.py` | deep | runs, analyses or audits registered hypothesis H-0025 | yes, while the scratchpad copy exists |
| B | `run_sealed_exits.py` | deep/long | writes or feeds phase-5 ledger rows | decade mode only - thirty-year absent |
| C | `buckets.py` | deep | pre-registration experiment script (ledger era up to 2026-09-15) | NO - scripts/deep does not exist |
| C | `entry_latency_test.py` | deep | pre-registration experiment script (ledger era up to 2026-09-15) | NO - scripts/deep does not exist |
| C | `exposure_levers_test.py` | deep/long | pre-registration experiment script (ledger era up to 2026-09-15) | decade mode only - thirty-year absent |
| C | `invert_signal_test.py` | deep | pre-registration experiment script (ledger era up to 2026-09-15) | NO - scripts/deep does not exist |
| C | `overnight_control_test.py` | deep | pre-registration experiment script (ledger era up to 2026-09-15) | NO - scripts/deep does not exist |
| C | `overnight_decomposition.py` | deep | pre-registration experiment script (ledger era up to 2026-09-15) | NO - scripts/deep does not exist |
| C | `overnight_persistence_test.py` | deep | pre-registration experiment script (ledger era up to 2026-09-15) | NO - scripts/deep does not exist |
| C | `retune_sweep.py` | deep | pre-registration experiment script (ledger era up to 2026-09-15) | NO - scripts/deep does not exist |
| C | `short_book_sim.py` | deep/long | pre-registration experiment script (ledger era up to 2026-09-15) | decade mode only - thirty-year absent |
| C | `short_mirror_test.py` | deep | pre-registration experiment script (ledger era up to 2026-09-15) | NO - scripts/deep does not exist |
| C | `stop_check.py` | deep/long | pre-registration experiment script (ledger era up to 2026-09-15) | decade mode only - thirty-year absent |
| C | `thirty_year_test.py` | long | pre-registration experiment script (ledger era up to 2026-09-15) | NO - thirty-year data absent |
| C | `trend_filter_test.py` | deep/long | pre-registration experiment script (ledger era up to 2026-09-15) | decade mode only - thirty-year absent |
| D | `attribute_entry_signal.py` | deep | unregistered analysis, forensics, feasibility or probe | yes, while the scratchpad copy exists |
| D | `audit_sizing.py` | deep | unregistered analysis, forensics, feasibility or probe | yes, while the scratchpad copy exists |
| D | `copy_analyse.py` | deep | unregistered analysis, forensics, feasibility or probe | yes, while the scratchpad copy exists |
| D | `copy_build_cache.py` | deep | unregistered analysis, forensics, feasibility or probe | yes, while the scratchpad copy exists |
| D | `decompose_timing.py` | deep | unregistered analysis, forensics, feasibility or probe | yes, while the scratchpad copy exists |
| D | `forensics_breadth.py` | deep | unregistered analysis, forensics, feasibility or probe | yes, while the scratchpad copy exists |
| D | `forensics_bucket_capacity.py` | deep | unregistered analysis, forensics, feasibility or probe | yes, while the scratchpad copy exists |
| D | `forensics_buckets.py` | deep | unregistered analysis, forensics, feasibility or probe | yes, while the scratchpad copy exists |
| D | `forensics_copy_sources.py` | deep | unregistered analysis, forensics, feasibility or probe | yes, while the scratchpad copy exists |
| D | `forensics_post_stop.py` | deep | unregistered analysis, forensics, feasibility or probe | yes, while the scratchpad copy exists |
| D | `forensics_regime_stability.py` | deep | unregistered analysis, forensics, feasibility or probe | yes, while the scratchpad copy exists |
| D | `form4_feasibility.py` | deep | unregistered analysis, forensics, feasibility or probe | yes, while the scratchpad copy exists |
| D | `h0022_gain_recognition.py` | deep | H-0022 was never registered | yes, while the scratchpad copy exists |
| D | `intraday_exit_measure.py` | deep | unregistered analysis, forensics, feasibility or probe | yes, while the scratchpad copy exists |
| D | `intraday_probe.py` | deep | unregistered analysis, forensics, feasibility or probe | yes, while the scratchpad copy exists |
| D | `probe_holding_cap.py` | deep | unregistered analysis, forensics, feasibility or probe | yes, while the scratchpad copy exists |
| D | `probe_owner_params.py` | deep | unregistered analysis, forensics, feasibility or probe | yes, while the scratchpad copy exists |
| D | `regime_forensics.py` | deep | unregistered analysis, forensics, feasibility or probe | yes, while the scratchpad copy exists |
