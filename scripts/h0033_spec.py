"""H-0033: the published "Beat the Market" SPY intraday momentum rule - fixed before any outcome.

Owner, 2026-10-04: "Continue researching" (what day traders do to be profitable
and consistently outperform SPY). Zarattini, Aziz & Barbon (2024) is the
strongest public claim that a day-trading rule beats SPY: 19.6%/yr, Sharpe 1.33,
2007 to April 2024, net of costs. Everything after its first version
(2024-05-10) is out of sample for the authors. This replicates their two
reported rules exactly; no parameter is chosen here.
"""

import hashlib
from pathlib import Path

from event_aware_trader.modelgov.prereg import Hypothesis

REPO = Path(__file__).resolve().parents[1]
CODE_FILES = ["scripts/h0033_noise_area.py", "scripts/run_h0033.py",
              "tests/test_h0033_noise_area.py"]
DATASET = {"id": "spy-5min-2016-2026-quarterly-43",
           "sha256": "9803ae210c0710960b7aa8c4de12b121a51adfc471643deeac599f6d8230d2c5"}
WINDOWS = {"full": ["2016-01-04", "2026-09-10"],
           "overlap_with_paper": ["2016-01-04", "2024-04-30"],
           "after_publication": ["2024-05-10", "2026-09-10"]}
COST_PER_SHARE = 0.0045          # the paper's $0.0035 commission + $0.001 slippage, each side
COST_STRESS = 0.009              # twice that: a half-spread of $0.005 alone exceeds their slippage


def code_hashes():
    return {f: hashlib.sha256((REPO / f).read_bytes()).hexdigest() for f in CODE_FILES}


def hypothesis(hashes=None):
    hashes = hashes or code_hashes()
    return Hypothesis(
        hypothesis_id="H-0033",
        statement=(
            "The published noise-area intraday momentum rule on SPY (Zarattini, Aziz & Barbon "
            "2024) keeps a positive, SPY-beating risk-adjusted return after its publication, in "
            "both of the paper's reported sizings."),
        rationale=(
            "It is the strongest public evidence that a day-trading rule beats SPY, it uses only "
            "SPY prices, and its rules are fully specified, so it can be tested without choosing "
            "anything. The only clean test of a published rule is the period after publication."),
        rule=(
            "Exactly as the paper: sigma(t,HH:MM) = mean |Close(HH:MM)/Open(9:30) - 1| over the "
            "previous 14 sessions; UB = max(Open, previous close)*(1+sigma), LB = min(Open, "
            "previous close)*(1-sigma); at each of 10:00, 10:30, ..., 15:30 hold long if price > UB "
            "and > VWAP, short if price < LB and < VWAP, else flat; flat at the 16:00 close. "
            "Config B: shares = AUM(t-1)/Open(t). Config C: shares = AUM(t-1)*min(4, 0.02/sigma_SPY)/"
            "Open(t), sigma_SPY the stdev of the previous 14 daily returns. Costs $0.0045 per share "
            "each side. Sessions without every required bar (early closes, gaps) are not traded and "
            "not used in sigma; on NYSE 13:00 early closes the store's after-hours bars are dropped, "
            "so that session's close is the 13:00 close. Duplicate quarter-boundary bars are merged "
            "by timestamp."),
        parameters={
            "dataset": DATASET,
            "population": "SPY regular-session 5-minute bars, 2016-01 to 2026-09-10",
            "benchmark": ("SPY held over the same sessions (price; total return approximated with "
                          "+1.58 pts/yr), and SPY's own Sharpe over the same window"),
            "windows": WINDOWS, "cost_per_share": COST_PER_SHARE, "cost_stress": COST_STRESS,
            "configs": ["B: 100% notional, no leverage", "C: 2% daily vol target, capped at 4x"],
            "sharpe_convention": "rf = 0, arithmetic daily mean x sqrt(252) - the paper's; rf 2.30% also reported",
            "code_sha256": hashes},
        search_procedure="Two configurations, the paper's own; nothing tuned.",
        max_configurations=2,
        datasets=["spy-5min-2016-2026-quarterly-43 (preserved; never used for this rule)",
                  "clean OOS: NOT USED"],
        information_boundary=(
            "sigma and sigma_SPY use only previous sessions; the bands use today's 09:30 open and "
            "the previous close; each decision uses the price and VWAP at its half-hour mark and "
            "nothing later. Sessions after 2026-09-10 are excluded."),
        execution_assumptions=(
            "Trades at the half-hour mark's price (the close of the 5-minute bar ending then), the "
            "paper's per-share costs; shorting SPY intraday assumed available (easy to borrow, no "
            "overnight borrow); Config C's up-to-4x intraday leverage assumed available, as the paper "
            "assumes."),
        primary_metric="Per config: Sharpe (rf 0) and annualised return after publication (2024-05-10 to 2026-09-10).",
        secondary_metrics=["every window: CAGR, total, volatility, Sharpe, max drawdown, worst day, by year",
                           "trades and traded sessions", "SPY held, same windows",
                           "costs doubled"],
        acceptance_criteria=(
            "Per config, all of: (R1) replication - Sharpe >= 1.0 on 2016-01 to 2024-04; (R2) after "
            "publication - annualised return > 0 AND Sharpe above SPY's own Sharpe over the same "
            "window; (R3) positive in at least 8 of the 11 calendar years 2016-2026; (R4) full-window "
            "Sharpe >= 0.7 at doubled costs; (R5) full-window max drawdown no deeper than SPY's. "
            "Passing earns at most PROMISING: the next step would be a shadow forward record, and "
            "the bot has no intraday order path."),
        rejection_criteria=("Per config: REJECTED if R1 or R2 fails. INCONCLUSIVE if both pass but "
                            "R3, R4 or R5 fails."),
        robustness_requirements=["costs doubled", "calendar-year consistency", "drawdown against SPY"],
        complexity_penalty=("An intraday order path, intraday shorting, and (Config C) up to 4x "
                            "intraday leverage - all outside the project's current rules."),
        required_oos_test="A registered shadow forward record of at least 60 sessions before any order.",
        promotion_requirements=["owner approval", "an intraday order path", "a leverage policy decision",
                                "the exposed credential rotated"])
