"""Seal H-0023 before any survivorship-corrected return is computed.

A VALIDITY AND CEILING AUDIT. No parameter is swept, no signal added,
no execution assumption relaxed, nothing promoted. The question is how
much of +58.5889000000% survives when the historical universe is given
a fair chance to contain the securities that disappeared.

WHAT THE UNIVERSE ACTUALLY IS, established from source before sealing.
`DEFAULT_UNIVERSE = tuple(CORRELATION_BUCKETS.keys())` - a curated
dict. strategy.py records how the list was assembled in September
2026: "Selected by the strategy's OWN floors - $20 minimum price, $50m
median daily dollar volume", then filtered for 3x funds, bitcoin
wrappers and cash-equivalents, and stopped at roughly the top 200
because "past 200 the edge decays monotonically".

TWO CONSEQUENCES, both recorded here rather than discovered later.
First, membership was chosen from the 2026 cross-section, so it is a
survivor set by construction. Second, the SIZE of the list was chosen
on measured edge, which is a separate selection effect layered on top
of survivorship and which this experiment does NOT remove.

EXP-0031 DOES NOT ALREADY ANSWER THIS. Its record reads
`{"universe": "46 ETFs"}`. A 46-ETF run is a survivorship-free PROXY,
not the same universe made complete, so its 9.14 -> 3.82 comparison
confounds removing survivorship with changing the asset set entirely.
It is carried forward as context and not as a bound.

THE CONSTRUCTION, fixed here.

  POPULATION   every Alpaca asset with status=inactive,
               asset_class=us_equity, on NYSE/NASDAQ/ARCA/AMEX/BATS -
               2,868 symbols. OTC excluded: the floors are $20 and
               $50m and no OTC name reaches them.
  ELIGIBILITY  a delisted symbol joins the universe only for the
               sessions where it met production's OWN floors, close
               >= $20 and 20-day dollar volume >= $50m, computed from
               closed bars only. That is the same rule the curated
               list says it used.
  UNIVERSE     curated 230 UNION eligible delisted. The curated
               membership is NOT re-ranked. Re-ranking would need the
               full active cross-section, and mixing that in would
               confound survivorship with a change of universe
               definition - the exact error EXP-0031 made.

DELISTING MUST BE GIVEN A PRICE, and there is no neutral choice.
A delisted name's bars simply STOP; the asset record carries no
delisting date and no delisting REASON, so an acquisition at a premium
and a bankruptcy are indistinguishable in this data. Sealed in
advance: a position still open when its bar history ends is closed at
the LAST AVAILABLE CLOSE through the same cost model as any other
exit, with exit_reason "delisted". The alternative - a 100% loss - is
reported as a SEPARATE BOUND and never merged into the headline.

"SURVIVORSHIP IS NOT MATERIAL" IS A FIRST-CLASS OUTCOME. Additional
names are not assumed to reduce performance; a delisting is as often
an acquisition at a premium as a failure.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0023 = Hypothesis(
    statement=(
        "A materially large part of the frozen baseline's "
        "+58.5889000000% is an artefact of running a 2026-selected "
        "surviving universe over historical sessions. Admitting the "
        "securities that met the same liquidity floors at the time and have "
        "since delisted changes the decade result enough to alter the "
        "interpretation of the strategy's historical profitability ceiling. "
        "The audit FAILS - and survivorship closes as a material limitation "
        "- if the corrected result is close to the baseline, or if the "
        "difference cannot be attributed, or if the reconstruction is not "
        "defensible enough to compare."),
    rationale=(
        "Every number this project has published rests on a universe whose "
        "230 members all still trade today: zero delistings. EXP-0031 "
        "gestured at the problem with a 46-ETF proxy and is routinely quoted "
        "as bounding decade CAGR between 3.82% and 9.14%, but that "
        "comparison changes the asset set as well as the survivorship, so it "
        "bounds nothing cleanly. Before any further search for economic "
        "edge, the most defensible historical baseline has to be "
        "established."),
    rule=(
        "ONE CHANGE ONLY: historical universe membership. Signal rules, "
        "RSI 35/60, ATR ceiling 0.035, 2.5x ATR stop, 20-bar cap, entry and "
        "exit timing, entry_fill=signal_close, the 0.652% haircut, the cost "
        "model, sizing, risk 0.005, bucket cap 1, 12 positions, 3 entries a "
        "day, candidate ordering and portfolio sequence are all untouched "
        "and run through the SAME code path. "
        "Baseline equivalence +58.5889000000% / 698 is asserted on the "
        "curated universe BEFORE the corrected universe is run; if it fails "
        "the experiment stops and the corrected result is not inspected. "
        "A delisted symbol is admitted only for the sessions where it met "
        "close >= $20 and 20-day dollar volume >= $50m from closed bars. "
        "Its bucket is assigned by the same CORRELATION_BUCKETS rule, "
        "defaulting to 'other' where the dict has no entry - documented as "
        "a deviation, because a curated dict cannot cover names nobody "
        "added."),
    parameters={
        "population": "Alpaca status=inactive, asset_class=us_equity, "
                      "exchange in NYSE/NASDAQ/ARCA/AMEX/BATS = 2,868",
        "excluded": "16,307 OTC symbols - cannot reach a $50m floor",
        "eligibility_rule": "close >= 20.0 AND 20-day dollar volume >= 50e6, "
                            "closed bars only - production's own floors",
        "universe": "curated 230 UNION eligible delisted; curated membership "
                    "NOT re-ranked",
        "why_not_reranked": "re-ranking needs the full active cross-section; "
                            "mixing it in confounds survivorship with a "
                            "change of universe definition",
        "delisting_terminal_value": {
            "sealed": "close the open position at the LAST AVAILABLE CLOSE "
                      "through the ordinary cost model, exit_reason "
                      "'delisted'",
            "bound_reported_separately": "100% loss on every position open "
                                         "at delisting",
            "why": "the asset record carries no delisting date and no "
                   "delisting reason, so an acquisition at a premium and a "
                   "bankruptcy are indistinguishable in this data"},
        "bucket_for_unlisted_names": "CORRELATION_BUCKETS.get(symbol, "
                                     "'other') - a documented deviation",
        "decomposition_required": ["added historical names",
                                   "portfolio competition", "cash effects",
                                   "bucket effects", "position effects",
                                   "candidate-order effects"],
        "materiality": "the standing 2-percentage-point reference, reused "
                       "unchanged",
        "stability": "existing chronological thirds and the 2-of-3 rule, "
                     "plus an annual breakdown where sample size permits",
        "EXP_0031_status": "context only; its universe is 46 ETFs and it "
                           "bounds nothing cleanly",
        "what_is_NOT_done": ["any parameter sweep", "any added signal",
                             "any news", "any leverage",
                             "any execution-assumption change",
                             "any benchmark change", "any re-ranking of the "
                             "curated universe", "any removal of a "
                             "poor-performing delisted name",
                             "any promotion", "any clean-OOS access",
                             "any live order"],
    },
    search_procedure=(
        "Two runs on one fixed construction: the curated universe and the "
        "survivorship-complete universe, through identical code. No "
        "universe is selected after seeing a result, no symbol is removed "
        "for looking anomalous, no year is dropped. The terminal-value "
        "choice is sealed here and its alternative is reported as a bound, "
        "not substituted for it."),
    max_configurations=2,
    datasets=["decade (development), curated 230 plus eligible delisted",
              "thirty_year: NOT USED. Access count stays at 13."],
    information_boundary=(
        "Eligibility at session t uses only bars at or before t - the same "
        "closed-bar arithmetic production uses. A delisted symbol is present "
        "for exactly the sessions in which it actually traded, which is what "
        "its bar history records; its disappearance is therefore observed at "
        "the time rather than known in advance. NOTHING uses the fact that a "
        "name is delisted TODAY to include or exclude it at an earlier date. "
        "The one irreducible leak is the population itself: the list of "
        "inactive assets is read in 2026, so the SET of names considered is "
        "known with hindsight even though each name's eligibility is not. "
        "That is stated as a limitation and not argued away."),
    execution_assumptions=(
        "Identical to production: entry_fill=signal_close, "
        "realistic_stop_fills, whole shares, CostModel 2bps + 4bps one way, "
        "0.652% rule-exit haircut, 0.02 ADV participation cap, 20% notional "
        "cap. The ONLY addition is the sealed terminal-value rule for a "
        "position open when a symbol stops trading."),
    primary_metric=(
        "Decade total return on the survivorship-complete universe against "
        "+58.5889000000%, with the SPY-relative comparison reported beside "
        "it and the fraction of the original result that survives stated "
        "explicitly."),
    secondary_metrics=[
        "CAGR, Sharpe, Sortino, max drawdown, exposure",
        "trade count, win rate, turnover, costs",
        "return per trade and return per unit of exposure",
        "symbol-sessions added by the corrected universe",
        "additional candidates and additional accepted trades",
        "existing trades whose admission changes",
        "delisted-name trades and their P&L, separately",
        "the 100%-loss terminal bound",
        "chronological thirds and an annual breakdown",
        "concentration by symbol, sector proxy, year and delisting cohort",
    ],
    acceptance_criteria=(
        "(A) SURVIVORSHIP BIAS IS MATERIAL: the corrected decade result "
        "differs from the baseline by more than the standing 2-point "
        "reference AND the difference is attributable, changing the "
        "interpretation of the historical ceiling. "
        "(B) BIAS EXISTS BUT DOES NOT CHANGE THE CORE CONCLUSION. "
        "(C) SURVIVORSHIP BIAS IS NOT MATERIAL. "
        "(D) PIT UNIVERSE CANNOT BE RECONSTRUCTED RELIABLY - membership, "
        "delisting dates, symbol mapping or corporate-action data are "
        "insufficient for a defensible comparison. "
        "No fifth category. No outcome promotes anything, changes a "
        "parameter, or authorises an optimisation of the corrected "
        "baseline."),
    rejection_criteria=(
        "Explicitly NOT successes: a difference driven by the terminal-value "
        "assumption rather than by the added names; a difference that cannot "
        "be decomposed; a result that depends on dropping a delisted name "
        "for looking anomalous - their existence is the reason for the "
        "audit; and treating the 46-ETF EXP-0031 figure as a validated "
        "bound."),
    robustness_requirements=[
        "baseline equivalence +58.5889000000% / 698 asserted FIRST",
        "production ordering preserved; any diagnostic order labelled "
        "COUNTERFACTUAL - NOT PRODUCTION ORDER and never mixed with "
        "production denominators",
        "no delisted name removed for poor performance",
        "terminal-value alternative reported as a separate bound",
        "chronological thirds plus an annual breakdown",
        "concentration measured without removing outliers",
        "H-0011/H-0013/H-0015/H-0016/H-0017/H-0018/H-0019/H-0020/H-0021 "
        "frozen and not reopened",
        "fingerprint da22011e...c237b unchanged",
        "zero reads of the thirty-year dataset",
    ],
    complexity_penalty=(
        "The standing two percentage points of decade total return, used as "
        "the reference for whether the survivorship difference is material."),
    required_oos_test=(
        "Not applicable; nothing is fitted and no forward claim is made. "
        "The clean forward record holds 0 sessions, is frozen until "
        "2026-10-12 and is not touched. Ceiling: research_evidence."),
    promotion_requirements=[
        "H-0023 promotes nothing and changes no parameter",
        "outcome A updates the project's stated profitability ceiling and "
        "authorises NO optimisation of the corrected baseline",
        "all prior experiments remain frozen",
    ],
    kind="exploratory",
    hypothesis_id="H-0023",
)


def main():
    try:
        row = register(H0023)
    except RegistrationError as error:
        print("refused: {0}".format(error))
        return 1
    p = row["payload"]
    print("registered {0}".format(p["hypothesis_id"]))
    print("  seal    {0}".format(p["seal"]))
    print("  commit  {0}".format(p["code_commit"]))
    print("\nchain: {0}".format(verify_chain()))
    print("declared configurations: {0}".format(declared_trials()))
    print("\nNo survivorship-corrected return computed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
