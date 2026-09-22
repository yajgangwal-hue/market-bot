# Final pre-Clean-OOS integrity audit

*Read-only audit. **No file changed, no parameter touched, no optimisation, no
experiment registered.** Every figure reconciled from live artefacts, not from
prior summaries.*

---

## H. Clean OOS gate: **NOT READY**

**One required remediation**, and it is not a code defect:

> **`EventAwareTraderCleanRecorder` still runs under `Logon Mode: Interactive
> only`.** The elevated installer has not taken effect.

Everything else passes or is an explicitly accepted non-conformance. Detail in
§I.

---

## A. Governance state

| artefact | value | agrees? |
|---|---|---|
| SPEC-0001 | **v1.0.0, NORMATIVE** | ✓ |
| frozen fingerprint | `da22011e7504759285255c8d…c237b` | ✓ |
| **baseline (re-run today)** | **+58.5889000000% / 698 trades** | ✓ |
| Sharpe / maxDD / exposure | 0.5107 / −12.9824% / 44.2794% | ✓ |
| registrations | **23** | ✓ |
| declared configurations | **63** | ✓ |
| prereg chain | intact | ✓ |
| `experiments.jsonl` rows | **53** | ✓ |
| remediation ledger | **9 rows, chain intact** | ✓ |
| clean OOS sessions | **0**; `forward-evaluation.jsonl` absent | ✓ |
| freeze date | **2026-09-11** (EXP-0017) | ✓ |
| embargo | **20 sessions**; 6 elapsed as of the 2026-09-21 local bar | ✓ |
| clean OOS start | **2026-10-12** (21st session after the freeze) | ✓ |

**No disagreement between artefacts.**

---

## B. SPEC-0001 conformance — every active decision

| Decision | Latest permissible info | Decision ts | Execution ts | Live | Emulator | Conformance | Evidence |
|---|---|---|---|---|---|---|---|
| **Entry signal** | D, in progress | last 20 min of D | same instant | `daily_bars` + `_with_today` (`:1899-1900`) | D's completed bar, fills at close | **PASS** (C-7 proxy) | source + `test_entry_timing` |
| **RSI rule exit** | D, in progress | first cycle the condition is true | same instant | `daily_bars` + `_with_today` (**C-19**) | RSI incl. D close, books at close | **PASS** | REM-0009; 18 tests |
| **Time exit** | D; count known at the bell | first cycle `bars_held ≥ 20` | same instant | `bars_held = k` via the same series | `bars_held += 1` per session | **PASS** | `bars_held` 19→20 test |
| **Stop placement** | continuous tape | on trade at/through stop | immediate | broker-resident GTC | `bar.low <= stop` + gap fills | **PASS** | §D below |
| **Stop reconciliation** | D, current broker state | every cycle, **unconditional** (`:1860`) | immediate | live positions + orders | no equivalent (live-only) | **PASS** | source |
| **Position sizing** | D, in progress | with the entry | same instant | live equity; ADV over partial volume | D-close-marked; ADV over complete volume | **PASS, C-9 asymmetry** | §C |
| **Portfolio / correlation limits** | D, current | at the decision | — | live positions + cycle state | D-marked | **PASS** | source |
| **Cash / risk guards** | D, current | at the decision | — | live broker equity vs session open (`:1464`, `:1507`) | D-close vs D-open mark | **PASS** | source |

### Inactive placeholders — all verified OFF

| branch | state |
|---|---|
| news | **0 imports** in `autotrade / portfolio / mean_reversion / strategy / risk / broker` |
| regime | not in `PRODUCTION_CANDIDATE`; `mr_regime_exit` absent |
| learned model / ranker | `live_model_floor = 0.0`; **`LEARNED_RANKING_ENABLED = False`**; promotions file **absent**; `candidate_rank` not in the candidate |
| shorting | long-only; no short branch reachable |
| other non-frozen branches | `PRODUCTION_CANDIDATE` has exactly **6 keys**: `entry_fill, entry_rule, mark_to_market_guard, max_entries_per_day, realistic_stop_fills, rule_exit_timing_haircut`. No take-profit, trail, partial, momentum, regime or limit-exit key |

Conformance was audited independently of the fingerprint, per §7.

---

## C. Current-day information audit

| use | location | in money path? | available at that ts? | future EOD info? | classification |
|---|---|---|---|---|---|
| `include_today=True` | `autotrade.py:674` (`_todays_bars`) | **YES** | yes — the forming bar | **no** | **conformant**; the single money-path use |
| `include_today=True` | `record_clean_session`, `phase4_checkpoint`, `preoos_dry_run`, `exit_at_peak` | no | — | — | recorder / tools, outside the decision path |
| `datetime.now()` | `:329`, `:2316` | no | — | — | telemetry stamps only |
| `datetime.now().date()` | `:678` | yes | selects *which* fetched bar is today | no | **conformant** |
| `series[-1].timestamp … else now` | `:723` | no | candidate `as_of`; fallback only on an empty series, which returns REJECT | no | metadata, not a decision input |
| `date.today()` | `:1464`, `:1507` | yes | daily / ISO-week guard **session key** | no | **conformant** — a boundary, not price information |
| `datetime.now()` | `broker.py:185` | no | `client_order_id` uniqueness | no | not a decision input |

