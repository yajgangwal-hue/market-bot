# Forensic audit of the current system

*2026-09-15. Read-only: nothing was modified to produce this. Paper account
PA30S46B79V8. Every number is from the actual repository, the actual
registry (`docs/experiments.jsonl`, 52 experiments) or the actual broker.
Anything not verified is marked **UNVERIFIED**.*

---

## 1. CURRENT SYSTEM

**Architecture.** A Python package (`src/event_aware_trader/`, 15,361 lines
across 40 modules) driven by two Windows Scheduled Tasks that invoke
PowerShell runners. There is no server, no message bus, no database — state
is JSON files on disk and the broker's own records. 58 test files, 9,575
lines, 767 tests.

**The modules that matter** (by size):

| module | lines | role |
|---|---|---|
| `autotrade.py` | 2,046 | the live loop: `run_once()` is the whole cycle |
| `strategy.py` | 1,194 | universe, correlation buckets, the *older* event-driven strategy |
| `cli.py` | 940 | command surface |
| `record.py` | 886 | performance record, benchmark verdict |
| `portfolio.py` | 876 | the backtest simulator |
| `broker.py` | 696 | Alpaca REST wrapper |
| `mean_reversion.py` | 540 | **the rule that actually trades** |
| `risk.py` | 447 | `RiskPolicy`, `CostModel`, `position_size` |
| `research.py` | 452 | research firewall, contamination ledger, registry |
| `news.py` | 296 | point-in-time news recorder (built 09-14/15) |
| `crypto_sleeve.py` | 173 | the BTC allocation |
| `regime.py` | 202 | regime classifier — **used by `strategy.py`, not by the live rule** |
| `leakage.py` | 172 | leakage auditor — **only ever called from its own test** |

**Decision pipeline (equity), exactly as coded:**

1. Task fires → `session-run.ps1` → rotate logs → refresh daily CSVs →
   `preflight` → `autotrade --asset-class equity` → `run_once()`.
2. `run_once` fetches daily bars (`fetch_alpaca_equity_bars`, `1d`,
   `adjustment="split"`) plus today's partial bar (`include_today=True`).
3. **Section 1** — walk open positions, compute RSI/ATR on the daily series,
   decide exits, call `close_out()` (cancel resting stop → wait → close).
4. **Section 1b** — `_reconcile_protective_stops`: every position gets a
   resting GTC stop; orphan sells cancelled.
5. **Section 1c** — `_learn_from_external_exits`: any symbol with stored
   entry features but no position is rebuilt from `fill_activities` into a
   training example, then `_retrain_now`.
6. **Section 2** — entries, **only inside the last 20 minutes of the
   session** (`entry_window_minutes=20`), max 3 per run.
7. **Section 2b** — reconcile stops again (added today; see §20.1).
8. `_sweep_cash` — idle cash above $2,000 floor and the 5% crypto reserve
   into SGOV.
9. Write `data/BENCHMARK.txt`, TradingView levels, audit log.

**Models.** One: `live_model.py`, a classifier fitted on 1,531 rows. Its
output is **not consulted** — `live_model_floor = 0.0` disables the veto,
because walk-forward showed it loses money monotonically (−0.45 to −2.52
points; AUC 0.5501 in-sample vs **0.5056** walk-forward). `trade_learning.py`
is a second, older model on `trade-examples.jsonl` (26,535 rows) — also not
in the money path. **The system trades on rules, not models.**

**Rules.** Long-only mean reversion:
- entry: `RSI(14) ≤ 35` AND `close > SMA(200)` AND `close ≥ $20` AND
  20-day average dollar volume ≥ $50M AND `ATR(14)/close ≤ 3.5%`
- stop: `close − 2.5 × ATR(14)`, resting GTC at the broker
- exit: `RSI(14) ≥ 60`, or the stop, or 20 trading days

**Indicators/features.** RSI(14), SMA(200), Wilder ATR(14), 20-day dollar
volume, and a conviction weight from depth of pullback off the 20-day high.
That is the entire feature set the money path uses.

