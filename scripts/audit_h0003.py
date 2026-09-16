"""Forensic audit of H-0003. Re-runs two ALREADY-RUN configurations only.

No new configuration is evaluated. The baseline and the 1.0R lock are
re-run purely to capture trade-level detail that the metrics file did not
retain, so the +13.7 points can be attributed rather than asserted.

The question this answers: is the improvement broad, or is it a handful
of unusual observations?
"""

import glob
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.data import load_bars                  # noqa: E402
from event_aware_trader.mean_reversion import conviction as shipped_conviction  # noqa: E402
from event_aware_trader.phase5.metrics import measure          # noqa: E402
from event_aware_trader.research import production_report      # noqa: E402
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto  # noqa: E402

SCRATCH = Path(glob.glob(
    "C:/Users/yajga/AppData/Local/Temp/claude/**/scratchpad/deep",
    recursive=True)[0]).parent
WINDOW = 400
_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-WINDOW:], c)
_conv = {}


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def load(folder="deep", since=None, minimum=500):
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        path = SCRATCH / folder / (symbol + ".csv")
        if not path.exists():
            continue
        try:
            bars = load_bars(path)
        except Exception:
            continue
        if since:
            bars = [b for b in bars if b.timestamp.date() >= since]
        if len(bars) >= minimum:
            out[symbol] = bars
    return out


