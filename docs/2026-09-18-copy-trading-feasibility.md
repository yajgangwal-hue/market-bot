# Copy-trading feasibility report

*2026-09-18. **FORENSIC_NON_PROMOTIONAL.** No experiment registered. No
production file modified. No promotion candidate. Emulator/research
only — nothing here touches a live account.*

## Verdict: **H-COPY is not justified.** Two independent reasons

1. **No external trader-signal source is accessible.** The subject of
   the request — copying other traders — has no data.
2. **The only internal source has zero same-day overlap with the main
   strategy**, which makes three of the five copy mechanisms
   structurally impossible rather than merely unproven. Of the two that
   remain, one is statistically indistinguishable from zero and the
   other moves the wrong way on excess return versus SPY.

---

## 1. Available signal sources

Authorized external access is Alpaca alone (`APCA_API_KEY_ID` /
`APCA_API_SECRET_KEY`, paper). Every endpoint this repository uses:

| endpoint | provides | trader signals? |
|---|---|---|
| `/v1beta1/news` | headlines | no |
| `/v2/stocks/bars` | daily/intraday OHLCV | no |
| `/v1beta3/crypto/us/bars`, `/latest/quotes` | crypto OHLCV, quotes | no |

Alpaca sells market data and execution. It has no leaderboard, no
signal feed and no copy-trading product. **There is nothing to query.**

| candidate source | provides | usable? |
|---|---|---|
| external trader feed | copied positions / provider signals | **ABSENT — no data of any kind** |
| `social.py` (X, Bluesky) | live posts, REVIEW_REQUIRED alerts | **No** — live fetch, zero archive |
| `data/news/` | live headline feed | **No** — 5 days (2026-09-15→19) |
| news archive (phase5) | 11,852 headlines, no bodies | **Closed** — classified A on 2026-09-18 |
| **trend rule** (`entry_rule="trend"`) | complete entry+exit system | **YES — the only one** |
| `smc.py` | structure detectors, confirmation-lagged | features, not a strategy |
| `cross_sectional.py` | peer-rank features | features, not a strategy |
| `regime_shorts.py` | short-only in confirmed bear tape | No — long-only book |
| `crypto_sleeve.py` | BTC allocation | No — different asset |
| `peak_exit.py` | intraday exit timing | exit only, not a signal |
| `live_model` / `trade_learning` | learned rank + veto | disabled, and not independent |

The two social paths are dead for history: `api.x.com/2/tweets/search/recent`
is a **7-day** window and no bearer token is set;
`public.api.bsky.app` `getAuthorFeed` is a live read that persists
nothing and returns posts, not trades. **No module in the repository
has ever written a signal stream to disk.**

Not attempted, deliberately: Collective2, DarwinEX, ZuluTrade, eToro.
These are the platforms that genuinely hold point-in-time signal
histories, and all four sit behind paid APIs and terms of service —
out of bounds under the instruction not to bypass paywalls or access
controls, and no credentials for them exist here.

## 2. Historical coverage

| source | span | usable history |
|---|---|---|
| external | — | **none** |
| `data/news/` | 2026-09-15 → 2026-09-19 | 5 days |
| trend rule | 2016-01-04 → 2026-09-04 | full decade, 2,684 sessions |

## 3. Timestamp quality

For the internal source the question is different in kind: the trend
rule is *deterministic code over daily bars*, so its "signal timestamp"
is the session close that produced it, exactly as for the main
strategy. There is no vendor clock, no publication lag and no revision
risk — and equally, no independent availability timestamp to validate,
because nothing is being published by anyone.

For the external sources the question is moot: there are no timestamps
because there are no signals.

## 4. Number of copyable traders/strategies

**One.** The trend rule.

Against the §3 definition — a copyable trader must supply signal
timestamp, instrument, direction, entry, exit, position state and
availability timestamp — the trend rule supplies all seven, because it
is re-runnable code rather than a record of someone's behaviour. No
external candidate supplies any of them.

## 5. Number of usable signals

| | |
|---|---|
| trend-rule entries over the decade | **920** |
| main-strategy entries | 698 |
| trend distinct symbols | 192 (of 230) |
| trend buckets touched | 29 |

## 6. Survivorship limitations

The usual survivorship concern for copy trading — evaluating only
traders who still exist — **does not arise**, because there is only one
source and it is code that cannot quit or blow up.

The limitation that *does* apply is inherited: the 230-name universe is
today's constituents, so both rules are evaluated on names that
survived. That biases both equally and does not affect their relative
comparison, which is what this report turns on.

## 7. Point-in-time feasibility

**Feasible and clean for the internal source.** The trend rule runs
through the identical portfolio engine on the identical bars with the
identical cost model, so a signal at session *t* uses only data through
*t* by construction — the same guarantee the main strategy has.

**Baseline equivalence was established before anything else ran:**
+58.5889000000% over 698 trades, matching the registered baseline
exactly.

Copy delay (§11) was not modelled, and did not need to be: with zero
same-day overlap there is no signal to relay.

