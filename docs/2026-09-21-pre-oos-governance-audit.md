# Pre-OOS governance audit — frozen candidate and clean-OOS machinery

*READ-ONLY. Nothing modified, nothing registered, no parameter touched.
Every finding below is traced to source or to live system state, not to
documentation. Problems are reported, not repaired.*

---

## 1. FROZEN CANDIDATE STATUS

### **FAIL — the published fingerprint does not describe what will run**

`frozen_fingerprint()` (`forward.py:104`) computes its digest from
**default-constructed** objects:

```python
mr, policy, costs, live = (MeanReversionConfig(), RiskPolicy(),
                           CostModel(), AutoTradeConfig())
```

`AutoTradeConfig.interval` defaults to `"1d"`, and `interval` **is one of the
eight fingerprinted live fields**. But the live money path
(`scripts/windows/session-run.ps1:177`) runs:

```
autotrade --asset-class equity --interval 15m --period 1mo --live
```

Recomputing the digest with the configuration `cli.command_autotrade`
actually builds:

| configuration | fingerprint |
|---|---|
| `AutoTradeConfig()` defaults — **published** | `da22011e7504759285255c8d…` |
| live (`interval='15m'`) — **what runs** | **`569a8da724f0f61064dd7013…`** |

**The live account is not running the fingerprinted configuration.**

**Materiality, stated fairly.** The *rule arithmetic is not corrupted*.
`daily_bars()` (`autotrade.py:394`) loads daily bars from disk precisely so
that "a rule calibrated in days must not be handed fifteen-minute candles,"
and `_mean_reversion_candidate` requires daily series. RSI(14), SMA(200) and
ATR(14) are computed on daily bars whatever `--interval` is.

But `interval` is **not inert**. The cycle's 15-minute fetch gates candidate
eligibility before the rule is consulted —
`if symbol in held or not bars or len(bars) < strategy.minimum_history:
continue` (`autotrade.py:1712`) — and `strategy` comes from
`StrategyConfig.for_interval(config.interval)`, whose thresholds scale by
`1/√(bars per session)`. Which symbols are even considered therefore depends
on a parameter the fingerprint records as a different value.

**This is the owner's decision to resolve, not mine.** Either path changes
something: aligning the runner to `--interval 1d` changes live behaviour;
re-issuing the fingerprint over the live config changes the published digest
from `da22011e…` to `569a8da7…` and makes every prior report's citation
stale. I have changed neither.

### Component verification

| component | frozen value | verified in source | status |
|---|---|---|---|
| RSI entry / exit | 35.0 / 60.0 | `MeanReversionConfig` | **PASS** |
| ATR ceiling | 0.035 | `max_atr_fraction` | **PASS** |
| Holding cap | 20 | `max_holding_bars` | **PASS** |
| Stop | 2.5× ATR | `stop_atr_multiple` | **PASS** |
| Trend filter | SMA 200 | `trend_ma_days` | **PASS** |
| min price / ADV | $20 / $50m | config | **PASS** |
| Risk per trade | 0.005 | `RiskPolicy` = CLI default 0.005 | **PASS** |
| Daily / weekly loss guards | 0.015 / 0.06 | CLI defaults match `RiskPolicy` | **PASS** |
| Max orders / run | 3 | CLI default 3 = config default | **PASS** |
| Entry window | 20 min | `entry_window_minutes` | **PASS** |
| Cash parking | SGOV, floor $2,000 | fingerprinted | **PASS** |
| Reserved fraction | 0.05 | fingerprinted | **PASS** |
| Equity / crypto separation | `--asset-class equity` passed explicitly | `session-run.ps1:177` | **PASS** |
| **`interval`** | `1d` fingerprinted / **`15m` live** | proven above | **FAIL** |

### Fields the freeze does **not** cover — **LIMITATION**

The fingerprint takes only 8 named `AutoTradeConfig` fields. **Not covered:**
`universe`, `period`, `asset_class`, `dry_run`, `require_broker_side_stop`,
`require_market_open`, `broker_retries`, `capital_base`,
`capital_baseline_equity`, `model_file`, `mean_reversion`.

`capital_base` / `capital_baseline_equity` matter most: they scale position
sizing **and both loss guards** together. They are `$null` in the runner
today, so the whole account is traded — but a change would not move the
fingerprint. `StrategyConfig` (including `--exit-mode`, default `trailing`) is
not fingerprinted at all; it is inert for the MR branch but unguarded.

