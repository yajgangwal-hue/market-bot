"""Run H-0033 exactly as registered. Research only; nothing here trades."""

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.modelgov import prereg                          # noqa: E402
from event_aware_trader.research import DATASET_USES, _record_gate_use  # noqa: E402

import h0033_noise_area as na                                           # noqa: E402
import h0033_spec as spec                                               # noqa: E402
import research_gate                                                    # noqa: E402

RESULTS = REPO / "docs" / "phase5" / "h0033-results.json"


def window(name):
    a, b = spec.WINDOWS[name]
    return date.fromisoformat(a), date.fromisoformat(b)


def both(curve, rets):
    return {"rf0": na.metrics(curve, rets), "rf2.3": na.metrics(curve, rets, 0.023)}


def main():
    try:
        registered = prereg.verify("H-0033", spec.hypothesis())
    except prereg.RegistrationError as error:
        print("REFUSED: " + str(error))
        return 2
    folder = research_gate.verify_dataset(spec.DATASET["id"], spec.DATASET["sha256"])
    _record_gate_use(spec.DATASET["id"], "rejection_test", 1, DATASET_USES)
    loaded = na.load_store(folder)
    last = date.fromisoformat(spec.WINDOWS["full"][1])
    sessions = {d: s for d, s in loaded.items() if d <= last}
    days = sorted(sessions)
    out = {"registration": {"seal": registered["seal"], "registered_at": registered["registered_at"]},
           "sessions": len(days), "first": days[0].isoformat(), "last": days[-1].isoformat(),
           "complete_sessions": sum(1 for s in sessions.values() if s.complete),
           "sessions_per_year": dict(sorted(Counter(d.year for d in days).items())),
           "incomplete": [d.isoformat() for d in days if not sessions[d].complete],
           "configs": {}}
    for label, sizing in (("B_full_notional", "full"), ("C_vol_target_4x", "dynamic")):
        res = {}
        for name in spec.WINDOWS:
            a, b = window(name)
            run = na.run(sessions, a, b, sizing=sizing, cost_per_share=spec.COST_PER_SHARE)
            first = run["curve"][0][0]
            spy_curve, spy_rets = na.spy_hold(sessions, first, b)
            res[name] = dict(both(run["curve"], run["daily_returns"]),
                             trades=run["trades"], traded_sessions=run["traded_days"],
                             first_session=first.isoformat(),
                             spy_same_days=both(spy_curve, spy_rets))
        a, b = window("full")
        stress = na.run(sessions, a, b, sizing=sizing, cost_per_share=spec.COST_STRESS)
        free = na.run(sessions, a, b, sizing=sizing, cost_per_share=0.0)
        res["full_costs_doubled"] = {"rf0": na.metrics(stress["curve"], stress["daily_returns"])}
        res["full_no_costs"] = {"rf0": na.metrics(free["curve"], free["daily_returns"])}
        full, overlap, after = (res[w]["rf0"] for w in ("full", "overlap_with_paper", "after_publication"))
        spy_after = res["after_publication"]["spy_same_days"]["rf0"]
        spy_full = res["full"]["spy_same_days"]["rf0"]
        criteria = {
            "R1": (overlap["sharpe"] or 0) >= 1.0,
            "R2": after["cagr"] > 0 and (after["sharpe"] or 0) > (spy_after["sharpe"] or 0),
            "R3": sum(1 for v in full["by_year"].values() if v > 0) >= 8,
            "R4": (res["full_costs_doubled"]["rf0"]["sharpe"] or 0) >= 0.7,
            "R5": abs(full["max_drawdown"]) <= abs(spy_full["max_drawdown"]),
        }
        res["criteria"] = criteria
        res["verdict"] = ("REJECTED" if not (criteria["R1"] and criteria["R2"]) else
                          "PROMISING BUT NOT READY FOR OOS" if all(criteria.values()) else "INCONCLUSIVE")
        out["configs"][label] = res
        print(label, res["verdict"], criteria, flush=True)
    RESULTS.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("wrote " + str(RESULTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
