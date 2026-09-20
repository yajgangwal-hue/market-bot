"""Seal H-0013 before any walk-forward or repriced result. Run once.

WHAT THIS IS. A measurement-validity experiment about the EXECUTION
YARDSTICK. No strategy, no signal, no parameter, no production change.
H-0012 showed the yardstick is materially miscategorised but could not
defend a magnitude; H-0013 asks whether a STABLE, POINT-IN-TIME model
exists, and is designed so that "no" is a first-class outcome.

BECAUSE SECTION 7 SELECTS AMONG MODELS, THE CANDIDATE SET AND THE
SELECTION RULE ARE BOTH FIXED HERE. Nothing may be added afterwards
and the rule may not be changed once errors are visible.

PRE-REGISTRATION INPUTS (measurements, not results). From 695 of 698
exits reconstructed on 5-minute RTH bars, features timestamped at the
trigger bar close:

  reverted   n=221  mean +0.6113%  95% CI [+0.3748%, +0.8556%]
  time_exit  n=238  mean -0.1109%  95% CI [-0.3898%, +0.1686%]
  stop       n=236  mean -0.2541%  95% CI [-0.5308%, +0.0234%]

TWO FACTS THAT SHAPE THE DESIGN, RECORDED BEFORE SEALING:

1. The charged 0.652% lies INSIDE the reverted 95% CI. For that
   category the incumbent constant is not statistically distinguishable
   from the measurement, and H-0013 must be able to conclude exactly
   that.
2. All 238 time exits trigger at minutes_from_open = 0 - the condition
   is true at the bell by construction - and their drift from trigger
   to the next tradable print is +0.0026% with a 95% CI of
   [-0.00694%, +0.01288%], INDISTINGUISHABLE FROM ZERO. The 0.652%
   charged against them is therefore not an execution cost at all; it
   prices roughly six and a half hours of holding.

CONDITIONING SCREEN, run before sealing on point-in-time features
only. Sign-stable across all three chronological thirds: rvol_before
(r=+0.3013), excursion_high_before (+0.0832), gap_open (+0.0761),
dist_prior_close (+0.0693). Not sign-stable and therefore ineligible:
minutes_from_open, ret_into_trigger, vwap_distance,
excursion_low_before, volume_ratio_bar, spy_ret_to_trigger,
spy_rvol_before, bars_remaining.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0013 = Hypothesis(
    statement=(
        "A SIMPLE, POINT-IN-TIME, REASON-SPECIFIC execution model estimates "
        "historical rule-exit drift with materially lower out-of-sample "
        "error than the incumbent flat 0.652%, and does so without relying "
        "on any single chronological period. The hypothesis FAILS if no "
        "candidate beats the incumbent on walk-forward error, or if the "
        "winning candidate's advantage is not stable across chronological "
        "periods. Selection is on ESTIMATION ERROR ONLY. Economic return "
        "plays no part in choosing the model and a model may not be "
        "preferred because it reprices the baseline higher."),
    rationale=(
        "H-0012 measured a +30.84-point repricing of which 94.3% came from "
        "time_exit, and could not defend a magnitude because the reverted "
        "estimate swung the answer 36.39 points across chronological "
        "thirds. That is a measurement-validity problem, not an economic "
        "one. Either the variation is explainable with information "
        "observable at the exit, in which case a defensible yardstick "
        "exists, or it is not, in which case the honest conclusion is that "
        "the historical execution estimate is too uncertain to serve as a "
        "precise profitability yardstick and accounting work should stop."),
    rule=(
        "FOUR candidate models, fixed here, no additions. "
        "(A) INCUMBENT: flat 0.652% on reverted and time_exit, 0 elsewhere. "
        "(B) H-0012 POOLED: full-sample reason-specific means, "
        "reverted +0.611300%, time_exit -0.110900%. USES FUTURE "
        "INFORMATION and is included only as a reference point, never as a "
        "winner. "
        "(C) H-0013 SIMPLE: expanding-window point-in-time reason-specific "
        "MEAN. For an exit on date T the estimate uses only same-reason "
        "exits STRICTLY BEFORE T, requiring at least 30 of them; below "
        "that threshold the incumbent 0.652% is used, so the model is "
        "always defined and never peeks. "
        "(D) H-0013 CONDITIONED: model C plus exactly ONE conditioning "
        "variable applied to `reverted` only, fitted by ordinary "
        "least squares on the same expanding point-in-time window with the "
        "same 30-observation minimum. THE CONDITIONER IS FIXED HERE AS "
        "`rvol_before` - realised 5-minute volatility strictly before the "
        "trigger bar - chosen by the pre-registered rule: among features "
        "that are point-in-time available AND sign-stable across all three "
        "chronological thirds, take the largest absolute correlation. That "
        "rule selects rvol_before at r=+0.3013 ahead of "
        "excursion_high_before, gap_open and dist_prior_close. "
        "rvol_before is undefined when fewer than three bars precede the "
        "trigger, covering 126 of 221 reverted exits; uncovered exits fall "
        "back to model C's unconditional estimate. No second conditioner "
        "may be added. "
        "`stop` exits keep zero haircut in ALL models - they pay none "
        "today and no measured evidence justifies introducing one."),
    parameters={
        "candidate_models": ["A_incumbent_flat_0.652",
                             "B_h0012_pooled_full_sample",
                             "C_h0013_pit_expanding_mean",
                             "D_h0013_pit_conditioned_rvol"],
        "conditioner": "rvol_before",
        "conditioner_selection_rule": "point-in-time available AND "
                                      "sign-stable across all three thirds, "
                                      "then largest |correlation|. Applied "
                                      "before sealing; result rvol_before "
                                      "at +0.3013.",
        "conditioner_coverage": "126 of 221 reverted exits; the rest fall "
                                "back to model C",
        "min_prior_observations": 30,
        "walk_forward": "expanding window, evaluated per calendar year "
                        "2016-2026, each year priced using only exits "
                        "strictly before 1 January of that year",
        "SELECTION_METRIC": "MEAN ABSOLUTE ERROR of predicted drift versus "
                            "realised drift, pooled over all walk-forward "
                            "predictions. Lower wins. RMSE reported as a "
                            "secondary check. ECONOMIC RETURN IS NOT A "
                            "SELECTION INPUT AND MAY NOT BE USED TO BREAK "
                            "TIES; ties go to the SIMPLER model, order "
                            "A > C > D, with B ineligible to win.",
        "B_is_ineligible": "Model B uses full-sample information and is "
                           "reported for reference only. It cannot be "
                           "selected however low its error.",
        "stability_requirement": "The winner must beat the incumbent on "
                                 "walk-forward MAE in at least 2 of the 3 "
                                 "chronological thirds, not merely in "
                                 "aggregate. A model that wins overall "
                                 "because of one period is NOT stable.",
        "recorded_before_sealing": {
            "reverted_mean": 0.006113, "reverted_ci": [0.003748, 0.008556],
            "time_exit_mean": -0.001109,
            "time_exit_ci": [-0.003898, 0.001686],
            "stop_mean": -0.002541, "stop_ci": [-0.005308, 0.000234],
            "charged_0.652_inside_reverted_CI": True,
            "time_exit_trigger_to_next_print_ci": [-0.0000694, 0.0001288],
            "time_exit_all_trigger_at_minute_zero": True},
    },
    search_procedure=(
        "Four models, each evaluated once on one fixed walk-forward "
        "schedule. No hyperparameter is tuned, no window length is "
        "searched, no second conditioner is tried, no feature is "
        "substituted after errors are seen. The economic repricing in "
        "section 8 is computed ONLY for the model the error criterion "
        "already selected, and is reported, not used to choose."),
    max_configurations=4,
    datasets=["decade (development)",
              "5-minute intraday for all 698 exit sessions plus SPY",
              "thirty_year: NOT USED. Access count stays at 13."],
    information_boundary=(
        "Every feature is computed from bars at or before the trigger bar's "
        "close, and that close is its recorded availability timestamp. The "
        "target - drift from trigger to session close - is strictly later "
        "and is never an input. Models C and D use ONLY exits dated "
        "strictly before the priced exit, so no future exit informs an "
        "earlier haircut. Model B deliberately violates this and is "
        "labelled and disqualified accordingly. The repricing itself "
        "remains a retrospective accounting exercise: no simulated trading "
        "decision consumes it."),
    execution_assumptions=(
        "Frozen production candidate throughout; only the recorded exit "
        "price changes, analytically, on the frozen trade path with "
        "entries, quantities, ordering, slots, signals and exits all held "
        "fixed. MEASURABILITY LIMIT restated: 5-minute OHLCV supports "
        "MARKET-order execution measurement only. It cannot establish "
        "bid/ask queue, displayed liquidity, queue position or limit-fill "
        "probability. H-0013 therefore touches only market-order exit "
        "categories and DOES NOT validate H-0011's limit behaviour."),
    primary_metric=(
        "Walk-forward mean absolute error of predicted versus realised "
        "trigger-to-close drift, per model, pooled and by chronological "
        "third."),
    secondary_metrics=[
        "RMSE", "bias (mean signed error)", "per-reason MAE",
        "per-year predicted vs realised drift with N",
        "economic repricing of the frozen baseline under the selected "
        "model, reported after selection and not used to select",
        "delta versus the original baseline and versus H-0012",
        "analytic impact on H-0007, H-0008, H-0009, H-0010, H-0011",
    ],
    acceptance_criteria=(
        "(A) STABLE MODEL: an eligible candidate (C or D) achieves lower "
        "pooled walk-forward MAE than the incumbent AND beats it in at "
        "least 2 of 3 chronological thirds. "
        "(B) PARTIALLY STABLE: the time_exit component is well measured and "
        "stable but the reverted component is not, so a reason-split "
        "correction is defensible for time_exit alone. "
        "(C) NO STABLE MODEL: no eligible candidate beats the incumbent "
        "stably. The registered conclusion is then that the historical "
        "execution estimate is too uncertain to serve as a precise "
        "profitability yardstick, and accounting work STOPS rather than "
        "continuing until a better number appears. "
        "(D) DATA-LIMITED: required information cannot be reconstructed. "
        "No outcome promotes anything, changes any trading rule, or alters "
        "any prior adjudication. Adopting any model as the project's "
        "standard yardstick would require its own separate registration."),
    rejection_criteria=(
        "Outcome C or D is a rejection of the stated hypothesis and is an "
        "acceptable, registered result. Explicitly NOT successes: a model "
        "that wins on pooled MAE but loses in two thirds; a model preferred "
        "because it reprices the baseline higher; a conditioner swapped in "
        "after seeing errors; any narrowing to a favourable subset of "
        "dates, symbols, sectors or exits."),
    robustness_requirements=[
        "baseline equivalence +58.5889000000% over 698 trades reproduced "
        "before any repricing",
        "walk-forward is strictly chronological with no future exit used "
        "for an earlier estimate",
        "per-reason and per-third error reported, never pooled away",
        "model B reported but disqualified from winning",
        "the 0.652%-inside-reverted-CI fact reported in the conclusion",
        "stop exits keep zero haircut in every model",
        "H-0011 assessed analytically only; not rerun, not altered",
        "queue and limit-fill limits restated, not dropped",
        "production fingerprint da22011e...c237b unchanged",
        "zero reads of the thirty-year dataset",
    ],
    complexity_penalty=(
        "Applies to model choice, not to return: ties on MAE go to the "
        "simpler model in the order A > C > D. A conditioned model must "
        "EARN its extra term with lower error, not merely match it."),
    required_oos_test=(
        "The walk-forward IS the out-of-sample test for the estimator, and "
        "it is the point of the experiment. The economic repricing remains "
        "in-sample by construction and is labelled as such. The thirty-year "
        "window is not touched; the clean forward record holds 0 sessions "
        "and is frozen until 2026-10-12. Ceiling: research_evidence."),
    promotion_requirements=[
        "H-0013 promotes nothing and changes no trading behaviour",
        "adopting any execution model as the project standard requires a "
        "separate registration",
        "changing rule_exit_timing_haircut in production requires its own "
        "registration, a new fingerprint and a restarted forward evaluation",
        "H-0011 and H-0012 both remain frozen",
    ],
    kind="confirmatory",
    hypothesis_id="H-0013",
)


def main():
    try:
        row = register(H0013)
    except RegistrationError as error:
        print("refused: {0}".format(error))
        return 1
    p = row["payload"]
    print("registered {0}".format(p["hypothesis_id"]))
    print("  seal    {0}".format(p["seal"]))
    print("  commit  {0}".format(p["code_commit"]))
    print("  when    {0}".format(p["registered_at"]))
    print("  cap     {0} candidate models".format(p["max_configurations"]))
    print("\nchain: {0}".format(verify_chain()))
    print("declared configurations across all registrations: {0}".format(
        declared_trials()))
    print("\nNo walk-forward error and no repriced result has been computed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
