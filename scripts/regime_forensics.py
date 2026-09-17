"""Read-only regime forensics. Does the market environment change anything?

NOT AN OPTIMISATION. No parameter is varied, no configuration swept,
nothing selected, nothing registered. The baseline is re-run once - an
already-recorded configuration - to recover trade-level quantities and
join them to point-in-time regime labels.

THE TRAP THIS FILE IS BUILT TO AVOID. "Regime" defined by looking at
what happened next is not a regime, it is the answer written on the
question paper. Every label here comes from prices at or before the
session it labels, and two specific guards are worth naming:

  EXPANDING THRESHOLDS. Calling volatility "high" because it sits in the
  top third of the WHOLE SAMPLE uses 2026 to label 2016. Every threshold
  here is an expanding percentile: the rank of today's reading among
  readings up to today, and nothing later.

  LAGGED APPLICATION. A session's return is attributed to the regime
  label formed at the PREVIOUS close. Labelling a day with its own close
  and then measuring that day's return is circular.

The discriminator that matters most is reported everywhere: SPY's own
return inside each regime, next to the strategy's. If the strategy looks
good in good regimes and SPY looks equally good, the regime signal has
found beta, not edge.
"""

import glob
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import fmean, median, pstdev

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
MIN_HISTORY_FOR_PERCENTILE = 252     # a year before any threshold is trusted


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


def expanding_rank(history, value):
    """Percentile of `value` among everything seen up to now. 0..1."""
    if len(history) < MIN_HISTORY_FOR_PERCENTILE:
        return None
    below = sum(1 for v in history if v <= value)
    return below / len(history)


def regime_labels(spy, tlt, hyg, lqd):
    """Point-in-time labels for every session. Nothing from the future."""
    labels = {}
    closes, vols, ratios = [], [], []
    running_high = None
    tlt_c = {b.timestamp.date(): b.close for b in tlt}
    hyg_c = {b.timestamp.date(): b.close for b in hyg}
    lqd_c = {b.timestamp.date(): b.close for b in lqd}

    for i, bar in enumerate(spy):
        day = bar.timestamp.date()
        closes.append(bar.close)
        running_high = bar.close if running_high is None else max(running_high,
                                                                  bar.close)
        rec = {}
        rec["above_ma200"] = (
            bar.close > sum(closes[-200:]) / 200.0 if len(closes) >= 200 else None)
        rec["above_ma50"] = (
            bar.close > sum(closes[-50:]) / 50.0 if len(closes) >= 50 else None)
        rec["drawdown"] = bar.close / running_high - 1.0 if running_high else None
        if len(closes) >= 21:
            rets = [closes[j] / closes[j - 1] - 1.0
                    for j in range(len(closes) - 20, len(closes))
                    if closes[j - 1]]
            vol = pstdev(rets) if len(rets) > 1 else None
            if vol is not None:
                rec["vol20"] = vol
                rec["vol_rank"] = expanding_rank(vols, vol)
                vols.append(vol)
        rec["mom126"] = (closes[-1] / closes[-127] - 1.0
                         if len(closes) >= 127 and closes[-127] else None)
        # Credit tone: high yield relative to investment grade. Falls when
        # credit is stressed, and it is a PRICE ratio so it is available
        # the moment both close.
        if day in hyg_c and day in lqd_c and lqd_c[day]:
            ratio = hyg_c[day] / lqd_c[day]
            rec["credit_ratio"] = ratio
            ratios.append(ratio)
            if len(ratios) >= 64:
                rec["credit_above_ma63"] = ratio > fmean(ratios[-63:])
        if day in tlt_c and tlt_c[day]:
            rec["spy_over_tlt"] = bar.close / tlt_c[day]
        labels[day] = rec
    return labels


def breadth_by_day(series, sessions):
    """Share of the universe above its own 200-day. SURVIVORSHIP-BIASED.

    The universe is today's constituents, so a name that failed and was
    delisted never drags this down. Reported for completeness and
    flagged everywhere it appears.
    """
    closes = {s: {b.timestamp.date(): b.close for b in bars}
              for s, bars in series.items()}
    ordered = {s: sorted(c) for s, c in closes.items()}
    running = {s: [] for s in series}
    out = {}
    counts = defaultdict(lambda: [0, 0])
    for s, bars in series.items():
        window = []
        for b in bars:
            window.append(b.close)
            if len(window) >= 200:
                above = b.close > sum(window[-200:]) / 200.0
                day = b.timestamp.date()
                counts[day][0] += 1 if above else 0
                counts[day][1] += 1
    for day, (up, total) in counts.items():
        if total >= 50:
            out[day] = up / total
    return out


