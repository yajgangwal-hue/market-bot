# Where to set take-profits and stop-losses — research and preparation

*2026-09-27. Owner's request: "Make the bot know enough about day trading and
educated enough to know where to set its take profits and stop losses —
don't implement it yet, just prepare it and research it."*

**Nothing in production changed.** No backtest was run, no research dataset
was read and no hypothesis was registered. Prepared, not wired:

- `src/event_aware_trader/exit_placement.py` — nothing in the trading loop imports it.
- `scripts/exit_check.py`.
- `tests/test_exit_placement.py`.
- DRAFT H-0026 (§7) — not sealed.

The frozen fingerprint is unchanged.

---

## The answer

**For the strategy the bot runs, its levels are already where the evidence
puts them:**

- a stop at 2.5 × ATR(14) below entry, resting at the broker (5.09% for a
  UNP entry today);
- no fixed profit target;
- a sale when the bounce is done (RSI(14) ≥ 60) or after 20 sessions.

This project has measured about 77 alternative exit configurations
([Research Gaps](../knowledge/05-open-questions/Research%20Gaps.md)): tighter
and wider stops, fixed targets, target-and-stop pairs, break-even locks,
trailing stops, partial sales and time caps. None beat this rule robustly
(§4).

**"Educated placement" is a set of rules, not a magic number.** The rules the
arithmetic, the literature and this project's own measurements agree on:

1. **Levels cannot create an edge.** With no edge, every target/stop pair loses
   exactly the trading cost on average (§1).
2. **Tight levels starve a real edge.** The expected gain equals the edge per
   day × the time held, and a tight pair holds for minutes (§1).
3. **Scale every level to the stock's own volatility**, and keep the stop well
   outside ordinary noise for the time you intend to hold (§3).
4. **For a bounce-back (mean-reversion) trade, a stop is insurance, not a
   profit tool.** Below the fair level the expected remaining gain is
   positive, so a stop there never adds expected profit (§2.2). Stops add
   value when losses tend to continue (momentum), which is not this strategy
   (§2.1).
5. **Take profit at or above the fair level, not below it.** A target chosen
   for a high win rate lowers total profit (§2.2, EXP-0050).
6. **Never pick levels by searching a backtest.** That is the classic
   overfitting trap (§2.5). Derive them from the trade's measured behaviour,
   then test that one rule once (§7).

**For day trading specifically:** levels only matter once a strategy has an
edge, and no day-trading strategy tested here has one ([the 2026-09-19
day-trading reports](2026-09-19-day-trading-research.md); EXP-0019). The
bot now "knows" how to judge any intraday pair against a stock's
volatility, costs and noise (`scripts/exit_check.py`, §6). It flags
+0.5% / −0.2% on those grounds before a single trade.

---

## 1. What a take-profit and a stop can and cannot do

Treat a price over short horizons as a random walk with drift μ per day
(the edge) and volatility σ per day. With a target +T and a stop −S, three
standard results for Brownian motion hold (verified numerically on
2026-09-27, to within simulation error):

- **Who hits first.** With no edge, the target comes first with probability
  **S / (T + S)**, whatever the volatility (optional stopping). With an edge
  it is (e^{2μS/σ²} − 1) / (e^{2μS/σ²} − e^{−2μT/σ²}).
- **How long it takes.** With no edge, the expected time to either level is
  **T × S / σ²**.
