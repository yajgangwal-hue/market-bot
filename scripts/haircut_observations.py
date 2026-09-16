"""Phase 4 §7. Collect live trigger-to-fill observations. Report at ~30.

The backtest charges a frozen 0.652% haircut on every RULE exit, to stand
for the gap between the close that triggers the exit and the price the
order actually gets. It is a BOUND, argued from spread and typical
slippage, not a measurement. This script measures it.

Eligible exits are `reverted` (RSI recovered) and `time` (holding cap) -
the two the haircut applies to. A `stop` exit is excluded: its slippage is
a different quantity with a different distribution, and pooling them would
flatter whichever is smaller.

Three rules the brief fixes and this script obeys:

  - the frozen 0.652% does not move during the observation period;
  - below ~30 eligible exits, the sample size is reported and the
    distribution is NOT, because a median over four trades is decoration;
  - a difference between the observed value and the frozen bound does not
    license replacing the bound. That is a separate reviewed change, and
    historical results are never restated under it.

  python scripts/haircut_observations.py            # offline, from the log
  python scripts/haircut_observations.py --broker   # match fills at Alpaca
"""

import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

AUDIT = REPO / "data" / "autotrade-audit.jsonl"
OUT = REPO / "data" / "haircut-observations.jsonl"

#: The exits the haircut applies to. A stop exit is a different quantity.
ELIGIBLE_REASONS = ("reverted", "time")

#: The frozen bound. Read, never written, by this script.
FROZEN_HAIRCUT = 0.00652

#: Below this, report the count and nothing else.
MINIMUM_SAMPLE = 30


def triggers(rows):
    """Eligible rule exits with a decision-time reference price.

    Exits logged before the loop recorded `last` and `exit_reason` are
    skipped rather than guessed at: without the trigger price there is no
    observation to make, and inferring one from the proceeds would measure
    the fill against itself.
    """
    out = []
    for row in rows:
        if row.get("event") != "exit":
            continue
        d = row.get("detail") or {}
        reason = d.get("exit_reason")
        trigger = d.get("last")
        if reason not in ELIGIBLE_REASONS or not trigger:
            continue
        result = d.get("result") or {}
        out.append({
            "at": row.get("at"),
            "symbol": d.get("symbol"),
            "reason": reason,
            "trigger_price": float(trigger),
            "order_id": result.get("order_id") if isinstance(result, dict) else None,
            "quantity": d.get("quantity"),
        })
    return out


def slippage(trigger_price, fill_price):
    """Fraction of the trigger price given up on the way out.

    Positive means the fill was WORSE than the trigger, which is the
    direction the haircut charges for. A negative value (a better fill) is
    kept rather than clipped: clipping the favourable tail would bias the
    measured mean upward and make the frozen bound look conservative when
    it is not.
    """
    if not trigger_price:
        return None
    return (trigger_price - fill_price) / trigger_price


def match_fills(observations, fills):
    """Pair each trigger with its fill, by order id where one exists."""
    by_order = {}
    for f in fills:
        if f.get("order_id"):
            by_order.setdefault(str(f["order_id"]), []).append(f)
    paired = []
    for obs in observations:
        rows = by_order.get(str(obs.get("order_id")), [])
        if not rows:
            continue
        qty = sum(float(r.get("qty") or 0.0) for r in rows)
        if not qty:
            continue
        # Volume-weighted: one exit order arrives as several partial fills.
        price = sum(float(r.get("price") or 0.0) * float(r.get("qty") or 0.0)
                    for r in rows) / qty
        paired.append(dict(obs, fill_price=round(price, 6),
                           filled_quantity=qty,
                           slippage=slippage(obs["trigger_price"], price)))
    return paired


def distribution(paired):
    values = sorted(o["slippage"] for o in paired if o["slippage"] is not None)
    if not values:
        return {"n": 0}
    def pct(p):
        if len(values) == 1:
            return values[0]
        i = min(len(values) - 1, max(0, int(round(p * (len(values) - 1)))))
        return values[i]
    return {
        "n": len(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "p10": pct(0.10), "p25": pct(0.25), "p75": pct(0.75), "p90": pct(0.90),
        "min": values[0], "max": values[-1],
    }


def main():
    rows = []
    if AUDIT.exists():
        for line in AUDIT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    observed = triggers(rows)
    print("eligible rule exits with a trigger price: {0}".format(len(observed)))
    print("frozen bound: {0:.3%} (unchanged, and not adjusted by this script)"
          .format(FROZEN_HAIRCUT))

    fills = []
    if "--broker" in sys.argv:
        from event_aware_trader.broker import (AlpacaPaperBroker, BrokerConfig,
                                               BrokerError)
        try:
            fills = AlpacaPaperBroker(
                BrokerConfig.from_environment()).fill_activities(page_size=500)
        except BrokerError as error:
            print("broker unreachable: {0}".format(error))
            return 2

    paired = match_fills(observed, fills)
    print("paired with a fill: {0}".format(len(paired)))
    if paired:
        OUT.write_text("".join(json.dumps(o, sort_keys=True) + "\n"
                               for o in paired), encoding="utf-8")
        print("wrote {0}".format(OUT.relative_to(REPO)))

    if len(paired) < MINIMUM_SAMPLE:
        print("SAMPLE TOO SMALL: {0} of ~{1} eligible exits. The observed "
              "distribution is not reported at this size and the frozen "
              "bound stands.".format(len(paired), MINIMUM_SAMPLE))
        return 0

    d = distribution(paired)
    print("observed trigger-to-fill slippage, n={0}".format(d["n"]))
    for key in ("min", "p10", "p25", "median", "mean", "p75", "p90", "max"):
        print("  {0:>6}: {1:+.4%}".format(key, d[key]))
    print("frozen bound {0:+.4%}; observed median {1:+.4%}; difference "
          "{2:+.4%}".format(FROZEN_HAIRCUT, d["median"],
                            d["median"] - FROZEN_HAIRCUT))
    print("This measurement is SEPARATE from the historical backtest. It "
          "does not restate any historical result and does not replace the "
          "frozen bound, which would be a reviewed methodological change.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
