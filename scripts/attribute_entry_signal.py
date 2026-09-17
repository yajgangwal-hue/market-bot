"""Read-only attribution. Where does the selection/timing drag come from?

NOT AN OPTIMISATION. No parameter is varied, no configuration is swept,
nothing is selected. The baseline is re-run once - an already-recorded
configuration - purely to recover trade-level quantities the summary
metrics did not retain.

THE DECOMPOSITION. For every closed trade, over its OWN entry-to-exit
calendar window:

    realised dollars = market + selection + timing

  market     the notional held in SPY for the identical dates
  selection  the same notional in the CHOSEN SYMBOL, minus market
             - did the strategy pick names that beat the index?
  timing     the realised result, minus buy-and-hold in that symbol
             - did the strategy capture the move it identified?
             - absorbs entry timing, exit timing, costs and the haircut

A NOTE ON FORWARD RETURNS. This measures what already happened. The
forward windows used here are MEASUREMENT, not features: nothing
computed in this file may ever be fed to a decision. It is labelled so
that a later reader cannot mistake one for the other.
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

#: The rule's own holding cap, used as the matched window for candidates
#: the strategy never took. A proxy, and labelled as one.
HOLDING_CAP = 20


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


def by_date(bars):
    return {b.timestamp.date(): b.close for b in bars}


def forward(closes, dates, day, sessions):
    """Return over `sessions` trading days from `day`, or None."""
    try:
        i = dates.index(day)
    except ValueError:
        return None
    j = min(i + sessions, len(dates) - 1)
    if j <= i or not closes[dates[i]]:
        return None
    return closes[dates[j]] / closes[dates[i]] - 1.0


def main():
    series = load()
    spy = by_date(series["SPY"])
    print("decade: {0} symbols".format(len(series)), flush=True)

    report = production_report(series, conviction=conviction,
                               dataset="decade", purpose="diagnostic")
    scored = measure(report, "baseline")
    print("baseline: {0} trades, total {1:+.4%}, exposure {2:.1%}".format(
        scored.trades, scored.total_return, scored.exposure))

    closes = {s: by_date(b) for s, b in series.items()}
    dates = {s: sorted(c) for s, c in closes.items()}

    rows = []
    skipped = 0
    for t in report.trades:
        d0, d1 = t.entry_time.date(), t.exit_time.date()
        c = closes.get(t.symbol, {})
        if d0 not in c or d1 not in c or d0 not in spy or d1 not in spy:
            skipped += 1
            continue
        notional = abs(t.quantity) * t.entry_price
        r_sym = c[d1] / c[d0] - 1.0
        r_spy = spy[d1] / spy[d0] - 1.0
        rows.append({
            "symbol": t.symbol, "entry": d0.isoformat(), "exit": d1.isoformat(),
            "sessions": t.bars_held, "notional": notional,
            "net_pnl": t.net_pnl, "exit_reason": t.exit_reason,
            "r_symbol": r_sym, "r_spy": r_spy,
            "market_dollars": notional * r_spy,
            "selection_dollars": notional * (r_sym - r_spy),
            "timing_dollars": t.net_pnl - notional * r_sym,
        })

    total_pnl = sum(r["net_pnl"] for r in rows)
    market = sum(r["market_dollars"] for r in rows)
    selection = sum(r["selection_dollars"] for r in rows)
    timing = sum(r["timing_dollars"] for r in rows)
    notional = sum(r["notional"] for r in rows)
    days_held = sum(r["sessions"] for r in rows)

    print("\nDOLLAR ATTRIBUTION over {0} trades ({1} skipped for missing bars)"
          .format(len(rows), skipped))
    print("  total notional deployed        {0:>14,.0f}".format(notional))
    print("  position-days held             {0:>14,}".format(days_held))
    print()
    print("  {0:<40} {1:>14} {2:>9}".format("component", "dollars", "share"))
    for name, value in (("market: SPY over the same windows", market),
                        ("selection: chosen names minus SPY", selection),
                        ("timing+costs: realised minus buy-hold", timing)):
        print("  {0:<40} {1:>14,.0f} {2:>9}".format(
            name, value,
            "-" if total_pnl == 0 else "{0:+.0%}".format(value / abs(total_pnl))))
    print("  {0:<40} {1:>14,.0f}".format("REALISED P&L (sum)", market + selection + timing))
    print("  {0:<40} {1:>14,.0f}".format("realised P&L (reported)", total_pnl))
    print("  reconciliation gap {0:,.4f}".format(
        abs(total_pnl - (market + selection + timing))))

    print("\n  as a return on the capital actually deployed:")
    for name, value in (("market", market), ("selection", selection),
                        ("timing+costs", timing)):
        print("    {0:<14} {1:>8.3%}".format(name, value / notional))

    # --- per trade, equal weighted ----------------------------------------
    print("\nPER-TRADE, EQUAL WEIGHTED")
    print("  {0:<34} {1:>9} {2:>9}".format("", "mean", "median"))
    for name, vals in (
            ("symbol buy-hold over window", [r["r_symbol"] for r in rows]),
            ("SPY over the same window", [r["r_spy"] for r in rows]),
            ("symbol minus SPY (selection)",
             [r["r_symbol"] - r["r_spy"] for r in rows])):
        print("  {0:<34} {1:>9.3%} {2:>9.3%}".format(
            name, fmean(vals), median(vals)))
    beat = sum(1 for r in rows if r["r_symbol"] > r["r_spy"])
    print("  chosen name beat SPY in {0} of {1} windows ({2:.1%})".format(
        beat, len(rows), beat / len(rows)))

    print("\n  selection by exit reason (did the picks work regardless of exit?)")
    groups = defaultdict(list)
    for r in rows:
        groups[r["exit_reason"]].append(r)
    print("  {0:<12} {1:>6} {2:>12} {3:>12} {4:>12}".format(
        "reason", "n", "sel $", "timing $", "sel per trade"))
    for reason in sorted(groups):
        g = groups[reason]
        print("  {0:<12} {1:>6} {2:>12,.0f} {3:>12,.0f} {4:>12.3%}".format(
            reason, len(g), sum(x["selection_dollars"] for x in g),
            sum(x["timing_dollars"] for x in g),
            fmean([x["r_symbol"] - x["r_spy"] for x in g])))

    # --- opportunity cost of refused candidates ---------------------------
    print("\nREFUSED CANDIDATES (20-session forward proxy, MEASUREMENT ONLY)")
    cand_path = REPO / "data" / "phase5" / "candidates-deep.jsonl"
    taken = {(r["symbol"], r["entry"]) for r in rows}
    cands = [json.loads(l) for l in
             cand_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    from datetime import date as _date
    took, left = [], []
    for c in cands:
        sym, day = c["symbol"], _date.fromisoformat(c["date"])
        if sym not in closes:
            continue
        fwd = forward(closes[sym], dates[sym], day, HOLDING_CAP)
        ref = forward(spy, sorted(spy), day, HOLDING_CAP)
        if fwd is None or ref is None:
            continue
        (took if (sym, c["date"]) in taken else left).append((fwd, fwd - ref))
    print("  candidates with a usable forward window: {0}".format(
        len(took) + len(left)))
    print("  {0:<26} {1:>7} {2:>12} {3:>12} {4:>9}".format(
        "", "n", "mean fwd", "mean vs SPY", "beat SPY"))
    for name, group in (("TAKEN by the strategy", took),
                        ("REFUSED (not traded)", left)):
        if not group:
            continue
        print("  {0:<26} {1:>7} {2:>12.3%} {3:>12.3%} {4:>9.1%}".format(
            name, len(group), fmean([a for a, _ in group]),
            fmean([b for _, b in group]),
            sum(1 for _, b in group if b > 0) / len(group)))

    out = REPO / "data" / "phase5" / "entry-attribution.json"
    out.write_text(json.dumps({
        "trades": len(rows), "skipped": skipped,
        "notional": notional, "position_days": days_held,
        "market_dollars": market, "selection_dollars": selection,
        "timing_dollars": timing, "realised_pnl": total_pnl,
        "selection_win_rate": beat / len(rows),
        "taken_forward": {"n": len(took),
                          "mean_vs_spy": fmean([b for _, b in took]) if took else None},
        "refused_forward": {"n": len(left),
                            "mean_vs_spy": fmean([b for _, b in left]) if left else None},
        "note": "measurement of what happened; never to be used as a feature",
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