- **What it is worth.** The expected gain is **μ × expected time held**
  (Wald's identity). A pair decides how often you win and how long you hold.
  It never decides whether you have an edge.

A round-trip cost c is paid on every trade. A win nets T − c, a loss costs
S + c, and the target must come first at least **(S + c) / (T + S)** of the
time.

Worked for UNP. Daily volatility 1.39% over the last 60 sessions; the
project's 0.12% round-trip cost; no edge assumed. "Chance" is how often the
target comes first with no edge. "Needed to break even" is how often it must
come first to cover the cost:

| target / stop | chance | needed to break even | expected time to exit | stop ÷ typical 15-min move | expected result |
|---|---:|---:|---:|---:|---:|
| +0.5% / −0.2% | 28.6% | 45.7% | 20 minutes | 0.7× | −0.12% |
| +1% / −1% | 50.0% | 56.0% | 202 minutes | 3.7× | −0.12% |
| +2% / −2% | 50.0% | 53.0% | 2.1 days | 7.3× | −0.12% |
| +5% / −5% | 50.0% | 51.2% | 12.9 days | 18.3× | −0.12% |

**Every row loses exactly the cost.** What changes is how hard the rest of
the strategy must work to overcome it. Give the same stock a genuine edge of
+0.05% a day:

- the +0.5% / −0.2% pair collects **+0.0026%** of it per trade (net −0.117%);
- the +5% / −5% pair collects **+0.64%** (net +0.52%).

Same edge, 250 times the value: the wide pair holds long enough for the edge
to work. That is the arithmetic behind EXP-0019 on the decade: 1-day holds
−39.3%, 3-day holds +5.2%, 20-day holds +123.1%.

The approximation is continuous watching with volatility spread evenly
through the day. Real volatility is U-shaped, highest at the open and close
(Wood, McInish & Ord 1985), and overnight gaps jump straight past both
levels. Both make tight pairs worse than the table shows.

## 2. What the research literature says

### 2.1 Stop-losses help only when losses tend to continue

- **Kaminski & Lo (2014).** *"under the Random Walk Hypothesis, simple 0/1
  stop-loss rules always decrease a strategy's expected return"*.
  - With momentum they can add value.
  - Test: a buy-and-hold US equity portfolio, monthly 1950–2004, switching
    into US long-term government bonds after losses. Certain rules added 50
    to 100 basis points a month during stop-out periods, which they explain
    with a regime-switching model of periodic flights to quality.
- **Lo & Remorov (2017).** On a large sample of individual US stocks, tight
  stops underperform buy-and-hold because of trading costs. They can
  outperform only for stocks with sufficiently high serial correlation.
- **Han, Zhou & Zhu (working paper, SSRN 2407199).** A 10% stop on the
  momentum strategy, 1926–2013:
  - cut the worst monthly loss from −49.79% to −11.36% (equal-weighted);
  - more than doubled the Sharpe ratio.

  This is a momentum result, which is the case Kaminski & Lo predict. A
  published review cautions it may rest on fitting a handful of crashes (CXO
  Advisory).

**For this bot:** the strategy buys oversold dips expecting a bounce, the
opposite of momentum. The literature predicts that tight stops cost it
return. This project's measurements agree:

- **EXP-0022:** 2.5 ATR was "a clean peak" among stops of 2.0 to 4.0 ATR.
- **H-0010:** every tighter stop paired with a target was rejected. The
  tightest, 0.917 ATR, did raise raw return by 19.25 points, but:
  - it breached the 14.2806% drawdown ceiling;
  - the entire gain came from its take-profit limits avoiding the rule-exit
    haircut, and net of that execution advantage it was $39,611 worse.

The stop still earns its place as insurance. After a stop-out, 22.2% of
names traded at least 5% below the fill within 10 sessions
([post-stop forensics](2026-09-17-post-stop-forensics.md)).

### 2.2 Take-profit for a trade that reverts to a fair level

- **Bertram (2010)** solves the first-passage problem for a mean-reverting
  (Ornstein–Uhlenbeck) price. It gives analytic trade length, expected
  return and optimal entry and exit thresholds.
- **Leung & Li (2015)** add costs and a stop-loss. A higher stop-loss level
  always implies a lower optimal take-profit level. Target and stop must be
  chosen together.
- **Carr & López de Prado (arXiv 1408.1159)** argue that calibrating levels on
  a backtest causes overfitting. They derive the optimal trading rule
  numerically on paths simulated from the fitted process. Lipton & López de
  Prado (2020) give a closed-form solution.
- **López de Prado (2018)**, *Advances in Financial Machine Learning*:
  - chapter 3, the triple-barrier method — levels scaled to volatility, plus
    a time barrier;
  - chapter 13, optimal trading rules from synthetic data.

What follows from the model, as implemented and tested in `exit_placement.py`:

- **Below the fair level the expected remaining gain is positive:**
  (F − P) × (1 − φ^(T−t)), where F is the fair level, P the current profit,
  φ = 2^(−1/half-life) the fraction of the gap left after one day, and T − t
  the days remaining. Judged on expected profit, a stop below F never helps.
  In a simulated trade (half-life 5 days, fair level 2σ above entry, 20-day
  cap), every tighter stop lowered expected profit, at every step from no stop
  to 0.5σ.
- **Judged on profit, the best target sat above the fair level** (3σ against
  F = 2σ).
- **Judged on smoothness (Sharpe), it sat at 1σ.** That is a far higher win
  rate and less profit. It is the same trap EXP-0050 measured on real trades:
  a 1.0R target raised the share of winning years and cut CAGR from 5.75% to
  4.88%.

### 2.3 Where orders cluster

- **Osler (2003), currency markets.** Take-profit orders cluster at round
  numbers, and stop-loss orders cluster just beyond them. Trends therefore
  tend to reverse at round numbers and speed up once they are crossed.
- **Bhattacharya, Holden & Jacobsen (2012), US stocks.** Traders buy
  excessively one cent below round numbers and sell excessively one cent
  above.
- **Kavajecz & Odders-White (2004).** Support and resistance levels coincide
  with peaks of limit-order-book depth.

What this suggests for placement, **never tested here** and small by nature:

- rest a take-profit just below an obvious round number rather than on it;
- avoid parking a stop just beyond one, where stops bunch and fills cascade.

### 2.4 Intraday timing, and who makes money day trading

- **Volatility and volume are U-shaped through the day** (Wood, McInish & Ord
  1985). A fixed intraday level is more likely to be hit near the open and
  the close.
- **Intraday return patterns exist:**
  - half-hour periodicity across stocks (Heston, Korajczyk & Sadka 2010);
  - the market's first half-hour predicts its last half-hour (Gao, Han, Li &
    Zhou 2018). The 2026-09-19 deep dive marked it "needs intraday bars".
    The SPY 5-minute bars preserved on 2026-09-24 make it testable, and it
    is still untested here. Its natural exit is the close, not a target or
    stop.
