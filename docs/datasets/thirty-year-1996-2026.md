# Datasheet — `thirty-year-1996-2026-229` (LOST)

*Historical in-sample research dataset. **No copy of the raw data exists.**
This record preserves what is known about it and marks the results that
depended on it. It invalidates nothing and rewrites no ledger record.*

## Status

| field | value |
|---|---|
| dataset ID | `thirty-year-1996-2026-229` |
| status | **lost** — no raw copy anywhere on this machine (a recursive search of the user profile and the repository on 2026-09-23 found none) |
| dataset SHA-256 | **none** — no checksum or manifest was ever recorded |
| name in `research.DATASETS` | `thirty_year` ("1996-2026, 229 names", status contaminated) |
| evidence class | historical in-sample |
| provenance class | **C** — unrecoverable |

## What is known, inferred and unknown

| | statement | source |
|---|---|---|
| known | universe of **229 names** | `research.DATASETS`; every one of the 13 recorded reads (all on 2026-09-16) records 229 symbols |
| known | start **1996-01-01** | `scripts/thirty_year_test.py`: `FROM = date(1996, 1, 1)` |
| known | source **Yahoo**, fetched "with a browser header" | `docs/2026-09-08-thirty-year-test.md` |
| known | stored beside the scripts as `long/`, later in a session scratchpad | `thirty_year_test.py` (`HERE / "long"`); `docs/2026-09-16-phase5-checkpoint.md` |
| unknown | which of today's 230 names is absent | not recorded |
| unknown | the end date | not recorded; the acquisition was on or about 2026-09-08 |
| unknown | adjustment basis and schema | not recorded. `data.fetch_yahoo_bars` is a generic yfinance fetcher (`auto_adjust=False`) and is **not** proven to be the code that acquired it |
| unknown | the acquisition code | not in the repository |

## Results that are non-reproducible from preserved raw data

These are recorded, unedited, in their ledgers. Each remains the historical
record of what was measured; none can be re-derived from raw data today.
Selection rules: an experiment whose `data_periods` contains `thirty_year`; a
phase-5 row whose `dataset` names the thirty-year window or whose metrics
carry `thirty_year` keys; a registration that declares thirty-year use.

| ledger | count | items |
|---|---:|---|
| `docs/experiments.jsonl` | 31 | EXP-0002, EXP-0004, EXP-0009, EXP-0014, EXP-0016, EXP-0020, EXP-0021, EXP-0022, EXP-0023, EXP-0025, EXP-0026, EXP-0027, EXP-0028, EXP-0029, EXP-0030, EXP-0031, EXP-0036, EXP-0037, EXP-0038, EXP-0039, EXP-0042, EXP-0043, EXP-0044, EXP-0045, EXP-0047, EXP-0048, EXP-0049, EXP-0050, EXP-0051, EXP-0052, EXP-0054 |
| `docs/phase5-research.jsonl` | 24 | P5-0007, P5-0008, P5-0009, P5-0010, P5-0014, P5-0015, P5-0016, P5-0017, P5-0019, P5-0020, P5-0021, P5-0022, P5-0023, P5-0024, P5-0025, P5-0026, P5-0031, P5-0032, P5-0033, P5-0034, P5-0036, P5-0037, P5-0038, P5-0039 |
| `docs/preregistrations.jsonl` | 5 | H-0001, H-0002, H-0003, H-0004, H-0007 |

For many of these, the thirty-year figure is a robustness check beside a
decade figure. The decade part is reproducible from the preserved decade
dataset; the thirty-year part is not.

## Requirements for any future reacquisition — not performed

A reacquisition would produce a **new** dataset. It must never be presented
as the original, and it cannot make the results above reproducible.

| requirement | value |
|---|---|
| universe | identify the absent name first, then the same 229 names |
| range | from 1996-01-01, with the end date fixed and recorded |
| source | Yahoo, with the request parameters and the adjustment basis chosen and recorded before download |
| schema | the decade schema, `timestamp,open,high,low,close,volume` |
| identity | a per-file SHA-256 list, a manifest and a dataset hash written at acquisition, registered in `docs/datasets/registry.json` |
| governance | the owner's decision; a new dataset ID; no reuse of the lost ID |