**No runtime assertion exists anywhere that the constructed config matches the
fingerprint.** `frozen_fingerprint()` is never called from the money path —
only from the recorder and research scripts.

---

## 2. MONEY-PATH FIREWALL

### **PASS**, with one caveat

| surface | finding | status |
|---|---|---|
| **News** | **Zero imports** of `news` in `autotrade.py`. The recorder writes `data/news/<date>.jsonl` and nothing reads it in the money path | **PASS** |
| **`trade_learning` veto** | Model loads (`status=UNPROVEN`, `veto_threshold=0.25`). `model_vetoes` line 422: `if not model.is_usable: return False`. **An UNPROVEN model never vetoes** | **PASS** |
| **`live_model` ranking** | `live.usable` requires **`LEARNED_RANKING_ENABLED`** *and* explicit promotion. Switch is `False` (`live_model.py:62`); `docs/model-promotions.jsonl` **does not exist**. Verified in the live `.venv`: `usable=False` | **PASS** |
| **Research → clean record** | `production_report` calls `reject_forward_data`, which refuses `CleanObservation` **by type** to depth 4 | **PASS** |
| **Clean record → research** | `FORWARD_LOG` lives under `data/`, deliberately not with the registry; never written by research code | **PASS** |
| **Registries / cached features / experiment outputs** | none imported by `autotrade.py` | **PASS** |

**CAVEAT — the live-model gate is state-dependent, not structural.** With
`live_model_floor = 0.0` the model could never *remove* a candidate, but the
same block **re-sorts** them:

```python
candidates.sort(key=lambda c: live_scores.get(c.symbol, 0.0), reverse=True)
```

Ordering is decisive — `max_orders_per_run=3` truncates, and H-0015 measured
cash binding on 54.65% of evaluated candidates. **The in-code comment
"model is recorded, not consulted: live_model_floor is 0.0"
(`autotrade.py:928`) is inaccurate**: the floor prevents removal, not
reordering. Today the block is unreachable because `usable=False`, and the
kill switch is correctly designed so a retrain cannot promote its own output
(the code records a 2026-09-16 retrain that would have re-armed itself).
`retrain` runs daily, so this depends on the switch staying off.

---

## 3. INFORMATION-BOUNDARY STATUS

| input | boundary as implemented | status |
|---|---|---|
| Daily bars | `daily_bars()` from local price files, cached on mtime | **PASS** |
| Partial/current bar | `_with_today()` appends the in-progress session only if the file lacks today; decision at 15:40 ET uses the session in progress — available at the timestamp | **PASS** |
| Indicators | RSI/SMA/ATR from closed daily bars + today's partial, all ≤ decision time | **PASS** |
| **ADV / participation cap** | `average_dollar_volume()` uses bars **strictly before** the session: "the session's own volume is not known then" | **PASS** |
| Corporate actions | `adjustment="split"` — prices as the tape printed them; matches how signals and stops were measured | **PASS** |
| News | not on the money path at all | **PASS** |
| Broker/position/cash state | read from the broker at cycle time | **PASS** |
| Orders / fills | counted by `submitted_at` / `transaction_time` UTC date | **PASS** |
| Stop prices | reconstructed from `evaluate()`'s own stop; `series_for_atr = daily_bars(symbol)` | **PASS** |
| **Benchmark return** | `bars[-1].close / bars[-2].close - 1.0` from a `days=120, include_today=True` fetch — see §6 | **LIMITATION** |

No input was found that can contain post-decision information. **Remaining
uncertainty:** `include_today=True` on the recorder's benchmark fetch returns
the in-progress SPY bar; the recorder runs at 13:15 local (16:15 ET), after
the close, so the bar is complete — but this is **timing-dependent, not
structurally enforced**. If the recorder ever fires early, `benchmark_return`
would use a partial SPY bar. **UNVERIFIED** that it cannot.

---

## 4. EXECUTION / ACCOUNTING STATUS