**Timeframes.** Daily bars for every decision. The loop *runs* every 15
minutes but re-reads the same daily bar (plus today's partial one). 5-minute
bars exist but are used only for research and the manual peak-exit tool.

**Assets it can trade:** 230 US equities/ETFs + 10 crypto pairs (BTC, ETH,
SOL, LTC, LINK, AAVE, AVAX, DOT, UNI, BCH).
**Assets it actually trades:** equities from the 230, plus **BTC only** via
the sleeve. The other nine crypto pairs are never traded — the rule cannot
fire on them (EXP-0003: zero trades).

**Data sources.** Alpaca market data (bars, split-adjusted), Alpaca trading
API, `data/tbill.csv` (3-month bill, 1970–), and as of 09-15 seven news
sources (Alpaca + Fed/CNBC×2/Yahoo/MarketWatch/BBC RSS).

**Cadence.** Equity: every 15 min, 06:30–13:00 PT weekdays. Crypto: a
persistent worker, **every 30 seconds, 24/7**, kept alive by a 1-minute
watchdog. Execution: equities can only *enter* in the final 20 minutes;
exits can fire on any cycle.

**Event-driven or interval-driven?** **Interval-driven, entirely.** Nothing
subscribes to a stream. There is no websocket, no webhook listener in the
money path (`webhook.py` exists, 139 lines, **UNVERIFIED** whether wired —
it is not imported by `autotrade.py`).

**Can it react between intervals?** No for equities (15-min granularity).
Effectively yes for crypto (30s). The GTC stops *do* work continuously at
the broker — that is the only genuinely continuous protection.

**Multiple positions:** yes, max 12, one per correlation bucket.
**Short:** no. Long-only; no short code path exists.
**Cash:** yes — median 74% idle in simulation, swept into SGOV.
**Crypto 24/7:** yes, the sleeve only.
**Broker integrations:** Alpaca paper only. `_require_paper_endpoint`
refuses any non-paper endpoint; `setup-keys.ps1` rejects live keys.
**Simulation only:** `portfolio.py`, `research.py`, `evaluation.py`,
`backtest.py`, `leakage.py`, all `mr_*` exit variants, `market_gate_*`,
`mr_take_profit_*`.
**Production/live:** `autotrade.py`, `broker.py`, `crypto_sleeve.py`,
`news.py`, `peak_exit.py` (manual tool), the two PowerShell loops.

---

## 2. EXACT CURRENT PERFORMANCE

Thirty years, 1996–2026, 229 symbols, $100,000 start, every live constraint
on (closing-window fills, gapped stops fill at the open, 3 entries/day,
mark-to-market guard, whole shares).

| metric | strategy alone | **with idle cash parked (what the account does)** |
|---|---|---|
| total return | 369.3% | **454.8%** |
| CAGR | 5.17% | **5.75%** |
| volatility (ann.) | 8.2% | **6.7%** |
| Sharpe (rf = 2.30% actual bills) | 0.38 | **0.53** |
| Sortino | 0.53 | **0.75** |
| max drawdown | −12.9% | **−11.2%** |
| Calmar | 0.40 | **0.51** |
| worst day | −3.84% | −3.21% |
| worst month | −6.50% (Aug 2019) | −5.49% (Aug 2019) |
| time underwater | 87% of days | **80% of days** |
| longest underwater run | 1,277 sessions (5.1 yrs) | **609 sessions (2.4 yrs)** |
| ruin prob. (25% DD) | 18.0% | **2.2%** |

Trade-level (30-year honest baseline): **1,522 trades, 54% win rate,
profit factor 1.39**, average hold 14.0 days, longest losing run 19,
average heat 3.91%.
Decade: 712 trades, 55%, PF 1.44, Sortino 1.26.
Average win $1,584 / average loss $1,298. Top 50 trades = **67% of all
profit**.

**Costs.** Commission $0/share. Half-spread 2 bps + slippage 4 bps = **6 bps
one-way**, charged both sides. Sensitivity: 3/6/9/12 bps → decade
+140.0%/+127.6%/+111.2%/+91.8%. **Market impact: not modelled.**
**Turnover:** partially measured — $29.4M through improvable exits over 30
years on a $100k account. Full turnover **UNVERIFIED**.
**Worst single trade / recovery time per drawdown: UNVERIFIED** (not
computed; time-underwater is reported instead).

**Which numbers are which:**

| label | figure | status |
|---|---|---|
| published/legacy | 9.14% decade, 5.66% 30yr | stops filled *at* the stop — too favourable |
| **honest** | 8.35% decade, 5.10–5.75% 30yr | gapped stops fill at the open |
| in-sample | all of the above | every parameter chosen on this data |
| validation | **none exists as a separate split** | — |
| out-of-sample | **none** | — |
| holdout | thirty-year window — **CONTAMINATED**, 30 recorded touches | — |
| forward/live | 3 sessions: account −1.16% vs SPY TR −0.90% | **NOT A FINDING** (floor is 60) |

**Which number should you trust?** None of them as a forecast. The most
defensible statement is a *range*: **2.24%/yr** (46-ETF survivorship-free
control, 30 years) to **5.75%** (230-name survivor universe, parked). The
gap between those two is survivorship bias, and it is the largest single
uncertainty in every performance number here. The 3-session forward record
is the only uncontaminated measurement and it is far too short to mean
anything.

---

## 3. SPY BENCHMARK

Identical window (1996-01-01 → 2026-09-05), identical $100,000, rf = 2.30%
(the actual mean 3-month bill over the period).

| | CAGR | vol | Sharpe | Sortino | maxDD | Calmar |
|---|---|---|---|---|---|---|
| **bot (parked)** | 5.75% | 6.7% | 0.53 | 0.75 | −11.2% | 0.51 |
| SPY **price** return | 8.55% | 19.2% | 0.40 | 0.57 | −56.5% | 0.15 |
| SPY **total** return | ~10.3% **ESTIMATE** | 19.2% | ~0.49 | ~0.68 | ~−55% | ~0.19 |
| SPY vol-matched to 6.7% | 3.34% | 6.7% | 0.18 | 0.25 | −23.4% | 0.14 |
| SPY vol-matched to 8.2% | 4.03% | 8.2% | 0.24 | 0.34 | −28.1% | 0.14 |

**Differences (bot minus SPY price return):** CAGR **−2.80 pts**, Sharpe
**+0.13**, Sortino **+0.18**, maxDD **+45.3 pts better**, vol **−12.5 pts**.
**Against SPY total return:** CAGR **≈ −4.5 pts**, Sharpe ≈ +0.04, Sortino
≈ +0.07.
**Against vol-matched SPY:** CAGR **+2.41 pts better**, Sharpe +0.35,
maxDD +12.2 pts better.

**Worst periods:** 2008 bot −5.1% vs SPY −38.3%; 2022 bot −8.0% vs −19.5%;
2001 bot **+1.8%** vs −12.9%; 2000–02 bot +3.8/+4.4/−0.3% vs
−10.7/−12.9/−22.8%. SPY's ten worst days since 1996: the bot lost between
0.0% and 1.2% on them. Beta 0.205, correlation 0.483 on 7,719 aligned days.

**Caveats that matter.** The SPY total-return figure before 2016 is an
ESTIMATE — no dividend-adjusted series before 2016 is reachable from this
machine (Alpaca history starts 2016; the Yahoo path fails on a certificate
error). The decade dividend contribution is MEASURED at +1.58 pts/yr
(15.00% TR vs 13.42% PR). The vol-matched rows assume uninvested capital
earns 0%; at the bill rate each would gain roughly (1−scale) × 2.30%/yr.

---

## 4. DATA AUDIT

| dataset | source | universe | span | TF | point-in-time? | survivorship | corporate actions |
|---|---|---|---|---|---|---|---|
| `deep/` | Alpaca | 230 | 2016–2026 | 1d | no | **YES, present** | splits adj; **no dividends** |
| `long/` | Alpaca | 229 | 1996–2026 | 1d | no | **YES, present** | splits adj; **no dividends** |
| ETF subset | Alpaca | 46 broad ETFs | both | 1d | no | **survivorship-free control** | same |
| crypto | Alpaca | BTC/ETH/SOL + meme | 2014–2026 | 1d | no | n/a | n/a |
| `data/*.csv` live | Alpaca | 241 files | rolling | 1d | no | yes | splits |
| 5-min cache | Alpaca | 98 syms | 2023-06– | 5m | no | yes | splits |
| `data/tbill.csv` | FRED-style | 3-mo bill | 1970–2026 | 1d | yes | n/a | n/a |
| `data/news/` | 7 sources | mixed | **2026-09-14–** | event | **YES** (`fetched_at`) | n/a | n/a |
| `live-training.jsonl` | own trades | 230 | replay + live | per-trade | partially | inherits | n/a |

**Timestamps.** ISO-8601 with explicit UTC offset (`2024-07-08T04:00:00+00:00`);
daily bars are stamped at 04:00 UTC = US session date. Timezone handling is
explicit, not inferred.

**Trustworthy:** `tbill.csv` (real rates, real dates); the ETF-subset control
(cannot delist); the news corpus (genuinely point-in-time by construction).
**Limited:** every equity price set — survivorship is present and measured
at up to 3–4 pts/yr of inflated return; **dividends are absent from the
simulator entirely**, which understates returns by roughly the dividend
yield of held names (conservative bias, but it means the bot's own numbers
and the SPY total-return numbers are not on the same footing).
**Revisions:** none of the price data is revision-tracked. **UNVERIFIED**
whether Alpaca back-adjusts historical bars after the fact.
**Missing data:** symbols with <400 bars are dropped silently by the loaders.

---

## 5. LOOK-AHEAD BIAS AUDIT — where the information boundary is

**The boundary is `fetch_alpaca_equity_bars(..., include_today=False)`**
(`data.py:343`). By default the *current, partial* daily bar is dropped, so
every rule computation sees only completed sessions. Exactly two call sites
pass `include_today=True`: `autotrade.py:674` (`_todays_bars`, deliberate —
live must see the forming bar to act in the closing window) and
`scripts/exit_at_peak.py:129`. That is the whole boundary, and it is narrow
enough to state precisely.

**Concrete paths checked:**

- **Rolling calculations** — `mean_reversion.evaluate()` is documented
  "Decide from bars up to and including the last one. No lookahead" and every
  indicator (`sma`, `rsi`, `wilder_atr`) is computed over `closes[:]` ending
  at the decision bar. **Clean.**
- **Stop evaluation** — `portfolio.py` captures `prior_high` *before* the
  current bar updates `highest_high`, specifically so a trailing stop cannot
  be compared against a high it could not have seen. **Clean, and this was a
  fixed bug.**
- **Gapped stop fills** — `realistic_stop_fills` fills at `bar.open` when the
  open is below the stop, not at the stop. **Clean.**
- **Take-profit fills** — fills at `bar.open` if gapped through, else at the
  level when `bar.high` reaches it. Correct for a limit. **Clean, tested.**
- **Entry fill** — `entry_fill="signal_close"` fills at the same bar's close.
  The signal is computed from that close, so the decision and the fill are
  simultaneous. This is realistic *only because* live places the order in the
  final 20 minutes. **Defensible but it is the tightest assumption in the
  system** — any widening of the live entry window breaks the equivalence.
- **Conviction cache** — was keyed on `(symbol, len(history))`, which
  collided across runs and moved a 30-year result by 0.5 pts. Now keyed on
  `history[0].timestamp` as well. **Fixed; was a real leak of cross-run
  state.**
- **News** — `visible_at()` filters on `fetched_at`, not the publisher's
  timestamp, and a row without a fetch time is **never** visible. **Clean by
  construction** — but only for news recorded from 2026-09-14 onward.
- **Labels** — `append_example` labels `1 if realized_r >= 1.0`, computed at
  exit from broker-reported P&L. No future data in the feature vector; the
  features are snapshotted at entry. **Clean.**

**Where leakage genuinely exists:**

1. **Train/test contamination — severe and acknowledged.** Every parameter
   was chosen on the same data used to report performance. 37 registry
   touches on the decade, 30 on the thirty-year window. This is not a
   suspicion; it is counted.
2. **Model selection** — `live_model.json` was fitted on the full replay,
   then evaluated. The walk-forward check (AUC 0.5501 → 0.5056) is what
   exposed it. The model is disabled as a result.
3. **Hyperparameter selection** — RSI 35, stop 2.5 ATR, cap 20%, hold 20
   days were each swept on the *same* windows their results are quoted on.
4. **Future asset selection / survivorship** — the universe is today's
   liquid 230. A name that delisted in 2003 is absent from the 1996 backtest.
   This is the single largest quantified leak: the overnight-gapper study
   showed 23.6%/yr on survivors and **−1.5%/yr** on a universe that cannot
   delist.

`leakage.py` exists and is good (it demonstrates 0.5588 honest vs 1.0000
with the outcome as a feature) — **but it is only ever called from its own
test file.** It has never been run against the live model.

---

## 6. BACKTEST OVERFITTING

From `docs/experiments.jsonl` (the registry is complete from 2026-09-08):

- **52 experiments**, **186 configurations**
- decisions: 30 rejected, 11 measured, 6 inconclusive, 3 accepted, 2 reverted
- **failed experiments: 32** (rejected + reverted)
- families: exits 12, crypto 6, filters 6, sizing 5, shorting 4, entries 3,
  measurement 3, benchmark 2, news 2, overnight 2, capital 2, others 5
- **exit combinations alone: 12 experiments** spanning trailing stops (4),
  partials (2), momentum (2), regime, vol-trail (2), take-profit (5),
  adaptive take-profit (6)
- **assets:** 230 equities + 10 crypto + 46-ETF control
- **timeframes:** 1 (daily) for decisions; 5-min for research only
- **same test period examined:** decade **37 times**, thirty-year **30 times**

**Has the strategy been selected using the data used to evaluate it?**
**Yes. Unambiguously.** This is stated in the code (`research.DATASETS` marks
every historical set `contaminated`) and is the reason the research firewall
exists.

**What exists:**
- deflated Sharpe — `stats.deflated_sharpe_ratio`, wired to the registry's
  own configuration count. At the observed trial spread (sd 0.081 from the
  11-variant exit sweep) over 117 equity-window configurations: **DSR 0.993**.
  At an assumed spread of 0.25: **0.53**. At unit variance: **0.000**.
- per-year distribution reporting (`walk_forward_years`) — median, quartiles,
  worst year, share positive
- both-halves checks on nearly every experiment
- a survivorship-free control universe
- an append-only registry with `related_before` counts

**What is missing:**
- **purged cross-validation** — none
- **embargo periods** — none
- **combinatorially purged CV (CPCV)** — none
- **explicit probability of backtest overfitting (PBO)** — never computed
- **parameter stability surfaces** — sweeps report point results, not
  stability neighbourhoods; "clean peak at 2.5 ATR" is asserted from five
  points with no neighbourhood analysis
- **true walk-forward with per-fold refitting** — `walk_forward_years`
  deliberately raises `NotImplementedError` for refitting, because slicing
  one run would leak later fits into earlier folds. Honest, but it means no
  refit-based walk-forward exists.

**Vulnerability estimate.** High for the *magnitude* of the reported return,
low-to-moderate for the *existence* of the edge. The edge survives a
survivorship-free control (2.24%/yr, positive in both halves) and both
halves of both windows, which is real evidence. But 186 configurations on
two windows means the specific parameter values are fitted, and the honest
expectation for forward return is the bottom of the 2.24%–5.75% range, not
the top.

---

## 7. TRAIN / VALIDATION / TEST SEPARATION

```
TRAINING:    1996-01-01 → 2026-09-05   (thirty_year, 229 names)
VALIDATION:  DOES NOT EXIST AS A SEPARATE SPLIT
HOLDOUT:     1996-01-01 → 2026-09-05   — the SAME data. CONTAMINATED.
LIVE/FORWARD: 2026-09-11 → present     (3 sessions)
```

The decade (2016-01-01 → 2026-09-05) was the development set; the thirty-year
window was intended as the deciding holdout. **It has been used for 30
recorded accept/reject decisions and is contaminated.** The project's own
rule — once a holdout decides something it is spent — is encoded in
`research.DATASETS` and declares all four historical sets contaminated.

**The only clean data is the forward record: 3 sessions.** The floor for
calling it a finding is 60 sessions (`benchmark.MINIMUM_SESSIONS`).

---

## 8. EXECUTION REALISM

| aspect | how the simulator handles it |
|---|---|
| bid/ask | **not modelled** as a spread; folded into 2 bps half-spread |
| spreads | flat 2 bps one-way, equities; **measured per-pair** for crypto |
| slippage | flat 4 bps one-way, constant across size/volatility/time |
| commissions | **$0.00/share** |
| market orders | the only type; both sim and live send market |
| limit orders | **never used** — broker only sends `type: market` |
| stop orders | live: real GTC stops at Alpaca. Sim: gapped stops fill at the **open** |
| stop gaps | **modelled correctly** (`realistic_stop_fills`) |
| partial fills | **NOT modelled** (0 references) |
| latency | **NOT modelled** (0 references) |
| liquidity | live enforces `max_volume_participation = 2%`; **the simulator does NOT** |
| market impact | **NOT modelled** (0 references) |
| order size | capped at 20% of equity, whole shares live |
| volume constraints | live only — see liquidity |
| overnight gaps | modelled (bar opens differ from prior closes) |
| intrabar ambiguity | resolved conservatively for stops (worst), correctly for limits (best) |
| price jumps | present in the data; no separate model |

**Unrealistic assumptions, most suspicious first:**

1. **Liquidity is enforced live but not in the backtest.** Every quoted
   return comes from a simulator with no participation cap; the live bot has
   one. The sim can take positions the bot would refuse.
2. **Flat 4 bps slippage regardless of conditions.** Real slippage widens
   exactly when this strategy trades — into broad sell-offs that push many
   names oversold at once. Systematically optimistic in the worst moments.
3. **Entry fills at the signal bar's close.** Defensible only because live
   trades the closing window; there is zero latency allowance between
   deciding and filling.
4. **No partial fills.** A 20%-of-equity position in a $50M-ADV name is
   assumed to fill whole at one price.
5. **No dividends.** Conservative (understates the bot) but it means bot and
   SPY-total-return are not measured on the same basis.
6. **`quantity` is a float in the simulator** unless whole-shares is forced;
   the production candidate forces whole shares, but any run that forgets is
   flattered.

---

## 9. ENTRY ANALYSIS

**What creates an entry:** all five gates pass — RSI(14) ≤ 35, close >
SMA(200), close ≥ $20, 20-day ADV ≥ $50M, ATR/close ≤ 3.5%, and a computable
positive stop.
**What confirms it:** nothing. There is no second confirmation step — the
gate *is* the decision.
**What invalidates it:** any single gate failing; correlation bucket already
occupied; ≥12 open positions; insufficient cash after the 5% reserve; the
mark-to-market daily guard; being outside the 20-minute window.

**Entry quality, measured:**
- average heat (worst adverse move while open): **3.91%** over 30 years
- **the market moves against the position first in the large majority of
  cases** — this is a mean-reversion book; `captured` on stop exits is
  **−3.07**, meaning stopped trades were underwater essentially throughout
- MFE/MAE are recorded per trade (`highest_high`, `lowest_low` on every
  `ClosedTrade`, and on live exits since 09-13)
- exact "% favourable immediately after entry": **UNVERIFIED** — MFE/MAE are
  stored but a first-N-days decomposition has not been run

**Best/worst regimes (EXP-0043, 1,501 trades bucketed by SPY state at entry):**

| market state at entry | trades | mean R | win% |
|---|---|---|---|
| SPY below 50dma | 677 | **0.211** | 56% |
| SPY above 50dma | 824 | 0.103 | 52% |
| SPY 2–5% off its high | 298 | **0.316** | 61% |
| SPY at highs (0 to −2%) | 450 | **0.059** | 50% |

**Entries or exits — which loses more expected value?** **Exits, decisively.**
Entries are already regime-sensitive in the right direction and the one
attempt to improve their timing (skip near market highs) *lost* money at
every threshold (EXP-0044). Exits carry a measured, unclaimed +0.73 to +1.47
CAGR points of available improvement (§10).

---

## 10. EXIT ANALYSIS

Thirty years, honest fills:

| exit | trades | P&L | captured | gave back | verdict |
|---|---|---|---|---|---|
| **reverted** (RSI ≥ 60) | 451 | **+$994,227** | **0.92** | 0.65% | near-optimal |
| **stop** | 542 | **−$829,266** | **−3.07** | **8.36%** | **the leak** |
| **time_exit** (20 days) | 529 | +$191,260 | −0.34 | 3.48% | mediocre |

Average holding 14.0 days. Trailing exits, partial exits, momentum exits and
regime exits **do not exist in production** — all were tested and rejected
(EXP-0036: partials and momentum raise win rate and lose money; trail
1.0R/3.0ATR +0.06 and regime +0.03 over 30 years, both rounding-level).
Manual exits exist as a directed tool (`exit_at_peak.py`), not a rule.

**The biggest exit leak: the stop.** 542 trades, −$829k, giving back 8.36%
of entry. But it **cannot be improved by timing** — a stop fills when it is
hit and the price is not a choice. The measurement confirms this at exactly
**0.00 upside per share**. Four separate attempts (widths 2.0–4.0, trailing,
partial, momentum) all lost money.

**The improvable leak is the other 968 trades**, which fill at the day's
close (EXP-0048):

| | baseline | exit at day's high (ceiling) | half the range |
|---|---|---|---|
| 30 years | 5.17% | 6.50% (+1.33) | **5.90% (+0.73)** |
| decade | 8.41% | 11.18% (+2.77) | **9.88% (+1.47)** |

Average upside per share: reverted 0.60% of exit price, time_exit 0.97%,
stop 0.00%.

**And a live-vs-sim divergence measured on real 5-minute bars**, 155 exits:

| when the rule says exit | proceeds vs selling at the trigger |
|---|---|
| sell at trigger ← **what live does** | baseline |
| sell at the day's close ← **what the backtest assumes** | **+0.65%** (early trigger) |
| sell into strength (pullback rule) | +0.09% |

**Live is exiting up to 0.65% worse than every backtested number assumes.**
This is not an enhancement opportunity; it is a discrepancy between the
system and its own reported results.

Early or late? The stop is *late* by construction (gives back 8.36% after
being up). `time_exit` is arbitrary rather than early or late — `captured`
−0.34 means it exits below the best price available roughly as often as not.
`reverted` at 0.92 captured is close to the best achievable.

---

## 11. POSITION SIZING

`risk.position_size(equity, entry, stop, policy, costs)`:

```
loss_per_share = (entry − stop) + round_trip_cost_per_share
risk_budget    = equity × 0.005
quantity       = min(risk_budget / loss_per_share,
                     equity × 0.20 / entry)      → floored
```

| factor | accounted for? |
|---|---|
| volatility | **yes, indirectly** — the stop is 2.5×ATR, so ATR sets size |
| stop distance | **yes** — it is the denominator |
| costs | **yes** — round-trip cost added to loss per share |
| liquidity | live only (2% participation); **not in the simulator** |
| spread | yes, via the cost model |
| confidence | **partially** — `conviction` (0.5–1.5× from pullback depth) |
| correlation | **yes, as a hard gate** — one position per bucket |
| portfolio exposure | yes — 20% per name, 12 positions, 5% crypto reserve |
| drawdown | **no** — size does not shrink after losses |
| regime | **no** — tested (EXP-0045/0047) and rejected, worse on both axes |
| expected value | **no** |
| uncertainty | **no** |

**Maximum position:** 20% of equity. **Maximum portfolio exposure:** 12
positions × 20% = 240% nominal, but bucket limits and cash cap it; observed
simulated maximum is **100%**, p90 **83.7%**, median **26.4%**.
**After a losing streak:** nothing changes — risk is a fixed 0.5% of *current*
equity, so size shrinks only as equity shrinks (mild natural de-risking).
**After a winning streak:** size grows with equity. No acceleration.
**Can sizing become dangerously aggressive?** **No.** There is no
martingale, no confidence scaling beyond 1.5×, no leverage. The 1.5%
mark-to-market daily halt and the 20% cap bound it. The realistic failure is
the opposite — 12 correlated longs in one sell-off, which the bucket rule
constrains but does not eliminate (today: IYR + XHB = 37.5% of exposure,
different buckets, same rate bet).

---

## 12. RISK

| control | value | enforced |
|---|---|---|
| max position risk | 0.5% of equity per trade | sim + live |
| max notional per name | 20% | sim + live |
| max open positions | 12 | sim + live |
| max per correlation bucket | 1 | sim + live |
| max daily loss | 1.5% (mark-to-market, live) | live; sim via `mark_to_market_guard` |
| max weekly loss | 6% | live |
| liquidity | 2% of ADV | **live only** |
| leverage | none — cash only, margin never used | both |
| crypto reserve | 5% withheld from the equity book | live |
| cash floor | $2,000 unparked | live |
| emergency shutdown | `data/run-until.txt` date; `Unregister-ScheduledTask` | live |
| abnormal volatility | `max_atr_fraction 3.5%` rejects the candidate | both |

**Market crashes very fast:** GTC stops rest at the broker and fire without
the bot. Gapped stops fill at the open — modelled, and measured as costing
0.56 CAGR points versus the fiction of filling at the stop. 2008 result:
−5.1% parked. **The real exposure is a gap-down before the reconciler runs**
— which is exactly the defect found today (§20.1).
**Liquidity disappears:** live refuses orders above 2% of ADV; the simulator
does not, so backtests overstate what is fillable.
**Data unavailable:** `preflight` blocks the cycle on stale price files; the
broker wrapper retries and logs `clock unavailable` → `status: halted` (this
happened on 2026-09-11 during an Alpaca 500). Positions keep their stops.
**Broker behaves unexpectedly:** the exit path requires the 403 on a
protected close, cancels, waits for the cancel to settle (bounded 10s), then
closes; failures are retried next cycle. The FakeBroker double mirrors
Alpaca's refusals (fractional GTC stops, reserved shares).

---

## 13. REGIME DETECTION

`regime.py` (202 lines) classifies:
- **trend**: uptrend / downtrend / sideways (long MA slope + distance)
- **volatility**: calm / normal / elevated / stressed (realized vol percentile)
- emits `risk_multiplier`, `allows_new_long`, reasons, blockers

| regime | detected? |
|---|---|
| bull / bear / sideways | **yes** (trend label) |
| high / low volatility | **yes** (percentile bands) |
| volatility expansion/contraction | **partially** — percentile only, no rate of change |
| trend | yes |
| reversal, breakout, failed breakout | **no** |
| risk-on / risk-off | **no** (the label exists in `events.py` for headlines, not price) |
| liquidity stress | **no** |

**Critical finding: the live rule does not use any of it.**
`classify_regime` is imported by `strategy.py` (the older event-driven
strategy, not what trades) and by `portfolio.py` only behind the
default-off `mr_regime_exit`. Grep confirms `mean_reversion.py` contains
zero references to regime.

**Does the strategy behave differently by regime?** Only through the
per-name 200-day filter, which empties the candidate list in a bear market
— that is why 2008 was −5.1%. That is emergent, not designed. Explicit
regime adaptation has been tested twice and rejected (EXP-0009, EXP-0045).

---

## 14. CONTINUOUS TRADING

| capability | equities | crypto |
|---|---|---|
| monitor continuously | **no** — 15-min polls | **near** — 30s polls |
| receive data continuously | **no** — REST pull only | no — REST pull |
| react immediately to events | **no** | no |
| exit between intervals | **only via resting GTC stops** | 30s |
| enter between intervals | **no** — and only in the last 20 min | 30s |
| manage positions continuously | no | 30s |
| respond to breaking news | **no** — news is recorded, never consulted | no |
| respond to volatility shocks | only the ATR gate at entry | no |

**What blocks it.** There is no streaming input anywhere. Everything is
`urllib.request` polling of Alpaca REST. There is no event loop, no
websocket client, no queue. The equity cadence is Windows Task Scheduler,
whose repetition floor is **1 minute** — which is why the crypto 30-second
cadence required a persistent worker process plus a watchdog.

**Architectural changes required for always-watching:**
1. Replace REST polling with Alpaca's **websocket stream** (trades, quotes,
   bars) — a persistent process, not a scheduled task.
