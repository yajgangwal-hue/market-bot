"""Seal H-0021 before any give-back number is computed. Run once.

A DIAGNOSTIC, not a candidate. No exit rule is proposed, no parameter
is tested, no configuration is spent, nothing is promoted. It answers
one question the owner's exit-optimisation directive asks in section
13 and that this project has never answered:

    when a trade became substantially profitable and then gave the
    gain back, how much of that gain could the bot ACTUALLY have
    taken?

WHY THE QUESTION IS NOT ALREADY ANSWERED. EXP-0048 measured a CEILING
- every rule exit refilled at that session's HIGH - and recorded in
its own reason field that the day high is unknowable in advance and
must not be quoted as a gain. ClosedTrade.highest_high is likewise a
daily high. This bot decides on CLOSES and executes at the NEXT OPEN.
A peak it could never have transacted at is not a forgone profit, and
measuring give-back against one manufactures an opportunity that does
not exist.

SO THE PEAK IS MEASURED THREE WAYS, and they are never merged:
  PEAK_HIGH      highest intraday high while held. NOT EXECUTABLE.
                 Reported only as the bound EXP-0048 already
                 established, and labelled as such every time.
  PEAK_CLOSE     highest close while held. This is what the rule can
                 OBSERVE at a decision point.
  PEAK_NEXTOPEN  highest open on the session AFTER an observed close.
                 This is what the bot could actually have TRANSACTED,
                 and it is the only peak against which a give-back may
                 be called forgone profit.

THE HEADLINE GIVE-BACK NUMBER OF THIS REPORT IS THE PEAK_NEXTOPEN ONE.
The other two exist so that the gap between them is visible.

WHAT THE PRIOR LEDGER ALREADY SAYS, carried forward and not re-run:
54 configurations across 12 registered exit experiments, plus H-0011.
RSI exit regions (EXP-0023, 4 cfg, rejected - reversed over thirty
years). Holding cap (EXP-0019 3 cfg and EXP-0024 5 cfg, both rejected
- monotone in holding period, the edge is overnight). Stop width
(EXP-0022, 5 cfg, rejected). Trailing stops, partial profits, momentum
and regime exits (EXP-0036, 11 cfg, rejected - two cleared by
rounding). Real take profit at N x risk (EXP-0049/0050, 5 cfg - return
falls MONOTONICALLY as the target tightens). Regime-varying take
profit (EXP-0051/0052, 6 cfg - every variant trails no-take-profit on
return). The mechanism behind all of it is recorded: the top 50 trades
carry 67% of all profit, so any cap on the upside costs money.

H-0021 SPENDS ZERO ECONOMIC CONFIGURATIONS. It fits nothing, sweeps
nothing and compares nothing against the baseline, so it adds nothing
to the multiple-testing count. Any candidate it motivates must be
registered separately and must carry the 54 prior exit configurations
forward into its own DSR.

"NO EXPLOITABLE PATTERN" IS A FIRST-CLASS OUTCOME, and on the prior
evidence it is the likelier one.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0021 = Hypothesis(
    statement=(
        "A repeatable, EXECUTABLE population exists in which the frozen "
        "strategy lets a substantial gain build and then realises much less "
        "of it - where 'substantial' and 'executable' are both measured "
        "against prices the bot could have transacted at, namely the "
        "highest open on a session following an observed close. The "
        "diagnostic FINDS NOTHING - and the profit-protection branch closes "
        "- if the give-back against that executable peak is small, or is "
        "concentrated in trades the existing stop and RSI exit already "
        "handle, or is unstable across chronological thirds, or exists only "
        "against the intraday high that EXP-0048 already ruled unknowable."),
    rationale=(
        "The owner's directive asks whether profitable positions give back "
        "too much before exiting. This project has measured a ceiling at "
        "the daily high and has rejected every mechanism that caps the "
        "upside, because the top 50 trades carry 67% of all profit. What it "
        "has never measured is the give-back against a peak the bot could "
        "actually have transacted at. Without that, any profit-protection "
        "rule would be sized against an opportunity that may not exist."),
    rule=(
        "READ-ONLY over the frozen baseline's decade trades. The baseline "
        "must reproduce +58.5889000000% / 698 first or nothing is computed. "
        "For every closed trade, walk the daily bars from the entry session "
        "to the exit session and record, in units of the trade's own risk "
        "R = (entry - initial_stop) / entry: the three peaks, the maximum "
        "adverse excursion, the realised exit, and the give-back from each "
        "peak. Nothing is fitted. No rule is simulated. No exit is altered. "
        "No trade is excluded for any reason."),
    parameters={
        "peaks": {
            "PEAK_HIGH": "highest intraday high while held - NOT EXECUTABLE, "
                         "reported only as EXP-0048's established bound",
            "PEAK_CLOSE": "highest close while held - observable at a "
                          "decision point",
            "PEAK_NEXTOPEN": "highest open on a session following an "
                             "observed close - the only transactable peak, "
                             "and the headline"},
        "risk_unit": "R = (entry_price - initial_stop) / entry_price",
        "give_back_bands_FIXED": [0.5, 1.0, 2.0],
        "band_meaning": "trades whose PEAK_NEXTOPEN reached at least this "
                        "many R before the realised exit",
        "reported_splits": ["exit_reason", "chronological third",
                            "regime trend_dual_ma", "holding period",
                            "ATR fraction at entry", "RSI at exit",
                            "distance from SMA200 at entry"],
        "stops_treated_separately": "a stop fills when hit; the price is not "
                                    "a choice, so stop exits are reported "
                                    "apart and never counted as give-back "
                                    "the bot declined to take",
        "prior_ledger_carried_forward": {
            "exit_family_configurations": 54,
            "all_family_configurations": 187,
            "registered_exit_experiments": 12,
            "verdicts": "RSI exit rejected; holding cap rejected twice; stop "
                        "width rejected; trailing/partial/momentum/regime "
                        "rejected; take profit monotonically negative; "
                        "regime take profit trails no-take-profit",
            "mechanism": "top 50 trades carry 67% of all profit"},
        "configurations_spent_here": 0,
        "what_is_NOT_done": ["any exit rule", "any take profit", "any "
                             "trailing stop", "any parameter sweep",
                             "any comparison against the baseline",
                             "any candidate", "any promotion",
                             "any production change", "any clean-OOS access",
                             "any thirty-year read"],
    },
    search_procedure=(
        "One descriptive pass over the frozen trade list. The three peak "
        "definitions and the three R bands are fixed here and may not be "
        "added to, moved or reselected after results are seen. No "
        "population is defined after inspecting an outcome. No trade is "
        "removed."),
    max_configurations=0,
    datasets=["decade (development), the frozen baseline's own 698 trades",
              "thirty_year: NOT USED. Access count stays at 13."],
    information_boundary=(
        "Purely retrospective description of trades that already closed in "
        "the frozen baseline. Nothing here is used as an input to any "
        "decision, so there is no forward-information boundary to violate - "
        "and equally, no figure here may be presented as a return, an edge "
        "or an achievable gain. A peak identified with hindsight is a "
        "measurement, not an opportunity."),
    execution_assumptions=(
        "The frozen framework's own, unchanged. PEAK_HIGH is explicitly "
        "flagged as unexecutable wherever it appears. PEAK_NEXTOPEN assumes "
        "only that an order placed after an observed close could fill at "
        "the next open, which is exactly what the frozen entry mechanism "
        "already assumes. No spread, slippage or haircut is subtracted from "
        "a hypothetical improvement, because no improvement is claimed."),
    primary_metric=(
        "Realised exit as a fraction of PEAK_NEXTOPEN, in R, over the "
        "profitable trades - and the aggregate dollars given back from that "
        "executable peak, reported beside the same figure computed from "
        "PEAK_HIGH so the difference between the two is explicit."),
    secondary_metrics=[
        "full MFE and MAE distributions under all three peak definitions",
        "share of profitable trades that gave back more than half their "
        "executable peak gain",
        "counts and dollars in each fixed R band",
        "give-back by exit reason, with stops reported separately",
        "give-back by chronological third and by regime",
        "holding period, RSI at exit and ATR fraction for the give-back "
        "population against everything else",
        "concentration of the give-back by symbol, year and trade",
    ],
    acceptance_criteria=(
        "(A) A MATERIAL, EXECUTABLE GIVE-BACK POPULATION EXISTS: a "
        "substantial share of profitable trades reach a transactable peak "
        "well above their realised exit, the dollars are material against "
        "the standing two-point reference, and the pattern holds in at "
        "least 2 of 3 chronological thirds. "
        "(B) GIVE-BACK EXISTS BUT IS NOT SHOWN TO BE EXPLOITABLE. "
        "(C) NO MATERIAL EXECUTABLE GIVE-BACK. "
        "(D) MEASUREMENT LIMITATION. "
        "No fifth category. Outcome A licenses the DESIGN of one separately "
        "sealed exit candidate - which must carry the 54 prior exit "
        "configurations into its DSR - and authorises nothing else. No "
        "outcome changes an exit, a parameter or production."),
    rejection_criteria=(
        "Explicitly NOT successes: a large give-back measured against the "
        "intraday high, which EXP-0048 already established is unknowable in "
        "advance; give-back concentrated in stop exits, where the price was "
        "not a choice; a pattern visible in one chronological third; a "
        "give-back that disappears once the trades carrying the top of the "
        "profit distribution are seen for what they are; and any suggestion "
        "that capping the upside is free, when five registered experiments "
        "have measured that it is not."),
    robustness_requirements=[
        "baseline equivalence +58.5889000000% / 698 verified first",
        "the three peak definitions never merged or substituted",
        "PEAK_HIGH labelled unexecutable at every appearance",
        "stop exits reported separately from rule exits",
        "no trade excluded, no outlier removed",
        "chronological thirds and the 2-of-3 rule on every headline figure",
        "prior 54 exit configurations stated in the report",
        "H-0011 and every prior exit experiment left frozen and not "
        "reinterpreted",
        "fingerprint da22011e...c237b unchanged",
        "zero reads of the thirty-year dataset",
    ],
    complexity_penalty=(
        "The standing two percentage points, used as the reference for "
        "whether the executable give-back is material. Any rule that "
        "later tries to capture it must also clear it net of costs."),
    required_oos_test=(
        "None applicable; nothing is fitted and no return is claimed. NOTE "
        "FOR THE PROGRAMME THIS DIAGNOSTIC OPENS: the clean forward record "
        "holds 0 sessions and is frozen until 2026-10-12, so no candidate "
        "arising from this work can reach a clean out-of-sample test before "
        "that date. READY FOR CLEAN OOS is the best attainable "
        "classification until then. Ceiling: research_evidence."),
    promotion_requirements=[
        "H-0021 promotes nothing and changes no parameter",
        "outcome A licenses only the DESIGN of one sealed exit candidate",
        "any such candidate carries 54 prior exit configurations into DSR",
        "all prior experiments remain frozen and none is reinterpreted",
    ],
    kind="exploratory",
    hypothesis_id="H-0021",
)


def main():
    try:
        row = register(H0021)
    except RegistrationError as error:
        print("refused: {0}".format(error))
        return 1
    p = row["payload"]
    print("registered {0}".format(p["hypothesis_id"]))
    print("  seal    {0}".format(p["seal"]))
    print("  commit  {0}".format(p["code_commit"]))
    print("\nchain: {0}".format(verify_chain()))
    print("declared configurations: {0}".format(declared_trials()))
    print("\nNo give-back computed. No exit rule proposed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