| check | finding | status |
|---|---|---|
| Order / fill timestamps | recorded from broker feeds by UTC date | **PASS** |
| Transaction costs, dividends | summed from the broker's fee and dividend activities | **PASS** |
| Whole-share constraint | `require_broker_side_stop=True` forces whole shares so a real resting stop exists | **PASS** |
| Protective orders | `unprotected_positions()` runs **every** clean session; `is_protective()` correctly refuses to count a take-profit limit leg as protection | **PASS** |
| Gapped stops | `realistic_stop_fills` in `PRODUCTION_CANDIDATE` | **PASS** |
| Broker reconciliation | `reconcile()` returns discrepancies and **never corrects** them; equity/cash to $1.00 or 1 bp, `positions_held` exact | **PASS** |
| Execution discrepancies | flagged when broker fills exist but the loop logged no entry/exit | **PASS** |
| **Per-name position sizes** | **`CleanObservation.positions` is never populated** | **FAIL** |
| **Return attribution** | `strategy_return` is **account-level** | **LIMITATION** |
| Partial fills, orphan/duplicate orders, restart/recovery mid-session | not exercised by this audit | **UNVERIFIED** |

### FAIL — the sizing-audit field is always empty

`CleanObservation` declares `positions: List[Dict]` with this rationale:

> Per-name sizes, not merely a count. "Position sizing follows the frozen risk
> policy" is one of the things each clean session must be checkable against,
> and **a count cannot be checked against a sizing rule.**

`build_observation()` (`record_clean_session.py:199`) *receives* `positions`
and uses it for `positions_held`, `exposure` and the naked-stop check — but
**never passes it to the constructor** (line 221). The field defaults to `[]`.
It is the only `CleanObservation(...)` construction site in the codebase.

**Consequence:** every clean session will record a position *count* and no
per-name sizes, so the claim "sizing followed the frozen risk policy" will not
be checkable from the record — which is the exact thing the field exists for.

### LIMITATION — the recorded return is not the frozen candidate's return

`equity = float(account["equity"])` is the **whole account**, and
`strategy_return = equity / prior_equity − 1`.

`positions_held` and `exposure` correctly exclude crypto (`"/" not in symbol`)
and SGOV — but the **return does not**. Confirmed live at the time of this
audit, from `data/crypto-sleeve.jsonl`:

```
"held": 5490.65, "quantity": 0.063267959, "equity": 98529.70,
"risk_on": true, "dry_run": false
```

**The account holds $5,491 of BTC — 5.6% of equity — traded live by
`EventAwareTraderCrypto` every 30 seconds.** So every clean-OOS
`strategy_return` will blend three books: the frozen equity candidate, the
BTC sleeve, and SGOV interest. The observation records no crypto position, so
**the frozen candidate's return cannot be separated from the record alone.**

---

## 5. OOS METRICS TO BE FROZEN

Recorded per session today: `session`, `as_of`, `config_fingerprint`,
`universe_size`, `signals`, `orders`, `fills`, `positions_held`, `exposure`,
`cash`, `equity`, `transaction_costs`, `dividends_received`,
`strategy_return`, `benchmark_return`, `exits`, `execution_discrepancies`,
`data_quality_issues`.

**(1) Descriptive — report always.** Cumulative return, cumulative benchmark
return, trade count, win rate, average and median trade, exposure, turnover,
transaction costs, positions held, session count, missing sessions.

**(2) Diagnostic — report, never promote on.** Volatility, Sharpe, Sortino,
maximum drawdown, profit factor, average holding period, daily-return
correlation and beta to SPY, downside deviation, regime-conditioned
descriptives using the **existing** `trend_dual_ma` definition only.

**(3) Formal criteria.** `forward.VERDICTS` today is exactly
`("INSUFFICIENT_EVIDENCE", "MEASURED_NO_CONCLUSION")` and
`MINIMUM_SESSIONS_FOR_ANY_VERDICT = 60`. **There is no PASS verdict in the
code**, which is correct: the module's own comment records that at 6–9%
annual volatility the standard error over 60 sessions exceeds the entire
annual edge. 60 sessions is a floor on when the question may be **asked**.

**Not meaningful over the available duration — say so rather than force it:**
CAGR (annualising ~60 sessions is not a rate), Sharpe and Sortino (standard
error dominates), maximum drawdown (a single-path extreme), Calmar, and any
regime statistic (three states over one quarter). These are diagnostics only.

**No metric may be added or redefined after results are visible.**

---

## 6. BENCHMARK DEFINITION

### **FAIL — the comparison is asymmetric, and the fingerprint mis-declares it**

| element | as implemented |
|---|---|
| instrument | SPY |
| **basis** | **price return** — `fetch_alpaca_equity_bars` default `adjustment="split"`; `benchmark_return = bars[-1].close / bars[-2].close − 1` |
| **strategy basis** | **total return** — account equity, with `dividends_received` credited as cash |
| period | per session, from the first eligible session |
| starting capital | $100,000 (`$StartingEquity`) |
| cash treatment | idle cash parked in SGOV, inside account equity |
| costs | real broker fees and fills |
| level | **account-level**, including the BTC sleeve |

