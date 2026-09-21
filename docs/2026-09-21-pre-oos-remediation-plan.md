# Pre-OOS remediation plan

*READ-ONLY analysis. Nothing implemented, nothing registered, no strategy
change, no fingerprint change. Every claim traced to source or live state.*

---

## 1. FINGERPRINT / 15m RUNNER MISMATCH — decision analysis

### What actually consumes the 15-minute bars

Traced through `run_once`. Under `entry_rule="mean_reversion"`,
`bars_by_symbol` (the `--interval` fetch) is read at exactly three places, and
in all three **only its presence and length matter, never its values**:

| site | use |
|---|---|
| `autotrade.py:1394` | position management — `if not bars: continue` (a held name with no bars is skipped entirely) |
| `autotrade.py:1705` | entry gate — `if not bars or len(bars) < strategy.minimum_history` |
| `autotrade.py:1823` | order placement — `if not bars: continue` |

Every number the rule uses comes from elsewhere:

- signal → `daily_bars(symbol)` (`:1712`), which reads the daily price files
  *specifically* so "a rule calibrated in days must not be handed
  fifteen-minute candles";
- partial session bar → `_todays_bars()` (`:644`), which makes its **own**
  `fetch_alpaca_equity_bars(..., days=4, include_today=True)` at the default
  `interval="1d"` — it does **not** depend on `config.interval`;
- stop reconstruction ATR → `series_for_atr = daily_bars(symbol)` (`:1451`),
  added because a 15-minute ATR made the stop "about NINE TIMES too tight";
- conviction → `daily_bars(candidate.symbol)` (`:1876`).

The only consumer of 15m *values* is the trailing-stop ATR at `:1399`, whose
own comment says "Only the TREND path needs the cycle's ATR" — dead code while
`entry_rule="mean_reversion"`.

### Option A — change the runner to `1d`

> **A naive Option A silently stops all trading. This is the most dangerous
> available fix and must be stated first.**

`--period` maps to a day count: `{"1mo": 35, … "2y": 760}`. Today the runner
passes `--interval 15m --period 1mo` → 35 days of 15-minute bars ≈ 624 bars
per symbol, comfortably over the gate.

Changing **only** `--interval 1d` leaves `--period 1mo` → 35 calendar days
≈ **24 daily bars**, against `strategy.minimum_history = 50` (verified: 50 for
both `1d` and `15m`; it does **not** scale with interval). Every symbol then
fails the gate at all three sites — **no entries, no exit management, no
orders** — and the failure is silent, because the gate is a `continue`.

**Correct Option A is to stop passing both flags**, so the CLI defaults apply
(`interval="1d"`, `period="2y"` → 760 days ≈ 520 daily bars).

| question | answer |
|---|---|
| What behaviour changes? | `bars_by_symbol` becomes daily. Used only as a presence/length gate, so no rule input changes |
| Does candidate eligibility change? | **Formally yes, economically inert.** The gate needs ≥50 bars; only names with <50 *daily* bars but ≥50 *15m* bars differ — i.e. listings younger than ~50 sessions. `MeanReversionConfig.minimum_history = 215`, so such names **cannot emit a BUY under either setting**. Held names necessarily have ≥215 daily bars, so exit management is unaffected |
| Historical equivalence still valid? | **Yes.** The simulator never reads `AutoTradeConfig.interval`; `production_report` uses `PRODUCTION_CANDIDATE` + `MeanReversionConfig`. Baseline **+58.5889000000% / 698** is untouched |
| Still the same candidate? | **Yes.** No economic rule, parameter, stop, exit or sizing changes |
| Prior evidence invalidated? | **No.** Nothing in the research record depends on the live `interval` |
| Operational dependency on 15m? | **None found for the MR path.** The partial bar, the ATR, the signal, the stop and conviction all fetch or read daily independently |
| Fingerprint result | **Restores `da22011e…` exactly.** `period` is not a fingerprinted field, so even an explicit `--period 2y` is digest-neutral |

**Required before switching:** a dry-run cycle comparing the candidate set
under `15m/1mo` against `1d/2y`. The inertness above is *analysed*, not
*measured*, and the three gates are `continue` statements that fail silently.

### Option B — re-issue the fingerprint over the live configuration

