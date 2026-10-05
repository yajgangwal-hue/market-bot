"""H-0027..H-0030: the shorting hypotheses, fixed before any outcome is computed.

Owner's request, 2026-10-03: research whether shorting could materially improve
the bot's robust, risk-adjusted returns relative to SPY; do not assume it works;
investigate the +0.5% / -0.2% idea as a target, not a requirement; preregister a
small number of economically motivated hypotheses; implement nothing unless the
evidence passes.

WHAT IS ALREADY ANSWERED, AND IS NOT RE-RUN
  EXP-0011  mirror short book, stop-distance sizing: -0.88%/yr decade, -0.19%/yr 30y
  EXP-0012  shorting the long rule's own signals: -0.501%/trade, no gradient
  EXP-0013  shorting violent opens: negative in every bucket (154,131 sessions)
  EXP-0026  violent-gap shorts as accounts: -49.8% to -64.2%/yr, -100% DD
  EXP-0043  the long book is BETTER when SPY is below its 200-day
  EXP-0011  also: overbought shorts ABOVE the 200-day lost (-0.454%/trade)
  H-0021/H-0025/H-0026, EXP-0049/0050: long-side take profits and band exits

WHAT IS NEW
  H-0027  EXP-0011's own open question: the mirror signal in a SEPARATE sleeve
          with equal-notional sizing, realistic fills, judged inside the account
  H-0028  the same, new shorts only in a confirmed bear tape
  H-0029  a different family: relative-weakness breakdown (momentum/trend) shorts
  H-0030  the owner's +0.5% / -0.2% pair against the frozen exits, both sides,
          one trade per signal

Registered WITHOUT a commit (the owner has not authorised commits): the
`code_commit` field records the pre-existing HEAD, so the binding of code to
registration is the SHA-256 of every code file, sealed in `parameters`.
"""

import hashlib
from pathlib import Path

from event_aware_trader.modelgov.prereg import Hypothesis

REPO = Path(__file__).resolve().parents[1]

CODE_FILES = [
    "scripts/short_sleeve_research.py",
    "scripts/run_short_hypotheses.py",
    "tests/test_short_sleeve_research.py",
]

DATASET = {"id": "decade-2016-2026-split-adjusted-230",
           "sha256": "935fed79de9803f1da2a380c6f3f76ab525b27c5d14830bbea4744a7bf73d4a7"}

POPULATION = (
    "The 230-name research universe as forensics_regime.load returns it (DEFAULT_UNIVERSE "
    "without crypto, files with >= 500 bars). A symbol is eligible on a session only with "
    ">= 215 bars of history and the long rule's own filters: close >= $20, 20-session "
    "average dollar volume >= $50M, 14-day Wilder ATR <= 3.5% of the close. The ETF "
    "survivorship control is the h0019_controls ETF set (INSTRUMENT_NAMES keyword match, "
    "STX removed, GLD added).")

BENCHMARK = (
    "Control A: the frozen long-only baseline (research.PRODUCTION_CANDIDATE, must reproduce "
    "+58.5889% / 698 trades) with idle cash parked at the 3-month bill rate "
    "(research.with_parked_cash). Control A-live: the long book as run since 2026-09-29 "
    "(frozen + EXP-0055 take profit at 1R, 5 bp trade-through), parked. D: A scaled to the "
    "combined account's volatility around the bill rate. Market: SPY total return "
    "15.00%/yr (EXP-0037, 2016-01-04..2026-09-14) for the headline; daily statistics on "
    "SPY's split-adjusted price series from this dataset plus 1.58 points a year of "
    "dividends (REM-0003), and a SPY/bill blend matched to the combined account's "
    "volatility. Same sessions, same starting capital ($100,000), same cash convention.")

INFORMATION_BOUNDARY = (
    "Every signal uses bars up to and including the signal session's close; the order is "
    "placed at that close, as the frozen long rule's entry_fill='signal_close' assumes "
    "(live: 15:45 on the forming bar). Market regime - SPY against its 200-day average, and "
    "SPY's 20-day realised volatility tercile against its own trailing 252 sessions - is as "
    "of the same close. Nothing uses a later bar. The decade dataset was used by "
    "EXP-0011/0012/0013/0026 and to develop the long strategy, so it is CONTAMINATED: every "
    "result is a rejection test (dataset purpose 'rejection_test') that can reject and "
    "cannot accept.")

