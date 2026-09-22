"""Seal H-0024 - intraday strategy capability gap audit. Run once.

A CAPABILITY AUDIT. No strategy, no economic backtest, no parameter
sweep, no production change, no promotion. One descriptive
configuration; ZERO economic comparisons.

WHAT IS ALREADY ANSWERED, AND IS NOT REOPENED. H-0014 is the sealed
intraday decision audit (`3acb220e...`, commit `4da278fa`). Its
statement is almost exactly this hypothesis: "Compressing a trading
session into a single daily OHLCV bar destroys information that is
measurable, available point-in-time during the session, and predictive
of subsequent SPY-relative return out of sample." It ran nested DAILY
vs DAILY+INTRADAY specifications, Spearman rank IC out of sample by
chronological third, the 2-of-3 stability rule and seven predeclared
path classes, over 5,252,811 snapshot rows and 525,712 sessions on
230/230 symbols. It classified **B**: the increment is sign-stable and
passes 2-of-3 at 3/3 on all ten snapshots, but collapses by about 85%
once the daily baseline is properly fitted, the one large apparent
opportunity is not identifiable in real time, and portfolio
constraints absorb almost all of what remains.

H-0024 THEREFORE DOES NOT RE-MEASURE INTRADAY INFORMATION. Re-running
it would repeat a sealed experiment with the same data and the same
method, which the governance forbids and which could only produce the
same number or a worse-founded one.

WHAT IS GENUINELY OPEN, and is the whole of this audit: H-0014
measured whether the information EXISTS. It did not trace whether the
emulator's decision ARCHITECTURE could act on it. That is section 16
of the directive and no prior branch covers it. The deliverable is an
exact code boundary, not a return.

THE OTHER CAPABILITY ROWS ARE POPULATED FROM CLOSED BRANCHES, not
re-measured: cross-sectional and relative strength (H-0019 P4, lift
+0.0407% at t=+0.64, negative on the ETF control; EXP-0025, ordering
flips between windows), volatility expansion (H-0019 P3 -> H-0020,
which breached the 14.2806% ceiling at 19.9234% and lost 16.9 points),
volume shock (H-0019 P5, lift -0.3797%), NBBO and spread and trade
intensity (H-0017), depth (H-0017: /v2/stocks/{sym}/book returns 404
at every tier), queue (H-0018 B), news and event timestamps (news
feasibility A - NO EVIDENCE; P5-0011/12/13, where the earnings filter
cost -10.8 points and the ANY-NEWS control cost -10.7), insider
filings (Form 4, all |d| < 0.2), gap behaviour (EXP-0005, EXP-0010,
EXP-0027).

A NEGATIVE RESULT CLOSES A BRANCH AND IS A FIRST-CLASS OUTCOME.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0024 = Hypothesis(
    statement=(
        "The dominant remaining capability gap is not another parameter of "
        "the daily mean-reversion strategy but the absence of a decision "
        "ARCHITECTURE able to act on information arriving during a session. "
        "The hypothesis FAILS - and intraday capability closes - if the "
        "architecture can already represent and act on such information, or "
        "if the architectural gap is real but the information behind it has "
        "already been bounded as too small or too unstable to matter, or if "
        "the gap cannot be established from the available code and data."),
    rationale=(
        "Every capability branch so far has returned the same shape of "
        "answer: the information exists and the portfolio value does not. "
        "H-0020 showed why in the sharpest form - a class with +2.4359% "
        "forward SPY-relative return, positive in 3 of 3 thirds and zero "
        "symbol-session overlap with production, still destroyed 16.9 points "
        "because it displaced better trades. If the binding constraint is "
        "the portfolio rather than information, an intraday architecture "
        "would not change it, and that must be established before any "
        "intraday mechanism is designed."),
    rule=(
        "READ-ONLY. The deliverable is a traced code boundary and a "
        "capability matrix assembled from ALREADY-SEALED results. "
        "Baseline equivalence +58.5889000000% / 698 is asserted first. "
        "No intraday dataset is re-analysed, no IC is recomputed, no "
        "feature is fitted, no horizon is selected, no threshold is swept, "
        "and no economic comparison of any kind is performed. Every "
        "capability row cites the branch that closed it; rows with no prior "
        "branch are marked NOT TESTED rather than estimated."),
    parameters={
        "architecture_questions_from_section_16": [
            "generate a candidate after the morning signal",
            "update a candidate during the session",
            "cancel or replace a pending decision",
            "enter after an intraday event",
            "exit before the daily close",
            "compare simultaneous opportunities",
            "reprioritise candidates",
            "respond to changing market state"],
        "evidence_source": "src/event_aware_trader/portfolio.py (the "
                           "emulator) and autotrade.py (the live loop), read "
                           "as source; no behaviour inferred from docs",
        "frozen_results_cited_not_recomputed": {
            "H-0014": "B; IC increment stable 3/3 across ten snapshots, "
                      "collapses ~85% under a fitted daily baseline; "
                      "5,252,811 snapshot rows",
            "H-0017": "depth unavailable (HTTP 404 at every tier); median "
                      "spread 1.63 bps",
            "H-0018": "B; queue span is 100% a validated modelling charge",
            "H-0019": "P3 +2.4359% / P4 collapsed to +0.0407% t=+0.64 / "
                      "P5 lift -0.3797%",
            "H-0020": "C; combined breached 14.2806% at 19.9234%, -16.9 pts, "
                      "crowding not addition",
            "H-0023": "D; survivorship magnitude unbounded"},
        "funnel_from_frozen_artefacts": {
            "symbol_sessions_scanned": 536324,
            "gate_passing": 487919,
            "production_BUY_signals": 5081,
            "reached_portfolio_evaluation": 1539,
            "accepted_trades": 698},
        "configurations_spent_here": 1,
        "economic_comparisons_spent_here": 0,
        "what_is_NOT_done": ["any strategy", "any new indicator",
                             "any ML model", "any parameter sweep",
                             "any regime or news filter",
                             "any re-analysis of the H-0014 snapshots",
                             "any IC recomputation", "any horizon selection",
                             "any production change", "any promotion",
                             "any clean-OOS access", "any live order",
                             "any reopening of H-0009 through H-0023"],
    },
    search_procedure=(
        "One pass: trace the production decision pipeline in source, answer "
        "the eight architecture questions with exact line references, and "
        "populate the capability matrix by citation. No capability is "
        "selected after seeing an economic outcome because no economic "
        "outcome is produced."),
    max_configurations=1,
    datasets=["source code and already-sealed results only; no dataset is "
              "re-analysed",
              "thirty_year: NOT USED. Access count stays at 13."],
    information_boundary=(
        "No forward information is used because no forward quantity is "
        "computed. The one boundary that matters here is the architectural "
        "one being traced: at what timestamp the emulator can first act on a "
        "fact. That is read from code, not estimated."),
    execution_assumptions=(
        "NONE APPLIED. In particular the 0.652% rule-exit haircut is NOT "
        "reused as slippage, transaction cost, intraday opportunity cost or "
        "evidence of an intraday edge - H-0012 and H-0013 established what "
        "it is and it stays there. Execution and decision capability are "
        "reported separately."),
    primary_metric=(
        "A binary, code-referenced answer to each of the eight architecture "
        "questions: can the emulator do this at all, and if not, at which "
        "line does the boundary sit."),
    secondary_metrics=[
        "the candidate funnel from frozen artefacts",
        "which exits can fire intraday and which cannot",
        "capability matrix with the closing branch cited per row",
        "rows with no prior branch, marked NOT TESTED",
        "the four-state distinction: data available, feature computable, "
        "decision accessible, strategy uses it",
    ],
    acceptance_criteria=(
        "(A) MATERIAL CAPABILITY GAP: a specific intraday class is "
        "unavailable, not reducible to daily features, frequent, "
        "information-bearing, chronologically stable and not an execution "
        "artefact. "
        "(B) CAPABILITY GAP EXISTS, ECONOMIC VALUE NOT ESTABLISHED. "
        "(C) EXISTING ARCHITECTURE IS NOT THE MAIN BOTTLENECK. "
        "(D) DATA/ARCHITECTURE LIMITATION. "
        "No fifth category. Each capability is additionally placed in "
        "exactly one of categories 1-5 from the directive. No outcome "
        "promotes anything or authorises an economic experiment to RUN; "
        "even A requires a separate registration first."),
    rejection_criteria=(
        "Explicitly NOT successes: restating H-0014's IC increment as a new "
        "finding; treating the existence of 5-minute data as a capability; "
        "treating NBBO availability as evidence of alpha; reusing the "
        "0.652% haircut as an intraday cost or edge; and nominating a "
        "capability on the basis of an unsealed economic result, of which "
        "this audit produces none."),
    robustness_requirements=[
        "baseline equivalence +58.5889000000% / 698 asserted first",
        "every capability row cites the branch that closed it, or is marked "
        "NOT TESTED",
        "architecture claims carry line references",
        "information value, decision value, strategy value and portfolio "
        "value reported as four separate levels and never collapsed",
        "H-0009 through H-0023 frozen and not reopened",
        "fingerprint da22011e...c237b unchanged",
        "zero reads of the thirty-year dataset",
        "clean OOS untouched at 0 sessions",
    ],
    complexity_penalty=(
        "The standing two percentage points. It is recorded for consistency "
        "and is not applied here, because this audit produces no economic "
        "quantity to compare against it."),
    required_oos_test=(
        "Not applicable; nothing is fitted and no return is claimed. The "
        "clean forward record holds 0 sessions, is frozen until 2026-10-12 "
        "and is not touched. Ceiling: research_evidence."),
    promotion_requirements=[
        "H-0024 promotes nothing and changes no parameter",
        "outcome A licenses the DESIGN of one separately sealed economic "
        "experiment, never its execution",
        "all prior experiments remain frozen and none is reinterpreted",
    ],
    kind="exploratory",
    hypothesis_id="H-0024",
)


def main():
    try:
        row = register(H0024)
    except RegistrationError as error:
        print("refused: {0}".format(error))
        return 1
    p = row["payload"]
    print("registered {0}".format(p["hypothesis_id"]))
    print("  seal    {0}".format(p["seal"]))
    print("  commit  {0}".format(p["code_commit"]))
    print("\nchain: {0}".format(verify_chain()))
    print("declared configurations: {0}".format(declared_trials()))
    print("\nNo economic result computed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
