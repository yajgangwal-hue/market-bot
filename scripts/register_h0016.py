"""Seal H-0016 before any cash-capacity economics. Run once.

READ-ONLY capacity audit. No parameter changed, no cap swept, no
production behaviour altered.

CORRECTION TO A NUMBER THE BRIEF SUPPLIED AS FROZEN, MADE BEFORE ANY
ECONOMIC CALCULATION.

The brief carries "cash-denied: 841" and "841/1,539 = 54.65%" from
H-0015. H-0015 obtained 841 as a RESIDUAL - passed guard, valid signal,
sizing > 0, not taken - and that inference was unsound, because between
position_size and the cash test production has three further exits:
the 2% ADV participation cap re-zeroing quantity, `fill <= stop_ref`,
and only then `outlay > cash`.

Production already counts the cash rejection exactly, in
report.rejected_for_capacity, so it never needed inferring. Measured on
an instrumented run that reproduced the baseline to ten decimals:

    report.rejected_for_capacity            839
    participation cap cut to zero             0
    position_size returned <= 0               0
    residual (the `fill <= stop_ref` exit)     2

So the correct figures are 839 cash-denied of 1,539 production-
evaluated candidates = 54.52%, not 841 / 54.65%. The error is small and
the brief's premise survives it, but H-0016 is registered on the
directly counted number rather than the inferred one, and the two
strays are recorded rather than absorbed.

A second measured fact, registered because it bears on interpretation:
the 2% ADV participation cap NEVER binds - 0 of 1,539 calls cut any
quantity. It is not a competing constraint in this population.

THE THREE FINDINGS THAT MUST NOT BE COLLAPSED, per the brief:
  A cash is frequently binding      - already established, 839/1,539
  B cash-denied candidates hold value - forward outcomes, tested here
  C removing cash would raise return  - needs a valid counterfactual
A does not prove B; B does not prove C.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0016 = Hypothesis(
    statement=(
        "The cash/notional constraint suppresses economically meaningful "
        "opportunity: among candidates the frozen production sequence "
        "actually evaluates, those rejected by cash have forward "
        "SPY-relative returns materially better than noise AND not worse "
        "than the candidates accepted, with that pattern stable across "
        "chronological thirds. The hypothesis FAILS if cash-denied "
        "candidates carry no meaningful forward opportunity, or the "
        "opportunity vanishes SPY-relative, or it is unstable across "
        "thirds, or it is concentrated in a few symbols, sessions or "
        "trades. A failure establishes that cash binds MECHANICALLY "
        "without suppressing value, and closes cash as a capacity "
        "bottleneck."),
    rationale=(
        "H-0015 stopped before economics but established, under "
        "production's own ordering, that of 1,539 candidates reaching the "
        "signal, 698 are accepted and the rest are overwhelmingly rejected "
        "for want of cash - now directly counted at 839. The entry cap "
        "binds on only 48 of 2,684 sessions. Cash is therefore the "
        "dominant mechanical rejection in the frozen system, and whether "
        "it costs anything is unmeasured. The mechanism is structural: "
        "max_notional_fraction 0.20 across up to 12 positions can commit "
        "240% of equity while cash is 100%, so cash binds well before the "
        "position cap does."),
    rule=(
        "READ-ONLY. The frozen baseline runs unchanged; production "
        "functions may be WRAPPED to record but never altered, and "
        "baseline equivalence at +58.5889000000% over 698 trades is "
        "asserted before anything is attributed. POPULATIONS ARE KEPT "
        "SEPARATE AND LABELLED: "
        "P = PRODUCTION-EVALUATED, the 1,539 symbol-sessions whose signal "
        "the frozen sequence actually evaluated. Cash rejection is a real "
        "production observation only within P. Guard-denied symbols are "
        "NEVER added to P - production never determined their candidacy. "
        "Q = COUNTERFACTUAL SIGNAL-FIRST, constructed only if needed and "
        "labelled COUNTERFACTUAL - NOT PRODUCTION ORDER in every table it "
        "appears in. Q's cash rate may never be described as production's. "
        "Nothing in the decision path changes: same universe, signals, "
        "timestamps, candidate ordering, stops, sizing contract, bucket, "
        "12-position cap, 3-entry cap, holding period, execution "
        "assumptions and costs."),
    parameters={
        "P_total": 1539, "P_accepted": 698, "P_cash_denied": 839,
        "P_fill_le_stop": 2,
        "cash_rate_in_P": 0.5452,
        "counter_source": "report.rejected_for_capacity, production's own, "
                          "not inferred",
        "corrected_from": "H-0015's residual estimate of 841 / 54.65%",
        "participation_cap_binds": 0,
        "HORIZONS": [1, 5, 10, 20],
        "primary_horizon": 10,
        "primary_metric": "forward SPY-relative return from the decision "
                          "session's close - the framework's existing "
                          "definition. No new benchmark.",
        "CONSTRAINT_INTENSITY_BINS": "requested_notional / available_cash, "
                                     "bins FIXED HERE and not to be revised: "
                                     "(1.0,1.25], (1.25,1.5], (1.5,2.0], "
                                     "(2.0,3.0], (3.0,inf). A ratio at or "
                                     "below 1.0 cannot be a cash rejection "
                                     "and its presence would indicate a "
                                     "measurement fault, to be reported.",
        "counterfactual_rule": "A cash-removal counterfactual is permitted "
                               "ONLY if it changes no candidate generation "
                               "and no decision ordering. It is expected to "
                               "be AMBIGUOUS, because admitting a rejected "
                               "candidate consumes cash, occupies a bucket "
                               "and a position slot, and so alters the state "
                               "every later decision sees. If that ambiguity "
                               "is present it MUST be reported as ambiguity "
                               "and the counterfactual NOT run. Manufacturing "
                               "attribution is forbidden.",
        "stability": "standing chronological thirds 2016-2019 / 2020-2023 / "
                     "2024-2026 and the standing 2-of-3 rule",
        "concentration": ["symbols", "sessions", "top-10 by rejected "
                          "notional", "years", "individual trades"],
        "what_is_NOT_varied": ["max_notional_fraction", "cash reserve",
                               "risk_per_trade", "conviction multiplier",
                               "candidate ordering", "allocation ranking",
                               "bucket cap", "max positions",
                               "max_entries_per_day", "any threshold"],
    },
    search_procedure=(
        "One instrumented pass over the frozen baseline. Fixed intensity "
        "bins. Four fixed horizons with the primary fixed in advance. At "
        "most one counterfactual, and only if it is unambiguous. No cap, "
        "reserve, size or ordering is swept. No parameter is selected."),
    max_configurations=2,
    datasets=["decade (development)",
              "thirty_year: NOT USED. Access count stays at 13."],
    information_boundary=(
        "Every recorded quantity - requested notional, available cash, "
        "constraint ratio, planned risk, signal strength - is the value "
        "production held at that decision timestamp. Forward returns are "
        "outcomes only and never enter any classification or binning."),
    execution_assumptions=(
        "Frozen and unchanged: market order at the signal close, gapped "
        "stops fill at the open, 2 bps half spread + 4 bps slippage each "
        "way, whole shares, 20% per name, 2% ADV cap, 0.652% rule-exit "
        "haircut. NOTE the ADV cap is measured at 0 binding occurrences in "
        "P, so it does not compete with cash in this population. No new "
        "execution model is introduced; a forward return measured here is "
        "PRE-EXECUTION evidence and may not be called a net edge."),
    primary_metric=(
        "Forward SPY-relative return at 10 sessions for the 839 cash-denied "
        "candidates, against the 698 accepted, described rather than ranked."),
    secondary_metrics=[
        "forward and SPY-relative return at 1, 5, 20",
        "win rate, MFE, MAE for both groups",
        "distribution by the fixed constraint-intensity bins",
        "requested vs allowed quantity and notional",
        "what consumed the cash: existing positions, earlier accepted "
        "entries this session, same-session competition",
        "same-session accepted vs cash-denied counts and cash trajectory",
        "concentration by symbol, session, year, top-10 rejected notional",
        "chronological thirds for every principal figure",
    ],
    acceptance_criteria=(
        "(A) MATERIAL CASH CAPACITY BOTTLENECK: cash binds frequently AND "
        "cash-denied candidates show forward SPY-relative opportunity that "
        "is stable in at least 2 of 3 chronological thirds and survives the "
        "concentration checks. "
        "(B) CASH BINDS, ECONOMIC VALUE UNCLEAR: binding is demonstrated but "
        "the rejected opportunity is weak, unstable, or not distinguishable "
        "from noise. "
        "(C) CASH CONSTRAINT NOT ECONOMICALLY IMPORTANT: binds mechanically "
        "with little evidence it suppresses value. "
        "(D) ATTRIBUTION NOT IDENTIFIABLE. "
        "No fifth category. No outcome promotes anything or changes a "
        "parameter. Even outcome A licenses only the DESIGN of a separate "
        "sealed experiment, never its execution."),
    rejection_criteria=(
        "Explicitly NOT successes: cash-denied candidates merely having "
        "positive raw forward returns, which says nothing without the "
        "SPY-relative comparison; an effect in one chronological third; an "
        "effect carried by a few symbols or sessions; a counterfactual "
        "earning more money, which the registration declares irrelevant in "
        "advance; and any finding that requires relaxing a non-cash control "
        "to appear."),
    robustness_requirements=[
        "baseline equivalence +58.5889000000% / 698 before any attribution",
        "P and Q never mixed; Q labelled COUNTERFACTUAL in every appearance",
        "guard-denied symbols never added to P",
        "cash count taken from report.rejected_for_capacity, not inferred",
        "the 2 `fill <= stop_ref` strays reported, not absorbed",
        "intensity bins fixed before results and not revised",
        "all four horizons reported, primary fixed in advance",
        "chronological thirds and the 2-of-3 rule",
        "concentration by symbol, session, year and trade",
        "counterfactual run ONLY if unambiguous; otherwise the ambiguity is "
        "the reported result",
        "A / B / C kept distinct: binding, opportunity, realised value",
        "production fingerprint da22011e...c237b unchanged",
        "H-0011 through H-0015 all remain frozen; H-0015's stop report is "
        "not amended and its stopped analysis is not rerun",
        "zero reads of the thirty-year dataset",
    ],
    complexity_penalty=(
        "Two percentage points of decade total return for any economic "
        "claim, the standing constant, applied unchanged."),
    required_oos_test=(
        "None available and none claimed. The decade is development data "
        "and this attribution is retrospective by construction. The "
        "thirty-year window is NOT touched. The clean forward record holds "
        "0 sessions and is frozen until 2026-10-12. Ceiling: "
        "research_evidence."),
    promotion_requirements=[
        "H-0016 promotes nothing and changes no parameter",
        "raising deployable capital, changing max_notional_fraction or "
        "adding leverage would each require its own registration, a new "
        "fingerprint and a restarted forward evaluation",
        "H-0011 through H-0015 remain frozen",
    ],
    kind="exploratory",
    hypothesis_id="H-0016",
)


def main():
    try:
        row = register(H0016)
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
    print("\nNo cash-capacity economics computed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