2. An **event loop** that reacts to ticks rather than a `run_once()` invoked
   on a timer. `run_once` is currently a batch function ~1,000 lines long
   that assumes it starts cold each time.
3. **State in memory** with periodic persistence, instead of read-modify-write
   JSON on every cycle (which is also why two loops need separate state files).
4. A **decision throttle** — reacting to every tick would breach rate limits
   and overtrade; the rule is daily-bar based, so tick reaction only makes
   sense for *exits* and *stops*, not entries.
5. **Supervision**: the crypto watchdog pattern (PID + heartbeat +
   kill-all-before-relaunch) generalised, because a persistent process that
   dies silently is worse than a cron job.

Honest note: **the strategy itself is daily.** Continuous monitoring would
improve *exit execution* (worth up to 0.65% per exit, measured) and *stop
responsiveness*. It would not make a daily-bar mean-reversion rule trade
more often, and forcing it to would be the overtrading the holding-period
sweep already priced at −39.3%.

---

## 15. NEWS / INFORMATION

**Does it use external information?** It **records** it; it does not **use**
it. As of 2026-09-15, seven sources: Alpaca (per-symbol) + Fed press, CNBC
economy, CNBC top, Yahoo Finance, MarketWatch, BBC business.

- **Timestamps:** every row carries both the publisher's `created_at` and
  the bot's own `fetched_at`.
