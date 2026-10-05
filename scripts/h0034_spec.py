"""H-0034 and H-0035: the two other published index day-trading rules by
Zarattini & Aziz, on SPY - fixed before any outcome.

Owner, 2026-10-04: "Continue researching different things that day traders do
to make them make the most amount of money consistently a day; don't implement
anything yet, but just research." H-0033 tested the same authors' 2024 SPY
rule. These are their two earlier rules, the most-circulated public claims that
an index day trade beats buying the index:

  H-0034  5-minute opening range breakout, "Can Day Trading Really Be
          Profitable?" (first version 2023-04-24): QQQ 2016 - Feb 2023,
          +675% against +169%, Sharpe 1.12, alpha 33% a year.
  H-0035  VWAP trend trading, "Volume Weighted Average Price (VWAP): The Holy
          Grail for Day Trading Systems" (2023-11-13): QQQ 2018 - Sep 2023,
          +671% against +126%, Sharpe 2.1, worst drop 9.4%.

The papers traded QQQ; the store holds SPY. The ORB paper presents its rule as
general ("without any loss of generality"), and the VWAP paper says the rule
can be run on 5-minute candles. So this asks whether the published claims hold
for SPY, and whether they held after publication.
"""

import hashlib
from pathlib import Path

from event_aware_trader.modelgov.prereg import Hypothesis

REPO = Path(__file__).resolve().parents[1]
CODE_FILES = ["scripts/h0034_index_day_rules.py", "scripts/h0033_noise_area.py",
              "scripts/run_h0034.py", "tests/test_h0034_index_day_rules.py"]
DATASET = {"id": "spy-5min-2016-2026-quarterly-43",
           "sha256": "9803ae210c0710960b7aa8c4de12b121a51adfc471643deeac599f6d8230d2c5"}
LAST_SESSION = "2026-09-10"
WINDOWS = {
    "H-0034": {"full": ["2016-01-04", LAST_SESSION],
               "paper_window": ["2016-01-04", "2023-02-17"],
               "after_publication": ["2023-04-24", LAST_SESSION]},
    "H-0035": {"full": ["2016-01-04", LAST_SESSION],
               "paper_window": ["2018-01-02", "2023-09-28"],
               "after_publication": ["2023-11-13", LAST_SESSION]},
}
COST_PRIMARY = 0.0045   # a share, each side: the same authors' own all-in figure in their 2024 SPY
                        # paper ($0.0035 commission + $0.001 slippage); SPY's 1-cent spread alone is
                        # $0.005 a side for a marketable order
COST_PAPER = 0.0005     # the papers' own: commission only, no slippage, no spread
COST_STRESS = 0.009


def code_hashes():
    return {f: hashlib.sha256((REPO / f).read_bytes()).hexdigest() for f in CODE_FILES}


_COMMON = dict(
    search_procedure="One configuration: the paper's own rule. Nothing tuned.",
    max_configurations=1,
    datasets=["spy-5min-2016-2026-quarterly-43 (preserved)", "clean OOS: NOT USED"],
    information_boundary=(
        "A decision made on a 5-minute candle's close is filled at the next candle's open; the "
        "16:00 exit is the last candle's close. A target inside a candle fills at its level; a "
        "stop inside a candle fills one cent beyond its level; either fills at the candle's open "
        "when the candle opens beyond it; when one candle reaches both, the stop is assumed "
        "first. Nothing after a decision's candle is used for it. Sessions after 2026-09-10 are "
        "excluded."),
    robustness_requirements=["costs doubled", "calendar-year consistency", "drawdown against SPY",
                             "the paper's own costs reported beside the realistic ones"],
    required_oos_test="A registered shadow forward record of at least 60 sessions before any order.",
    promotion_requirements=["owner approval", "an intraday order path", "an intraday shorting policy",
                            "the exposed credential rotated"],
)


def _criteria(paper_window):
    acceptance = (
        "All of: (R1) the published claim, transferred to SPY on the paper's own terms - over the "
        "paper's own window " + paper_window + " at the paper's cost ($0.0005 a share), annualised "
        "return above SPY's AND Sharpe above SPY's, same sessions; (R2) after publication at the "
        "realistic cost ($0.0045 a share each side), annualised return > 0 AND Sharpe above SPY's "
        "own Sharpe over the same sessions; (R3) positive in at least 8 of the 11 calendar years "
        "2016-2026 at the realistic cost; (R4) full-window Sharpe >= 0.7 at $0.009 a share; (R5) "
        "full-window worst drawdown no deeper than SPY's. Passing earns at most PROMISING.")
    rejection = "REJECTED if R1 or R2 fails. INCONCLUSIVE if both pass but R3, R4 or R5 fails."
    return acceptance, rejection


