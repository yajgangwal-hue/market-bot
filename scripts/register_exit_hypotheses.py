"""Register the exit hypotheses BEFORE any of them is run.

Run once. Re-running refuses, because a registration that can be rewritten
is not a registration. The seals printed here are the tokens a later
confirmatory run must present.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

COMMON = dict(
    datasets=["decade (development)", "thirty_year (robustness, overlapping)"],
    information_boundary=(
        "Daily bars up to and including the decision bar. The exit decision "
        "is taken on the session close that triggers it; no intraday path "
        "within the exit session is used, and the 0.652% exit-timing "
        "haircut already charges for that uncertainty."),
    execution_assumptions=(
        "Frozen: market order at the signal close, gapped stops fill at the "
        "open, 2bps half spread + 4bps slippage each way, whole shares, "
        "3 entries per day, 20% per name, 0.652% rule-exit haircut."),
    primary_metric=("portfolio total return net of costs, with parked cash "
                    "applied to BOTH arms"),
    secondary_metrics=["CAGR", "annualised volatility", "Sharpe", "Sortino",
                       "max drawdown", "Calmar", "profit factor", "win rate",
                       "average win", "average loss", "average holding days",
                       "turnover", "modelled transaction costs", "exposure",
                       "captured", "gave_back", "stop rate"],
    acceptance_criteria=(
        "Beats the frozen baseline on the PRIMARY metric on the decade AND "
        "does not raise annualised volatility or maximum drawdown by more "
        "than 10 percent; AND is monotone or flat across adjacent parameter "
        "values; AND remains positive after removing its single best "
        "calendar year; AND beats the baseline in at least 7 of 11 calendar "
        "years; AND holds sign on the thirty-year window."),
    rejection_criteria=(
        "Fails any acceptance clause. A variant that improves per-trade "
        "statistics while reducing portfolio total return is REJECTED - "
        "Phase 5 produced four of exactly that shape."),
    robustness_requirements=[
        "adjacent-parameter monotonicity",
        "leave-one-best-year-out stays positive",
        "at least 7 of 11 calendar years better",
        "sign holds on the thirty-year window",
        "parked cash applied to both arms"],
    complexity_penalty=(
        "A variant must beat the baseline by more than 2 percentage points "
        "of decade total return to justify added money-path machinery; "
        "below that the baseline is retained on simplicity grounds."),
    required_oos_test=(
        "None available. Both windows are contaminated for the current "
        "candidate and the clean forward record holds 0 sessions. The "
        "ceiling for any result here is research_evidence."),
    promotion_requirements=[
        "survives every robustness requirement",
        "survives an untouched test period that does not yet exist",
        "no unresolved leakage",
        "realistic costs and execution",
        "parameter stability demonstrated",
        "new fingerprint and a restarted forward evaluation"],
    kind="confirmatory",
)

HYPOTHESES = [
    Hypothesis(
        statement=("Trades that end at the 20-session holding cap give back "
                   "most of the favourable excursion they reached, so a "
                   "trailing stop that arms only after a threshold gain "
                   "converts part of that giveback into realised return "
                   "without cutting winners short."),
        rationale=("Measured on the frozen baseline: time exits capture "
                   "-0.10 of the available move and give back 4.18 percent, "
                   "and stopped trades give back 8.47 percent. Those two "
                   "buckets hold 477 of 698 decade trades. A trail that arms "
                   "late cannot touch a trade that never ran up."),
        rule=("After unrealised gain reaches A times initial risk per share, "
              "raise the stop to the running high minus B times ATR(14), "
              "ratcheting only upward. Entry, RSI exit and holding cap "
              "unchanged."),
        parameters={"arm_at_R": [1.0, 1.5, 2.0], "atr_multiple": [2.0, 3.0]},
        search_procedure=("Full grid of 6, evaluated once. No re-cutting and "
                          "no value added after seeing the surface."),
        max_configurations=6, **COMMON),

    Hypothesis(
        statement=("A fixed multiple-of-risk take profit does NOT improve "
                   "portfolio wealth, because the strategy's return comes "
                   "from a right tail that a fixed target truncates."),
        rationale=("Registered as a hypothesis expected to FAIL, so the "
                   "result is informative either way and the owner's "
                   "recurring question gets a measured answer under the "
                   "current configuration rather than a recalled one."),
        rule=("Resting limit at entry plus N times initial risk per share. "
              "Entry, stop, RSI exit and holding cap unchanged."),
        parameters={"take_profit_R": [1.5, 2.0, 3.0]},
        search_procedure="Full grid of 3, evaluated once.",
        max_configurations=3, **COMMON),

    Hypothesis(
        statement=("Protecting an existing gain beats targeting a fixed one: "
                   "once a trade has run up by G, moving the stop to "
                   "breakeven plus costs removes the loss case while leaving "
                   "the upside uncapped."),
        rationale=("Distinct from the trail: this changes only the DOWNSIDE "
                   "of a trade that has already worked. It is the cheapest "
                   "mechanism that could act on the 8.47 percent giveback in "
                   "the stop bucket."),
        rule=("When unrealised gain reaches G times initial risk per share, "
              "move the stop to entry plus round-trip cost. Ratchet only "
              "upward."),
        parameters={"lock_at_R": [1.0, 1.5, 2.0]},
        search_procedure="Full grid of 3, evaluated once.",
        max_configurations=3, **COMMON),

    Hypothesis(
        statement=("Selling half at a target and letting the rest run "
                   "improves risk-adjusted return without reducing total "
                   "return, because it lowers variance more than it lowers "
                   "expectation."),
        rationale=("Scaling out is the standard answer to the tail problem "
                   "and is registered so it is tested rather than assumed. "
                   "It adds real money-path machinery - partial fills, two "
                   "stop quantities - so the complexity penalty applies with "
                   "full force."),
        rule=("Sell half the position at entry plus S times initial risk per "
              "share; the remainder keeps the original stop and the RSI and "
              "holding exits."),
        parameters={"scale_at_R": [1.0, 2.0]},
        search_procedure="Full grid of 2, evaluated once.",
        max_configurations=2, **COMMON),
]


def main():
    for hypothesis in HYPOTHESES:
        try:
            row = register(hypothesis)
        except RegistrationError as error:
            print("refused: {0}".format(error))
            continue
        payload = row["payload"]
        print("{0}  seal {1}  trials {2}".format(
            payload["hypothesis_id"], payload["seal"][:12],
            payload["max_configurations"]))
        print("    {0}".format(payload["statement"][:70]))
    print("\nchain: {0}".format(verify_chain()))
    print("declared trials across all registrations: {0}".format(
        declared_trials()))
    print("\nNothing has been run. These are commitments, not results.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
