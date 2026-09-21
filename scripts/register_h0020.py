"""Seal H-0020 before any portfolio is run. Run once.

A VALIDATION of the P3 population H-0019 nominated. NOT a parameter
experiment. NOT a sweep. The ATR ceiling does not move, and no
production value changes.

THE QUESTION. Does the population the 3.5% ATR ceiling currently
excludes contain a robust, tradable, PORTFOLIO-LEVEL opportunity once
survivorship, next-open execution, the real production exits, costs,
portfolio constraints and drawdown are all applied? The question is
NOT what ceiling makes the most money, and no answer here may change
one.

P3 IS FROZEN AT THE H-0019 DEFINITION and may not be redefined,
narrowed, widened or filtered after results are seen:

    price >= 20 AND 20-day dollar volume >= 50m AND positive stop
    AND RSI(14) <= 35 AND close > SMA(200)
    AND ATR(14)/close > 0.035

IMPLEMENTED BY ENUMERATION, NOT BY MOVING THE CEILING. The wrapper
calls production's own evaluate() twice: once with the frozen config,
once with max_atr_fraction=None. P3 = (ceiling-off says BUY) AND
(frozen config says STAND_ASIDE). The single value None is used only
to ENUMERATE the excluded population; the resulting candidate set is
DISJOINT from production's by construction, so no observation
production would have taken can enter the P3 run. That is not a
threshold search: there is one value, it is not a candidate ceiling,
and it is never reported as one.

THE DECISION TIMESTAMP, and the exact H-0019 comparison. Membership is
determined from bars up to and including session t's close - the same
instant production decides. The frozen research framework then enters
at session t+1's OPEN. So membership is fully known BEFORE the trade
is initiated, and the gap between t's close and t+1's open is
structurally uncapturable by the frozen entry mechanism. H-0019's
headline +2.4359% was measured close-to-close and is therefore NOT a
tradable return; it is retained here only as a labelled diagnostic.

SURVIVORSHIP IS THE FIRST GATE, AND IT IS ALREADY KNOWN TO BE HARD.
Verified before sealing: all 230 symbols in the decade universe trade
through 2026-09. ZERO delistings. The universe is 100% survivors, no
point-in-time constituent data exists in this project, and none can be
obtained from the current vendor. The 67 broad ETFs are the only
survivorship-safe control available, and H-0019 found just 99 P3
observations in them.

SO THE FAILING CONDITION IS REGISTERED IN ADVANCE. If the ETF
survivorship control produces FEWER THAN 65 TRADES, the control is
underpowered, the survivorship limitation is classified UNRESOLVED,
and the equity result may NOT be called validated whatever it shows.
65 is this project's own precedent, not a new threshold: the rsi_entry
note in mean_reversion.py records that 65 trades could not distinguish
a setting from noise and 189 could. Given 99 observations, this
condition is LIKELY TO BIND, and that is the honest expected outcome
rather than a reason to weaken it.

DRAWDOWN IS A PRIMARY METRIC. The promotion ceiling is 110% of the
frozen baseline maximum drawdown: 14.2806%. A combined portfolio that
breaches it FAILS regardless of return. Higher return never substitutes
for the risk constraint.

WHAT THIS CANNOT CONCLUDE. No outcome changes the ATR ceiling, promotes
anything, reinterprets any of the previously rejected parameter
experiments, or broadens the question to another structural exclusion.
The best available outcome is that the evidence justifies DESIGNING a
separately preregistered parameter experiment later.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import (                  # noqa: E402
    Hypothesis, RegistrationError, declared_trials, register, verify_chain)

H0020 = Hypothesis(
    statement=(
        "The P3 population excluded by the 3.5% ATR ceiling contains a "
        "robust portfolio-level opportunity that survives a "
        "survivorship-safe control, next-open execution, the frozen "
        "production exits, the frozen portfolio and risk constraints, the "
        "framework's own costs, and the 110% maximum-drawdown ceiling - and "
        "is sufficiently independent of the existing strategy to justify "
        "designing a future, separately preregistered parameter experiment. "
        "The validation FAILS if the survivorship control is underpowered "
        "or negative, if the portfolio-level result is unstable across "
        "chronological thirds, if the combined portfolio breaches 14.2806%, "
        "if the result depends on a handful of symbols or trades, or if P3 "
        "adds nothing incremental to the frozen portfolio."),
    rationale=(
        "H-0019 nominated exactly one structural exclusion and recorded "
        "three objections to it: survivorship unresolved with a 99-"
        "observation control, half the population in 2024-2026, and a "
        "population that is by construction the high-volatility one. "
        "H-0019 measured per-observation forward returns with a fixed "
        "horizon and no portfolio. H-0011 already demonstrated that "
        "trade-level sums do not survive contact with cash, buckets and "
        "slots. So the nomination is not evidence until it is run through "
        "the frozen machinery that actually decides what the bot does."),
    rule=(
        "THREE PORTFOLIOS, each run on TWO universes, using the FROZEN "
        "simulator with no change to exits, sizing, buckets, guards, cash "
        "or costs. "
        "A = FROZEN PRODUCTION, which must reproduce +58.5889000000% / 698 "
        "or the experiment stops. "
        "B = P3-ONLY, the module-level mean_reversion_signal wrapped to "
        "emit BUY only for P3 members and STAND_ASIDE otherwise. "
        "C = COMBINED, emitting production's signal when it is a BUY and "
        "the P3 signal otherwise, so the frozen constraints allocate "
        "between them. "
        "UNIVERSES: the full 230-symbol decade set (survivorship-"
        "contaminated, labelled as such) and the 67 broad ETFs (the only "
        "survivorship-safe control available). "
        "Stops, targets and sizing for P3 candidates come from the SAME "
        "frozen arithmetic - stop = close - 2.5*ATR - so a wider stop "
        "automatically buys less. Nothing about the exit or the risk budget "
        "is touched."),
    parameters={
        "P3_definition_FROZEN": ("price>=20 AND dv20>=50e6 AND stop>0 AND "
                                 "RSI(14)<=35 AND close>SMA(200) AND "
                                 "ATR(14)/close>0.035"),
        "enumeration_device": ("evaluate() called twice; max_atr_fraction="
                               "None used ONLY to enumerate the excluded "
                               "population; P3 = ceiling-off BUY AND frozen "
                               "STAND_ASIDE; disjoint from production"),
        "decision_timestamp": "session t close; entry at session t+1 open",
        "runs": ["A_frozen", "B_p3_only", "C_combined"],
        "universes": {"full": "230 symbols, 0 delistings, 100% survivors",
                      "etf_control": "67 broad ETFs, survivorship-safe"},
        "SURVIVORSHIP_GATE": {
            "verified_before_sealing": "all 230 symbols trade through "
                                       "2026-09; zero delistings; no "
                                       "point-in-time constituent data "
                                       "exists in this project",
            "min_trades_for_a_powered_control": 65,
            "precedent": "mean_reversion.py rsi_entry note: 65 trades could "
                         "not distinguish a setting from noise, 189 could",
            "if_below": "classify survivorship UNRESOLVED; the equity result "
                        "may NOT be called validated; outcome cannot be A"},
        "RISK_GATE": {"baseline_max_drawdown": -0.129824,
                      "ceiling_110pct": 0.142806,
                      "primary": True,
                      "rule": "a combined portfolio breaching the ceiling "
                              "FAILS regardless of return"},
        "stability": "existing chronological thirds 2016-2019 / 2020-2023 / "
                     "2024-2026 and the standing 2-of-3 rule; no new split",
        "regimes": "forensics_regime.build_signals()['trend_dual_ma'] ONLY - "
                   "SPY against its own 200 and 50 day averages as of t-1. "
                   "No regime is fitted and no regime becomes a rule.",
        "costs": "the frozen framework's own: CostModel 2bps half-spread + "
                 "4bps slippage one way, and the 0.652% rule-exit haircut. "
                 "Nothing arbitrary is subtracted and no gross figure is "
                 "reported as net.",
        "benchmark": "SPY price-only, exactly as the frozen research "
                     "framework defines it, from the same series",
        "diagnostics_kept_separate": ["fixed 10-session horizon (H-0019's "
                                      "lens, diagnostic ONLY)",
                                      "overnight vs intraday decomposition "
                                      "of the realised path",
                                      "the uncapturable t-close to t+1-open "
                                      "gap"],
        "what_is_NOT_done": ["any ATR threshold sweep", "any percentile or "
                             "volatility-ranked alternative ceiling",
                             "any redefinition of P3", "any post-hoc filter "
                             "or outlier removal", "any exit or holding "
                             "period optimisation", "any new regime fit",
                             "any learned model", "any production change",
                             "any promotion", "any clean-OOS access",
                             "any live brokerage action",
                             "any reinterpretation of the 12 rejected "
                             "parameter experiments"],
    },
    search_procedure=(
        "Six runs, fixed here: three portfolios on two universes. No "
        "configuration is added, removed or retuned after results are "
        "visible. No portfolio is selected as preferred by return. The ATR "
        "ceiling takes exactly one non-production value, None, and only as "
        "an enumeration device that cannot enter a result."),
    max_configurations=6,
    datasets=["decade (development), the existing fixed 230-symbol universe "
              "and its 67-ETF subset",
              "thirty_year: NOT USED. Access count stays at 13."],
    information_boundary=(
        "P3 membership is computed from daily bars up to and including "
        "session t's close - SMA(200), RSI(14), ATR(14) and the 20-day "
        "dollar volume all use closed bars only - and the hypothetical "
        "trade is initiated at session t+1's open, so membership is fully "
        "determined before initiation. No forward price, and no information "
        "from any later session, enters membership, sizing or the stop. "
        "The framework's own forward-data rejection and dataset gate run on "
        "every call."),
    execution_assumptions=(
        "The frozen framework's, unchanged: entry at the next session's "
        "open, realistic_stop_fills, whole shares, 3 entries a day, "
        "mark-to-market guard, CostModel one-way 6bps, and the 0.652% "
        "rule-exit haircut. H-0019's close-to-close +2.4359% is NOT a "
        "tradable return and is reported only as a labelled diagnostic. "
        "The t-close to t+1-open gap is reported separately and described "
        "as uncapturable by the frozen entry mechanism, not as a loss."),
    primary_metric=(
        "Portfolio-level maximum drawdown of the combined portfolio against "
        "the 14.2806% ceiling, together with its incremental total return "
        "over the frozen baseline. Drawdown is primary; return cannot "
        "substitute for it."),
    secondary_metrics=[
        "total return, CAGR, annualised volatility, Sharpe, Sortino, Calmar",
        "maximum drawdown and drawdown duration",
        "trade count, win rate, profit factor, expectancy, average hold",
        "turnover, modelled transaction costs, exposure",
        "exit-reason mix against production's",
        "equity-curve return correlation between B and A",
        "incremental return, incremental drawdown and exposure change of C "
        "over A",
        "concentration by symbol, year, trade and regime",
        "leave-out sensitivity on the largest few trades, reported "
        "descriptively and never applied as a filter",
        "all of the above per chronological third",
        "the ETF survivorship control, reported beside the full universe "
        "and never merged with it",
    ],
    acceptance_criteria=(
        "(A) EVIDENCE SUFFICIENT TO JUSTIFY A FUTURE, SEPARATELY "
        "PREREGISTERED PARAMETER EXPERIMENT: the ETF survivorship control "
        "is powered at >= 65 trades AND positive; the combined portfolio "
        "stays within 14.2806%; P3 is incremental rather than a "
        "re-expression of the existing book; the result holds in at least "
        "2 of 3 chronological thirds; and it does not depend on a handful "
        "of symbols or trades. "
        "(B) INCONCLUSIVE. "
        "(C) NO EVIDENCE. "
        "(D) LIMITATION - survivorship or data prevents validation, "
        "including the registered case where the ETF control is "
        "underpowered. "
        "No fifth category. NO outcome changes the ATR ceiling, promotes "
        "anything, or authorises a parameter experiment to RUN; A licenses "
        "only its DESIGN under a separate seal."),
    rejection_criteria=(
        "Explicitly NOT successes: a large P3-only total return with an "
        "underpowered survivorship control; a combined portfolio that beats "
        "the baseline on return while breaching 14.2806%; a result carried "
        "by one chronological third or one regime; a result that vanishes "
        "when a few trades are set aside; P3 merely duplicating trades the "
        "frozen portfolio already takes; and choosing whichever of the "
        "three portfolios has the highest return, which this registration "
        "forbids in advance."),
    robustness_requirements=[
        "baseline equivalence +58.5889000000% / 698 verified before anything",
        "P3 candidate set proven DISJOINT from production's, by count",
        "membership timestamp proven to precede entry",
        "ETF control reported separately and never merged",
        "drawdown treated as primary; the 110% ceiling applied explicitly",
        "chronological thirds and the 2-of-3 rule on every headline figure",
        "concentration measured; no observation removed",
        "existing regime definitions reused unchanged",
        "H-0011/H-0013/H-0015/H-0016/H-0017/H-0018/H-0019 all frozen",
        "the 12 rejected parameter experiments not reinterpreted",
        "broker fix dc329bb untouched and excluded from evidence",
        "fingerprint da22011e...c237b unchanged",
        "ATR ceiling still 0.035 at the end of the run",
        "zero reads of the thirty-year dataset",
    ],
    complexity_penalty=(
        "The standing two percentage points of decade total return, applied "
        "to the INCREMENTAL contribution of C over A, not to P3's "
        "standalone return."),
    required_oos_test=(
        "The chronological thirds and the ETF survivorship control are the "
        "out-of-sample discipline. The clean forward record holds 0 "
        "sessions, is frozen until 2026-10-12 and is not touched. "
        "Ceiling: research_evidence."),
    promotion_requirements=[
        "H-0020 promotes nothing and changes no parameter",
        "the ATR ceiling remains 0.035 whatever the outcome",
        "outcome A licenses only the DESIGN of one separately sealed "
        "parameter experiment, never its execution",
        "all prior experiments remain frozen and none is reinterpreted",
    ],
    kind="exploratory",
    hypothesis_id="H-0020",
)


def main():
    try:
        row = register(H0020)
    except RegistrationError as error:
        print("refused: {0}".format(error))
        return 1
    p = row["payload"]
    print("registered {0}".format(p["hypothesis_id"]))
    print("  seal    {0}".format(p["seal"]))
    print("  commit  {0}".format(p["code_commit"]))
    print("\nchain: {0}".format(verify_chain()))
    print("declared configurations: {0}".format(declared_trials()))
    print("\nNo portfolio run. No ATR value changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
