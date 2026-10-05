"""Run H-0034 and H-0035 exactly as registered. Research only; nothing here trades."""

import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.modelgov import prereg                          # noqa: E402
from event_aware_trader.research import DATASET_USES, _record_gate_use  # noqa: E402

import h0033_noise_area as na                                           # noqa: E402
import h0034_index_day_rules as dr                                      # noqa: E402
import h0034_spec as spec                                               # noqa: E402
import research_gate                                                    # noqa: E402

RESULTS = REPO / "docs" / "phase5" / "h0034-h0035-results.json"
RULES = {"H-0034": "orb", "H-0035": "vwap"}


def both(curve, rets):
    return {"rf0": na.metrics(curve, rets), "rf2.3": na.metrics(curve, rets, 0.023)}


def main():
    registered = {}
    for h in spec.hypotheses():
        try:
            registered[h.hypothesis_id] = prereg.verify(h.hypothesis_id, h)
        except prereg.RegistrationError as error:
            print("REFUSED: " + str(error))
            return 2
    folder = research_gate.verify_dataset(spec.DATASET["id"], spec.DATASET["sha256"])
    _record_gate_use(spec.DATASET["id"], "rejection_test", 1, DATASET_USES)
    last = date.fromisoformat(spec.LAST_SESSION)
    sessions = {d: b for d, b in dr.load_bars(folder).items() if d <= last}
    closes = {d: s for d, s in na.load_store(folder).items() if d <= last}
    out = {"registrations": {k: {"seal": v["seal"], "registered_at": v["registered_at"]}
                             for k, v in registered.items()},
           "sessions": len(sessions),
           "complete_sessions": sum(1 for b in sessions.values() if dr.complete(b)),
           "hypotheses": {}}
    for hid, rule in RULES.items():
        res = {}
        for name, (a, b) in spec.WINDOWS[hid].items():
            a, b = date.fromisoformat(a), date.fromisoformat(b)
            row = {}
            variants = [("realistic", spec.COST_PRIMARY, dr.STOP_SLIPPAGE),
                        ("paper_cost", spec.COST_PAPER, dr.STOP_SLIPPAGE),
                        ("stress", spec.COST_STRESS, dr.STOP_SLIPPAGE), ("no_cost", 0.0, dr.STOP_SLIPPAGE)]
            if rule == "orb":
                variants += [("realistic_stops_at_level", spec.COST_PRIMARY, 0.0),
                             ("paper_cost_stops_at_level", spec.COST_PAPER, 0.0)]
            for label, cost, slip in variants:
                run = dr.run(sessions, a, b, rule, cost, stop_slippage=slip)
                row[label] = dict(both(run["curve"], run["daily_returns"]), trades=run["trades"],
                                  traded_sessions=run["traded_days"], outcomes=run["outcomes"],
                                  first_session=run["curve"][0][0].isoformat())
            first = date.fromisoformat(row["realistic"]["first_session"])
            row["spy_same_days"] = both(*na.spy_hold(closes, first, b))
            res[name] = row
        spy_paper = res["paper_window"]["spy_same_days"]["rf0"]
        paper = res["paper_window"]["paper_cost"]["rf0"]
        after = res["after_publication"]["realistic"]["rf0"]
        spy_after = res["after_publication"]["spy_same_days"]["rf0"]
        full = res["full"]["realistic"]["rf0"]
        criteria = {
            "R1": paper["cagr"] > spy_paper["cagr"] and (paper["sharpe"] or 0) > (spy_paper["sharpe"] or 0),
            "R2": after["cagr"] > 0 and (after["sharpe"] or 0) > (spy_after["sharpe"] or 0),
            "R3": sum(1 for v in full["by_year"].values() if v > 0) >= 8,
            "R4": (res["full"]["stress"]["rf0"]["sharpe"] or 0) >= 0.7,
            "R5": abs(full["max_drawdown"]) <= abs(res["full"]["spy_same_days"]["rf0"]["max_drawdown"]),
        }
        res["criteria"] = criteria
        res["verdict"] = ("REJECTED" if not (criteria["R1"] and criteria["R2"]) else
                          "PROMISING BUT NOT READY FOR OOS" if all(criteria.values()) else "INCONCLUSIVE")
        out["hypotheses"][hid] = res
        print(hid, rule, res["verdict"], criteria, flush=True)
    RESULTS.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("wrote " + str(RESULTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