def hypotheses(hashes=None):
    hashes = hashes or code_hashes()
    params = {"dataset": DATASET,
              "population": "SPY regular-session 5-minute bars; complete sessions only (13:00 early "
                            "closes and sessions with a missing bar are not traded)",
              "benchmark": ("SPY held close to close over the same sessions, from the strategy's first "
                            "session (price only), and SPY's own Sharpe over them"),
              "costs_per_share_each_side": {"primary": COST_PRIMARY, "paper": COST_PAPER,
                                            "stress": COST_STRESS},
              "sharpe_convention": "rf = 0, arithmetic daily mean x sqrt(252); rf 2.30% also reported",
              "capital": 100_000, "code_sha256": hashes}
    a34, r34 = _criteria("2016-01-04 to 2023-02-17")
    a35, r35 = _criteria("2018-01-02 to 2023-09-28")
    orb = Hypothesis(
        hypothesis_id="H-0034",
        statement=("The published 5-minute opening range breakout (Zarattini & Aziz 2023), run on "
                   "SPY, beats holding SPY - on the paper's own terms in its own window, and after "
                   "publication at realistic costs."),
        rationale=("The most-circulated public evidence that a simple index day trade beats buying "
                   "the index. Its rule is fully specified, so nothing has to be chosen; its claim "
                   "is stated as general. The 2026-09-07 test of the stocks-in-play variant used "
                   "230 large caps, not an index ETF."),
        rule=("First 5-minute candle up (close > open): long at the open of the second candle; "
              "down: short; open == close: no trade. Stop at the first candle's low (long) or high "
              "(short); R = |entry - stop|; target 10R; otherwise out at the 16:00 close. Shares = "
              "int(min(equity x 0.01 / R, 4 x equity / entry)). One trade a session at most."),
        parameters=dict(params, windows=WINDOWS["H-0034"],
                        paper=("Zarattini & Aziz, Can Day Trading Really Be Profitable?, SSRN 4416622, "
                               "first version 2023-04-24")),
        execution_assumptions=("Up to 4x intraday buying power, as the paper assumes (FINRA day-trading "
                               "accounts); SPY shortable intraday with no borrow fee; costs per share as "
                               "listed; the target a resting limit filled at its level; the stop a stop "
                               "order filled one cent ($0.01, SPY's tick) beyond its level, a deliberate "
                               "conservative allowance for a stop order taking the next price (on a one-cent "
                               "tick walk the candle logic with level fills matched an exact tick simulation "
                               "on 3,932 of 3,932 trades). Results with stops at their level are reported "
                               "beside."),
        primary_metric="Sharpe (rf 0) and annualised return after publication, 2023-04-24 to 2026-09-10, realistic cost.",
        secondary_metrics=["every window at all three costs: CAGR, total, volatility, Sharpe, worst drawdown, by year",
                           "trades, exits by stop / target / close", "SPY held, same sessions"],
        acceptance_criteria=a34, rejection_criteria=r34,
        complexity_penalty="An intraday order path, intraday shorting and up to 4x intraday leverage.",
        **_COMMON)
    vwap = Hypothesis(
        hypothesis_id="H-0035",
        statement=("The published VWAP trend rule (Zarattini & Aziz 2023), run on SPY 5-minute "
                   "candles, beats holding SPY - on the paper's own terms in its own window, and "
                   "after publication at realistic costs."),
        rationale=("VWAP is the most-used retail day-trading reference line, and this paper is its "
                   "most-circulated performance claim. The paper says the rule can be run on "
                   "5-minute candles, which is what the store holds."),
        rule=("VWAP = sum(typical price x volume) / sum(volume), regular session, typical = (high + "
              "low + close) / 3. After the first candle closes: long if it closed above VWAP, short "
              "if below. Then reverse whenever a candle closes on the other side of VWAP; a close "
              "exactly at VWAP changes nothing. Out at the 16:00 close. All equity, no leverage."),
        parameters=dict(params, windows=WINDOWS["H-0035"],
                        paper=("Zarattini & Aziz, Volume Weighted Average Price (VWAP): The Holy Grail "
                               "for Day Trading Systems, dated 2023-11-13; 1-minute candles in the paper")),
        execution_assumptions=("No leverage; SPY shortable intraday with no borrow fee; every reversal "
                               "pays the per-share cost on both legs."),
        primary_metric="Sharpe (rf 0) and annualised return after publication, 2023-11-13 to 2026-09-10, realistic cost.",
        secondary_metrics=["every window at all three costs: CAGR, total, volatility, Sharpe, worst drawdown, by year",
                           "trades a session", "SPY held, same sessions"],
        acceptance_criteria=a35, rejection_criteria=r35,
        complexity_penalty="An intraday order path and intraday shorting; several reversals a session.",
        **_COMMON)
    return [orb, vwap]
