# H-0014 raw-bar reproduction — governance plan

*2026-09-24. **PLAN ONLY.** Nothing has been downloaded, run, registered or
modified. The intraday preservation task is complete. Its record is
[2026-09-24-intraday-data-preservation-audit.md](2026-09-24-intraday-data-preservation-audit.md).
Labels: **confirmed** — read from committed code, git history, preserved
manifests or the verified data; **inferred** — reasoned from that evidence;
**unknown** — not recorded anywhere in the repository.*

**This plan cannot run as specified without authorization.** §9 lists nine
items, eight of which need a decision before acquisition. Three of them
conflict with how the task was specified:
- the coverage conflict (§9 #4);
- post-freeze bars (§9 #3);
- the replay harness (§9 #2).

---

## Revision 2 — final execution plan (2026-09-24, late)

**Status: BLOCKED ON CREDENTIALS. Nothing has been requested.**
- **The check:** both variable names are present in User scope, but
  `HKCU\Environment` was last written at **2026-09-09T00:14:52Z**, before the
  **2026-09-19T18:47:20Z** exposure. Checked 2026-09-25T04:16:52Z, by names
  and metadata only.
- **Gate for any vendor request:**
  1. the owner rotates the key in the Alpaca dashboard and re-runs
     `scripts/windows/setup-keys.ps1`;
  2. metadata shows a write after the exposure (necessary, not sufficient);
  3. the owner confirms that new keys were generated.
- **Metadata is not proof of authentication.**

**Label:** every reacquired byte, file, log line and record carries
**"REACQUIRED — NOT THE ORIGINAL H-0014 RAW DATA"**, permanently.

### R2.1 Calibration — the only phase authorised, and only after rotation

**Sample** (a fixed rule, decided before any request, so nothing can be
cherry-picked):
- Take the 459 **rule-exit** sessions (221 reverted and 238 time exits of
  `docs/phase5/h0011-cache.json` BASELINE) whose preserved file is in
  `intraday-exit-sessions-5min-698`, ordered by (exit date, symbol).
- Choose the **first rule exit of each calendar year 2016 … 2026** (11
  sessions) plus **the latest rule exit overall** (1). That is 12 sessions.
  If the latest is already chosen, take the next latest.
- **Stop exits (239) are excluded:** their acquisition code is not in the
  repository.

**Request** — exactly the committed `scripts/intraday_exits_acquire.py`
`fetch()`:
- `GET https://data.alpaca.markets/v2/stocks/bars?symbols=<symbol as recorded
  in h0011-cache, url-quoted, no vendor mapping>&timeframe=5Min&start=<exit
  date>&end=<exit date + 1 day>&limit=10000&adjustment=split`;
- credential headers by name, timeout 60 s, **one attempt, no retry, no
  pagination** — exactly as committed;
- **no `feed` parameter**;
- the only substitution is a wrapper around `urllib.request.urlopen` that
  saves the **exact response bytes** before the committed code parses them.

**Recorded per request, never including credentials:**
- the URL;
- UTC send and receive times;
- HTTP status;
- every response header except any that echoes credentials (for example
  `Date`, `Content-Type`, `Content-Length`, a request ID if present);
- body length and SHA-256;
- `next_page_token`.

The historical `next_page_token` was `null` in all 698 files. A non-null value
now is recorded as a structural difference, and is **not** followed.

**Location:** `data/_h0014-calibration/<UTC date>/` (gitignored, not
registered), with a README carrying the label.

**A1 — the serialised payload.** The historical procedure was
`write_text(json.dumps(payload), encoding="utf-8")`, where
`payload = json.loads(r.read().decode("utf-8"))`.
- Apply exactly that to the new body, in memory.
- Compare the result byte for byte with the preserved file (read from the
  verified dataset).
- **The historical HTTP bytes do not exist, so no claim is made about them.**

**A2 — the bars.** Parse both, then compare:
- **Structure:** the top-level keys; the symbol key(s); the bar count;
- **Rows:** the ordered timestamp sequence; missing and extra rows by
  timestamp;
- **Fields**, per bar: every persisted field (`t, o, h, l, c, v, n, vw` as
  present) — exact value and type; nulls;
- **Paging:** `next_page_token`.

**No tolerance of any kind.**

| class | rule |
|---|---|
| **A — exact** | all 12: A1 byte-equal **and** A2 identical |
| **B — structurally valid, different** | all 12 obtained and usable; at least one byte or value differs |
| **C — incomplete or failed** | any of the 12 not obtained completely (HTTP error, truncated body, missing symbol) |
| **D — indeterminate** | the comparison cannot establish reproducibility: a preserved file fails the gate, or the response format changed so that neither A1 nor A2 is meaningful |

**What A means:** only "current vendor acquisition reproduced the preserved
representation for the tested sample". It does not mean the original H-0014
raw data has been recovered.

**Stop after classification.**
- **B, C or D:** record the limitation. The preserved snapshots remain the
  surviving evidence; nothing is repaired or re-run.
- **A:** it only allows the full reacquisition to be *separately*
  authorised.

### R2.2 The full reacquisition — the plan only (needs its own authorization after an A)

| # | item | final plan | where |
|---|---|---|---|
| 1 | universe | the 230 stems of the verified decade dataset (`AAOI` … `XRT`). `BRK-B` is requested as `BRK.B`, the committed `VENDOR` mapping | §2.2 |
| 2 | snapshot sessions | 2016-11-15 … 2026-08-07. 525,712 symbol-sessions; 370 … 2,444 per symbol; per-symbol first and last sessions in the preserved manifest | §2.2 |
| 3 | request windows | six per symbol, committed and fixed: `2016-01-01→2018-01-01`, `→2020-01-01`, `→2022-01-01`, `→2024-01-01`, `→2026-01-01`, `2026-01-01→2026-09-19`. 1,380 initial requests | §2.2 |
| 4 | warm-up | each snapshot session needs the 20 prior sessions' intraday bars (trailing volume profile), and 220 daily bars of history. The exact windows cover both | §2.2 |
| 5 | pagination | follow `next_page_token` with `limit=10000`. Vendor boundaries are opaque, and the originals were not recorded, so page structure is **not** comparable | §2.4 |
| 6 | raw file count | one file per response. **Not knowable in advance**: at least 1,380, estimated 7,000–12,000 | §3 |
| 7 | storage | about 7–13 GB raw, plus 3.03 GB of regenerated snapshots. Reserve 20 GB (40.1 GB free on 2026-09-24); abort below 10 GB | §3 |
| 8 | post-freeze observations | **yes**, with the exact shape: 2026-09-11 … 09-18 (6 sessions, embargo window, not Clean OOS). Flagged in the registry; no research may read them. The alternative (end 2026-09-05) deviates from the recorded shape and needs its own authorization | §2.4, §9 #3 |
| 9 | forward-outcome columns | regeneration recomputes each row's `fwd5/10/20`, `spy_fwd5/10/20`, `mfe20`, `mae20` from the decade daily data. They are compared cell by cell only, **never aggregated** | §9 #5 |
| 10 | registration | `h0014-5min-bars-reacquired-<YYYYMMDD>-230` at `data/research/…`, flat, read-only, gate-verified. Registered **as reacquired raw data, not as an experiment input** | §4 |
| 11 | provenance | the permanent label above. Request log in the dataset. Feed stated as "not sent; vendor default at <date>"; historical feed inferred SIP | §2.4, §4 |
| 12 | retention | the raw data is kept and registered. The regenerated snapshots stay in `data/_h0014-regeneration/`, pending the owner's decision. The calibration work output is kept with its report | §4, §9 #6 |
| 13 | failure and retry | the committed `fetch` makes 4 attempts per page with 2/4/6 s back-off; after that the symbol is abandoned. Only incomplete symbols are re-requested later, and every attempt is logged. A symbol enters the dataset only when all six windows are complete (via staging) | §5 P1 |
| 14 | hashing | the SHA-256 of every response body at receipt, a manifest (sorted), a `sha256sum` list, and a dataset hash under the gate's rule; `verify_dataset` passes before any regeneration | §5 P2 |
| 15 | production isolation | only `https://data.alpaca.markets/v2/stocks/bars` is allowed; no broker or `src/` import on the money path; nothing in `src/` or the scheduled wrappers references `data/research/`. The fingerprint and learned switches are checked before and after | §7 |
| 16 | isolation from sealed experiments | no H-0014 analysis, IC or model. `h0014-results.json`, the seal, the registration and the preserved snapshots are hash-checked before and after. Regeneration writes only to a new, empty folder, with an audit hook blocking any other write | §5 P3, §7 |

---

## 1. The task, as authorised in principle

1. Acquire a **new, separately identified** copy of 5-minute bars for the 230
   H-0014 symbols, using the committed request shape.
2. Store it under a new `data/research/` dataset identity.
3. Use the committed snapshot builder **only** to test whether that copy
   regenerates the **preserved** snapshots.
4. Compare byte for byte; if that fails, report a structured field-level
   difference.
5. Classify the outcome A / B / C / D.

**Not to be done:**
- no H-0014 analysis, IC, model or result statistic;
- no change to the preserved datasets, sealed outputs, runners, `src/`,
  models or Clean OOS;
- no repair of anything.

## 2. Facts established read-only

### 2.1 The committed builder — `scripts/h0014_acquire_snapshots.py`

| fact | label |
|---|---|
| **Two commits:** `6036727` (2026-09-20 16:49:19Z) and `b6a68de` (2026-09-21 00:44:35Z). They differ **only** in `main()`'s scheduling block (the `H0014_LIMIT` chunk size). Every other definition is identical: `fetch`, `sessionise`, `rvol`, `load_spy`, `to_et`, `headers`, `VENDOR`, `SNAPSHOTS`, `LABELS`, `COLS`, `OPEN_M` | confirmed |
| The working tree equals `b6a68de` except for the module-level path lookup (`_scratch`, removed in the 2026-09-24 migration) | confirmed |
| **Which code wrote which file.** 2 files (`AAPL.csv` 16:45:15Z, `AAOI.csv`) predate the first commit, so uncommitted code wrote them. 58 files were written between the two commits, 170 after `b6a68de` | confirmed (file times) |
| The uncommitted code that wrote AAPL and AAOI equals `6036727`, committed four minutes later | **inferred**, not provable |
| **The builder keeps no raw bars.** It fetches over the network, reduces to snapshot rows, writes one CSV per symbol and discards the bars. It cannot read raw bars from disk | confirmed |
| **The builder records no dataset use.** It writes no row to `docs/dataset-uses.jsonl` | confirmed |

### 2.2 Symbols and sessions

| fact | value | label |
|---|---|---|
| symbols | 230 = every CSV stem of the verified decade dataset, `AAOI` … `XRT`. Sent to the vendor as-is except `BRK-B` → `BRK.B` (`VENDOR`) | confirmed |
| request windows per symbol (fixed, identical for every symbol) | `2016-01-01→2018-01-01`, `2018-01-01→2020-01-01`, `2020-01-01→2022-01-01`, `2022-01-01→2024-01-01`, `2024-01-01→2026-01-01`, **`2026-01-01→2026-09-19`** | confirmed |
| initial requests | **1,380** (230 × 6) | confirmed |
| sessions the builder uses | decade calendar index 220 … len−21 = **2016-11-15 … 2026-08-07** (2,444 sessions). Each snapshot also needs the **20 prior sessions' intraday bars** (the trailing volume profile) | confirmed (code) |
| preserved snapshot sessions | 525,712 symbol-sessions, 5,252,811 rows. 370 … 2,444 sessions per symbol. First session 2016-11-15 … 2025-02-18 (by listing date), last 2026-08-07 for all. 2,682 sessions have fewer than 10 snapshot rows | confirmed (read from the verified copy's `session` and `snap` columns only) |
| extra days in the exact windows | before each symbol's first needed session; **2026-09-08 … 2026-09-18** after the decade data ends, of which **2026-09-11, 14, 15, 16, 17, 18 fall after the 2026-09-11 freeze** | confirmed |

### 2.3 The request, exactly as committed

- **Endpoint:** `GET https://data.alpaca.markets/v2/stocks/bars`
- **Query:** `symbols=<vendor symbol>&timeframe=5Min&start=<YYYY-MM-DD>&end=<YYYY-MM-DD>&limit=10000&adjustment=split`, with `&page_token=<token>` appended on continuation pages.
- **Headers:** `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY` (read from the environment by **name**), plus `User-Agent: market-bot-research/1.0`.
- **Transport:** timeout 120 s, `ssl.create_default_context()`.
- **Retries:** up to 4 attempts per page, sleeping 2, 4, then 6 s. After the 4th failure the symbol is abandoned (`FETCH FAILED`) and is picked up again by a later run.
- **Pacing:** 0.25 s between pages, 0.2 s between windows.
- **Not sent:** `feed`, `asof`, `sort`, `currency`.

### 2.4 Answers to the pre-acquisition questions

| question | answer | label |
|---|---|---|
| historical feed | **Not explicit**: no request sets `feed`, so the vendor default for the account at request time applied. The H-0013 report (2026-09-20) records "the data plan refuses 'recent SIP data' for an end date of today or later". That implies the default was **SIP** under a plan that restricts recent SIP data | **inferred** SIP; explicitly **unknown** |
| pagination | **The code side is deterministic and fully specified** (loop on `next_page_token`, `limit=10000`). **The vendor side is not fully understood:** page boundaries and tokens are vendor-generated and opaque, and **the original tokens and page structure were never recorded**. Page structure cannot be compared; only content can | code: confirmed; vendor: **unknown** |
| original acquisition time | **Per symbol, approximately only.** Each CSV was written seconds to minutes after that symbol's last page: 2026-09-20T16:45:15Z (AAPL) … 2026-09-21T06:17:44Z (XRT), per-file times in the preserved manifest. No request log, response `Date` header or request ID survives | file times confirmed; link to fetch time **inferred** |
| post-freeze observations | **Yes, if the exact request shape is used.** The last window ends 2026-09-19 and returns bars through 2026-09-18 — six sessions after the 2026-09-11 freeze, all in the embargo window. They are **not Clean OOS**, which begins with the first clean session, projected 2026-10-12. The original run received the same bars in memory, and the builder discards them (they are not in the decade calendar) | confirmed |
| interpreter | the `.venv` (created 2026-09-01) and the system Python are both **3.11.9**. Which one ran the original is unrecorded, but both are the same version | versions confirmed; interpreter used **unknown** |
| other regeneration inputs | the decade dataset (verified; unmodified since 2026-09-08) and the SPY store (verified copy; source files written 2026-09-20 06:18–06:23Z, before the run began, and unchanged since). Both are byte-identical to what the original run read | **inferred** from file times and hashes |

## 3. Expected sizes

**Raw data — estimate.** Roughly 584,000 symbol-sessions are requested, at
100 to 185 five-minute bars each, including extended hours:
- the preserved exit sessions, fetched with the same request shape, average
  182.6 bars per session (median 173);
- the SPY store averages about 185.

At **120.6 bytes per bar** (the preserved exit payloads) that gives **about
7–13 GB**, in about 7,000–12,000 HTTP responses. The builder's docstring says
"~48M bars and ~2.9GB", but that assumed regular trading hours only, which the
request does not restrict to.

**Raw files — not exactly knowable in advance.** One file per vendor response
means the count depends on the vendor's pagination. The floor is 1,380, one
per window; the estimate is 7,000–12,000.

**Regenerated snapshots — exact expectation.** 230 CSVs named `<SYMBOL>.csv`,
with the same 35-column header, 5,252,811 rows and 3,029,641,196 bytes. Each
must match the per-file SHA-256 in
`docs/datasets/h0014-intraday-snapshots-230.manifest.json`.

**Disk:**
- required: up to ~13 GB raw, plus 3.03 GB of regenerated snapshots and
  margin — **reserve 20 GB**;
- currently free: **40,068,255,744 bytes (~40.1 GB)** on C:;
- rule: abort acquisition if free space falls below 10 GB.

**Time:** the original run took 13.5 h of wall-clock time, in chunks. The
estimate is several hours of requests at the committed pacing, run as a
resumable background task.

## 4. Identities and paths

| item | name and path | registered? |
|---|---|---|
| reacquired raw bars | **`h0014-5min-bars-reacquired-<YYYYMMDD>-230`** at `data/research/h0014-5min-bars-reacquired-<YYYYMMDD>-230/`, where `<YYYYMMDD>` is the UTC date acquisition starts. Flat directory (what the gate verifies). One file per vendor response, `<SYMBOL>__<start>__<end>__p<NNN>.json`, holding the **exact response bytes**. Plus `_requests.jsonl`: URL without credentials, page, HTTP status, response `Date` and request-ID headers, receive time, bytes, SHA-256 | yes, after verification: checksum list, manifest, registry entry, datasheet. **Kind: "raw vendor payload — REACQUIRED <date> with the committed request shape; NOT the original H-0014 raw data (never retained)"** |
| staging (a symbol moves into the dataset only when all six windows are complete) | `data/_h0014-regeneration/staging/` (gitignored) | no; emptied once every symbol is complete |
| regenerated snapshots | `data/_h0014-regeneration/<dataset-id>/` (gitignored work area). **Never** under `data/research/h0014-intraday-snapshots-230/` | no; per-file hashes recorded in the report. Retention is your decision (§9 #6) |
| optional calibration (§5 P0) | `data/_h0014-regeneration/p0-calibration-<YYYYMMDD>/` | no |

## 5. Procedure (after authorization)

**P0 — calibration: recommended, and needs separate approval (§9 #9).**
- **What:** re-request about 12 preserved exit sessions (stratified by year
  and liquidity; the list fixed before any request) with
  `intraday_exits_acquire.py`'s committed request (`start=<day>`,
  `end=<day+1>`, same shape).
- **Compare:** bar by bar (`t, o, h, l, c, v, n, vw`) with the preserved
  `intraday-exit-sessions-5min-698` files. Those files are re-serialised JSON
  (`json.dumps`), not raw bytes, so the comparison is of bars, not bytes.
- **Why:** those files were fetched on 2026-09-20, about 11 hours before the
  H-0014 run, by the same account with the same default feed.
- **If they differ:** stop before the multi-hour acquisition. The vendor's
  current answer provably differs from 2026-09-20, so the original response
  cannot be reconstructed (D). Report, and go no further without new
  authorization.

**P1 — acquisition (recorder).**
1. Execute the **committed `b6a68de` source text**, verbatim, in a fresh
   process, and call its own `fetch(sym, start, end)` for the six committed
   windows, in the committed order: symbols sorted, windows ascending.
2. The only substitution is a recording wrapper around
   `urllib.request.urlopen`. It saves each response body **byte-exact**
   before the committed code decodes it, and refuses any URL other than
   `https://data.alpaca.markets/v2/stocks/bars`.
3. Credentials are read by name and never logged. HTTP errors and retries
   are logged, not stored as data.
4. A symbol moves from staging into the dataset only when all six windows
   are complete. A failed symbol may be re-requested in a later run, as the
   original chunked run did, and every attempt is logged.

**P2 — verification and registration.**
1. Per-file SHA-256 hashes, a manifest, a checksum list and the dataset hash
   (gate convention).
2. Registry entry, datasheet, read-only.
3. `research_gate.verify_dataset` passes.

**P3 — regeneration (replay; no network).**
1. In a fresh process, execute the committed `b6a68de` source verbatim.
2. Rebind only its module globals:
   - `DEEP` → the verified decade dataset;
   - `SPYDIR` → the verified `spy-5min-2016-2026-quarterly-43`;
   - `SNAP` → a **new, empty** directory under `data/_h0014-regeneration/`.
3. Replace `urllib.request.urlopen` with a replay that serves the recorded
   bodies by exact URL, including page tokens, and raises on any unrecorded
   URL.
4. Block all sockets.
5. Set credential **placeholder** names so the committed `headers()` does not
   refuse; they never leave the process.
6. Replace `time.sleep` with a no-op. It has no effect on output.
7. Require `H0014_ONLY` and `H0014_LIMIT` to be unset.
8. Run the committed `main()` unchanged.
9. An audit hook blocks any write outside the new output directory.
10. Replay twice: the two outputs must be byte-identical (a determinism
    control).

**P4 — comparison.** Only difference magnitudes are reported, never an
aggregate of any column.
1. **Byte level:** each regenerated file's SHA-256 against the preserved
   manifest.
2. **If any file differs, a field-level comparison:**
   - file presence;
   - the header;
   - the ordered `(session, snap)` key sequence;
   - then cell by cell for all 35 columns, separating **representation-only**
     differences (the cells parse to the same number) from **value**
     differences;
   - per column: the count of differing cells, the first difference, and the
     largest absolute and relative difference.

**P5 — record.** A report and datasheet; the registry updated for the
reacquired dataset only; the knowledge base updated with established facts
only.

## 6. Outcome classes (fixed before any data is seen)

| class | rule | what gets recorded |
|---|---|---|
| **A — exact reproduction** | 230/230 regenerated files byte-identical to the preserved snapshots, and the two replays identical | "Reacquired bars (<date>) regenerate the preserved H-0014 snapshots exactly with the committed builder." **The raw dataset is still labelled *reacquired*, never *original*.** The snapshots use only regular-hours bars up to 15:30 ET (open, high, low, close, volume), so A says nothing about extended-hours bars, `n`, `vw` or page structure |
| **B — structurally valid, byte-different** | 230/230 files present; identical headers; identical ordered `(session, snap)` keys in every file; at least one cell differs (sub-classes B1 representation-only, B2 value difference). **No tolerance promotes B to A** | "The historical H-0014 raw input is unavailable; the preserved derived snapshots remain the surviving H-0014 evidence." The structured difference is attached. No repair, no re-run |
| **C — incomplete or failed** | any symbol's acquisition incomplete after the permitted re-requests; any regenerated file missing or extra; a header or key-sequence difference; the builder failing on a symbol; or the two replays differing | same statement as B, plus the failure detail |
| **D — indeterminate** | the original vendor response cannot be reconstructed or tested: P0 shows vendor drift; the vendor refuses the committed request shape (API or plan change); or a preserved input (decade, SPY, snapshots) fails verification | same statement; the stop point and its cause |

In every class, `docs/phase5/h0014-results.json`, the seal, the registration
and `h0014-intraday-snapshots-230` stay exactly as they are.

## 7. Guarantees and how each is enforced

| guarantee | mechanism |
|---|---|
| **The preserved datasets are untouched** | they are read-only files. The gate verifies all six before and after. The new dataset ID must not already exist. Output directories must be new and empty and outside every registered dataset path. An audit hook blocks writes elsewhere. No preserved path is ever an output target |
| **The scratchpad is untouched** | nothing reads its stores. The committed source's module-level lookup lists scratchpad directories when it is executed (read-only), and the harness then rebinds every path. The tree fingerprint (`dd147953…`) is re-checked afterwards |
| **The money path is not entered** | the new scripts are research-side; nothing in `src/` or the scheduled wrappers references `data/research/`, `research_gate` or the new scripts (checked 2026-09-24: none). The only allowed URL is the market-data bars endpoint — no trading or account endpoint, no broker import, no order. The fingerprint and both learned-model switches are re-checked before and after |
| **No experiment result is recomputed or changed** | `h0014_analyse`, `run_h0014`, `h0014_validate` and `h0014_ic_yearly` are not run; there is no IC, model or statistic. Regeneration necessarily recomputes each row's forward-outcome cells (`fwd5/10/20`, `spy_fwd5/10/20`, `mfe20`, `mae20`), which are part of the snapshot table (§9 #5). They are compared cell by cell only, never aggregated. The sealed files' hashes are re-checked afterwards |
| **Clean OOS untouched** | the request windows end 2026-09-19, before any clean session exists. The clean record, chain, freeze, embargo and benchmark guard are re-checked |
| **Ledgers unchanged** | the builder records no dataset use, and the new scripts add none. Only the dataset registry gains the new entry |

## 8. What this plan does not claim

- An exact reproduction would **not** prove the reacquired bytes equal the
  2026-09-20/21 vendor responses.
- **Any** outcome leaves H-0014's sealed result exactly as recorded, and
  unreproduced.

## 9. Authorization required before any acquisition

| # | decision | why it is needed | recommendation |
|---|---|---|---|
| 1 | **Network access to the vendor with the account's market-data credentials** | the task makes about 7,000–12,000 authenticated requests. Earlier in this programme an Alpaca secret was exposed in a transcript and flagged for rotation; **whether it was rotated is not established here** | confirm the credential now in the environment is the rotated one; checked by name and presence only |
| 2 | **Two new research-side scripts** (the recorder of §5 P1; replay and comparison of §5 P3–P4) that execute the committed builder **unmodified** but substitute its network layer (record, then replay), rebind `DEEP`, `SPYDIR` and `SNAP`, use credential placeholders during replay, and make `time.sleep` a no-op | the builder cannot read raw data from disk. This is input/output substitution, not a code change, but it goes beyond "use the committed code only" as literally stated | approve, with the controls in §5 and §7 |
| 3 | **Post-freeze bars** in the new dataset | the exact request shape returns bars through 2026-09-18, six sessions after the freeze (embargo window, not Clean OOS). The alternative — ending the last window at 2026-09-05 — **deviates from the recorded request shape** and changes pagination | **(a)** store exactly as returned, with the post-freeze sessions flagged in the registry and datasheet and a rule that no research reads them; or **(b)** authorise the deviation |
| 4 | **Coverage: "exactly the preserved snapshot sessions" versus "the exact request shape"** | the two are incompatible. The committed shape fetches fixed windows (2016-01-01 … 2026-09-19), a superset. The builder also needs each snapshot's 20 prior intraday sessions. Fetching only the snapshot sessions would change the regenerated values and the request shape | fetch the exact committed windows (a superset of the snapshot sessions) |
| 5 | **Forward-outcome cells recomputed** during regeneration (per row, from the decade daily data) | they are columns of the preserved derived table; comparing the table recomputes them | accept as data regeneration, compared cell by cell only, never summarised |
| 6 | **Storage and retention**: up to ~13 GB of new raw data (gitignored, no off-machine backup) plus 3.03 GB of regenerated work output | disk and backup policy | approve; decide afterwards whether the regenerated output is kept |
| 7 | **Long-running background acquisition**, with re-requests of failed symbols | rate limits may abandon symbols, and each re-request is a new vendor call | approve re-requests, all logged |
| 8 | **Registry entry** for the reacquired dataset | an additive governance record | already part of the task as specified; confirm |
| 9 | **P0 calibration** (about 12 extra requests) | not part of the task as specified | recommended as a go / no-go gate before the full run |

Until these are decided, **nothing is acquired.**
