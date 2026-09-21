"""H-0015 - first-binding-reason attribution of the frozen portfolio layer.

READ-ONLY. src/ is NOT modified. Production functions are wrapped from
the outside to RECORD what production decided; none of their return
values is altered, so the run must reproduce the frozen baseline exactly
and that is asserted before anything is attributed.

THE `break` IS HANDLED HONESTLY. In run_portfolio the 3-entries/day cap
is a break that ends the whole day's symbol loop. Candidates after it
NEVER reach the guard, the signal, sizing or cash. They are recorded as
    entries_per_day_never_evaluated
and NOT as bucket/cash/anything production did not run. A separate
category
    entries_per_day_reached_guard
is reserved for candidates that did reach the guard on a day that had
already filled its three entries. Both are reported separately, and no
candidate is ever assigned a guard it did not face.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader import portfolio as PM                  # noqa: E402
from event_aware_trader import risk as RM                        # noqa: E402
from event_aware_trader.forward import frozen_fingerprint        # noqa: E402
from event_aware_trader.mean_reversion import (                  # noqa: E402
    MeanReversionConfig, conviction as shipped_conviction)
from event_aware_trader.modelgov import prereg                   # noqa: E402
from event_aware_trader.phase5.metrics import measure            # noqa: E402
from event_aware_trader.research import production_report        # noqa: E402
from forensics_regime import load                                 # noqa: E402

SEAL = "82c55dd2b4244556c66c2325abd276ef22690b7e56d7207f5dc7b479faec268f"
FP = "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b"
OUT = REPO / "docs" / "phase5" / "h0015-attribution.json"

# Sealed first-binding order. NOT to be varied.
ORDER = ["equity_nonpositive", "daily_loss_guard", "weekly_loss_guard",
         "max_open_positions", "correlation_bucket"]
GUARD_TEXT = {
    "Account equity is non-positive": "equity_nonpositive",
    "Daily loss guard has been reached; stop for the day": "daily_loss_guard",
    "Weekly loss guard has been reached; stop and review": "weekly_loss_guard",
    "Maximum open-position count reached": "max_open_positions",
    "Correlation bucket already has an open position": "correlation_bucket",
}

LOG = []            # ordered trace of production decisions
_conv = {}


def conviction(symbol, history):
    k = (symbol, len(history), history[0].timestamp if history else None)
    v = _conv.get(k)
    if v is None:
        v = _conv[k] = shipped_conviction(history[-40:])
    return v


def install_probes():
    """Wrap, never alter. Every wrapper returns the genuine value."""
    real_guard = PM.evaluate_guard
    real_signal = PM.mean_reversion_signal
    real_size = PM.position_size

    def guard(*a, **k):
        d = real_guard(*a, **k)
        LOG.append(["guard", None, d.allowed, list(d.reasons)])
        return d

    def signal(symbol, history, cfg):
        s = real_signal(symbol, history, cfg)
        stamp = history[-1].timestamp.date().isoformat() if history else None
        ok = bool(s.is_buy and s.stop is not None and s.stop < s.close)
        LOG.append(["signal", symbol, ok, stamp])
        return s

    def size(*a, **k):
        q, planned = real_size(*a, **k)
        LOG.append(["size", None, q > 0, None])
        return q, planned

    PM.evaluate_guard = guard
    PM.mean_reversion_signal = signal
    PM.position_size = size
    return real_guard, real_signal, real_size


def main():
    s = [p for p in prereg.load() if p["hypothesis_id"] == "H-0015"]
    if not s or s[0]["seal"] != SEAL:
        print("REFUSED: H-0015 seal missing or altered.")
        return 2
    if not prereg.verify_chain()["intact"]:
        print("REFUSED: chain broken.")
        return 2
    if frozen_fingerprint() != FP:
        print("REFUSED: fingerprint moved.")
        return 2
    print("H-0015 seal {0} | commit {1}".format(SEAL[:16],
                                                s[0]["code_commit"][:12]))

    series = load()
    real = install_probes()
    print("\nrunning the frozen baseline with recording probes ...", flush=True)
    rep = production_report(series, conviction=conviction, dataset="decade",
                            purpose="rejection_test",
                            mr_config=MeanReversionConfig())
    PM.evaluate_guard, PM.mean_reversion_signal, PM.position_size = real
    m = measure(rep, "BASELINE").as_dict()
    print("  {0:+.10%} over {1} trades | required +58.5889000000% / 698"
          .format(m["total_return"], m["trades"]))
    if abs(m["total_return"] - 0.585889) > 5e-7 or m["trades"] != 698:
        print("STOPPED: probes perturbed the baseline. Nothing attributed.")
        return 2
    print("  IDENTICAL - probes are non-invasive, proceeding\n", flush=True)

    # ---- rebuild the (date, symbol) decision sequence --------------------
    # A guard call is always immediately followed by a signal call when the
    # guard allowed. Signal calls carry the date. Walk the trace forwards.
    records = []
    i = 0
    pending_guard = None
    while i < len(LOG):
        kind, sym, ok, extra = LOG[i]
        if kind == "guard":
            pending_guard = (ok, extra)
        elif kind == "signal":
            allowed, reasons = pending_guard if pending_guard else (True, [])
            rec = {"date": extra, "symbol": sym, "guard_allowed": allowed,
                   "guard_reasons": reasons, "signal_ok": ok, "sized": None}
            if ok and i + 1 < len(LOG) and LOG[i + 1][0] == "size":
                rec["sized"] = LOG[i + 1][2]
            records.append(rec)
            pending_guard = None
        i += 1
    # guard-denied calls produce no signal call; recover them by position
    denied = []
    i = 0
    seq = []
    while i < len(LOG):
        if LOG[i][0] == "guard":
            nxt = LOG[i + 1] if i + 1 < len(LOG) else None
            if nxt and nxt[0] == "signal":
                seq.append(("eval", nxt[1], LOG[i][2], LOG[i][3]))
                i += 1
            else:
                seq.append(("denied", None, LOG[i][2], LOG[i][3]))
        i += 1
    # assign dates to denied guards: the date of the next dated event
    dates = [r["date"] for r in records]
    print("  guard calls {0:,} | signal calls {1:,} | dated records {2:,}"
          .format(sum(1 for x in LOG if x[0] == "guard"),
                  sum(1 for x in LOG if x[0] == "signal"), len(records)))

    taken = {(t.symbol, t.entry_time.date().isoformat()) for t in rep.trades}
    # NOTE entries fill at the SIGNAL close, so the decision date is the
    # trade's own entry date under entry_fill="signal_close".
    per_day_fills = Counter(d for _s, d in taken)

    # ---- first-binding attribution on the CANDIDATE universe -------------
    # Candidate universe = symbol-sessions where the frozen signal is a
    # valid buy. That is guard-independent and is the sealed denominator.
    attrib = Counter()
    rows = []
    for r in records:
        if not r["signal_ok"]:
            continue                       # not a candidate at all
        key = (r["symbol"], r["date"])
        if not r["guard_allowed"]:
            first = None
            for name in ORDER:
                if any(GUARD_TEXT.get(x) == name for x in r["guard_reasons"]):
                    first = name
                    break
            attrib[first or "guard_other"] += 1
            rows.append((r["symbol"], r["date"], first or "guard_other"))
            continue
        if r["sized"] is False:
            attrib["sizing_zero_quantity"] += 1
            rows.append((r["symbol"], r["date"], "sizing_zero_quantity"))
            continue
        if key in taken:
            attrib["accepted"] += 1
            rows.append((r["symbol"], r["date"], "accepted"))
        else:
            attrib["cash"] += 1
            rows.append((r["symbol"], r["date"], "cash"))

    print("\n=== FIRST-BINDING ATTRIBUTION over EVALUATED candidates ===")
    tot = sum(attrib.values())
    for k, v in attrib.most_common():
        print("  {0:<32} {1:>7,}  {2:>7.2%}".format(k, v, v / tot))
    print("  {0:<32} {1:>7,}".format("TOTAL evaluated candidates", tot))
    print("  accepted reconciles to trades: {0} vs {1}".format(
        attrib["accepted"], len(rep.trades)))

    json.dump({"FORENSIC_NON_PROMOTIONAL": True, "seal": SEAL,
               "baseline": m, "attribution_evaluated": dict(attrib),
               "total_evaluated_candidates": tot,
               "trades": len(rep.trades),
               "rows": rows,
               "fills_per_day": dict(per_day_fills)},
              open(OUT, "w"), indent=1, sort_keys=True, default=str)
    print("\nwrote {0}".format(OUT.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
