"""Seal H-0025 before any give-back or gain-to-loss number is computed.

FORENSIC MEASUREMENT ONLY. No exit rule is proposed, no parameter tested, no
economic comparison made, nothing promoted. The frozen strategy entering Clean
OOS is untouched.

WHY THIS IS NOT H-0021 REPEATED. H-0021 (sealed 563d778a, 2026-09-21) measured
give-back against PEAK_NEXTOPEN and reported 73.6% aggregate / 87.3% median
retention, and it did so under two choices that this hypothesis revisits:

  1. THE EXECUTION BOUNDARY H-0021 ASSUMED IS NOT THE FROZEN ONE.
     H-0021's execution_assumptions state that filling at the next open "is
     exactly what the frozen entry mechanism already assumes." It is not.
     research.PRODUCTION_CANDIDATE fixes entry_fill = "signal_close", and
     portfolio.py books every rule exit at bar.close * (1 - 0.00652). SPEC-0001
     v1.0.0 - written 2026-09-22, the day AFTER H-0021 - made that boundary
     canonical (C-1: the exit rule sees the session in progress). H-0021
     therefore measured the give-back against a price STRICTLY WORSE than the
     one the frozen strategy actually transacts at, which UNDERSTATES it. The
     canonical executable peak is max(close) * (1 - haircut), not max(open).

  2. H-0021 EXCLUDED THE STOP POPULATION BY CONSTRUCTION.
     Its seal reads: "a stop fills when hit and the price was not a choice",
     so all 239 stop exits were reported apart and removed from the pool. But
     the owner's question here is the gain-to-loss transition: a trade that
     reached a real, executable, observed gain and then realised a LOSS. That
     population lives predominantly inside the stop exits H-0021 set aside.
     The stop PRICE was not a choice; the decision to remain in the trade at
     an observed +X% WAS one, taken by the frozen exit rule at that close.
     H-0021 never measured it.

  3. H-0021's BANDS WERE PEAK-CONDITIONED, NOT CROSSING-CONDITIONED.
     Its R bands select trades whose PEAK reached N x R - a retrospective
     filter. This hypothesis conditions on the FIRST BAR AT WHICH an executable
     gain threshold was crossed and measures only what happened AFTERWARDS.
     The two are different populations and answer different questions.

If the numbers below turn out to restate H-0021 within noise, outcome D says
so, and that is a first-class result. A repeat dressed as a discovery is the
failure mode this seal exists to prevent.

NOTHING HERE MAY MOVE A PARAMETER. Outcome A licenses ONE thing: a written
future-research proposal that must itself be separately registered and must
carry the prior exit ledger into its DSR. It does not license an exit rule, a
candidate, a fit, or any production change.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0025 = Hypothesis(
    statement=(
        "Under the CANONICAL SPEC-0001 execution boundary - a rule exit "
        "transacts at that session's own close less the 0.652% haircut - a "
        "repeatable population of frozen-strategy trades reaches a "
        "materially positive EXECUTABLE unrealised gain and subsequently "
        "realises a LOSS, and the state observable at the moment the gain "
        "threshold was crossed carries information about which trades "
        "deteriorate. The hypothesis FINDS NOTHING if: the gain-to-loss "
        "population is small or immaterial; or it is confined to trades the "
        "stop already resolves within a bar or two of the crossing; or the "
        "give-back at each band is indistinguishable from the normal "
        "pullback of trades that go on to larger gains; or no crossing-time "
        "feature separates deterioration from continuation; or the whole "
        "picture restates H-0021 once the boundary is corrected."),
    rationale=(
        "The owner reports that unrealised gains appear to be given back "
        "before trades eventually exit. H-0021 measured give-back but (a) "
        "against next-open rather than the canonical signal-close boundary "
        "that SPEC-0001 v1.0.0 fixed the following day, which understates "
        "it, and (b) with all 239 stop exits removed from the pool as 'not "
        "a choice', which removes exactly the gain-to-loss population the "
        "owner is asking about. Whether a trade that showed +3% and then "
        "realised -5% represents a decision failure or ordinary volatility "
        "in a mean-reversion book has never been measured on this strategy."),
    rule=(
        "READ-ONLY over the frozen baseline's decade trades. The baseline "
        "must reproduce +58.5889000000% / 698 first or nothing is computed. "
        "For every closed trade without exception, walk the daily bars from "
        "the entry session to the exit session inclusive. At each bar t "
        "record the EXECUTABLE unrealised return "
        "x(t) = close(t)*(1-0.00652)/entry_price - 1. For each predeclared "
        "band B, locate t*(B) = the FIRST bar with x(t) >= B, and measure "
        "ONLY what follows t*(B). Nothing is fitted. No rule is simulated. "
        "No exit is altered. No trade is excluded for any reason. No "
        "threshold is selected as best."),
    parameters={
        "execution_boundary_CANONICAL": {
            "EXECUTABLE": "close(t) * (1 - 0.00652) at any bar t in the "
                          "hold - the frozen strategy's own rule-exit price "
                          "under SPEC-0001 C-1 and entry_fill=signal_close",
            "MODEL_AVAILABLE": "raw close(t), and next open(t+1) - real "
                               "prices requiring a formally defined rule",
            "HINDSIGHT_ONLY": "intraday high(t) - never counted as a forgone "
                              "opportunity, reported only as a bound",
            "adverse_asymmetry": "low(t) IS executable downward because the "
                                 "protective stop is a resting order; this "
                                 "asymmetry is stated wherever MAE appears"},
        "gain_bands_FIXED_percent": [0.5, 1.0, 2.0, 3.0, 5.0, 10.0],
        "band_meaning": "first bar at which the EXECUTABLE unrealised return "
                        "reaches the band; all statistics look forward only",
        "per_band_metrics_FIXED": [
            "trades reaching it", "percent eventually profitable",
            "percent eventually losing", "median subsequent give-back",
            "p75/p90/p95 subsequent give-back", "median final return",
            "maximum subsequent loss", "median bars from threshold to exit",
            "fraction achieving a larger executable gain afterwards"],
        "three_populations_NEVER_MERGED": {
            "A": "normal winner development - pulls back, then exceeds the "
                 "gain it gave back",
            "B": "excessive give-back - reaches a band, exits profitable but "
                 "well below the executable peak",
            "C": "gain-to-loss - reaches a band, realises a loss"},
        "crossing_time_features_FIXED": [
            "executable return at t*", "RSI(14) at t*", "ATR(14)/close at t*",
            "bars_held at t*", "drawdown from running executable peak at t*",
            "volume(t*) / mean volume over the prior 20 bars",
            "SPY-relative return from entry to t*", "SPY RSI(14) at t*",
            "close/SMA200 at t*"],
        "feature_method": "Spearman rank IC of each feature against the "
                          "subsequent outcome, day-collapsed to one "
                          "observation per calendar day to defuse clustered "
                          "positions, reported with chronological thirds. NO "
                          "MODEL IS FITTED. No feature is added, dropped or "
                          "transformed after results are seen.",
        "stops_INCLUDED_and_why": "H-0021 excluded stop exits because the "
                                  "fill price was not a choice. That is "
                                  "correct about the PRICE and wrong about "
                                  "the POSITION: remaining in a trade at an "
                                  "observed executable gain is a decision the "
                                  "frozen rule took. Stop exits are included "
                                  "here and always reported separately.",
        "configurations_spent_here": 1,
        "economic_comparisons_spent_here": 0,
        "prior_ledger_carried_forward": {
            "exit_family_configurations": 54,
            "registered_exit_experiments": 12,
            "mechanism": "top 50 trades carry 67% of all profit",
            "H-0021": "give-back exists, concentrated in the time exit; "
                      "RSI exit gives back nothing; biggest winners give "
                      "back essentially nothing; NO NEW CANDIDATE"},
        "what_is_NOT_done": [
            "any exit rule", "any take profit", "any trailing stop",
            "any profit lock", "any dynamic or volatility stop",
            "any momentum or giveback exit", "any parameter sweep",
            "any threshold selection", "any fitted model",
            "any comparison against the baseline", "any candidate",
            "any promotion", "any production change",
            "any clean-OOS access", "any thirty-year read",
            "any use of the live forward record as evidence"],
    },
    search_procedure=(
        "One descriptive pass over the frozen trade list. The six gain "
        "bands, the nine per-band metrics, the three populations and the "
        "nine crossing-time features are fixed here and may not be added "
        "to, moved, reselected or re-binned after results are seen. No "
        "population is defined after inspecting an outcome. No trade is "
        "removed. No band is nominated as best - selecting one would be "
        "parameter optimisation and is forbidden by the directive."),
    max_configurations=1,
    datasets=["decade (development), the frozen baseline's own 698 trades",
              "thirty_year: NOT USED. Access count stays at 13.",
              "clean OOS: NOT USED. 0 sessions, frozen until 2026-10-12.",
              "live audit log: NOT USED AS EVIDENCE. 22 entries / 3 exits, "
              "and it is the embargoed forward period."],
    information_boundary=(
        "Every per-band and per-feature statistic is computed from bars at "
        "or before t*(B) for the conditioning, and from bars after t*(B) for "
        "the outcome. The intraday high is never used as an opportunity. The "
        "analysis is retrospective description of trades that already closed "
        "in the frozen baseline; no figure here is an achievable return, an "
        "edge, or a gain, and none may be quoted as one. A peak identified "
        "with hindsight is a measurement, not an opportunity."),
    execution_assumptions=(
        "The frozen framework's own, unchanged, and CORRECTED relative to "
        "H-0021: the executable exit price is that session's own close less "
        "the 0.652% rule-exit haircut, because research.PRODUCTION_CANDIDATE "
        "sets entry_fill=signal_close and portfolio.py books rule exits at "
        "bar.close*(1-0.00652). The next-open price H-0021 used is reported "
        "alongside as the conservative alternative so the two are "
        "comparable. No spread or slippage is subtracted from a hypothetical "
        "improvement, because no improvement is claimed."),
    primary_metric=(
        "The share of trades crossing each predeclared executable gain band "
        "that go on to realise a LOSS, together with the median and p90 "
        "give-back from the running executable peak observed at or after the "
        "crossing - reported band by band, with no band nominated as best."),
    secondary_metrics=[
        "full distribution of executable MFE and MAE, stops included",
        "population A / B / C counts and dollars at every band",
        "median bars from crossing to exit, and to the eventual peak",
        "fraction continuing to a larger executable gain after the crossing",
        "the same figures under the next-open price, for H-0021 comparison",
        "the same figures under the hindsight high, labelled unexecutable",
        "give-back and gain-to-loss by exit reason, stops reported apart",
        "chronological thirds and the 2-of-3 rule on every headline figure",
        "concentration of the gain-to-loss pool by symbol, year and trade",
        "Spearman IC of each fixed crossing-time feature, day-collapsed",
    ],
    acceptance_criteria=(
        "(A) EVIDENCE EXISTS: a material share of band crossings realise a "
        "loss, the give-back is large relative to the normal pullback of "
        "trades that continue, the pattern holds in at least 2 of 3 "
        "chronological thirds, it is not concentrated in a handful of "
        "symbols or trades, and at least one fixed crossing-time feature "
        "shows a stable association with deterioration. "
        "(B) EVIDENCE IS WEAK OR INCONCLUSIVE. "
        "(C) EVIDENCE DOES NOT EXIST. "
        "(D) ALREADY ANSWERED BY H-0021 - the corrected boundary and the "
        "included stop population do not change its conclusion. "
        "No fifth category. Outcome A licenses ONE written future-research "
        "proposal, which must be separately registered before any data is "
        "touched for it. No outcome changes an exit, a parameter, a "
        "threshold or production."),
    rejection_criteria=(
        "Explicitly NOT successes: a give-back measured against the intraday "
        "high; a gain-to-loss population that is simply the left tail of a "
        "distribution whose right tail carries the book's profit; a pattern "
        "visible in one chronological third; a feature association that "
        "requires dropping or transforming a feature after seeing it; a "
        "band chosen because it looked best; any implication that the top "
        "of the winner distribution can be truncated for free, when five "
        "registered experiments measured that it cannot; and any use of the "
        "22-entry live record to support a conclusion."),
    robustness_requirements=[
        "baseline equivalence +58.5889000000% / 698 verified first",
        "EXECUTABLE / MODEL-AVAILABLE / HINDSIGHT-ONLY labelled at every "
        "appearance and never merged",
        "stop exits included but always reported separately",
        "no trade excluded, no outlier removed, no band reselected",
        "chronological thirds and the 2-of-3 rule on every headline figure",
        "day-collapsing on every IC",
        "prior 54 exit configurations stated in the report",
        "H-0021 and every prior exit experiment left frozen; H-0021 is "
        "corrected on the execution boundary, NOT reinterpreted on its own "
        "terms, and its seal and numbers stand as recorded",
        "fingerprint da22011e...c237b unchanged",
        "zero reads of the thirty-year dataset, zero reads of clean OOS",
    ],
    complexity_penalty=(
        "The standing two percentage points. Any rule that later tries to "
        "capture anything measured here must clear it net of costs, and must "
        "also pay the give-back its own trigger width costs by construction "
        "- which EXP-0048 measured eats a third to a half before anything "
        "is captured."),
    required_oos_test=(
        "None applicable; nothing is fitted and no return is claimed. The "
        "clean forward record holds 0 sessions and is frozen until "
        "2026-10-12, so no proposal arising from this work can reach a clean "
        "out-of-sample test before that date. Ceiling: research_evidence."),
    promotion_requirements=[
        "H-0025 promotes nothing and changes no parameter",
        "outcome A licenses only a WRITTEN future-research proposal",
        "any such proposal is separately registered before data is touched",
        "any resulting candidate carries the prior exit ledger into its DSR",
        "all prior experiments remain frozen and none is reinterpreted",
    ],
    kind="exploratory",
    hypothesis_id="H-0025",
)


def main():
    chain = verify_chain()
    if not chain["intact"]:
        print("REFUSED: registration chain is not intact.")
        return 2
    try:
        register(H0025)
    except RegistrationError as exc:
        print("REFUSED: {0}".format(exc))
        return 2
    # `register` does not return the stored row; read it back.
    from event_aware_trader.modelgov.prereg import load
    rec = [r for r in load() if r["hypothesis_id"] == "H-0025"][-1]
    print("H-0025 sealed {0}".format(rec["seal"]))
    print("  commit  {0}".format(rec["code_commit"]))
    print("  trials  {0}".format(declared_trials()))
    print("  chain   {0}".format(verify_chain()["intact"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