- **Outcomes for day traders:**
  - fewer than 1% of Taiwanese day traders predictably earn positive returns
    net of fees (Barber, Lee, Liu & Odean 2014);
  - of Brazilian individuals who day-traded equity index futures for more
    than 300 days (2013–2015), 97% lost money (Chague, De-Losso &
    Giovannetti 2020).

Placement skill does not rescue a strategy without an edge.

### 2.5 The overfitting trap

Choosing levels by trying many and keeping the best is data snooping:

- **Sullivan, Timmermann & White (1999).** The best of a large universe of
  technical rules did not outperform in the following ten years.
- **Corrections for trying many things:**
  - the deflated Sharpe ratio (Bailey & López de Prado 2014);
  - the probability of backtest overfitting (Bailey, Borwein, López de Prado
    & Zhu 2017);
  - a t-statistic hurdle above 3 (Harvey, Liu & Zhu 2016).
- **McLean & Pontiff (2016).** Published predictors earn 26% less out of
  sample and 58% less after publication.

This project's registration rules exist for this reason. Every new exit
proposal carries the family's prior configurations into its
multiple-testing burden (Agent Instructions, "Before proposing research").

## 3. Placement rules the bot now knows

| rule | why | grade |
|---|---|---|
| Scale levels to the stock's own volatility (ATR or σ), never one fixed % for every stock | noise scales with σ; the stop peak was found in ATR units (EXP-0022) | arithmetic + measured here |
| Keep the stop well outside the noise of the holding period; flag a stop inside two typical 15-minute moves | a stop inside noise is ended by noise | arithmetic |
| A target/stop ratio does not create an edge; it only moves the win rate | S / (T + S) | arithmetic |
| Costs are per trade; tight pairs need a much higher hit rate | (S + c) / (T + S) | arithmetic |
| Expected gain = edge × time held; tight pairs starve the edge | Wald's identity | arithmetic |
| For bounce-back trades, a stop is insurance and belongs wide | Kaminski & Lo 2014; Lo & Remorov 2017; EXP-0022; H-0010 | literature + measured here |
| Take profit at or above the fair level; a high-win-rate target lowers profit | Leung & Li 2015; Carr & López de Prado; EXP-0050 | literature + measured here |
| Derive levels from the trade's measured dynamics, then test the one rule once | Carr & López de Prado; Bailey et al.; Sullivan et al. | literature |
| Stops do not protect against gaps: a triggered stop becomes a market order; a stop-limit may not fill | Alpaca order documentation | vendor fact |
| Alpaca brackets pair a take-profit limit with a stop; time in force day or GTC; no extended hours; GTC orders auto-cancel after 90 days | Alpaca order documentation | vendor fact |
| Round numbers: rest targets just below them, keep stops away from just beyond them | Osler 2003; Bhattacharya et al. 2012 | literature, untested here |
| Holding period matters more than level choice | EXP-0019: 1 day −39.3%, 20 days +123.1% | measured here |

