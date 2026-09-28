# Intraday preservation — 2026-09-24

*Datasheet for the four intraday research stores that existed only in a
Claude session scratchpad. Preservation and provenance only: **input data is
preserved and hash-verifiable. No experiment was re-run** — not H-0013,
H-0014 or H-0017, and nothing else. The audit record is
[2026-09-24-intraday-data-preservation-audit.md](../2026-09-24-intraday-data-preservation-audit.md).*

## 1. Objective

The data must survive the clean-up of a temporary directory, and any copy of
it must be verifiable byte for byte. Preservation proves that and nothing
more. It does not show:
- that a sealed experiment can be re-run;
- that its result reproduces;
- that the builders are deterministic;
- that the acquisitions could be repeated.

## 2–3. Source and destination

| store (source, unchanged) | preserved at (read-only, gitignored) |
|---|---|
| `…/C--market-bot/ba9a513c-7a3b-43dd-bc7f-dfe8be46d8d9/scratchpad/raw/intraday-exits/` | `data/research/intraday-exit-sessions-5min-698/` |
| `…/scratchpad/raw/intraday-spy/` | `data/research/spy-5min-2016-2026-quarterly-43/` |
| `…/scratchpad/snapshots/` | `data/research/h0014-intraday-snapshots-230/` |
| `…/scratchpad/raw/h0017-micro/` | `data/research/h0017-trades-quotes-221/` |

