"""H-0032: market intraday momentum on SPY, as a day trade - fixed before any outcome.

Owner, 2026-10-03: "speratly research what day trades do to be profitable and
consistently out preform the spy". The literature review is
docs/2026-10-03-day-trading-what-works.md. This is the one documented intraday
effect the project had never tested (it needs intraday bars), run once.
"""

import hashlib
from pathlib import Path

from event_aware_trader.modelgov.prereg import Hypothesis

REPO = Path(__file__).resolve().parents[1]
CODE_FILES = ["scripts/h0032_intraday_momentum.py", "scripts/run_h0032.py",
              "tests/test_h0032_intraday_momentum.py"]
DATASET = {"id": "spy-5min-2016-2026-quarterly-43",
           "sha256": "9803ae210c0710960b7aa8c4de12b121a51adfc471643deeac599f6d8230d2c5"}
LAST_SESSION = "2026-09-10"        # the research freeze boundary the datasheet asks users to apply
COSTS_BPS = [0.0, 1.0, 2.0, 6.0, 12.0]
PRIMARY_COST_BPS = 2.0


def code_hashes():
    return {f: hashlib.sha256((REPO / f).read_bytes()).hexdigest() for f in CODE_FILES}


def hypothesis(hashes=None):
    hashes = hashes or code_hashes()
    return Hypothesis(
        hypothesis_id="H-0032",
        statement=(
            "Buying SPY at 15:30 ET and selling at the 16:00 close, on every session whose return "
            "from the previous close to 10:00 ET was positive, earns a positive net return per trade "
            "after a 2 bp round trip, reliably (t >= 2) and in both halves of 2016-2026."),
        rationale=(
            "Gao, Han, Li & Zhou (JFE 2018) found SPY's first half-hour return predicts its last "
            "half-hour return, 1993-2013, attributing it to hedging and late-informed trading. It is "
            "the best-documented intraday effect in the literature reviewed, and the only one with "
            "academic standing this project could not test before (it needs intraday bars). Long-only "
            "because the bot does not short (H-0027..H-0029 rejected)."),
        rule=(
            "Session t: r_first = (09:55-bar close on t) / (15:55-bar close on t-1) - 1; r_last = "
            "(15:55-bar close on t) / (15:25-bar close on t) - 1, bars stamped by start time in New "
            "York time. If r_first > 0, return r_last - cost; otherwise flat. Sessions missing a "
            "required bar, or more than 4 calendar days after the previous valid session, are "
            "skipped. Sessions up to " + LAST_SESSION + "."),
        parameters={
            "dataset": DATASET,
            "population": "SPY only, regular-session 5-minute bars, 2016-01 to " + LAST_SESSION,
            "benchmark": ("SPY held (price return from the same bars); the strategy's account holds idle "
                          "cash at the 3-month bill rate (data/tbill.csv)"),
            "costs_round_trip_bps": COSTS_BPS, "primary_cost_bps": PRIMARY_COST_BPS,
            "halves": ["2016-2020", "2021-" + LAST_SESSION],
            "code_sha256": hashes},
        search_procedure="One rule. Cost levels are reported, not chosen; the long-short variant is descriptive.",
        max_configurations=1,
        datasets=["spy-5min-2016-2026-quarterly-43 (preserved; used before only for market-context "
                  "features by H-0013/H-0014, never for this effect)", "clean OOS: NOT USED"],
        information_boundary=(
            "The signal uses prices to 10:00 ET; the entry uses the 15:25-bar close, known at 15:30; "
            "the exit is the 15:55-bar close. Nothing later than the decision is used. Sessions after "
            + LAST_SESSION + " are excluded."),
        execution_assumptions=(
            "A market order at 15:30 fills at the 15:25-bar close and a market-on-close order at the "
            "15:55-bar close; the difference from real fills is covered by the cost, 2 bp round trip "
            "primary (SPY's quoted spread is about one cent on a $200-$700 price), with 0, 1, 6 and "
            "12 bp reported. No borrow, no overnight risk."),
        primary_metric="Mean net return per traded session, long-only, at 2 bp round trip.",
        secondary_metrics=[
            "OLS slope of r_last on r_first, t-stat and R-squared, full window and halves",
            "win rate, median", "the long-short variant (descriptive)",
            "the account with idle cash at the bill rate: CAGR against SPY held; years beating SPY",
            "every cost level"],
        acceptance_criteria=(
            "All of: (R1) mean net return per trade at 2 bp > 0 with t >= 2.0; (R2) > 0 in each half; "
            "(R3) the slope replicates: > 0 with t >= 2.0 over the full window; (R4) mean net return "
            "per trade at 6 bp > 0. Passing earns at most PROMISING: a single historical window; the "
            "next step would be a shadow forward record."),
        rejection_criteria="REJECTED if R1 fails. INCONCLUSIVE if R1 passes but R2, R3 or R4 fails.",
        robustness_requirements=["both halves", "costs 0/1/2/6/12 bp reported"],
        complexity_penalty=("A new intraday order path (15:30 entry, market-on-close exit) the bot "
                            "does not have."),
        required_oos_test="A registered shadow forward record of at least 60 sessions before any order.",
        promotion_requirements=["owner approval", "an intraday order path", "the exposed credential rotated"])
