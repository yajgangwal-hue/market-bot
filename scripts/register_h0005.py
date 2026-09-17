"""Seal H-0005 before any sub-1.0R result exists. Run once.

Registered in the FAILING direction: the claim is that the breakeven
lock's effect at 1.0R is a threshold artefact and that lowering the
trigger will NOT produce a gradient. H-0002 was registered as expected
to fail and did not, which was the most informative result of Phase 6,
so a hypothesis stated in the direction its author doubts is worth more
than one stated in the direction they hope for.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.gradient import (                # noqa: E402
    INERT_BAND_POINTS, MAX_DOMINANCE_RATIO, MIN_ABS_SPEARMAN,
    MIN_MOVING_POINTS)
from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

#: Already observed under H-0003 and FROZEN. These are prior evidence.
#: H-0005 generates only the three sub-1.0R points; these three complete
#: the six-point family and are never recomputed into it.
FROZEN_PRIOR_POINTS = {1.00: +13.7125, 1.50: -1.3647, 2.00: 0.0000}

#: The direction the registration predicts IF a gradient exists: the
#: effect strengthens as the trigger falls, because a lower trigger arms
#: the lock on more trades. Spearman rho between threshold and delta must
#: therefore be NEGATIVE. Declared before the sub-1.0R points exist.
EXPECTED_DIRECTION = -1

H0005 = Hypothesis(
    statement=(
        "The breakeven lock's +13.71 points at a 1.0R trigger is a threshold "
        "artefact rather than a gradient. Triggers below 1.0R will NOT "
        "produce a monotone strengthening of the effect, and the six-point "
        "family will classify as SPIKE."),
    rationale=(
        "A mechanism should degrade smoothly as its trigger moves, not "
        "appear at one point. The three observed points are +13.71 at 1.0R, "
        "-1.36 at 1.5R and 0.00 at 2.0R: the largest move is unboundedly "
        "larger than the second-largest positive, which is the signature of "
        "a fitted point. Either a sub-1.0R threshold is also substantially "
        "positive, in which case the mechanism is real and strengthens as it "
        "arms more often, or 1.0R is where the noise happened to land. "
        "Registered in the failing direction deliberately."),
    rule=(
        "Unchanged from H-0003. When (prior_high - entry) / initial risk per "
        "share >= G, move the stop to entry x 1.0012, ratcheting upward "
        "only. prior_high EXCLUDES today's bar. Entry rule, RSI exit, "
        "holding cap, sizing, candidate selection and risk accounting are "
        "untouched."),
    parameters={
        "new_thresholds_R": [0.25, 0.50, 0.75],
        "frozen_prior_points_R": FROZEN_PRIOR_POINTS,
        "six_point_family_R": [0.25, 0.50, 0.75, 1.00, 1.50, 2.00],
        "stop_offset": "entry x 1.0012 (12 bps round trip)",
        "expected_spearman_direction": EXPECTED_DIRECTION,
        "gradient_constants": {
            "MIN_MOVING_POINTS": MIN_MOVING_POINTS,
            "MAX_DOMINANCE_RATIO": MAX_DOMINANCE_RATIO,
            "MIN_ABS_SPEARMAN": MIN_ABS_SPEARMAN,
            "INERT_BAND_POINTS": INERT_BAND_POINTS},
        "family_rule": (
            "0.25R, 0.50R and 0.75R are ONE hypothesis family. No individual "
            "configuration receives an independent promotion opportunity. "
            "Family-level classification governs, and no configuration may "
            "bypass it."),
    },
    search_procedure=(
        "Exactly three new runs, once each, decade only. The frozen prior "
        "points are reused, never recomputed into the family. No threshold "
        "may be added after the surface is visible - not 0.125, 0.375, "
        "0.625, 0.875 or 1.25 - and no alternative stop offset, regime "
        "filter or feature-derived condition may be introduced. A result "
        "suggesting another experiment requires its own registration."),
    max_configurations=3,
    datasets=["decade (development)"],
    information_boundary=(
        "Daily bars up to and including the decision bar. prior_high is "
        "captured before today's high is incorporated, so the trigger "
        "cannot see inside its own bar. The 0.652% exit-timing haircut "
        "continues to charge for intraday path uncertainty."),
    execution_assumptions=(
        "Frozen production candidate: market order at the signal close, "
        "gapped stops fill at the open, 2 bps half spread + 4 bps slippage "
        "each way, $0 commission, whole shares, 3 entries per day, 20% per "
        "name, 2% ADV participation cap, 0.652% rule-exit haircut."),
    primary_metric=("portfolio total return net of costs, decade, reported "
                    "both including and excluding 2025"),
    secondary_metrics=[
        "CAGR", "annualised volatility", "Sharpe", "Sortino", "max drawdown",
        "Calmar", "trades", "win rate", "average trade", "median trade",
        "worst loss", "profit factor", "expectancy", "turnover",
        "transaction costs", "exposure", "stop rate", "average holding days"],
    acceptance_criteria=(
        "BOTH of the following. (1) The six-point family classifies as "
        "GRADIENT: G1 at least 3 thresholds positive; G2 largest delta <= "
        "2.5x the second-largest positive delta; G3 both neighbours of the "
        "maximum positive, or the single neighbour if it is an endpoint; G4 "
        "|Spearman rho| >= 0.6; and the sign of rho is NEGATIVE, agreeing "
        "with the registered direction. (2) At least one configuration meets "
        "every standing clause: total_return_candidate > "
        "total_return_baseline; volatility_candidate <= 1.10 x "
        "volatility_baseline; abs(max_drawdown_candidate) <= 1.10 x "
        "abs(max_drawdown_baseline); positive with its single best calendar "
        "year removed; better than baseline in at least 7 of 11 calendar "
        "years; AND positive both INCLUDING and EXCLUDING 2025."),
    rejection_criteria=(
        "The family classifies as SPIKE or INERT, or no configuration meets "
        "every standing clause, or the sign of rho disagrees with the "
        "registered direction. A configuration that improves per-trade "
        "statistics while reducing portfolio total return is rejected. "
        "Acceptance yields research_evidence only; H-0005 cannot promote "
        "anything."),
    robustness_requirements=[
        "six-point family classified by the registered constants",
        "directional monotonicity: sign of rho matches the registration",
        "all five adjacent differences reported",
        "positive both including and excluding 2025",
        "leave-one-best-year-out applied by the same shared function used "
        "for every prior configuration",
        "implementation equivalence at G=1.00R before any new run",
        "zero reads of the thirty-year dataset",
    ],
    complexity_penalty=(
        "More than 2 percentage points of decade total return to justify "
        "money-path machinery. Below that the baseline is retained on "
        "simplicity grounds regardless of classification."),
    required_oos_test=(
        "None available and none consumed. The thirty-year window is "
        "CONTAMINATED ROBUSTNESS EVIDENCE with 13 prior reads, not a "
        "holdout, and H-0005 performs zero reads of it. The clean forward "
        "record holds 0 sessions. The ceiling for H-0005 is "
        "research_evidence."),
    promotion_requirements=[
        "H-0005 alone can promote nothing",
        "a separate registration, a new fingerprint and a restarted forward "
        "evaluation would be required",
        "explicit promotion naming the exact identity digest",
    ],
    kind="confirmatory",
    hypothesis_id="H-0005",
)

#: The 27-trade descriptive protocol. Strictly non-decision-making.
ANALYSIS_PROTOCOL = {
    "population": ("trades that were winners under the baseline and losers "
                   "under the G=1.00R lock"),
    "permitted_entry_time": [
        "rsi", "atr_fraction", "above_ma200_by", "drop_5", "volume_ratio",
        "sector", "market_above_ma50", "market_above_ma200",
        "market_drawdown", "market_volatility_20"],
    "permitted_at_arming": [
        "sessions_from_entry_to_arming", "r_multiple_of_prior_high_at_arming",
        "atr_fraction_at_arming"],
    "permitted_between_arming_and_stop": [
        "sessions_elapsed", "index_fell_over_that_span", "gap_on_stop_session"],
    "forbidden": [
        "realised pnl", "exit reason", "the baseline counterfactual outcome",
        "anything computed from prices after the stop fired"],
    "may_report": ["counts", "distributions", "standardised differences",
                   "descriptive summaries"],
    "may_not": ["rank features", "select features", "select thresholds",
                "derive rules", "produce p-value-based decisions",
                "alter the H-0005 verdict", "select a configuration",
                "create a trading rule"],
    "status": ("DESCRIPTIVE ONLY. Nothing observed here may enter the H-0005 "
               "verdict. Anything interesting is recorded as a future "
               "hypothesis requiring its own registration and its own data."),
}


def main():
    try:
        row = register(H0005)
    except RegistrationError as error:
        print("refused: {0}".format(error))
        return 1
    payload = row["payload"]
    print("registered {0}".format(payload["hypothesis_id"]))
    print("  seal         {0}".format(payload["seal"]))
    print("  commit       {0}".format(payload["code_commit"]))
    print("  registered   {0}".format(payload["registered_at"]))
    print("  cap          {0} configurations".format(
        payload["max_configurations"]))
    print("  direction    spearman rho expected {0}".format(EXPECTED_DIRECTION))
    print("  frozen prior {0}".format(FROZEN_PRIOR_POINTS))
    print("\nchain: {0}".format(verify_chain()))
    print("declared configurations across all registrations: {0}".format(
        declared_trials()))
    print("\nNothing has been run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
