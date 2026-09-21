"""Seal H-0019 before any opportunity-class measurement. Run once.

A CAPABILITY AUDIT of opportunity generation. No strategy is built, no
economic backtest is run, no parameter is swept, no production change.

THE GENERATOR, TRACED FROM CODE BEFORE SEALING. mean_reversion.evaluate
emits BUY only when ALL of the following hold, and STAND_ASIDE
otherwise:

  1. close >= min_price (20.0)
  2. 20-day dollar volume >= 50,000,000
  3. close > SMA(200)                    <- uptrend only
  4. RSI(14) <= 35.0                     <- oversold only
  5. ATR(14)/close <= 0.035              <- low volatility only
  6. close - 2.5*ATR > 0

There is no other action. `action = "BUY" if not reasons` - the
function cannot emit a short, cannot emit a continuation, and never
compares one symbol with another. The whole generator is a
single-symbol, daily-close, long-only oversold filter.

STRUCTURAL EXCLUSIONS, therefore, are facts about the code and not
hypotheses: momentum and continuation (rule 4), everything below its
own 200-day average (rule 3), volatility shocks (rule 5), the entire
short side (no such action exists), any cross-sectional or peer
comparison (no such input exists), any intraday behaviour (daily
closes only), and any event-driven behaviour (no event data on the
path).

WHAT THIS AUDIT MEASURES. For each structural exclusion, remove that
ONE condition and nothing else, and measure the forward SPY-relative
behaviour of the observations it was suppressing. Removing one
condition at a time is what makes the attribution clean: each probe
answers "what is THIS filter throwing away", not "does some new
strategy work".

THE PROBES ARE FIXED HERE and may not be added to, tuned, or swapped
after results are seen:

  P1 DISCARDED HALF   RSI<=35 and close <= SMA200. Same behaviour
                      class as production, opposite trend filter. Not
                      a new class - the half the rule discards.
  P2 MOMENTUM         RSI>=65 and close > SMA200. The mirror of the
                      entry condition.
  P3 VOLATILITY       RSI<=35, close > SMA200, ATR/close > 0.035.
                      Exactly the population the ATR ceiling rejects.
  P4 CROSS-SECTIONAL  Symbol's 21-day return in the bottom decile of
                      the universe THAT SESSION, an input the
                      generator has no capacity to compute.
  P5 VOLUME SHOCK     Session dollar volume >= 3x its own trailing
                      20-day mean. Volume is currently a FILTER, never
                      a signal.

All five keep every other production gate - min_price, liquidity
floor, positive stop - so only the named condition differs.

NOT TESTED HERE, deliberately: intraday and event classes. H-0014
measured intraday incremental information at about +0.006 IC and
H-0017 showed full-universe quote acquisition is infeasible; Form 4
and news were already tested and were negative. Re-probing them would
repeat closed work.

INDEPENDENCE IS REQUIRED. A probe that fires on the same
symbol-sessions as production, or whose forward returns track it, is
another expression of the same edge and is recorded as NOT genuinely
new however it performs.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0019 = Hypothesis(
    statement=(
        "The candidate generator's structural exclusions suppress at least "
        "one economically meaningful, point-in-time measurable opportunity "
        "class that is INDEPENDENT of the existing oversold-bounce edge. "
        "The audit FAILS - and opportunity generation is not the bottleneck "
        "- if every suppressed population has forward SPY-relative "
        "behaviour indistinguishable from noise, or unstable across "
        "chronological thirds, or so entangled with the existing signal "
        "that it is the same edge re-expressed."),
    rationale=(
        "Every rejected experiment in this programme has varied parameters "
        "of ONE behaviour class. The generator has never been asked whether "
        "a different class is worth looking at. Capacity is closed three "
        "ways, queue uncertainty is a measurement issue, and intraday "
        "information measured at about +0.006 IC - so the untested "
        "structural question is what the filters discard before any of "
        "that applies."),
    rule=(
        "READ-ONLY measurement on the frozen 230-symbol decade universe. "
        "No trade is simulated, no portfolio is constructed, no cost model "
        "is applied to a hypothetical strategy, and production is "
        "untouched. Each probe removes exactly ONE production condition "
        "and retains min_price 20.0, the 50M dollar-volume floor and a "
        "positive stop. Forward outcomes are measured from the decision "
        "session's close; they are OUTCOMES and never inputs."),
    parameters={
        "probes": {
            "P1_discarded_half": "RSI(14)<=35 AND close<=SMA(200)",
            "P2_momentum": "RSI(14)>=65 AND close>SMA(200)",
            "P3_volatility_excluded": "RSI<=35 AND close>SMA200 AND "
                                      "ATR/close>0.035",
            "P4_cross_sectional": "21-day return in the bottom decile of "
                                  "the universe that session",
            "P5_volume_shock": "session dollar volume >= 3x trailing 20-day "
                               "mean"},
        "production_reference": "RSI<=35 AND close>SMA200 AND ATR/close<=0.035",
        "HORIZONS": [5, 10, 20],
        "primary_horizon": 10,
        "primary_metric": "forward SPY-relative return from the decision "
                          "close; the framework's existing definition",
        "independence_tests": ["symbol-session overlap with the production "
                               "signal", "same-day overlap",
                               "forward-return correlation with the "
                               "production population",
                               "behaviour restricted to sessions where "
                               "production produced NO candidate"],
        "stability": "standing chronological thirds and the 2-of-3 rule",
        "materiality": "the standing 2-percentage-point reference, reused "
                       "unchanged; no new threshold invented",
        "not_probed_and_why": {
            "intraday": "H-0014 measured ~+0.006 IC; H-0017 showed "
                        "full-universe quote acquisition infeasible",
            "event": "Form 4 all |d|<0.2; news archive headline-only, "
                     "classified A_NO_EVIDENCE"},
        "what_is_NOT_done": ["any strategy", "any backtest", "any sweep",
                             "any ML", "any threshold tuning",
                             "any production change", "any promotion",
                             "any clean-OOS access"],
    },
    search_procedure=(
        "Five fixed probes, measured once each, on one fixed universe and "
        "three fixed horizons with the primary fixed in advance. No probe "
        "is added, removed, retuned or swapped after results are visible. "
        "No probe is selected as a winner by descriptive return; a "
        "nomination requires independence and stability as well."),
    max_configurations=5,
    datasets=["decade (development), the existing fixed 230-symbol universe",
              "thirty_year: NOT USED. Access count stays at 13."],
    information_boundary=(
        "Every probe condition is computed from daily bars up to and "
        "including the decision session's close - exactly the information "
        "production has at that moment. SMA(200), RSI(14), ATR(14), 20-day "
        "dollar volume and the 21-day return all use closed bars only. The "
        "cross-sectional decile is computed across the universe using only "
        "that session's completed bars. Forward returns start after the "
        "decision and are never inputs."),
    execution_assumptions=(
        "NONE APPLIED. This is a descriptive measurement of forward "
        "movement, not a tradable result. No fill, no spread, no haircut "
        "and no participation cap is modelled, and consequently no "
        "descriptive figure here may be called an edge or a return. "
        "Transaction-cost sensitivity is reported as a hurdle the "
        "measured movement would have to clear, not as a net result."),
    primary_metric=(
        "Forward SPY-relative return at 10 sessions for each probe "
        "population, against the production population measured the same "
        "way, reported per chronological third."),
    secondary_metrics=[
        "frequency: symbol-sessions firing, and share of the universe",
        "forward SPY-relative at 5 and 20",
        "win rate", "overlap with production signal by symbol-session and "
        "by day", "behaviour on sessions where production had no candidate",
        "chronological thirds for every figure",
        "share of movement that would survive a round-trip cost hurdle",
    ],
    acceptance_criteria=(
        "(A) MATERIAL OPPORTUNITY-GENERATION GAP: at least one probe is "
        "structurally absent from the generator, fires often enough to "
        "matter, shows forward SPY-relative behaviour that is material "
        "against the standing reference, holds in at least 2 of 3 "
        "chronological thirds, AND is independent of the production "
        "signal by the registered overlap and correlation tests. "
        "(B) CLASS EXISTS, ECONOMIC EDGE NOT ESTABLISHED. "
        "(C) OPPORTUNITY GENERATION NOT SHOWN TO BE THE BOTTLENECK. "
        "(D) DATA / TEMPORAL LIMITATION. "
        "No fifth category. Outcome A nominates exactly ONE class for a "
        "separately sealed economic experiment and authorises nothing "
        "else."),
    rejection_criteria=(
        "Explicitly NOT successes: a probe with a large descriptive "
        "forward return that overlaps the production signal; an effect in "
        "one chronological third; an effect that would not clear a "
        "realistic round-trip cost; a probe that fires so rarely it cannot "
        "matter; and choosing whichever probe has the highest descriptive "
        "return, which the registration forbids in advance."),
    robustness_requirements=[
        "baseline equivalence +58.5889000000% / 698 verified first",
        "each probe removes exactly ONE production condition",
        "production accounting semantics preserved; no population "
        "retroactively reassigned past a guard that prevented evaluation",
        "independence measured, not assumed",
        "chronological thirds and the 2-of-3 rule on every figure",
        "cost hurdle stated for any movement described as meaningful",
        "H-0011, H-0013, H-0015, H-0016, H-0017, H-0018 all frozen",
        "broker fix dc329bb untouched and excluded from evidence",
        "fingerprint da22011e...c237b unchanged",
        "zero reads of the thirty-year dataset",
    ],
    complexity_penalty=(
        "The standing two percentage points, reused as the reference for "
        "whether measured movement is material."),
    required_oos_test=(
        "The chronological thirds are the out-of-sample discipline for a "
        "descriptive audit; no model is fitted. The clean forward record "
        "holds 0 sessions, is frozen until 2026-10-12 and is not touched. "
        "Ceiling: research_evidence."),
    promotion_requirements=[
        "H-0019 promotes nothing and changes no parameter",
        "outcome A licenses the DESIGN of one separately sealed economic "
        "experiment, never its execution",
        "all prior experiments remain frozen",
    ],
    kind="exploratory",
    hypothesis_id="H-0019",
)


def main():
    try:
        row = register(H0019)
    except RegistrationError as error:
        print("refused: {0}".format(error))
        return 1
    p = row["payload"]
    print("registered {0}".format(p["hypothesis_id"]))
    print("  seal    {0}".format(p["seal"]))
    print("  commit  {0}".format(p["code_commit"]))
    print("\nchain: {0}".format(verify_chain()))
    print("declared configurations: {0}".format(declared_trials()))
    print("\nNo opportunity-class measurement performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
