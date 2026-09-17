"""Record every H-0007 configuration in the ledger, independently.

Mechanical on purpose. Each cutoff gets its own row carrying the clauses
it failed, and the one cutoff that passed A and B is recorded as a SPIKE
with its neighbours' failure in the same row, so nobody can later quote
"+0.003 Sharpe" without meeting the two configurations that say it is
noise. No configuration is described as best, and the verdict is the
adjudicator's, not mine.
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
        "exposure", "win_rate", "profit_factor", "longest_losing_run")
LEAK = [
    "decade is contaminated for the current candidate; ceiling is "
    "research_evidence",
    "thirty-year window NOT read; remains contaminated robustness evidence "
    "at 13 reads",
    "survivorship: today's universe",
    "SPY comparison is PRICE ONLY - SPY dividends are excluded, which "
    "understates the benchmark by roughly 1.3-1.5 CAGR points a year",
    "SEARCH COST: the volatility dimension was chosen after a descriptive "
    "pass over six regime dimensions on this same decade, so this result "
    "carries a multiple-comparison penalty and may not be read as if the "
    "dimension had been named in advance",
    "the abstention decision uses SPY closes through t-1 only; it cannot "
    "see session t, and it can only remove a candidate",
]


def keys(d):
    out = {k: d.get(k) for k in KEYS}
    for extra in ("vs_spy_points", "sessions_denied", "removed_n",
                  "removed_winners", "removed_losers", "removed_winner_pnl",
                  "removed_loser_pnl"):
        if extra in d:
            out[extra] = d[extra]
    return out


def main():
    res = json.loads((REPO / "docs" / "phase5" / "h0007-results.json")
                     .read_text(encoding="utf-8"))
    adj = json.loads((REPO / "docs" / "phase5" / "h0007-adjudication.json")
                     .read_text(encoding="utf-8"))
    base = res["baseline"]
    base_keys = keys(base)
    base_keys["vs_spy_points"] = 100.0 * (base["total_return"] - res["spy_total"])
    verdicts = {v["label"]: v for v in adj["per_configuration"]}

    for row in sorted(res["configurations"], key=lambda r: r["cutoff"]):
        v = verdicts[row["label"]]
        spike = row["label"] in adj["spike"]
        failed = [c for c in ("A", "B", "C") if not v[c]]
        record(Experiment(
            hypothesis=(
                "H-0007 / {0}: no new entries when SPY's 20-day realised "
                "volatility sits below the {1:.4f} expanding percentile as "
                "of the prior close{2}".format(
                    row["label"], row["cutoff"],
                    " [SPIKE: passed A and B, neighbours failed]"
                    if spike else "")),
            configuration={
                "sealed_as": "H-0007", "seal": res["seal"],
                "cutoff": row["cutoff"], "vol_days": 20,
                "threshold_method": "expanding percentile",
                "minimum_history_readings": 252,
                "applied_through": "model_veto (removal only)",
                "family_member": True, "is_spike": spike,
                "clauses_failed": failed,
            },
            dataset="decade (development) only; zero thirty-year reads",
            date_range="2016-01-04 to 2026-09-04",
            universe="230 US equities and ETFs",
            costs="frozen: 2 bps half spread + 4 bps slippage each way, "
                  "$0 commission",
            execution_assumptions=(
                "frozen production candidate, unchanged. Abstention removes "
                "candidates before sizing; open positions, stops, exits and "
                "the 20-bar holding cap are untouched. Idle cash earns 0%."),
            information_sources=["daily OHLCV", "SPY closes through t-1"],
            trials=3, metrics=keys(row), baseline_metrics=base_keys,
            validation_methodology=(
                "pre-registered {0}; equivalence established first (a "
                "never-firing veto reproduced the baseline to 0.000000000000 "
                "drift and the same 698 trades); four sealed clauses "
                "evaluated in order; clause D conditional and NOT "
                "triggered".format(res["seal"][:16])),
            leakage_risks=LEAK,
            conclusion=(
                "Clause A {0} (Sharpe {1:.6f} vs {2:.6f}, {3:+.6f}). "
                "Clause B {4} (maxDD {5:.4%} vs a {6:.4%} ceiling). "
                "Clause C FAILED family-wide: Spearman(cutoff, Sharpe) = "
                "{7:+.4f} where POSITIVE was declared - the gradient runs "
                "exactly backwards, so more abstention gives LESS "
                "risk-adjusted return, not more. Abstention refused trades "
                "whose net P&L was POSITIVE ({8:+,.0f} over {9} refused "
                "trades, {10} winners against {11} losers), and selection "
                "per dollar of notional {12} versus baseline. The mechanical "
                "prior - that a calm tape holds the weak mean-reversion "
                "trades - is contradicted in direction.".format(
                    "passed" if v["A"] else "failed",
                    row["sharpe"], base["sharpe"], row["sharpe"] - base["sharpe"],
                    "passed" if v["B"] else "failed",
                    row["max_drawdown"], -adj["drawdown_ceiling"],
                    adj["spearman_cutoff_sharpe"],
                    row["removed_winner_pnl"] + row["removed_loser_pnl"],
                    row["removed_n"], row["removed_winners"],
                    row["removed_losers"],
                    "rose slightly" if row["attr"]["selection_per"]
                    > res["baseline_attr"]["selection_per"] else "fell")),
            verdict="rejected",
            suitable_for_further_testing=False,
        ))

    # The family-level row. The three cutoffs are one hypothesis and the
    # direction finding belongs to the family, not to any member.
    record(Experiment(
        hypothesis="H-0007 FAMILY: volatility-percentile entry abstention",
        configuration={"sealed_as": "H-0007", "seal": res["seal"],
                       "cutoffs": [0.20, 0.25, 1 / 3], "family_row": True,
                       "declared_direction_sharpe": "POSITIVE",
                       "observed_direction_sharpe": "NEGATIVE"},
        dataset="decade (development) only; zero thirty-year reads",
        date_range="2016-01-04 to 2026-09-04",
        universe="230 US equities and ETFs",
        costs="frozen",
        execution_assumptions="frozen production candidate, unchanged",
        information_sources=["daily OHLCV", "SPY closes through t-1"],
        trials=3,
        metrics={"spearman_cutoff_sharpe": adj["spearman_cutoff_sharpe"],
                 "spearman_cutoff_total_return":
                     adj["spearman_cutoff_total_return"],
                 "configurations_passing_abc": 0,
                 "thirty_year_reads": 13},
        baseline_metrics={"spearman_cutoff_sharpe": None,
                          "spearman_cutoff_total_return": None,
                          "configurations_passing_abc": None,
                          "thirty_year_reads": 13},
        validation_methodology=(
            "pre-registered direction, evaluated once across all three "
            "sealed cutoffs; no cutoff added, removed or re-run"),
        leakage_risks=LEAK,
        conclusion=(
            "REJECTED, and informative in the rejecting. The declared "
            "direction was Spearman(cutoff, Sharpe) POSITIVE; the observed "
            "value is -1.0000, a perfect reversal across all three cutoffs. "
            "Total return moved as declared (-1.0000) but that alone cannot "
            "accept. The single cutoff that cleared A and B, C quintile, "
            "gained +0.003240 Sharpe - 0.99% of one standard error of the "
            "Sharpe estimate - while earning 1.67% LESS per day on 2.29% "
            "less volatility, so its ratio rose because the denominator "
            "shrank, which the registration named in advance as not being "
            "evidence of improved selection. Every cutoff fell further "
            "behind SPY. Clause D was not evaluated and the thirty-year "
            "window was not opened; its access count stays at 13. The "
            "durable finding is the sign: on this decade, a calm tape is "
            "where this strategy's entries work BEST, not worst."),
        verdict="rejected",
        suitable_for_further_testing=False,
    ))

    print(json.dumps(summary(), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