EXECUTION = (
    "Short sale at the signal close x (1 - 6 bp). Resting buy-stop k x ATR(14) above the "
    "signal close: a session that opens at or above it covers at the open (gap-through), "
    "otherwise at the stop; plus 6 bp. RSI cover and the time cap cover at the close x "
    "(1 + 6 bp + the 0.652% rule-exit haircut). A take-profit limit fills at its level only if "
    "price trades 5 bp through it, or at the open on a gap; a bar touching stop and target "
    "is given to the stop. Borrow 0.5%/yr and dividends 2.0%/yr on entry notional per "
    "calendar day held; SEC fee 0.278 bp on the sale. No new short under SEC Rule 201 (a "
    "decline of 10% or more that session or the one before). Every name is assumed "
    "borrowable: historical borrow availability is not in the data. Whole shares. Sizing: "
    "equal notional, 5% of account equity per short; at most 6 shorts and 30% of equity "
    "short in total; one per correlation bucket; never a name the long book holds that "
    "session. Long market value + short notional never exceeds equity at an entry, and if "
    "the long book's own growth breaks that, the youngest shorts are covered at that close "
    "with rule-exit pricing. The long book is the frozen emulator run, untouched; the sleeve "
    "is an overlay on its equity curve. In the parked account the short notional earns no "
    "interest: the sleeve is charged the bill rate on it.")

HALVES = ["2016-01-04..2020-12-31", "2021-01-01..2026-09-04"]

COSTS = {"one_way_bps": 6.0, "rule_exit_haircut": 0.00652, "borrow_annual": 0.005,
         "dividend_annual": 0.02, "sec_fee_bps": 0.278}

SLEEVE = {"notional_fraction": 0.05, "max_positions": 6, "max_short_fraction": 0.30,
          "one_per_bucket": True, "rf_for_sharpe": 0.023, "starting_capital": 100_000}

DATASETS = ["decade (contaminated; rejection test only) via research_gate.verify_dataset",
            "thirty_year: LOST - not used",
            "clean OOS: NOT USED (the forward record holds no shorts)",
            "live audit log: NOT USED"]

SECONDARY = [
    "sleeve trade distribution: n, mean, median, p05/p25/p50/p75/p90/p95, win rate, mean and "
    "median winner and loser, profit factor, expectancy, t-stat",
    "maximum adverse and favourable excursion per trade (daily-bar approximation)",
    "holding time; exit-reason mix; stop exits that gapped through and their excess loss "
    "beyond the stop",
    "expectancy at one-way cost 0 / 6 / 12 / 24 bp",
    "results by SPY regime (above/below its 200-day) and volatility tercile at entry",
    "worst 10 trades with dates, gap, loss as % of equity at entry",
    "accounts A, B (sleeve alone, $100,000), C (A + sleeve), D (A scaled to C's volatility), "
    "SPY price, SPY total return (approx.), risk-matched SPY/bill blend: CAGR, total return, "
    "volatility, Sharpe, Sortino, max drawdown, downside deviation, Calmar, worst day, "
    "longest losing streak, by year",
    "correlation of the sleeve's daily P&L with A's daily returns and with SPY; beta to SPY",
    "the sleeve in A's weak periods: A more than 5% below its peak; A's worst decile of "
    "months; 2022",
    "exposure (average short notional / equity), turnover, forced covers, Rule 201 skips",
    "directional accuracy: share of signals followed by a lower close after 5/10/20 "
    "sessions against the base rate of all eligible stock-days below their 200-day",
]

ACCEPTANCE = (
    "All of: (R1) Delta Sharpe > 0 over the full window AND in each half; (R2) the sleeve's "
    "net expectancy per trade > 0 with t >= 2.0; (R3) combined CAGR >= control CAGR; (R4) "
    "combined max drawdown no deeper than 1.10 x the control's; (R5) robustness, each fixed "
    "in advance - R1 (full window) and R3 still hold with one-way cost 12 bp, with borrow "
    "3%/yr plus dividends 4%/yr, and against control A-live; and the sleeve's net "
    "expectancy per trade is > 0 when its universe is the ETF survivorship control; (R6) "
    "tail - no single short loses more than 1.0% of account equity at entry, and the "
    "combined account's worst day is no more than 0.5 percentage points worse than the "
    "control's. Passing ALL earns at most PROMISING BUT NOT READY FOR OOS: the data is "
    "contaminated and the thirty-year window is lost.")