| question | answer |
|---|---|
| What must be fingerprinted? | To be honest rather than merely different, Option B cannot stop at `interval`. It must add `period`, `asset_class`, `dry_run`, `capital_base`, `capital_baseline_equity`, a digest of `universe`, and `StrategyConfig` (incl. `exit_mode`). `capital_base` matters most: it scales sizing **and both loss guards** together |
| Resulting digest | **Not `569a8da7…`.** That value is only "defaults with `interval='15m'`". A correct Option B produces a third, currently uncomputed digest |
| Strategy change or governance correction? | **Governance correction.** No economic rule moves. But the digest *is* the candidate's identity in this project, so re-issuing it is a governance event, not a silent edit |
| What becomes stale? | Every citation of `da22011e…`. Worse — **~8 research scripts hard-code `FP = "da22011e…"` and `return 2` on mismatch** (`run_h0011/12/13`, `h0014_analyse`, `h0016_probe_cash`, `h0019_measure`, `h0019_controls`, `run_h0020`, `run_h0021`, `phase4_checkpoint`). They would refuse to run, so the historical record would become non-reproducible until each is updated |
| Preserving equivalence | An additive mapping row: old digest, new digest, date, reason, and the statement that no economic parameter changed |
| New registration required? | **No.** There is no hypothesis and no configuration search. Recording it as an *experiment* would be actively harmful — see §8 |

### Option C — derive the fingerprint from the configuration actually used

The defect is structural: `frozen_fingerprint()` **recomputes from source
defaults** instead of **observing the run**. Option C closes the class, not
the instance.

Three facts make it cheap:

1. `run_once` already returns `{"interval": config.interval, "dry_run": …,
   "asset_class": …}` (`autotrade.py:2085-2090`) and writes its result to the
   audit log the recorder already reads.
2. **`append_session(observation, path, expected_fingerprint=None)` already
   accepts an expected fingerprint** (`forward.py:160`) — the plumbing exists
   and is unused.
3. The digest body is a pure function of config objects; it needs a parameter,
   not a rewrite.

Shape: a `config_digest(mr, policy, costs, live, candidate)` helper; `run_once`
emits the digest of the config it was handed; the recorder reads it and passes
it as `expected_fingerprint`; the declared frozen constant stays the reference
that research scripts assert against. Divergence then becomes **structurally
impossible to record silently**, because the stamp is produced by the process
that traded.

### RECOMMENDED GOVERNANCE CHOICE: **C, with A as its precondition**

In reproducibility terms, not performance:

- **A alone** restores the digest but leaves the mechanism unguarded. The same
  defect recurs the next time a runner flag is added, and nothing would detect
  it. It fixes the instance.
- **B alone** blesses the divergence: it makes the published digest describe
  today's runner, breaks ~8 scripts' reproducibility assertions, invalidates
  every citation, and still leaves the stamp a *recomputation of source*
  rather than an *observation of the run*. It buys no reproducibility.
- **C** makes the recorded fingerprint evidence about what happened rather
  than a restatement of what the file says. That is the property OOS needs.
  But C alone would stamp a digest that no existing report cites.

**A then C** ends with the runner on the declared configuration, the effective
digest equal to `da22011e…`, every existing citation still valid, and the
mechanism guarded. A is reversible and digest-neutral; C is additive.

---

## 2. BENCHMARK MISMATCH — the correction

The strategy side is unambiguously **total return**: dividends arrive as cash
in account equity, and the observation carries `dividends_received`. So the
only question is what SPY series to compare it against.

| option | verdict |
|---|---|
| **A. total vs total** | **Matches the account actually being evaluated, and matches the basis the fingerprint already declares** |
| B. price vs price | Would require stripping dividends from the strategy side — i.e. reconstructing a return the account did not earn. Less faithful and *more* work |

**Decisive secondary point: A keeps the fingerprint fixed.** The digest
includes `"benchmark": {… "basis_post_2016": "total_vs_total" …}`. Fixing the
*implementation* to match the declaration leaves `da22011e…` unchanged.
Changing the *declaration* to `total_vs_price` would move the digest and drag
in the whole of §1 Option B. Correcting the code is therefore both the more
faithful and the cheaper path.

The source already sanctions it. `data.py:274-278`:

> `"all"` folds dividends into the closes and is **ONLY for the benchmark**:
> the objective is stated against the S&P 500's total return, and SPY's price
> return understates that by about two points a year.

The recorder simply never uses it — `record_clean_session.py:254` calls
`fetch_alpaca_equity_bars([BENCHMARK], days=120, interval="1d",
include_today=True)` and takes the default `adjustment="split"`.