The fingerprint declares `"basis_post_2016": "total_vs_total"` and
`"dividends": "cash_not_reinvested"`. **The recorder implements
`total_vs_price`.** SPY's price return understates its total return by
**≈1.58 points a year** (measured, and already recorded in this project), so
the comparison currently flatters the strategy by roughly that margin.

This must be settled **before** 2026-10-12, because changing it afterwards
would be redefining the benchmark in light of results.

---

## 7. HISTORICAL VS PROSPECTIVE EVIDENCE

**PASS — the separation is enforced by type, not convention.**

| | historical development evidence | prospective clean-OOS evidence |
|---|---|---|
| store | `docs/experiments.jsonl`, `docs/preregistrations.jsonl`, `docs/phase5-research.jsonl` | `data/forward-evaluation.jsonl` |
| burden | ≥187 configurations; 21 preregistrations, 60 declared; 39 phase-5 executions | 0 sessions |
| **exit family alone** | **~77 configurations** — 54 in `experiments.jsonl` plus 23 in the preregistration ledger (H-0001 6, H-0002 3, H-0003 3, H-0004 2, H-0005 3, H-0010 3, H-0011 3) | — |
| universe | one decade, one 100%-survivor universe | forward, same universe |
| status | **contaminated by construction** | untouched |

Configurations from different ledgers are **not** independent discoveries and
are not to be counted as such. The historical record is the source of the
hypothesis; it is not confirmation of it. `reject_forward_data` enforces the
boundary in the only direction software can: research code cannot read the
clean record.

---

## 8. SURVIVORSHIP LIMITATION

**LIMITATION — documented, quantified, unresolved.**

- All 230 symbols trade through 2026-09. **Zero delistings.** The historical
  universe **has not been demonstrated to be delisting-complete**; it is
  100% survivors.
- No point-in-time constituent dataset exists in this project or from the
  current vendor.
- **EXP-0031 is the evidence and its bounds must be preserved**: decade CAGR
  **9.14% → 3.82%**, thirty-year **5.66% → 2.24%** on the survivorship-safe
  ETF subset, **positive in both halves**. The edge is real; its magnitude is
  inflated.
- EXP-0027 is the cautionary case: **+23.6%/yr on survivors → −1.5%/yr on
  ETFs.**

The historical CAGR must **not** be presented as though survivorship were
resolved. Any future delisting-complete dataset is a **separate evidence
stream** with its own methodology, never a substitution into this one.

---

## 9. OOS TAMPER / REPRODUCIBILITY STATUS

| requirement | mechanism | status |
|---|---|---|
| Append-only | `path.open("a")`; `append_session` refuses a duplicate `session` with `ForwardDataLeak` | **PASS** |
| Records cannot be edited | SHA-256 chain over `(previous + payload)`; `verify_chain` reports the **first** break; `load_sessions` **raises** rather than returning tampered rows | **PASS** |
| Parameters cannot change silently | `append_session` refuses on fingerprint drift (`FrozenConfigChanged`) | **PASS (but see below)** |
| Earlier observations immutable | each digest binds its predecessor | **PASS** |
| Missing data cannot become success | `continuity()` names every missing eligible session; "a missing session is reported, never filled" | **PASS, not automatic** |
| Broker reconciliation auditable | `reconcile()` reports, never corrects | **PASS** |
| **Selective deletion** | **a truncated prefix of a valid chain is itself a valid chain** | **LIMITATION** |
| **Restart cannot reset state** | the log is a file; nothing outside the chain records expected length | **LIMITATION** |

**Precise limitations:**

1. **Trailing truncation is not detectable by the chain.** Deleting records
   from the middle breaks it; deleting the last *N* leaves a self-consistent
   chain. The countermeasure exists — `continuity()` compares recorded
   sessions against an independently derived eligible calendar — but **it is
   invoked only by `scripts/phase4_checkpoint.py`, never by the recorder.**
   Detection therefore depends on somebody running the checkpoint.
2. **The fingerprint guard cannot catch live divergence.** It compares the
   observation's stamp against `frozen_fingerprint()` — and the recorder
   produced that stamp from the same defaults. Both sides read defaults, so
   the check can detect a change to the *source*, never a mismatch between
   source defaults and the *running* configuration. Combined with §1 this
   means every OOS observation would be stamped `da22011e…` while the account
   ran `569a8da7…`.
