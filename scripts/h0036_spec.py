"""H-0036: the full 7,846-rule technical-analysis universe as SPY day trades -
fixed before any outcome.

Owner, 2026-10-04: "continue researching and leave nothing out" (what day
traders do to make money consistently). Chart rules are what most day traders
use. Sullivan, Timmermann & White (1999) built the standard universe of 7,846
rules - filters, moving averages, support and resistance, channel break-outs and
on-balance volume - and the test that corrects for searching across all of
them. Marshall, Cahan & Cahan (2008) ran that universe on SPY 5-minute bars for
2002-2003: no rule was profitable after the correction. This asks the same
question of 2016-2026, as day trades, and adds an out-of-sample test.
"""

import hashlib
from pathlib import Path

from event_aware_trader.modelgov.prereg import Hypothesis

REPO = Path(__file__).resolve().parents[1]
CODE_FILES = ["scripts/h0036_ta_universe.py", "scripts/h0034_index_day_rules.py",
              "scripts/h0033_noise_area.py", "scripts/run_h0036.py",
              "tests/test_h0036_ta_universe.py"]
DATASET = {"id": "spy-5min-2016-2026-quarterly-43",
           "sha256": "9803ae210c0710960b7aa8c4de12b121a51adfc471643deeac599f6d8230d2c5"}
WINDOWS = {"full": ["2016-01-04", "2026-09-10"],
           "first_half": ["2016-01-04", "2020-12-31"],
           "second_half": ["2021-01-01", "2026-09-10"]}
COST_PER_SHARE = 0.0045      # each side; SPY's half-spread is $0.005
BOOTSTRAP = {"n_boot": 1000, "q": 0.1, "seed": 20261004}   # q from the paper's Appendix C


def code_hashes():
    return {f: hashlib.sha256((REPO / f).read_bytes()).hexdigest() for f in CODE_FILES}


def hypothesis(hashes=None):
    hashes = hashes or code_hashes()
    return Hypothesis(
        hypothesis_id="H-0036",
        statement=(
            "Some rule in the standard 7,846-rule technical-analysis universe (Sullivan, "
            "Timmermann & White 1999), run on SPY 5-minute bars as a day trade, beats staying out "
            "of the market after realistic costs once the search across all 7,846 rules is "
            "accounted for, and the best rule of 2016-2020 keeps working in 2021-2026."),
        rationale=(
            "Chart rules are what most day traders use. The universe and the data-snooping test "
            "are the field's standard, published long before this data; the 2002-2003 SPY "
            "5-minute test found nothing. Nothing here is chosen: the rules are the paper's."),
        rule=(
            "The 7,846 rules of the paper's Appendix A with days read as 5-minute bars: filter "
            "rules (x, x with extrema e, x with hold c, x with neutral y), moving averages and "
            "on-balance-volume averages (single and fast/slow, with band b, delay d or hold c, "
            "plus the nine Brock-Lakonishok-LeBaron rules), support and resistance (previous-n or "
            "e-extrema levels, band b, delay d, hold c) and channel break-outs (n, width x, band "
            "b, hold c). Indicators run on the continuous series of 5-minute closes of complete "
            "sessions. A rule's state at a bar's close sets its position over the next bar inside "
            "the session; every position is closed at 16:00 and reopened at the next session's "
            "first close if the rule still says so. Interpretations where the paper leaves a "
            "choice are fixed in the engine's docstring."),
        parameters={
            "dataset": DATASET,
            "population": ("SPY regular-session 5-minute bars, complete sessions only (no 13:00 "
                           "early closes, no session with a missing bar), 2016-01-04 to 2026-09-10"),
            "benchmark": ("staying out of the market (zero), as in the paper; and for R3 SPY held "
                          "close to close over the same sessions"),
            "windows": WINDOWS, "cost_per_share_each_side": COST_PER_SHARE,
            "bootstrap": BOOTSTRAP,
            "tests": "White (2000) Reality Check; Hansen (2005) SPA, consistent version",
            "performance": "mean daily net return per unit of notional; flat overnight",
            "code_sha256": hashes},
        search_procedure="The whole published universe of 7,846 rules, corrected for by the tests.",
        max_configurations=7846,
        datasets=["spy-5min-2016-2026-quarterly-43 (preserved)", "clean OOS: NOT USED"],
        information_boundary=(
            "A position held over a bar's return is set by closes up to the previous bar's close. "
            "No overnight return is earned: the first bar of each session, which carries the "
            "overnight gap, is never held. Sessions after 2026-09-10 are excluded."),
        execution_assumptions=(
            "Trades at the close of the bar that gives the signal, as in the paper and the 2008 "
            "SPY study; $0.0045 a share each side on every change, on the 16:00 exit and on the "
            "next morning's re-entry; SPY shortable intraday at no fee; unit notional, no leverage."),
        primary_metric="Reality Check and SPA p-values for the best rule, full window, net of costs.",
        secondary_metrics=["the same before costs", "each half's best rule and its p-values",
                           "the best rule by family", "the ten best rules", "rules with a positive mean"],
        acceptance_criteria=(
            "All of: (R1) full window, net of costs: Reality Check p < 0.05 AND SPA p < 0.05; "
            "(R2) the rule with the best 2016-2020 net mean earns a positive 2021-2026 net mean "
            "with t >= 2.0; (R3) that rule's 2021-2026 Sharpe (rf 0) is above SPY's over the same "
            "sessions. Passing earns at most PROMISING."),
        rejection_criteria="REJECTED if R1 or R2 fails. INCONCLUSIVE if R1 and R2 pass but R3 fails.",
        robustness_requirements=["before-cost tests reported", "each half tested separately"],
        complexity_penalty="An intraday order path and intraday shorting; most rules trade many times a day.",
        required_oos_test="A registered shadow forward record of at least 60 sessions before any order.",
        promotion_requirements=["owner approval", "an intraday order path", "the exposed credential rotated"])
