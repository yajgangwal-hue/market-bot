"""FORENSIC_NON_PROMOTIONAL. Audit the sizing mechanism. NO REGISTRATION.

READ-ONLY. src/ untouched, nothing registered, nothing promoted. This
decides whether a defensible H-0010 exists; it does not run one.

THE EQUATION, traced from risk.position_size and its one caller in
portfolio.py rather than from documentation:

    loss_per_share = (entry - stop) + round_trip_cost_per_share(entry, stop)
    risk_limited   = equity * risk_per_trade / loss_per_share
    cash_limited   = equity * max_notional_fraction / entry
    quantity       = floor(min(risk_limited, cash_limited))
    quantity      *= conviction(symbol, history)        # [0.5, 1.5]
    quantity       = min(quantity, equity * max_notional_fraction / entry)
    quantity       = cap_by_participation(quantity, entry, adv, 0.02)
    if quantity <= 0: the candidate is DROPPED

with stop = entry - 2.5 * ATR(14), so loss_per_share is ~2.5 ATR plus
costs. That makes the scheme EQUAL-RISK, volatility-normalised through
ATR, with a 20%-of-equity concentration cap and a 2%-of-ADV
participation cap.

WHAT THIS AUDIT MUST ESTABLISH. Equal-risk sizing makes an implicit
empirical claim: that expected R-multiple does NOT depend on stop
distance. If that claim holds, the current scheme is already the right
one and there is no sizing hypothesis. If it is violated, there is a
redistribution - not an exposure - hypothesis available.

Testing that claim is not feature-fishing. ATR is ALREADY a sizing
input; the question is whether the existing input is correctly
calibrated. No new variable is introduced.
"""

import json
import sys
from collections import defaultdict
from datetime import date
from math import floor
from pathlib import Path
from statistics import fmean, median, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.indicators import wilder_atr            # noqa: E402
from event_aware_trader.mean_reversion import conviction as shipped_conviction  # noqa: E402
from event_aware_trader.phase5.metrics import measure           # noqa: E402
from event_aware_trader.research import (                        # noqa: E402
    production_policy, production_report)
from event_aware_trader.risk import CostModel, cap_by_participation  # noqa: E402

from forensics_regime import load                                # noqa: E402

_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-400:], c)
_conv = {}


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def pct(v, p):
    if not v:
        return None
    s = sorted(v)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def corr(a, b):
    if len(a) < 30:
        return None
    ma, mb = fmean(a), fmean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    return num / (da * db) if da and db else None


def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos + 1.0
        return r
    return corr(rank(xs), rank(ys))


