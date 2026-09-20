"""Seal H-0014 before any intraday information test. Run once.

WHAT THIS IS. A capability audit of TEMPORAL RESOLUTION. It asks
whether compressing a session into one daily OHLCV bar destroys
information the strategy could act on, and it is designed so that
"no, it does not" is a clean, publishable outcome.

IT IS NOT a parameter search. No threshold, stop, target, holding
period, ATR floor, size, ranker cutoff or regime boundary is varied.
The frozen rule is held exactly as production defines it and the ONLY
thing introduced is EARLIER INFORMATION AVAILABILITY.

WHY NOW. H-0013 closed the execution-accounting question at 5-minute
resolution: time_exit drift is statistically zero, the reverted
category resists every point-in-time conditioner available, and
further precision there needs quote data. The remaining open question
from the capability audit is bottleneck B - temporal resolution - and
this is its direct test.

THE PREDECLARED COMPARISON, fixed here so it cannot be chosen later.
At an intraday snapshot time T on session D the two representations
are:

  DAILY REPRESENTATION - everything the production strategy actually
  has at time T, which is bars through the PRIOR session's close only.
  RSI(14), ATR(14), SMA(200), ADV, momentum, drawdown, all computed on
  daily closes up to D-1.

  INTRADAY REPRESENTATION - the same, PLUS features computed from
  5-minute bars of session D up to and including the bar ending at T.

The test is whether the second contains information about forward
outcomes that the first does not. Nothing else.

NEGATIVE RESULT IS A REAL OUTCOME. If intraday features add little
out-of-sample information, or path ordering does not separate
outcomes, or apparent gains vanish after costs or portfolio
constraints, the registered conclusion is that temporal resolution is
NOT the main missing edge and the programme should move to another
information source.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0014 = Hypothesis(
    statement=(
        "Compressing a trading session into a single daily OHLCV bar "
        "destroys information that is (i) measurable, (ii) available "
        "point-in-time during the session, and (iii) predictive of "
        "subsequent SPY-relative return out of sample. The hypothesis "
        "FAILS if intraday features add no incremental out-of-sample rank "
        "information over the daily representation, or if the increment is "
        "not stable across chronological thirds, or if intraday candidates "
        "merely reproduce the existing daily candidates. A negative result "
        "establishes that temporal resolution is not the main missing edge "
        "and closes bottleneck B."),
    rationale=(
        "The capability audit measured that price traverses 2.01x the net "
        "daily move, that a close-only RSI misses 18,698 symbol-sessions "
        "where its own condition held intraday (45% more than it sees), and "
        "that the best daily feature explains only R2=17.7% of when a rule "
        "actually fired. Those are information-capacity facts. None of them "
        "shows that the lost information is PREDICTIVE or TRADEABLE, and "
        "this experiment is the difference between those claims."),
    rule=(
        "The frozen strategy is held fixed in every respect: the same 230 "
        "symbol universe, rsi_entry 35.0, rsi_exit 60.0, stop 2.5xATR, "
        "20-session cap, bucket cap 1, 12-position cap, 3 entries/day, "
        "risk_per_trade 0.005, 20% notional, 2% ADV, the same cost model "
        "and the same 0.652% rule-exit haircut. NOTHING in the decision "
        "rule changes and no production file is modified. The single "
        "intervention is that features may be observed at intraday "
        "snapshots instead of only at the close. "
        "SNAPSHOTS, fixed: 09:35, 09:45, 10:00, 10:30, 11:00, 12:00, 13:00, "
        "14:00, 15:00, 15:30 US/Eastern, each using only 5-minute bars "
        "whose close is at or before the snapshot. "
        "FEATURES, fixed, all with an explicit availability timestamp equal "
        "to the snapshot: return from prior close; return from session "
        "open; high and low excursion so far; distance from session VWAP; "
        "intraday range so far; short-window (15m) and medium-window (60m) "
        "return; acceleration as the difference of those two; reversal from "
        "the session high and from the session low; realised 5-minute "
        "volatility so far; range expansion versus the prior 20-session "
        "average true range; cumulative volume versus the same symbol's "
        "trailing 20-session volume at the same time of day; volume "
        "acceleration; SPY intraday return to the snapshot; SPY realised "
        "intraday volatility to the snapshot."),
    parameters={
        "snapshots_et": ["09:35", "09:45", "10:00", "10:30", "11:00",
                         "12:00", "13:00", "14:00", "15:00", "15:30"],
        "universe": "the existing fixed 230-symbol decade set; no symbol "
                    "added, removed or substituted",
        "PRIMARY_TEST": "Spearman rank information coefficient (IC) between "
                        "a predeclared linear score and forward SPY-relative "
                        "return, computed OUT OF SAMPLE by chronological "
                        "third: fit on earlier thirds, score the next. The "
                        "project already uses Spearman for rank agreement, "
                        "so no new statistic is introduced.",
        "MODEL_FORM": "ordinary least squares on standardised features, no "
                      "regularisation search, no interaction terms, no "
                      "feature selection after seeing results. Two nested "
                      "specifications only: DAILY (prior-close features) and "
                      "DAILY+INTRADAY. The increment is IC(daily+intraday) "
                      "minus IC(daily).",
        "FORWARD_HORIZONS": [5, 10, 20],
        "horizon_rule": "All three are reported. The PRIMARY is 10 sessions, "
                        "fixed here because it is the horizon nearest the "
                        "frozen strategy's realised 13.97-session average "
                        "hold. A horizon may NOT be chosen after seeing "
                        "results.",
        "PATH_CLASSES": ["selloff_then_recovery", "recovery_then_selloff",
                         "early_low_persistent_strength",
                         "late_low_close_near_low", "high_low_recovery",
                         "low_high_fade", "unclassified"],
        "path_rule": "Classes are assigned from the ORDER of the session's "
                     "extremes and the close position, using only that "
                     "session's bars. Sessions with the SAME daily OHLCV "
                     "signature may fall in different classes - that is the "
                     "point of the test.",
        "classification_A_B_C_D": {
            "A": "eventual daily RSI<=35 signal already detectable at the "
                 "snapshot",
            "B": "eventual daily signal only detectable later",
            "C": "intraday dislocation that the closing daily signal never "
                 "represents",
            "D": "intraday condition appears and the eventual daily signal "
                 "does not fire"},
        "STABILITY_REQUIREMENT": "any positive increment must hold in at "
                                 "least 2 of 3 chronological thirds. An "
                                 "increment carried by one period is "
                                 "recorded as NOT stable.",
        "MATERIALITY": "the project's standing 2-percentage-point complexity "
                       "penalty governs any economic claim; for the "
                       "information test the increment must additionally be "
                       "stable per the requirement above. No new threshold "
                       "is invented.",
        "what_is_NOT_varied": ["rsi_entry", "rsi_exit", "stop multiple",
                               "take profit", "holding period", "ATR floor",
                               "position size", "bucket cap", "max positions",
                               "ranker", "veto", "regime cutoffs",
                               "the 0.652% haircut"],
    },
    search_procedure=(
        "Ten fixed snapshots, one fixed feature set, one fixed model form, "
        "three reported horizons with the primary fixed in advance, one "
        "fixed path taxonomy. No sweep of any kind. No feature added or "
        "dropped after results are visible. The portfolio-interaction "
        "analysis in section 9 is descriptive and may not be used to select "
        "anything."),
    max_configurations=1,
    datasets=["decade (development)",
              "5-minute intraday for the fixed 230-symbol universe plus SPY",
              "thirty_year: NOT USED. Access count stays at 13."],
    information_boundary=(
        "At snapshot T on session D only bars whose close is at or before T "
        "may enter any feature, and daily features use closes through D-1 "
        "ONLY - session D's close is future information at every snapshot "
        "and is never read. Forward outcomes start from the snapshot and "
        "run forward; they are targets, never inputs. Trailing "
        "normalisations use the prior 20 sessions strictly before D. The "
        "out-of-sample split is chronological, so no later third informs an "
        "earlier one."),
    execution_assumptions=(
        "Unchanged from production: market order at the signal close for "
        "entries, gapped stops fill at the open, 2 bps half spread + 4 bps "
        "slippage each way, whole shares, 3 entries per day, 20% per name, "
        "2% ADV cap, 0.652% rule-exit haircut on reverted and time_exit. "
        "MEASURABILITY LIMIT restated: 5-minute OHLCV supports market-order "
        "reasoning only. It cannot establish queue position, displayed "
        "liquidity or limit-fill probability, so no conclusion here may be "
        "read as validating H-0011's limit behaviour."),
    primary_metric=(
        "Out-of-sample Spearman IC increment at the 10-session horizon: "
        "IC(daily + intraday) minus IC(daily alone), by snapshot, reported "
        "per chronological third."),
    secondary_metrics=[
        "IC at 5 and 20 sessions",
        "counts and percentages in classes A, B, C, D",
        "forward SPY-relative return, MFE and MAE by class",
        "forward outcomes by path class",
        "candidates per snapshot and conversion to the eventual daily signal",
        "signals invisible until the close",
        "intraday candidates that disappear before the close",
        "portfolio conflicts: bucket collisions, 12-position headroom, slot "
        "competition from earlier entry",
        "all of the above by chronological third",
    ],
    acceptance_criteria=(
        "(A) STRONG INTRADAY INFORMATION GAP: a positive out-of-sample IC "
        "increment at the primary horizon, stable in at least 2 of 3 "
        "chronological thirds, AND a materially non-empty class C - "
        "intraday dislocations the daily signal never represents - with "
        "forward SPY-relative return distinguishable from the class-D "
        "false-signal population. "
        "(B) INFORMATION EXISTS, EDGE NOT DEMONSTRATED: a stable IC "
        "increment but class C does not separate economically, or the "
        "separation does not survive the cost and portfolio-constraint "
        "descriptions. "
        "(C) INTRADAY RESOLUTION ADDS LITTLE: no stable IC increment and no "
        "economically separable class C. Temporal resolution is then NOT "
        "the main bottleneck and the programme moves to another information "
        "source. "
        "(D) DATA/EXECUTION LIMITATION: information and execution effects "
        "cannot be distinguished with the available data. "
        "No outcome promotes anything, changes any trading rule, or alters "
        "any prior adjudication. Outcome A licenses only the DESIGN of a "
        "separate, smaller economic experiment - not its execution."),
    rejection_criteria=(
        "Outcomes C and D reject the hypothesis and are acceptable "
        "registered results. Explicitly NOT successes: an IC increment "
        "carried by a single chronological third; a class C that merely "
        "re-labels existing daily candidates; gains that vanish under the "
        "existing cost framework; an improvement that exists only because a "
        "horizon or snapshot was chosen after seeing results; any narrowing "
        "to a favourable subset of dates, symbols or sectors."),
    robustness_requirements=[
        "baseline equivalence +58.5889000000% over 698 trades reproduced "
        "before any intraday result",
        "every feature carries an explicit availability timestamp and no "
        "session-D close is read at any snapshot",
        "out-of-sample split is chronological, never random",
        "results reported per chronological third, never pooled away",
        "all three forward horizons reported with the primary fixed in "
        "advance",
        "class C separated from class D explicitly",
        "portfolio conflicts reported, not assumed away",
        "queue and limit-fill limits restated",
        "production fingerprint da22011e...c237b unchanged",
        "H-0011, H-0012 and H-0013 all remain frozen",
        "zero reads of the thirty-year dataset",
    ],
    complexity_penalty=(
        "Two percentage points of decade total return for any economic "
        "claim, the standing constant. For the information test the "
        "corresponding discipline is the stability requirement: an "
        "increment must appear in at least 2 of 3 thirds to count."),
    required_oos_test=(
        "The chronological third-wise split IS the out-of-sample test and "
        "is the point of the experiment. The decade remains development "
        "data. The thirty-year window is NOT touched. The clean forward "
        "record holds 0 sessions and is frozen until 2026-10-12. Ceiling: "
        "research_evidence."),
    promotion_requirements=[
        "H-0014 promotes nothing and changes no trading behaviour",
        "outcome A licenses designing a separate economic experiment; that "
        "experiment requires its own registration before it is run",
        "any intraday decision engine would require its own registration, a "
        "new strategy fingerprint and a restarted forward evaluation",
        "H-0011, H-0012 and H-0013 remain frozen",
    ],
    kind="exploratory",
    hypothesis_id="H-0014",
)


def main():
    try:
        row = register(H0014)
    except RegistrationError as error:
        print("refused: {0}".format(error))
        return 1
    p = row["payload"]
    print("registered {0}".format(p["hypothesis_id"]))
    print("  seal    {0}".format(p["seal"]))
    print("  commit  {0}".format(p["code_commit"]))
    print("  when    {0}".format(p["registered_at"]))
    print("\nchain: {0}".format(verify_chain()))
    print("declared configurations across all registrations: {0}".format(
        declared_trials()))
    print("\nNo intraday information result has been computed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
