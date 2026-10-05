# Governed research dataset migration

*2026-09-24. Research-infrastructure and governance only. No backtest, no
experiment run or registered, no hypothesis ID used, no economic figure
computed, no Clean OOS read, no model trained, promoted or evaluated, no
strategy, parameter, emulator, execution-model or benchmark change, nothing in
`src/` or `tests/` touched, nothing deleted from the scratchpad. Labels:
**confirmed** — verified mechanically in this task; **inferred** — reasoned
from repository evidence; **unknown** — not established.*

---

> **Update, later on 2026-09-24 — the §14.1 gap is closed.**
>
> - **The check:** the H-0014 daily-feature cache was recomputed in memory by
>   the committed `build_daily_cache` (`90dc4bd`) from the verified decade
>   dataset. The bytes match exactly (SHA-256 `b653ac1f…4030`), with 0 of
>   3,190,344 values different, and no write was made.
> - **The copy:** the cache is registered as `h0014-daily-features-decade-230`
>   and copied, verified, to `data/research/`.
> - **The pointer:** `h0014_analyse` now reads that copy, verified at import
>   and fail-closed, and never reads the scratchpad original — which is kept,
>   untouched.
> - **Evidence:** [the datasheet](datasets/h0014-daily-features.md).
>
> Every condition of the task's rule A now holds, so **the decade research
> path is fully gated (A)**. Clean OOS is untouched. The intraday stores of §6
> remain scratchpad-only and unresolved. Class A and class D scripts outside
> governed research still read the scratchpad's decade copy. The text below is
> kept as written.
>
> **Update, later still — §6 and §14.2.** The four intraday stores of §6
> (`raw/intraday-exits`, `raw/intraday-spy`, `snapshots/`, `raw/h0017-micro`) are
> now preserved byte-identically, read-only and registered — [intraday preservation](datasets/intraday-preservation-2026-09-24.md).
> Input data is preserved; no experiment was re-run. The runners still read
> the scratchpad originals.
>
> Still unpreserved:
>
> - H-0014's raw 5-minute bars, which were never written to disk;
> - H-0008's `intraday_cache/`.

## §17 Final classification: **B — decade research path still partially gated**

**Every governed decade *OHLCV* read now goes through the verified dataset
gate (confirmed).** That covers 17 migrated scripts, plus `forensics_regime.py`
and its 29 importers, gated earlier today.

- Each read is pinned to `decade-2016-2026-split-adjusted-230` /
  `935fed79…73d4a7`.
- It fails closed, and has no scratchpad fallback.
- Import-time decade access is gated.
- The input is structurally identical to what each script read before.

**B is not given for the intraday stores.** The rule excludes them, and they
are listed in §6.

**Why A is not claimed.** One governed decade-data path still reaches an
unverified decade-derived file in the scratchpad (§14.1):

- H-0014's sealed analysis body, `h0014_analyse.build_daily_cache()`, reads
  daily features derived from decade prices, cached at
  `…/scratchpad/h0014-daily-features.json` (written 2026-09-20 23:30).
- It prefers that cache to recomputing from the verified data.
- `h0014_ic_yearly` imports and calls the same function.

The cache was **not** bypassed. Its code was first committed 13 minutes after
the cache was written, so the committed code cannot be shown to have produced
it. Recomputing would therefore not be provably semantics-preserving. §5 of
the task requires such a case to be classified unresolved, not forced.

---

## §1 Scope

**Changed:**
- **Data path:** only the path-resolution layer of 20 governed research
  scripts.
- **One shared helper:** added to `scripts/research_gate.py`, where the gate
  also gained a check that a dataset lies under the research data root.
- **Documentation:** records made stale by the migration.

**Not changed:** `src/`, `tests/`, the preserved dataset, the scratchpad, every
ledger, the fingerprint, every derived file, every downstream computation, and
the 400-bar window.

**Not done:**
- no backtest, historical run or research computation;
- no P&L, CAGR, Sharpe or drawdown;
- no Clean OOS or forward read;
- no model action;
- no reacquisition or migration of intraday data.

## §2 Governance state — confirmed, before any change and again after