def classify(rec, breadth):
    """The four simple, economically interpretable structures."""
    out = {}
    out["trend200"] = ("above" if rec.get("above_ma200") else "below") \
        if rec.get("above_ma200") is not None else None
    out["trend50"] = ("above" if rec.get("above_ma50") else "below") \
        if rec.get("above_ma50") is not None else None
    dd = rec.get("drawdown")
    out["drawdown"] = (None if dd is None else
                       "near_high" if dd > -0.05 else
                       "pullback" if dd > -0.10 else "deep")
    vr = rec.get("vol_rank")
    out["vol_rank"] = (None if vr is None else
                       "calm" if vr < 1 / 3 else
                       "normal" if vr < 2 / 3 else "stressed")
    out["credit"] = (None if rec.get("credit_above_ma63") is None else
                     "firm" if rec["credit_above_ma63"] else "soft")
    out["breadth"] = (None if breadth is None else
                      "narrow" if breadth < 0.4 else
                      "mixed" if breadth < 0.6 else "broad")
    return out


def compound(returns):
    v = 1.0
    for r in returns:
        v *= 1.0 + r
    return v - 1.0


def main():
    series = load()
    spy_bars = series["SPY"]
    print("decade: {0} symbols, SPY {1} -> {2}".format(
        len(series), spy_bars[0].timestamp.date(), spy_bars[-1].timestamp.date()),
        flush=True)

    labels = regime_labels(spy_bars, series["TLT"], series["HYG"], series["LQD"])
    breadth = breadth_by_day(series, sorted(labels))
    spy_close = {b.timestamp.date(): b.close for b in spy_bars}
    spy_days = sorted(spy_close)

    report = production_report(series, conviction=conviction,
                               dataset="decade", purpose="diagnostic")
    scored = measure(report, "baseline")
    print("baseline: {0} trades, total {1:+.4%}, CAGR {2:+.4%}, maxDD {3:.4%}"
          .format(scored.trades, scored.total_return, scored.cagr,
                  scored.max_drawdown), flush=True)

    # ---- daily returns bucketed by the PREVIOUS close's label -----------
    equity = {s.date(): v for s, v in report.equity_curve}
    cash = {s.date(): v for s, v in report.cash_curve}
    eq_days = sorted(equity)

    dims = ("trend200", "trend50", "drawdown", "vol_rank", "credit", "breadth")
    strat = {d: defaultdict(list) for d in dims}
    bench = {d: defaultdict(list) for d in dims}
    expo = {d: defaultdict(list) for d in dims}

    for i in range(1, len(eq_days)):
        today, prior = eq_days[i], eq_days[i - 1]
        if equity[prior] <= 0:
            continue
        r_s = equity[today] / equity[prior] - 1.0
        if prior not in spy_close or today not in spy_close:
            continue
        r_b = spy_close[today] / spy_close[prior] - 1.0
        state = classify(labels.get(prior, {}), breadth.get(prior))
        invested = 1.0 - (cash.get(today, 0.0) / equity[today]
                          if equity[today] else 0.0)
        for d in dims:
            if state.get(d):
                strat[d][state[d]].append(r_s)
                bench[d][state[d]].append(r_b)
                expo[d][state[d]].append(max(0.0, min(1.0, invested)))

    print("\n" + "=" * 96)
    print("DAILY RETURNS BY REGIME  (label from the PRIOR close; SPY price only)")
    print("=" * 96)
    for d in dims:
        print("\n  {0}".format(d.upper()))
        print("  {0:<12} {1:>7} {2:>11} {3:>11} {4:>10} {5:>9} {6:>9}".format(
            "state", "days", "strategy", "SPY", "strat-SPY", "ann vol", "exposure"))
        for state in sorted(strat[d]):
            rs, rb = strat[d][state], bench[d][state]
            cs, cb = compound(rs), compound(rb)
            years = len(rs) / 252.0
            print("  {0:<12} {1:>7} {2:>11} {3:>11} {4:>10} {5:>9} {6:>9}".format(
                state, len(rs), "{0:+.2%}".format(cs), "{0:+.2%}".format(cb),
                "{0:+.2%}".format(cs - cb),
                "{0:.1%}".format(pstdev(rs) * (252 ** 0.5)) if len(rs) > 2 else "-",
                "{0:.1%}".format(fmean(expo[d][state])) if expo[d][state] else "-"))
            if years > 0.25:
                print("  {0:<12} {1:>7} {2:>11} {3:>11}".format(
                    "", "ann:", "{0:+.2%}".format((1 + cs) ** (1 / years) - 1),
                    "{0:+.2%}".format((1 + cb) ** (1 / years) - 1)))

    # ---- trade-level attribution by entry regime ------------------------
    print("\n" + "=" * 96)
    print("TRADE ATTRIBUTION BY ENTRY REGIME  (market / selection / timing)")
    print("=" * 96)
    closes = {s: {b.timestamp.date(): b.close for b in bars}
              for s, bars in series.items()}
    rows = []
    for t in report.trades:
        d0, d1 = t.entry_time.date(), t.exit_time.date()
        c = closes.get(t.symbol, {})
        if d0 not in c or d1 not in c or d0 not in spy_close or d1 not in spy_close:
            continue
        notional = abs(t.quantity) * t.entry_price
        r_sym = c[d1] / c[d0] - 1.0
        r_spy = spy_close[d1] / spy_close[d0] - 1.0
        prior = spy_days[max(0, spy_days.index(d0) - 1)]
        rows.append({
            "state": classify(labels.get(prior, {}), breadth.get(prior)),
            "notional": notional, "pnl": t.net_pnl, "held": t.bars_held,
            "reason": t.exit_reason,
            "market": notional * r_spy,
            "selection": notional * (r_sym - r_spy),
            "timing": t.net_pnl - notional * r_sym,
        })

    for d in ("trend200", "drawdown", "vol_rank"):
        print("\n  {0}".format(d.upper()))
        print("  {0:<12} {1:>5} {2:>11} {3:>11} {4:>11} {5:>11} {6:>7} {7:>7} {8:>6}"
              .format("state", "n", "market $", "select $", "timing $", "P&L $",
                      "win%", "stop%", "hold"))
        groups = defaultdict(list)
        for r in rows:
            if r["state"].get(d):
                groups[r["state"][d]].append(r)
        for state in sorted(groups):
            g = groups[state]
            n = len(g)
            print("  {0:<12} {1:>5} {2:>11,.0f} {3:>11,.0f} {4:>11,.0f} "
                  "{5:>11,.0f} {6:>7.1%} {7:>7.1%} {8:>6.1f}".format(
                      state, n, sum(x["market"] for x in g),
                      sum(x["selection"] for x in g),
                      sum(x["timing"] for x in g), sum(x["pnl"] for x in g),
                      sum(1 for x in g if x["pnl"] > 0) / n,
                      sum(1 for x in g if x["reason"] == "stop") / n,
                      fmean([x["held"] for x in g])))
            print("  {0:<12} {1:>5} {2:>11} {3:>11} {4:>11}".format(
                "", "per $:", "{0:+.3%}".format(sum(x["market"] for x in g)
                                                / sum(x["notional"] for x in g)),
                "{0:+.3%}".format(sum(x["selection"] for x in g)
                                  / sum(x["notional"] for x in g)),
                "{0:+.3%}".format(sum(x["timing"] for x in g)
                                  / sum(x["notional"] for x in g))))

    # ---- opportunity set and capacity by regime -------------------------
    print("\n" + "=" * 96)
    print("OPPORTUNITY SET AND CAPACITY BY REGIME (trend200)")
    print("=" * 96)
    cands = [json.loads(l) for l in
             (REPO / "data" / "phase5" / "candidates-deep.jsonl")
             .read_text(encoding="utf-8").splitlines() if l.strip()]
    cand_days = defaultdict(int)
    for c in cands:
        cand_days[date.fromisoformat(c["date"])] += 1
    taken_days = defaultdict(int)
    for t in report.trades:
        taken_days[t.entry_time.date()] += 1

    by_state = defaultdict(lambda: {"sessions": 0, "cands": 0, "taken": 0,
                                    "days_over_3": 0, "days_at_3": 0})
    for day in spy_days:
        prior_i = max(0, spy_days.index(day) - 1)
        state = classify(labels.get(spy_days[prior_i], {}),
                         breadth.get(spy_days[prior_i])).get("trend200")
        if not state:
            continue
        b = by_state[state]
        b["sessions"] += 1
        b["cands"] += cand_days.get(day, 0)
        b["taken"] += taken_days.get(day, 0)
        if cand_days.get(day, 0) > 3:
            b["days_over_3"] += 1
        if taken_days.get(day, 0) >= 3:
            b["days_at_3"] += 1
    print("  {0:<8} {1:>9} {2:>10} {3:>8} {4:>11} {5:>12} {6:>11}".format(
        "state", "sessions", "candidates", "taken", "conversion",
        "days >3 cands", "days at 3"))
    for state in sorted(by_state):
        b = by_state[state]
        print("  {0:<8} {1:>9} {2:>10} {3:>8} {4:>11} {5:>12} {6:>11}".format(
            state, b["sessions"], b["cands"], b["taken"],
            "{0:.1%}".format(b["taken"] / b["cands"]) if b["cands"] else "-",
            b["days_over_3"], b["days_at_3"]))

    out = REPO / "data" / "phase5" / "regime-forensics.json"
    out.write_text(json.dumps({
        "daily_by_regime": {
            d: {s: {"days": len(strat[d][s]),
                    "strategy_cum": compound(strat[d][s]),
                    "spy_cum": compound(bench[d][s]),
                    "mean_exposure": fmean(expo[d][s]) if expo[d][s] else None}
                for s in strat[d]} for d in dims},
        "capacity_by_trend200": dict(by_state),
        "note": "point-in-time labels, lagged one session; SPY price only; "
                "breadth is survivorship-biased",
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