### A defect found in the copy source

`strategy.generate_candidate` detects `stop <= 0`, appends the blocker
`"Calculated stop is non-positive"`, and then **continues** into
`costs.round_trip_cost_per_share(entry, stop)`, which raises
`ValueError("price must be positive")`. The blocker is recorded and
never reached, so `run_portfolio(entry_rule="trend")` cannot complete
on this universe at all. `mean_reversion.evaluate` guards the identical
case correctly.

It fired **once in ~617,000 evaluations** — a rare edge case, but it
means the trend rule had evidently never been exercised at this scale.
`src/` was **not** modified; the research script shims the raise into
the `REJECT` the function was already assembling, and both premises
were validated (the cost model does raise on a negative price;
`_rejected(...)` yields `Action.REJECT`, which the engine skips). The
production fix is queued as a separate task.

## 8. Independence from the existing strategy

| dimension | MAIN | TREND |
|---|---|---|
| underlying data | daily OHLCV, 230 names | **same bars** |
| direction | buy weakness, RSI ≤ 35 | buy strength, breakout/ADX |
| trend filter | close > 200-day SMA | 20/50 SMA + ADX ≥ 18 + R² ≥ 0.4 |
| entry trigger | RSI(14) ≤ 35 | composite score ≥ 70 |
| exit | RSI ≥ 60 / 2.5 ATR / 20 bars | trailing 2.5 ATR from 0.5R / 20 bars |
| stop | 2.5 × ATR(14) | 2.0 × ATR(14) |
| liquidity floor | $50M ADV, $20 | **same** |
| universe / benchmark / holding cap | 230 / SPY / 20 bars | **same** |

**Daily return correlation: +0.2253** (n = 2,683). Genuinely low — these
are not the same trade.

**But the decisive number is the overlap:**

| | |
|---|---|
| main entries | 698 |
| trend entries | 920 |
| **same symbol, same day** | **0 — 0.00%** |
| distinct symbols shared | 157 |
| buckets shared | 28 of 29 |
| sessions both hold something | 1,937 (72.2%) |
| **mean same NAME held by both** | **0.0000** |
| sessions sharing a bucket | 1,049 (39.1%) |

**Not once in a decade do the two rules select the same name on the
same day.** This is mechanical, not statistical: RSI ≤ 35 oversold and
ADX ≥ 18 breakout structure are mutually exclusive states. They are
genuinely independent *in selection* — and that independence is
precisely what destroys most of the copy mechanisms.

Duplicated-risk check (§5 of the brief): the two never hold the same
name simultaneously, so copy trading here would **not** multiply
single-name exposure. It would, however, share a correlation bucket on
39.1% of sessions.

## 9. Execution feasibility

Not reached in any meaningful sense. With zero same-day overlap there
is no signal to relay, so slippage, latency, staleness, partial fills
and duplicate-signal handling are all moot for Modes A/C/D. For Mode E
the blend below is daily-rebalanced and **frictionless** — an
idealisation that *flatters* the blend, since real rebalancing costs
money. Stated rather than corrected.

## 10. Expected research value

### Standalone

| | MAIN (prod) | TREND (copy) | SPY |
|---|---|---|---|
| total return | **+58.59%** | +17.59% | +283.14% |
| CAGR | +4.43% | +1.53% | — |
| annualised volatility | 9.34% | 5.64% | — |
| Sharpe | **0.5107** | 0.2978 | — |
| Sortino | 0.7221 | 0.4193 | — |
| max drawdown | −12.98% | −8.93% | — |
| trades | 698 | 920 | — |
| win rate | **51.15%** | 39.02% | — |
| profit factor | 1.234 | 1.139 | — |
| turnover | 21.70 | 13.89 | — |
| costs | $13,868 | $8,874 | — |
| exposure | 44.28% | 31.36% | — |
| **excess vs SPY** | **−224.55 pts** | **−265.56 pts** | 0 |

The copy source is worse than the main strategy on every economic
measure that matters, and further behind SPY.

Year by year, the trend rule is negative in 2016 and 2018, and its one
strong year (2024, +8.88%) is the main strategy's weakest (+1.23%).

### The mechanisms, one at a time

| mode | status |
|---|---|
| **A — Confirmation** | **structurally impossible.** BOTH = 0; there is never agreement to confirm |
| **B — Independent candidates** | **not significant.** See below |
| **C — Ranking** | **structurally impossible.** Cannot rank main's candidates by a signal that never fires on them |
| **D — Veto** | **structurally impossible.** No overlapping name exists to veto |
| **E — Diversification** | measurable, and fails the objective. See below |

**Mode B.** Forward excess vs SPY of names each rule selects:

| state | n | exc 5s | exc 10s | exc 20s | win@10 |
|---|---|---|---|---|---|
| BOTH | **0** | — | — | — | — |
| MAIN_ONLY | 5,072 | +0.143% | +0.095% | +0.186% | 50.1% |
| COPY_ONLY | 918 | +0.092% | +0.081% | +0.628% | 47.5% |