**The simulator contains ZERO uses of the clock, the broker, or the network.**
`grep` over `portfolio.py` for `datetime.now|date.today|time.time|utcnow|
requests|urllib` returns only comment text. The emulator is a pure function of
its inputs — the strongest available guarantee against current-day leakage in
the historical path.

**Known asymmetry (C-9), unchanged and untouched per instruction:** live
computes ADV over a series whose last bar carries **partial-session** volume;
the emulator uses **complete-session** volume, so the emulator is systematically
more permissive on the liquidity floor and participation cap. H-0015 measured
cash as the sole first-binding reason across 1,539 evaluated candidates, so it
is **non-binding**.

---

## D. Stop safety

Invariant: *every open equity position must have a verified broker-resident
protective stop covering the full authoritative filled quantity.*

| # | Failure mode | Result | Evidence |
|---|---|---|---|
| **A** | stale / partial position quantity | **PASS** | `broker.order(id)` gives the authoritative `filled_qty`; `_settled_position_quantity` refuses a read below a known fill, re-reads ≤3×, and never returns more than the broker has shown. 21 regression tests incl. the historical 219/229 case |
| **B** | cancel-before-submit | **PASS (telemetry)** / exposure remains | Cancel then submit; if submit fails, `protective_stop_placed` is **not** logged, `protective_stop_FAILED` is, and `_verify_stop_coverage` re-reads and classifies `unprotected`. **No false "protected" telemetry.** The window itself cannot be closed — Alpaca reserves shares against any resting sell, so no atomic replace exists |
| **C** | submission failure | **PASS** | Position stays open; `_with_retry` retries in-cycle (`broker_retries=3`); loud `protective_stop_FAILED` + `stop_coverage_SHORTFALL`; repaired next cycle (≤15 min intraday). **Limitation: no external alerting** — detection is log-based |
| **D** | crash / restart | **PASS for recovery**, exposure for one case | `_reconcile_protective_stops` runs **unconditionally** in §1b (`:1860`) at the start of every cycle, so the next process start reconciles — after cancel, after submit-before-verify, and after fill-before-reconcile alike. **Accepted exposure:** a crash spanning the close leaves only the `tif=day` bracket, which expires at the bell |
| **E** | broker verification | **PASS** | "Protected" requires an order the broker reports in `RESTING_ORDER_STATUSES` **and** covering the full quantity. `pending_new` / `pending_cancel` do **not** count |
| **F** | live verification | **PASS** | 4 of 4 equity positions fully protected, **zero uncovered**, all `status=new`: BAC 151/151 @ 53.2, CVS 124/124 @ 81.71, UNP 48/48 @ 254.77, VZ 174/174 @ 43.61 |

**Crypto:** BTC holds **$5,466.81 (5.56% of equity)** with **no broker-resident
stop** — managed by the 30-second worker. Does **not** satisfy the invariant.
Separate track, explicitly out of scope, unchanged.

---

## E. Test determinism

**The decisive test:** the full suite was run with `urllib.request.urlopen`
replaced and `socket.socket.connect` severed.

```
tests run : 1252
failures  : 0
errors    : 0
network attempts blocked: 0
```

**Zero network attempts.** The suite is hermetic and reproducible without
network access.

| dimension | finding |
|---|---|
| network / broker API | **0 attempts**. The four files C-19 exposed (`test_paper_launch_safety`, `test_exit_closes_for_real`, `test_entry_timing`, `test_autotrade`) now stub `_todays_bars` at module level; `TodaysBarsTests` restores the real function because it asserts on that function itself |
| current date / time | 5 files read the clock, all **date-relative not date-dependent** — `test_live_pipeline` generates and asserts on `date.today()` consistently; `test_lookahead` builds "tomorrow" as `now + 1 day` |
| environment variables | only `test_broker.py`, which **pops and restores** the APCA keys to test the missing-credential path |
| randomness | **all seeded** — `random.Random(7/11/3/5/seed)` |
| filesystem state | `test_adjudication` guards with `skipTest`; `test_preflight` explicitly handles "a fresh clone has no CSVs". **One finding:** `test_learned_component_disabled.py:358` reads `data/trade-model.json` **without a guard** — `data/` is gitignored, so this would error on a fresh clone |
| order-state dependence | none found; fixtures construct their own broker state |

---

## F. Accounting / benchmark

