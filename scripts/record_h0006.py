"""Record every H-0006 configuration in the ledger, independently.

Mechanical on purpose. Each row carries the verdict the adjudicator
returned and nothing chosen here: the control is recorded as a control,
the two candidates are recorded with whatever clauses they failed, and
no configuration is described as "best". Written before the results
existed so it could not be shaped by them.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.phase5.ledger import (                 # noqa: E402
    Experiment, record, summary)

KEYS = ("total_return", "cagr", "annualised_volatility", "sharpe", "sortino",
        "max_drawdown", "calmar", "trades", "turnover", "transaction_costs",
        "exposure", "longest_losing_run")
LEAK = [
    "decade is contaminated for the current candidate; ceiling is "
    "research_evidence",
    "thirty-year window NOT read; remains contaminated robustness evidence "
    "at 13 reads",
    "survivorship: today's universe",
    "SPY comparison is PRICE ONLY - SPY dividends are excluded, which "
    "understates the benchmark by roughly 1.5-2 points a year",
    "the overlay charges 6 bps one-way on every dollar moved and on the "
    "whole balance at a trend flip; it cannot alter a trade",
]


def keys(d):
    out = {k: d.get(k) for k in KEYS}
    for extra in ("vs_spy_points", "switches"):
        if extra in d:
            out[extra] = d[extra]
    return out


def main():
    res = json.loads((REPO / "data" / "phase5" / "h0006-results.json")
                     .read_text(encoding="utf-8"))
    base = res["baseline"]
    base_keys = keys(base)
    base_keys["vs_spy_points"] = 100.0 * (base["total_return"] - res["spy_total"])
    for row, verdict in zip(res["configurations"], res["verdicts"]):
        is_control = row["label"].startswith("C1")
        record(Experiment(
            hypothesis="H-0006 / {0}: idle capital in the index{1}".format(
                row["label"], " (CONTROL)" if is_control else ""),
            configuration={"sealed_as": "H-0006", "seal": res["seal"],
                           "mode": row["mode"], "is_control": is_control,
                           "trend_days": 200, "cost_one_way_bps": 6,
                           "family_member": True},
            dataset="decade (development) only; zero thirty-year reads",
            date_range="2016-2026",
            universe="230 US equities and ETFs; idle cash overlay on SPY",
            costs="strategy leg frozen; index leg 6 bps one-way per dollar "
                  "moved and on the whole balance at each flip",
            execution_assumptions="frozen production candidate for the "
                                  "strategy leg; overlay on the cash curve",
            information_sources=["daily OHLCV; SPY close vs its own 200-day"],
            trials=3, metrics=keys(row), baseline_metrics=base_keys,
            validation_methodology=(
                "pre-registered and sealed before any result; overlay mode "
                "'none' verified as the exact identity first; registered "
                "clauses with a 2-point margin; positive including and "
                "excluding 2025; family clause: trend filter must reduce "
                "drawdown against the unconditional control; reported "
                "against SPY over the identical window"),
            leakage_risks=LEAK,
            conclusion=(
                "{0}. Failed clauses: {1}. Total {2:+.2%} vs baseline "
                "{3:+.2%} vs SPY {4:+.2%}; max drawdown {5:.2%} vs baseline "
                "{6:.2%}; {7} trend flips."
                .format("Control; cannot survive by construction" if is_control
                        else ("Passes every registered clause" if verdict["survives"]
                              else "Does not pass"),
                        ", ".join(verdict["failed"]) or "none",
                        row["total_return"], base["total_return"],
                        res["spy_total"], row["max_drawdown"],
                        base["max_drawdown"], row.get("switches"))),
            verdict=("research_evidence" if (verdict["survives"] and not is_control)
                     else "rejected"),
            suitable_for_further_testing=bool(verdict["survives"]
                                              and not is_control)))
    print(json.dumps(summary(), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
