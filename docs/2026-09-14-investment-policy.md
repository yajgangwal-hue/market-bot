# Investment policy: this account against the S&P 500

*2026-09-14. Paper account PA30S46B79V8. This is a research project on a paper
account, written by a system that is not a licensed adviser; nothing here is a
recommendation for real money.*

## 1. The objective, and the verdict the evidence gives it

**Objective as stated:** outperform the S&P 500 over the long term on a
risk-adjusted basis; seek a higher total return than the index over a
multi-year period at a reasonable level of risk; measure against the index's
total return including dividends; claim nothing not measured over the same
period.

**Verdict, on everything measured to date:**

| | total return | drawdown | Sharpe (excess over bills) |
|---|---|---|---|
| thirty years 1996–2026 | **loses** by ~4.5 pts/yr | **wins** — −11.2% vs −56.5% | ahead, 0.53 vs ~0.42 |
| decade 2016–2026 | **loses** by ~5–6 pts/yr | **wins** — −11.2% vs −33.8% | **behind**, 0.67 vs 0.77 |

The account **does not achieve a higher total return than the S&P 500** in
any measured configuration — thirty-six experiments, one hundred and
thirty-four configurations, including every blend that holds part of its
idle cash in SPY. What it achieves is a **fraction of the index's drawdown
for roughly half its return**: Calmar 0.51 against 0.15 over thirty years,
0.75 against 0.45 over the decade; beta 0.205; on the index's ten worst days
since 1996 it lost between 0.0% and 1.2%.

On the standard Sharpe definition it is a tie, and an honest one: the
project's own convention measured Sharpe over a zero risk-free rate, which
flattered a book that is 74% cash earning the bill rate. Measured over the
actual three-month bill (2.30% mean), the thirty-year advantage narrows to
0.53 against ~0.42 and the decade reverses. **"Outperforms on a risk-adjusted
basis" is true if risk means drawdown, and not established if it means
volatility.** That distinction is the most important sentence in this
document, and the previous week's reports did not make it.

## 2. What is confirmed, what is estimated, what cannot be done

**Confirmed** (measured, reproducible from the repository):
- SPY total return 2016-01-04 → 2026-09-14: 15.00%/yr (Alpaca bars,
  `adjustment=all`); price return 13.42%; dividends +1.58 pts/yr.
- SPY price return 1996–2026: 8.55%/yr, maxDD −56.5%, 22 of 30 years
  positive, worst year 2008 −38.3%, worst within-year drawdown −48.4%.
- The production candidate, every live constraint, thirty years: 5.17%
  alone / 5.75% with idle cash in bills; maxDD −12.9% / −11.2%; 23 / 25 of
  30 years positive; worst year 2022 −10.5% / −8.0%; ruin at a 25% drawdown
  18% / 2.2%. Per-year table in `docs/2026-09-13-research-firewall.md`.
- Correlation to SPY 0.483, beta 0.205, vol 8.2% vs 19.2%, on 7,719
  aligned days.
- Mean three-month bill 1996–2026: 2.30%; 2016–2026: 2.25%
  (`data/tbill.csv`).

**Estimated** (labelled wherever it appears):
- SPY thirty-year *total* return, ~10.3%/yr. No dividend-adjusted series
  before 2016 is reachable from this machine — Alpaca's history starts 2016
  and the Yahoo path fails on a certificate error. The decade's measured
  +1.58 pts and SPY's higher yield in 1996–2015 bound it at +1.6 to +2.0 pts
  over the confirmed price figure.

**Cannot be done to the standard the objective sets, and is not attempted:**
- **Company fundamentals, valuation, earnings, growth.** The repository has
  no fundamentals data source — confirmed by search; the only match for
  "eps" is a substring. A bottom-up stock selection cannot be evaluated here
  without fabricating inputs, so it is not proposed.
- **A current macro or sector read.** This system's knowledge ends June
  2026 and it has no verified economic-data feed. In its place the strategy
  is *regime-tested* rather than regime-forecast: its thirty-year record
  spans 2000–02 (three down years for SPY: −10.7%, −12.9%, −22.8%; the
  candidate 3.8%, 4.4%, −0.3% parked), 2008 (SPY −38.3%; candidate −5.1%),
  2020 (SPY's worst single day −10.9%; candidate −0.15%) and 2022 (SPY
  −19.5%; candidate −8.0%). That is the evidence a discretionary macro view
  would have to beat, and it is more than a point-in-time opinion is.

