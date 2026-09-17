"""Seal H-0006 before any index-parking result exists. Run once.

Step 2 and 3 of the research loop, recorded here so the ranking is
auditable. Three directions were considered after the SPY decomposition:

  A. Entry confirmation (delay entry to the first up-close after the
     signal). Plausible, but the entry-window work already measured that
     entering EARLIER, at the signal close, beat next-open by +1.3 CAGR
     points. Prior evidence points the wrong way. Not first.

  B. A minimum-ATR entry floor to cut the 47.8% stop rate in low-vol
     names. Already tested in Phase 5: rejected at the portfolio level,
     and the reason it failed is the reason everything failed - freed
     capital earned nothing.

  C. Change what idle capital earns. Every filter in Phases 5 and 6 failed
     for this one reason, and the decomposition puts the entire gap to
     the benchmark here: 44.3% average exposure in a decade the index
     tripled. Highest impact, obvious mechanism, no simulator change,
     fully registrable, decade only. First.

Registered in the direction the author DOUBTS on the risk clause: the
expectation is that return rises substantially and that the drawdown
clause is where it fails, because the parked capital inherits the index's
2020 fall until the 200-day filter releases it.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0006 = Hypothesis(
    statement=(
        "Deploying the strategy's idle capital into the index while the index "
        "closed above its 200-day average the session before, and holding "
        "cash otherwise, raises decade total return by more than the "
        "complexity penalty WITHOUT breaching the registered risk clauses. "
        "The author expects the return clause to pass and the drawdown clause "
        "to fail."),
    rationale=(
        "The frozen strategy averages 44.3% invested and returns +58.59% over "
        "the decade. The index held passively at that same weight returns "
        "+88.79% with idle cash at zero and +116.05% at the bill rate. Stock "
        "selection and timing therefore measure at -30.2 points against "
        "passive exposure, and every filter and exit tested in Phases 5 and 6 "
        "failed at the portfolio level because capital freed by rejecting a "
        "trade earned nothing. No exit rule can close a 225-point gap that is "
        "made of exposure. The 200-day filter is the strategy's OWN trend "
        "constant applied to its own idle cash; nothing is chosen."),
    rule=(
        "An overlay on the cash curve, identical in mechanism to the accepted "
        "SGOV overlay. Idle cash above the $2,000 floor and the 5% reserve "
        "earns the index's daily return on sessions where the index closed "
        "above its 200-day average THE SESSION BEFORE; otherwise it earns "
        "the cash rate for that configuration. Full one-way friction of 6 bps "
        "is charged on every dollar moved and on the whole balance whenever "
        "the trend state flips. The strategy's trades, sizes, stops and exits "
        "are untouched."),
    parameters={
        "configurations": {
            "C1 always": "idle cash in the index unconditionally - the CONTROL "
                         "isolating pure exposure from the trend filter",
            "C2 trend_cash0": "index above its 200-day the session before, "
                              "else cash at 0%",
            "C3 trend_bills": "index above its 200-day the session before, "
                              "else cash at the 3-month bill rate"},
        "trend_days": 200, "index": "SPY", "cost_one_way_bps": 6,
        "floor": 2000.0, "reserved_fraction": 0.05,
        "family_rule": (
            "C1, C2 and C3 are ONE family. C1 is a control, not a candidate: "
            "it exists so the trend filter's contribution can be separated "
            "from raw exposure. No configuration receives an independent "
            "promotion opportunity."),
        "expected_direction": (
            "return: C1 >= C2 >= C3 is NOT expected; C1 >= C2 and C3 >= C2 "
            "are (bills beat zero). drawdown: the trend filter must make C2 "
            "and C3 SHALLOWER than C1, or the mechanism is not doing what "
            "it claims."),
    },
    search_procedure=(
        "Three configurations, once each, decade only. The 200-day window is "
        "the strategy's own constant and may not be varied. No other index, "
        "no other trend length, no leverage, no partial allocation fraction "
        "may be added after the surface is visible. A result suggesting "
        "another experiment requires its own registration."),
    max_configurations=3,
    datasets=["decade (development)"],
    information_boundary=(
        "The index's close and 200-day average as of session t-1 decide "
        "session t's exposure. The overlay is applied to the baseline's "
        "recorded cash curve and cannot alter a trade."),
    execution_assumptions=(
        "Frozen production candidate for the strategy leg. Index leg: 6 bps "
        "one-way on every dollar moved, and on the entire parked balance at "
        "each trend flip. The SGOV overlay charges 2 bps; the index is "
        "charged three times that because it is not a cash equivalent."),
    primary_metric=("portfolio total return net of costs, decade, reported "
                    "both including and excluding 2025, and against SPY over "
                    "the identical window"),
    secondary_metrics=[
        "CAGR", "annualised volatility", "Sharpe", "max drawdown", "Calmar",
        "excess return vs SPY", "year-by-year vs SPY", "worst year",
        "number of trend flips", "friction charged", "share of sessions in "
        "the index"],
    acceptance_criteria=(
        "For C2 or C3 (never C1, which is a control): total_return_candidate "
        "> total_return_baseline + 2 points; volatility_candidate <= 1.10 x "
        "volatility_baseline; abs(max_drawdown_candidate) <= 1.10 x "
        "abs(max_drawdown_baseline); positive with its best year removed; "
        "better than baseline in at least 7 of 11 calendar years; positive "
        "both including and excluding 2025. FAMILY clause: "
        "abs(max_drawdown_C2) < abs(max_drawdown_C1), i.e. the trend filter "
        "must reduce drawdown against unconditional exposure. Acceptance "
        "yields research_evidence only."),
    rejection_criteria=(
        "Any clause fails. The author's stated expectation is that the "
        "drawdown clause fails for every configuration because the 200-day "
        "filter releases parked capital only after a fall has begun. If so, "
        "the finding is that the exposure gap cannot be closed inside the "
        "current risk budget - which is the answer, not a failure of the "
        "experiment. The result is recorded either way."),
    robustness_requirements=[
        "reported against SPY over the identical window, year by year",
        "positive including and excluding 2025",
        "leave-one-best-year-out by the shared function",
        "C2 drawdown shallower than C1 (mechanism check)",
        "friction and flip count reported",
        "equivalence: mode 'none' reproduces the baseline exactly first",
        "zero reads of the thirty-year dataset",
    ],
    complexity_penalty=(
        "More than 2 percentage points of decade total return. Below that "
        "the SGOV overlay stands."),
    required_oos_test=(
        "None available and none consumed. Thirty-year window: 13 reads, "
        "contaminated robustness evidence, not touched here. Clean forward "
        "record: 0 sessions. Ceiling: research_evidence."),
    promotion_requirements=[
        "H-0006 alone can promote nothing",
        "changing what live idle cash holds is a PRODUCTION change and would "
        "need its own authorisation, a new fingerprint and a restarted "
        "forward evaluation",
        "explicit promotion naming the exact configuration",
    ],
    kind="confirmatory",
    hypothesis_id="H-0006",
)


def main():
    try:
        row = register(H0006)
    except RegistrationError as error:
        print("refused: {0}".format(error))
        return 1
    p = row["payload"]
    print("registered {0}".format(p["hypothesis_id"]))
    print("  seal       {0}".format(p["seal"]))
    print("  commit     {0}".format(p["code_commit"]))
    print("  cap        {0}".format(p["max_configurations"]))
    print("\nchain: {0}".format(verify_chain()))
    print("declared configurations: {0}".format(declared_trials()))
    print("\nNothing has been run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
