"""Record the Phase 6 results into the research ledger. Failures included."""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.phase5.ledger import (                 # noqa: E402
    Experiment, record, summary)

DATA = REPO / "data" / "phase5"
COSTS = "2 bps half spread + 4 bps slippage each way, $0 commission"
EXECUTION = ("market order at the signal close; gapped stops fill at the "
             "open; whole shares; 3 entries/day; 20% per name; 2% ADV cap; "
             "0.652% rule-exit haircut")
UNIVERSE = "230 US equities and ETFs, survivorship-affected, crypto excluded"

EXIT_LEAKAGE = [
    "both windows are contaminated for the current candidate; the ceiling "
    "for any result is research_evidence",
    "the thirty-year window CONTAINS the decade, so the two are not "
    "independent samples",
    "survivorship: the universe is today's constituents",
    "intraday path within an exit session is not modelled; the 0.652% "
    "haircut is a frozen bound standing in for it",
]
NEWS_LEAKAGE = EXIT_LEAKAGE + [
    "the vendor archive is read as it exists today; a story deleted since "
    "publication is invisible",
    "702 of 11,852 items were revised after publication",
    "32% of items tag more than five symbols, so single-name attribution "
    "is weak",
    "news history begins in 2016, so no news feature can be checked on the "
    "thirty-year window",
]


def load(name):
    path = DATA / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def keys(row):
    wanted = ("total_return", "cagr", "annualised_volatility", "sharpe",
              "sortino", "max_drawdown", "calmar", "trades", "win_rate",
              "average_trade", "median_trade", "worst_loss", "profit_factor",
              "expectancy", "turnover", "transaction_costs", "exposure",
              "longest_losing_run", "average_hold_days")
    return {k: row.get(k) for k in wanted}


def main():
    deep = load("sealed-exits-deep.json")
    long = load("sealed-exits-long.json")
    news = load("news-filters-deep.json")
    if not deep:
        print("run scripts/run_sealed_exits.py deep first")
        return 1
    base, base_long = deep[0], (long[0] if long else {})
    by_long = {r.get("label"): r for r in long[1:]} if long else {}

    families = {}
    for row in deep[1:]:
        families.setdefault(row["hypothesis"], []).append(row)

    NOTES = {
        "H-0001": ("Trailing stop, armed after a threshold gain. Best "
                   "configuration (arm 1.0R, 3 ATR) gained 6.9 points but "
                   "beat the baseline in only 5 of 11 years, and the family "
                   "is NOT monotone: at 2 ATR the same arm points give "
                   "+2.2, -9.3 and -0.2. REJECTED on the registered "
                   "clauses."),
        "H-0002": ("Fixed take profit. REGISTERED AS EXPECTED TO FAIL, and "
                   "it did not. At 2.0R it gained 2.7 points on the decade "
                   "with 8 of 11 years better, +0.9 excluding its best "
                   "year, an unchanged drawdown, and the family is "
                   "monotone. It holds sign on the thirty-year window at "
                   "+7.0 points. This contradicts the earlier finding that "
                   "every binding take-profit level cost return - that work "
                   "predated the haircut and the participation cap."),
        "H-0003": ("Breakeven profit lock. The strongest result of the "
                   "phase: +13.7 points on the decade and +23.6 on the "
                   "thirty-year window, with drawdown slightly BETTER on "
                   "both and volatility unchanged. It passes every "
                   "per-configuration clause. It FAILS the family "
                   "monotonicity clause, because the mechanism is inert "
                   "above 1.0R - 699 and 698 trades against 698 baseline - "
                   "so the surface is a threshold rather than an unstable "
                   "optimum. Distinguishing those needs a grid BELOW 1.0R, "
                   "which the seal does not contain. NOT a promotion "
                   "candidate on this evidence; it earns a new "
                   "registration."),
        "H-0004": ("Scaling out half at a target. Rejected on both "
                   "settings: -6.8 points at 1.0R on 1,045 trades, and "
                   "nil at 2.0R. Selling half the winners removes the right "
                   "tail the strategy depends on, and the extra turnover is "
                   "paid for nothing."),
    }
    VERDICTS = {"H-0001": "rejected", "H-0002": "research_evidence",
                "H-0003": "research_evidence", "H-0004": "rejected"}

    recorded = []
    for hid in sorted(families):
        rows = families[hid]
        best = max(rows, key=lambda r: r["total_return"])
        metrics = keys(best)
        if best["label"] in by_long:
            metrics["thirty_year_total_return"] = by_long[best["label"]]["total_return"]
            metrics["thirty_year_max_drawdown"] = by_long[best["label"]]["max_drawdown"]
        baseline = keys(base)
        if base_long:
            baseline["thirty_year_total_return"] = base_long.get("total_return")
            baseline["thirty_year_max_drawdown"] = base_long.get("max_drawdown")
        recorded.append(Experiment(
            hypothesis="{0}: {1}".format(hid, best["label"]),
            configuration={"sealed_as": hid,
                           "configurations": [r["label"] for r in rows],
                           "best": best.get("configuration")},
            dataset="decade (development) + thirty_year (robustness)",
            date_range="2016-2026 / 1996-2026",
            universe=UNIVERSE, costs=COSTS, execution_assumptions=EXECUTION,
            information_sources=["daily OHLCV only"],
            trials=len(rows), metrics=metrics, baseline_metrics=baseline,
            validation_methodology=(
                "pre-registered before any run; seal verified at run time; "
                "full portfolio re-run so freed capital is reallocated; "
                "per-calendar-year differences; leave-one-best-year-out; "
                "adjacent-parameter monotonicity; sign check on the "
                "thirty-year window"),
            leakage_risks=EXIT_LEAKAGE,
            conclusion=NOTES[hid], verdict=VERDICTS[hid],
            suitable_for_further_testing=VERDICTS[hid] == "research_evidence"))

    if news:
        base_news = news[0]
        for row in news[1:]:
            recorded.append(Experiment(
                hypothesis="News as an entry filter: {0}".format(row["label"]),
                configuration={"veto": row["label"],
                               "lookback_hours": 72,
                               "coverage": row.get("coverage")},
                dataset="decade + Alpaca/Benzinga point-in-time archive",
                date_range="2016-2026", universe=UNIVERSE, costs=COSTS,
                execution_assumptions=EXECUTION,
                information_sources=["Alpaca /v1beta1/news (Benzinga), tier 2"],
                trials=1, metrics=keys(row), baseline_metrics=keys(base_news),
                validation_methodology=(
                    "point-in-time snapshot at the decision timestamp derived "
                    "from the exchange clock, items at or after it excluded; "
                    "99.9% candidate coverage; full portfolio re-run"),
                leakage_risks=NEWS_LEAKAGE,
                conclusion=(
                    "Every news filter made the ACCOUNT worse and deepened "
                    "drawdown. Decisive point: the earnings filter (-10.8 "
                    "points) is indistinguishable from the any-news control "
                    "(-10.7 points), so the separation found on taken trades "
                    "was not specific to earnings and did not survive capital "
                    "reallocation."),
                verdict="rejected", suitable_for_further_testing=False))

    for exp in recorded:
        row = record(exp)
        print("{0}  {1:<20} {2}".format(row["id"], row["verdict"],
                                        exp.hypothesis[:56]))
    print("\n{0}".format(json.dumps(summary(), indent=1)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