## 4. What this project has already measured

The exit family carries about 77 configurations. The items below are the
ledger's own records ([Do Not Re-Research](../knowledge/03-research/Do%20Not%20Re-Research.md)).

| family | what was measured | outcome |
|---|---|---|
| stop width | EXP-0022, 5 widths: "clean peak at 2.5; wider raises win rate and loses a third" | frozen at 2.5 ATR |
| tighter stop + target | H-0010: 0.917 / 1.25 / 1.75 ATR stops with a 2.5R target returned +19.25 / −4.47 / −20.35 points. All three breached the drawdown ceiling. The +19.25 was the target's limit exits avoiding the rule-exit haircut; net of that, $39,611 worse | REJECTED |
| fixed take-profit | EXP-0050: baseline 5.75% CAGR; 1.0R 4.88%; 1.5R 5.15%; 2.0R 5.65%. H-0002: 2.0R +2.7 points on the decade, +7.0 on thirty years | conflicting — **CONF-1 open** |
| target by market day | EXP-0052: tight when the market is down, 1R-down / 3R-up 5.41% vs 5.75% | worse |
| break-even lock | H-0003: 1.0R lock +13.7 points. H-0005: across 0.25–2.0R the series was −41.01, −14.04, +23.94, +13.71, −1.36, 0.00 | spike, REJECTED |
| trailing stop | P5-0007: best +6.9 points, but better in only 5 of 11 years; EXP-0036 | REJECTED |
| partial profit | P5-0010: −6.8 points at 1.0R, nil at 2.0R | REJECTED |
| RSI exit level | EXP-0023: a higher RSI exit, "decade +1.12/+1.43 pts; thirty-year +0.17/+0.11, first half worse, drawdown worse" | REJECTED |
| holding period | EXP-0019; EXP-0024: every longer cap worse | 20 sessions kept |
| volatility-triggered exits | never registered; H-0025 found crossing-time ATR/price *positively* associated with outcome | not open |
| give-back | H-0021: 81.2% of trades crossing +2% go on to a higher gain. H-0025: the gain-to-loss class is not separable at decision time | closed twice |
| exit execution | EXP-0048: every rule exit at the day's high would add +1.33 points, which is unexecutable; H-0011 limit exits INCONCLUSIVE | execution area |
| owner's +0.5% / −0.2%, live | tracked on paper since 2026-09-28 (`tight_exit_comparison` in the daily report) | not evidence; one week of data |

Two caveats cover all of it:

- **Survivorship.** The decade baseline is survivorship-affected. EXP-0031
  found 9.14 → 3.82 CAGR. H-0023: "no further economic search should treat
  +58.5889% as a validated baseline."
- **Lost data.** The thirty-year dataset is lost, so no new result can be
  checked on it.

## 5. Where the bot's levels sit now, and why that is the educated answer

- **Stop: 2.5 × ATR(14), resting at the broker.**
  - Outside ordinary noise: about 19× a typical 15-minute move for UNP.
  - At the measured peak of its family (EXP-0022).
  - Insurance against the trade's premise failing (§2.1, post-stop
    forensics).
- **No fixed target.**
  - The strategy earns its money in the right tail (H-0021: 81.2% of +2%
    crossers go higher).
  - Fixed targets measured here cost return as they tighten (EXP-0050).
- **Exit when the bounce is done, RSI(14) ≥ 60.** This is the practical
  version of "sell at the fair level" (§2.2). A higher RSI exit did not hold
  up (EXP-0023).
- **Time barrier: 20 sessions.** Shorter and longer both did worse (EXP-0019,
  EXP-0024).

**The open question is the entries, not these levels:** whether the dip it
buys bounces often enough. The Clean OOS evaluation from 2026-10-12 answers
that. No exit setting can.

## 6. What was prepared (not wired)

`src/event_aware_trader/exit_placement.py`, pure functions:

- **Barrier arithmetic:** target-first probability with or without an edge,
  expected holding time, expected gain, break-even hit rate.
- **`assess()`:** judges a proposed pair against a stock's volatility, in
  plain words.
