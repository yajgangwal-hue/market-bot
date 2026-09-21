"""Seal H-0017 before any microstructure measurement. Run once.

A CAPABILITY AUDIT, not an economic experiment. No strategy change, no
parameter change, no threshold search, no economic backtest. Section 12
of the brief requires any economic test to be a SEPARATE sealed
experiment, so none is attempted here.

WHAT THE DATA AUDIT ALREADY ESTABLISHED, recorded before any analysis
so scope cannot be rationalised afterwards:

  NBBO quotes ARE accessible - /v2/stocks/quotes returns bid, ask, bid
  size, ask size, exchange codes, CONDITION FLAGS and tape, with
  sub-millisecond exchange timestamps, back to at least 2016-01-05.
  Trades are likewise available with price, size, exchange and
  condition codes.

  So the H-0011/H-0013 minimum requirement - NBBO top-of-book with
  exchange-clock timestamps at or finer than trigger resolution,
  covering the 221 reverted sessions, with condition flags - IS
  satisfiable in principle. That is a change from H-0013, where it was
  the blocking gap.

  BUT DENSITY FORBIDS WHOLESALE ACQUISITION. AAPL returns >10,000
  quotes in a single minute and ~120,000 trades in one session; XLV
  2,581 quotes/minute. A decade of NBBO for 230 symbols is on the order
  of 10^10 records and is not acquirable here. Any measurement must be
  TARGETED at specific decision timestamps, and the audit says so
  rather than discovering it late.

THE ONE QUESTION THIS AUDIT EXISTS TO ANSWER is H-0011's unresolved
one: when the sealed limit condition is reached, what is the
probability an order resting at that level actually fills?

QUEUE POSITION REMAINS UNRECONSTRUCTIBLE and this registration says so
in advance. NBBO gives displayed size at the top of book; it does not
give the order book behind it, nor where in the queue a hypothetical
order would sit. Therefore fill probability CANNOT be point-estimated.
What CAN be measured, honestly, is a BOUND: the volume that actually
transacted at or through the limit level while the order would have
been working. If that displaced volume vastly exceeds the order size,
a fill is near-certain irrespective of queue. If it is comparable,
the case is marginal and is reported as marginal, not as a fill.

Fabricating a fill, or assuming queue position, is forbidden.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0017 = Hypothesis(
    statement=(
        "Quote- and trade-level microstructure data contain point-in-time "
        "information the daily-OHLCV and 5-minute-snapshot architecture "
        "cannot observe, AND that information is sufficient to resolve "
        "H-0011's unanswered fill-probability question. The audit FAILS - "
        "and the microstructure direction closes - if the accessible data "
        "cannot establish fill probability beyond what 5-minute OHLCV "
        "already implied, or if the spread and top-of-book information at "
        "the decision boundary proves redundant with what the sealed "
        "intraday snapshots already encode."),
    rationale=(
        "H-0011 was classified B - REPRODUCIBLE BUT FRAGILE - specifically "
        "because its touch-equals-fill assumption carried its whole result "
        "and 5-minute OHLCV could not test it. H-0013 stalled on the same "
        "requirement for reverted-exit drift. Both named NBBO with "
        "exchange-clock timestamps and condition flags as the minimum "
        "missing capability. The data audit shows that data IS reachable, "
        "so the requirement can now be tested rather than restated."),
    rule=(
        "READ-ONLY capability audit. No production file is modified, no "
        "strategy is run, no parameter is varied, no economic backtest is "
        "performed. Baseline equivalence at +58.5889000000% over 698 trades "
        "is asserted before anything else. "
        "MEASUREMENT 1 - FILL BOUND. For each of the 221 `reverted` exits in "
        "the frozen baseline, the H-0011 limit level is the trigger close, "
        "recoverable exactly as H-0012 established: "
        "trigger_close = baseline_exit_price / (F x (1 - haircut)). Over the "
        "NEXT regular session, measure from TRADE prints: whether any trade "
        "occurred at or above the level; the total share volume at or above "
        "it; the time of first touch; and the ratio of that displaced volume "
        "to the position's own share count. "
        "MEASUREMENT 2 - SPREAD STATE. For a bounded window around the same "
        "decision timestamps, measure from NBBO: bid, ask, midpoint, "
        "absolute and relative spread, and displayed bid/ask size. "
        "Condition codes are retained and abnormal conditions are excluded "
        "rather than silently kept. "
        "NOTHING ELSE IS MEASURED. The wider feature inventory in the brief "
        "is not attempted, because the density audit shows the universe-wide "
        "acquisition it would need is infeasible here, and that infeasibility "
        "is itself a registered finding."),
    parameters={
        "data_source": "Alpaca /v2/stocks/quotes and /v2/stocks/trades",
        "quote_fields": ["bp", "ap", "bs", "as", "bx", "ax", "c", "z", "t"],
        "trade_fields": ["p", "s", "x", "c", "z", "t", "i"],
        "timestamp_convention": "exchange clock, RFC3339 UTC, "
                                "sub-millisecond; converted to US/Eastern "
                                "with the explicit post-2007 DST rule "
                                "because tzdata is absent in this "
                                "environment",
        "earliest_verified": "2016-01-05",
        "density_measured": {"AAPL_quotes_per_minute": ">10000",
                             "XLV_quotes_per_minute": 2581,
                             "SHW_quotes_per_minute": 44,
                             "AAPL_trades_per_session": ">120000"},
        "wholesale_acquisition": "INFEASIBLE and not attempted. A decade of "
                                 "NBBO for 230 symbols is order 10^10 "
                                 "records.",
        "population": "the 221 `reverted` exits of the frozen baseline, the "
                      "exact population H-0011's limit mechanism acted on",
        "limit_level_recovery": "trigger_close = exit_price / (F x (1-H)), "
                                "F = 1 - one_way_bps/10000, H = 0.00652; the "
                                "identity H-0012 already verified",
        "QUEUE_POSITION": "UNRECONSTRUCTIBLE, registered in advance. NBBO "
                          "shows displayed top-of-book size only, not the "
                          "book behind it nor where a hypothetical order "
                          "would sit. Fill probability may therefore be "
                          "BOUNDED, never point-estimated.",
        "fill_bound_rule": "displaced_volume = shares traded at or above the "
                           "limit while the order would be working. "
                           "Reported against the position's own share count. "
                           "A ratio far above 1 means a fill is near-certain "
                           "regardless of queue; a ratio near or below 1 is "
                           "reported as MARGINAL. No fill is ever asserted.",
        "condition_codes": "retained; abnormal/irregular conditions excluded "
                           "explicitly, not silently",
        "stability": "standing chronological thirds and the 2-of-3 rule",
        "what_is_NOT_done": ["any economic backtest", "any strategy change",
                             "any threshold search", "any feature selection",
                             "any ML model", "any clean-OOS use",
                             "any rerun or re-adjudication of H-0011",
                             "any use of the 0.652% haircut as a "
                             "microstructure execution cost"],
    },
    search_procedure=(
        "Two fixed measurements over one fixed population. No threshold is "
        "searched, no feature is selected on outcomes, no alternative window "
        "is tried and kept. If the fill bound proves uninformative, that is "
        "the result."),
    max_configurations=1,
    datasets=["decade (development) - the 221 reverted-exit sessions",
              "thirty_year: NOT USED. Access count stays at 13."],
    information_boundary=(
        "Every quote and trade used is timestamped on the exchange clock "
        "and only records at or after the order would have been placed are "
        "read for the fill bound; only records at or before the decision "
        "are read for spread state. No forward return is used anywhere in "
        "this audit - it measures information availability and execution "
        "feasibility, not profitability."),
    execution_assumptions=(
        "NONE ASSUMED. That is the point. The 0.652% production haircut is "
        "explicitly NOT applied as a microstructure execution cost, per "
        "H-0012 and H-0013 which showed it mixes timing with execution. "
        "Market-order crossing is measured from the actual quoted spread. "
        "Limit fills are NOT modelled; only bounded."),
    primary_metric=(
        "Distribution across the 221 reverted exits of displaced volume at "
        "or above the H-0011 limit level during the following session, "
        "expressed as a ratio to the position's own share count, together "
        "with the share of exits where no trade reached the level at all."),
    secondary_metrics=[
        "time of first touch relative to the session open",
        "share of exits with zero trades at or above the level",
        "quoted absolute and relative spread at the decision boundary",
        "displayed bid and ask size at the decision boundary",
        "chronological thirds for each of the above",
        "quote and trade condition-code distribution",
    ],
    acceptance_criteria=(
        "(A) GENUINE MICROSTRUCTURE CAPABILITY GAP: the data resolve "
        "H-0011's question - fill probability is boundable to a useful "
        "degree - AND spread/top-of-book state at the decision boundary is "
        "shown to carry information the 5-minute snapshots do not. "
        "(B) INFORMATION EXISTS, ECONOMIC EDGE NOT ESTABLISHED: the data "
        "are genuinely incremental but no robust tradable advantage is "
        "demonstrated here, which is the expected outcome given that no "
        "economic test is run under this seal. "
        "(C) MICROSTRUCTURE ADDS LITTLE: the accessible data prove "
        "redundant with the existing architecture. "
        "(D) DATA / EXECUTION LIMITATION: integrity or coverage prevents "
        "measurement. "
        "No fifth category. No outcome promotes anything. Outcome A or B "
        "licenses only the DESIGN of a separate sealed economic experiment, "
        "never its execution under this seal."),
    rejection_criteria=(
        "Explicitly NOT successes: a fill bound so wide it permits any "
        "conclusion; spread information that merely restates the 5-minute "
        "range; any result requiring an assumed queue position; any "
        "fabricated fill; any use of forward returns to choose what to "
        "measure."),
    robustness_requirements=[
        "baseline equivalence +58.5889000000% / 698 before any measurement",
        "queue-position limitation restated in every fill-related "
        "conclusion",
        "condition codes reported; abnormal conditions excluded explicitly",
        "chronological thirds reported",
        "H-0011 NOT rerun, NOT re-adjudicated, and its B classification "
        "left standing whatever this audit finds",
        "H-0015 and H-0016 frozen",
        "production fingerprint da22011e...c237b unchanged",
        "zero reads of the thirty-year dataset",
        "raw vendor payloads kept in the scratchpad, separate from derived "
        "research artefacts",
    ],
    complexity_penalty=(
        "Not applicable - no economic claim is made under this seal. The "
        "standing 2-point penalty would apply to any successor economic "
        "experiment."),
    required_oos_test=(
        "Not applicable to a capability audit; no model is fitted and no "
        "return is claimed. The clean forward record holds 0 sessions and "
        "is frozen until 2026-10-12, and is not touched. Ceiling: "
        "research_evidence."),
    promotion_requirements=[
        "H-0017 promotes nothing and changes no parameter",
        "any microstructure decision rule requires its own registration, a "
        "new fingerprint and a restarted forward evaluation",
        "H-0011, H-0012, H-0013, H-0014, H-0015 and H-0016 all remain "
        "frozen",
    ],
    kind="exploratory",
    hypothesis_id="H-0017",
)


def main():
    try:
        row = register(H0017)
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
    print("\nNo microstructure measurement performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
