# Intraday data preservation audit

*2026-09-24. Data preservation and provenance only. **Input data preserved and
hash-verifiable — no experiment was re-run.** Not done:*
- *H-0013, H-0014 or H-0017, or any builder, sealed result or backtest;*
- *any P&L, Sharpe, CAGR or drawdown;*
- *any vendor request;*
- *any Clean OOS or forward read;*
- *any change to strategy, parameters, execution model, emulator or
  benchmark;*
- *any model action, or any change to `src/` or `tests/`;*
- *any deletion from the scratchpad.*

*The datasheet is
[datasets/intraday-preservation-2026-09-24.md](datasets/intraday-preservation-2026-09-24.md).*

---

## §17 Final classification: **B — partial intraday preservation**

**Every file that any H-0013, H-0014 or H-0017 code reads is preserved
(confirmed).**
- **Where:** four registered datasets under `data/research/`.
- **How:** byte-identical to the scratchpad originals, with per-file SHA-256
  hashes and a dataset-level hash, verified through the existing gate.
- **Other inputs:** the tracked files and the already-gated decade data and
  H-0014 feature cache.

**The exact missing input — H-0014's raw 5-minute bars for the 230-symbol
universe.**
- **What the registration says:** H-0014 declares "5-minute intraday for the
  fixed 230-symbol universe plus SPY".
- **What happened to them:** `scripts/h0014_acquire_snapshots.py` fetched
  those bars from the vendor in memory, and wrote only the derived snapshot
  tables. The bars were never written to disk, so they exist in no
  scratchpad and no repository, and could not be preserved.
- **What survives:** the SPY component (preserved) and the snapshots, the
  earliest retained form of the 230-symbol bars (preserved).

A is therefore not claimed. **Preservation does not make any of the three
experiments reproducible.** None was re-run.

---

## §1 Scope

**Preserved:** the four data-bearing stores that existed only in the Claude
session scratchpad `ba9a513c-7a3b-43dd-bc7f-dfe8be46d8d9`:
- `raw/intraday-exits`
- `raw/intraday-spy`
- `snapshots`
- `raw/h0017-micro`

That is 1,192 files, 5,246,704,028 bytes.

**How:**
- each store got its own dataset identity, checksum list, manifest and
  registry entry;
- the copies are read-only;
- the originals are kept, untouched.

**Inventoried but not preserved:** `raw/intraday-probe`, which no H-0013,
H-0014 or H-0017 code reads (§10). The rest of the scratchpad is scripts, logs,
test tooling, and data preserved earlier (`deep/`, the H-0014 feature cache).

## §2 Governance state — confirmed at the start and again at the end

| item | start | end |
|---|---|---|
| baseline (P5-0001 and P5-0038 `baseline_metrics`) | 0.585889 / 698 | unchanged |
| dataset-use ledger | 162 rows | 162 rows |
| registrations / remediations / lineage / experiments / phase 5 | 24 / 9 / 3 / 53 / 39 rows; `d55e288a` / `f8d82279` / `667f1190` / `ef6a9b5e` / `fcaba151` | identical; byte-identical to HEAD |
| fingerprint | `da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b` | same |
| Clean OOS | 0 sessions, chain intact | same |
| freeze / embargo | 2026-09-11 / 20 | same |
| `LEARNED_RANKING_ENABLED` / `LEARNED_VETO_ENABLED` | False / False | same |
| `src/`, `tests/` | 0 changes | 0 changes |

## §3 Source inventory