## 3. The strategy as it runs, in the form the objective requires

### A. The engine: mean reversion in liquid US equities

- **Thesis.** Large, liquid names that have sold off sharply (RSI(14) ≤ 35)
  while still in a long-term uptrend (above their 200-day average) tend to
  recover over the following weeks. 73.6% of the strategy's return arrives
  overnight, close to open, which is why entries fill in the last twenty
  minutes of the session rather than the next morning.
- **Evidence.** Positive in both halves of both windows; positive on the
  46-ETF survivorship-free control (2.24% over thirty years — the honest
  floor of the return range, the 230-name figure being the survivor
  ceiling). Entry timing worth +1.3 pts on the decade, +1.1 over thirty
  years, cost-matched at four friction levels.
- **Sizing.** Risk 0.5% of equity per trade against a 2.5-ATR stop; no
  position above 20% of equity; at most three entries a session; whole
  shares. Idle cash held back: a $2,000 floor plus 5% of equity reserved
  for the crypto sleeve.
- **Exit.** RSI(14) ≥ 60 (the reversion has happened), or the 2.5-ATR stop
  (resting at the broker as a GTC order, filled at the open if gapped
  through), or twenty trading days (the edge decays; holding longer was
  measured worse at every longer cap).
- **Risks.** Survivorship in the universe (measured: it inflates the return
  by up to 3–4 pts/yr — hence the range). Regime: a sustained bear without
  sharp recoveries (2000–02 produced near-zero years, not losses). Execution:
  the stop leaks — stopped trades give back 8.4% of entry on average, the
  largest measured cost, and no tested exit variant recovered it without
  losing more elsewhere.
- **Invalidation.** Any of: a calendar year below −10% (the thirty-year
  worst parked is −8.0%); a within-year drawdown past −15% (worst observed
  −12.9%); a forward record of sixty-plus sessions whose per-trade edge is
  measurably negative (`record.py` computes this with a confidence
  interval); or the survivorship-free control turning negative on a fresh
  window. Each halts new entries pending review; none is triggered.

### B. Idle cash in Treasury bills (SGOV)

- **Thesis.** The book is idle 74% of the time by design. Cash that earns
  the bill rate is the single largest measured improvement in the project
  and cannot lose money.
- **Evidence.** +1.49 pts/yr over thirty years at the rate that actually
  prevailed each day; drawdown improved; ruin at 25% fell from 18% to 2.2%
  because interest refills drawdowns. Alternatives measured and rejected:
  SPY for any fraction of idle cash (see §4).
- **Sizing and mechanics.** Everything above the floor and the reserve;
  unparked automatically when an entry needs it. First fired live today,
  $25,692.55, once capital was freed.
- **Risk / invalidation.** Rate risk is negligible at 0–3 month duration.
  Invalidated only if the instrument fails to track bills, which it has not.

### C. Bitcoin allocation sleeve, 5% of equity

- **Thesis.** Not a trading edge — every crypto trading family was measured
  and lost. An *allocation*: hold BTC while it is above its own 100-day
  average, nothing otherwise, at 5%, because its daily-return correlation
  with the equity book is +0.035 and a 42%-volatility asset added at that
  weight lowered the combined drawdown (−14.1% → −13.5%) while adding
  return (7.60% → 9.13% on the decade).
- **Evidence.** The improvement is one number on one window and is the
  weakest evidence in this book — recorded as such in the registry. Larger
  weights, ETH, a split, other trend windows and a trailing stop were all
  measured and rejected (second-half deterioration, or noise).
- **Sizing.** 5%, rebalanced within a 20% band of target, buys capped at
  available cash, sells never capped. Reached target for the first time
  today, $5,094.
- **Invalidation.** The correlation rising above ~0.3 for a sustained
  period, or the sleeve's contribution turning negative over a full BTC
  cycle. Neither can be judged on the forward record yet.

### D. What is deliberately not in the book, with the number that kept it out

Shorting volatile opens (−52% to −64%/yr as an account); an overnight-gap
book (23.6%/yr on survivors, −1.5% on the ETF control — survivorship, not
edge); meme-coin allocations (all lose at measured spreads); the "rescue"
exit and every early-exit variant (win rate up, CAGR down: 7.83% → 6.41%);
a model veto on entries (loses money monotonically out of sample, AUC 0.51
walk-forward); candidate ranking (noise); holding longer than twenty days;
any stop other than 2.5 ATR; any position cap other than 20%. Every one is
in `docs/experiments.jsonl` with its result, and none is coming back
without a forward-record case.

