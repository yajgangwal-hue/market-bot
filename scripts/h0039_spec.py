"""H-0039: diversified trend following on futures - fixed before any outcome.

Owner, 2026-10-04: "i want you to build a smart futuers trading strategy".

The candidate is the futures strategy with the longest record in the
literature, and the one this project's broker study
(docs/2026-09-28-long-short-and-broker-research.md) named: time-series
momentum across asset classes (Moskowitz, Ooi & Pedersen 2012; Hurst, Ooi &
Pedersen 2017). Its rule is taken from those papers and fixed here: nothing is
searched.

Free futures history is front-month prices spliced at each roll, and the
splices are not returns. So each market is measured through a fund that
tracks it (the dataset's datasheet lists the gaps this leaves). Whole-contract
sizing at the owner's account size is NOT measured here. It is a separate
check before any implementation.

Prior trials that touch trend rules, all REJECTED:
- H-0036: 7,846 single-market chart rules on SPY, including moving-average and
  channel rules.
- EXP-0003: crypto strategy families, including trend.
- EXP-0033 and EXP-0034: crypto trend windows.
- EXP-0004 and EXP-0020: the mean-reversion strategy's 200-day filter, a
  different use.
This test differs: the literature puts the edge in diversification across
asset classes, which a single market cannot show.
"""

import hashlib
from datetime import date
from pathlib import Path

from event_aware_trader.modelgov.prereg import Hypothesis

REPO = Path(__file__).resolve().parents[1]
HYPOTHESIS_ID = "H-0039"
CODE_FILES = ["scripts/h0039_acquire.py", "scripts/h0039_trend.py", "scripts/run_h0039.py",
              "tests/test_h0039_trend.py"]
DATASET = {"id": "futures-proxies-yahoo-2006-2026-20",
           "sha256": "dc1d1049c62f4cf0f86b2e31eb359b1f1f9c73f7be1727aa886f8ea473958042"}
END = date(2026, 9, 30)
SPLIT = date(2017, 1, 1)
BOOTSTRAP = {"method": "stationary (Politis & Romano 1994), re-centred, one-sided",
             "q": 0.05, "resamples": 10_000, "seed": 20261004}
PRIOR_TRIALS = {"search_size_equity": 173, "declared_trials_before": 7930,
                "related": ["H-0036", "EXP-0003", "EXP-0033", "EXP-0034", "EXP-0004", "EXP-0020"]}


def code_hashes():
    return {f: hashlib.sha256((REPO / f).read_bytes()).hexdigest() for f in CODE_FILES}


def markets():
    import h0039_trend as engine
    return {s: {"class": c, "stands_for": f, "cost_per_side": k, "rolls_per_year": r}
            for s, (c, f, k, r) in engine.MARKETS.items()}