### RECOMMENDED BENCHMARK DEFINITION

| element | definition |
|---|---|
| instrument | **SPY** |
| data source | Alpaca `/v2/stocks/bars`, `timeframe=1Day`, **`adjustment="all"`** |
| basis | **total return**, both sides |
| split treatment | included in `adjustment="all"` |
| dividend treatment (benchmark) | folded into adjusted closes ⇒ **reinvested** |
| dividend treatment (strategy) | **credited as cash** (`dividends_received`), may then be parked in SGOV |
| session return | `close[t] / close[t-1] − 1` from consecutive adjusted closes |
| observation timing | after the US close; the recorder runs 16:15 ET |
| start / end | first eligible session **2026-10-12** → end of the evaluation window |
| starting capital | $100,000 (`$StartingEquity`) |
| cash treatment | strategy cash inside account equity; benchmark fully invested |
| level | see §5 — **must be stated as equity-sleeve or account-level, not left implicit** |

**Two things to record explicitly rather than paper over:**

1. **Reinvestment asymmetry.** Benchmark dividends are reinvested; strategy
   dividends sit in cash and may earn SGOV yield. Over ~60 sessions at SPY's
   ~1.3% yield this is single-digit basis points, but it is a real asymmetry
   and belongs in the definition.
2. **Adjusted series are retroactively restated** by the vendor on each new
   distribution. The recorder must therefore **store the two closes it used**
   alongside `benchmark_return`, so the stored number stays auditable even if
   a later fetch returns different adjusted values.

No performance comparison is offered here and none was computed.

---

## 3. MISSING `positions` RECORD — the fix

**Classification: instrumentation only.** Not a schema change (the field
exists), not a candidate change, not a fingerprint change (the observation
schema is not part of the digest), not a research registration.

`build_observation()` already computes the `equities` list it needs; the
constructor call at `record_clean_session.py:221` simply omits `positions=`.

Smallest safe fix — pass a **whitelisted projection** of the list already in
hand:

| field | source | why |
|---|---|---|
| `symbol` | position | identify the name |
| `quantity` | position | the sizing quantity |
| `market_value` | position | exposure contribution |
| `average_entry_price` | position | reconstruct the risk budget |
| `has_protective_stop` | `is_protective()` over `resting_sells[symbol]` | stop state |
| `stop_price` | the protective order | verify the 2.5× ATR stop |

**Deliberately excluded:** account numbers, order ids, API identifiers, and
anything not needed to reconstruct sizing.

This makes count, symbols, quantities, sizing, stop state and exposure all
reconstructible, and keeps `positions_held` / `exposure` / `positions` derived
from one list so they cannot disagree. **No trading decision is touched** —
`build_observation` runs after the session and influences nothing.

---

## 4. RECORDER PRINCIPAL — the blocker

**No code change is required.** `install-clean-recorder.ps1:59` already builds
an S4U principal:

```powershell
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited
```

with a documented fallback path below it. The task is Interactive today
because **the S4U registration needs elevation and fell back at install
time** — the same elevation problem recorded for the crypto installer.

**Credential availability is already proven, empirically.** `session-run.ps1`
is the S4U trading task; it has **no** USER-scope fallback, it hard-exits if
`$env:APCA_API_KEY_ID` is unset, and its last run returned **result=0**.
So S4U on this machine does load USER-scoped variables, and the recorder —
which reads the same variables — will inherit that. *This still needs one
confirming run rather than assumption.*

| consideration | recommendation |
|---|---|
| principal | **S4U**, same user, `RunLevel Limited` — matches the trading task |
| SYSTEM / service account | **No.** SYSTEM has no user profile and no USER-scope environment, so the keys would be unreachable |
| working directory | `$Repo`; `record-clean-session.ps1:25` already sets `PYTHONPATH` |
| broker/data file access | same user ⇒ unchanged |
| concurrency | trading 13:00 local, recorder 13:15 local — 15 minutes apart, no overlap. Keep it that way |
| triggered by the trading task? | **No — keep independent.** A recorder chained to the trading task would not run on a session the trading task failed, and that is exactly the session whose failure most needs recording |
| duplicate protection | already present: `append_session` refuses a duplicate `session` |
| retry | one retry inside the window is safe *because* duplicates are refused |
| failure detection | check `LastTaskResult` plus §6's continuity line; a silent non-run is the failure mode that matters |