## 4. The decision only the owner can make

The objective contains two goals the evidence says cannot both be met with
what exists: a higher total return than SPY, and a reasonable level of risk
— where "reasonable" has meant, in every decision taken this week, *lower
drawdown than the index*. The trade-off has been measured. Idle cash held in
SPY instead of bills, thirty years:

| idle cash in | CAGR | worst drawdown | CAGR per point of drawdown |
|---|---|---|---|
| all bills — live | 6.17% | −11.7% | 0.53 |
| 25% SPY | 6.50% | −16.3% | 0.40 |
| 50% SPY | 6.80% | −25.0% | 0.27 |
| 75% SPY | 7.08% | −32.6% | 0.22 |
| all SPY | 7.34% | −39.3% | 0.19 |
| *SPY alone, for comparison* | *8.55% price / ~10.3% TR* | *−56.5%* | *0.15* |

(SPY leg at price return; each rung would be higher by an estimated +0.4 to
+1.6 pts on a total-return basis. The ordering does not change.)

Every step up the ladder buys return at a *worse* rate than the step
before, and the top rung still trails the index. There are only three ways
to a higher total return than SPY, and none is available:

1. **Hold SPY as the core and run this book as a satellite.** Measured: the
   blend returns *less* than SPY alone, because the book's invested periods
   earn less than the index does in those same periods. This book is a
   drawdown reducer, not a return enhancer, and should be described as one.
2. **Leverage.** The book's 5.2% at 8.2% volatility levered to the index's
   volatility is ~12% gross, less ~6% in borrowing at bill-plus rates on the
   levered portion: roughly 6%, below SPY, at 2.3× the operational risk.
3. **A new source of return.** Thirty-six experiments did not find one, and
   the historical windows are now contaminated for this candidate's family.
   A genuinely new idea goes through the registry, the per-year
   distribution, the deflated Sharpe, and the forward record — in that
   order, hypothesis first — and is the only route that could change §1.

**Recommendation:** keep the book as it is, and state its objective
correctly: *the index's downside exposure cut by three-quarters, at roughly
half its return, with a positive expectancy in every regime since 1996.*
If the owner's objective is instead the index's return, the honest answer is
to hold the index — every configuration here is a worse way to get it.

## 5. Measurement, review, and what would change this document

- **The benchmark is tracked automatically.** `scripts/benchmark.py` runs at
  every session close and writes `data/BENCHMARK.txt`: the account, from the
  equity readings the bot recorded at the time, against SPY with dividends
  reinvested over the identical days. It is flagged **NOT A FINDING** until
  sixty sessions — about a quarter — and nothing may cite it as a result
  before then. Today it has one complete session in common.
- **Every change is an experiment.** Hypothesis, configuration and data
  period are registered before the result is known; the result is judged as
  a distribution across years, not a mean; the Sharpe pays for the count of
  configurations tried (`research.deflated_sharpe`). The historical windows
  reject ideas; only the forward record accepts them.
- **Review triggers** (§3 invalidation conditions) halt new entries; the
  weekly `record` report computes the per-trade edge with its interval; a
  forward record of sixty sessions is the first point at which anything in
  §1 may be revised.
- **Costs.** Modelled at measured levels: equity friction cost-matched at
  3–12 bps per side; crypto at each pair's measured round-trip spread;
  parking at 2 bps per move. Taxes are not modelled and would fall hardest on
  the twenty-day holding period; that is a real-money consideration outside
  a paper account's scope and is noted, not ignored.

## 6. The account today

Equity $99,992. Six equity positions were held into this morning at 99.3% of
equity — capital committed before the reserve existed. The owner closed TJX
and VNQ; the sleeve funded itself to target and the cash parked within
minutes. RTX and LIN are being closed into intraday strength by
`scripts/exit_at_peak.py` on the owner's instruction, with a 15:48 ET
deadline; that is a directed action, not a rule, and the reason it is not a
rule is in §3D. Forward record: two sessions, one comparable. Nothing about
performance is claimed.

## 7. What is not claimed

That the account beats the index on return. That its Sharpe advantage is
established. That it has an out-of-sample record. That the thirty-year total
return of SPY is known to better than half a point. That any position in it
was chosen on fundamentals. Each of these is a thing this document could
have said and did not, and the reader should hold it to that.