| item | before | after |
|---|---|---|
| baseline (`baseline_metrics`, P5-0001 and P5-0038) | total_return 0.585889, trades 698 | unchanged (ledger byte-identical to HEAD) |
| dataset-use ledger | 162 rows | 162 rows |
| frozen fingerprint | `da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b` | same |
| Clean OOS | 0 sessions, chain intact, `data/forward-evaluation.jsonl` absent | same |
| freeze / embargo | 2026-09-11 / 20 sessions | same |
| planned Clean OOS start | 2026-10-12, projected (Phase 4 §1) | same |
| `LEARNED_RANKING_ENABLED` / `LEARNED_VETO_ENABLED` | False / False | False / False |
| registrations / remediations / lineage / experiments / phase-5 rows | 24 / 9 / 3 / 53 / 39 | byte-identical to HEAD |
| `src/`, `tests/` | 0 changes | 0 changes |

## §3 Starting inventory

The 22 class-B scripts that the loader audit
([2026-09-24](2026-09-24-research-loader-and-clean-oos-integrity-audit.md) §4.2)
left outside the gate:

- **19 with their own lookup:**
  - **11 first-match `…/scratchpad/deep` globs:** `audit_h0003`,
    `h0005_descriptive_27`, `phase5_anatomy`, `phase5_candidates`,
    `phase5_filters`, `phase5_news_filter`, `run_h0005`, `run_h0006`,
    `run_h0007`, `run_h0008`, `run_sealed_exits`.
  - **8 "a scratchpad holding ≥ 200 `deep/*.csv`" lookups:**
    `h0013_build_features`, `h0014_acquire_snapshots`, `h0014_analyse`,
    `h0014_validate`, `h0017_acquire`, `h0017_analyse`,
    `intraday_exits_acquire`, `run_h0014`.
- **1 via import:** `h0014_ic_yearly`.
- **2 via derived files:** `phase5_fetch_news`, `phase5_news_analysis`.

## §4 Reconciled dependency graph — confirmed by a mechanical rescan

The rescan covers every Python file in the repository, tracked and untracked,
and confirmed the same 22. It also found two dependencies the inventory had
not recorded:

- `run_h0008` also reads an intraday store, `intraday_cache/`, which exists in
  no scratchpad.
- `h0014_analyse` and `h0014_ic_yearly` also read the derived feature cache
  (§14.1).

**Categories.** A = decade dependency, migrated. B = intraday dependency,
retained. C = derived-file dependency, traced.

| script | programme | decade input | intraday input | derived input | category | migrated here |
|---|---|---|---|---|---|---|
| `audit_h0003` | H-0003 audit | `load()` over the universe | — | — | A | yes |
| `h0005_descriptive_27` | H-0005 | `load()` | — | — | A | yes |
| `run_h0005` | H-0005 | `load()` | — | — | A | yes |
| `run_h0006` | H-0006 | `load()` | — | — | A | yes |
| `run_h0007` | H-0007 | `load(folder)` — `deep` or the lost `long` | — | — | A | yes |
| `run_sealed_exits` | H-0001 … H-0004 sealed exits, phase 5 | `load(folder)` | — | — | A | yes |
| `phase5_anatomy` | phase 5 | `load(folder)` | — | writes `data/phase5/anatomy-deep.jsonl` | A | yes |
| `phase5_candidates` | phase 5 | inline in `main()` | — | writes `candidates-deep.jsonl` | A | yes |
| `phase5_filters` | phase 5 | `load(folder)` | — | — | A | yes |
| `phase5_news_filter` | phase 5 | `load(folder)` | — | reads `news-archive-deep.jsonl`, `news-windows-deep.txt` | A + C | yes (decade) |
| `run_h0008` | H-0008 | `load_daily()` | `intraday_cache/` — **absent everywhere** | — | A + B | decade yes; intraday retained |
| `h0013_build_features` | H-0013 | `DEEP/<sym>.csv` via `csv.DictReader` | `raw/intraday-exits`, `raw/intraday-spy` | `docs/phase5/h0011-cache.json` (tracked) | A + B + C | decade yes; intraday retained |
| `h0014_acquire_snapshots` | H-0014 | `DEEP` (listing and CSVs) | `snapshots/` (writes), `raw/intraday-spy` | — | A + B | decade yes; intraday retained |
| `h0014_analyse` | H-0014 sealed body | `DEEP` | `snapshots/` | **`h0014-daily-features.json`, scratchpad, unverified** | A + B + C | decade yes; intraday and cache retained |
| `h0014_validate` | H-0014 | `deep` in `main()` | `snapshots/` | — | A + B | decade yes; intraday retained |
| `run_h0014` | H-0014 | `DEEP` | `snapshots/` | — | A + B | decade yes; intraday retained |
| `h0014_ic_yearly` | H-0014 | `DEEP` via `h0014_analyse` | `snapshots/` via `h0014_analyse` | the same cache, via `build_daily_cache()` | A + B + C | decade yes, through `h0014_analyse` |
| `h0017_acquire` | H-0017 | **none** — the old lookup only used decade files as a marker | `raw/h0017-micro` | `docs/phase5/h0017-targets.json` | B | locator re-keyed |
| `h0017_analyse` | H-0017 | none | `raw/h0017-micro` | — | B | locator re-keyed |
| `intraday_exits_acquire` | acquisition of the rule-exit sessions H-0013 uses | none | `raw/intraday-exits` | `docs/phase5/h0011-cache.json` | B | locator re-keyed |
| `phase5_fetch_news` | phase 5 | none | — | `anatomy-deep.jsonl` or `candidates-deep.jsonl`; writes the news archive | C | no — nothing to migrate |
| `phase5_news_analysis` | phase 5 | none | — | `anatomy-deep.jsonl`, `news-archive-deep.jsonl` | C | no — nothing to migrate |