- **Processing:** `events.classify_headline` — keyword categories
  (inflation, central_bank, energy, growth, geopolitics, earnings, other)
  and a stance, deliberately conservative (defaults to `other`/`neutral`).
- **Duplicates:** deduplicated by id within a day file; RSS ids are
  `source:link`, stable across refetches.
- **Source reliability:** **not determined.** No weighting, no scoring.
- **Replayable as known at the time?** **Yes** — `visible_at(rows, moment)`
  filters on `fetched_at` and never shows a row lacking one. But only for
  data recorded from 2026-09-14 onward. **Corpus size today: 2 days.**

**Why it is not wired to trading:** EXP-0040/0041 measured the owner's own
example — 10 Apple September launches, event dates derived from the API
rather than recalled. Run-up 30 sessions *before*: **+5.11%**, positive 9/10.
Buying **on** the day: +1d **−0.58%** (positive 3/10), +5d −0.33%, +20d
+0.78%. Buy-the-rumour-sell-the-news.

**Infrastructure still required to use news safely:** months of point-in-time
corpus; a labelling scheme tying headlines to forward returns without
lookahead; source-reliability weighting; and a test run through the same
firewall (registered hypothesis, both halves, deflated Sharpe).

---

## 16. CRYPTO

- **Assets:** 10 pairs configured; **only BTC/USD is ever traded.**
- **Exchange:** Alpaca crypto (paper).
- **Data:** Alpaca daily bars, BTC 2014–, ETH 2017–, SOL 2020–, meme 2021–.
- **Timeframe:** daily for the trend decision; the worker polls every 30s.
- **Fees:** modelled as measured per-pair round-trip spreads
  (`MEASURED_ROUND_TRIP`): ETH 0.0237%, BTC 0.0342%, SOL 0.0589%, …
  BCH 0.617%, PEPE 0.293%, DOGE 0.320%, TRUMP 0.317%, WIF 0.327%,
  SHIB 0.382%, BONK 0.727%.
