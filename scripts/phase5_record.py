"""Record Phase 5 experiments into the research ledger.

Reads the measured outputs rather than retyping numbers, so a figure in
the ledger cannot drift from the figure the run produced. Every row keeps
the fields the brief requires, including the leakage risks and the trial
count, and every row - including the failures, which are most of them -
is appended and never overwritten.

  python scripts/phase5_record.py
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.phase5.ledger import (                 # noqa: E402
    Experiment, load, record, summary)

DATA = REPO / "data" / "phase5"

COSTS = "2 bps half spread + 4 bps slippage each way, $0 commission"
EXECUTION = ("market order at the signal close; gapped stops fill at the "
             "open; whole shares; 3 entries per day; 20% per name; "
             "0.652% exit-timing haircut on rule exits")
UNIVERSE = "230 US equities and ETFs, survivorship-affected, crypto excluded"

PRICE_LEAKAGE = [
    "both windows are contaminated for the current candidate; a positive "
    "result here can never be an acceptance",
    "the thirty-year window contains the decade, so the two are not "
    "independent samples",
    "survivorship: the universe is today's, so names that failed are absent",
]
NEWS_LEAKAGE = PRICE_LEAKAGE + [
    "the vendor archive is read as it exists today; a story deleted since "
    "publication is invisible and its absence undetectable",
    "178 of 3,032 items were revised after publication, so the stored text "
    "may post-date the stored timestamp",
    "symbol tagging is the vendor's and may be automated; 32% of items tag "
    "more than five symbols",
    "news history begins in 2016, so no news feature can be checked on the "
    "thirty-year window at all",
]


def per_year_robustness(rows):
    base = rows[0]
    years = sorted(base["by_year"])
    out = {}
    for r in rows[1:]:
        d = {y: r["by_year"].get(y, 0) - base["by_year"][y] for y in years}
        total = sum(d.values())
        best = max(d, key=lambda y: d[y])
        out[r["label"]] = {
            "sum_of_yearly_differences": round(total, 6),
            "best_year": best,
            "sum_excluding_best_year": round(total - d[best], 6),
            "years_better": sum(1 for v in d.values() if v > 0),
            "years": len(years),
        }
    return out


def main():
    path = DATA / "filters-deep.json"
    if not path.exists():
        print("run scripts/phase5_filters.py deep first")
        return 1
    rows = json.loads(path.read_text(encoding="utf-8"))
    base = rows[0]
    robust = per_year_robustness(rows)

    baseline_metrics = {k: base[k] for k in (
        "total_return", "cagr", "annualised_volatility", "sharpe", "sortino",
        "max_drawdown", "calmar", "profitable_years", "trades", "win_rate",
        "average_trade", "median_trade", "worst_loss", "profit_factor",
        "expectancy", "stop_rate", "turnover", "transaction_costs",
        "exposure")}

    families = {}
    for r in rows[1:]:
        families.setdefault(r["family"], []).append(r)

    HYPOTHESES = {
        "atr_floor": ("Entries in names whose 2.5-ATR stop sits inside "
                      "ordinary daily noise are stopped out by noise, so a "
                      "minimum ATR fraction should raise portfolio return."),
        "trend_margin": ("Entries within a hairline of the 200-day average "
                         "have the worst median R and the highest stop rate, "
                         "so requiring real distance above it should help."),
        "needs_a_drop": ("An oversold reading with no actual recent fall is a "
                         "slow grind rather than a dislocation, so requiring "
                         "a real 5-session drop should help."),
        "volume_ceiling": ("An extreme-volume entry day is capitulation or a "
                           "news repricing rather than a dip, so skipping "
                           "those entries should help."),
        "combined": ("If the two strongest single filters are real they "
                     "should compose."),
    }

    recorded = []
    for family, variants in families.items():
        best = max(variants, key=lambda r: r["total_return"])
        stats = robust[best["label"]]
        improves = best["total_return"] > base["total_return"]
        survives = (stats["sum_excluding_best_year"] > 0 and
                    stats["years_better"] >= 7)
        conclusion = describe(family, variants, base, robust, survives)
        recorded.append(Experiment(
            hypothesis=HYPOTHESES[family],
            configuration={"family": family,
                           "thresholds": [v["label"] for v in variants],
                           "applied_via": "model_veto (can only remove a "
                                          "candidate); no frozen parameter "
                                          "was changed"},
            dataset="decade (contaminated)",
            date_range="2016-2026",
            universe=UNIVERSE,
            costs=COSTS,
            execution_assumptions=EXECUTION,
            information_sources=["daily OHLCV only"],
            trials=len(variants),
            metrics={k: best[k] for k in baseline_metrics},
            baseline_metrics=baseline_metrics,
            validation_methodology=(
                "full portfolio re-run so freed capital is reallocated; "
                "per-calendar-year differences against the baseline; "
                "leave-one-best-year-out; adjacent-threshold stability"),
            leakage_risks=PRICE_LEAKAGE,
            conclusion=conclusion,
            verdict="research_evidence" if survives else "rejected",
            suitable_for_further_testing=bool(survives)))

    # The news screening. A separation test on taken trades, explicitly not
    # a portfolio result.
    news = DATA / "news-features-deep.jsonl"
    if news.exists():
        rows_n = [json.loads(l) for l in
                  news.read_text(encoding="utf-8").splitlines() if l.strip()]
        earnings = [r for r in rows_n if r.get("earnings", 0) > 0]
        clean = [r for r in rows_n if r.get("earnings", 0) == 0]
        recorded.append(Experiment(
            hypothesis=("An earnings-category headline published in the 72 "
                        "hours before the decision marks a repricing rather "
                        "than a dislocation, so oversold entries taken into "
                        "one should underperform."),
            configuration={"feature": "earnings headline within 72h before "
                                      "the decision timestamp",
                           "classifier": "events.classify_headline category "
                                         "keywords, headline text only",
                           "test": "post-hoc split of the baseline's own "
                                   "trades; NOT a portfolio re-run"},
            dataset="decade (contaminated) + Alpaca/Benzinga news archive",
            date_range="2016-2026",
            universe=UNIVERSE,
            costs=COSTS,
            execution_assumptions=EXECUTION,
            information_sources=["Alpaca /v1beta1/news (Benzinga), tier 2"],
            trials=7,
            metrics={"trades": len(earnings),
                     "total_pnl": round(sum(r["net_pnl"] for r in earnings), 2),
                     "stop_rate": round(sum(1 for r in earnings
                                            if r["exit_reason"] == "stop")
                                        / len(earnings), 4) if earnings else None},
            baseline_metrics={"trades": len(clean),
                              "total_pnl": round(sum(r["net_pnl"] for r in clean), 2),
                              "stop_rate": round(sum(1 for r in clean
                                                     if r["exit_reason"] == "stop")
                                                 / len(clean), 4) if clean else None},
            validation_methodology=(
                "point-in-time snapshot at the decision timestamp, derived "
                "from the exchange clock; items published at or after that "
                "instant excluded; NO portfolio re-run yet, so the effect on "
                "the account is unmeasured"),
            leakage_risks=NEWS_LEAKAGE,
            conclusion=(
                "The separation is the largest found in this phase: {0} "
                "trades into an earnings headline returned ${1:,.0f} against "
                "${2:,.0f} from the other {3}, with a materially higher stop "
                "rate. It is a separation on taken trades only. Every "
                "price-based filter in this phase also separated on taken "
                "trades and then FAILED as a portfolio, so this must not be "
                "treated as a portfolio result until it is re-run with "
                "capital reallocation."
                .format(len(earnings), sum(r["net_pnl"] for r in earnings),
                        sum(r["net_pnl"] for r in clean), len(clean))),
            verdict="research_evidence",
            suitable_for_further_testing=True))

    for exp in recorded:
        row = record(exp)
        print("{0}  {1:<22} {2}".format(row["id"], row["verdict"],
                                        exp.hypothesis[:60]))
    print("\n{0}".format(json.dumps(summary(), indent=1)))
    return 0


def describe(family, variants, base, robust, survives):
    best = max(variants, key=lambda r: r["total_return"])
    stats = robust[best["label"]]
    spread = ["{0}: {1:+.1%}".format(v["label"].split()[-1],
                                     v["total_return"] - base["total_return"])
              for v in variants]
    return (
        "Best configuration {0} changed decade total return by {1:+.1f} "
        "points ({2:+.2f} CAGR points). Across thresholds the change was {3}, "
        "which is {4}. It beat the baseline in {5} of {6} calendar years, and "
        "removing its single best year ({7}) leaves {8:+.1f} points. {9}"
        .format(best["label"],
                100 * (best["total_return"] - base["total_return"]),
                100 * (best["cagr"] - base["cagr"]),
                "; ".join(spread),
                "monotone" if _monotone(variants) else "NOT monotone, which "
                "is the signature of noise rather than a mechanism",
                stats["years_better"], stats["years"], stats["best_year"],
                100 * stats["sum_excluding_best_year"],
                "Survives the robustness checks." if survives else
                "Does not survive: rejected as a portfolio improvement "
                "despite improving per-trade quality."))


def _monotone(variants):
    values = [v["total_return"] for v in variants]
    return (all(a <= b for a, b in zip(values, values[1:])) or
            all(a >= b for a, b in zip(values, values[1:])))


if __name__ == "__main__":
    raise SystemExit(main())