**Counts, confirmed:**
- **17 scripts read decade data; all 17 migrated.** 10 are decade-only and 7
  mix decade with intraday.
- **3 are intraday-only.** Their locator no longer depends on decade files.
- **2 are derived-file only.**
- **Class B as a whole (42):** 36 read decade data only through the gate (the
  loader, its 18 governed importers and these 17), 3 are intraday-only, 2
  derived-only, and `register_h0017` has no lookup.

## §5 Decade-data migrations — the exact path-resolution change

**Shared helper, reusing `verify_dataset`** — `scripts/research_gate.py`:

| function | behaviour |
|---|---|
| `price_dir(folder)` | `"deep"` → `verify_dataset(DECADE, DECADE_SHA256)`: exact file set, every SHA-256, dataset hash pinned in code (so an edited registry is caught too), path durable and under `data/research/`. `"long"` → the lost thirty-year dataset: **always refused**. Any other label is refused. Verifies on every call; no fallback, no cache. |
| `decade_dir()` | `price_dir("deep")` |
| `dataset_file(dir, name)` | a file of the verified directory; raises if it is absent or would resolve outside it |
| `verify_dataset` (strengthened) | now also refuses a registered path outside `data/research/`, including through `..` |

**Loader rules** — each loader was read individually. Every group:
- keeps its ordering (the sorted non-crypto universe, or `sorted(DEEP.glob)`);
- keeps its population filter (`>= 500`, or `>= 400` with `since`), the
  400-bar lines, the file naming (`<SYMBOL>.csv`), and its parser (`load_bars`
  or `csv.DictReader`);
- uses the split-adjusted, not dividend-adjusted, data it used before.

| group | before | after |
|---|---|---|
| `load(folder, since, minimum)` — `audit_h0003`, `run_h0007`, `run_sealed_exits`, `phase5_anatomy`, `phase5_filters`, `phase5_news_filter` | module-level `SCRATCH = Path(glob.glob(".../scratchpad/deep", recursive=True)[0]).parent`; `SCRATCH / folder / sym.csv`; missing → `continue`; `load_bars` error → `continue` | `base = price_dir(folder)` inside `load()`, before the loop; `load_bars(dataset_file(base, sym + ".csv"))`; missing or malformed **raises** |
| `load()` with `"deep"` — `run_h0005`, `h0005_descriptive_27`, `run_h0006`, `run_h0008` (`load_daily`) | the same glob; two nesting styles of the same silent skips | `base = price_dir("deep")`; the same single line |
| inline in `main()` — `phase5_candidates` | the same glob; skips inline | `base = price_dir(spec["folder"])` right after `spec` is chosen, before any computation; the same single line |
| directory users — `h0013_build_features`, `h0014_acquire_snapshots`, `h0014_analyse`, `run_h0014` (module level), `h0014_validate` (in `main()`), `h0014_ic_yearly` (via import) | `DEEP = <scratchpad with ≥ 200 deep CSVs> / "deep"`, with a first-match fallback across scratchpads | `DEEP = decade_dir()`, verified at import; `h0014_validate` verifies in `main()` |

**Consequences for the lost thirty-year dataset:**
- `long` modes (`audit_h0003`, `run_h0007`, `run_sealed_exits`, phase 5) now
  fail immediately.