- **The Carr–López de Prado optimal-trading-rule search** on simulated
  mean-reverting paths (`simulate_ou_rules`, `optimal_rule`,
  `continuation_value`). Every rule is run on the same simulated paths. The
  objective must be declared in advance.

`tests/test_exit_placement.py` — 23 tests, synthetic inputs only:

- the closed forms;
- Wald's identity;
- a random walk has no rule with an edge;
- the simulated mean matches the closed form;
- every stop lowers expected profit on a reverting trade;
- the Sharpe objective picks a tighter, less profitable target;
- reproducibility and cost handling.

`scripts/exit_check.py` — "ask the bot" whether a pair makes sense. It reads
the symbol's daily price file for volatility and compares with the bot's own
stop. It places nothing:

```bash
.venv/Scripts/python.exe scripts/exit_check.py --target 0.5 --stop 0.2 --symbol UNP
```

For UNP it reports:

- 29% chance, 46% needed;
- about 20 minutes to exit;
- the stop is 0.7× a typical 15-minute move, inside noise;
- expected −0.12% a trade;
- a new UNP entry today would get the bot's stop 5.09% below entry.

## 7. DRAFT H-0026 — the one principled test left, NOT registered

Every target tested here was a hand-picked multiple of risk. The literature's
method is different in kind. Calibrate the strategy's own bounce-back
process, derive the target on synthetic paths, then test that one rule once.

The draft keeps every frozen exit and adds one resting limit at
entry + k* × ATR:

- k* is recalibrated each year from earlier trades only, with a 20-session
  purge.
- The objective is fixed as expected profit per trade, not Sharpe.
- The frozen 2.5-ATR stop stays, because the model cannot value insurance.
- Any gain must survive once the rule-exit haircut its limit exits avoid is
  counted separately. That is the trap H-0010's +19.25 points fell into.

**Validation.** The draft passes `research_gate.check_registration` with no
problems. It builds as a `modelgov.prereg.Hypothesis`. H-0026 is unused; the
2026-09-22 reviews list it as free. **Nothing was appended to
`docs/preregistrations.jsonl`.**

**Expected outcome, stated before any number exists: likely no improvement.**

- EXP-0050 measured return falling as fixed targets tighten.
- H-0021 found most +2% crossers go higher.
- Its value is settling whether a *process-derived* target can beat the RSI
  exit, and informing CONF-1.

**Recommendation:** do not spend it before the Clean OOS verdict. The entries
are the open question.

To run it:

1. The owner approves.
2. The code is committed.
3. The exit family's prior configurations are counted exactly.
4. The registration is sealed.
5. The runner is built.

<details><summary>The draft registration, exactly as validated on 2026-09-27</summary>