REJECTION = (
    "REJECTED if any of R1 (full window), R2, R3 or R4 fails. INCONCLUSIVE if those pass "
    "but R1 in either half, R5 or R6 fails.")

ROBUSTNESS = [
    "R5a one-way cost 12 bp",
    "R5b borrow 3%/yr + dividends 4%/yr",
    "R5c control A-live (frozen + EXP-0055 take profit)",
    "R5d ETF survivorship-control short universe",
    "R1 both halves",
    "haircut 0 REPORTED only - it cannot rescue a failure",
]

COMPLEXITY = (
    "A second strategy and a second money path: shorts invert every sign in the live code "
    "(the reconciler would rest a SELL stop on a short and double it), and add borrow, "
    "recall, squeeze and Rule 201 risks the long book does not carry. The benefit must clear "
    "every criterion before any of that cost is considered.")

OOS = (
    "None available. A pass would justify only a registered SHADOW record - signals and "
    "hypothetical fills logged by the bot, no orders - from the first clean session "
    "(2026-10-27), judged after at least 60 sessions and 30 shadow trades.")

PROMOTION = ["a sealed shadow-record hypothesis registered before its first session",
             "owner approval", "a separately governed sleeve with its own fingerprint",
             "a short-safe reconciler (buy-stops above shorts) and kill switches",
             "the exposed Alpaca credential rotated"]


def code_hashes():
    return {f: hashlib.sha256((REPO / f).read_bytes()).hexdigest() for f in CODE_FILES}


def _common(extra, hashes):
    params = {"dataset": DATASET, "population": POPULATION, "benchmark": BENCHMARK,
              "costs": COSTS, "halves": HALVES, "code_sha256": hashes}
    params.update(extra)
    return params