- Before, they resolved `SCRATCH/long`, which does not exist, skipped every
  symbol and continued with empty data.

**Row-level parsing is unchanged.** `event_aware_trader.data.load_bars` drops
unusable rows inside `src/`, which this task may not touch. The file-level
silent skips were all in the scripts, and all are removed.

## §6 Intraday exceptions — UNPRESERVED, scratchpad-only, NOT restored

The decade gate does nothing for these, and **no intraday result is
reproducible without the scratchpad.**

**How they are found now:**
- One allow-listed function, `research_gate.unpreserved_intraday_store(relpath)`.
- It is keyed on the intraday store itself, so the scratchpad's decade copy
  is no longer a marker, and `"deep"` is not on its list.
- It refuses unless exactly one scratchpad holds the store.
- It verifies nothing.

**The resolved paths are identical to before (§9):**

| store | programme | files on 2026-09-24 | used by |
|---|---|---:|---|
| `raw/intraday-exits` | H-0011 rule-exit sessions → H-0013 features | 698 | `intraday_exits_acquire` (writes), `h0013_build_features` |
| `raw/intraday-spy` | SPY 5-minute bars | 43 | `h0013_build_features`, `h0014_acquire_snapshots` |
| `raw/h0017-micro` | H-0017 trade and quote payloads | 221 | `h0017_acquire` (writes), `h0017_analyse` |
| `snapshots/` | H-0014 intraday snapshots | 230 | `h0014_acquire_snapshots` (writes), `h0014_analyse`, `h0014_validate`, `run_h0014`, `h0014_ic_yearly` |
| `intraday_cache/` | H-0008 5-minute bars | **0 — absent everywhere** | `run_h0008.load_intraday` |

**One behaviour change in an intraday component (confirmed):**
- **Before:** `run_h0008.load_intraday` returned `None` for every symbol, and
  silently, because the store is gone.
- **Now:** the locator raises, naming the missing store. Where the store
  exists, a single missing symbol file still returns `None`, as before.
- **H-0008's intraday reconstruction was already non-reproducible**
  (inferred). This newly recorded dependency is not in the preservation
  record.

The locator was re-keyed for `h0013_build_features`, `h0014_acquire_snapshots`
and `h0017_acquire`, which write into their stores. Re-acquiring into a
missing store would now fail rather than write into whichever scratchpad held
the decade files. Durable intraday preservation is a separate task.

## §7 Derived-file dependencies — provenance

| derived file | where | produced by | from | hash recorded? | consumers |
|---|---|---|---|---|---|
| `anatomy-deep.jsonl` (2026-09-15 20:30) | `data/phase5/`, gitignored | `phase5_anatomy` | decade data from the scratchpad copy | no | `phase5_fetch_news`, `phase5_news_analysis` |
| `candidates-deep.jsonl` (2026-09-15 20:53) | same | `phase5_candidates` | the same | no | `phase5_fetch_news --candidates` |
| `news-archive-deep.jsonl`, `news-windows-deep.txt` (2026-09-15 21:16) | same | `phase5_fetch_news` | the anatomy or candidate windows, plus the **Alpaca news API** — an external acquisition with no preserved copy | no | `phase5_news_analysis`, `phase5_news_filter` |
| `news-features-deep.jsonl` (2026-09-15 20:35) | same | `phase5_news_analysis` | anatomy + archive | no | — |
| `h0011-cache.json` | `docs/phase5/`, **tracked** (`6ae4ee2`, 2026-09-19) | the H-0011 runner, through the shared loader, then reading the scratchpad | decade data | git blob only | `h0013_build_features`, `intraday_exits_acquire` |
| `h0014-daily-features.json` (2026-09-20 23:30, 72.9 MB) | **scratchpad** | `h0014_analyse.build_daily_cache()` | decade data from the scratchpad copy | no | `h0014_analyse`, `h0014_ic_yearly` — **§14.1** |

**Classification:**
- `phase5_fetch_news` and `phase5_news_analysis` are **derived-file only**
  (C): they read no price data and reach no scratchpad (§11).
- Their upstream decade producers are now gated. Regenerating the anatomy and
  candidate files from the verified dataset is possible in principle (not
  done: it is research computation).
- **The news archive is not reproducible** from anything preserved. It is an
  external API pull with no hash.
- Every derived file above predates the migration, and none was rewritten.

