"""Run H-0036 exactly as registered. Research only; nothing here trades."""

import json
import math
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.modelgov import prereg                          # noqa: E402
from event_aware_trader.research import DATASET_USES, _record_gate_use  # noqa: E402

import h0033_noise_area as na                                           # noqa: E402
import h0034_index_day_rules as dr                                      # noqa: E402
import h0036_spec as spec                                               # noqa: E402
import h0036_ta_universe as ta                                          # noqa: E402
import research_gate                                                    # noqa: E402

RESULTS = REPO / "docs" / "phase5" / "h0036-results.json"


def stats(x: np.ndarray) -> dict:
    n = x.size
    sd = float(x.std(ddof=1)) if n > 1 else 0.0
    mean = float(x.mean())
    return {"sessions": int(n), "mean_daily": mean, "annualised": mean * 252,
            "t": mean / (sd / math.sqrt(n)) if sd > 0 else None,
            "sharpe": mean / sd * math.sqrt(252) if sd > 0 else None,
            "positive_share": float((x > 0).mean())}


def tests(matrix, rules, boot):
    out = ta.reality_check_and_spa(matrix, n_boot=boot["n_boot"], q=boot["q"], seed=boot["seed"])
    kept = np.flatnonzero(out.pop("kept_mask"))
    best = int(kept[out.pop("best_index_among_tested")])
    out["best_rule"] = ta.label(rules[best])
    out["best_rule_index"] = best
    return out


def main():
    try:
        registered = prereg.verify("H-0036", spec.hypothesis())
    except prereg.RegistrationError as error:
        print("REFUSED: " + str(error))
        return 2
    folder = research_gate.verify_dataset(spec.DATASET["id"], spec.DATASET["sha256"])
    _record_gate_use(spec.DATASET["id"], "rejection_test", 1, DATASET_USES)
    last = date.fromisoformat(spec.WINDOWS["full"][1])
    bars = {d: b for d, b in dr.load_bars(folder).items() if d <= last and dr.complete(b)}
    started = time.time()
    series = ta.Series(bars, spec.COST_PER_SHARE)
    rules = ta.universe()
    gross, net = ta.run_universe(series, rules)
    built = time.time() - started
    days = np.array(series.days)
    split = date.fromisoformat(spec.WINDOWS["second_half"][0])
    first, second = days < split, days >= split
    boot = spec.BOOTSTRAP
    out = {"registration": {"seal": registered["seal"], "registered_at": registered["registered_at"]},
           "sessions": int(days.size), "first": str(days[0]), "last": str(days[-1]),
           "first_half_sessions": int(first.sum()), "second_half_sessions": int(second.sum()),
           "rules": len(rules), "seconds_to_build": round(built, 1)}
    out["full_net"] = tests(net, rules, boot)
    out["full_gross"] = tests(gross, rules, boot)
    out["first_half_net"] = tests(net[:, first], rules, boot)
    out["second_half_net"] = tests(net[:, second], rules, boot)
    # persistence: pick on 2016-2020, judge on 2021-2026
    pick = int(np.argmax(net[:, first].mean(axis=1)))
    closes = {d: s for d, s in na.load_store(folder).items() if d <= last}
    second_days = [d for d in days[second]]
    curve, spy = na.spy_hold(closes, second_days[0], second_days[-1])
    spy = np.array(spy)
    out["persistence"] = {"rule": ta.label(rules[pick]), "rule_index": pick,
                          "first_half_net": stats(net[pick, first]),
                          "second_half_net": stats(net[pick, second]),
                          "second_half_gross": stats(gross[pick, second]),
                          "spy_second_half": stats(spy)}
    means = net.mean(axis=1)
    order = np.argsort(-means)
    out["top10_full_net"] = [dict(rule=ta.label(rules[k]), **stats(net[k])) for k in order[:10]]
    fam = {}
    for k, r in enumerate(rules):
        if r[0] not in fam or means[k] > means[fam[r[0]]]:
            fam[r[0]] = k
    out["best_by_family_full_net"] = {f: dict(rule=ta.label(rules[k]), **stats(net[k])) for f, k in fam.items()}
    out["share_positive_full"] = {"net": float((means > 0).mean()),
                                  "gross": float((gross.mean(axis=1) > 0).mean())}
    out["spy_full"] = stats(np.array(na.spy_hold(closes, days[0], days[-1])[1]))
    p = out["persistence"]
    criteria = {
        "R1": out["full_net"]["reality_check_p"] < 0.05 and out["full_net"]["spa_p"] < 0.05,
        "R2": p["second_half_net"]["mean_daily"] > 0 and (p["second_half_net"]["t"] or 0) >= 2.0,
        "R3": (p["second_half_net"]["sharpe"] or -9) > (p["spy_second_half"]["sharpe"] or 0),
    }
    out["criteria"] = criteria
    out["verdict"] = ("REJECTED" if not (criteria["R1"] and criteria["R2"]) else
                      "PROMISING BUT NOT READY FOR OOS" if all(criteria.values()) else "INCONCLUSIVE")
    RESULTS.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("sessions", "rules", "seconds_to_build", "criteria", "verdict")}))
    print("full net:", {k: out["full_net"][k] for k in ("best_rule", "best_mean", "reality_check_p", "spa_p")})
    print("full gross:", {k: out["full_gross"][k] for k in ("best_rule", "best_mean", "reality_check_p", "spa_p")})
    print("wrote " + str(RESULTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