Remediation is operational: **re-run the installer from an elevated
PowerShell**, then verify with a `--status` run under the task.

---

## 5. CRYPTO CONTAMINATION — separating the measurement

Live state at audit time: `held: 5490.65`, `quantity: 0.063267959`,
`equity: 98529.70`, `risk_on: true`, `dry_run: false` — **BTC is 5.6% of the
account and trades every 30 seconds.**

`positions_held` and `exposure` already exclude crypto and SGOV; only
`strategy_return = equity / prior_equity − 1` does not.

**The account already has a sleeve boundary — it just is not recorded.**
`reserved_fraction = 0.05` withholds 5% of equity from the equity book "AND
from the parking sweep", and the crypto worker spends only that. So the two
books are separated at the *decision* level today; the gap is purely
*measurement*.

**Recommendation: do not create a second account, a second trading process, or
a synthetic sleeve.** Record the components and derive all four views.

| quantity | how obtained | added to observation |
|---|---|---|
| account equity | `account["equity"]` | already present |
| **crypto market value** | positions where `"/" in symbol` | **add** |
| **parking (SGOV) market value** | position where `symbol == PARKING` | **add** |
| cash | `account["cash"]` | already present |
| **reserved fraction in force** | `config.reserved_fraction` | **add** (makes the boundary auditable) |
| **external cash movements** | broker `JNLC`/transfer activities for the session | **add** — otherwise a deposit reads as return |

Then:

- **frozen equity strategy** = account equity − crypto market value
  (SGOV stays inside: it is the equity book's parked cash, since
  `reserved_fraction` is withheld *before* the parking sweep)
- **crypto sleeve** = crypto market value
- **SGOV / cash** = parking market value + cash
- **combined account** = account equity

Session returns follow from consecutive observations, with external cash
movements subtracted from the numerator so transfers never read as
performance.

| item | treatment |
|---|---|
| starting capital for the OOS candidate | equity-sleeve value at the first eligible session — recorded, not assumed |
| deposits / withdrawals | recorded from broker activities; excluded from return |
| transfers between sleeves | bounded by `reserved_fraction`; record it each session |
| benchmark comparison | against the **equity-sleeve** return, with the combined account reported beside it |
| exposure | already equity-only; unchanged |
| realized / unrealized P&L | derivable once market values are recorded |

**Which is the headline must be frozen before 2026-10-12.** Recommended: the
**equity-sleeve return** is the frozen candidate's result; the combined
account is reported alongside as context. Reporting both prevents the
post-hoc choice this whole phase exists to prevent.

---

## 6. HASH-CHAIN CONTINUITY

**Yes — and the minimum check is three lines, using functions that already
exist.** `record_clean_session.py:256-257` already computes `sessions` and
`window`; `forward.continuity(recorded, calendar, registry_rows)` already
exists and already returns `missing`; `CleanObservation.data_quality_issues`
already exists and is already populated with other findings.

Minimum: before appending, call `continuity(load_sessions(), sessions,
registry)` and, if `missing` is non-empty, append a
`"missing eligible sessions: …"` entry to `data_quality_issues`.

Effect: a trailing truncation — the one tamper a self-consistent chain cannot
reveal — becomes visible **inside the next observation**, which is itself
chained. No new file, no new schedule, no new infrastructure.

---

## 7. REMEDIATION ORDER — derived from the code, not assumed

The ordering constraint that is easy to get wrong: **the benchmark decision
must come first**, because the benchmark block is *inside* the fingerprint. If
the declaration were changed rather than the implementation, the digest moves
and the §1 decision changes completely. Settling §2 as "fix the code to match
the declaration" makes §1 independent of it.

| # | step | depends on | why here |
|---|---|---|---|
| 1 | **Benchmark methodology decision** (§2) | — | The benchmark block is inside the digest. Fixing the implementation keeps `da22011e…`; changing the declaration would not |
| 2 | **Fingerprint governance decision** (§1): A, B or C | 1 | Can only be made once the digest's benchmark block is known to be stable |
| 3 | **Dry-run verification of A** — candidate sets under `15m/1mo` vs `1d/2y` | 2 | Three silent `continue` gates; inertness is analysed, not measured |
| 4 | **Runner change** (A) | 3 | Only after the dry run shows no candidate-set change |
| 5 | **Observation instrumentation** (§3 positions, §5 sleeve fields, §6 continuity, §2 stored closes) | 1 | All touch `build_observation`; all fingerprint-neutral; one coherent change |
| 6 | **Effective-digest plumbing** (C) | 4, 5 | Stamps the digest the runner now produces; touches the same recorder path as step 5 |
| 7 | **Recorder principal → S4U** (§4) | 5, 6 | Re-install and verify against the *final* recorder code |
| 8 | **End-to-end dry run** — `record-clean-session.ps1 --status` under the S4U task | 7 | Proves credentials, paths and refusals under the real principal |
| 9 | **OOS gate re-audit** | 8 | Re-run this audit's checks |

