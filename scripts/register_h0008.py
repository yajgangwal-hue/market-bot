"""Seal H-0008 before any drift is measured. Run once.

EXECUTION-MODEL CALIBRATION RESEARCH, NOT EVIDENCE OF MARKET EDGE.
Nothing in H-0008 proposes to trade differently. It asks one question:
is the 0.652% rule-exit timing haircut defensible, given that it was
chosen as the worst of three point estimates from 155 exits because the
live trigger-time distribution was unknown?

The answer may be that the haircut is right, or too low. Those are
outcomes, not failures. The acceptance criteria are about statistical
defensibility and stability, NEVER about whether a different haircut
improves the backtest.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0008 = Hypothesis(
    statement=(
        "The rule-exit timing haircut of 0.652% is more conservative than "
        "the measured trigger-to-close drift distribution supports. "
        "Measured across every reconstructable rule exit in the five-minute "
        "window, the registered percentile of the ADVERSE drift distribution "
        "will fall BELOW 0.652%. This is a statement about the execution "
        "model's calibration and about nothing else: no entry, exit, sizing "
        "or ranking rule changes, and a confirmed lower haircut is not "
        "evidence of market edge."),
    rationale=(
        "portfolio.py charges the WORST of three trigger-time point "
        "estimates (10:00 ET 0.652%, 12:30 ET 0.289%, 15:00 ET 0.120%) "
        "measured on 155 real exits, and the file's own comment says the "
        "live trigger-time distribution is UNVERIFIED - three logged rule "
        "exits, all before exit-quality instrumentation existed - and "
        "instructs replacing it with the measured distribution once enough "
        "exits accrue. A worst-case point estimate standing in for a "
        "distribution is a placeholder by construction. The five-minute "
        "cache now permits the distribution to be reconstructed directly "
        "rather than waiting on live accrual."),
    rule=(
        "RECONSTRUCTION. The live bot decides on DAILY bars whose last "
        "element is TODAY'S STILL-FORMING bar, so its close is the current "
        "price; mean_reversion.should_exit orders stop, then RSI>=60 "
        "('reverted'), then the holding cap ('time'). For each rule exit the "
        "frozen baseline produces on the decade run, whose exit date lies "
        "inside the intraday window and whose symbol is in the intraday "
        "cache:\n"
        "  REVERTED: walk that session's five-minute bars forward in time. "
        "At each bar form the provisional daily series - completed daily "
        "closes through t-1, plus a provisional today-close equal to that "
        "five-minute bar's close - and compute RSI(14). The TRIGGER is the "
        "FIRST bar at which RSI>=60. Nothing after the trigger influences "
        "where the trigger is.\n"
        "  TIME_EXIT: the holding cap is a date condition with no intraday "
        "component, so it is already satisfied when the session opens. The "
        "TRIGGER is the first regular-session five-minute bar.\n"
        "DRIFT = session_close / trigger_price - 1. The position is long and "
        "is being SOLD, so a POSITIVE drift means the close was above the "
        "trigger, the live bot sold lower than the simulator assumes, and "
        "the simulator overstates by that amount. The haircut corrects "
        "exactly this quantity, so it is calibrated on the POSITIVE tail."),
    parameters={
        "current_haircut": 0.00652,
        "replacement_rule": "The replacement haircut is the Nth PERCENTILE "
                            "of the measured drift distribution. N is "
                            "registered here; the VALUE falls out of the "
                            "data and is not chosen. A percentile of the "
                            "adverse tail, not the mean, because the haircut "
                            "exists to bound a cost rather than to estimate "
                            "its centre.",
        "percentiles": {"A": 75, "B": 90, "C": 95},
        "rsi_period": 14, "rsi_exit": 60.0,
        "intraday_window": "2023-05-22 to 2026-09-15, five-minute bars, "
                           "98 symbols",
        "information_boundary": "The trigger is located by walking the "
                                "session FORWARD and halting at the first "
                                "crossing; no later bar can move it. The "
                                "drift then reads the session close, which "
                                "is AFTER the trigger - that is the "
                                "measurement itself, not an input to any "
                                "decision. Nothing computed in H-0008 may "
                                "ever become a feature.",
        "known_incompleteness": "The exit DATES come from the simulator, "
                                "which decides on completed daily closes. "
                                "The live bot can cross RSI 60 intraday on a "
                                "day that closes below 60, and would exit on "
                                "a day the simulator holds. The haircut "
                                "cannot model that at all, at any value. "
                                "H-0008 MEASURES how often it happens and "
                                "reports it as a bound on how much of the "
                                "live/simulated gap a haircut can ever "
                                "close. This is a secondary measurement and "
                                "is not part of acceptance.",
        "provenance": "GENERATED from the read-only timing decomposition of "
                      "2026-09-17, which found the exit gap is -$54,858 of "
                      "which -$55,405 is the haircut on 459 rule exits and "
                      "+$547 is stops. That decomposition varied nothing and "
                      "selected nothing - it is an identity that reconciles "
                      "to 0.000000 - so H-0008 does not inherit a "
                      "multiple-comparison cost from a parameter search. It "
                      "does inherit the ordinary cost of being the direction "
                      "chosen from among several the decomposition exposed.",
    },
    search_procedure=(
        "Exactly three percentiles, once each, on the one intraday window "
        "that exists. No fourth percentile may be added after the "
        "distribution is visible, no percentile may be moved, and the "
        "window may not be trimmed. No entry, exit, sizing, ranking or veto "
        "rule is part of H-0008."),
    max_configurations=3,
    datasets=["decade (development), for the baseline and the exit dates",
              "five-minute intraday cache 2023-05-22 to 2026-09-15, 98 "
              "symbols",
              "thirty_year: NOT USED. H-0008 does not read it at any point "
              "and its access count stays at 13."],
    information_boundary=(
        "The trigger is found by forward walk and first crossing. The drift "
        "reads the close afterwards as the measured quantity. No decision "
        "anywhere in the system consumes anything produced here."),
    execution_assumptions=(
        "Frozen production candidate, unchanged. H-0008 changes no order, "
        "no size and no rule. CostModel is applied on top of the haircut "
        "and represents a different thing; it is not re-estimated here."),
    primary_metric=(
        "The registered percentile of the trigger-to-close drift "
        "distribution, in percent, compared against the 0.652% currently "
        "charged. Strategy performance is REPORTED but is explicitly NOT an "
        "acceptance criterion, because a haircut chosen to improve the "
        "backtest is not a calibration."),
    secondary_metrics=[
        "sample size, overall and per exit reason",
        "mean drift", "median drift", "standard deviation",
        "the 5th, 25th, 75th, 90th, 95th and 99th percentiles",
        "worst single observation",
        "share of observations with ADVERSE (positive) drift",
        "drift by exit reason: reverted against time_exit",
        "drift by trigger time of day, in half-hour buckets",
        "drift by symbol, with the largest contributors named",
        "drift by calendar year",
        "drift by SPY volatility regime, expanding percentile, prior close",
        "first-half against second-half of the intraday window",
        "count of intraday RSI>=60 crossings on days the simulator did NOT "
        "exit, as the bound on what any haircut can model",
        "resulting decade performance at each registered percentile, "
        "reported and never used to accept",
    ],
    acceptance_criteria=(
        "ALL FOUR, and none of them is a performance test. "
        "(A) SAMPLE SUFFICIENCY: at least 100 reconstructable rule exits. "
        "The estimate being replaced rests on 155; a replacement resting on "
        "less is not an improvement. "
        "(B) TEMPORAL STABILITY: the registered percentile computed on the "
        "first half of the intraday window and on the second half differ by "
        "no more than 0.25 percentage points. An unstable distribution means "
        "the evidence is insufficient and the existing haircut STANDS. "
        "(C) NOT CONCENTRATED: no single symbol supplies more than 15% of "
        "observations and no single calendar year more than 50%. "
        "(D) DIRECTION: the registered percentile is strictly BELOW 0.652%. "
        "Acceptance yields research_evidence and a recorded candidate value. "
        "It does NOT change the haircut: that is a separate promotion "
        "decision with its own registration."),
    rejection_criteria=(
        "Any clause fails. Two outcomes are registered IN ADVANCE as "
        "legitimate and are not failures of the research: the measured "
        "percentile may sit AT or ABOVE 0.652%, which CONFIRMS the current "
        "haircut and is a useful result; or the distribution may prove "
        "unstable or concentrated, in which case the evidence is "
        "insufficient and the current haircut stands unchanged. If evidence "
        "is insufficient, KEEP THE EXISTING HAIRCUT. A lower haircut "
        "raises backtest return mechanically - that is arithmetic, not "
        "evidence, and it may never be cited as support."),
    robustness_requirements=[
        "equivalence: the frozen baseline reproduces +58.5889% through the "
        "same execution path before any drift is measured",
        "three percentiles form the conservatism gradient; they must be "
        "monotone in N or the distribution is not being read sensibly",
        "first half against second half of the intraday window, reported "
        "whatever it shows",
        "per-year and per-symbol concentration reported, with the largest "
        "contributors named rather than aggregated away",
        "time-of-day buckets reported, since the estimate being replaced is "
        "itself a time-of-day estimate and the two must be comparable",
        "the count of unmodellable intraday crossings reported, so the "
        "ceiling on this whole exercise is visible",
    ],
    complexity_penalty=(
        "None: a percentile of a measured distribution is strictly simpler "
        "than a hand-picked worst case. The risk here is not complexity but "
        "OPTIMISM - every clause above exists to stop a favourable number "
        "being adopted because it is favourable."),
    required_oos_test=(
        "None available and none claimed. The intraday window is 3.3 years "
        "and is the only such data that exists. The second-half stability "
        "check is a within-sample split, not a holdout, and is labelled as "
        "one. The clean forward record holds 0 sessions and is not touched. "
        "Ceiling: research_evidence."),
    promotion_requirements=[
        "H-0008 alone can promote nothing and cannot alter the haircut",
        "a passing percentile is a recorded candidate value only",
        "changing the production haircut requires its own registration, the "
        "old numbers preserved beside the new, and an explicit decision",
        "live accrual remains the preferred evidence; this is a "
        "reconstruction and is labelled as one",
    ],
    kind="confirmatory",
    hypothesis_id="H-0008",
)


def main():
    try:
        row = register(H0008)
    except RegistrationError as error:
        print("refused: {0}".format(error))
        return 1
    p = row["payload"]
    print("registered {0}".format(p["hypothesis_id"]))
    print("  seal    {0}".format(p["seal"]))
    print("  commit  {0}".format(p["code_commit"]))
    print("  when    {0}".format(p["registered_at"]))
    print("  cap     {0} configurations".format(p["max_configurations"]))
    print("\nchain: {0}".format(verify_chain()))
    print("declared configurations across all registrations: {0}".format(
        declared_trials()))
    print("\nNothing has been measured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
