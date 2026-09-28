# Datasheet — `h0014-daily-features-decade-230`

*Registered 2026-09-24 in [registry.json](registry.json). **Derived features,
not price data.** Historical in-sample. Governance record only: nothing here
is an H-0014 result, and none was computed to produce it.*

## Identity

| field | value |
|---|---|
| dataset ID | `h0014-daily-features-decade-230` |
| dataset SHA-256 (the registry convention: `<file>\t<size>\t<sha256>\n`) | `7fbf76458b559695c4686c651de0600234417f98afa25a36df0ab14a8f548e57` |
| file | `h0014-daily-features.json`, 72,936,335 bytes |
| file SHA-256 | `b653ac1fa835e81fb07b6779916c00c2eefc11b1a13bbf1218c0e561f7504030` ([checksum list](h0014-daily-features-decade-230.sha256)) |
| verified copy | `data/research/h0014-daily-features-decade-230/` — gitignored, read-only, and its modification time is preserved from the original |
| original | the Claude session scratchpad, `…/scratchpad/h0014-daily-features.json`. Created and modified 2026-09-21T06:30:10Z (2026-09-20 23:30:10 local). **Kept, untouched**: its hash, size and modification time were identical before and after the check and the copy |

## Content

| field | value |
|---|---|
| structure | JSON `{symbol: {date: [d_rsi, d_atrfrac, d_sma200, d_mom21, d_dd252, d_advr]}}` |
| symbols | 230, sorted, `AAOI` … `XRT` — every file of the decade dataset |
| rows (symbol × date) | 531,724 = 582,324 bars − 220 warm-up bars × 230 symbols |
| dates | 2016-11-15 … 2026-09-04; 2,464 distinct; 390 … 2,464 per symbol; sorted within every symbol |
| values | 6 per row, all `float`, no nulls, no NaN |

## How it is built

`build_daily_cache()` in `scripts/h0014_analyse.py`:
- **Commit:** `90dc4bdd9edee38814b0c7e5ef3a62296aba8ba4`, the file's only
  commit.
- **Function source SHA-256:**
  `fd2624869381c8287b936bc326f7d09b696a1e987157e081931b004516be3413`.
  It is unchanged in the working tree.

**Inputs:**
- Every `*.csv` of the decade dataset: split-adjusted, not
  dividend-adjusted, read with `csv.DictReader`.
- `event_aware_trader.indicators.rsi` and `wilder_atr`, last changed
  2026-09-05.
- `event_aware_trader.data.Bar`, last changed 2026-09-14.
- Neither `src/` file has changed since the cache was written.

**Information boundary:** the features for session D use bars strictly before
D (`prev = bars[:i]`), which is D−1 information. This is the registration's
"daily features use closes through D-1 ONLY".

**Rows and lookbacks:**
- Rows start at bar index 220, the 221st bar.
- The lookbacks run over the full prior history, with no 400-bar window:
  - `d_rsi`: Wilder RSI(14);
  - `d_atrfrac`: Wilder ATR(14) ÷ the last close;
  - `d_sma200`: the last close ÷ its 200-bar mean − 1;
  - `d_mom21`: the last close ÷ the close 21 sessions earlier − 1;
  - `d_dd252`: the last close ÷ the highest close of up to 252 bars − 1;
  - `d_advr`: the mean of close × volume over 20 bars.

## Reproduction check — 2026-09-24: **A, REPRODUCIBLE, exactly**

**Method:**
- The committed function body, taken verbatim from `90dc4bd`, was executed
  in memory, with `DEEP` bound to the gate-verified decade dataset
  (`935fed79…73d4a7`).
- `CACHE` was bound to an in-memory stand-in that reports "does not exist"
  and captures, instead of writing, the text the function would save.
- An audit hook blocked every file write for the whole process. None was
  attempted.
- No model was fitted, and no IC, P&L, trade simulation or H-0014 analysis
  ran. Run time: 350 seconds.

| comparison | result |
|---|---|
| bytes the function would have written vs the original file | **identical** — 72,936,335 = 72,936,335; SHA-256 `b653ac1f…4030` = `b653ac1f…4030` |
| symbols; their order | 230 = 230; identical |
| (symbol, date) rows; date sets and order per symbol | 531,724 = 531,724; 0 symbols differ |
| values compared, field by field, independently of the byte check | 3,190,344 |
| value mismatches, per feature | 0, 0, 0, 0, 0, 0 |
| type mismatches; nulls; NaN | 0; 0; 0 |
| largest absolute difference; largest ULP distance | 0.0; 0 |
| first row and last row, every symbol | equal |
| first row is bar 220, every symbol | yes |
| latest date | 2026-09-04 (the dataset's end; nothing after the 2026-09-11 freeze) |

**Tolerance: none was needed.** The match is exact, bit for bit.

**What this establishes:** the cache is exactly what the committed code
produces from the verified decade dataset. It is not a record of *when* the
original run happened, but its content no longer depends on the scratchpad.

## Use

`scripts/h0014_analyse.py` reads the cache as `CACHE =
dataset_file(verify_dataset("h0014-daily-features-decade-230", <pinned
hash>), "h0014-daily-features.json")`:
- verified at import, and fail-closed;
- `h0014_ic_yearly` gets it through `build_daily_cache()`;
- because the verified copy always exists, the function's write branch never
  runs;
- the scratchpad original is no longer read.

The H-0014 sealed result (`docs/phase5/h0014-results.json`, seal
`3acb220e…`) is **unchanged, and was not re-run**. It also depends on the
intraday `snapshots/`, which were scratchpad-only when this was written. **Later on
2026-09-24** they were preserved byte-identically as `h0014-intraday-snapshots-230`
([intraday preservation](intraday-preservation-2026-09-24.md)): input data is preserved
and hash-verifiable, and the result has not been re-run.
