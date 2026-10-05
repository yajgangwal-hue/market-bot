"""Run H-0032 exactly as registered. Research only; nothing here trades."""

import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.modelgov import prereg                          # noqa: E402
from event_aware_trader.research import DATASET_USES, _record_gate_use, load_tbill_rates  # noqa: E402

import h0032_intraday_momentum as im                                    # noqa: E402
import h0032_spec as spec                                               # noqa: E402
import research_gate                                                    # noqa: E402

RESULTS = REPO / "docs" / "phase5" / "h0032-results.json"
SPLIT = date(2021, 1, 1)


def main():
    try:
        registered = prereg.verify("H-0032", spec.hypothesis())
    except prereg.RegistrationError as error:
        print("REFUSED: " + str(error))
        return 2
    folder = research_gate.verify_dataset(spec.DATASET["id"], spec.DATASET["sha256"])
    _record_gate_use(spec.DATASET["id"], "rejection_test", 1, DATASET_USES)
    prices = im.load_store(folder)
    rows = im.daily_rows(prices, last_day=date.fromisoformat(spec.LAST_SESSION))
    halves = {"2016-2020": [r for r in rows if r[0] < SPLIT],
              "2021-" + spec.LAST_SESSION: [r for r in rows if r[0] >= SPLIT]}
    rates = load_tbill_rates(REPO / "data" / "tbill.csv")

    def bill(day):
        for back in range(8):
            probe = date.fromordinal(day.toordinal() - back)
            if probe in rates:
                return rates[probe]
        return 0.0

    out = {"registration": {"seal": registered["seal"], "registered_at": registered["registered_at"]},
           "sessions": len(rows), "first": rows[0][0].isoformat(), "last": rows[-1][0].isoformat(),
           "regression": {"full": im.ols([r[1] for r in rows], [r[2] for r in rows])},
           "long_only": {}, "long_short_2bp": None}
    for label, part in halves.items():
        out["regression"][label] = im.ols([r[1] for r in part], [r[2] for r in part])
    for bps in spec.COSTS_BPS:
        trades = im.strategy_returns(rows, bps / 1e4)
        out["long_only"]["{0:g}bp".format(bps)] = {
            "all": im.summarise(trades),
            "halves": {label: im.summarise(im.strategy_returns(part, bps / 1e4))
                       for label, part in halves.items()},
            "account": im.account(trades, rows, bill)}
    out["long_short_2bp"] = im.summarise(im.strategy_returns(rows, 0.0002, long_short=True))
    p = out["long_only"]["2bp"]
    criteria = {
        "R1": (p["all"].get("mean") or 0) > 0 and (p["all"].get("t") or 0) >= 2.0,
        "R2": all((v.get("mean") or 0) > 0 for v in p["halves"].values()),
        "R3": out["regression"]["full"]["beta"] > 0 and out["regression"]["full"]["t"] >= 2.0,
        "R4": (out["long_only"]["6bp"]["all"].get("mean") or 0) > 0,
    }
    out["criteria"] = criteria
    out["verdict"] = ("REJECTED" if not criteria["R1"] else
                      "PROMISING BUT NOT READY FOR OOS" if all(criteria.values()) else "INCONCLUSIVE")
    RESULTS.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("sessions", "first", "last", "criteria", "verdict")}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