- **Slippage/liquidity/funding:** **not separately modelled**; no funding
  (spot only, no perps).
- **24/7:** yes — persistent worker, 30s, watchdog-supervised.
- **Meme support:** the code can trade them; the allocation rule refuses to.

**Why no edge was found:**
- **BTC/ETH/SOL and the other seven** (EXP-0003): mean reversion, trend
  following, breakout and cross-sectional momentum were all tested on Alpaca
  history and a decade of verified Yahoo data. **Every family lost.** The
  cause is structural, not parametric: sizing by risk budget over stop
  distance gives an asset with a 4–13% daily range a position too small to
  matter. The shipped rule produced **zero trades** on crypto.
- **What *was* validated** (EXP-0015) is an **allocation**, not a trade: hold
  BTC while above its own 100-day average, at 5%. Correlation with the equity
  book **+0.035**; decade CAGR 7.60% → 9.13%, maxDD −14.1% → −13.5%. Graded
  **weak** — one number on one window, and the return is 0.05 × BTC's own
  history rather than an edge.
- Larger allocations, ETH, 50/50 splits (EXP-0032): return rises, **second
  half falls at every step**. Rejected.
- Other trend windows (EXP-0033): 60.9/73.9/64.0/76.7/60.7 — sawtooth, noise.
- Trailing stop on the sleeve (EXP-0035): 74.7/61.0/63.0/65.2 vs 64.0 plain —
  one good cell, noise. **This is the direct answer to "can it be managed
  with stops": tested, adds nothing.**