def main():
    policy = production_policy()
    costs = CostModel()
    series = load()
    print("decade: {0} symbols".format(len(series)), flush=True)
    report = production_report(series, conviction=conviction,
                               dataset="decade", purpose="diagnostic")
    m = measure(report, "baseline").as_dict()
    print("baseline: {0} trades, total {1:+.4%}, exposure {2:.2%}\n".format(
        m["trades"], m["total_return"], m["exposure"]), flush=True)

    equity = {t.date(): v for t, v in report.equity_curve}
    dates = {s: [b.timestamp.date() for b in bs] for s, bs in series.items()}
    index = {s: {d: i for i, d in enumerate(ds)} for s, ds in dates.items()}

    print("=" * 78)
    print("1. THE MECHANISM, as traced")
    print("=" * 78)
    print("  classification   EQUAL-RISK, ATR-normalised, with two caps")
    print("  risk_per_trade                 {0}".format(policy.risk_per_trade))
    print("  max_notional_fraction          {0}".format(
        policy.max_notional_fraction))
    print("  max_volume_participation       {0}".format(
        policy.max_volume_participation))
    print("  allow_fractional_shares        {0}  (whole shares; Alpaca "
          "refuses a GTC stop on a fraction)".format(
              policy.allow_fractional_shares))
    print("  conviction multiplier          ON, [0.5, 1.5], from drawdown")
    print("                                 off the 20-day high")
    print("  candidate_rank in production   NOT PASSED -> scarce capital is")
    print("                                 allocated ALPHABETICALLY")
    print("  near_high/pullback risk scale  1.0 / 1.0 (regime-conditional")
    print("                                 sizing exists but is OFF)")

    # ---- per trade reconstruction ---------------------------------------
    rows, skipped = [], 0
    for t in report.trades:
        d0 = t.entry_time.date()
        i = index.get(t.symbol, {}).get(d0)
        eq = equity.get(d0)
        if i is None or not eq:
            skipped += 1
            continue
        bars = series[t.symbol][:i + 1]
        atr = wilder_atr(bars, 14)
        if not atr or atr <= 0:
            skipped += 1
            continue
        entry = t.entry_price
        stop = t.initial_stop
        if stop <= 0 or stop >= entry:
            skipped += 1
            continue
        lps = (entry - stop) + costs.round_trip_cost_per_share(entry, stop)
        risk_limited = eq * policy.risk_per_trade / lps
        cash_limited = eq * policy.max_notional_fraction / entry
        base = float(floor(min(risk_limited, cash_limited)))
        cv = shipped_conviction(bars[-40:]) if len(bars) >= 40 else 1.0
        scaled = base * cv
        ceiling_q = eq * policy.max_notional_fraction / entry
        clamped = min(scaled, ceiling_q)
        adv = fmean([b.close * b.volume for b in bars[-20:]])
        final = cap_by_participation(clamped, entry, adv,
                                     policy.max_volume_participation)
        # which constraint produced the final size?
        if abs(final - clamped) > 1e-9:
            binder = "participation"
        elif abs(clamped - scaled) > 1e-9:
            binder = "notional_cap"
        elif cash_limited < risk_limited:
            binder = "notional_cap"
        else:
            binder = "risk_budget"
        notional = abs(t.quantity) * entry
        rows.append({
            "symbol": t.symbol, "date": d0.isoformat(), "year": d0.year,
            "qty": t.quantity, "entry": entry, "notional": notional,
            "equity": eq, "size_pct": notional / eq,
            "atr_frac": atr / entry, "loss_per_share_frac": lps / entry,
            "conviction": cv, "binder": binder,
            "planned_risk_pct": (t.quantity * lps) / eq,
            "r": t.r_multiple, "pnl": t.net_pnl, "reason": t.exit_reason,
            "bars_held": t.bars_held,
        })

    print("\n" + "=" * 78)
    print("2. WHICH CONSTRAINT ACTUALLY BINDS  (reconstructed, n={0}, {1} "
          "skipped)".format(len(rows), skipped))
    print("=" * 78)
    b = defaultdict(int)
    for r in rows:
        b[r["binder"]] += 1
    for k in sorted(b, key=lambda x: -b[x]):
        print("  {0:<18} {1:>5} ({2:.1%})".format(k, b[k], b[k] / len(rows)))

    sz = [r["size_pct"] for r in rows]
    pr = [r["planned_risk_pct"] for r in rows]
    print("\n  position size as % of equity")
    print("    mean {0:.2%}  median {1:.2%}  p10 {2:.2%}  p90 {3:.2%}  "
          "max {4:.2%}".format(fmean(sz), median(sz), pct(sz, 10),
                               pct(sz, 90), max(sz)))
    print("  planned risk as % of equity (budget is {0:.2%})".format(
        policy.risk_per_trade))
    print("    mean {0:.3%}  median {1:.3%}  p10 {2:.3%}  p90 {3:.3%}".format(
        fmean(pr), median(pr), pct(pr, 10), pct(pr, 90)))

    # ---- THE EQUAL-RISK ASSUMPTION --------------------------------------
    print("\n" + "=" * 78)
    print("3. IS THE EQUAL-RISK ASSUMPTION VIOLATED?")
    print("=" * 78)
    print("  Equal-risk sizing asserts expected R does NOT depend on stop")
    print("  distance. If R rises or falls with ATR, capital is misallocated.")
    print("  ATR is ALREADY a sizing input, so this tests calibration of an")
    print("  existing term, not a new feature.")
    vals = sorted(r["atr_frac"] for r in rows)
    q1, q2, q3 = pct(vals, 25), pct(vals, 50), pct(vals, 75)
    print("\n  {0:<16} {1:>6} {2:>10} {3:>10} {4:>10} {5:>9} {6:>9}".format(
        "ATR quartile", "n", "mean ATR", "mean size", "mean R", "median R",
        "win"))
    quart = {}
    for name, lo, hi in (("Q1 tightest", -1, q1), ("Q2", q1, q2),
                         ("Q3", q2, q3), ("Q4 widest", q3, 1e9)):
        g = [r for r in rows if lo < r["atr_frac"] <= hi]
        if not g:
            continue
        quart[name] = {"n": len(g),
                       "atr": fmean([r["atr_frac"] for r in g]),
                       "size": fmean([r["size_pct"] for r in g]),
                       "mean_r": fmean([r["r"] for r in g]),
                       "median_r": median([r["r"] for r in g]),
                       "win": sum(1 for r in g if r["pnl"] > 0) / len(g),
                       "pnl": sum(r["pnl"] for r in g)}
        q = quart[name]
        print("  {0:<16} {1:>6} {2:>10.2%} {3:>10.2%} {4:>10.3f} {5:>9.3f} "
              "{6:>9.1%}".format(name, q["n"], q["atr"], q["size"],
                                 q["mean_r"], q["median_r"], q["win"]))
    rho_atr = spearman([r["atr_frac"] for r in rows], [r["r"] for r in rows])
    print("\n  Spearman(ATR fraction, realised R) = {0:+.4f}".format(rho_atr))
    se = 1.0 / (len(rows) - 1) ** 0.5
    print("  approx SE under the null {0:.4f}, so |rho| below about {1:.3f} "
          "is noise".format(se, 2 * se))
    print("  -> {0}".format(
        "NO usable relationship: equal-risk is not detectably miscalibrated"
        if abs(rho_atr) < 2 * se else
        "a relationship exists; magnitude and stability decide"))

    # ---- is conviction calibrated? --------------------------------------
    print("\n" + "=" * 78)
    print("4. IS THE EXISTING CONVICTION MULTIPLIER CALIBRATED?")
    print("=" * 78)
    cv = sorted(r["conviction"] for r in rows)
    c1, c2, c3 = pct(cv, 25), pct(cv, 50), pct(cv, 75)
    print("  {0:<16} {1:>6} {2:>11} {3:>10} {4:>10} {5:>9} {6:>12}".format(
        "conviction", "n", "mean mult", "mean size", "mean R", "win",
        "total P&L"))
    for name, lo, hi in (("Q1 lowest", -1, c1), ("Q2", c1, c2),
                         ("Q3", c2, c3), ("Q4 highest", c3, 1e9)):
        g = [r for r in rows if lo < r["conviction"] <= hi]
        if not g:
            continue
        print("  {0:<16} {1:>6} {2:>11.3f} {3:>10.2%} {4:>10.3f} {5:>9.1%} "
              "{6:>12,.0f}".format(
                  name, len(g), fmean([r["conviction"] for r in g]),
                  fmean([r["size_pct"] for r in g]),
                  fmean([r["r"] for r in g]),
                  sum(1 for r in g if r["pnl"] > 0) / len(g),
                  sum(r["pnl"] for r in g)))
    rho_cv = spearman([r["conviction"] for r in rows], [r["r"] for r in rows])
    print("\n  Spearman(conviction, realised R) = {0:+.4f}".format(rho_cv))
    print("  -> {0}".format(
        "the multiplier is NOT detectably predictive of R on this sample"
        if abs(rho_cv) < 2 * se else "the multiplier carries signal"))

    # ---- does big capital earn its keep? --------------------------------
    print("\n" + "=" * 78)
    print("5. DO LARGE POSITIONS EARN THEIR CAPITAL?")
    print("=" * 78)
    ordered = sorted(rows, key=lambda r: -r["size_pct"])
    n = len(ordered)
    print("  {0:<14} {1:>6} {2:>11} {3:>13} {4:>13} {5:>10}".format(
        "size decile", "n", "mean size", "notional $", "P&L $", "per $1k"))
    for k in range(5):
        g = ordered[k * n // 5:(k + 1) * n // 5]
        tot = sum(r["notional"] for r in g)
        p = sum(r["pnl"] for r in g)
        print("  {0:<14} {1:>6} {2:>11.2%} {3:>13,.0f} {4:>13,.0f} "
              "{5:>10.2f}".format(
                  "Q{0} {1}".format(k + 1, "largest" if k == 0 else
                                    ("smallest" if k == 4 else "")),
                  len(g), fmean([r["size_pct"] for r in g]), tot, p,
                  1000 * p / tot if tot else 0.0))

    # ---- stability of the allocation inefficiency -----------------------
    # Declared here: chronological thirds by entry date, equal count.
    print("")
    print("=" * 78)
    print("6. STABILITY - chronological thirds, declared before computing")
    print("=" * 78)
    ordered_t = sorted(rows, key=lambda r: r["date"])
    th = len(ordered_t) // 3
    parts = [("early", ordered_t[:th]), ("middle", ordered_t[th:2 * th]),
             ("late", ordered_t[2 * th:])]

    def per1k(g):
        n = sum(r["notional"] for r in g)
        return 1000 * sum(r["pnl"] for r in g) / n if n else 0.0

    print("  LARGEST SIZE QUINTILE vs the rest, P&L per $1,000 of notional")
    print("  {0:<8} {1:>6} {2:>12} {3:>12} {4:>12} {5:>12}".format(
        "period", "n Q1", "Q1 $/1k", "rest $/1k", "Q1 mean R", "rest mean R"))
    stab_size = {}
    for name, part in parts:
        o = sorted(part, key=lambda r: -r["size_pct"])
        k = len(o) // 5
        q1, rest = o[:k], o[k:]
        stab_size[name] = {"n": len(q1), "q1": per1k(q1), "rest": per1k(rest),
                           "q1_r": fmean([r["r"] for r in q1]),
                           "rest_r": fmean([r["r"] for r in rest])}
        v = stab_size[name]
        print("  {0:<8} {1:>6} {2:>12.2f} {3:>12.2f} {4:>12.3f} "
              "{5:>12.3f}".format(name, v["n"], v["q1"], v["rest"],
                                  v["q1_r"], v["rest_r"]))
    worse = sum(1 for v in stab_size.values() if v["q1"] < v["rest"])
    print("  largest quintile WORSE than the rest in {0} of 3 periods".format(
        worse))

    print("")
    print("  TIGHTEST-ATR QUARTILE vs the rest - the structural driver")
    print("  {0:<8} {1:>6} {2:>12} {3:>12} {4:>12}".format(
        "period", "n", "Q1atr $/1k", "rest $/1k", "Q1atr mean R"))
    stab_atr = {}
    for name, part in parts:
        o = sorted(part, key=lambda r: r["atr_frac"])
        k = len(o) // 4
        q1, rest = o[:k], o[k:]
        stab_atr[name] = {"n": len(q1), "q1": per1k(q1), "rest": per1k(rest),
                          "q1_r": fmean([r["r"] for r in q1])}
        v = stab_atr[name]
        print("  {0:<8} {1:>6} {2:>12.2f} {3:>12.2f} {4:>12.3f}".format(
            name, v["n"], v["q1"], v["rest"], v["q1_r"]))
    worse_atr = sum(1 for v in stab_atr.values() if v["q1"] < v["rest"])
    print("  tightest-ATR quartile WORSE in {0} of 3 periods".format(
        worse_atr))

    out = REPO / "docs" / "phase5" / "sizing-audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "FORENSIC_NON_PROMOTIONAL": True,
        "mechanism": "equal-risk, ATR-normalised, 20% notional cap, 2% ADV "
                     "participation cap, conviction [0.5,1.5], whole shares, "
                     "alphabetical candidate order in production",
        "policy": {f: getattr(policy, f) for f in
                   ("risk_per_trade", "max_notional_fraction",
                    "max_volume_participation", "max_open_positions",
                    "max_per_bucket", "allow_fractional_shares")},
        "trades": len(rows), "skipped": skipped,
        "binders": dict(b),
        "size_pct": {"mean": fmean(sz), "median": median(sz),
                     "p10": pct(sz, 10), "p90": pct(sz, 90), "max": max(sz)},
        "planned_risk_pct": {"mean": fmean(pr), "median": median(pr)},
        "atr_quartiles": quart,
        "spearman_atr_r": rho_atr, "spearman_conviction_r": rho_cv,
        "noise_band_2se": 2 * se,
        "stability_by_size": stab_size,
        "stability_by_atr": stab_atr,
        "size_q1_worse_in": worse,
        "atr_q1_worse_in": worse_atr,
        "note": "READ-ONLY audit. No experiment registered.",
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