**Their decade input — inferred, not proven.** The scratchpad `deep/` copy has
been unmodified since 2026-09-08, and today it matches the checksum list
file-for-file. So the derived files were most likely built from bytes
identical to the verified dataset (provenance class B). No derived file is
cryptographically tied to it.

## §8 400-bar preservation — confirmed

| check | result |
|---|---|
| changed lines touching `WINDOW`, `_full`, `mean_reversion_signal` or the history slice, across the 20 migrated scripts | **0** |
| `WINDOW` after import, in the 10 migrated scripts that apply the patch, and `forensics_regime` | **400** in all 11 |
| runtime probe per module, in a fresh interpreter; `_full` replaced by a recorder, so no signal is computed | a 1,000-bar history reaches the signal as bars 600 … 999, **exactly 400**; a 250-bar history reaches it whole. Identical in all 11 |
| `phase5_candidates`' own slice, `history = bars[max(0, i - WINDOW + 1):i + 1]` | byte-identical to HEAD; `WINDOW = 400` |
| H-0013 / H-0014 scripts | no patch before, none after — they compute their own features |

No alternative window was tried.

## §9 Structural input validation — confirmed, identical

**Method:**
- A harness imported each script (every one has a `__main__` guard, and none
  has a top-level call).
- It called **only** its loader, or read the directory the script resolves,
  and hashed what the script would receive.
- It ran once before any edit and once after.
- No research code ran, and the dataset-use ledger stayed at 162 rows.

| checked | before (scratchpad) | after (gate) |
|---|---|---|
| `load()` users (10 + inline `phase5_candidates`) | 230 symbols, 582,324 bars, 0 nulls; per-symbol counts and first and last timestamps; the sorted order; one digest over every bar field (`69b1fce1…`) | **identical in all 11** |
| directory users (`h0013`, the five H-0014 scripts) | 230 files, 582,324 rows; schema `timestamp, open, high, low, close, volume`; 0 empty cells; every file ending 2026-09-04; one digest over every row (`a8abf1d7…`) | **identical in all 6** |
| intraday paths (`RAW`, `SPYDIR`, `SNAP`, `CACHE`) in 9 scripts | the scratchpad `ba9a513c…` paths | **the same paths** |
| resolved decade directory | `…/scratchpad/deep` | `data/research/decade-2016-2026-split-adjusted-230` |

**Scratchpad `deep/`:** 230 CSVs, no extra files. Every consumer's population
is therefore unchanged, including those built from `glob("*.csv")`.

## §10 Negative tests — disposable fixtures, all fail closed

**Setup:**
- Fixtures were full copies of the dataset under `data/research/_neg-*`, plus
  `data/_outside-fixture` and `data/_fixture-meta`.
- Each case ran in a fresh interpreter, with the loader (`run_h0005.load()`
  unless stated) pointed at the fixture.
- Every fixture was deleted afterwards (confirmed). The governed dataset was
  never written to, and re-verifies.

**Columns:** `load_bars` counts calls made before the failure. "Scratchpad"
counts scratchpad access attempts, with the scratchpad left available so any
fallback would have shown.

| # | case | result | raised in | `load_bars` | scratchpad |
|---|---|---|---|---:|---:|
| 1 | valid verified dataset | **succeeds**: 230 symbols, 582,324 bars | — | 230 | 0 |
| 2 | missing file (`AAPL.csv` removed) | `DatasetGateError`: file set differs | `verify_directory` | 0 | 0 |
| 3 | corrupted file (1 byte of `QQQ.csv`) | `DatasetGateError`: SHA-256 differs | `verify_directory` | 0 | 0 |
| 3b | unexpected extra file | `DatasetGateError`: file set differs | `verify_directory` | 0 | 0 |
| 4 | wrong dataset ID | `DatasetGateError`: not in the registry | `verify_dataset` | 0 | 0 |
| 4b | unknown folder label (`"weekly"`) | `DatasetGateError` | `price_dir` | 0 | 0 |
| 5 | scratchpad-only path | `DatasetGateError`: under a temporary directory | `verify_dataset` | 0 | 1 * |
| 6 | out of root — a **byte-identical** copy at `data/_outside-fixture` | `DatasetGateError`: outside the research data root | `verify_dataset` | 0 | 0 |
| 6b | `data/research/../_outside-fixture` | `DatasetGateError`: outside the root | `verify_dataset` | 0 | 0 |
| 6c | a file name escaping the verified directory | `DatasetGateError` | `dataset_file` | 0 | 0 |
| 7 | malformed registration (no dataset, benchmark or information boundary) | `check_registration` returns 3 problems → refused | — | 0 | 0 |
| 7b | registry hash disagrees with the pinned hash | `DatasetGateError` | `verify_dataset` | 0 | 0 |
| 8 | **verification fails while the scratchpad is available** | `DatasetGateError`; **no fallback** | `verify_directory` | 0 | **0** |
| 8b | thirty-year `long` label (`run_h0007`) | `DatasetGateError`: status `lost` | `verify_dataset` | 0 | **0** |
| 9 | an unparseable file whose checksums were rebuilt so the gate passes | `ValueError`: raised, **not skipped**; `load()` never returns | `load_bars` | 179 | 0 |
| 10 | import-time verification failure (`h0014_analyse`) | `DatasetGateError` at import, before the intraday lookup | `verify_directory` | 0 | 0 |