3. **Eligibility is enforced by the recorder script, not by `append_session`.**
   A direct call could file an ineligible session.

---

## 10. BLOCKERS BEFORE 2026-10-12

| # | blocker | severity | owner decision required |
|---|---|---|---|
| 1 | **Fingerprint ≠ live configuration** (`da22011e…` vs `569a8da7…`, `--interval 15m`) | **FAIL** | **Yes** — align the runner to `1d` (changes live behaviour) **or** re-issue the fingerprint over the live config (invalidates every prior citation). I have done neither |
| 2 | **Benchmark asymmetry** — strategy total return vs SPY **price** return, while the fingerprint declares `total_vs_total` | **FAIL** | Yes — must be settled *before* the first observation |
| 3 | **`CleanObservation.positions` never populated** — per-name sizing unverifiable from the record | **FAIL** | No, but it is a recorder defect and every unrecorded session is unrecoverable |
| 4 | **Clean recorder runs under Interactive logon** (`EventAwareTraderCleanRecorder`, principal `Interactive/yajga`). The trading task is already `S4U` | **LIMITATION → blocker** | Yes — needs an elevated re-install. **A session missed because nobody was logged in is a permanent hole by design** |
| 5 | **Account-level return includes a live BTC sleeve** ($5,491, 5.6% of equity, trading every 30s) and SGOV | **LIMITATION** | Yes — either isolate the measurement or accept and document that OOS measures the *account*, not the frozen candidate |
| 6 | `continuity()` not run by the recorder — trailing-truncation detection is manual | **LIMITATION** | No |
| 7 | Partial fills, orphan/duplicate orders, restart/recovery mid-session untested | **UNVERIFIED** | No |
| 8 | Benchmark fetch uses `include_today=True`; completeness depends on the 16:15 ET run time, not on a structural guard | **UNVERIFIED** | No |

**Not blockers — verified sound:** the hash chain and append-only discipline;
both learned-model gates; the news firewall; the ADV look-ahead guard; the
naked-stop check; broker reconciliation that reports rather than corrects;
and the derivation of the start date itself.

### The start date is correct and derived, not asserted

`freeze_date` = **2026-09-11** (last `accepted`/`reverted` row, EXP-0017),
embargo = **20 sessions** (= `max_holding_bars`, not a free parameter).
Counting real sessions forward from 2026-09-11: 09-14 … 10-09 is 20 sessions,
so the 21st — the first clean session — is **2026-10-12**. Confirmed.

**H-0019, H-0020 and H-0021 did not move it**: `freeze_date` counts only rows
whose decision is `accepted` or `reverted`, and all recent work was
research-evidence or rejected. **Note the standing property:** any future
experiment recorded as `accepted` or `reverted` will move the freeze date and
slide the clean-OOS start with it, automatically.

Current state: `data/forward-evaluation.jsonl` **does not yet exist**,
0 sessions, chain intact, and the recorder correctly **refuses** while the
embargo has not expired (5 of 20 sessions elapsed at the last local bar).

---

## 11. FINAL OOS READINESS

# **NOT READY**

Three **FAIL** items and one operational **blocker** stand between here and a
scientifically defensible clean OOS. None of them is a strategy problem, and
**none requires changing the frozen candidate's logic** — they are defects in
the machinery that is supposed to make the result checkable:

1. the fingerprint certifies a configuration the account does not run;
2. the benchmark is asymmetric and mis-declared;
3. the field that would prove sizing compliance is never written;
4. the recorder can silently not run, and a missed session cannot be recovered.

The strongest honest status remains **READY FOR CLEAN OOS *once items 1–4 are
resolved*** — and I have not resolved them, because items 1, 2 and 5 require
the owner's decision and the directive says to report rather than repair.

Nothing was validated or promoted. The candidate has no prospective evidence
and will have none before 2026-10-12.

### Governance end state

Registrations **21**, declared configurations **60**, chain intact.
Thirty-year reads **13**. `frozen_fingerprint()` still returns
`da22011e…c237b`. ATR ceiling 0.035, RSI 35/60, 20-bar cap, 2.5× ATR stop,
sizing, buckets, cash rules, guards, broker and learned models — **all
unchanged by this audit**. Clean OOS untouched, 0 sessions, start date
unchanged at 2026-10-12. No experiment registered. No live trading change.