---

## 17. MEME COINS

**DOGE, SHIB, PEPE, TRUMP, BONK — the evidence (EXP-0034):**

| | finding |
|---|---|
| measurable edge | **No.** All lose or fail both halves. DOGE: 2.7%/yr at **−95% drawdown** vs 5.4% simply holding |
| liquidity | adequate on Alpaca for the size this account trades |
| spreads | **measured, and punishing**: DOGE 32 bps, SHIB 38, PEPE 29, TRUMP 32, WIF 33, BONK **73** round-trip — 10–20× BTC's 3.4 bps |
| slippage | **UNVERIFIED** separately; folded into the measured spread |
| historical data | **thin**: DOGE 2,081 bars, SHIB 1,279, PEPE 592, TRUMP 599, BONK 209, WIF 206. BONK and WIF have under a year |
| realistic execution | yes — spreads were measured live, not assumed |

**Verdict from the evidence:** tradeable, unallocated. The spread alone
consumes the edge, and with 206–599 bars for the newest names there is not
enough history to establish one either way.

---

## 18. STRATEGY DIVERSIFICATION

| # | source | signal | exploits | best regime | fails in | hold | corr | contribution |
|---|---|---|---|---|---|---|---|---|
| 1 | mean reversion | RSI ≤ 35 above SMA200 | overnight gap after oversold pullbacks | pullbacks in an uptrend; 2× edge below SPY 50dma | sustained bear with no bounces | 14 days avg | — | **essentially all P&L** |
| 2 | cash parking | none — mechanical | the risk-free rate on 74% idle cash | high rates | ZIRP | continuous | ~0 | **+1.49 CAGR pts** |
| 3 | BTC sleeve | BTC > 100dma | BTC's own trend | crypto bull | crypto bear/chop | weeks–months | **+0.035** | decade +1.5 CAGR, weak evidence |

