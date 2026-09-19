"""Record H-0009 in the ledger. One row per threshold, plus the family.

Mechanical. Each row carries the clauses it failed and the displacement
decomposition that explains WHY, so a later reader meets the churn
finding rather than just a negative return column.
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
        "exposure", "win_rate", "profit_factor", "stop_rate",
        "average_winner", "average_loser")
LEAK = [
    "decade is contaminated for this candidate AND for this parameter "
    "specifically, which has now been swept on it three times",
    "SEARCH COST: the 35-40 region was chosen after a seven-band RSI table "
    "computed on this same decade on 2026-09-18, so this carries a "
    "multiple-comparison penalty and may not be read as if named in advance",
    "PRIOR SWEEPS: rsi_entry was swept on two years, then on the decade on "
    "2026-09-07 (30/35/40/45). 39 and 40 were excluded from H-0009 BEFORE "
    "sealing because that sweep already measured them as failures",
    "survivorship: today's universe",
    "SPY comparison is PRICE ONLY, understating the benchmark by roughly "
    "1.3-1.5 CAGR points a year",
    "thirty-year window NOT read; stays at 13",
]


def keys(d):
    out = {k: d.get(k) for k in KEYS}
    return out


def main():
    adj = json.loads((REPO / "docs" / "phase5" / "h0009-adjudication.json")
                     .read_text(encoding="utf-8"))
    base = adj["baseline"]
    base_keys = keys(base)
    base_keys["vs_spy_points"] = 100.0 * (base["total_return"]
                                          - adj["spy_total"])
    verdicts = {v["label"]: v for v in adj["per_configuration"]}

    for label in ("A rsi36", "B rsi37", "C rsi38"):
        m = adj["configurations"][label]
        v = verdicts[label]
        d = adj["displacement"][label]
        q = adj["quality"].get(label, {})
        failed = [c for c in ("A", "B", "C", "D") if not v[c]]
        met = keys(m)
        met["vs_spy_points"] = 100.0 * (m["total_return"] - adj["spy_total"])
        met.update({"delta_points_vs_baseline": 100.0 * v["delta"],
                    "kept_of_baseline_698": d["kept"],
                    "empty_slot_adds": d["empty"],
                    "empty_slot_pnl": d["empty_pnl"],
                    "swaps": d["swaps"], "swap_gain": d["swap_gain"],
                    "newly_admitted_35_38": d["newly_admitted_35_38"]})
        record(Experiment(
            hypothesis=(
                "H-0009 / {0}: admit RSI {1} candidates to compete for the "
                "existing unchanged slots".format(label, v["rsi"])),
            configuration={"sealed_as": "H-0009", "seal": adj["seal"],
                           "parameter": "MeanReversionConfig.rsi_entry",
                           "value": v["rsi"], "baseline_value": 35.0,
                           "family_member": True, "clauses_failed": failed,
                           "only_parameter_changed": True},
            dataset="decade (development) only; zero thirty-year reads",
            date_range="2016-01-04 to 2026-09-04",
            universe="230 US equities and ETFs",
            costs="frozen: 2 bps half spread + 4 bps slippage each way, "
                  "$0 commission, 0.652% rule-exit haircut",
            execution_assumptions=(
                "frozen production candidate in every respect except "
                "rsi_entry, passed via run_portfolio's existing mr_config "
                "argument. Stops, sizing, 20-bar cap, bucket cap of 1, "
                "12-position cap, 3-per-day cap, candidate ordering and the "
                "benchmark are untouched. No production file modified."),
            information_sources=["daily OHLCV through the decision bar"],
            trials=3, metrics=met, baseline_metrics=base_keys,
            validation_methodology=(
                "pre-registered {0}; baseline equivalence established first "
                "(+58.5889000000% over 698 trades through the same override "
                "path); five sealed clauses - return above a 2-point "
                "complexity penalty, drawdown within 1.10x, gradient not "
                "spike, displacement, leave-one-best-year-out".format(
                    adj["seal"][:16])),
            leakage_risks=LEAK,
            conclusion=(
                "Total return {0:+.2%} against the baseline's {1:+.2%}, a "
                "delta of {2:+.2f} points. Max drawdown {3:.4%} against a "
                "{4:.4%} ceiling. Clauses failed: {5}. Displacement: of the "
                "baseline's 698 trades only {6} survive; {7} additions took "
                "genuinely empty slots and earned {8:+,.0f} in total, and "
                "{9} swaps netted {10:+,.0f}. The newly admitted RSI 35-38 "
                "band realised {11} per trade against {12} for the <=35 "
                "band, with lower favourable excursion for the same adverse "
                "excursion - a shallower dislocation gives the 2.5-ATR stop "
                "the same risk with less upside.".format(
                    m["total_return"], base["total_return"],
                    100 * v["delta"], m["max_drawdown"], -adj["ceiling"],
                    ", ".join(failed), d["kept"], d["empty"],
                    d["empty_pnl"], d["swaps"], d["swap_gain"],
                    "${0:,.0f}".format(q.get("35-38", {}).get("mean_pnl", 0)),
                    "${0:,.0f}".format(q.get("<=35", {}).get("mean_pnl", 0)))),
            verdict="rejected",
            suitable_for_further_testing=False,
        ))

    record(Experiment(
        hypothesis="H-0009 FAMILY: does the RSI 35-40 name-level hump "
                   "survive the portfolio's slot constraint?",
        configuration={"sealed_as": "H-0009", "seal": adj["seal"],
                       "thresholds": [36.0, 37.0, 38.0], "family_row": True,
                       "excluded_before_sealing": [39.0, 40.0],
                       "declared_direction_drawdown": "DEEPENS (expected)",
                       "declared_direction_return": "AMBIGUOUS",
                       "observed_return_direction": "monotone DOWN"},
        dataset="decade (development) only; zero thirty-year reads",
        date_range="2016-01-04 to 2026-09-04",
        universe="230 US equities and ETFs",
        costs="frozen", execution_assumptions="frozen; one parameter moved",
        information_sources=["daily OHLCV through the decision bar"],
        trials=3,
        metrics={"spearman_threshold_delta": adj["spearman"],
                 "deltas_points": adj["deltas_points"],
                 "configurations_passing": 0,
                 "rsi_entry_after": 35.0, "thirty_year_reads": 13},
        baseline_metrics={"spearman_threshold_delta": None,
                          "configurations_passing": None,
                          "rsi_entry_after": 35.0, "thirty_year_reads": 13},
        validation_methodology="pre-registered family of three adjacent "
                               "integer thresholds; no value added, moved or "
                               "re-run after the surface was visible",
        leakage_risks=LEAK,
        conclusion=(
            "REJECTED, with Spearman(threshold, return delta) = -1.0000: "
            "every loosening is worse and worse in order, at -14.34, -54.51 "
            "and -55.27 points. Drawdown deepens monotonically and breaches "
            "the 14.2806% ceiling at every threshold, including rsi36 by "
            "0.11 points. The central finding is NOT that new candidates "
            "displace old ones one-for-one: empty-slot additions were "
            "positive but trivial (+$3,023 over 202 trades at rsi36, about "
            "$15 each). The damage is CHURN. Of the baseline's 698 trades "
            "only 425 survive at rsi36, 273 at rsi37 and 201 at rsi38, "
            "because the bucket and per-day caps are resolved in candidate "
            "order and a 35-38 name arriving in a bucket locks out the <=35 "
            "name that would have claimed it. The <=35 band's own realised "
            "P&L degrades from $73 to $26 to $12 per trade as the gate "
            "loosens - the survivors are a worse subset. This reconciles "
            "the breadth pass's name-level hump with the portfolio result: "
            "35-38 names run 4.95% in favour at best against <=35's 5.52% "
            "for the same adverse excursion, so a forward-return "
            "measurement sees a hump that the 2.5-ATR stop and 20-bar cap "
            "erase. Three independent sweeps of rsi_entry now agree; the "
            "entry-threshold direction is closed."),
        verdict="rejected",
        suitable_for_further_testing=False,
    ))
    print(json.dumps(summary(), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