Day-collapsed — one observation per session, which is the honest unit
given that names move together within a day:

| state | days | mean @10s | SE | **t** |
|---|---|---|---|---|
| MAIN_ONLY | 1,275 | +0.0590% | 0.0977% | **0.60** |
| COPY_ONLY | 707 | +0.1379% | 0.2147% | **0.64** |

Neither is distinguishable from zero. And the price-only SPY benchmark
contributes a **+0.052% mechanical artefact** at 10 sessions from
excluded dividends — which is essentially all of MAIN_ONLY's +0.059%.
COPY_ONLY sits nominally higher but at t = 0.64 that is noise.

**Mode E.** Daily-rebalanced blends, measured rather than approximated:

| main/trend | total | CAGR | vol | Sharpe | maxDD | vs SPY |
|---|---|---|---|---|---|---|
| **100/0** | **58.59%** | 4.43% | 9.34% | 0.5107 | −12.98% | **−224.55** |
| 75/25 | 48.57% | 3.79% | 7.45% | 0.5365 | −10.74% | −234.57 |
| 50/50 | 38.30% | 3.09% | 5.97% | **0.5397** | −8.58% | −244.84 |
| 25/75 | 27.93% | 2.34% | 5.27% | 0.4650 | −6.96% | −255.21 |
| 0/100 | 17.59% | 1.53% | 5.64% | 0.2978 | −8.93% | −265.56 |

The 50/50 blend raises Sharpe by **+0.0291** and cuts drawdown by 4.40
points — both real, and exactly what a +0.2253 correlation predicts.
It does so by giving up **20.29 points of total return** and widening
the gap to SPY by the same 20.29 points.

Every blend sits comfortably **within** the 110% ceiling (14.2806%).
Every blend moves the **wrong way** on excess return versus SPY.

That is diversification into a weaker strategy — dilution, not alpha.
It is the H-0006 pattern in a new costume: a ratio improvement
purchased with return, against a governing objective that is stated in
excess return versus SPY.

## 11. Is a formal H-COPY experiment justified?

**No.**

1. The external premise has no data, and the honest response is to say
   so rather than substitute something else and call it copy trading.
2. Three of five mechanisms are impossible by construction, which no
   amount of data would fix — it follows from the rules being opposite.
3. The one informational mechanism (B) sits at t = 0.64 day-collapsed,
   with most of the nominal effect explained by a benchmark artefact.
4. The one portfolio mechanism (E) is measurable and real, and it makes
   the primary objective worse.
5. Registering would spend a hypothesis slot and a chain link on a
   question already answered mechanically.

**What would change this:** a signal source that is (a) genuinely
external, (b) carries a public-availability timestamp distinct from its
generation timestamp, (c) spans multiple years with a
survivorship-complete roster including traders who stopped, and (d)
encodes information not derivable from daily OHLCV. That is a
data-acquisition problem with a licensing cost, not a modelling one.
The only free, legal, timestamp-clean approximations are SEC filings —
13F (quarterly, 45-day lag, structurally too slow against a ~14-session
holding period) and Form 4 insider transactions (~2-day filing lag, and
the filing date is a genuine availability timestamp). Form 4 is a
different hypothesis, not copy trading, and would need its own
acquisition work and registration.

## Governance

| check | result |
|---|---|
| frozen fingerprint | `da22011e…c237b` — **unchanged** |
| production source | **unchanged**; `src/` working tree clean |
| `rsi_entry` / bucket cap / max positions | 35.0 / 1 / 12 — unchanged |
| learned ranker / veto | `False` / `False` |
| exit haircut | **0.652% unchanged** |
| 110% drawdown ceiling | **unchanged**, applied to every blend |
| clean OOS | **untouched** |
| registrations | 8, chain intact — **none added** |
| promotion candidates | **none** |
| research ledger | 30 experiments, 91 configurations — unchanged |
| thirty-year reads | **13** |
| baseline equivalence | **PASS**, +58.5889000000% / 698 trades |
| artefacts | every JSON carries `FORENSIC_NON_PROMOTIONAL: true` |

## Process note

The first attempt at this analysis was lost: it ran ~20 minutes of
simulation and persisted only at the end, and the invocation piped
through `sed`, which exits 0 even when Python dies — so a killed
process reported success. The work is now split: `copy_build_cache.py`
runs both strategies once and writes the cache immediately;
`copy_analyse.py` answers every question from that cache in seconds and
can be re-run freely.

## Next

Unchanged by this result: **slot competition at RSI ≤ 40**, descriptive
and read-only. Of the 13,215 additional name-days in the (35,40] hump
found by the breadth pass, how many would win a slot under completely
unchanged capacity rules? It is the only surviving lead with measurable
value behind it, needs no new data, and converts a name-level finding
into a portfolio-level one.

## Artefacts

- `scripts/copy_build_cache.py`, `scripts/copy_analyse.py`,
  `scripts/forensics_copy_sources.py`
- `docs/phase5/copy-feasibility.json`
- `docs/phase5/copy-cache.json` (683 KB, regenerable)
