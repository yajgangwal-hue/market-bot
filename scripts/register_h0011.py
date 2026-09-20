"""Seal H-0011 before any configuration is run. Run once.

PROVENANCE, STATED FIRST.

H-0010 rejected a tighter stop plus a 2.5R take profit on three
clauses, and its clause E found why the configuration had looked good:
take-profit exits are resting LIMITS and pay no 0.652% rule-exit
haircut, worth $58,857 across 987 trades - 3.06x the entire gain. That
was recorded as an EXECUTION finding needing its own registration.
This is it.

The three day-trading surveys of 2026-09-19 then established, from an
entirely separate literature, that this same mechanism is what
separates the persistently profitable minority from everyone else: the
top of the intraday distribution is paid the spread rather than paying
it, and Sharpe scales as (edge/noise) x sqrt(N) ONLY once cost per
trade is driven to roughly zero. Against this bot's own CostModel the
maker/taker swing is 16.5 bps per round trip.

SO THE DIRECTION IS WELL MOTIVATED AND THE PRIOR MEASUREMENT IS
BIASED UPWARD. H-0010 counted the avoided haircut and nothing else. A
resting limit is not free: it is an option written to the market, and
it is exercised against you in two ways that a naive limit backtest
books as profit.

  NON-FILL. Price never reaches the offer. You keep the exposure the
  rule told you to shed, and you cross later at a worse price, having
  paid the haircut anyway.

  ADVERSE SELECTION. You fill on sessions price rose into your offer
  and miss on sessions it fell away from it. Fills therefore land on
  the good outcomes and non-fills on the bad ones. The difference
  between those two populations is not edge; it is the option premium
  being collected from you.

Clause E below exists to charge both. The registered expectation is
that the mechanism is REAL but SMALLER than H-0010 implied, and the
honest question is whether what remains clears the 2-point penalty.

NO CONFIGURATION IN THIS FAMILY HAS BEEN RUN. Unlike H-0010, whose
centre point was seen before registration, H-0011 is sealed blind.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0011 = Hypothesis(
    statement=(
        "Replacing the market-order RSI exit with a resting sell LIMIT at "
        "the trigger close raises decade total return above the frozen "
        "baseline, AND the improvement survives once non-fills and adverse "
        "selection are charged against it. The claim is about EXECUTION, "
        "not selection: the entry rule, the stop, the holding cap and the "
        "sizing are all untouched, so any change in return can only come "
        "from how the same exits are filled. A gain that disappears when "
        "the cost of not being filled is priced is a rejection."),
    rationale=(
        "The frozen rule exits `reverted` at the close and is charged a "
        "0.652% trigger-to-close haircut, because the live bot crosses the "
        "spread the moment the rule fires. H-0010 incidentally measured "
        "what happens when an exit is a resting limit instead: $58,857 of "
        "haircut avoided across 987 trades, larger than any strategy "
        "effect in 39 experiments. The microstructure literature says the "
        "same thing from the other direction - passive high-frequency "
        "trading is profitable even without rebates while aggressive is "
        "not, and the top six firms in a latency race win over 80% of it. "
        "But H-0010 priced only the benefit. A resting limit also writes "
        "an option to the market. This measures the net."),
    rule=(
        "ONE parameter moves and nothing else does. run_portfolio's "
        "mr_limit_exit is set to (offset, patience). When the RSI exit "
        "condition fires (strength >= rsi_exit 60.0) the position is NOT "
        "sold; a resting sell limit is armed at trigger_close x (1 + "
        "offset) and works for `patience` sessions starting the NEXT "
        "session. On each working session, AFTER the stop is checked so a "
        "bar spanning both is resolved adversely: fill at the open if the "
        "open is at or above the level, else fill at the level if the high "
        "reaches it, else spend one session of patience. When patience is "
        "exhausted - or when bars_held reaches max_holding_bars, so the "
        "20-bar cap stays hard - the position is sold at the close and IS "
        "charged the 0.652% haircut, recorded as `limit_lapsed`. "
        "UNCHANGED: rsi_entry 35.0, rsi_exit 60.0, stop_atr_multiple 2.5, "
        "max_holding_bars 20, the correlation-bucket cap of 1, the "
        "12-position cap, 3 entries per day, risk_per_trade 0.005, "
        "max_notional_fraction 0.20, the 2% ADV cap, costs, slippage, the "
        "universe, the benchmark, candidate ordering, and the haircut "
        "itself on time_exit and on lapsed limits."),
    parameters={
        "parameters_moved": ["run_portfolio.mr_limit_exit"],
        "offset": 0.0,
        "patience_sessions": {"A": 1, "B": 2, "C": 3},
        "why_offset_zero": "A limit AT the trigger close asks the narrowest "
                           "possible question: same price, maker instead of "
                           "taker. Any positive offset also asks the "
                           "trader to forecast, which confounds execution "
                           "with selection. Offset is FIXED at 0.0 and may "
                           "not be varied; the gradient is patience alone, "
                           "so the family stays one-dimensional.",
        "why_patience_is_the_gradient": "Patience is the direct dial on the "
                                        "cost side. More patience raises the "
                                        "fill rate and lowers lapses, but "
                                        "holds unwanted exposure longer. If "
                                        "the mechanism is real the deltas "
                                        "should move smoothly across 1, 2, "
                                        "3. No fourth value may be added.",
        "provenance": "CLEAN. No configuration in this family has been run. "
                      "The mechanism's DIRECTION was suggested by H-0010's "
                      "clause E, which is disclosed, but no limit-exit "
                      "configuration has ever been measured on this data.",
        "declared_direction": {
            "fill_rate": "RISES monotonically with patience",
            "limit_lapsed_count": "FALLS monotonically with patience",
            "average_hold_days": "RISES with patience, by less than the "
                                 "patience itself, because many limits fill "
                                 "on the first working session",
            "haircut_paid": "FALLS relative to baseline, because filled "
                            "exits pay none",
            "total_return": "AMBIGUOUS and deliberately not predicted. The "
                            "registered EXPECTATION is that the gross gain "
                            "is real but materially smaller than the "
                            "$58,857 H-0010 implied, because that figure "
                            "priced only the benefit side."},
    },
    search_procedure=(
        "Exactly three configurations, once each, decade only. Offset is "
        "fixed at 0.0 throughout. No intermediate or fourth patience value "
        "may be added after the surface is visible. No entry change, no "
        "stop change, no holding-cap change, no sizing change, no ranking "
        "change, no regime condition, no change to the haircut. A result "
        "suggesting any of those requires its own registration."),
    max_configurations=3,
    datasets=["decade (development)",
              "thirty_year: NOT USED. H-0011 does not read it and its "
              "access count stays at 13."],
    information_boundary=(
        "Daily bars through the decision bar, exactly as production. The "
        "limit level is set from the trigger session's close, known at the "
        "moment the rule fires. Fill resolution uses only the open, high "
        "and low of sessions AFTER the order was placed. No forward "
        "information enters. The one modelling assumption is that a bar "
        "whose high reaches the level would have filled a resting order at "
        "that level, which is the same assumption the existing take-profit "
        "and mr_partial paths already make."),
    execution_assumptions=(
        "Frozen production candidate except the one registered parameter: "
        "market order at the signal close on entry, gapped stops fill at "
        "the open, 2 bps half spread + 4 bps slippage each way, $0 "
        "commission, whole shares, 3 entries per day, 20% per name, 2% ADV "
        "cap, idle cash at 0%. The 0.652% rule-exit haircut is charged on "
        "time_exit and on limit_lapsed, and NOT on limit_exit, which is "
        "the whole point of the experiment. NO maker rebate is assumed: "
        "the modelled benefit is escaping the haircut only, not being paid "
        "to provide liquidity, because this bot has no rebate "
        "relationship. Queue position is not modelled and cannot be on "
        "daily bars - see the required disclosure in clause E."),
    primary_metric=(
        "Decade total return net of costs, versus the frozen baseline's "
        "+58.5889%, reported alongside cumulative excess return versus SPY "
        "price-only over the identical window."),
    secondary_metrics=[
        "CAGR", "annualised volatility", "Sharpe", "Sortino", "max drawdown",
        "Calmar", "trades", "win rate", "profit factor", "expectancy",
        "turnover", "transaction costs", "exposure", "average holding days",
        "stop rate", "exit-reason mix including limit_exit and limit_lapsed",
        "FILL RATE: limit_exit / (limit_exit + limit_lapsed)",
        "haircut avoided on filled exits, in dollars",
        "realised P&L of FILLED exits vs the same trades exited at the "
        "trigger close as market orders",
        "realised P&L of LAPSED exits vs the same trades exited at the "
        "trigger close as market orders",
        "year-by-year total return",
        "mean and median R multiple", "worst trade",
    ],
    acceptance_criteria=(
        "ALL FIVE. "
        "(A) RETURN: total return exceeds the baseline's +58.5889% by MORE "
        "THAN 2 percentage points, the standing complexity penalty. "
        "(B) DRAWDOWN: abs(max_drawdown) <= 1.10 x abs(-12.9824%) = "
        "14.2806%. THE CEILING IS NOT RELAXED FOR ANY REASON. Holding "
        "unwanted exposure while an order works is precisely the kind of "
        "change that can deepen a drawdown, so this clause is load-bearing "
        "here rather than a formality. "
        "(C) GRADIENT, NOT SPIKE: across the three patience values the "
        "return deltas versus baseline must not be dominated by one point "
        "- the largest positive delta <= 2.5x the second-largest positive "
        "delta, the constant H-0005, H-0009 and H-0010 used. "
        "(D) ROBUSTNESS: the passing configuration beats the baseline in "
        "at least 7 of 11 calendar years AND remains above baseline with "
        "its single best calendar year removed. "
        "(E) ADVERSE SELECTION MUST BE PRICED, NOT ASSUMED AWAY. This is "
        "the clause the experiment exists for, and it is the correction to "
        "H-0010, which measured only avoided haircut. Split every armed "
        "order into FILLED and LAPSED. For each group compute the "
        "counterfactual: what that same trade would have realised had it "
        "been sold at the trigger close as a market order, haircut "
        "included. The experiment passes only if TOTAL (filled gain + "
        "lapsed loss) still exceeds the 2-point penalty. If the filled "
        "group gains while the lapsed group loses more, the mechanism is "
        "transferring money from the trades you could not get out of to "
        "the ones you could, and it is REJECTED however good the headline "
        "looks. Additionally the adjudication MUST disclose, and must not "
        "net out, that queue position is unmodelled: on daily bars a bar "
        "whose high touches the level is assumed to fill, which overstates "
        "the fill rate by an unknown amount. A configuration that passes "
        "only by a margin smaller than that disclosed uncertainty is "
        "recorded as INCONCLUSIVE, not as a pass. "
        "Acceptance yields research_evidence. It does NOT promote: routing "
        "exits as limits is a production change requiring its own "
        "registration, a new fingerprint and a restarted forward "
        "evaluation."),
    rejection_criteria=(
        "Any clause fails. Specific rejections that are NOT successes: a "
        "gain arising because lapsed positions happened to recover in this "
        "decade; a gain concentrated in one year; a higher Sharpe arising "
        "from a smaller volatility denominator; a lower drawdown arising "
        "from lower exposure; a fill rate so high it implies the daily-bar "
        "fill assumption is doing the work. If the whole family fails, the "
        "finding is that the $58,857 H-0010 measured is not net-realisable "
        "on this rule, which CLOSES the limit-exit direction and with it "
        "the last lead the day-trading research identified."),
    robustness_requirements=[
        "equivalence: the frozen baseline reproduces +58.5889% over 698 "
        "trades through the same override path before any configuration "
        "runs, and mr_limit_exit=None must be byte-identical to production",
        "strategy fingerprint da22011e...c237b unchanged throughout",
        "three patience values form the gradient; a lone passing "
        "configuration with failing neighbours is a spike",
        "year-by-year reported, 2025 included and never removed after the "
        "fact",
        "leave-one-best-year-out",
        "filled vs lapsed counterfactuals reported separately (clause E)",
        "fill rate reported, with the daily-bar fill assumption disclosed "
        "as an upward bias of unknown size",
        "exit-reason mix reported, so a collapse of one bucket cannot hide "
        "inside an aggregate",
        "20-bar holding cap verified never exceeded",
        "zero reads of the thirty-year dataset",
    ],
    complexity_penalty=(
        "Two percentage points of decade total return. The change adds a "
        "resting order and a patience counter to the money path, and it "
        "introduces a state where the strategy wants to be flat and is "
        "not, which is a genuinely new risk the frozen rule does not have."),
    required_oos_test=(
        "None available and none claimed. The decade is development data. "
        "The thirty-year window is contaminated robustness evidence at 13 "
        "reads and is NOT touched. The clean forward record holds 0 "
        "sessions and the forward evaluation is frozen until 2026-10-12. "
        "Ceiling: research_evidence."),
    promotion_requirements=[
        "H-0011 alone can promote nothing",
        "a passing configuration is at most an adjudication candidate",
        "routing real exits as resting limits requires its own "
        "registration, a new strategy fingerprint and a restarted forward "
        "evaluation",
        "live promotion would additionally require the queue-position "
        "assumption to be replaced by measured fill data from real resting "
        "orders, because the daily-bar assumption cannot be validated from "
        "this dataset at all",
        "the 14.2806% ceiling applies unchanged to any later promotion",
    ],
    kind="confirmatory",
    hypothesis_id="H-0011",
)


def main():
    try:
        row = register(H0011)
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