\* The refusal check's `Path.resolve()` stats the injected path. That is
metadata only, and no data is read.

**Before any research computation:** yes, in every case. Cases 1–8b and 10
fail before a single bar is read. Case 9 fails inside `load()`, which never
returns, so no caller computes.

## §11 Import-time tests — no hidden scratchpad access

**Scratchpad blocked.** Every open, stat, lstat, glob, scandir and listdir on
it raised.

| scripts | import | decade load | scratchpad attempts |
|---|---|---|---:|
| the 10 migrated `load()` scripts, plus `forensics_regime` | ok | ok: 230 / 582,324 | **0** |
| `phase5_candidates` | ok | `price_dir("deep")` resolves 230 files | **0** |
| `phase5_fetch_news`, `phase5_news_analysis` | ok | — (no price data) | **0** |
| `h0014_validate` | ok (lookups happen in `main()`) | — | **0** |
| `h0013_build_features`, `h0014_acquire_snapshots`, `h0014_analyse`, `run_h0014`, `h0014_ic_yearly`, `h0017_acquire`, `h0017_analyse`, `intraday_exits_acquire` | **fails — explicitly intraday** | where present, `DEEP = decade_dir()` passed first | 1 — the intraday locator's glob, raised in `unpreserved_intraday_store` |
| `run_h0008`, intraday part | `load_intraday` fails in `unpreserved_intraday_store` | — | 1 |

**Scratchpad available.** Every access was recorded.

| scripts | accesses touching `deep/` | stores touched |
|---|---:|---|
| the 8 intraday modules above | **0** | only their own listed stores |
| `run_h0008`, `h0014_validate`, `phase5_fetch_news`, `phase5_news_analysis` at import | 0 | none |

No governed module looks up decade data in the scratchpad at import, or at
all.

## §12 Clean OOS integrity — confirmed

- **Clean record:** 0 sessions, chain intact, `data/forward-evaluation.jsonl`
  absent.
- **Embargo, freeze and fingerprint:** 20 sessions, 2026-09-11, `da22011e…`.
- **Benchmark guard:** intact (`clean_window()` → `(None, 0)`,
  `MINIMUM_SESSIONS` 60). The first report is still 60 clean sessions after
  the embargo.
- **The guard in production:** the scheduled session close ran it at
  2026-09-24 12:45:51 local, during this task. `data/BENCHMARK.txt`'s forward
  section reads "0 clean sessions recorded" and reports nothing.
- **Nothing this task ran reads forward data.** No holdout output exists.

## §13 Model state — models frozen and UNPROVEN; the snapshot record is unchanged

**Nothing was touched:** no training, retraining, promotion, evaluation,
deployment or flag change. Both flags are False, and the promotions file is
absent.

**The snapshot** `docs/model-state/pre-clean-oos-2026-09-24.json` is unchanged
(SHA-256 `f479d507…`). Of the five files it records, four still match.

**The fifth, `data/live-model.json`, was rewritten during this task:**
- **When:** 2026-09-24 12:45:53 local (19:45:53Z).
- **By:** the scheduled end-of-session retrain, not by this task.
  `data/session.log` records "retraining on the record so far" at 12:45:51.
- **State now:** SHA-256 `e8986dcd…`, still UNPROVEN, still 3,063 examples.
- **Inputs:** its training rows are unchanged (`live-training.jsonl` still
  matches the snapshot).
- **Record:** this is the documented gap in action. The retrain is again in
  neither the lineage ledger nor the audit log. Recorded, not repaired.