A read-only inventory was taken at 2026-09-24T22:09:40Z, before any copy. The
scratchpad root is
`C:\Users\yajga\AppData\Local\Temp\claude\C--market-bot\ba9a513c-…\scratchpad\`.

| store | files | bytes | type | content | source written (UTC) | raw or derived | H-ID |
|---|---:|---:|---|---|---|---|---|
| `raw/intraday-exits` | 698 | 15,356,853 | JSON, `{"bars": {SYM: [...]}, "next_page_token": null}` | 127,461 five-minute bars; 176 symbols; exit sessions 2016-11-09 … 2026-09-03 | 2026-09-20 05:50 … 06:18 | raw | H-0013 |
| `raw/intraday-spy` | 43 | 61,284,227 | JSON, quarterly | 498,822 SPY bars; 2016-01-01 … 2026-09-18 | 2026-09-20 06:18 … 06:23 | raw | H-0013, H-0014 |
| `snapshots` | 230 | 3,029,641,196 | CSV, 35 columns, one header for all | 5,252,811 rows; 230 symbols; sessions 2016-11-15 … 2026-08-07 | 2026-09-20 16:45 … 2026-09-21 06:17 | derived | H-0014 |
| `raw/h0017-micro` | 221 | 2,140,421,752 | JSON, `target` / `trades` / `quotes` / pages / errors / windows | 16,988,838 trades and 1,514,343 quotes; 120 symbols; exits 2016-12-09 … 2026-08-13 | 2026-09-21 15:07 … 15:47 | raw | H-0017 |
| `raw/intraday-probe` (not preserved) | 18 | 1,277,684 | JSON | 10,561 bars; 6 symbols | 2026-09-20 05:49 … 05:50 | raw | none — Phase 1 probe |

Every per-file size, SHA-256, source modification time and structural record
is in `docs/datasets/<id>.manifest.json`.

## §4 Experiment dependency map

The boundary is established from committed code and tracked records, not
from directory contents.

| experiment | input store | data type | date range | instruments | raw or derived | preservation required | status |
|---|---|---|---|---|---|---|---|
| H-0013 (builder `h0013_build_features.py`) | `raw/intraday-exits`: `<symbol>_<exit>.json` per trade of `docs/phase5/h0011-cache.json` BASELINE | 5-minute bars | exit sessions 2016-11-09 … 2026-09-03 | 176 symbols | raw | yes — all 698 (the registration's "all 698 exit sessions") | **preserved** — 698 expected = 698 present |
| H-0013 (builder) | `raw/intraday-spy`: every `*.json` | SPY 5-minute bars | 2016-01 … 2026-09-18 | SPY | raw | yes, all 43 | **preserved** |
| H-0013 (runner `run_h0013.py`) | `docs/phase5/h0013-features.json`, `h0011-cache.json`, decade prices | derived features, trade list | — | — | derived | already durable (tracked; gated) | durable |
| H-0014 (snapshot builder `h0014_acquire_snapshots.py`) | `raw/intraday-spy`: every `*.json` | SPY 5-minute bars | as above | SPY | raw | yes | **preserved** |
| H-0014 (snapshot builder) | vendor 5-minute bars for the 230 symbols, fetched in memory | 5-minute bars | — | 230 symbols | raw | yes (registered input) | **MISSING — never written to disk** |
| H-0014 (sealed analysis `h0014_analyse.py`; `run_h0014`, `h0014_validate`, `h0014_ic_yearly`) | `snapshots`: one CSV per decade symbol, 230/230 required | derived snapshot tables | sessions 2016-11-15 … 2026-08-07 | 230 symbols | derived | yes | **preserved** — 230 = 230 |
| H-0014 (sealed analysis) | daily-feature cache; decade prices | derived; OHLCV | — | 230 symbols | derived; raw | already durable | durable (`h0014-daily-features-decade-230`, reproduced byte-for-byte; decade gated) |
| H-0017 (`h0017_analyse.py`) | `raw/h0017-micro`: every `*.json` | trades and quotes | exits 2016-12-09 … 2026-08-13 | 120 symbols | raw | yes — the 221 targets | **preserved** — 221 = 221; every embedded target matches its name |
| H-0017 (acquisition) | `docs/phase5/h0017-targets.json` | target list | — | — | derived | already durable (tracked) | durable |

## §5 Preservation manifests

| dataset ID | files | bytes | dataset SHA-256 | checksum list SHA-256 | manifest SHA-256 |
|---|---:|---:|---|---|---|
| `intraday-exit-sessions-5min-698` | 698 | 15,356,853 | `071d519b490219b8b045e89b508960473dfb7ca3782c047fbc6fccdbab2541e6` | `d8155ab99f19c46a789b5ecc6ed8997e5e9f3571d663a9cb57e7e2b84856100a` | `aeec7703d8670d47f030c29b185b6d14ee65510947720db43f3aa60a28e09a4f` |
| `spy-5min-2016-2026-quarterly-43` | 43 | 61,284,227 | `9803ae210c0710960b7aa8c4de12b121a51adfc471643deeac599f6d8230d2c5` | `8df3ff495d3c8c0f9716996749da18791e4f3bdcc46201345b08bd461bc83926` | `eaad96b22b8cdf8f9583ae65b45b99cf76bb68a3f5de7a81ebf7cbff4baeb9e9` |
| `h0014-intraday-snapshots-230` | 230 | 3,029,641,196 | `b38d525752a11c4515a19039272635cb51f9754f7b1ec35ca47770419c981ec3` | `f3dd0df9d9762573f1bee6acddbc980580811dd37d166cc476b5d805e80b0789` | `26be9cd8450572f4eeae61de3ab8c581bcb7ee3152802db5bb42ca690cebab77` |
| `h0017-trades-quotes-221` | 221 | 2,140,421,752 | `22ea00853653a3fe8ce3bdfa6f25bc22400b7e3a16beaebb5e7e0442254eeb43` | `65ca7adab5b5fbbff4d536722f3420a33b5c40c88b9c073de8b086e86bd7f218` | `3488c101efb11c9d7d7dfd9c56e6cbc2e58397dffaffcb913027772301ecbff7` |

- **Dataset hash:** the gate's rule — the SHA-256 of
  `<file>\t<size>\t<sha256>\n` per file, sorted by file name.
- **Checksum lists:** in `sha256sum` format, sorted, with LF line endings.
- **Manifests:** sorted keys, with files in name order.
- **Four separate identities:** the SPY store is shared by H-0013 and H-0014,
  and no store is indivisible from another.

## §6 Byte-identity verification — confirmed

| check | result |
|---|---|
| source hashed before copying | every file of all four stores, at inventory |
| copy | `shutil.copy2` (bytes and modification time), flat, same file names |
| every destination file re-hashed and compared (file, size, SHA-256) with the pre-copy list | **1,192 / 1,192 identical**; no missing and no extra file |
| destination read-only | yes, every file |
| `verify` pass | for each dataset: the gate `VERIFIED`; copy = manifest; source = manifest; source modification times unchanged; checksum list = manifest → **ALL VERIFIED** |
| source unchanged | per-file hashes and modification times equal the inventory; the whole scratchpad tree (1,510 files by path, size and modification time) fingerprints `dd147953…` before and after |
| `research_gate.py --audit` | 6 preserved datasets VERIFIED, thirty-year listed as lost → PASS |

No discrepancy occurred, so no stop was needed. Nothing was overwritten or
deleted.

## §7 Provenance

| field | status |
|---|---|
| vendor endpoint and parameters of the 459 rule-exit sessions (`/v2/stocks/bars`, 5Min, `adjustment=split`) | **inferred** — the files were written 05:50–05:56Z; `intraday_exits_acquire.py` (rule exits only) was committed 05:57Z |
| acquisition code of the 239 stop-exit sessions | **unknown** — no committed script acquires stops |
| acquisition code, parameters and adjustment of the SPY store | **unknown** — no committed script writes it |
| snapshot builder | **confirmed** code (`6036727`); **inferred** that this code produced the files (the timing matches) |
| raw 5-minute bars behind the snapshots | **never retained** |
| H-0017 endpoints (`/v2/stocks/trades`, `/v2/stocks/quotes`) | **confirmed** (registration and code, `94d3003`) |
| H-0017 page caps (3 trade pulls, 1 quote pull) | **confirmed**, and already recorded in the sealed `h0017-results.json` (`acquisition_errors`) |
| vendor `feed` | **unknown** — set by no request |
| information boundary | exits ≤ 2026-09-03 and H-0017 ≤ 2026-08-14: before the freeze. Snapshots ≤ 2026-08-07. **The SPY store runs to 2026-09-18, past the 2026-09-11 freeze.** That is embargo-window market data, not Clean OOS. The consumers bound their own use; any future use must apply the freeze boundary |

## §8 Gate integration

**`scripts/research_gate.py` needed no change (confirmed).**
- Every store is a flat directory, which is exactly what `verify_dataset`
  checks: the exact file set, every SHA-256, the dataset hash, a durable path
  under `data/research/`.
- The four datasets were registered in `docs/datasets/registry.json`. The
  registry round-trips byte-for-byte, and existing entries are untouched.
- Each entry records ID, hash, source, preserved location, counts, bytes,
  coverage, population, raw or derived, acquisition, experiments, information
  boundary, execution relevance and preservation date.
- `research_gate.verify_dataset("<id>", "<sha256>")` now identifies each
  exact dataset.

**The historical runners were deliberately not repointed.** They still read
the scratchpad originals through `research_gate.unpreserved_intraday_store`.
The stated reasons:
- nothing re-runs, so there was nothing to make consistent;
- a pointer change would create the appearance of an experiment run from the
  preserved copy.

That function's comment ("no verified copy") is now out of date for four of
its five stores; it was left as is because the gate required no change.

## §9 Failure tests — disposable fixtures

**Setup:**
- Fixtures were copies of `spy-5min-2016-2026-quarterly-43` under
  `data/research/_neg-spy-*`, plus a fixture registry in
  `data/_fixture-meta`. All were deleted afterwards (confirmed).
- The real preserved datasets and the scratchpad were never modified.
- Each case ran the gate in a fresh interpreter that recorded every
  scratchpad access.

| # | case | result | scratchpad accesses |
|---|---|---|---:|
| T0 | valid preserved dataset (control) | **passes** | 0 |
| T1 | missing file | refused: file set differs | 0 |
| T2 | flipped byte | refused: SHA-256 differs | 0 |
| T3 | extra file | refused: file set differs | 0 |
| T4 | renamed file | refused: file set differs | 0 |
| T5 | changed manifest — a byte flipped **and** the checksum list rewritten to match | refused: the dataset hash does not equal the registered one | 0 |
| T5b | pinned dataset hash edited | refused | 0 |
| T6 | destination path → another dataset's directory | refused: file set differs | 0 |
| T6b | destination path → the scratchpad source | refused: under a temporary directory | 1 * |
| T6c | destination path outside `data/research/` | refused: outside the research data root | 0 |
| T6d | destination path through `..` | refused: outside the root | 0 |

\* The refusal check's own metadata lookup on the injected scratchpad path.
No data was read.

**No fallback to the scratchpad:** in every failing case other than T6b, the
gate made **0** scratchpad accesses.

## §10 Remaining dependencies

1. **H-0014's raw 5-minute bars for the 230 symbols** were never retained, and
   only vendor reacquisition could supply them. A new pull might not match the
   original bytes.
2. **Acquisition code not in the repository:** the 239 stop-exit sessions,
   and the SPY store.
3. **H-0008's `intraday_cache/`** exists nowhere. It is outside H-0013,
   H-0014 and H-0017.
4. **`raw/intraday-probe`** — the Phase 1 feasibility probe, read only by the
   ungoverned `intraday_probe.py` — is not preserved and is out of scope.
5. **Historical runners** still locate the stores in the scratchpad (§8).
6. **No off-machine backup:** the preserved copies, like the decade data, are
   gitignored. Only the checksum lists and manifests are committable.
7. **Hidden-dependency search (confirmed):**
   - Repository-wide, for the store names, the H-IDs, `h0011-cache`,
     `h0013-features` and `h0017-targets`.
   - Every other input the three experiments read is tracked in git
     (`h0011-cache.json`, `h0013-features.json`, `h0017-targets.json`) or
     already gated.
   - The other "snapshots" hits are a local variable in
     `build_training_seed.py` and prose in the registration scripts.

## §11 H-0013 status — input preservation only

- **Builder inputs:** the complete intraday input boundary of the builder
  (`h0013_build_features.py`) is **preserved**: all 698 exit-session files and
  all 43 SPY files.
- **Runner inputs:** the tracked `h0013-features.json`, the tracked
  `h0011-cache.json` and the gated decade data are durable.
- **Provenance gap:** the acquisition code of 239 of the 698 sessions (stops)
  and of the SPY store is unknown.
- **Unchanged:** H-0013 was not re-run, and its registration, acceptance
  decision and adjudication are unchanged. **Input data preserved and
  hash-verifiable; the experiment was not reproduced.**

## §12 H-0014 status

- **Daily-feature input:** reproducible. It was reproduced byte-for-byte from
  the verified decade dataset earlier today (`h0014-daily-features-decade-230`).
- **Intraday input:** the snapshots, which the sealed analysis reads, and the
  SPY store, which the snapshot builder reads, are now **preserved outside the
  scratchpad and hash-verifiable**.
- **Missing:** the raw 5-minute bars for the 230 symbols, which the snapshots
  were built from and which were never retained.
- **Unchanged:** `docs/phase5/h0014-results.json` (SHA-256 `8ded7e38…`), the
  seal and the registration. H-0014 was not re-run and the cache was not
  rebuilt.
- **Wording:** daily-feature input reproducible; intraday input preserved and
  hash-verifiable; the result itself was not reproduced.

## §13 H-0017 status — input preservation only

- **Preserved:** the complete input boundary that `h0017_analyse.py` reads,
  all 221 target files. Each file carries its target record, trades (next
  session) and quotes (the exit's closing five minutes). The target list is
  tracked.
- **Preserved exactly as acquired:** the four capped pulls (3 trade, 1
  quote), which the sealed result already reports.
- **Unchanged:** no vendor was queried, the analysis was not re-run, and the
  H-0017 conclusion is unchanged. **Input data preserved; the experiment was
  not reproduced.**

## §14 Clean OOS integrity — confirmed

- **The clean record:** 0 clean sessions, chain intact,
  `data/forward-evaluation.jsonl` absent.
- **Unchanged mechanisms:** the freeze (2026-09-11) and the embargo (20).
  `benchmark.py`'s guard is intact (`clean_window()` → `(None, 0)`, 60
  sessions).
- **Nothing ran against forward data.**
- **The newest bytes preserved** are SPY bars from 2026-09-18, in the embargo
  window. Only their timestamps were read, for coverage, and no value was
  analysed. The Clean OOS window does not begin until the first clean session
  (projected 2026-10-12), so no holdout observation exists yet, and none was
  consumed.
- **Models and orders:** both switches are off. Both model files are
  unchanged (`e8986dcd…`, `a13ac286…`, UNPROVEN). No order: the live audit
  log was last written at 13:00:04 local, before this task began.

## §15 Files changed

| file | change |
|---|---|
| `scripts/preserve_intraday_stores.py` | **new** — the inventory, preserve and verify tool |
| `docs/datasets/registry.json` | 4 entries added |
| `docs/datasets/<id>.sha256` × 4 | **new** — checksum lists |
| `docs/datasets/<id>.manifest.json` × 4 | **new** — per-file manifests |
| `docs/datasets/intraday-preservation-2026-09-24.md` | **new** — the datasheet |
| `docs/2026-09-24-intraday-data-preservation-audit.md` | **new** — this report |
| `docs/datasets/README.md`, `docs/datasets/h0014-daily-features.md` | the preservation status (earlier text kept) |
| `docs/2026-09-24-dataset-preservation-and-research-gate.md`, `…-governed-research-dataset-migration.md`, `…-research-loader-and-clean-oos-integrity-audit.md` | dated notes only |
| `knowledge/07-sources/Datasets.md`, `knowledge/05-open-questions/Research Gaps.md` | the preservation status; rebuilt and validated (PASS) |
| `data/research/<id>/` × 4 (gitignored) | **new** — the preserved copies, read-only |
| `data/_preservation-work/` (gitignored) | the inventory JSON and the failure-test script — working evidence |

## §16 Files intentionally untouched

- **Code:** `src/`; `tests/`; `scripts/research_gate.py`; every H-0013,
  H-0014 and H-0017 runner and builder.
- **Records:** every ledger; the frozen fingerprint; the model files and the
  snapshot.
- **Sealed results:** `docs/phase5/*`, including `h0014-results.json`,
  `h0013-*` and `h0017-results.json`, and every seal and registration.
- **Data:** the decade dataset and the H-0014 feature cache (both already
  preserved); the original scratchpad — its whole tree is identical before
  and after, and nothing was deleted.