Steps 1–2 are decisions; 3–9 are work. Steps 5 and 6 are the only code
changes, both confined to the recorder and both fingerprint-neutral.

---

## 8. NO SILENT HISTORICAL REWRITE

### **A mathematical dependency that must not be tripped**

`purge.freeze_date()` returns the latest `when` among
`experiments.jsonl` rows whose `decision` is in
`CONFIG_CHANGING = ('accepted', 'reverted')`. `evaluation_window` then adds a
20-session embargo. The current freeze is **2026-09-11** (EXP-0017), which
lands the first clean session on **2026-10-12**.

**If any remediation is recorded in `experiments.jsonl` with decision
`accepted` or `reverted`, the freeze date moves to that date and the clean-OOS
start slides ~20 sessions — automatically and silently.**

None of these remediations is an experiment. They must be recorded as
**governance corrections in their own additive log**, never as accepted
experiments. Done that way, **2026-10-12 does not move**, and I am not
proposing to move it.

### The correction record (additive, not a rewrite)

| what was wrong | discovered | corrected representation | reports affected | still usable? | new fingerprint? |
|---|---|---|---|---|---|
| `frozen_fingerprint()` digests source defaults, not the running config; runner passes `--interval 15m` | 2026-09-21 | Under **A+C**: runner returns to the declared `1d`, and the stamp is emitted by the process that trades | Every doc citing `da22011e…` | **Yes** — the simulator never reads `AutoTradeConfig.interval`; baseline +58.5889000000% / 698 unaffected | **No** under A+C. **Yes** under B |
| Benchmark implemented as SPY **price** return while the digest declares `total_vs_total` | 2026-09-21 | `adjustment="all"`, matching the declaration | No historical report — the recorder has never produced an observation (0 sessions) | **Yes**; nothing was ever measured with it | **No** |
| `CleanObservation.positions` never populated | 2026-09-21 | Constructor receives the projection | None — 0 sessions recorded | **Yes** | **No** |
| Recorder runs Interactive | 2026-09-21 | S4U via elevated re-install | None | **Yes** | **No** |
| `strategy_return` is account-level, includes a live BTC sleeve | 2026-09-21 | Record component market values; derive four views | None | **Yes** | **No** |

Nothing historical is rewritten. Two of the five defects have produced no
artefact at all, because the clean record is empty.

---

## 9. FINAL OUTPUT

### A. FINDINGS

| # | issue | source | severity | affects |
|---|---|---|---|---|
| 1 | Fingerprint digests defaults; runner passes `--interval 15m` | `forward.py:104`, `session-run.ps1:177` | **FAIL** | **Governance + measurement.** Rule arithmetic protected by `daily_bars()`; `interval` still gates eligibility at 3 sites |
| 2 | Benchmark is SPY price return, declared `total_vs_total` | `record_clean_session.py:254`, `forward.py:131` | **FAIL** | **Measurement.** Flatters by ≈1.58 pts/yr |
| 3 | `CleanObservation.positions` never written | `record_clean_session.py:221` | **FAIL** | **Measurement.** Sizing compliance unverifiable |
| 4 | Recorder runs Interactive | scheduled task principal | **BLOCKER** | **Measurement.** A missed session is a permanent hole |
| 5 | `strategy_return` includes a live BTC sleeve + SGOV | `record_clean_session.py:205` | **LIMITATION** | **Measurement.** Recorded return is not the candidate's |
| 6 | `continuity()` never called by the recorder | `forward.py:464` | **LIMITATION** | **Governance.** Trailing truncation undetected |
| 7 | Fingerprint omits `universe`, `period`, `asset_class`, `capital_base`, `StrategyConfig` | `forward.py:117-121` | **LIMITATION** | **Governance.** `capital_base` scales sizing *and* both guards |
| 8 | Comment "model is recorded, not consulted" understates the reorder path | `autotrade.py:928` | **LIMITATION** | **Governance.** Inert today (`usable=False`) |
| 9 | Partial fills, orphan/duplicate orders, restart mid-session | — | **UNVERIFIED** | Measurement |

