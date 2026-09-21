"""Seal H-0018 before any economic bound is computed. Run once.

An ECONOMIC-LEVERAGE AUDIT of the queue uncertainty H-0017 left open.
No strategy, no backtest, no counterfactual, no MBO acquisition. The
question is whether resolving the unresolved 190 could matter enough
to justify depth-of-book data - NOT whether it would be interesting.

DOCUMENTED DEVIATION, recorded at the owner's explicit instruction.
Commit dc329bb changed src/event_aware_trader/broker.py only, to stop
the live adapter emitting a sell quantity larger than the position
held ("{:.6f}" rounds half-up; it now floors). The literal "src/
unchanged" condition is waived for that isolated change and ONLY that
change. The simulator does not import the broker adapter, the
fingerprint is unchanged, baseline equivalence passed after the fix,
the fix is not to be reverted, and it enters no H-0018 calculation as
evidence in either direction.

WHAT IS FROZEN EVIDENCE, not to be recomputed or reinterpreted:
  H-0017: 221/221 covered; 28 NO-OBSERVED-TRADE; 190 HIGH-BOUND;
  3 MARGINAL; median qualifying volume 8,260x position size; median
  spread 1.63 bps; 52% of limits at or below the bid; stable across
  thirds. HIGH-BOUND is NOT a fill and NOT a probability.
  H-0011: frozen at B. Its modelled fill rate is NOT ground truth.

THE CENTRAL DISTINCTION THIS AUDIT MUST HOLD. A large count of
uncertain observations is not the same as a large amount of
economically recoverable return. 190 unresolved exits could still
carry negligible leverage. The audit is designed so that "the
uncertainty does not matter" is a first-class outcome.

PORTFOLIO ATTRIBUTION IS EXPECTED TO BE UNIDENTIFIABLE and that is
registered in advance. H-0011 already demonstrated that altering one
exit changes later cash, buckets, slots and the trade set itself -
96.4% of quantities differed and 117 trades differed in existence. So
a trade-level bound can be computed and a portfolio-level bound very
likely cannot. Reporting that is the correct result; summing
trade-level differences and calling it portfolio alpha is forbidden.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0018 = Hypothesis(
    statement=(
        "Resolving the queue uncertainty on the 190 HIGH-BOUND reverted "
        "exits carries enough potential economic leverage to justify "
        "acquiring and reconstructing depth-of-book / MBO data. The audit "
        "FAILS - and the queue branch closes - if the defensible "
        "trade-level economic bound on those 190 is small relative to the "
        "baseline, or if the portfolio-level impact cannot be identified "
        "without rerunning a frozen experiment, or if MBO could only "
        "refine historical accounting rather than change a decision that "
        "could have been made at the time."),
    rationale=(
        "H-0017 closed the NBBO question and left exactly one thing open: "
        "whether 190 hypothetical limit orders would have filled. The "
        "instinct is to acquire MBO next. But the programme has already "
        "twice found that a frequently-occurring mechanism carried no "
        "economic value - the entry cap binds on 1.79% of sessions, and "
        "cash binds on 54.52% of candidates while rejecting the WORSE "
        "ones. Count is not leverage. Before spending a major branch on "
        "order-level data, the maximum economically relevant size of the "
        "question must be bounded."),
    rule=(
        "READ-ONLY. No simulator run, no counterfactual, no H-0011 rerun, "
        "no MBO acquisition. Only already-recorded artefacts are read: "
        "the frozen H-0011 cache and the H-0017 results. "
        "POPULATIONS, kept distinct and never merged: "
        "A = the 28 NO-OBSERVED-TRADE exits, where no qualifying "
        "transaction occurred at or above the level, so no fill was "
        "possible under the registered criterion. "
        "B = the 190 HIGH-BOUND exits, where qualifying volume existed and "
        "fill is unknowable from NBBO. "
        "C = the 3 MARGINAL exits, reported separately and never folded "
        "into either. "
        "BOUNDS, not estimates. The upper bound assumes, purely as "
        "arithmetic, that every unresolved order filled at its limit; the "
        "lower bound assumes none did and each took the baseline exit "
        "instead. Neither is a backtest and neither may be described as "
        "one. Every assumption is labelled at the point it is used."),
    parameters={
        "frozen_inputs": {
            "H-0017": {"covered": 221, "no_observed_trade": 28,
                       "high_bound": 190, "marginal": 3,
                       "median_volume_ratio": 8260,
                       "median_spread_bps": 1.63,
                       "pct_at_or_below_bid": 0.52},
            "H-0011": "frozen at B; modelled fill rate is NOT ground truth",
            "baseline": {"total_return": 0.585889, "trades": 698,
                         "sharpe": 0.5107, "max_drawdown": -0.129824,
                         "exposure": 0.442794},
        },
        "documented_deviation": {
            "commit": "dc329bb", "file": "src/event_aware_trader/broker.py",
            "reason": "live adapter emitted a sell quantity above the held "
                      "position; now floors instead of rounding half-up",
            "waived_by": "owner instruction",
            "simulator_imports_broker": False,
            "fingerprint_unchanged": True,
            "baseline_passed_after": True,
            "enters_h0018_evidence": False,
            "revert": "NO"},
        "bounds_to_compute": [
            "count and share of reverted exits and of all 698 trades",
            "aggregate notional of the unresolved 190",
            "aggregate baseline P&L of those trades",
            "upper bound trade-level difference (all fill at limit)",
            "lower bound trade-level difference (none fill)",
            "per-trade distribution of that difference",
            "the 28 proven-impossible contribution, separately"],
        "portfolio_level": "EXPECTED NOT IDENTIFIABLE. If altering an exit "
                           "changes later cash, buckets, slots or the trade "
                           "set - which H-0011 already showed it does - then "
                           "no unique portfolio attribution exists without "
                           "rerunning a frozen experiment, and the report "
                           "must say NOT IDENTIFIABLE WITHOUT "
                           "FROZEN-EXPERIMENT RERUN rather than substitute "
                           "a trade-level sum.",
        "decision_vs_accounting": "The central test. MBO earns a branch "
                                  "only if depth information observable "
                                  "BEFORE the decision could change what "
                                  "the bot does - not merely tell us "
                                  "afterwards whether an order filled.",
        "materiality_reference": "the standing 2-percentage-point complexity "
                                 "penalty, reused unchanged as the project's "
                                 "existing definition of a material economic "
                                 "difference; no new threshold invented",
        "what_is_NOT_done": ["any simulator run", "any counterfactual",
                             "any H-0011 rerun or reinterpretation",
                             "any MBO purchase, download or connection",
                             "any parameter sweep", "any exposure change",
                             "any production change"],
    },
    search_procedure=(
        "One pass over already-recorded artefacts. Bounds computed once, "
        "with the assumption behind each stated inline. No subset, period, "
        "symbol, spread bucket, fill assumption or queue model is selected "
        "after inspecting an economic result. If the evidence does not "
        "support a stable conclusion the report says INCONCLUSIVE."),
    max_configurations=1,
    datasets=["already-recorded artefacts only: docs/phase5/h0011-cache.json "
              "and docs/phase5/h0017-results.json",
              "thirty_year: NOT USED. Access count stays at 13."],
    information_boundary=(
        "No new market data is read. No forward information enters any "
        "classification - the populations were fixed by H-0017 before any "
        "economic quantity was computed here. Bounds are arithmetic over "
        "recorded outcomes and are labelled as such."),
    execution_assumptions=(
        "NONE APPLIED. The 0.652% production haircut is not used as a "
        "microstructure cost, not calibrated toward, not replaced, and not "
        "changed. HIGH-BOUND is never converted to a fill probability and "
        "traded-through price is never equated with a fill."),
    primary_metric=(
        "The defensible trade-level economic bound on the 190 unresolved "
        "exits, expressed in dollars and as a share of the baseline's "
        "decade result, with upper and lower bounds stated separately."),
    secondary_metrics=[
        "share of reverted exits and of all 698 trades",
        "aggregate notional and baseline P&L of the unresolved population",
        "per-trade distribution of the bounded difference",
        "the 28 proven-impossible contribution, separately",
        "decision-value versus accounting-value assessment",
        "MBO feasibility: coverage, fields, reconstruction, resources",
        "capability comparison against the other unresolved bottlenecks",
    ],
    acceptance_criteria=(
        "(A) MBO ECONOMICALLY JUSTIFIED: the bounded leverage is material "
        "against the standing 2-point reference AND depth information "
        "could plausibly change a pre-trade or execution decision, not "
        "merely the historical accounting. "
        "(B) MEASUREMENT VALUE EXISTS, ECONOMIC LEVERAGE NOT ESTABLISHED. "
        "(C) QUEUE UNCERTAINTY NOT STRATEGICALLY IMPORTANT: the defensible "
        "bounds are too small to be a material bottleneck. "
        "(D) MBO INFEASIBLE. "
        "No fifth category. No outcome promotes anything or authorises an "
        "acquisition; even A requires a separate registration before any "
        "data is obtained."),
    rejection_criteria=(
        "Explicitly NOT successes: a large COUNT of unresolved sessions; "
        "MBO being scientifically interesting; a bound that is large only "
        "because it assumes every order filled at its best possible price; "
        "any argument that requires treating HIGH-BOUND as a fill rate."),
    robustness_requirements=[
        "baseline equivalence +58.5889000000% / 698 verified first",
        "populations A, B and C never merged",
        "every bound labelled with the assumption that produced it",
        "portfolio-level impact reported as NOT IDENTIFIABLE if it is",
        "H-0011 and H-0013 not rerun, not reinterpreted, not re-adjudicated",
        "the broker deviation recorded and excluded from evidence",
        "fingerprint da22011e...c237b unchanged",
        "zero reads of the thirty-year dataset",
        "no MBO data acquired",
    ],
    complexity_penalty=(
        "The standing two percentage points of decade total return, reused "
        "as the reference for whether a bounded effect is material."),
    required_oos_test=(
        "Not applicable; no model is fitted and no return is claimed. The "
        "clean forward record holds 0 sessions, is frozen until 2026-10-12, "
        "and is not touched. Ceiling: research_evidence."),
    promotion_requirements=[
        "H-0018 promotes nothing and changes no parameter",
        "outcome A authorises only the DESIGN of a separate MBO study, "
        "never its acquisition or execution",
        "H-0011, H-0013, H-0015, H-0016 and H-0017 all remain frozen",
    ],
    kind="exploratory",
    hypothesis_id="H-0018",
)


def main():
    try:
        row = register(H0018)
    except RegistrationError as error:
        print("refused: {0}".format(error))
        return 1
    p = row["payload"]
    print("registered {0}".format(p["hypothesis_id"]))
    print("  seal    {0}".format(p["seal"]))
    print("  commit  {0}".format(p["code_commit"]))
    print("\nchain: {0}".format(verify_chain()))
    print("declared configurations: {0}".format(declared_trials()))
    print("\nNo economic bound computed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