## §14 Remaining dependencies

**14.1 Decade data — the reason for B**

- **The H-0014 daily-features cache:**
  `…/scratchpad/h0014-daily-features.json`, derived from decade prices and
  unverified.
  - `h0014_analyse.build_daily_cache()` reads it in preference to recomputing
    from the gated `DEEP`; `h0014_ic_yearly` calls the same function.
  - It was written 2026-09-20 23:30. `h0014_analyse.py`'s only commit
    (`90dc4bd`, 23:42 the same day) came afterwards, so the committed code
    cannot be shown to have produced it.
  - Left in place, per §5.
- **Outside class B, untouched:**
  - `build_training_seed` (class A — builds the live learner's seed; not
    scheduled; left under the no-model-work rule of §16) still globs the
    scratchpad decade copy.
  - **7 ungoverned class-D scripts** do too: `attribute_entry_signal`,
    `decompose_timing`, `forensics_post_stop`, `intraday_exit_measure`,
    `intraday_probe`, `probe_holding_cap`, `regime_forensics`.
  - **13 legacy class-C scripts** read `scripts/deep` or `scripts/long`,
    which do not exist. They cannot find data and never reach the scratchpad.
- **`load_bars` in `src/`** still drops unusable rows inside a file. That is
  pre-existing, and out of scope.

**14.2 Intraday data — scratchpad-only, not reproducible without it**

- The four stores in §6: 5.25 GB including `raw/`, as recorded earlier.
- H-0008's `intraday_cache/` exists nowhere.
- The H-0014 cache lives beside `snapshots/`.

**14.3 Derived and external**

- The news archive is an external API pull with no preserved copy.
- The `data/phase5/` derived files carry no hashes.

**14.4 Governance and model (unchanged by this task)**

- Retrains are not in `model-lineage.jsonl`.
- End-of-session retrains are not in the audit log; another occurred today
  (§13).
- Neither learned switch is in the fingerprint.
- The Clean OOS risk-adjusted metrics (rf 2.30%) have no committed
  implementation.

**Do not delete the scratchpad.** It holds every intraday store above, the
H-0014 cache, and the decade copy that class A and class D scripts still read.

## §15 Files changed — only these

| file | change |
|---|---|
| `scripts/research_gate.py` (new today, not yet committed) | `price_dir`, `decade_dir`, `dataset_file`, `unpreserved_intraday_store`; the research-root check in `verify_dataset`; docstring |
| `scripts/audit_h0003.py`, `run_h0005.py`, `run_h0006.py`, `run_h0007.py`, `run_sealed_exits.py`, `h0005_descriptive_27.py`, `phase5_anatomy.py`, `phase5_candidates.py`, `phase5_filters.py`, `phase5_news_filter.py` | decade path → gate; file-level silent skips removed |
| `scripts/run_h0008.py` | the same, plus the intraday locator (§6) |
| `scripts/h0013_build_features.py`, `h0014_acquire_snapshots.py`, `h0014_analyse.py`, `h0014_validate.py`, `run_h0014.py`, `h0014_ic_yearly.py` | `DEEP` → gate; intraday stores → the sanctioned locator at identical paths; unused `glob` / `os` imports removed |
| `scripts/h0017_acquire.py`, `h0017_analyse.py`, `intraday_exits_acquire.py` | locator re-keyed to the intraday store; no decade read |
| `docs/2026-09-24-governed-research-dataset-migration.md` | **new** — this report |
| `docs/2026-09-24-dataset-preservation-and-research-gate.md`, `docs/2026-09-24-research-loader-and-clean-oos-integrity-audit.md` | dated notes; original text kept |
| `docs/datasets/decade-2016-2026.md`, `docs/datasets/README.md` | the gating status |
| `knowledge/` | the notes that went stale; rebuilt and validated |

## §16 Files intentionally untouched

- **Code:** `src/` (including `load_bars` and `research.DATASETS`); `tests/`;
  `scripts/forensics_regime.py` and `scripts/benchmark.py` (both already
  gated).
- **Scripts outside class B:** `build_training_seed.py`, the class-C and
  class-D scripts, `phase5_fetch_news.py`, `phase5_news_analysis.py`.
- **Data:** the preserved dataset and its checksum list, manifest and
  registry entry; the scratchpad (nothing added to its data stores, nothing
  removed); every derived file.
- **Records:** every ledger; the fingerprint; the model files and the
  snapshot.
