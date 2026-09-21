"""Seal H-0015 before any capacity attribution is computed. Run once.

A READ-ONLY forensic attribution of the portfolio/capacity layer. No
strategy change, no parameter change, no cap selected, no optimisation.

TWO CORRECTIONS TO THE FRAMING, RECORDED BEFORE ANY NEW NUMBER.

(1) The two "~59%" figures in circulation are NOT comparable and do not
show two co-equal bottlenecks.

    - 59.5% is real: bucket-forensics measured status_counts on the
      FROZEN candidate set - taken 698, bucket 3,025, other 1,201,
      cash 163, totalling 5,087, which reconciles exactly to the
      breadth funnel's 5,087 survivors. 3,025/5,081 = 59.5%.
    - 59.4% is NOT the same quantity. It came from H-0014's portfolio
      conversion, computed on a LOOSER set - 39,855 sessions passing
      RSI<=35 alone at a single 10:00 snapshot, without the trend_200d,
      liquidity, ATR-ceiling or stop-positive filters - and with the
      bucket tested FIRST, so the cap figure is conditional on bucket
      survivors. It is not "59.4% of frozen candidates".

    In the frozen accounting the 3-entries/day cap lives inside the
    1,201 "other" bucket, i.e. AT MOST 23.6% of candidates, not 59.4%.
    The correlation bucket is the larger constraint by a wide margin,
    and H-0015 is registered on that corrected understanding.

(2) The bucket dimension of the decision-quality question is ALREADY
ANSWERED and was classified A (no evidence). bucket-forensics measured
marginal-vs-occupant over n=3,025 blocked/occupant pairs: the blocked
candidate beat the occupant on only 28.1% / 29.8% / 30.5% / 29.5% /
29.1% of occasions at 1/3/5/10/20 sessions, with mean differences of
-0.011% / +0.039% / +0.044% / -0.141% / -0.133% - tiny and sign-
flipping. H-0015 must NOT re-present that as a new finding, and its
novel contribution is the ENTRY-CAP dimension, the mutually exclusive
first-binding-reason accounting, and the interaction analysis.

ATTRIBUTION IS ORDER-DEPENDENT, so the order is fixed here and is the
order production actually evaluates, read from run_portfolio. It is not
chosen for convenience and may not be varied.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0015 = Hypothesis(
    statement=(
        "The portfolio/capacity layer destroys economically useful "
        "opportunity: candidates rejected by a binding portfolio constraint "
        "have forward SPY-relative returns that are materially BETTER than "
        "the candidates actually taken, and that difference is stable across "
        "chronological thirds. The hypothesis FAILS if rejected candidates "
        "are no better than accepted ones, or the difference is not stable, "
        "or it is concentrated in a few years, symbols or extreme trades. A "
        "failure establishes that the capacity layer is discarding mediocre "
        "candidates rather than good ones, and that portfolio capacity is "
        "NOT the next bottleneck."),
    rationale=(
        "The frozen funnel yields 5,087 candidates and 698 trades, so 86.3% "
        "are rejected after generation. bucket-forensics attributed 3,025 to "
        "the correlation bucket, 1,201 to other constraints, 163 to cash and "
        "698 taken. What has never been separated is the 3-entries-per-day "
        "cap, which in production is a BREAK that ends the day's evaluation "
        "entirely - candidates after the third fill are never tested against "
        "bucket or cash at all. Whether that cap discards useful opportunity "
        "is unmeasured, and H-0014's portfolio conversion raised it without "
        "answering it on the frozen candidate set."),
    rule=(
        "READ-ONLY. The frozen baseline runs unchanged and every candidate "
        "it generates is recorded with the FIRST BINDING REASON it met, in "
        "the exact order run_portfolio evaluates them. That order, fixed "
        "here: (1) name already held, in warmup, or already pending - "
        "recorded as UNAVAILABLE, not a rejection; (2) equity non-positive; "
        "(3) daily loss guard; (4) weekly loss guard; (5) max open positions "
        "12; (6) correlation bucket cap 1; (7) signal not a buy or stop "
        "invalid - recorded as NOT-A-CANDIDATE, not a portfolio rejection; "
        "(8) sizing, quantity <= 0; (9) cash, outlay > cash; (10) "
        "3-entries-per-day cap, meaning the day had already filled its three "
        "entries when this symbol's turn came in iteration order; (11) "
        "ACCEPTED. Reasons 2-6 are evaluated together by evaluate_guard, "
        "which returns all of them; the FIRST in the listed order is the one "
        "recorded. The accounting MUST reconcile exactly: accepted + every "
        "rejection reason = the candidate universe, and any residual is "
        "reported rather than absorbed."),
    parameters={
        "attribution_order": ["unavailable_held_or_pending",
                              "equity_nonpositive", "daily_loss_guard",
                              "weekly_loss_guard", "max_open_positions",
                              "correlation_bucket", "not_a_candidate_signal",
                              "sizing_zero_quantity", "cash", "entries_per_day",
                              "accepted"],
        "order_is_productions_own": "read from run_portfolio and "
                                    "evaluate_guard; NOT chosen for "
                                    "convenience and may not be varied. "
                                    "Attribution is order-dependent and a "
                                    "different order would produce different "
                                    "shares, which is precisely why it is "
                                    "fixed in advance.",
        "FORWARD_HORIZONS": [1, 3, 5, 10, 20],
        "primary_horizon": 10,
        "primary_metric": "forward SPY-relative return from the decision "
                          "session's close, the framework's existing "
                          "definition; no new benchmark is introduced",
        "decision_quality_test": "On days with MORE candidates than the cap "
                                 "allows, compare the forward SPY-relative "
                                 "return of the candidates TAKEN against "
                                 "those rejected by the entry cap, paired "
                                 "within the same session so market moves "
                                 "cancel. Same paired design for bucket "
                                 "rejections against their occupant, "
                                 "mirroring bucket-forensics so the two are "
                                 "directly comparable.",
        "counterfactuals": ["frozen capacity, as production runs",
                            "entry cap removed, ALL other frozen controls "
                            "retained - bucket cap 1, 12 positions, cash, "
                            "sizing, costs, haircut, stops unchanged",
                            "entry cap raised to 6, a single clearly defined "
                            "higher-capacity point"],
        "counterfactual_rule": "DESCRIPTIVE ATTRIBUTION ONLY. Exactly three "
                               "points, fixed here. No search over caps. The "
                               "6 is not a candidate value and will not be "
                               "recommended; it exists so the shape between "
                               "3 and unlimited is visible. Whichever "
                               "produces the highest return is IRRELEVANT to "
                               "the conclusion and may not be cited as "
                               "support for changing the cap.",
        "regime_definition": "REUSED EXACTLY from the existing regime "
                             "forensics. No new regime is defined or fitted.",
        "stability": "the standing chronological thirds, 2016-2019 / "
                     "2020-2023 / 2024-2026, and the standing 2-of-3 rule",
        "concentration_tests": ["top-1/5/10/20 trade share of any measured "
                                "difference", "top-10 symbol share",
                                "leave-one-best-year-out"],
        "already_answered_do_not_recount": "bucket marginal-vs-occupant, "
                                           "n=3,025, win 28.1-30.5%, mean "
                                           "diff sign-flipping. Classified A. "
                                           "Reported as context, never as a "
                                           "new H-0015 result.",
    },
    search_procedure=(
        "One attribution pass over the frozen baseline. Three fixed "
        "counterfactual points. Five fixed horizons with the primary fixed "
        "in advance. No cap, ranking rule, threshold or portfolio "
        "configuration is searched. No parameter is selected. If a "
        "counterfactual looks attractive that is an observation about the "
        "cost of the current constraint, not a recommendation, and the "
        "report must say so explicitly."),
    max_configurations=3,
    datasets=["decade (development)",
              "thirty_year: NOT USED. Access count stays at 13."],
    information_boundary=(
        "Candidate classification uses only information available at the "
        "decision timestamp - the same bars, guard state, cash and position "
        "counts production had at that moment. Forward returns are outcomes "
        "only and never enter any classification. The existing embargo and "
        "purge conventions are unchanged."),
    execution_assumptions=(
        "Frozen throughout: market order at the signal close, gapped stops "
        "fill at the open, 2 bps half spread + 4 bps slippage each way, "
        "whole shares, 20% per name, 2% ADV cap, 0.652% rule-exit haircut on "
        "reverted and time_exit. The counterfactuals change ONLY the entry "
        "cap and retain every other control explicitly. NOTE: a "
        "counterfactual that admits more names would face costs and "
        "participation limits this forensic does not re-derive per name, so "
        "its returns are an UPPER BOUND on what execution could deliver."),
    primary_metric=(
        "Paired within-session difference in forward SPY-relative return at "
        "10 sessions between candidates taken and candidates rejected by the "
        "entry cap, with the same statistic for bucket rejections."),
    secondary_metrics=[
        "first-binding-reason counts and shares, reconciling to the universe",
        "forward return distribution by rejection reason at 1/3/5/10/20",
        "median, mean, hit rate, SPY-relative by reason",
        "concentration: top-1/5/10/20 trade and top-10 symbol shares",
        "chronological thirds for every principal figure",
        "regime breakdown using the existing definitions",
        "co-occurrence of entry-cap, bucket and cash pressure by session",
        "three counterfactual capacity points, descriptive only",
    ],
    acceptance_criteria=(
        "The capability-gap conclusion is reported under the standing A/B/C/D "
        "definitions. "
        "(A) capacity is the binding bottleneck: entry-cap-rejected "
        "candidates are materially BETTER than those taken on a paired "
        "within-session basis, the difference is stable in at least 2 of 3 "
        "chronological thirds, and it is not concentrated in a few years, "
        "symbols or extreme trades. "
        "(B) a real difference exists but is not stable, or does not survive "
        "concentration tests, or cannot be expressed without violating a "
        "frozen control. "
        "(C) rejected candidates are no better than accepted ones - the "
        "capacity layer is discarding mediocre candidates and portfolio "
        "capacity is NOT the next bottleneck. "
        "(D) the attribution cannot be made cleanly from available data. "
        "No outcome promotes anything, changes any parameter, or selects a "
        "cap. Raising the entry cap or loosening the bucket would each "
        "require a separate registration."),
    rejection_criteria=(
        "Explicitly NOT successes: a counterfactual earning more money; "
        "rejected candidates merely having positive forward returns in "
        "absolute terms, which says nothing without the paired comparison; "
        "an effect present in one chronological third; an effect carried by "
        "a handful of trades or symbols; any difference that requires "
        "silently relaxing the bucket, cash, sizing or cost controls to "
        "appear."),
    robustness_requirements=[
        "baseline equivalence +58.5889000000% over 698 trades before any "
        "attribution",
        "accounting reconciles exactly to the candidate universe; residual "
        "reported",
        "paired within-session comparison so market-wide moves cancel",
        "all five horizons reported, primary fixed in advance",
        "chronological thirds and the 2-of-3 rule applied",
        "concentration tests on trades, symbols and years",
        "existing regime definitions reused verbatim",
        "counterfactuals retain every non-cap control explicitly",
        "the already-answered bucket marginal-vs-occupant result cited as "
        "context, never recounted as new",
        "production fingerprint da22011e...c237b unchanged",
        "H-0011, H-0012, H-0013, H-0014 all remain frozen",
        "zero reads of the thirty-year dataset",
    ],
    complexity_penalty=(
        "Two percentage points of decade total return for any economic "
        "claim, the standing constant, applied unchanged. It is not a "
        "complexity charge here - H-0015 adds no complexity - but the "
        "project's existing definition of a material economic difference."),
    required_oos_test=(
        "None available and none claimed. The decade is development data and "
        "the attribution is retrospective by construction. The thirty-year "
        "window is NOT touched. The clean forward record holds 0 sessions "
        "and is frozen until 2026-10-12. Ceiling: research_evidence."),
    promotion_requirements=[
        "H-0015 promotes nothing and changes no parameter",
        "raising the entry cap requires its own registration, a new "
        "fingerprint and a restarted forward evaluation",
        "loosening the correlation bucket requires its own registration",
        "H-0011, H-0012, H-0013 and H-0014 remain frozen",
    ],
    kind="exploratory",
    hypothesis_id="H-0015",
)


def main():
    try:
        row = register(H0015)
    except RegistrationError as error:
        print("refused: {0}".format(error))
        return 1
    p = row["payload"]
    print("registered {0}".format(p["hypothesis_id"]))
    print("  seal    {0}".format(p["seal"]))
    print("  commit  {0}".format(p["code_commit"]))
    print("  when    {0}".format(p["registered_at"]))
    print("\nchain: {0}".format(verify_chain()))
    print("declared configurations: {0}".format(declared_trials()))
    print("\nNo attribution has been computed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