| requirement | state |
|---|---|
| primary result = equity-sleeve | `equity_sleeve_return`, net of `cash_movements` — **present** |
| crypto reported separately | `crypto_market_value` — **present** |
| SGOV / cash parking consistent | `parking_market_value` + `reserved_fraction` — **present**; parked cash stays inside the equity sleeve because `reserved_fraction` is withheld before the sweep |
| benchmark methodology | SPY, `adjustment="all"` (`record_clean_session.py:345`) = **total return**, matching the fingerprint's declared `basis_post_2016: total_vs_total` |
| matching observation dates | benchmark return is `bars[-1]/bars[-2]` on the same session the observation records |
| no future benchmark info | benchmark is an **outcome** recorded after the session; it enters no decision |
| split / dividend treatment | adjusted pair **and** split pair stored (`benchmark_close`, `benchmark_prev_close`, `benchmark_close_split`, `benchmark_prev_close_split`, `benchmark_basis`) so a vendor restatement cannot silently change a recorded value |
| combined account still reported | `strategy_return` retains its original name and meaning — the **combined account** — and is never presented as the candidate's return |

30 observation fields present. **PASS.**

---

## G. Research contamination

| check | result | evidence |
|---|---|---|
| no optimisation in the money path | **PASS** | `PRODUCTION_CANDIDATE` has 6 keys, none a tuned exit/entry variant |
| no parameter selected with post-freeze info | **PASS** | **Zero `+`/`−` lines** touching `rsi_entry`, `rsi_exit`, `max_atr_fraction`, `stop_atr_multiple`, `max_holding_bars`, `risk_per_trade`, `max_open_positions`, `max_entries_per_day`, `rule_exit_timing_haircut`, `min_price`, `min_average_dollar_volume` across every `src/` commit since the freeze |
| no OOS observation used to tune | **PASS** | 0 OOS sessions exist; the file is absent |
| news not in the strategy | **PASS** | 0 imports in the money path |
| regime not in the strategy | **PASS** | not in the candidate |
| no current market behaviour justified a change | **PASS** | the only money-path changes since the freeze are REM-0007/0008 (stop safety) and REM-0009 (C-19), both implementation corrections |
| remediations not treated as experiments | **PASS** | separate `docs/remediations.jsonl` (9 rows, chained); `experiments.jsonl` unchanged at 53; freeze date still 2026-09-11 |
| **baseline still reproduces** | **PASS** | re-run today: **+58.5889000000% / 698** |

---

## I. Required remediation before OOS

### Blocking — exactly one

**The clean recorder is not running under a non-interactive principal.**

```
TaskName   : \EventAwareTraderCleanRecorder
Logon Mode : Interactive only          <-- blocker
Status     : Ready   Last Result: 0    Next Run: 9/23/2026 1:15 PM
```

For contrast the trading task reads `Logon Mode: Interactive/Background`, which
is how `schtasks` renders S4U.

**Why this blocks OOS rather than being accepted:** an Interactive task does not
run when nobody is logged in, and a missed clean session is a **permanent hole**
— the record is append-only and may never be backfilled. The holes would not be
random: they would correlate with when the machine happened to be logged out,
which is a selection effect on *which* sessions get recorded. The installer's
own comment says as much.

**Action (owner, elevated PowerShell):**

```
Set-ScheduledTask -TaskName 'EventAwareTraderCleanRecorder' -Principal (New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited)
```

Then `(Get-ScheduledTask -TaskName 'EventAwareTraderCleanRecorder').Principal.LogonType`
must print `S4U`. 20 days remain.

### Explicitly accepted non-conformances — none blocking

| # | item | why acceptable |
|---|---|---|
| 1 | **C-9** partial-vs-complete volume | non-binding: H-0015 found cash the sole first-binding reason across 1,539 candidates |
| 2 | legacy `bars_held` fallback would over-count by one | **unreachable**: all 4 live positions carry `opened_at_ts`, and every new position is stamped at entry |
| 3 | cancel-before-submit window | Alpaca provides no atomic replace; telemetry cannot report a false "protected" |
| 4 | crash spanning the close | bounded, documented; recovery is guaranteed at the next cycle |
| 5 | crypto has no broker-resident stop | separate authorised track, out of scope |
| 6 | fingerprint cannot prove implementation conformance | documented governance limitation (§7); conformance audited independently here |
| 7 | `test_learned_component_disabled.py:358` unguarded `data/` read | test hygiene only; cannot affect the money path or OOS. One-line `skipTest` guard available |

None of items 1–7 can change decision semantics, invalidate equity protection,
contaminate OOS, or make results non-reproducible.

---

## Future research ideas — recorded, NOT implemented

- `PATCH /v2/orders/{id}` to remove the cancel-before-submit window.
- A conformance assertion that the fingerprint cannot provide (§7 limitation).

Neither is an optimisation and neither is proposed for action now.

---

*Production unchanged by this audit: fingerprint `da22011e…c237b`, RSI 35/60,
ATR 0.035, 20-bar cap, 2.5× ATR stop, risk 0.005, 12 positions, haircut 0.652%,
23 registrations, 63 declared, 53 experiments, 9 remediations, clean OOS 0
sessions opening 2026-10-12. No file modified.*