def hypothesis(hashes=None):
    hashes = hashes or code_hashes()
    return Hypothesis(
        hypothesis_id=HYPOTHESIS_ID,
        statement=(
            "A diversified trend-following futures portfolio - time-series momentum with 1-, 3- "
            "and 12-month signals, equal risk per market, a 10% volatility target and monthly "
            "rebalancing - measured on 19 futures-tracking funds from May 2008 to September 2026 "
            "net of micro-futures costs, earns a positive return over Treasury bills, keeps it "
            "after the papers that documented it, and helps an account holding SPY beat SPY."),
        rationale=(
            "Time-series momentum earned positive returns across equity, bond, commodity and "
            "currency futures in Moskowitz, Ooi & Pedersen (2012; 58 markets, 1985-2009) and "
            "over 1880-2016 in Hurst, Ooi & Pedersen (2017). The explanations offered are slow "
            "then excessive reaction to news, and hedgers' demand. It is the futures candidate "
            "the 2026-09-28 broker study named. Its documented edge comes from diversification "
            "across asset classes, which H-0036's single-market rules on SPY could not test. "
            "This project has found published rules fading after publication, so the second "
            "half (2017 on, after both papers) is a direct test of that."),
        rule=(
            "At the last session of each month, for each market: signal = mean of the signs of "
            "its 21-, 63- and 252-session total returns in excess of bills (prod(1+r)/prod(1+rf) "
            "- 1). Volatility = annualised EWMA of daily excess returns, centre of mass 60 "
            "sessions, demeaned. Raw weight = signal / volatility; the book is scaled to 10% "
            "ex-ante annual volatility using those volatilities and the trailing 252-session "
            "correlation matrix; gross notional capped at 10x equity (a guard, not a working "
            "limit). Trade at the next session's close; hold to the next rebalance, weights "
            "drifting with prices. Account: equity in bills, R = rf + sum w (r - rf) - costs."),
        parameters={
            "dataset": DATASET,
            "population": ("19 futures-tracking funds (h0039_trend.MARKETS); calendar = the "
                           "sessions all 19 trade, from 2007-04-18 (UNG's first day) to the end "
                           "date"),
            "benchmark": "SPY total return (Yahoo adjusted close) over identical sessions",
            "markets": markets(),
            "lookbacks_sessions": [21, 63, 252], "volatility_centre_of_mass": 60,
            "correlation_window": 252, "target_volatility": 0.10, "gross_cap": 10.0,
            "rebalance": "last session of each month", "execution": "next session's close",
            "first_decision": "first month-end with 252 sessions of returns",
            "overlay": {"spy": 0.80, "bills": 0.20, "plus": "the futures P&L stream"},
            "end": END.isoformat(), "split_for_halves": SPLIT.isoformat(),
            "bootstrap": BOOTSTRAP, "prior_trials": PRIOR_TRIALS,
            "code_sha256": hashes},
        search_procedure=(
            "One primary configuration fixed in advance. Secondary rows are reported and "
            "cannot overturn it: 12-month signal only (Moskowitz, Ooi & Pedersen), weekly "
            "rebalancing, double costs, an overlay on 100% SPY, and bills alone."),
        max_configurations=3,
        datasets=["futures-proxies-yahoo-2006-2026-20 via research_gate.verify_dataset - purpose "
                  "rejection_test (historical_in_sample: may reject, cannot accept)"],
        information_boundary=(
            "Signals, volatilities and correlations at a decision use closes through that "
            "session only; the trade is at the next session's close; a session's bill return "
            "uses the previous session's yield. Yahoo recomputes adjusted closes from later "
            "dividends, which changes price levels, not day-to-day returns."),
        execution_assumptions=(
            "Trades at the next session's close, at the fund's close standing in for the "
            "future's settlement. Costs per side per market as parameters['markets'] are "
            "charged on rebalance turnover and on rolls (2 sides x |w| x rolls a year, accrued "
            "daily). Futures notional earns r - rf; equity earns bills. Positions are "
            "fractional; whole-contract rounding is not modelled. Fund fees stay in the proxies' "
            "returns."),
        primary_metric=(
            "The primary configuration's stand-alone net Sharpe ratio over the full window "
            "(annualised, excess over bills), with its stationary-bootstrap one-sided p-value "
            "for mean excess return > 0."),
        secondary_metrics=[
            "CAGR, volatility and worst drawdown: stand-alone, overlay and SPY, full window and "
            "halves", "year by year", "double costs", "12-month signal only",
            "weekly rebalancing", "overlay on 100% SPY", "P&L by asset class",
            "correlation with SPY", "gross leverage and how often the cap bound",
            "turnover and costs a year",
            "data quality (largest one-day move per fund)"],
        acceptance_criteria=(
            "G1 edge: Sharpe >= 0.30 and bootstrap p <= 0.05. G2 survives publication: mean "
            "excess return > 0 in both halves (before 2017-01-01, and from it). G3 SPY-relative: "
            "the overlay account (80% SPY, 20% bills, plus the futures P&L) has a higher CAGR "
            "than SPY over the full window and in both halves, and a shallower worst drawdown "
            "than SPY over the full window. G4 costs: at double costs, Sharpe >= 0.30 and mean "
            "excess > 0. NOT REJECTED - nominated for a forward paper test - only if G1 to G4 "
            "all hold."),
        rejection_criteria=(
            "REJECTED if G1 or G2 fails. WEAK if G1 and G2 hold but G3 or G4 fails: an edge "
            "with no SPY-relative case, or one that does not survive double costs."),
        robustness_requirements=["both halves", "double costs", "12-month-only signal",
                                 "weekly rebalancing", "by asset class", "by year"],
        complexity_penalty=(
            "A second broker for futures, 19 markets of daily data, monthly orders, contract "
            "rolls, and whole-contract sizing at about $100,000."),
        required_oos_test=(
            "A forward record in a futures broker's paper account, sized in whole micro "
            "contracts, before any real money."),
        promotion_requirements=["owner approval", "a whole-contract sizing check",
                                "a futures paper account connected through the secure key setup",
                                "a forward paper record"])