**Scratchpad root:** `C:\Users\yajga\AppData\Local\Temp\claude\`. Every store
is flat, so each copy keeps the same file names at the same level.

**Nothing in the scratchpad changed.** The whole tree (1,510 files, by path,
size and modification time) fingerprints `dd147953…` before and after.

## 4–8. Identity

**Dataset SHA-256** follows the gate's rule: the SHA-256 of
`<file>\t<size>\t<sha256>\n` per file, sorted by file name. **Checksum list**
is the `sha256sum`-format file the gate reads. **Manifest** is the per-file
record (bytes, SHA-256, source modification time, structural metadata).

| dataset ID | files | bytes | dataset SHA-256 | checksum list SHA-256 | manifest SHA-256 |
|---|---:|---:|---|---|---|
| `intraday-exit-sessions-5min-698` | 698 | 15,356,853 | `071d519b490219b8b045e89b508960473dfb7ca3782c047fbc6fccdbab2541e6` | `d8155ab99f19c46a…` | `aeec7703d8670d47…` |
| `spy-5min-2016-2026-quarterly-43` | 43 | 61,284,227 | `9803ae210c0710960b7aa8c4de12b121a51adfc471643deeac599f6d8230d2c5` | `8df3ff495d3c8c0f…` | `eaad96b22b8cdf8f…` |
| `h0014-intraday-snapshots-230` | 230 | 3,029,641,196 | `b38d525752a11c4515a19039272635cb51f9754f7b1ec35ca47770419c981ec3` | `f3dd0df9d9762573…` | `26be9cd8450572f4…` |
| `h0017-trades-quotes-221` | 221 | 2,140,421,752 | `22ea00853653a3fe8ce3bdfa6f25bc22400b7e3a16beaebb5e7e0442254eeb43` | `65ca7adab5b5fbbf…` | `3488c101efb11c9d…` |
| **total** | **1,192** | **5,246,704,028** | | | |

**Files:** `docs/datasets/<id>.sha256` (the checksum lists, read by the gate)
and `docs/datasets/<id>.manifest.json` (per-file SHA-256, size and source
modification time, plus structural metadata).

## 9–10. Coverage

| dataset | date coverage | instruments | content |
|---|---|---|---|
| `intraday-exit-sessions-5min-698` | exit sessions 2016-11-09 … 2026-09-03; bar timestamps 2016-11-09T09:00Z … 2026-09-04T23:15Z (extended hours included) | 176 symbols | 127,461 five-minute bars; one file per baseline trade, `<SYMBOL>_<exit date>.json` |
| `spy-5min-2016-2026-quarterly-43` | 2016-01-01T00:00Z … **2026-09-18T23:55Z** — 43 contiguous quarters | SPY | 498,822 five-minute bars |
| `h0014-intraday-snapshots-230` | sessions 2016-11-15 … 2026-08-07 | 230 symbols, the decade universe | 5,252,811 rows × 35 columns; 3,700 … 24,438 rows per symbol |
| `h0017-trades-quotes-221` | exit dates 2016-12-09 … 2026-08-13; the last trade 2026-08-14 | 120 symbols | 16,988,838 trades and 1,514,343 quotes; one file per target, each carrying its own target record |

## 11. Experiment dependencies

The boundaries below are established from committed code and tracked
records, not from directory contents.

| experiment | store | how it is read | boundary check |
|---|---|---|---|
| H-0013 | intraday exit sessions | `h0013_build_features.py`: `RAW/<symbol>_<exit>.json` for every trade in `docs/phase5/h0011-cache.json` BASELINE | 698 expected = 698 present; 0 missing, 0 extra; symbol and date match every name |
| H-0013 | SPY | the same builder reads every `*.json` | 43 contiguous quarters, SPY only |
| H-0014 | SPY | `h0014_acquire_snapshots.py` reads every `*.json`, for the snapshots' `spy_ret` / `spy_rvol` | the same |
| H-0014 | snapshots | `h0014_analyse.py` (the sealed body), `run_h0014.py`, `h0014_validate.py`, `h0014_ic_yearly.py`: one CSV per decade symbol; `h0014_analyse` refuses anything short of 230/230 | 230 = 230; one header for all |
| H-0017 | trades and quotes | `h0017_analyse.py` reads every `*.json` | 221 targets in `docs/phase5/h0017-targets.json` = 221 files; every embedded target matches its file name |

**Other inputs, already durable:**
- **Tracked in git:** `docs/phase5/h0011-cache.json`,
  `docs/phase5/h0013-features.json` (what `run_h0013` itself reads) and
  `docs/phase5/h0017-targets.json`.
- **Gated datasets:** the decade prices and the H-0014 daily-feature cache.

## 12. Raw or derived

- **Raw vendor payloads:** exit sessions, SPY, and H-0017 trades and quotes.
- **Derived:** the H-0014 snapshots — per-symbol tables of features and
  forward outcomes, computed from 5-minute bars.
  - The columns `fwd5`, `fwd10`, `fwd20`, `spy_fwd5`/`10`/`20`, `mfe20` and
    `mae20` are forward outcomes: targets, never inputs, under the
    registration's information boundary.
  - Preservation did not read or convert them.

## 13. Known provenance

| dataset | known | label |
|---|---|---|
| exit sessions, 459 rule exits (221 reverted, 238 time_exit) | Alpaca `/v2/stocks/bars`, `timeframe=5Min`, `adjustment=split`, `limit=10000`. Written 2026-09-20T05:50–05:56Z. `scripts/intraday_exits_acquire.py` acquires exactly these reasons and was committed at 05:57Z (`3c169b5`) | inferred |
| snapshots | built by `scripts/h0014_acquire_snapshots.py` (first committed `6036727`, 2026-09-20T16:49Z) from Alpaca `/v2/stocks/bars` 5Min, `adjustment=split`, plus the SPY store and decade daily CSVs. Written 2026-09-20T16:45Z … 2026-09-21T06:17Z | confirmed (code) / inferred (that this exact code ran) |
| H-0017 trades and quotes | Alpaca `/v2/stocks/trades` and `/v2/stocks/quotes`, `limit=10000` per page. `scripts/h0017_acquire.py`, first committed `94d3003` (2026-09-21T15:07Z). Written 15:07–15:47Z | confirmed (code) / inferred (that this exact code ran) |
| H-0017 acquisition caps | `trade_err: "capped"` in `AAPL_2026-02-02`, `AAPL_2026-07-02`, `NVDA_2026-02-25` (600,000 trades each); `quote_err: "capped"` in `NVDA_2026-02-25` (60,000 quotes). The sealed `docs/phase5/h0017-results.json` records the same (`acquisition_errors`: trade_capped 3, quote_capped 1) | confirmed |

## 14. Unknown provenance

- **The 239 stop-exit sessions** were written 2026-09-20T06:15–06:18Z. The
  committed acquisition script excludes stops, and no committed code acquires
  them, so the acquisition code and request parameters are **unknown**.
- **The SPY store** was written 06:18–06:23Z, one minute before H-0013's
  registration commit. No committed script writes it: both commits that
  mention it only read it. The acquisition code, request parameters and
  adjustment are **unknown**.
- **H-0014's raw 5-minute bars for the 230 symbols were never written to
  disk.** The builder fetched them in memory and wrote only the snapshots.
  They are in no scratchpad and no repository, so they could not be
  preserved. The snapshots are the earliest retained form.
- **The vendor's `feed` parameter** is not set in any request. Which feed the
  account defaulted to at the time is **unknown**.

## 15. Validation procedure

`scripts/preserve_intraday_stores.py`:
- **`inventory`** — read-only: the per-file SHA-256 of every source file
  before copying, the boundary checks, and the scratchpad tree fingerprint.
- **`preserve`** — for each store:
  - copies every file with `shutil.copy2` (bytes and modification time);
  - re-hashes every destination file and compares file, size and SHA-256
    with the pre-copy source list, **stopping without overwriting or deleting
    anything** on any difference;
  - makes the copy read-only;
  - writes the checksum list and manifest, and registers the dataset.
- **`verify`** — for every dataset:
  - the gate (`research_gate.verify_dataset` with the pinned hash);
  - the copy against the manifest, and the source against the manifest,
    including modification times;
  - that the copy is read-only;
  - that the checksum list's hash matches the manifest.

All four pass, the gate audit passes, and 11 failure cases on disposable
fixtures behave as they should (audit record §9).

Re-verify at any time; this command is read-only:

```bash
python scripts/preserve_intraday_stores.py verify
```

## 16. Unresolved dependencies

1. **H-0014's raw 5-minute bars for the 230 symbols** were never retained.
   Only vendor reacquisition could supply them, and a new pull might not
   match the original bytes.
2. **The acquisition code** of the 239 stop-exit sessions and of the SPY
   store is not in the repository.
3. **The historical runners are unchanged.** They still locate these stores
   in the scratchpad, through `research_gate.unpreserved_intraday_store`.
   That function's comment ("no verified copy") is now out of date for these
   four stores. It was left untouched because the gate needed no change.
4. **Out of scope and not preserved:**
   - `raw/intraday-probe` (18 files, 1,277,684 bytes, 6 symbols; dataset
     SHA-256 `8bc3d7e7…`) — the Phase 1 feasibility probe, read only by
     `scripts/intraday_probe.py`, not by H-0013, H-0014 or H-0017;
   - H-0008's `intraday_cache/`, which exists nowhere.

## 17. No experiment was re-run

H-0013, H-0014 and H-0017 were not executed, and no builder ran. No vendor
was contacted. No feature, statistic, P&L or forward value was computed. The
sealed results, seals and registrations are unchanged.