```json
{
  "hypothesis_id": "H-0026",
  "kind": "confirmatory",
  "statement": "A profit-take level derived from the frozen strategy's OWN reversion dynamics - a discrete Ornstein-Uhlenbeck process calibrated walk-forward to past trades' post-entry paths in ATR units, with the profit-take chosen on synthetic paths to maximise expected net profit per trade (Carr & Lopez de Prado, arXiv 1408.1159) - raises decade total return above the frozen baseline when added as a resting limit to the unchanged frozen exits. The hypothesis FAILS if the derived level rarely binds (fewer than 5% of trades exit at it), if the improvement is below the standing two-point complexity penalty, if the 14.2806% drawdown ceiling is breached, if fewer than 2 of 3 chronological thirds improve, or if the gain does not survive deflation for the exit family's prior configurations.",
  "rationale": "Every take-profit this project tested was a hand-picked multiple of risk (EXP-0049/0050, H-0002, H-0010, EXP-0051/0052). The literature's answer to 'where should a mean-reverting trade take profit' is different in kind: estimate the trade's reversion process, then derive the level from it on synthetic data, so the level is not searched on the backtest (Carr & Lopez de Prado 2014; Lipton & Lopez de Prado 2020; Bertram 2010; Leung & Li 2015). Under that model a stop below the fair level never adds expected profit, so the frozen 2.5-ATR stop is kept as insurance against the fair level itself moving, which the model cannot value. It is kept because post-stop forensics found 22.2% of stopped names traded at least 5% below the fill within 10 sessions. Expected outcome, stated before any number: likely NO improvement, because EXP-0050 measured return falling as fixed targets tighten, and H-0021 found 81.2% of trades crossing +2% went on higher. The value of the test is that it would settle whether a process-derived target, rather than a hand-picked one, can beat the RSI exit, and it would inform CONF-1.",
  "rule": "Keep every frozen exit unchanged: the 2.5 x ATR(14) resting stop, RSI(14) >= 60 and the 20-session cap. ADD one resting sell limit at entry_price + k* x ATR(14)_at_entry, placed at entry and cancelled when any other exit fires. For each calendar year Y from 2018 on, calibrate the discrete O-U process P_t = (1 - phi) x F + phi x P_(t-1) + sigma x e_t by pooled OLS of dP_t on P_(t-1) over the 20-session post-entry close paths, in units of entry ATR, of every baseline trade whose 20-session path ended at least 20 sessions before Y begins (the purge). Paths continue past the trade's actual exit. No trimming, no per-symbol parameters. Then simulate 100,000 paths with seed = Y, the stop at 2.5 ATR and a 20-step time barrier, and set k*(Y) to the grid point with the highest expected net profit per trade. The grid is 0.5 to 10.0 ATR in steps of 0.5, plus 'no target'. If 'no target' wins, year Y trades exactly as the baseline.",
  "parameters": {
    "dataset": {
      "id": "decade-2016-2026-split-adjusted-230",
      "sha256": "935fed79de9803f1da2a380c6f3f76ab525b27c5d14830bbea4744a7bf73d4a7"
    },
    "population": "the frozen baseline's own decade trades (698) for calibration paths; the frozen emulator's candidate stream, unchanged, for evaluation",
    "benchmark": "the frozen baseline on the same emulator and data (+58.5889% / 698 trades must reproduce first); SPY total return reported alongside",
    "profit_take_grid_atr": "0.5, 1.0, ..., 10.0 and none - searched ONLY on synthetic paths",
    "stop_atr": 2.5,
    "time_barrier_sessions": 20,
    "objective": "expected net profit per trade (mean), fixed now; Sharpe is NOT the objective",
    "calibration": "pooled OLS AR(1) on post-entry ATR-unit close paths, expanding window, 20-session purge, yearly refit",
    "synthetic_paths": 100000,
    "seed": "calendar year",
    "fill_rule": "limit fills at the open if the open is at or above it, else at the limit if the high exceeds it by at least 5 basis points; if the stop and the limit are both touched on one daily bar the STOP is assumed first",
    "costs": "the frozen CostModel unchanged; the limit exit pays no rule-exit haircut because a resting limit fills at its price"
  },
  "search_procedure": "One configuration. The grid is traversed only on synthetic paths, never on the backtest. The objective, grid, calibration method, purge, seeds, fill rule and ambiguity rule are fixed here and may not change after any result is seen. No second configuration, no alternative objective, no alternative calibration.",
  "max_configurations": 1,
  "datasets": [
    "decade (development) via research_gate.verify_dataset; the frozen baseline's 698 trades",
    "thirty_year: LOST - not used",
    "clean OOS: NOT USED",
    "live audit log: NOT USED"
  ],
  "information_boundary": "k*(Y) uses only paths that ended at least 20 sessions before year Y begins; ATR(14) is read at the entry bar; the limit is placed at entry. No bar after the decision is used to set a level. Same-bar stop/limit ambiguity is resolved against the rule.",
  "execution_assumptions": "Frozen SPEC-0001 boundary: entry at the signal close; rule exits at close x (1 - 0.652%); stops at the stop price or the open if gapped. The added limit fills per the fill rule; daily OHLCV cannot establish queue position (H-0017, H-0018), so touch fills are reported only as a secondary, optimistic bound.",
  "primary_metric": "decade total return of the frozen emulator with the added limit minus the frozen baseline's, same entries and candidate stream",
  "secondary_metrics": [
    "max drawdown against the 14.2806% ceiling",
    "the rule-exit haircut avoided by limit exits, in dollars, attributed separately",
    "share of trades exiting at the limit",
    "chronological thirds, 2-of-3 rule",
    "per-year deltas",
    "k*(Y) path across years",
    "the touch-fill optimistic bound, labelled unexecutable",
    "count of same-bar ambiguous days",
    "deflated Sharpe ratio for the exit family's configurations + 1"
  ],
  "acceptance_criteria": "ALL of: primary metric >= +2.0 points (the standing complexity penalty); the improvement survives after the rule-exit haircut the limit exits avoid is attributed separately (H-0010's clause E: a gain that is only avoided haircut is an execution-accounting effect, not a better exit); drawdown within 14.2806%; at least 2 of 3 chronological thirds positive; limit binds on >= 5% of trades; deflated Sharpe ratio significant at 95% with N = the exit family's exact prior configuration count (about 77, counted before sealing) + 1.",
  "rejection_criteria": "Explicitly NOT successes: a gain explained by the avoided rule-exit haircut (H-0010: +19.25 points that were -$39,611 net of it); a gain that appears only under touch fills; a gain concentrated in one year or one third; a k* that moves erratically across years (reported, and not rescued by smoothing); any use of Sharpe as the objective after the fact; any comparison against a baseline other than the frozen one.",
  "robustness_requirements": [
    "baseline +58.5889% / 698 reproduced first",
    "survivorship: H-0023 says the decade baseline is not validated, so the ceiling is research_evidence",
    "every prior exit configuration named in the report",
    "CONF-1 stated, and not resolved silently"
  ],
  "complexity_penalty": "The standing two percentage points.",
  "required_oos_test": "None available: the thirty-year dataset is lost and Clean OOS is reserved for the frozen strategy. A passing result is research_evidence only; promotion would need a separately governed forward evaluation.",
  "promotion_requirements": [
    "owner approval",
    "money-path review (SPEC-0001 C-27)",
    "new fingerprint and a restarted evaluation clock",
    "Clean OOS remains uncontaminated"
  ]
}
```

