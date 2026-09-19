"""Seal H-0009 before any result exists. Run once.

THE FAMILY WAS NARROWED BEFORE SEALING, AND WHY.

`rsi_entry` has already been swept twice. The decade sweep of
2026-09-07, recorded in mean_reversion.py itself, tested 30 / 35 / 40 /
45 and found a clean peak at 35 with drawdown deepening monotonically
as the gate loosens: -9.4%, -15.0%, -19.1%, -23.7%. An earlier two-year
sweep had 40 failing and dismissed it as noise; the decade agreed.
risk.py names the exact mechanism - "MORE signals at the OLD size is
worse than either, and quadruples the drawdown" - and records that
signal frequency and position size are one decision, not two.

So 39 and 40 were REMOVED from the family before sealing rather than
after seeing results. Re-running them would re-measure a documented
failure and spend a chain link doing it. What the old sweep never
touched is the interval BETWEEN 35 and 40, and that is exactly where
the 2026-09-18 breadth pass located its hump. H-0009 tests 36, 37 and
38 and nothing else.

WHAT IS GENUINELY NEW HERE, stated so the result is not oversold: the
fine structure between 35 and 40, and the SLOT-COMPETITION and
DISPLACEMENT analysis, which no prior sweep performed at any threshold.

THE HONEST PRIOR. The old sweep's drawdown gradient is a mechanical
exposure effect and should transport in DIRECTION even though its
magnitudes will not - its rsi-35 baseline was +127.6% against today's
+58.59%, because it predates the P1 stop fix and the 0.652% haircut.
The registered expectation below is therefore that this family FAILS on
drawdown, and the reason to run it anyway is the displacement question.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0009 = Hypothesis(
    statement=(
        "Admitting candidates with RSI strictly between 35 and 38 to compete "
        "for the portfolio's existing, unchanged slots improves total return "
        "and excess return versus SPY, WITHOUT deepening maximum drawdown "
        "beyond 110% of the frozen baseline. The claim is about SELECTION "
        "under a fixed capacity constraint, not about trading more: an "
        "increase in trade count, exposure or gross return that does not "
        "survive the drawdown clause and the displacement decomposition is "
        "a rejection, not a partial success."),
    rationale=(
        "The read-only breadth pass of 2026-09-18 measured forward excess "
        "versus SPY by RSI band on 192,392 symbol-sessions that passed every "
        "filter except RSI. The result was an inverted U: the band the "
        "strategy actually trades, RSI<=35, returned +0.095% at 10 sessions "
        "against a +0.052% price-only-SPY dividend artefact - approximately "
        "zero - while (35,37.5] returned +0.422% and (37.5,40] +0.406%, and "
        "(37.5,40] was positive in all three chronological thirds. Separately "
        "the capacity pass found the 12-position cap never binds and 52.1% of "
        "sessions produce no candidate at all, so additional eligible names "
        "would frequently fill EMPTY slots rather than displace anything. "
        "Whether that improves the constrained portfolio is the open "
        "question."),
    rule=(
        "One parameter changes: MeanReversionConfig.rsi_entry, from 35.0 to "
        "the registered value, passed via run_portfolio's existing "
        "`mr_config` argument. `rsi_entry` has exactly one decision call "
        "site - mean_reversion.evaluate line 417 - so the change affects "
        "ENTRY ELIGIBILITY ONLY. rsi_exit stays 60.0; the stop, the 20-bar "
        "holding cap, sizing, the 0.652% haircut, the correlation-bucket cap "
        "of 1, the 12-position cap, the 3-entries-per-day cap, the ADV and "
        "price floors, costs, slippage, the universe, the benchmark and the "
        "candidate ordering are all untouched. No production file is "
        "modified and no new ranking mechanism is introduced."),
    parameters={
        "parameter": "MeanReversionConfig.rsi_entry",
        "baseline": 35.0,
        "configurations": {"A": 36.0, "B": 37.0, "C": 38.0},
        "removed_before_sealing": {
            "values": [39.0, 40.0],
            "why": "The decade sweep of 2026-09-07 recorded in "
                   "mean_reversion.py already measured rsi_entry 40 at "
                   "+84.0% whole / +20.7% holdout / -19.1% maxDD against "
                   "35's +127.6% / +33.3% / -15.0%, with drawdown "
                   "monotone across 30/35/40/45. Re-running 39 and 40 "
                   "would re-measure a documented failure. Removed BEFORE "
                   "sealing, not after seeing results."},
        "prior_evidence": "rsi_entry has been swept TWICE - once on two "
                          "years before the account simulator existed, once "
                          "on the decade on 2026-09-07. 35 won both. The "
                          "unexplored region is strictly between 35 and 40, "
                          "which the decade sweep jumped.",
        "provenance": "GENERATED from a descriptive seven-band RSI table "
                      "computed on THIS decade on 2026-09-18. The 35-40 "
                      "region was chosen after seeing that table, so this "
                      "hypothesis carries a multiple-comparison and search "
                      "cost and may NOT be read as if the region had been "
                      "named in advance. The band boundaries here (36/37/38) "
                      "are integer steps inside it, not re-fitted cut points.",
        "information_boundary": "RSI(14) on closes through the decision bar, "
                                "identical to production. No forward return, "
                                "forward volatility, forward benchmark or "
                                "later portfolio outcome enters candidate "
                                "generation, ranking or admission.",
        "family_rule": "A, B and C are ONE family. No configuration has an "
                       "independent promotion opportunity, and the "
                       "highest-return threshold may not be selected after "
                       "the surface is visible.",
        "declared_direction": {
            "trades": "RISES monotonically with the threshold",
            "exposure": "RISES monotonically with the threshold",
            "max_drawdown": "DEEPENS monotonically with the threshold - this "
                            "is the mechanical exposure effect the prior "
                            "sweep measured and it is expected to recur",
            "total_return": "AMBIGUOUS and deliberately not predicted. The "
                            "name-level evidence says these candidates are "
                            "no worse; the prior portfolio sweep says "
                            "loosening costs return. The experiment exists "
                            "to separate those."},
    },
    search_procedure=(
        "Exactly three thresholds, once each, decade only. No intermediate or "
        "fractional value may be added after the surface is visible - not "
        "36.5, not 37.5, not 39 - and 39 and 40 are excluded by this "
        "registration. No sizing change, no ranking change, no exit change, "
        "no capacity change, no regime condition. A result suggesting any of "
        "those requires its own registration."),
    max_configurations=3,
    datasets=["decade (development)",
              "thirty_year: NOT USED. H-0009 does not read it and its access "
              "count stays at 13."],
    information_boundary=(
        "Daily bars through the decision bar only, exactly as production. "
        "Candidate ordering and portfolio selection order are preserved "
        "unchanged, so admission cannot depend on anything later."),
    execution_assumptions=(
        "Frozen production candidate in every respect except rsi_entry: "
        "market order at the signal close, gapped stops fill at the open, "
        "2 bps half spread + 4 bps slippage each way, $0 commission, whole "
        "shares, 3 entries per day, 20% per name, 2% ADV cap, 0.652% "
        "rule-exit haircut, idle cash at 0%."),
    primary_metric=(
        "Decade total return net of costs, and its difference from the "
        "frozen baseline's +58.5889%, reported alongside cumulative excess "
        "return versus SPY price-only over the identical window."),
    secondary_metrics=[
        "CAGR", "annualised volatility", "Sharpe", "Sortino", "max drawdown",
        "drawdown duration", "Calmar", "trades", "win rate", "average winner",
        "average loser", "profit factor", "turnover", "transaction costs",
        "exposure", "year-by-year total return",
        "candidates generated / accepted / refused by each constraint",
        "share of sessions at capacity", "average free slots",
        "newly admitted RSI 35-38 entries", "displaced RSI<=35 entries",
        "empty-slot additions",
        "forward 5/10/20-session return and excess vs SPY for RSI<=35 "
        "candidates and RSI 35-38 candidates separately",
        "stop rate, adverse excursion and favourable excursion by band",
        "incremental P&L attributable to each slot decision",
    ],
    acceptance_criteria=(
        "ALL FIVE, evaluated on the family as sealed. "
        "(A) RETURN: at least one configuration's decade total return exceeds "
        "the baseline's +58.5889% by MORE THAN 2 percentage points, the "
        "standing complexity penalty used by every prior registration. "
        "(B) DRAWDOWN: that configuration's abs(max_drawdown) <= 1.10 x "
        "abs(-12.9824%) = 14.2806%. The ceiling is not relaxed for any "
        "reason. "
        "(C) GRADIENT, NOT SPIKE: across the three thresholds the return "
        "deltas versus baseline must not be dominated by one point - the "
        "largest positive delta <= 2.5x the second-largest positive delta, "
        "the same constant H-0005 used. "
        "(D) DISPLACEMENT: the incremental P&L must not be produced by "
        "displacement. Entries admitted into EMPTY slots must be net "
        "positive on their own, AND the P&L of displaced RSI<=35 candidates "
        "must not exceed the P&L of the RSI 35-38 entries that replaced "
        "them. A configuration that profits only by evicting better "
        "candidates is rejected. "
        "(E) ROBUSTNESS: the passing configuration remains above baseline "
        "with its single best calendar year removed. "
        "Acceptance yields research_evidence. It does NOT promote: changing "
        "rsi_entry is a production change requiring its own registration, a "
        "new fingerprint and a restarted forward evaluation."),
    rejection_criteria=(
        "Any clause fails. THE REGISTERED EXPECTATION IS THAT THIS FAMILY "
        "FAILS CLAUSE B, because the prior decade sweep found drawdown "
        "deepening monotonically as the gate loosens and that is a "
        "mechanical consequence of added exposure rather than an artefact of "
        "the superseded simulator it was measured on. A higher trade count, "
        "higher gross return, higher exposure, higher beta, or a Sharpe "
        "improvement arising from a volatility denominator are each "
        "explicitly INSUFFICIENT and none of them constitutes partial "
        "success. If the family fails, the finding is that the 35-40 "
        "name-level hump does not survive the capacity constraint, which "
        "closes the entry-threshold direction rather than inviting a "
        "fourth sweep."),
    robustness_requirements=[
        "equivalence: the frozen baseline reproduces +58.5889% over 698 "
        "trades through the same execution path before any configuration runs",
        "three adjacent thresholds form the gradient; a lone working "
        "threshold with failing neighbours is recorded as a spike",
        "year-by-year reported, 2025 included and never removed after the fact",
        "leave-one-best-year-out",
        "leave-out the strongest few trades",
        "early / middle / late chronological thirds",
        "behaviour under the already-defined market states; no new regime "
        "definition is introduced",
        "displacement decomposed trade by trade, with the counterfactual "
        "candidate named",
        "zero reads of the thirty-year dataset",
    ],
    complexity_penalty=(
        "Two percentage points of decade total return. Below that the frozen "
        "boundary stands on simplicity grounds regardless of sign, because "
        "moving a parameter that has already survived two sweeps requires "
        "more than a marginal reading."),
    required_oos_test=(
        "None available and none claimed. The decade is contaminated for "
        "this candidate and for this parameter specifically, which has been "
        "swept on it twice before. The thirty-year window is contaminated "
        "robustness evidence at 13 reads and is NOT touched. The clean "
        "forward record holds 0 sessions. Ceiling: research_evidence."),
    promotion_requirements=[
        "H-0009 alone can promote nothing",
        "a passing configuration is at most an adjudication candidate",
        "changing rsi_entry in production requires its own registration, a "
        "new strategy fingerprint, and a restarted forward evaluation",
        "the 110% drawdown ceiling applies unchanged to any later promotion",
    ],
    kind="confirmatory",
    hypothesis_id="H-0009",
)


def main():
    try:
        row = register(H0009)
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
