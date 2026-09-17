"""Seal H-0007 before any abstention result exists. Run once.

The hypothesis is the MECHANICAL one and nothing else: mean reversion's
selection edge should scale with realised volatility, so abstaining in
unusually calm conditions should raise risk-adjusted return. The
descriptive pass that prompted it also found two net-negative states -
calm volatility and a 5-10% market pullback - and those observations are
recorded here as PROVENANCE, not as additional hypotheses. H-0007 tests
one signal, one direction, three cutoffs.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0007 = Hypothesis(
    statement=(
        "Abstaining from NEW ENTRIES while SPY's 20-day realised volatility "
        "sits in the bottom expanding percentile improves risk-adjusted "
        "return (Sharpe) relative to the frozen baseline, while LOWERING "
        "total return, because abstention removes market exposure as well "
        "as losses."),
    rationale=(
        "Mechanical prior, formed independently of any outcome table: a "
        "mean-reversion edge is the size of the bounce off an oversold "
        "reading, and bounce size scales with volatility. In unusually calm "
        "conditions the same RSI threshold fires on smaller dislocations, so "
        "the edge per trade should shrink toward the cost of trading."),
    rule=(
        "For session t, compute SPY's 20-day realised volatility as of the "
        "PRIOR close t-1, take its expanding percentile among every such "
        "reading from the start of the series through t-1, and if that "
        "percentile is strictly below the cutoff, allow NO NEW ENTRIES on "
        "session t. Applied through `model_veto`, which can only remove a "
        "candidate. Positions already open are unaffected: sizing, stops, "
        "exits and the holding cap are untouched. Before 252 volatility "
        "readings exist the percentile is not trusted and entries are "
        "ALLOWED, so the early window matches the baseline exactly."),
    parameters={
        "signal": "SPY 20-day realised volatility, population stdev of the "
                  "20 daily closes-to-close returns ending at t-1",
        "threshold_method": "EXPANDING percentile - the rank of the reading "
                            "among all readings through t-1 and nothing "
                            "later. A full-sample quantile would let 2026 "
                            "label 2016 and is forbidden.",
        "minimum_history_readings": 252,
        "cutoffs": {"A": 1 / 3, "B": 0.25, "C": 0.20},
        "information_boundary": "through the PRIOR close only. Today's open, "
                                "high, low, close and volume are all excluded "
                                "from today's abstention decision, which is "
                                "stricter than the strategy's own entry rule "
                                "and cannot leak.",
        "family_rule": "A, B and C are ONE family. No configuration has an "
                       "independent promotion opportunity.",
        "declared_direction": {
            "sharpe": "rises as the cutoff rises, i.e. Spearman(cutoff, "
                      "Sharpe) POSITIVE",
            "total_return": "falls as the cutoff rises, i.e. Spearman("
                            "cutoff, total return) NEGATIVE"},
        "provenance": (
            "GENERATED AFTER a descriptive forensic pass on 2026-09-17 that "
            "examined six regime dimensions on this same decade. This "
            "hypothesis therefore carries a multiple-comparison and search "
            "cost: the volatility dimension was chosen from among six that "
            "had already been looked at. The mechanical prior is independent "
            "of those tables, but the CHOICE of dimension was not, and this "
            "result may not be treated as if the dimension had been named in "
            "advance."),
    },
    search_procedure=(
        "Exactly three cutoffs, once each, decade only. No intermediate "
        "value may be tested, no cutoff added after the surface is visible, "
        "and no other regime dimension - drawdown, moving averages, "
        "HYG/LQD, SPY/TLT, breadth, dispersion, correlation, liquidity - is "
        "part of H-0007. No sizing, exit, ranker or veto change."),
    max_configurations=3,
    datasets=["decade (development)",
              "thirty_year (contaminated robustness, CONDITIONAL single read)"],
    information_boundary=(
        "SPY closes through session t-1 decide session t's abstention. "
        "Nothing from session t's own bar is used."),
    execution_assumptions=(
        "Frozen production candidate, unchanged: market order at the signal "
        "close, gapped stops fill at the open, 2 bps half spread + 4 bps "
        "slippage each way, $0 commission, whole shares, 3 entries per day, "
        "20% per name, 2% ADV cap, 0.652% rule-exit haircut. Idle cash earns "
        "0%, as the simulator holds it."),
    primary_metric=(
        "Sharpe as computed by evaluation._ratio: mean daily return divided "
        "by population stdev of daily returns, times sqrt(252), at RISK-FREE "
        "RATE ZERO. Reported alongside total return, which is expected to "
        "fall."),
    secondary_metrics=[
        "cumulative return", "CAGR", "annualised volatility", "Sortino",
        "max drawdown", "Calmar", "trades", "turnover", "transaction costs",
        "exposure", "win rate", "profit factor", "sessions abstained",
        "winners removed", "losers removed", "P&L of removed winners",
        "P&L of removed losers", "market / selection / timing attribution",
        "cumulative return vs SPY price-only", "year-by-year vs baseline"],
    acceptance_criteria=(
        "ALL FOUR. (A) sharpe_candidate > sharpe_baseline. "
        "(B) abs(max_drawdown_candidate) <= 1.10 x abs(max_drawdown_baseline). "
        "(C) MONOTONICITY across the three registered cutoffs in the declared "
        "direction: Spearman(cutoff, Sharpe) > 0 AND Spearman(cutoff, total "
        "return) < 0, with no sign reversal between adjacent cutoffs on the "
        "Sharpe series. (D) THIRTY-YEAR SIGN: the Sharpe improvement holds in "
        "sign on the thirty-year window. Clause D is evaluated ONLY IF at "
        "least one configuration passes A, B and C on the decade; if none "
        "does, the thirty-year window is NOT read and its access count stays "
        "at 13. Acceptance yields research_evidence, never promotion."),
    rejection_criteria=(
        "Any clause fails. The REGISTERED EXPECTATION is that H-0007 may "
        "fail because abstention removes more market beta and more winners "
        "than it removes losses - H-0006 established that idle capital earns "
        "nothing. A Sharpe rise caused purely by removing exposure is NOT "
        "evidence that selection improved, and the report must separate the "
        "two. A total-return fall alone does not reject, since it is the "
        "declared direction."),
    robustness_requirements=[
        "equivalence: the unchanged baseline reproduces through the same "
        "execution path before any configuration is evaluated",
        "three cutoffs form the robustness gradient; a lone working cutoff "
        "with failing neighbours is recorded as a spike",
        "year-by-year reported, 2025 included and never removed after the "
        "fact",
        "removed trades decomposed into winners and losers with their P&L",
        "attribution split into market, selection and timing so a beta "
        "effect cannot be reported as a selection effect",
        "thirty-year read is conditional and happens at most once",
    ],
    complexity_penalty=(
        "Abstention adds a market-state dependency to the entry path. It "
        "must improve Sharpe outright; a Sharpe gain inside noise does not "
        "justify the dependency."),
    required_oos_test=(
        "None available. The thirty-year window is CONTAMINATED ROBUSTNESS "
        "EVIDENCE with 13 prior reads and is not a holdout; clause D uses it "
        "at most once and labels it as such. The clean forward record holds "
        "0 sessions and is not touched. Ceiling: research_evidence."),
    promotion_requirements=[
        "H-0007 alone can promote nothing",
        "a passing configuration is at most an adjudication candidate",
        "promotion requires the explicit mechanism, an exact identity, and "
        "fails closed on anything missing or mismatched",
    ],
    kind="confirmatory",
    hypothesis_id="H-0007",
)


def main():
    try:
        row = register(H0007)
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
    print("\nNothing has been run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
