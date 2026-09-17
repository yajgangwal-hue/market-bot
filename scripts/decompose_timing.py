"""Read-only. Where inside the timing drag does the money actually go?

NOT AN OPTIMISATION. Nothing is varied, swept or selected. The frozen
baseline is re-run once to recover trade-level quantities the summary
metrics do not retain.

THE IDENTITY. `entry_price` and `exit_price` on a ClosedTrade are the
COST-ADJUSTED fills, so the spread and slippage are already inside them
and net_pnl = q*(exit_fill - entry_fill). With c0 the close on the entry
date and c1 the close on the exit date:

    realised          = q*(exit_fill - entry_fill)
    same shares held
    close to close    = q*(c1 - c0)

    difference        = q*(c0 - entry_fill)     ENTRY GAP
                      + q*(exit_fill - c1)      EXIT GAP

Exact, not a regression. Each gap carries its own half of the trading
cost plus the real question: how far from that day's close the strategy
actually transacted. Split by exit reason, because a stop, a rule exit
and a holding cap are three different mechanisms and they are not
equally changeable.

EXCURSIONS. `highest_high` and `lowest_low` are recorded while the
position is open, so how far a trade ran in favour before it closed is
measurable directly. Quoted as percentages of the entry fill, which
needs no planned-risk denominator and cannot be distorted by one.

A NOTE ON UNITS. The entry attribution scaled by notional = q*entry_fill
against a close-to-close return, so its "timing" differs from the
identity above by the factor entry_fill/c0, a few basis points. The
reconciliation is printed rather than assumed.
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

#: What the cost model charges, one way. Used only to say how much of a
#: gap is unavoidable friction and how much is where the fill landed.
ONE_WAY_BPS = 6.0


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


def money(x):
    return "{0:>13,.0f}".format(x)


def main():
    series = load()
    print("decade: {0} symbols".format(len(series)), flush=True)
    report = production_report(series, conviction=conviction,
                               dataset="decade", purpose="diagnostic")
    scored = measure(report, "baseline")
    print("baseline: {0} trades, total {1:+.4%}\n".format(
        scored.trades, scored.total_return))

    bars_by = {s: {b.timestamp.date(): b for b in bs} for s, bs in series.items()}
    rows, skipped = [], 0
    for t in report.trades:
        d0, d1 = t.entry_time.date(), t.exit_time.date()
        book = bars_by.get(t.symbol, {})
        if d0 not in book or d1 not in book:
            skipped += 1
            continue
        c0, c1, q = book[d0].close, book[d1].close, t.quantity
        rows.append({
            "symbol": t.symbol, "reason": t.exit_reason, "held": t.bars_held,
            "qty": q, "notional": abs(q) * t.entry_price, "net_pnl": t.net_pnl,
            "entry_gap": q * (c0 - t.entry_price),
            "exit_gap": q * (t.exit_price - c1),
            "buyhold": q * (c1 - c0),
            "entry_off_close": (t.entry_price / c0 - 1.0) if c0 else 0.0,
            "exit_off_close": (t.exit_price / c1 - 1.0) if c1 else 0.0,
            "realised_pct": t.exit_price / t.entry_price - 1.0,
            "mfe_pct": (t.highest_high / t.entry_price - 1.0
                        if t.highest_high else None),
            "mae_pct": (t.lowest_low / t.entry_price - 1.0
                        if t.lowest_low else None),
            "r": t.r_multiple,
        })

    tot = lambda k: sum(r[k] for r in rows)                     # noqa: E731
    realised, buyhold = tot("net_pnl"), tot("buyhold")
    entry_gap, exit_gap, notional = tot("entry_gap"), tot("exit_gap"), tot("notional")
    friction = notional * ONE_WAY_BPS / 10000.0

    print("THE IDENTITY, over {0} trades ({1} skipped for missing bars)".format(
        len(rows), skipped))
    print("  {0:<46}{1}".format("same shares, held close to close", money(buyhold)))
    print("  {0:<46}{1}".format("+ entry gap   q*(c0 - entry_fill)",
                                money(entry_gap)))
    print("  {0:<46}{1}".format("+ exit gap    q*(exit_fill - c1)", money(exit_gap)))
    print("  {0:<46}{1}".format("= REALISED (sum)", money(buyhold + entry_gap + exit_gap)))
    print("  {0:<46}{1}".format("  realised (reported)", money(realised)))
    print("  reconciliation gap {0:,.6f}".format(
        abs(realised - (buyhold + entry_gap + exit_gap))))
    print("\n  of which unavoidable friction at {0:.0f} bps one way:".format(
        ONE_WAY_BPS))
    print("    {0:<44}{1}".format("entry side", money(-friction)))
    print("    {0:<44}{1}".format("exit side (approx, on entry notional)",
                                  money(-friction)))
    print("    {0:<44}{1}".format("the rest of the two gaps",
                                  money(entry_gap + exit_gap + 2 * friction)))
    print("\n  as a return on the {0:,.0f} of notional deployed:".format(notional))
    for name, v in (("held close to close", buyhold), ("entry gap", entry_gap),
                    ("exit gap", exit_gap)):
        print("    {0:<24} {1:>9.4%}".format(name, v / notional))

    # ---- by exit reason -------------------------------------------------
    groups = defaultdict(list)
    for r in rows:
        groups[r["reason"]].append(r)
    order = sorted(groups, key=lambda k: -len(groups[k]))

    print("\nBY EXIT REASON")
    print("  {0:<12} {1:>5} {2:>13} {3:>13} {4:>13} {5:>13}".format(
        "reason", "n", "buy-hold $", "entry gap", "exit gap", "realised $"))
    for reason in order:
        g = groups[reason]
        print("  {0:<12} {1:>5} {2} {3} {4} {5}".format(
            reason, len(g), money(sum(x["buyhold"] for x in g)),
            money(sum(x["entry_gap"] for x in g)),
            money(sum(x["exit_gap"] for x in g)),
            money(sum(x["net_pnl"] for x in g))))

    print("\n  where the fill landed relative to that day's close:")
    print("  {0:<12} {1:>5} {2:>13} {3:>13} {4:>13}".format(
        "reason", "n", "mean exit", "median exit", "worst exit"))
    for reason in order:
        g = groups[reason]
        v = [x["exit_off_close"] for x in g]
        print("  {0:<12} {1:>5} {2:>13.4%} {3:>13.4%} {4:>13.4%}".format(
            reason, len(g), fmean(v), median(v), min(v)))

    # ---- what was on the table ------------------------------------------
    print("\nWHAT WAS ON THE TABLE - excursions as % of the entry fill")
    print("  {0:<12} {1:>5} {2:>10} {3:>10} {4:>10} {5:>12}".format(
        "reason", "n", "mean MFE", "mean MAE", "mean out", "MFE captured"))
    usable = [r for r in rows if r["mfe_pct"] is not None]
    for reason in order:
        g = [x for x in groups[reason] if x["mfe_pct"] is not None]
        if not g:
            continue
        mfe = fmean([x["mfe_pct"] for x in g])
        got = fmean([x["realised_pct"] for x in g])
        print("  {0:<12} {1:>5} {2:>10.3%} {3:>10.3%} {4:>10.3%} {5:>12}".format(
            reason, len(g), mfe, fmean([x["mae_pct"] for x in g]), got,
            "{0:.1%}".format(got / mfe) if mfe else "-"))
    mfe_all = fmean([r["mfe_pct"] for r in usable])
    got_all = fmean([r["realised_pct"] for r in usable])
    print("  {0:<12} {1:>5} {2:>10.3%} {3:>10.3%} {4:>10.3%} {5:>12.1%}".format(
        "ALL", len(usable), mfe_all, fmean([r["mae_pct"] for r in usable]),
        got_all, got_all / mfe_all))

    print("\n  trades that were up and finished down:")
    for threshold in (0.02, 0.03, 0.05):
        gave = [r for r in usable if r["mfe_pct"] > threshold
                and r["realised_pct"] < 0]
        print("    ran +{0:.0%} in favour yet closed NEGATIVE: {1:>3} of {2} "
              "({3:>5.1%}), {4:>12,.0f}".format(
                  threshold, len(gave), len(usable), len(gave) / len(usable),
                  sum(r["net_pnl"] for r in gave)))
    never = [r for r in usable if r["mfe_pct"] <= 0.005]
    print("    never ran even +0.5% in favour:            {0:>3} ({1:.1%}), "
          "{2:>12,.0f}".format(len(never), len(never) / len(usable),
                               sum(r["net_pnl"] for r in never)))

    out = REPO / "docs" / "phase5" / "timing-decomposition.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "trades": len(rows), "skipped": skipped, "notional": notional,
        "buyhold_dollars": buyhold, "entry_gap": entry_gap,
        "exit_gap": exit_gap, "realised": realised,
        "friction_one_way_bps": ONE_WAY_BPS,
        "modelled_friction_both_ways": 2 * friction,
        "mean_mfe_pct": mfe_all, "mean_realised_pct": got_all,
        "mfe_capture": got_all / mfe_all,
        "by_reason": {k: {
            "n": len(g), "buyhold": sum(x["buyhold"] for x in g),
            "entry_gap": sum(x["entry_gap"] for x in g),
            "exit_gap": sum(x["exit_gap"] for x in g),
            "realised": sum(x["net_pnl"] for x in g),
            "mean_exit_off_close": fmean([x["exit_off_close"] for x in g]),
            "mean_mfe_pct": fmean([x["mfe_pct"] for x in g
                                   if x["mfe_pct"] is not None] or [0]),
            "mean_realised_pct": fmean([x["realised_pct"] for x in g]),
        } for k, g in groups.items()},
        "note": "read-only measurement; nothing here may become a feature",
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