def key(trade):
    return (trade.symbol, trade.entry_time.date())


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "deep"
    folder, since, minimum = (
        ("deep", None, 500) if which == "deep"
        else ("long", date(1996, 1, 1), 400))
    dataset = "decade" if which == "deep" else "thirty_year"
    series = load(folder, since, minimum)
    print("{0}: {1} symbols".format(which, len(series)), flush=True)

    base_report = production_report(series, conviction=conviction,
                                    dataset=dataset, purpose="diagnostic")
    lock_report = production_report(series, conviction=conviction,
                                    dataset=dataset, purpose="diagnostic",
                                    mr_lock_at_r=1.0)
    base_m = measure(base_report, "baseline")
    lock_m = measure(lock_report, "lock 1.0R")

    base = {key(t): t for t in base_report.trades}
    lock = {key(t): t for t in lock_report.trades}
    shared = sorted(set(base) & set(lock))
    only_base = sorted(set(base) - set(lock))
    only_lock = sorted(set(lock) - set(base))

    print("\nTRADE POPULATIONS")
    print("  baseline trades            {0}".format(len(base)))
    print("  lock trades                {0}".format(len(lock)))
    print("  same symbol and entry day  {0}".format(len(shared)))
    print("  only in baseline           {0}".format(len(only_base)))
    print("  only in lock               {0}".format(len(only_lock)))
    print("  -> the trade COUNT barely moves, but the POPULATION does")

    # --- how many shared trades actually changed at all ------------------
    changed = [k for k in shared
               if abs(base[k].net_pnl - lock[k].net_pnl) > 1e-6]
    identical = len(shared) - len(changed)
    print("\nOF THE SHARED TRADES")
    print("  identical outcome          {0}".format(identical))
    print("  outcome changed            {0}".format(len(changed)))

    buckets = defaultdict(lambda: {"n": 0, "delta": 0.0})

    def put(name, delta):
        buckets[name]["n"] += 1
        buckets[name]["delta"] += delta

    for k in changed:
        b, l = base[k], lock[k]
        delta = l.net_pnl - b.net_pnl
        if b.net_pnl <= 0 and l.net_pnl > 0:
            put("loser turned into a winner", delta)
        elif b.net_pnl <= 0 and l.net_pnl <= 0 and delta > 0:
            put("loss reduced", delta)
        elif b.net_pnl <= 0 and delta < 0:
            put("loss deepened", delta)
        elif b.net_pnl > 0 and l.net_pnl <= 0:
            put("winner turned into a loser", delta)
        elif b.net_pnl > 0 and delta < 0:
            put("winner cut short", delta)
        else:
            put("winner improved", delta)

    for k in only_base:
        put("trade removed (baseline only)", -base[k].net_pnl)
    for k in only_lock:
        put("trade added (lock only)", lock[k].net_pnl)

    print("\nATTRIBUTION OF THE P&L DIFFERENCE")
    print("  {0:<34} {1:>6} {2:>14}".format("bucket", "n", "P&L delta"))
    total = 0.0
    for name, agg in sorted(buckets.items(), key=lambda kv: -abs(kv[1]["delta"])):
        total += agg["delta"]
        print("  {0:<34} {1:>6} {2:>14,.0f}".format(name, agg["n"], agg["delta"]))
    print("  {0:<34} {1:>6} {2:>14,.0f}".format("TOTAL", "", total))
    print("  realised P&L: baseline {0:,.0f} -> lock {1:,.0f}".format(
        sum(t.net_pnl for t in base_report.trades),
        sum(t.net_pnl for t in lock_report.trades)))

    # --- concentration ----------------------------------------------------
    deltas = sorted(((lock[k].net_pnl - base[k].net_pnl), k) for k in changed)
    top = deltas[-10:][::-1]
    bottom = deltas[:5]
    gross_positive = sum(d for d, _ in deltas if d > 0)
    print("\nCONCENTRATION AMONG CHANGED SHARED TRADES")
    print("  gross positive delta       {0:,.0f}".format(gross_positive))
    print("  top 10 contributors        {0:,.0f}  ({1:.0%} of gross positive)"
          .format(sum(d for d, _ in top),
                  sum(d for d, _ in top) / gross_positive
                  if gross_positive else 0))
    for d, k in top[:5]:
        print("     {0:<6} {1}  {2:+,.0f}".format(k[0], k[1], d))
    print("  worst 5 contributors:")
    for d, k in bottom:
        print("     {0:<6} {1}  {2:+,.0f}".format(k[0], k[1], d))

    # --- exit reasons and holding -----------------------------------------
    def reasons(trades):
        out = defaultdict(int)
        for t in trades:
            out[t.exit_reason] += 1
        return dict(out)

    print("\nEXIT REASONS")
    print("  baseline {0}".format(reasons(base_report.trades)))
    print("  lock     {0}".format(reasons(lock_report.trades)))
    print("  mean hold: baseline {0:.2f} -> lock {1:.2f} days".format(
        base_m.average_hold_days, lock_m.average_hold_days))
    print("  exposure : baseline {0:.1%} -> lock {1:.1%}".format(
        base_m.exposure or 0, lock_m.exposure or 0))
    print("  turnover : baseline {0:.2f} -> lock {1:.2f}".format(
        base_m.turnover or 0, lock_m.turnover or 0))
    print("  costs    : baseline {0:,.0f} -> lock {1:,.0f}".format(
        base_m.transaction_costs or 0, lock_m.transaction_costs or 0))

    # --- per year ----------------------------------------------------------
    print("\nPER YEAR")
    years = sorted(set(base_m.by_year) | set(lock_m.by_year))
    print("  {0:<6} {1:>10} {2:>10} {3:>10} {4:>9} {5:>9}".format(
        "year", "baseline", "lock", "delta", "n base", "n lock"))
    nb = defaultdict(int)
    nl = defaultdict(int)
    for t in base_report.trades:
        nb[t.entry_time.year] += 1
    for t in lock_report.trades:
        nl[t.entry_time.year] += 1
    diffs = {}
    for y in years:
        d = lock_m.by_year.get(y, 0) - base_m.by_year.get(y, 0)
        diffs[y] = d
        print("  {0:<6} {1:>9.2%} {2:>10.2%} {3:>+10.2%} {4:>9} {5:>9}".format(
            y, base_m.by_year.get(y, 0), lock_m.by_year.get(y, 0), d,
            nb.get(y, 0), nl.get(y, 0)))
    positive = sum(1 for d in diffs.values() if d > 0)
    best = max(diffs, key=lambda y: diffs[y])
    worst = min(diffs, key=lambda y: diffs[y])
    print("  years better {0} of {1} | best {2} {3:+.2%} | worst {4} {5:+.2%}"
          .format(positive, len(years), best, diffs[best], worst, diffs[worst]))
    print("  sum of yearly deltas {0:+.2%}, excluding best {1:+.2%}, "
          "excluding worst {2:+.2%}".format(
              sum(diffs.values()), sum(diffs.values()) - diffs[best],
              sum(diffs.values()) - diffs[worst]))

    out = REPO / "data" / "phase5" / "h0003-attribution-{0}.json".format(which)
    out.write_text(json.dumps({
        "populations": {"baseline": len(base), "lock": len(lock),
                        "shared": len(shared), "only_base": len(only_base),
                        "only_lock": len(only_lock),
                        "identical": identical, "changed": len(changed)},
        "attribution": {k: v for k, v in buckets.items()},
        "per_year": diffs,
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