**None of items 1–9 affects the strategy's economic rules.**

### B. DECISIONS REQUIRED (human approval)

1. **Fingerprint: A, B or C.** Recommended **C with A as precondition**.
2. **Benchmark: total-vs-total via `adjustment="all"`.** Recommended, and it
   keeps the digest fixed.
3. **Headline OOS return: equity sleeve or combined account.** Recommended
   equity sleeve, combined reported beside it. Must be frozen before 10-12.
4. **Elevated re-install of the recorder task.** Requires an admin shell the
   session cannot open.

Everything else is mechanical and needs no approval.

### C. RECOMMENDED REMEDIATION (smallest safe)

1. Runner: drop `--interval` and `--period` so CLI defaults apply — **after**
   the dry run in step 3.
2. Recorder benchmark fetch: `adjustment="all"`; store both closes used.
3. `build_observation`: pass the whitelisted `positions` projection.
4. `build_observation`: add crypto MV, parking MV, `reserved_fraction`, and
   session cash movements.
5. Recorder: one `continuity()` call feeding `data_quality_issues`.
6. `config_digest(config)` emitted by `run_once`, consumed by the recorder via
   the existing `expected_fingerprint` parameter.
7. Recorder task: elevated re-install → S4U.

### D. IMPLEMENTATION ORDER

Section 7's nine steps, in that order. The two hard constraints: **benchmark
decision before fingerprint decision** (the benchmark block is inside the
digest), and **dry run before the runner change** (three silent `continue`
gates).

### E. OOS GATE — must all be PASS before 2026-10-12

| # | gate |
|---|---|
| 1 | Effective runtime digest == the published frozen fingerprint, asserted by the recorder, not recomputed from defaults |
| 2 | Benchmark implemented on the declared basis, with the closes used stored per observation |
| 3 | A recorded observation contains per-name symbol, quantity, market value, entry price and stop state |
| 4 | Recorder registered **S4U** and proven to run and authenticate with nobody logged in |
| 5 | Observation distinguishes equity sleeve / crypto / cash+SGOV / combined, and the headline is frozen in writing |
| 6 | `continuity()` runs at record time and writes gaps into `data_quality_issues` |
| 7 | `data/forward-evaluation.jsonl` still absent or chain-intact at 0 sessions on 2026-10-11 |
| 8 | Registrations 21, declared 60, chain intact, thirty-year reads 13 |
| 9 | `freeze_date` still 2026-09-11 — **no remediation recorded as `accepted`/`reverted`** |
| 10 | MR config unchanged: ATR 0.035, RSI 35/60, cap 20, stop 2.5×, risk 0.005, guards 0.015/0.06 |

### F. EXPECTED POST-REMEDIATION STATE

- **Frozen candidate** — byte-identical economics. ATR 0.035, RSI 35/60,
  20-bar cap, 2.5× ATR stop, risk 0.005, buckets, cash rules: untouched.
- **Fingerprint** — still `da22011e7504759285255c8d…`, but now *emitted by the
  trading process* and *verified* by the recorder rather than recomputed from
  defaults on both sides. Divergence becomes unrecordable rather than merely
  unnoticed.
- **Benchmark** — SPY total return (`adjustment="all"`), symmetric with the
  account's total return, matching the declaration already inside the digest,
  with the underlying closes stored per session.
- **Observations** — per-name sizes and stop state; equity-sleeve, crypto,
  cash/SGOV and combined all derivable; external cash movements separated from
  return; gaps surfaced in `data_quality_issues`.
- **Sleeve accounting** — one account, two books, boundary `reserved_fraction`
  recorded each session. No second trading process.
- **Recorder** — S4U, independent 16:15 ET trigger, duplicate-protected,
  proven to run logged-out.
- **Hash chain** — unchanged mechanism (append-only, duplicate refusal,
  fingerprint-drift refusal, first-break reporting), now with trailing
  truncation detectable through continuity.
- **Clean OOS** — still opens **2026-10-12**, 0 sessions recorded until then.

### Governance end state of this task

Nothing implemented. Nothing registered. Registrations **21**, declared **60**,
chain intact, thirty-year reads **13**. `frozen_fingerprint()` still returns
`da22011e…c237b`. No strategy parameter, runner, task, schema or clean-OOS
date changed by this analysis.
