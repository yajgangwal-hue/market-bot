"""Read-only. Is the 20-bar cap a binding deadline or a mercy killing?

NOT AN OPTIMISATION and NOT A REGISTRATION. One question, asked before
spending a pre-registration slot on it:

  when the clock forces an exit, was the trade still going somewhere?

The decomposition says `time_exit` closes 238 trades that ran +4.86% in
favour at their best and hand back all but +0.68%. Two stories fit that
equally well. Either the reversion was underway and the deadline cut it
short - in which case a longer cap converts `time_exit` trades into
`reverted` trades, where capture is 84% - or the move already happened
and faded, and the deadline is closing a position that is going nowhere,
in which case a longer cap just holds a fading trade into its stop.

The distinguishing measurement is what the price did AFTER the forced
exit. It is hindsight by construction: it measures what happened, it can
never become a feature, and a positive reading is a reason to REGISTER a
hypothesis, never a result in itself.

The honest comparator is the same forward window on SPY, because holding
longer also means holding market exposure longer, and H-0007 just showed
how easily a beta effect reads as a selection effect.
"""

import glob
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import fmean, median

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

HORIZONS = (5, 10, 20, 40)
RSI_EXIT = 60.0


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def load():
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        path = SCRATCH / "deep" / (symbol + ".csv")
        if path.exists():
            try:
                bars = load_bars(path)
            except Exception:
                continue
            if len(bars) >= 500:
                out[symbol] = bars
    return out


def rsi(closes, period=14):
    if len(closes) <= period:
        return None
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    ag, al = gains / period, losses / period
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        ag = (ag * (period - 1) + max(d, 0.0)) / period
        al = (al * (period - 1) + max(-d, 0.0)) / period
    if al == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + ag / al)


def main():
    series = load()
    print("decade: {0} symbols".format(len(series)), flush=True)
    report = production_report(series, conviction=conviction,
                               dataset="decade", purpose="diagnostic")
    print("baseline: {0} trades\n".format(
        measure(report, "baseline").trades), flush=True)

    dates = {s: [b.timestamp.date() for b in bs] for s, bs in series.items()}
    closes = {s: [b.close for b in bs] for s, bs in series.items()}
    lows = {s: [b.low for b in bs] for s, bs in series.items()}
    spy_d, spy_c = dates["SPY"], closes["SPY"]
    spy_at = {d: i for i, d in enumerate(spy_d)}

    groups = defaultdict(list)
    for t in report.trades:
        groups[t.exit_reason].append(t)
    print("exit reasons: {0}\n".format(
        {k: len(v) for k, v in sorted(groups.items())}))

    for reason in ("time_exit", "reverted", "stop"):
        trades = groups.get(reason, [])
        if not trades:
            continue
        print("AFTER A '{0}' EXIT - what the name did next".format(reason))
        print("  {0:>4} {1:>5} {2:>11} {3:>11} {4:>11} {5:>9} {6:>9}".format(
            "days", "n", "mean fwd", "median fwd", "mean vs SPY", "up", "beat"))
        for h in HORIZONS:
            rows = []
            for t in trades:
                s = t.symbol
                try:
                    i = dates[s].index(t.exit_time.date())
                except ValueError:
                    continue
                j = i + h
                if j >= len(closes[s]):
                    continue
                si = spy_at.get(t.exit_time.date())
                if si is None or si + h >= len(spy_c):
                    continue
                fwd = closes[s][j] / closes[s][i] - 1.0
                ref = spy_c[si + h] / spy_c[si] - 1.0
                rows.append((fwd, fwd - ref))
            if not rows:
                continue
            print("  {0:>4} {1:>5} {2:>11.3%} {3:>11.3%} {4:>11.3%} "
                  "{5:>9.1%} {6:>9.1%}".format(
                      h, len(rows), fmean([a for a, _ in rows]),
                      median([a for a, _ in rows]),
                      fmean([b for _, b in rows]),
                      sum(1 for a, _ in rows if a > 0) / len(rows),
                      sum(1 for _, b in rows if b > 0) / len(rows)))
        print()

    # ---- the specific question: would the cap have resolved? ------------
    print("IF THE CAP WERE LONGER, WHAT WOULD THE 238 time_exit TRADES DO?")
    print("  Counting, for each extra allowance, whether RSI(14) reaches 60")
    print("  (the rule's own exit) before the position's stop is touched.")
    print("  {0:>6} {1:>5} {2:>9} {3:>9} {4:>9} {5:>13}".format(
        "extra", "n", "reverted", "stopped", "neither", "mean outcome"))
    trades = groups.get("time_exit", [])
    for extra in (10, 20, 40):
        reverted = stopped = neither = 0
        outcomes = []
        for t in trades:
            s = t.symbol
            try:
                i = dates[s].index(t.exit_time.date())
            except ValueError:
                continue
            if i + extra >= len(closes[s]):
                continue
            stop = t.exit_stop or t.initial_stop
            hit = None
            for k in range(1, extra + 1):
                if stop and lows[s][i + k] <= stop:
                    hit = ("stop", stop / t.exit_price - 1.0)
                    break
                r = rsi(closes[s][max(0, i + k - 60):i + k + 1])
                if r is not None and r >= RSI_EXIT:
                    hit = ("reverted", closes[s][i + k] / t.exit_price - 1.0)
                    break
            if hit is None:
                hit = ("neither",
                       closes[s][i + extra] / t.exit_price - 1.0)
            if hit[0] == "reverted":
                reverted += 1
            elif hit[0] == "stop":
                stopped += 1
            else:
                neither += 1
            outcomes.append(hit[1])
        n = len(outcomes)
        if not n:
            continue
        print("  {0:>6} {1:>5} {2:>9.1%} {3:>9.1%} {4:>9.1%} {5:>13.3%}".format(
            "+{0}".format(extra), n, reverted / n, stopped / n, neither / n,
            fmean(outcomes)))

    print("\n  'mean outcome' is the return from the forced exit price to")
    print("  whichever event came first. Positive means the extra time paid,")
    print("  BEFORE the extra capital lock-up and the trades not taken")
    print("  because the capital was still in this one. Neither is priced")
    print("  here, and both are real. This is a direction, not a result.")

    out = REPO / "docs" / "phase5" / "holding-cap-probe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "note": "read-only hindsight measurement; never a feature",
        "exit_reason_counts": {k: len(v) for k, v in groups.items()},
    }, indent=1, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