**Is it diversified? No — it is one strategy plus two overlays.**

Source 1 is the entire equity edge. Sources 2 and 3 are not independent
*edges*: parking is a rate, not a strategy, and the sleeve is a 5% beta
allocation to an uncorrelated asset. There is one signal, one direction
(long), one timeframe (daily), one behaviour (mean reversion).

The correlation-bucket rule diversifies *within* source 1, and even that is
imperfect: homebuilders and real_estate are separate buckets but the same
rate bet (today, 37.5% of equity exposure in both while the 10-year yield hit
its highest since 2007).

---

## 19. WHAT THE BOT IS MISSING

**CRITICAL — fix before any expansion**
1. Live exits fill up to **0.65% worse** than every backtested number assumes.
2. No uncontaminated evaluation data. 3 forward sessions against a 60-session floor.
3. Liquidity cap enforced live but **not in the simulator** — the two disagree.
4. `leakage.py` has never been run on the live model.
5. Only one source of edge. If mean reversion stops working, there is nothing else.

**HIGH VALUE**
6. Exit execution: +0.73 to +1.47 CAGR points of measured, unclaimed ceiling.
7. Dividends absent from the simulator — bot and SPY are not on the same basis.
8. Survivorship: the true expectation is the 2.24%–5.75% range, not the top.
9. Parameter stability surfaces instead of point sweeps.
10. Streaming data for exit responsiveness (not for more trading).

**EXPERIMENTAL**
11. The news corpus, once months of point-in-time data exist.
12. A second, genuinely uncorrelated edge.
13. PBO / CPCV / purged-embargoed CV.

**LOW VALUE — do not build**
14. Shorting. Four tests, all rejected, large samples.
15. Regime gating or regime sizing. Both rejected on both axes.
16. Meme coins. Spreads eat the edge; data too thin.
17. A directional predictor. AUC 0.5056 walk-forward; the veto lost money.
18. More exit variants. Twelve experiments; two cleared by rounding.

---

## 20. TOP 10 WEAKNESSES I WOULD FIX FIRST

### 1. Positions opened in the closing window had no overnight stop
**Problem** Bracket legs are `time_in_force: day` and expire at 16:00; the GTC
reconciler ran only *before* entries. **Evidence** MDY, 29 shares, $19,425,
found naked today. **Why** It is the overnight gap that carries 73.6% of
returns. **Impact** Removes an unbounded tail risk. **Risk** Low.
**Validate** Ordering test — one reconcile before entries, one after.
**Before new strategies?** **YES — already fixed today**, listed because it
was live for four days and nothing failed loudly.

### 2. Live exit fills are 0.65% worse than the backtest assumes
**Problem** The rule sells at the trigger cycle; the simulator assumes the
close. **Evidence** 155 exits on 5-min bars: close beats trigger by +0.652%
(early), +0.289% (midday), +0.120% (late). **Why** Every quoted return is
built on the better price. **Impact** Up to +0.65%/exit, ~968 improvable
trades. **Risk** Moderate — touches the exit path, where this project's worst
bugs have lived. **Validate** Forward A/B on live exits, and re-run the
5-min harness. **Before new strategies? YES.**

### 3. No uncontaminated evaluation data
**Problem** 186 configurations on two windows; the holdout is spent.
**Evidence** `research.DATASETS` marks all four historical sets contaminated;
37 decade touches, 30 thirty-year. **Why** No further historical comparison
can accept anything. **Impact** Restores the ability to make decisions.
**Risk** None — it is discipline, not code. **Validate** 60 forward sessions.
**Before new strategies? YES — this is the gate.**

### 4. The simulator has no liquidity constraint
**Problem** `max_volume_participation = 2%` is enforced in `autotrade.py`
only. **Evidence** grep: zero references in `portfolio.py`. **Why** The
backtest can take positions the bot would refuse, in exactly the illiquid
moments that matter. **Impact** Unknown until measured; likely small for
$50M-ADV names at $100k, material if the account grows. **Risk** Low.
**Validate** Re-run the candidate with the cap on; compare. **Before new
strategies? YES** — it is a correctness gap between sim and live.

