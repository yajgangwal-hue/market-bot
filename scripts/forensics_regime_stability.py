"""Read-only addendum to the regime forensics. Three questions only.

1. IS IT BETA? The strategy's best states may simply be the states where
   the index ran hardest. Decomposed explicitly, because "more exposure
   at a good moment" is not alpha.
2. IS IT STABLE? The finding that the FAVOURABLE state is the strategy's
   worst is checked on pre-declared chronological thirds of the sessions.
   The split is thirds by session order, declared here before computing.
3. CAN A TRANSITION BE ACTED ON? The first pass measured only direct
   favourable->unfavourable flips and found n=2, because almost every
   transition passes through neutral. Re-measured as ENTRY INTO a state
   from any other state, which is the thing a live loop would react to.

Also quantifies the cash drag by state, which is the mechanism the
hypothesis is really about.
"""

import glob
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import fmean, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.data import load_bars                  # noqa: E402
from event_aware_trader.mean_reversion import conviction as shipped_conviction  # noqa: E402
from event_aware_trader.research import production_report      # noqa: E402
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto  # noqa: E402

sys.path.insert(0, str(REPO / "scripts"))
from forensics_regime import build_signals, load, STATES, TRADING_YEAR  # noqa: E402

_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-400:], c)
_conv = {}


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def main():
    series = load()
    report = production_report(series, conviction=conviction,
                               dataset="decade", purpose="diagnostic")
    labels, days, _diag = build_signals(series)
    spy_close = {b.timestamp.date(): b.close for b in series["SPY"]}
    equity = {t.date(): v for t, v in report.equity_curve}
    cash = {t.date(): v for t, v in report.cash_curve}
    eq_days = sorted(equity)
    port_ret, spy_ret = {}, {}
    for i, d in enumerate(eq_days):
        if i:
            p = equity[eq_days[i - 1]]
            port_ret[d] = equity[d] / p - 1.0 if p else 0.0
    sd = sorted(spy_close)
    for i, d in enumerate(sd):
        if i:
            spy_ret[d] = spy_close[d] / spy_close[sd[i - 1]] - 1.0

    # ---- 1. beta vs alpha -----------------------------------------------
    print("=" * 76)
    print("1. IS THE REGIME EFFECT BETA? strategy vs SPY over the same days")
    print("=" * 76)
    print("  'implied beta' is cov/var of the daily series inside the state.")
    print("  'residual' is the strategy's annualised return minus beta x SPY's.")
    beta_out = {}
    for name in ("trend_dual_ma", "spy_volatility", "risk_spy_tlt"):
        lab = labels[name]
        print("\n  {0}".format(name))
        print("    {0:<14} {1:>6} {2:>10} {3:>10} {4:>8} {5:>11} {6:>10}".format(
            "state", "days", "strategy", "SPY", "beta", "beta x SPY",
            "residual"))
        beta_out[name] = {}
        for st in STATES:
            ds = [d for d in eq_days if lab.get(d) == st and d in port_ret
                  and d in spy_ret]
            if len(ds) < 40:
                continue
            p = [port_ret[d] for d in ds]
            s = [spy_ret[d] for d in ds]
            mp, ms = fmean(p), fmean(s)
            var = sum((x - ms) ** 2 for x in s)
            beta = (sum((a - mp) * (b - ms) for a, b in zip(p, s)) / var
                    if var else 0.0)
            ann_p, ann_s = mp * TRADING_YEAR, ms * TRADING_YEAR
            beta_out[name][st] = {"days": len(ds), "strategy": ann_p,
                                  "spy": ann_s, "beta": beta,
                                  "beta_spy": beta * ann_s,
                                  "residual": ann_p - beta * ann_s}
            print("    {0:<14} {1:>6} {2:>10.2%} {3:>10.2%} {4:>8.3f} "
                  "{5:>11.2%} {6:>10.2%}".format(
                      st, len(ds), ann_p, ann_s, beta, beta * ann_s,
                      ann_p - beta * ann_s))

    # ---- 2. cash drag ----------------------------------------------------
    print("\n" + "=" * 76)
    print("2. CASH DRAG BY STATE - the mechanism the hypothesis is about")
    print("=" * 76)
    print("  foregone = mean cash share x SPY's annualised return in that")
    print("  state. What the idle half of the account did not earn.")
    lab = labels["trend_dual_ma"]
    print("\n  {0:<14} {1:>6} {2:>10} {3:>12} {4:>14}".format(
        "state", "days", "cash %", "SPY ann", "foregone ann"))
    drag = {}
    for st in STATES:
        ds = [d for d in eq_days if lab.get(d) == st]
        if len(ds) < 40:
            continue
        c = fmean([cash[d] / equity[d] for d in ds if equity.get(d)])
        s = fmean([spy_ret[d] for d in ds if d in spy_ret]) * TRADING_YEAR
        drag[st] = {"cash": c, "spy_ann": s, "foregone": c * s}
        print("  {0:<14} {1:>6} {2:>10.1%} {3:>12.2%} {4:>14.2%}".format(
            st, len(ds), c, s, c * s))

    # ---- 3. stability of the headline finding ---------------------------
    print("\n" + "=" * 76)
    print("3. STABILITY - chronological thirds of the sessions, declared")
    print("   before computing. Does 'favourable is the worst state' hold?")
    print("=" * 76)
    third = len(eq_days) // 3
    parts = [("early", eq_days[:third]), ("middle", eq_days[third:2 * third]),
             ("late", eq_days[2 * third:])]
    stability = {}
    for name in ("trend_dual_ma", "spy_volatility", "breadth",
                 "credit_hyg_lqd", "risk_spy_tlt", "spy_drawdown"):
        lb = labels[name]
        stability[name] = {}
        line = []
        for pname, pdays in parts:
            vals = {}
            for st in STATES:
                r = [port_ret[d] for d in pdays
                     if lb.get(d) == st and d in port_ret]
                if len(r) >= 30:
                    vals[st] = fmean(r) * TRADING_YEAR
            if len(vals) < 2:
                line.append("{0}: n/a".format(pname))
                continue
            worst = min(vals, key=vals.get)
            stability[name][pname] = {"values": vals, "worst": worst}
            line.append("{0}: worst={1}".format(pname, worst[:5]))
        print("  {0:<18} {1}".format(name, "  ".join(line)))
    hits = sum(1 for n, v in stability.items()
               for p in v.values() if p["worst"] == "favourable")
    total = sum(len(v) for v in stability.values())
    print("\n  'favourable' was the worst state in {0} of {1} "
          "signal-x-period cells ({2:.0%})".format(hits, total, hits / total))

    print("\n  detail for the primary signal:")
    print("  {0:<10} {1:>12} {2:>12} {3:>14}".format(
        "period", "favourable", "neutral", "unfavourable"))
    for pname in ("early", "middle", "late"):
        v = stability["trend_dual_ma"].get(pname, {}).get("values", {})
        print("  {0:<10} {1:>12} {2:>12} {3:>14}".format(
            pname,
            "{0:.2%}".format(v["favourable"]) if "favourable" in v else "-",
            "{0:.2%}".format(v["neutral"]) if "neutral" in v else "-",
            "{0:.2%}".format(v["unfavourable"]) if "unfavourable" in v else "-"))

    # ---- 4. transitions, measured as entry into a state ------------------
    print("\n" + "=" * 76)
    print("4. TRANSITIONS - ENTRY INTO a state from any other state")
    print("=" * 76)
    lb = labels["trend_dual_ma"]
    seq = [(d, lb.get(d)) for d in days if lb.get(d)]
    di = {d: i for i, d in enumerate(days)}
    entries = defaultdict(list)
    for i in range(1, len(seq)):
        if seq[i][1] != seq[i - 1][1]:
            entries[seq[i][1]].append(seq[i][0])
    trans = {}
    for st in STATES:
        evs = entries[st]
        print("\n  entering {0}: {1} events".format(st, len(evs)))
        print("    {0:>9} {1:>12} {2:>12} {3:>10}".format(
            "sessions", "SPY before", "SPY after", "after > 0"))
        trans[st] = {"n": len(evs), "windows": {}}
        for h in (5, 10, 20, 40):
            before, after = [], []
            for d in evs:
                i = di.get(d)
                if i is None or i - h < 0 or i + h >= len(days):
                    continue
                if days[i - h] not in spy_close or days[i + h] not in spy_close:
                    continue
                before.append(spy_close[days[i]] / spy_close[days[i - h]] - 1.0)
                after.append(spy_close[days[i + h]] / spy_close[days[i]] - 1.0)
            if not before:
                continue
            trans[st]["windows"][h] = {
                "n": len(before), "before": fmean(before),
                "after": fmean(after),
                "after_positive": sum(1 for x in after if x > 0) / len(after)}
            print("    {0:>9} {1:>12.2%} {2:>12.2%} {3:>10.1%}   n={4}".format(
                h, fmean(before), fmean(after),
                sum(1 for x in after if x > 0) / len(after), len(before)))

    print("\n  READ THIS AS: if entering 'unfavourable' were a defensive")
    print("  signal, SPY's return AFTER the flip should be negative. ")

    out = REPO / "docs" / "phase5" / "regime-stability.json"
    out.write_text(json.dumps({
        "beta": beta_out, "cash_drag": drag, "stability": stability,
        "favourable_worst_cells": {"hits": hits, "total": total,
                                   "share": hits / total},
        "transitions": trans,
        "note": "read-only; nothing registered or changed",
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