def hypotheses(hashes=None):
    hashes = hashes or code_hashes()
    mirror_rule = ("At the signal close: RSI(14) >= 70 and close < SMA(200), plus the eligibility "
                   "filters. Short at that close. Cover: buy-stop 2.5 x ATR(14) above the signal "
                   "close; RSI(14) <= 40 at a close; or 20 sessions held. Candidates ranked by RSI, "
                   "highest first, ties by symbol.")
    h27 = Hypothesis(
        hypothesis_id="H-0027",
        statement=(
            "A separately sized short sleeve on the failed-rally signal (RSI(14) >= 70 below the "
            "200-day average), covered at RSI(14) <= 40, a 2.5-ATR stop or 20 sessions, at equal 5% "
            "notional, improves the frozen long-only account's risk-adjusted return without "
            "costing return or breaching the drawdown ceiling."),
        rationale=(
            "EXP-0011 measured this signal at +1.200% a trade over thirty years but -0.88%/yr as an "
            "account, and named the cause - stop-distance sizing gave the high-ATR trades carrying "
            "the edge the smallest positions, and the book sat idle - and the one change that "
            "could alter the answer: equal-weight sizing in a sleeve of its own. This tests that, "
            "once, with the realistic fills that study lacked. Economically: short-term reversal "
            "is paid for providing liquidity (Nagel 2012), and below the 200-day the stock's own "
            "drift is weaker, which is where EXP-0011 found the mirror worked."),
        rule=mirror_rule + " Every session regime.",
        parameters=_common({"signal": "rsi14 >= 70 and close < sma200", "cover_rsi": 40,
                            "stop_atr": 2.5, "max_bars": 20, "bear_gate": False,
                            "sleeve": SLEEVE}, hashes),
        search_procedure="One configuration. The robustness runs are fixed in advance and cannot replace it.",
        max_configurations=1, datasets=DATASETS,
        information_boundary=INFORMATION_BOUNDARY, execution_assumptions=EXECUTION,
        primary_metric=("Delta Sharpe: annualised excess-return Sharpe (rf 2.30%) of the combined "
                        "parked account (A + sleeve) minus that of A, over the decade's sessions."),
        secondary_metrics=SECONDARY, acceptance_criteria=ACCEPTANCE,
        rejection_criteria=REJECTION, robustness_requirements=ROBUSTNESS,
        complexity_penalty=COMPLEXITY, required_oos_test=OOS,
        promotion_requirements=PROMOTION)

    h28 = Hypothesis(
        hypothesis_id="H-0028",
        statement=(
            "The H-0027 sleeve opening new shorts ONLY when SPY has closed below its 200-day average "
            "for 3 consecutive sessions improves the frozen long-only account's risk-adjusted return "
            "without costing return or breaching the drawdown ceiling."),
        rationale=(
            "regime_shorts.py recorded, on an earlier model-ranked bot (2021-2026, unregistered), "
            "that always-on shorts took six years from +58.90% to -0.74% while bear-gated shorts "
            "returned +55.98%: +17.57% in 2022 against +3.81%, -9.59% in 2023. Shorting only when "
            "the market's own drift is negative is the textbook remedy for the drift that kills "
            "always-on shorts. Against it: EXP-0043 found the LONG book is better when SPY is below "
            "its 200-day, so the gate concentrates the sleeve exactly where the long book is "
            "strongest. The test decides which effect dominates."),
        rule=mirror_rule + (" New shorts only when SPY's close has been below its 200-day average "
                            "for each of the last 3 sessions; open shorts keep their own exits."),
        parameters=_common({"signal": "rsi14 >= 70 and close < sma200", "cover_rsi": 40,
                            "stop_atr": 2.5, "max_bars": 20, "bear_gate": "SPY < SMA200 for 3 sessions",
                            "sleeve": SLEEVE}, hashes),
        search_procedure="One configuration. The robustness runs are fixed in advance and cannot replace it.",
        max_configurations=1, datasets=DATASETS,
        information_boundary=INFORMATION_BOUNDARY, execution_assumptions=EXECUTION,
        primary_metric=("Delta Sharpe: annualised excess-return Sharpe (rf 2.30%) of the combined "
                        "parked account (A + sleeve) minus that of A, over the decade's sessions."),
        secondary_metrics=SECONDARY, acceptance_criteria=ACCEPTANCE,
        rejection_criteria=REJECTION, robustness_requirements=ROBUSTNESS,
        complexity_penalty=COMPLEXITY, required_oos_test=OOS,
        promotion_requirements=PROMOTION)

    h29 = Hypothesis(
        hypothesis_id="H-0029",
        statement=(
            "A short sleeve on relative-weakness breakdowns - close below the 200-day average, a new "
            "50-session closing low, and a 63-session return at least 10 points behind SPY's - "
            "covered by a 2.5-ATR stop or after 20 sessions, at equal 5% notional, improves the "
            "frozen long-only account's risk-adjusted return without costing return or breaching "
            "the drawdown ceiling."),
        rationale=(
            "A different family from the long book's reversal: trend and momentum. Stocks that are "
            "falling, and falling faster than the market, tend to keep underperforming over one to "
            "twelve months (Jegadeesh & Titman 1993; Moskowitz, Ooi & Pedersen 2012, 'time series "
            "momentum'). It would be uncorrelated with a book that buys dips in uptrends. Known "
            "risks, recorded before the result: momentum's short leg crashes in sharp rebounds, and "
            "this universe of today's survivors lacks both the names that fell to delisting (biasing "
            "AGAINST the hypothesis) and the names taken over at a premium (biasing FOR it)."),
        rule=("At the signal close: close < SMA(200); close below every close of the prior 50 "
              "sessions; (close / close 63 sessions ago - 1) minus SPY's same return <= -10%; plus "
              "the eligibility filters. Short at that close. Cover: buy-stop 2.5 x ATR(14) above the "
              "signal close, or 20 sessions held; no RSI cover. Candidates ranked by how far behind "
              "SPY, furthest first, ties by symbol. Every session regime."),
        parameters=_common({"signal": "close < sma200, new 50-session closing low, 63d return - SPY 63d <= -0.10",
                            "cover_rsi": None, "stop_atr": 2.5, "max_bars": 20, "bear_gate": False,
                            "sleeve": SLEEVE}, hashes),
        search_procedure="One configuration. The robustness runs are fixed in advance and cannot replace it.",
        max_configurations=1, datasets=DATASETS,
        information_boundary=INFORMATION_BOUNDARY, execution_assumptions=EXECUTION,
        primary_metric=("Delta Sharpe: annualised excess-return Sharpe (rf 2.30%) of the combined "
                        "parked account (A + sleeve) minus that of A, over the decade's sessions."),
        secondary_metrics=SECONDARY, acceptance_criteria=ACCEPTANCE,
        rejection_criteria=REJECTION, robustness_requirements=ROBUSTNESS,
        complexity_penalty=COMPLEXITY, required_oos_test=OOS,
        promotion_requirements=PROMOTION)

    h30 = Hypothesis(
        hypothesis_id="H-0030",
        statement=(
            "On the same signals, a fixed +0.5% target with a -0.2% stop earns more per trade, after "
            "costs, than the frozen exits - for the frozen long rule's signals and, separately, for "
            "the H-0027 failed-rally short signals."),
        rationale=(
            "The owner's target, tested as a hypothesis rather than imposed. Prior evidence predicts "
            "failure: post-entry paths are a random walk with drift (H-0026), expected gain is edge "
            "x time held so tight pairs starve the edge, 81.2% of +2% crossers went higher (H-0025), "
            "and an entry at the close faces an overnight gap that is often larger than 0.2% on its "
            "own. The long-side pair has been tracked live since 2026-09-28 but never measured at "
            "decade scale; it is included to answer the owner's question, not as a candidate."),
        rule=("Populations: every eligible signal, at most one open per symbol (a symbol is skipped "
              "until its frozen-exit trade would have closed). Long signals: the frozen rule (RSI(14) "
              "<= 35 above SMA(200), eligibility filters). Short signals: H-0027's. Entry at the "
              "signal close +/- 6 bp. FROZEN exits: long - 2.5-ATR stop, RSI >= 60, 20 sessions; short "
              "- H-0027's. TIGHT exits: a resting target 0.5% beyond the entry fill and a stop 0.2% "
              "against it, nothing else, 20-session cap. Gaps: a session opening beyond the stop "
              "exits at the open; opening beyond the target exits at the open. A bar touching both is "
              "given to the stop (primary); the target-first ordering is reported as an optimistic "
              "bound that can pass nothing."),
        parameters=_common({"target_pct": 0.005, "stop_pct": 0.002, "max_bars": 20,
                            "sides": ["long (frozen rule's signals)", "short (H-0027 signals)"],
                            "ordering": "stop first on a two-sided bar (primary)"}, hashes),
        search_procedure="Two configurations, one per side. No other level pair is evaluated.",
        max_configurations=2, datasets=DATASETS,
        information_boundary=INFORMATION_BOUNDARY, execution_assumptions=EXECUTION,
        primary_metric=("Per side: mean paired difference in net return per signal, tight (stop-first "
                        "ordering) minus frozen, on the same signals."),
        secondary_metrics=[
            "per side and per exit set: distribution (n, mean, median, percentiles, win rate, winners, "
            "losers, profit factor, t-stat)",
            "tight stops: realised loss against the intended -0.2% - mean, median, p05, worst, share "
            "worse than -0.25% / -0.5% / -1.0%, share gapped",
            "breakeven win rate for the tight pair after costs",
            "expectancy at one-way cost 0 / 6 / 12 bp",
            "the target-first optimistic bound",
            "both halves"],
        acceptance_criteria=(
            "Per side, all of: the paired difference > 0 with t >= 2.0; > 0 in each half; and the "
            "tight pair's net expectancy per trade > 0. Earns at most PROMISING BUT NOT READY FOR OOS: "
            "one trade per signal ignores the portfolio, and the data is contaminated."),
        rejection_criteria=(
            "Per side: REJECTED if the paired difference <= 0 or the tight pair's net expectancy <= 0. "
            "INCONCLUSIVE otherwise."),
        robustness_requirements=["both halves", "one-way cost 0 / 6 / 12 bp reported",
                                 "target-first ordering reported, cannot pass"],
        complexity_penalty="None beyond the exit change itself; the evidence must stand on its own.",
        required_oos_test=OOS,
        promotion_requirements=PROMOTION)
    return [h27, h28, h29, h30]
