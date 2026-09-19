"""Seal H-0010 before any configuration is run. Run once.

PROVENANCE, STATED FIRST BECAUSE IT IS THE MAIN RISK.

On 2026-09-19 the owner asked for a 2% stop, a 5% take profit and a
2-session holding cap. All three were MEASURED before anything was
set, on this same decade, in a FIVE-configuration sweep:

    baseline                   +58.59%   Sharpe 0.5107   maxDD -12.98%
    hold 2 days only           -77.52%   Sharpe -2.3933  maxDD -77.89%
    stop ~2% only              +30.46%   Sharpe 0.2810   maxDD -26.71%
    stop ~2% + TP 5%           +77.84%   Sharpe 0.6040   maxDD -17.47%
    all three as asked         -78.57%   Sharpe -1.8493  maxDD -79.67%

The holding cap was abandoned on that evidence: a 2-session cap turns
1,747 of 1,821 trades into forced time-exits and collapses the
'reverted' bucket from 221 trades to 5. It forms no part of H-0010 and
max_holding_bars stays at 20.

H-0010 therefore carries a REAL AND UNUSUAL SELECTION COST: its
centre point was chosen after seeing its own decade result. That is
the opposite of the normal order and it cannot be undone. The family
below exists precisely to test whether that point is a gradient or a
spike, and the registered expectation is that it FAILS the drawdown
clause at the observed setting.

THE SECOND RISK, AND WHY CLAUSE E EXISTS. A take profit is a resting
LIMIT: portfolio.py fills it at its level, or at the open on a gap,
and - unlike 'reverted' and 'time_exit' - it pays NO 0.652% rule-exit
haircut. The observed configuration produced 335 take-profit exits.
Avoided haircut alone could plausibly exceed the entire +19.25-point
gain. That is legitimate modelling, because a resting limit really
does escape trigger-to-close drift, but it is an EXECUTION effect and
not evidence that tighter stops and profit targets select better
trades. Clause E forces the two apart.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0010 = Hypothesis(
    statement=(
        "Pairing a TIGHTER ATR-scaled stop with a 2.5R take profit raises "
        "decade total return above the frozen baseline WITHOUT breaching the "
        "standing 14.2806% drawdown ceiling, and the improvement survives "
        "after the avoided rule-exit haircut is attributed separately. The "
        "claim is about the payoff asymmetry, not about trading more: higher "
        "turnover, higher gross return or a gain that is wholly explained by "
        "haircut avoidance are each a rejection."),
    rationale=(
        "The frozen rule exits on RSI>=60, a 2.5-ATR stop or a 20-bar cap, "
        "and has no profit target. Its realised outcome is an average hold "
        "of 14.0 sessions capturing 11.2% of the mean favourable excursion, "
        "with the 'reverted' bucket carrying the entire book. A tighter stop "
        "with a fixed reward-to-risk target converts that into a different "
        "payoff shape - more, smaller losses against fewer, larger wins - "
        "and the measured point showed win rate falling to 36.17% while "
        "profit factor held at 1.203. Whether that shape is a real "
        "improvement or one favourable draw is what the family tests."),
    rule=(
        "Two parameters move together and nothing else does. "
        "MeanReversionConfig.stop_atr_multiple is reduced from 2.5 to the "
        "registered value, and run_portfolio's existing mr_take_profit_r is "
        "set to 2.5, both through the mr_config / keyword override path so "
        "no production file is edited. The take profit is a resting limit at "
        "raw_entry + 2.5 x risk_per_share, filled at its level or at the "
        "open on a gap, evaluated BEFORE the RSI exit, and it pays no "
        "rule-exit haircut. UNCHANGED: rsi_entry 35.0, rsi_exit 60.0, "
        "max_holding_bars 20, the correlation-bucket cap of 1, the "
        "12-position cap, the 3-entries-per-day cap, risk_per_trade 0.005, "
        "max_notional_fraction 0.20, the 2% ADV participation cap, costs, "
        "slippage, the 0.652% haircut on reverted and time_exit, the "
        "universe, the benchmark and candidate ordering."),
    parameters={
        "parameters_moved": ["MeanReversionConfig.stop_atr_multiple",
                             "run_portfolio.mr_take_profit_r"],
        "take_profit_r": 2.5,
        "stop_atr_multiple": {"A": 0.917, "B": 1.25, "C": 1.75},
        "baseline_stop_atr_multiple": 2.5,
        "why_these_three": "A is the observed point: 0.917 x ATR centres the "
                           "average stop near 2% of price, which is what the "
                           "owner asked for, and 2.5R against a 2% stop is "
                           "the requested 5% target. B and C widen the stop "
                           "while holding the 2.5 reward-to-risk fixed, so "
                           "the family is a one-dimensional gradient on stop "
                           "width. No fourth value may be added.",
        "fixed_percentage_stop_not_available":
            "A literal fixed 2% stop is NOT expressible in configuration. "
            "The stop is entry - multiple x ATR(14), so its distance is "
            "volatility-dependent: 2.99% of price in the tightest ATR "
            "quartile and 7.73% in the widest. An exact fixed 2% would "
            "require editing mean_reversion.evaluate, a production change, "
            "and is deliberately NOT part of H-0010.",
        "holding_cap": "UNCHANGED at 20. The owner's requested 2-session cap "
                       "was measured at -77.52% standalone and -78.57% "
                       "combined, and is excluded on that evidence.",
        "provenance": "SEVERE AND DISCLOSED. Configuration A's decade result "
                      "was seen BEFORE this registration was written, in a "
                      "five-configuration sweep run at the owner's request. "
                      "A may not be read as a pre-registered result. B and C "
                      "have never been run. The family's purpose is to "
                      "establish whether A is a point on a gradient or a "
                      "spike, and B and C carry the evidential weight.",
        "declared_direction": {
            "stop_rate": "FALLS monotonically as the stop widens",
            "turnover": "FALLS monotonically as the stop widens",
            "max_drawdown": "SHALLOWS monotonically as the stop widens, "
                            "because equal-risk sizing holds dollar risk per "
                            "trade roughly constant while a wider stop is "
                            "hit less often",
            "total_return": "AMBIGUOUS and deliberately not predicted"},
    },
    search_procedure=(
        "Exactly three configurations, once each, decade only. The take "
        "profit is fixed at 2.5R throughout and may not be varied. No "
        "intermediate stop multiple may be added after the surface is "
        "visible. No holding-cap change, no entry change, no sizing change, "
        "no ranking change, no regime condition. A result suggesting any of "
        "those requires its own registration."),
    max_configurations=3,
    datasets=["decade (development)",
              "thirty_year: NOT USED. H-0010 does not read it and its access "
              "count stays at 13."],
    information_boundary=(
        "Daily bars through the decision bar, exactly as production. The "
        "take-profit level is set from the entry price and the initial risk "
        "per share, both known at entry. No forward information enters."),
    execution_assumptions=(
        "Frozen production candidate except the two registered parameters: "
        "market order at the signal close, gapped stops fill at the open, "
        "2 bps half spread + 4 bps slippage each way, $0 commission, whole "
        "shares, 3 entries per day, 20% per name, 2% ADV cap, 0.652% "
        "rule-exit haircut on reverted and time_exit ONLY, idle cash at 0%. "
        "The take profit is a resting limit and pays no haircut, which is "
        "correct modelling and is the subject of clause E."),
    primary_metric=(
        "Decade total return net of costs, versus the frozen baseline's "
        "+58.5889%, reported alongside cumulative excess return versus SPY "
        "price-only over the identical window."),
    secondary_metrics=[
        "CAGR", "annualised volatility", "Sharpe", "Sortino", "max drawdown",
        "Calmar", "trades", "win rate", "average winner", "average loser",
        "profit factor", "expectancy", "turnover", "transaction costs",
        "exposure", "average holding days", "stop rate",
        "exit-reason mix including take_profit count",
        "year-by-year total return",
        "P&L attributable to avoided rule-exit haircut",
        "P&L net of that attribution",
        "mean and median R multiple", "worst trade", "longest losing run",
    ],
    acceptance_criteria=(
        "ALL FIVE. "
        "(A) RETURN: total return exceeds the baseline's +58.5889% by MORE "
        "THAN 2 percentage points, the standing complexity penalty. "
        "(B) DRAWDOWN: abs(max_drawdown) <= 1.10 x abs(-12.9824%) = "
        "14.2806%. THE CEILING IS NOT RELAXED FOR ANY REASON, INCLUDING A "
        "LARGE RETURN. "
        "(C) GRADIENT, NOT SPIKE: across the three stop multiples the return "
        "deltas versus baseline must not be dominated by one point - the "
        "largest positive delta <= 2.5x the second-largest positive delta, "
        "the constant H-0005 and H-0009 used. A configuration that passes "
        "alone while both neighbours fail is recorded as a SPIKE and "
        "rejected, and configuration A passing alone is the specific case "
        "this clause exists to catch. "
        "(D) ROBUSTNESS: the passing configuration beats the baseline in at "
        "least 7 of 11 calendar years AND remains above baseline with its "
        "single best calendar year removed. "
        "(E) NOT MERELY HAIRCUT AVOIDANCE: the take-profit exits pay no "
        "0.652% rule-exit haircut. Compute the haircut that those exits "
        "would have paid had they been rule exits, subtract it from the "
        "configuration's P&L, and the remaining improvement must STILL "
        "exceed the 2-point penalty. A gain wholly explained by avoided "
        "haircut is an execution effect, not selection edge, and is "
        "rejected under this clause while being recorded as an execution "
        "finding in its own right. "
        "Acceptance yields research_evidence. It does NOT promote: changing "
        "the stop or adding a take profit is a production change requiring "
        "its own registration, a new fingerprint and a restarted forward "
        "evaluation."),
    rejection_criteria=(
        "Any clause fails. THE REGISTERED EXPECTATION IS THAT "
        "CONFIGURATION A FAILS CLAUSE B: it was measured at -17.47% against "
        "a 14.2806% ceiling, over by 3.19 points. The open question is "
        "whether B or C recover the return while staying inside the "
        "ceiling. Higher turnover, higher gross return, higher exposure, a "
        "better Sharpe arising from a volatility denominator, or one strong "
        "year are each explicitly INSUFFICIENT. If the whole family fails, "
        "the finding is that the observed +19.25 points is not reachable "
        "within the risk budget, which closes the stop/take-profit "
        "direction rather than inviting a fourth configuration."),
    robustness_requirements=[
        "equivalence: the frozen baseline reproduces +58.5889% over 698 "
        "trades through the same override path before any configuration runs",
        "three stop multiples form the gradient; a lone passing "
        "configuration with failing neighbours is a spike",
        "year-by-year reported, 2025 included and never removed after the "
        "fact",
        "leave-one-best-year-out",
        "haircut-avoidance attributed and subtracted (clause E)",
        "turnover and transaction costs reported, since the observed point "
        "more than doubled both",
        "exit-reason mix reported, so a collapse of the 'reverted' bucket "
        "cannot hide inside an aggregate",
        "zero reads of the thirty-year dataset",
    ],
    complexity_penalty=(
        "Two percentage points of decade total return. The configuration "
        "adds a second exit mechanism to the money path and more than "
        "doubles turnover, so a marginal reading does not justify it."),
    required_oos_test=(
        "None available and none claimed. The decade is contaminated for "
        "this candidate, and configuration A is contaminated twice over "
        "because its result was seen before registration. The thirty-year "
        "window is contaminated robustness evidence at 13 reads and is NOT "
        "touched. The clean forward record holds 0 sessions. Ceiling: "
        "research_evidence."),
    promotion_requirements=[
        "H-0010 alone can promote nothing",
        "a passing configuration is at most an adjudication candidate, and "
        "configuration A cannot be one on its own given its provenance",
        "changing the stop or adding a take profit in production requires "
        "its own registration, a new strategy fingerprint and a restarted "
        "forward evaluation",
        "the 14.2806% ceiling applies unchanged to any later promotion",
    ],
    kind="confirmatory",
    hypothesis_id="H-0010",
)


def main():
    try:
        row = register(H0010)
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