### 5. One source of edge
**Problem** Mean reversion is the entire equity P&L. **Evidence** §18.
**Why** No redundancy; a regime that kills it kills everything.
**Impact** Large but slow. **Risk** High — every new-edge search so far has
failed. **Validate** The full firewall. **Before new strategies?** This *is*
the new-strategy question — but not before #2 and #3.

### 6. `leakage.py` has never been run on the live model
**Problem** A good auditor exists and is only invoked by its own test.
**Evidence** grep: `audit_for_leakage` appears in `tests/test_leakage.py`
and nowhere else. **Why** The one model in the repo was disabled for
suspected overfitting; nobody ran the tool built to diagnose exactly that.
**Impact** Diagnostic clarity, cheap. **Risk** None.
**Validate** Run it; it should report near 0.5588, not 0.9. **YES — it is an
afternoon.**

### 7. Dividends are absent from the simulator
**Problem** `portfolio.py` has zero dividend handling; prices are
split-adjusted only. **Evidence** grep. **Why** Understates the bot by the
yield of held names, and makes the SPY total-return comparison apples to
oranges. **Impact** Estimated +0.5–0.8 CAGR points. **Risk** Low.
**Validate** Re-run with `adjustment="all"` and compare. **Not blocking.**

### 8. Stop losses give back 8.36% and four fixes have failed
**Problem** 542 trades, −$829,266, `captured` −3.07. **Evidence** §10.
**Why** It is the single largest loss category. **Impact** Unknown — every
attempted fix cost more than it saved. **Risk** High. **Validate** Firewall.
**Before new strategies? NO** — it is well-explored; treat as priced.

### 9. Parameter stability is asserted, not measured
**Problem** "Clean peak at 2.5 ATR" comes from five points, no neighbourhood
analysis. **Evidence** EXP-0022 and siblings report point results.
**Why** A peak that is a spike is an overfit; a peak on a plateau is robust.
**Impact** Confidence, not return. **Risk** None. **Validate** Surface plots
across adjacent parameter pairs. **Not blocking, but cheap.**

### 10. No streaming input anywhere
**Problem** Everything is REST polling; equities at 15-min granularity.
**Evidence** §14. **Why** Caps exit responsiveness and makes "always
watching" impossible. **Impact** Enables #2 fully. **Risk** High — a
persistent event loop is a rewrite of `run_once`. **Validate** Shadow-run the
streaming loop against the scheduled one for weeks. **Before new strategies?
NO** — do #2 with the existing 15-min loop first.

---

## 21. SUMMARY

**CURRENT SYSTEM** One long-only daily mean-reversion rule over 230 US
equities, plus a 5% BTC trend allocation and SGOV cash parking. 15,361 lines,
767 tests. Interval-driven: equities every 15 min with entries confined to
the last 20 minutes; crypto every 30s, 24/7. Alpaca paper only. No shorting,
no leverage, no models in the money path.

**CURRENT PERFORMANCE** 30 years, parked, honest fills: **CAGR 5.75%, vol
6.7%, Sharpe 0.53, Sortino 0.75, maxDD −11.2%, Calmar 0.51, 1,522 trades,
54% win, PF 1.39, ruin 2.2%, 80% of days underwater.** Trust the *range*
2.24%–5.75%, not the point.

**SPY COMPARISON** Loses on return (−2.80 pts vs price, ≈−4.5 vs total),
wins on drawdown (−11.2% vs −56.5%), wins on Sharpe/Sortino versus price
return and versus vol-matched SPY, roughly ties versus SPY total return.

**DATA RISKS** Survivorship in every equity set (up to 3–4 pts/yr). No
dividends. No revision tracking. Point-in-time exists only for news, only
since 2026-09-14.

**LEAKAGE RISKS** The boundary is clean and provable (`include_today=False`,
two audited exceptions). The real leakage is **selection**: 186
configurations on the same data used to report results.

**OVERFITTING RISKS** High for magnitude, low-moderate for existence. DSR
0.993 at the observed spread but 0.53 at a plausible wider one. No PBO, no
purged CV, no embargo, no stability surfaces.

**EXECUTION RISKS** No partial fills, no latency, no market impact, no
liquidity cap in the simulator, flat slippage that is optimistic exactly when
the strategy trades.

**ENTRY WEAKNESSES** Single-gate, no confirmation, 30% of trades taken near
market highs earn a median 0.001R — but removing them was measured as worse.

**EXIT WEAKNESSES** The stop is the leak (−$829k) and is unfixable by
timing. The improvable ceiling is +0.73 to +1.47 CAGR on the other 968
trades, and live currently sells 0.65% worse than the backtest assumes.

**POSITION-SIZING WEAKNESSES** No drawdown response, no regime response
(both tested, both worse), no expected-value term. Bounded and safe; not
adaptive.

**REGIME WEAKNESSES** A regime classifier exists and **the live rule ignores
it entirely.** Regime adaptation has been rejected twice. Bear-market
survival is emergent from the 200-day filter, not designed.

**CONTINUOUS-TRADING ARCHITECTURE** Crypto is effectively continuous (30s).
Equities are not and cannot be without replacing REST polling with a
websocket stream, an event loop, in-memory state, a decision throttle and
process supervision. Worth doing for *exits*, not for more trading.

**NEWS/INFORMATION GAPS** Recording works and is genuinely point-in-time,
but the corpus is 2 days old, source reliability is unscored, and nothing is
wired to a decision — correctly, since the one tested thesis was the wrong
half of the trade.

**CRYPTO GAPS** Only BTC trades. No edge found in any crypto trading family;
the 5% allocation is the only validated piece and is graded weak. Meme coins
are tradeable, measured, and unallocated because spreads (29–73 bps) eat the
edge and the newest have under a year of data.

**WHAT I WOULD NOT CHANGE** The 200-day trend filter (removing it doubled
drawdown). The 2.5-ATR stop (every alternative lost). The 20-day hold (the
sweep is monotone). The 20% cap and one-per-bucket. Cash parking. Entry in
the closing window. The disabled model veto. The research firewall itself.

**WHAT MUST BE FIXED BEFORE PROCEEDING**
1. Close the live-vs-backtest exit gap (0.65%/exit).
2. Accumulate 60 forward sessions — nothing historical can accept a change.
3. Put the liquidity cap in the simulator so sim and live agree.
4. Run `leakage.py` against the live model.

Only then is adding a second strategy a sound use of effort.
