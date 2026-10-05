"""H-0038: where the take profit should sit - fixed before any outcome.

H-0038 is H-0037 (seal 06ac2c80..., registered 2026-10-04 22:44 UTC) with one
defect fixed. H-0037's runner reproduced the baseline (+58.5889% / 698) and
replayed 698 of 698 baseline exits exactly, then crashed in its verdict step
(a lookup of a "B_minus_C" comparison it never computed) before printing or
writing any result. No outcome was seen. Every rule, dataset, haircut and
criterion below is H-0037's, unchanged.

Owner, 2026-10-04: "Right now there are many trades that are open and the bot
is currently making a profit but it is unrecognized so research know where to
set take profits and stop losses."

On every open position the live take profit (EXP-0055: 2.5 x entry ATR, which
is 1R against the 2.5-ATR stop) sits BELOW the price at which the bot's own
bounce exit (RSI(14) >= 60) would sell. EXP-0050 measured a 1.0R target
costing CAGR (5.75% -> 4.88%), and EXP-0055's own diagnostic put the live
target at -$29,230 net of its execution accounting. Never tested: a resting
sell limit AT the bounce level, refreshed each session - the bot's own
profit exit as a visible broker order. This compares the placements on the
frozen baseline's trades, one placement against another, trade by trade.
"""

import hashlib
from pathlib import Path

from event_aware_trader.modelgov.prereg import Hypothesis

REPO = Path(__file__).resolve().parents[1]
HYPOTHESIS_ID = "H-0038"
CODE_FILES = ["scripts/h0037_tp_placement.py", "scripts/run_h0038.py",
              "tests/test_h0037_tp_placement.py", "tests/test_h0038_decide.py"]
DATASET = {"id": "decade-2016-2026-split-adjusted-230",
           "sha256": "935fed79de9803f1da2a380c6f3f76ab525b27c5d14830bbea4744a7bf73d4a7"}
HAIRCUTS = {"primary": 0.003, "backtest": 0.00652, "none": 0.0}
SPLIT = "2021-01-01"
MATCH_FLOOR = 0.95


def code_hashes():
    return {f: hashlib.sha256((REPO / f).read_bytes()).hexdigest() for f in CODE_FILES}


def hypothesis(hashes=None):
    hashes = hashes or code_hashes()
    return Hypothesis(
        hypothesis_id=HYPOTHESIS_ID,
        statement=(
            "A resting sell limit at the bounce level (the price at which the session's close would "
            "put RSI(14) at 60, refreshed each session) earns more per trade than the live 2.5-ATR "
            "take profit, on the frozen strategy's own trades."),
        rationale=(
            "The live target sits below the bounce exit on every open position, so it sells the "
            "bounce before it completes; the project's own measurements say early targets cost "
            "return. A limit at the bounce level keeps the strategy's own exit, adds the limit "
            "order's execution, and is visible at the broker. Nothing new is fitted. This is "
            "H-0037 re-registered after its runner crashed in the verdict step before any result "
            "was printed or written; the rules are unchanged."),
        rule=(
            "The frozen baseline's 698 decade trades keep entries, sizes and stops. Each is "
            "replayed on its daily bars under A (no take profit: stop, RSI >= 60 at the close, 20 "
            "sessions), B (A plus a resting limit at entry + 2.5 x entry ATR, the live setting), C "
            "(the stop and 20 sessions, plus a resting limit at the bounce level set from closes "
            "through the previous session) and D (one resting limit at the lower of B's and C's). "
            "Fills and costs as the engine's docstring states; market sales at the close pay the "
            "rule-exit haircut h."),
        parameters={
            "dataset": DATASET,
            "population": "the frozen baseline's 698 decade trades (+58.5889%, reproduced first)",
            "benchmark": "placement B, the live 2.5-ATR take profit; A, no take profit, as a reference",
            "haircuts": HAIRCUTS, "split_for_halves": SPLIT, "replay_match_floor": MATCH_FLOOR,
            "rsi": "Wilder RSI(14) as indicators.rsi; exit level 60", "side_cost": 0.0006,
            "code_sha256": hashes},
        search_procedure="Four placements fixed in advance; no level is searched.",
        max_configurations=4,
        datasets=["decade (development) via research_gate.verify_dataset - purpose rejection_test",
                  "thirty-year: lost; clean OOS: NOT USED"],
        information_boundary=(
            "The bounce level for session t uses closes through t-1 only; the take profit uses the "
            "entry's ATR; fills use session t's open, high and low; same-session stop and limit go "
            "to the stop after the open."),
        execution_assumptions=(
            "Limits fill at their level or the better open; stops at their level or the worse "
            "open; 6 bp a side on every fill; close-time rule sales also pay h. Per-trade replay: "
            "an earlier exit's freed capital is not redeployed (portfolio effects are not measured)."),
        primary_metric="Mean paired net R per trade, C minus B, at h = 0.3%.",
        secondary_metrics=["every pair of placements at every h", "halves (entries before/after 2021)",
                           "exits by reason", "sessions held and R per session held", "by year"],
        acceptance_criteria=(
            "First, replay A at h = 0.652% must reproduce at least 95% of the baseline's exits "
            "(same day, price within 1e-6 relative), or the run is STOPPED. Then MOVE (C over B): "
            "mean(C - B) > 0 with paired t >= 2.0 at h = 0.3%, positive in both halves, and "
            "positive at h = 0.652% and h = 0. KEEP (B over C): the same with B and C swapped. "
            "Otherwise NO DIFFERENCE SHOWN. A result here can only nominate a portfolio-level "
            "registered test; the decade data cannot accept a change."),
        rejection_criteria="C is rejected as a placement if KEEP holds; B is if MOVE holds.",
        robustness_requirements=["three haircuts", "both halves", "R per session held reported"],
        complexity_penalty="None in the rule; a daily-refreshed broker order in any later implementation.",
        required_oos_test="A portfolio-level registered test, then a shadow forward record, before any change.",
        promotion_requirements=["owner approval", "a portfolio-level test", "the exposed credential rotated"])
