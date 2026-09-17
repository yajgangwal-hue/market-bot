"""Record H-0008 in the ledger. One row per percentile, plus the family.

Mechanical. Each row carries the clauses it failed and the value it
measured. The family row carries the finding that matters: the haircut
was hypothesised to be too conservative and the measurement says the
opposite at every registered percentile.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.phase5.ledger import (                 # noqa: E402
    Experiment, record, summary)

LEAK = [
    "execution calibration, NOT market edge; nothing here changes a trade",
    "the trigger is located by forward walk and halts at the first "
    "crossing, so no later bar can move it; the drift then reads the "
    "session close as the measured quantity and never as a decision input",
    "RECONSTRUCTION, not live accrual: the live trigger-time distribution "
    "is still unverified at 3 logged rule exits",
    "coverage is 160 of 459 rule exits (35%): the intraday cache spans "
    "2023-05-22 to 2026-09-15 and holds 98 of 230 symbols, so the "
    "measurement is of the recent window and the larger names",
    "the exit DATES come from the simulator; 1.9% of held sessions cross "
    "RSI 60 intraday and close below it, which no haircut models at any "
    "value",
    "thirty-year window NOT read; stays at 13",
]


def main():
    d = json.loads((REPO / "docs" / "phase5" / "h0008-drift.json")
                   .read_text(encoding="utf-8"))
    adj = json.loads((REPO / "docs" / "phase5" / "h0008-adjudication.json")
                     .read_text(encoding="utf-8"))
    current = d["current_haircut"]
    base = {"haircut": current,
            "source": "worst of three trigger-time point estimates on 155 "
                      "exits"}
    verdicts = {v["label"]: v for v in adj["per_configuration"]}

    for cfg in d["configurations"]:
        v = verdicts[cfg["label"]]
        failed = [c for c in ("A", "B", "C", "D") if not v[c]]
        record(Experiment(
            hypothesis=(
                "H-0008 / {0}: the {1}th percentile of the measured "
                "trigger-to-close drift as a replacement for the 0.652% "
                "rule-exit haircut".format(cfg["label"], cfg["percentile"])),
            configuration={"sealed_as": "H-0008", "seal": d["seal"],
                           "percentile": cfg["percentile"],
                           "family_member": True, "clauses_failed": failed,
                           "kind": "execution_calibration"},
            dataset="five-minute intraday 2023-05-22 to 2026-09-15, 98 "
                    "symbols; decade only for the baseline and exit dates",
            date_range="2023-05-22 to 2026-09-15",
            universe="98 symbols present in the intraday cache",
            costs="unchanged; CostModel is applied on top of the haircut "
                  "and was not re-estimated",
            execution_assumptions="frozen production candidate, unchanged. "
                                  "H-0008 alters no order, size or rule.",
            information_sources=["five-minute bars", "prior daily closes"],
            trials=3,
            metrics={"measured_value": cfg["value"],
                     "ratio_to_charged": cfg["value"] / current,
                     "first_half": cfg["first_half"],
                     "second_half": cfg["second_half"],
                     "half_gap": cfg["half_gap"],
                     "sample": d["reconstructed"]},
            baseline_metrics=dict(base, measured_value=current,
                                  ratio_to_charged=1.0),
            validation_methodology=(
                "pre-registered {0}; baseline equivalence established first "
                "(+58.5889% reproduced on 698 trades); four clauses - "
                "sample, stability, concentration, direction - none of "
                "which is a performance test".format(d["seal"][:16])),
            leakage_risks=LEAK,
            conclusion=(
                "Measured {0:.4%}, which is {1:.2f}x what is charged. "
                "Clause D required it to sit BELOW 0.652% and it does not. "
                "Clause B (halves within 0.25 points) {2}. The registered "
                "direction is contradicted: at this percentile the adverse "
                "drift is larger than the haircut, not smaller.".format(
                    cfg["value"], cfg["value"] / current,
                    "passed at {0:.4%}".format(cfg["half_gap"]) if v["B"]
                    else "FAILED at {0:.4%}".format(cfg["half_gap"]))),
            verdict="rejected",
            suitable_for_further_testing=False,
        ))

    record(Experiment(
        hypothesis="H-0008 FAMILY: is the 0.652% rule-exit haircut "
                   "unnecessarily conservative?",
        configuration={"sealed_as": "H-0008", "seal": d["seal"],
                       "percentiles": [75, 90, 95], "family_row": True,
                       "declared_direction": "percentile BELOW 0.652%",
                       "observed": "every percentile ABOVE 0.652%",
                       "haircut_changed": False,
                       "kind": "execution_calibration"},
        dataset="five-minute intraday 2023-05-22 to 2026-09-15, 98 symbols",
        date_range="2023-05-22 to 2026-09-15",
        universe="98 symbols present in the intraday cache",
        costs="unchanged", execution_assumptions="frozen, unchanged",
        information_sources=["five-minute bars", "prior daily closes"],
        trials=3,
        metrics={"n": d["reconstructed"], "mean": d["mean"],
                 "median": d["median"], "stdev": d["stdev"],
                 "p75": d["percentiles"]["75"], "p90": d["percentiles"]["90"],
                 "p95": d["percentiles"]["95"], "worst": d["worst"],
                 "adverse_share": d["adverse_share"],
                 "unmodellable_share": (d["unmodellable"]["crossed_intraday"]
                                        / d["unmodellable"]["closed_below_60"]),
                 "haircut_after": current},
        baseline_metrics={"haircut_after": current},
        validation_methodology="pre-registered percentile rule; the VALUE "
                               "fell out of the data and was not chosen",
        leakage_risks=LEAK,
        conclusion=(
            "REJECTED, and the rejection confirms the production setting. "
            "The hypothesis was that 0.652% is more conservative than the "
            "data supports. Measured on 160 reconstructed rule exits the "
            "adverse drift is LARGER at every registered percentile: p75 "
            "0.6712% (1.03x), p90 1.4362% (2.20x), p95 1.8327% (2.81x). "
            "The haircut STANDS UNCHANGED and at the bounding percentiles "
            "is arguably too low. Recorded but NOT adopted: the mean drift "
            "is +0.2129%, below what is charged - H-0008 registered a "
            "percentile of the adverse tail rather than the mean because "
            "portfolio.py calls the haircut a conservative bound and not a "
            "best guess, and switching to the mean after seeing that it "
            "flatters is precisely what pre-registration prevents. Whether "
            "the haircut should bound or estimate is a legitimate future "
            "registration, not a conclusion here. Ceiling on the whole "
            "exercise: 46 of 2,457 held sessions (1.9%) cross RSI 60 "
            "intraday and close below it, so the live bot exits where the "
            "simulator holds and no haircut value represents that."),
        verdict="rejected",
        suitable_for_further_testing=False,
    ))
    print(json.dumps(summary(), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