</details>

## 8. What turning anything on would take

The prepared pieces do not change trading. To act on any of them:

- **An exit-rule change** is a strategy semantics change (SPEC-0001 C-26). It
  needs owner approval and a money-path review (C-27). It would also change
  the fingerprint and restart the evaluation clock that reaches its first
  clean session on 2026-10-12.
- **Bracket orders (take-profit plus stop)** are supported by Alpaca with day
  or GTC time in force. At entry the bot already submits a bracket as a day
  order, with its take-profit leg far away: MDY on 2026-09-24, reference
  664.48, take-profit 751.25, about +13%. After that, the rule exits and the
  GTC resting stop do the work.

## Sources

**Literature (each checked on 2026-09-27):**

- K. M. Kaminski & A. W. Lo, "When do stop-loss rules stop losses?", *Journal
  of Financial Markets* 18 (2014) 234–254 — [RePEc](https://ideas.repec.org/p/hhs/sifrwp/0063.html),
  [MIT](https://dspace.mit.edu/entities/publication/bb69ca4b-0cdc-487f-831d-63b2e84fafee).
- A. W. Lo & A. Remorov, "Stop-loss strategies with serial correlation,
  regime switching, and transaction costs", *Journal of Financial Markets* 34
  (2017) 1–15 — [SSRN](https://www.ssrn.com/abstract=2695383).
- Y. Han, G. Zhou & Y. Zhu, "Taming momentum crashes: a simple stop-loss
  strategy", working paper — [SSRN 2407199](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2407199);
  caveat: [CXO Advisory](https://www.cxoadvisory.com/technical-trading/stop-losses-to-avoid-stock-momentum-crashes/).
- W. K. Bertram, "Analytic solutions for optimal statistical arbitrage
  trading", *Physica A* 389(11) (2010) 2234–2243 — [RePEc](https://ideas.repec.org/a/eee/phsmap/v389y2010i11p2234-2243.html).
- T. Leung & X. Li, "Optimal mean reversion trading with transaction costs and
  stop-loss exit", *IJTAF* 18(3) (2015) — [arXiv 1411.5062](https://arxiv.org/abs/1411.5062).
- P. Carr & M. López de Prado, "Determining optimal trading rules without
  backtesting" — [arXiv 1408.1159](https://arxiv.org/abs/1408.1159).
- A. Lipton & M. López de Prado, "A closed-form solution for optimal
  Ornstein–Uhlenbeck driven trading strategies", *IJTAF* (2020) —
  [arXiv 2003.10502](https://arxiv.org/abs/2003.10502).
- M. López de Prado, *Advances in Financial Machine Learning*, Wiley (2018),
  chapters 3 and 13 — [chapter 13](https://www.oreilly.com/library/view/advances-in-financial/9781119482086/c13.xhtml).
- C. L. Osler, "Currency orders and exchange rate dynamics: an explanation for
  the predictive success of technical analysis", *Journal of Finance* 58(5)
  (2003) 1791–1819 — [RePEc](https://ideas.repec.org/a/bla/jfinan/v58y2003i5p1791-1819.html).
- K. A. Kavajecz & E. R. Odders-White, "Technical analysis and liquidity
  provision", *Review of Financial Studies* 17(4) (2004) — [OUP](https://academic.oup.com/rfs/article-abstract/17/4/1043/1570736).
- U. Bhattacharya, C. W. Holden & S. Jacobsen, "Penny wise, dollar foolish:
  buy-sell imbalances on and around round numbers", *Management Science*
  58(2) (2012) 413–431 — [RePEc](https://ideas.repec.org/a/inm/ormnsc/v58y2012i2p413-431.html).
- R. A. Wood, T. H. McInish & J. K. Ord, "An investigation of transactions
  data for NYSE stocks", *Journal of Finance* 40(3) (1985) — [DOI](https://doi.org/10.2307/2327796).
- S. L. Heston, R. A. Korajczyk & R. Sadka, "Intraday patterns in the
  cross-section of stock returns", *Journal of Finance* 65(4) (2010)
  1369–1407 — [RePEc](https://ideas.repec.org/a/bla/jfinan/v65y2010i4p1369-1407.html).
- L. Gao, Y. Han, S. Z. Li & G. Zhou, "Market intraday momentum", *Journal of
  Financial Economics* 129(2) (2018) 394–414 — [EconPapers](https://econpapers.repec.org/RePEc:eee:jfinec:v:129:y:2018:i:2:p:394-414).
- B. M. Barber, Y.-T. Lee, Y.-J. Liu & T. Odean, "The cross-section of
  speculator skill: evidence from day trading", *Journal of Financial
  Markets* (2014) — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=529063).
- F. Chague, R. De-Losso & B. Giovannetti, "Day Trading for a Living?"
  (2020) — [SSRN 3423101](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101),
  as cited in [the 2026-09-19 day-trading report](2026-09-19-day-trading-research.md).
- R. Sullivan, A. Timmermann & H. White, "Data-snooping, technical trading rule
  performance, and the bootstrap", *Journal of Finance* 54(5) (1999)
  1647–1691 — [RePEc](https://ideas.repec.org/a/bla/jfinan/v54y1999i5p1647-1691.html).
- D. H. Bailey & M. López de Prado, "The deflated Sharpe ratio", *Journal of
  Portfolio Management* 40(5) (2014) 94–107 — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551).
- D. H. Bailey, J. Borwein, M. López de Prado & Q. J. Zhu, "The probability of
  backtest overfitting", *Journal of Computational Finance* 20(4) (2017)
  39–69 — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253).
- C. R. Harvey, Y. Liu & H. Zhu, "…and the cross-section of expected returns",
  *Review of Financial Studies* 29(1) (2016) 5–68 — [RePEc](https://ideas.repec.org/a/oup/rfinst/v29y2016i1p5-68..html).
- R. D. McLean & J. Pontiff, "Does academic research destroy stock return
  predictability?", *Journal of Finance* 71(1) (2016) 5–32.
- J. Sweeney, *Maximum Adverse Excursion: Analyzing Price Fluctuations for
  Trading Management*, Wiley (1997) — [Wiley](https://www.wiley.com/en-us/Maximum+Adverse+Excursion:+Analyzing+Price+Fluctuations+for+Trading+Management-p-x000030303).
  This is where maximum-adverse-excursion analysis comes from in practice;
  H-0025 measured MFE and MAE on this strategy.

**Vendor:**

- Alpaca, "Orders at Alpaca" — [docs](https://docs.alpaca.markets/docs/orders-at-alpaca).

**This project:** [Do Not Re-Research](../knowledge/03-research/Do%20Not%20Re-Research.md),
[Research Gaps](../knowledge/05-open-questions/Research%20Gaps.md),
[post-stop forensics](2026-09-17-post-stop-forensics.md),
[H-0025](2026-09-23-h0025-gain-to-loss-forensics.md), `docs/experiments.jsonl`,
`docs/phase5-research.jsonl`, `docs/preregistrations.jsonl`.
