"""Decompose the 841 that H-0015 attributed to "cash". Read-only.

H-0015 inferred cash as a RESIDUAL: passed guard, valid signal, sizing
> 0, not taken. That inference is wrong. Between position_size and the
cash test production has three more exits:

  1. the 2% ADV participation cap can reduce quantity, then
     `if quantity <= 0: continue`
  2. `if fill <= stop_ref: continue`   (buy fill at or below the stop)
  3. `if outlay > cash: report.rejected_for_capacity += 1; continue`

Only (3) is cash. And production already COUNTS it exactly, in
report.rejected_for_capacity, so it never needed inferring.

This measures the true split. No production file is modified; probes
wrap and return genuine values, and baseline equivalence is asserted.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader import portfolio as PM                  # noqa: E402
from event_aware_trader.forward import frozen_fingerprint        # noqa: E402
from event_aware_trader.mean_reversion import (                  # noqa: E402
    MeanReversionConfig, conviction as shipped_conviction)
from event_aware_trader.phase5.metrics import measure            # noqa: E402
from event_aware_trader.research import production_report        # noqa: E402
from forensics_regime import load                                 # noqa: E402

FP = "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b"
_conv = {}
STATS = {"size_calls": 0, "size_zero": 0,
         "participation_calls": 0, "participation_cut": 0,
         "participation_to_zero": 0}


def conviction(symbol, history):
    k = (symbol, len(history), history[0].timestamp if history else None)
    v = _conv.get(k)
    if v is None:
        v = _conv[k] = shipped_conviction(history[-40:])
    return v


def main():
    if frozen_fingerprint() != FP:
        print("REFUSED: fingerprint moved.")
        return 2
    real_size = PM.position_size
    real_cap = PM.cap_by_participation

    def size(*a, **k):
        q, planned = real_size(*a, **k)
        STATS["size_calls"] += 1
        if q <= 0:
            STATS["size_zero"] += 1
        return q, planned

    def cap(quantity, price, adv, frac):
        allowed = real_cap(quantity, price, adv, frac)
        STATS["participation_calls"] += 1
        if allowed < quantity:
            STATS["participation_cut"] += 1
            if allowed <= 0:
                STATS["participation_to_zero"] += 1
        return allowed

    PM.position_size = size
    PM.cap_by_participation = cap
    print("running the frozen baseline with cash-path probes ...", flush=True)
    rep = production_report(load(), conviction=conviction, dataset="decade",
                            purpose="rejection_test",
                            mr_config=MeanReversionConfig())
    PM.position_size, PM.cap_by_participation = real_size, real_cap

    m = measure(rep, "BASELINE").as_dict()
    print("  {0:+.10%} over {1} trades".format(m["total_return"], m["trades"]))
    if abs(m["total_return"] - 0.585889) > 5e-7 or m["trades"] != 698:
        print("STOPPED: probes perturbed the baseline.")
        return 2
    print("  IDENTICAL - probes non-invasive\n")

    cash_rej = getattr(rep, "rejected_for_capacity", None)
    print("=== THE DECOMPOSITION H-0015 GOT WRONG ===")
    print("  H-0015 residual attributed to 'cash'        841")
    print("  production's OWN cash counter")
    print("    report.rejected_for_capacity              {0}".format(cash_rej))
    print()
    print("  position_size calls                         {0:,}".format(
        STATS["size_calls"]))
    print("    of which returned quantity <= 0           {0:,}".format(
        STATS["size_zero"]))
    print("  participation-cap calls                     {0:,}".format(
        STATS["participation_calls"]))
    print("    of which CUT the quantity                 {0:,}".format(
        STATS["participation_cut"]))
    print("    of which cut it to ZERO (-> continue)     {0:,}".format(
        STATS["participation_to_zero"]))
    print()
    residual = 841 - (cash_rej or 0) - STATS["participation_to_zero"]
    print("  841 - cash({0}) - participation_zero({1}) = {2}".format(
        cash_rej, STATS["participation_to_zero"], residual))
    print("  the remainder is the `fill <= stop_ref` exit and any")
    print("  candidate whose signal fired but whose day had already")
    print("  broken on the 3-entry cap before its turn.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
