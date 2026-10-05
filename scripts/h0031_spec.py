"""H-0031: one position at a time, with all of the money in it - fixed before any outcome.

Owner, 2026-10-03: "instead of making multiple trades if it could just make 1 big
trade with all of its money if that would be better".

WHAT IS ALREADY ANSWERED, AND IS NOT RE-RUN
  EXP-0021  per-name notional caps other than 20%: a clean peak at 20% - but
            sizing stayed risk-based (0.5% of equity per trade), so no position
            ever held the whole account
  EXP-0046  raising risk_per_trade: every configuration worse
  EXP-0001  two names per bucket: worse drawdown, no return
  H-0006    idle cash into SPY: fails the 110% drawdown ceiling
  H-0016    the cash/notional constraint is not economically important
None of them puts the whole account into one trade. This does, once.
"""

import hashlib
from pathlib import Path

from event_aware_trader.modelgov.prereg import Hypothesis

import short_hypotheses_spec as shorts

REPO = Path(__file__).resolve().parents[1]

CODE_FILES = ["scripts/run_h0031.py", "scripts/short_sleeve_research.py",
              "scripts/run_short_hypotheses.py"]


def code_hashes():
    return {f: hashlib.sha256((REPO / f).read_bytes()).hexdigest() for f in CODE_FILES}


def hypothesis(hashes=None):
    hashes = hashes or code_hashes()
    return Hypothesis(
        hypothesis_id="H-0031",
        statement=(
            "Holding ONE position at a time with 99% of the account in it - the frozen rule's own "
            "entries and exits, the most oversold qualifying candidate taking the single slot - earns "
            "a higher CAGR than the frozen several-position book, without a worse Sharpe and inside "
            "the drawdown ceiling."),
        rationale=(
            "The frozen book is invested 44% of the time on average and its gap to SPY is exposure "
            "(spy-gap-is-exposure). Putting the whole account behind each trade raises exposure "
            "while a position is open. Against it: one name carries all of the idiosyncratic risk "
            "(a 2.5-ATR stop is about -5.6% of the account; a gap through it more), only one signal "
            "in many can be taken, and the per-trade edge (+0.57% net on 1,857 non-overlapping "
            "signals, H-0030) is small against a single stock's ~6% per-trade spread. The test "
            "decides which effect dominates."),
        rule=(
            "research.PRODUCTION_CANDIDATE unchanged (signal-close entry, realistic stop fills, "
            "max 3 entries a day, mark-to-market guard, 0.652% rule-exit haircut, frozen "
            "MeanReversionConfig exits), with the policy changed in exactly three places: "
            "max_open_positions 1, max_notional_fraction 0.99, risk_per_trade 1.0 (so the notional "
            "cap, not the risk budget, sets the size); conviction scaling OFF (it would shrink the "
            "single position to as little as half); candidates ranked by the live bot's own score, "
            "100 - RSI(14), highest first. Whole shares; the participation cap (2% of 20-day dollar "
            "volume) still applies."),
        parameters={
            "dataset": shorts.DATASET, "population": shorts.POPULATION,
            "benchmark": ("Control A: the frozen baseline (must reproduce +58.5889% / 698), idle "
                          "cash parked at the bill rate; SPY total return 15.00%/yr (EXP-0037) and "
                          "SPY held with all of the money as the literal 'one big trade'."),
            "max_open_positions": 1, "max_notional_fraction": 0.99, "risk_per_trade": 1.0,
            "conviction": None, "candidate_rank": "100 - RSI(14) at the signal close, highest first",
            "halves": shorts.HALVES, "rf_for_sharpe": 0.023, "code_sha256": hashes},
        search_procedure=("One configuration. The robustness runs are fixed in advance and cannot "
                          "replace it."),
        max_configurations=1,
        datasets=shorts.DATASETS,
        information_boundary=shorts.INFORMATION_BOUNDARY.split(" The decade dataset")[0] + (
            " The decade dataset was used to develop the long strategy, so it is CONTAMINATED: "
            "the result is a rejection test that can reject and cannot accept."),
        execution_assumptions=(
            "The frozen emulator's own: buy at the signal close x (1 + 6 bp); a resting GTC stop "
            "2.5 ATR below, filled at the open when the session opens below it; RSI >= 60 and the "
            "20-session cap at the close x (1 - 6 bp - 0.652%). Idle cash parked at the 3-month "
            "bill rate (research.with_parked_cash) for the headline; unparked also reported."),
        primary_metric="CAGR of the parked account minus the frozen baseline's, over the decade's sessions.",
        secondary_metrics=[
            "total return, volatility, Sharpe (rf 2.30%), Sortino, max drawdown, Calmar, worst day, "
            "longest losing streak, by year", "trades, win rate, exposure",
            "worst single trade as a share of the account", "SPY total return and SPY price",
            "one-way cost 12 bp", "the frozen emulator's default (alphabetical) candidate order",
            "ETF survivorship-control universe"],
        acceptance_criteria=(
            "All of: (R1) parked CAGR above the baseline's over the full window AND in each half; "
            "(R2) Sharpe not below the baseline's; (R3) max drawdown no deeper than 1.10 x the "
            "baseline's; (R4) robustness fixed in advance - R1 (full window) still holds at one-way "
            "cost 12 bp and with the default candidate order, and on the ETF survivorship-control "
            "universe the single-position book's CAGR exceeds the baseline's on that universe. "
            "Passing ALL earns at most PROMISING BUT NOT READY FOR OOS."),
        rejection_criteria=(
            "REJECTED if R1 (full window), R2 or R3 fails. INCONCLUSIVE if those pass but R1 in "
            "either half or R4 fails."),
        robustness_requirements=["one-way cost 12 bp", "default (alphabetical) candidate order",
                                 "ETF survivorship-control universe", "both halves"],
        complexity_penalty=("None in code - it is three policy values - but all of the account in "
                            "one name is a concentration the frozen policy exists to prevent."),
        required_oos_test=shorts.OOS,
        promotion_requirements=["owner approval", "a new fingerprint and a restarted forward "
                                "evaluation", "the exposed Alpaca credential rotated"])
