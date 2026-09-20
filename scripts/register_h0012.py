"""Seal H-0012 before the repriced baseline is computed. Run once.

WHAT THIS IS. A yardstick audit, not a strategy. No decision rule is
touched, no parameter is optimised, no signal is added. The only thing
that changes is the PRICE at which two existing exit categories are
recorded, and the only question is whether the project's historical
economic conclusions were distorted by the old accounting.

PROVENANCE OF THE INPUTS, STATED FIRST.

The 2026-09-20 intraday measurement reconstructed 459 of 459 rule
exits at 100% coverage from 5-minute bars, RTH-filtered, reconciled to
the daily set with zero unexplained mismatches. It measured, for
A = (session close - intraday trigger price) / trigger price:

    reverted    n=221  mean +0.6113%  median +0.4560%  sd 1.8112%
    time_exit   n=238  mean -0.1109%  median +0.0967%  sd 2.1344%

Those measurements are PRE-REGISTRATION INPUTS - they are the
instrument being calibrated, not the result being tested. The RESULT
of H-0012 is the repriced baseline and the historical impact audit,
and neither has been computed at sealing time.

THE KNOWN INSTABILITY, DISCLOSED BEFORE SEALING AND NOT AVERAGED AWAY.
Across chronological thirds the reverted drift runs +0.8064%,
+0.9590%, +0.0335% - the final third collapses to roughly zero while
the full-sample mean is +0.6113%. time_exit is far steadier at
-0.0068%, -0.2075%, -0.0822%. Both keep their sign, but a single
historical mean for `reverted` is carried by the first two thirds.
This is exactly the condition that can produce verdict C, and it is
registered here so that outcome cannot be presented as a surprise.

WHAT THIS EXPERIMENT CANNOT DO. It cannot show the strategy is
better, that anyone could capture the trigger-to-close movement, that
a new exit rule is profitable, or that intraday trading works. It can
only establish whether the historical emulator's execution accounting
was conservative, accurate, or materially distorted.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0012 = Hypothesis(
    statement=(
        "The frozen baseline's historical economics are MATERIALLY distorted "
        "by the flat 0.652% rule-exit haircut, and a reason-specific haircut "
        "derived from the measured 459-exit trigger-to-close distribution is "
        "a more defensible research yardstick. Material means the repriced "
        "decade total return differs from the registered +58.5889% by MORE "
        "than 2 percentage points - the project's standing complexity "
        "penalty, used unchanged in H-0005, H-0009, H-0010 and H-0011, and "
        "NOT a threshold invented for this experiment. The hypothesis fails "
        "if the repriced baseline lands within that band, in which case the "
        "flat constant is adequate for historical strategy comparison and is "
        "preserved."),
    rationale=(
        "The exit gap is -$54,858 against a realised +$57,560, and its "
        "mean_exit_off_close of -0.7116% matches the charged 0.652% plus "
        "0.06% one-way slippage to four decimals - so the largest single "
        "line in the P&L is an accounting assumption, not observed market "
        "movement. The intraday reconstruction showed the constant is nearly "
        "right for `reverted` (+0.6113% measured vs 0.652% charged) and has "
        "the WRONG SIGN for `time_exit` (-0.1109% measured). It also showed "
        "the constant conflates two unrelated things: execution drift from "
        "trigger to the next tradable print is -0.0013% with sd 0.0688%, "
        "essentially zero, while the 0.652% is really the price difference "
        "between acting at the trigger and waiting for the close."),
    rule=(
        "NOTHING in the decision path changes. Entry rule, stop, holding "
        "cap, sizing, bucket cap, position cap, ordering, universe and costs "
        "are all identical to the frozen baseline, and no production file is "
        "modified. Only the recorded exit PRICE of two categories changes, "
        "computed analytically from the frozen baseline's own trade log. "
        "MAPPING, fixed here: the simulator records exit_raw = close x "
        "(1 - H). The measured trigger price is close / (1 + A). Setting "
        "those equal gives H' = A / (1 + A). With the full-sample means "
        "A_reverted = +0.611300% and A_time_exit = -0.110900%: "
        "H'_reverted = +0.607586% and H'_time_exit = -0.111023%, the latter "
        "being a CREDIT. Each affected trade is repriced by the exact "
        "multiplier (1 - H') / (1 - H) applied to its recorded exit_price: "
        "1.00044706 for reverted and 1.00768031 for time_exit. Net P&L is "
        "recomputed as (exit_price' - entry_price) x quantity, which is an "
        "EXACT identity in this trade log - verified at max absolute error "
        "0.0000000000 across all 698 trades before sealing. `stop` exits and "
        "every other category are UNCHANGED: stops pay no haircut, their "
        "measured exit gap is +$547, and no measured evidence justifies "
        "touching them. The full-sample average is NOT used in place of "
        "reason-specific behaviour, and neither population is extrapolated "
        "onto the other."),
    parameters={
        "parameters_moved": ["recorded exit_price of `reverted` and "
                             "`time_exit` trades, analytically"],
        "A_reverted_full_sample": 0.006113,
        "A_time_exit_full_sample": -0.001109,
        "H_prime_reverted": 0.00607586,
        "H_prime_time_exit": -0.00111023,
        "multiplier_reverted": 1.00044706,
        "multiplier_time_exit": 1.00768031,
        "baseline_haircut_unchanged_in_src": 0.00652,
        "estimator": "MEAN, not median. P&L aggregates additively in price, "
                     "so the mean is the unbiased estimator for a sum. The "
                     "median is reported alongside but is NOT used, and this "
                     "choice is fixed before any result is seen.",
        "stop_exits": "UNCHANGED. No haircut is charged on stops today and "
                      "none is introduced.",
        "path_is_held_fixed": "DELIBERATE AND LIMITING. The reprice is "
                              "analytic on the frozen trade log, so entry "
                              "dates, quantities and the set of trades are "
                              "identical by construction. This ISOLATES the "
                              "accounting effect from the portfolio-path "
                              "effect, which is the right decomposition for "
                              "a yardstick audit and is also what keeps "
                              "production src/ untouched. It does NOT "
                              "measure how sizing and slot competition would "
                              "respond to different equity - the H-0011 "
                              "validation gate showed that response is real "
                              "(quantity differed on 96.4% of trades) and it "
                              "is explicitly OUT OF SCOPE here.",
        "chronological_instability_disclosed": {
            "reverted_thirds": [0.008064, 0.009590, 0.000335],
            "time_exit_thirds": [-0.000068, -0.002075, -0.000822],
            "note": "reverted's final third collapses to ~0 while the "
                    "full-sample mean is +0.6113%. Registered in advance as "
                    "a candidate reason for verdict C."},
        "point_in_time": {
            "classification": "HISTORICAL DESCRIPTIVE ESTIMATE, not a "
                              "point-in-time executable model.",
            "why_permitted": "This is a retrospective yardstick measurement, "
                             "not a trading signal. No simulated trader acts "
                             "on it.",
            "pit_cross_check": "An expanding-window estimate using only "
                               "prior same-reason exits, minimum 20 "
                               "observations, converges to +0.6144% "
                               "(reverted) and -0.1121% (time_exit) against "
                               "full-sample +0.6113% and -0.1109%. Reported "
                               "so the gap between descriptive and "
                               "executable estimation is visible rather "
                               "than assumed away."},
    },
    search_procedure=(
        "ONE repricing model, computed once. No variant, no sensitivity "
        "sweep that could become a selection, no alternative estimator "
        "chosen after seeing the result. The historical impact audit "
        "inspects prior experiments but DOES NOT rerun them and DOES NOT "
        "alter any adjudication; an experiment whose verdict would change is "
        "flagged for separately governed review, not reopened here."),
    max_configurations=1,
    datasets=["decade (development)",
              "5-minute intraday, 459 rule-exit sessions, fixed universe",
              "thirty_year: NOT USED. Access count stays at 13."],
    information_boundary=(
        "The repricing is a retrospective descriptive measurement and is "
        "labelled as such. The intraday reconstruction itself used only bars "
        "at or before each trigger to detect the trigger, and prior daily "
        "closes strictly before the exit session. No simulated decision is "
        "made using the repricing, so no look-ahead can enter a trading "
        "rule. The full-sample mean IS future information relative to an "
        "early-decade trade, which is precisely why this is registered as a "
        "yardstick audit and NOT as a point-in-time executable model, and "
        "why the expanding-window cross-check is reported."),
    execution_assumptions=(
        "Frozen production candidate throughout. The ONLY change is the "
        "recorded exit price of reverted and time_exit trades. "
        "MEASURABILITY LIMIT, stated explicitly: 5-minute OHLCV supports "
        "MARKET-order execution measurement, because a market order crosses "
        "the spread and queue position is irrelevant. It does NOT support "
        "limit-order fill probability, depth, quoted spread or queue "
        "position. H-0012 therefore touches ONLY exit categories whose "
        "mechanics are measurable from the available data. H-0011's "
        "limit-exit fragility is NOT addressed and remains unresolved."),
    primary_metric=(
        "Repriced decade total return versus the registered +58.5889%, with "
        "the difference decomposed into the reverted contribution and the "
        "time_exit contribution separately."),
    secondary_metrics=[
        "trade count", "Sharpe", "max drawdown", "exposure",
        "transaction costs", "win rate", "profit factor", "expectancy",
        "equity curve", "per-trade results",
        "per-reason dollar contribution to the repricing delta",
        "year-by-year repriced return",
        "for each affected prior experiment: original result, repriced "
        "result, original delta vs baseline, repriced delta vs repriced "
        "baseline, whether ordering changes, whether the verdict would "
        "change",
    ],
    acceptance_criteria=(
        "Two questions are answered separately and must not be merged. "
        "(1) LEVEL: does the repriced baseline differ from +58.5889% by more "
        "than the standing 2-point complexity penalty? "
        "(2) RANKING: does the repricing change the relative ordering or the "
        "pass/fail outcome of any prior experiment? "
        "A yes to (2) is the more serious finding even if (1) is no, because "
        "a yardstick that preserves levels but reorders conclusions has been "
        "distorting comparisons. "
        "STABILITY GATE, registered in advance: if the reason-specific mean "
        "is not stable enough to serve as a single historical constant - "
        "judged by the chronological thirds already disclosed above, where "
        "reverted runs +0.8064%, +0.9590%, +0.0335% - the verdict is C "
        "(measurable but unstable) EVEN IF the level test passes. A large "
        "repricing driven by an estimate that is itself unstable is not a "
        "better yardstick. "
        "Acceptance yields research_evidence about the MEASURING "
        "INSTRUMENT. It promotes nothing, changes no trading rule, and does "
        "not license adopting the new haircut in production or in future "
        "experiments without a separate registration."),
    rejection_criteria=(
        "The repriced baseline lands within 2 points of +58.5889% AND no "
        "prior experiment's ordering or outcome changes. In that case the "
        "flat 0.652% is adequate for historical comparison and is preserved "
        "unchanged, which is a genuine and useful result: it would mean 40 "
        "experiments of accumulated conclusions do not need restating. "
        "Explicitly NOT successes: a large level change that is entirely "
        "time_exit while reverted is confirmed accurate would show the "
        "constant was miscategorised rather than wrong in magnitude, and "
        "must be reported that way; and any result that depends on the "
        "unstable reverted third-three estimate must be reported as such."),
    robustness_requirements=[
        "baseline equivalence: +58.5889000000% over 698 trades reproduced "
        "before any repricing is computed",
        "the net_pnl identity (exit_price - entry_price) x qty verified "
        "exact on all 698 trades - confirmed at max error 0.0 before sealing",
        "reason-specific distributions reported with count, mean, median, "
        "sd, p10, p25, p75, p90 and worst decile",
        "chronological thirds reported for each reason, never averaged away",
        "expanding-window point-in-time estimate reported alongside the "
        "full-sample descriptive estimate",
        "per-reason decomposition of the repricing delta",
        "historical impact audit covering H-0002, H-0003, H-0005, H-0007, "
        "H-0008, H-0009 and H-0011, restricted to those that actually depend "
        "on the affected exit accounting",
        "H-0011 assessed ANALYTICALLY ONLY - it is not rerun and not altered",
        "queue and limit-fill limitations restated, not silently dropped",
        "production fingerprint da22011e...c237b unchanged throughout",
        "zero reads of the thirty-year dataset",
    ],
    complexity_penalty=(
        "Two percentage points of decade total return, the standing "
        "constant. Applied to the LEVEL question only. It is not a "
        "complexity charge in the usual sense here, because the experiment "
        "adds no complexity to the strategy - it is reused unchanged as the "
        "project's existing definition of a material economic difference, "
        "rather than inventing a new threshold after seeing the result."),
    required_oos_test=(
        "None available and none claimed. The decade is development data and "
        "the intraday measurement was taken on the same window, so the "
        "repricing is in-sample by construction - unavoidable for a "
        "retrospective yardstick audit and disclosed rather than corrected. "
        "The thirty-year window is NOT touched. The clean forward record "
        "holds 0 sessions and is frozen until 2026-10-12. Ceiling: "
        "research_evidence."),
    promotion_requirements=[
        "H-0012 alone can promote nothing and changes no trading behaviour",
        "adopting the reason-specific haircut as the project's standard "
        "yardstick requires its own registration",
        "changing rule_exit_timing_haircut in production requires a separate "
        "registration, a new strategy fingerprint and a restarted forward "
        "evaluation",
        "any prior experiment whose verdict would change is flagged for "
        "separately governed review and is NOT reopened by this experiment",
        "the 14.2806% drawdown ceiling applies unchanged to any later "
        "promotion",
    ],
    kind="confirmatory",
    hypothesis_id="H-0012",
)


def main():
    try:
        row = register(H0012)
    except RegistrationError as error:
        print("refused: {0}".format(error))
        return 1
    p = row["payload"]
    print("registered {0}".format(p["hypothesis_id"]))
    print("  seal    {0}".format(p["seal"]))
    print("  commit  {0}".format(p["code_commit"]))
    print("  when    {0}".format(p["registered_at"]))
    print("  cap     {0} configuration".format(p["max_configurations"]))
    print("\nchain: {0}".format(verify_chain()))
    print("declared configurations across all registrations: {0}".format(
        declared_trials()))
    print("\nNo repriced result has been computed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
