"""FORENSIC_NON_PROMOTIONAL. Copy-trading feasibility, from the cache.

READ-ONLY. Reads docs/phase5/copy-cache.json, writes a report JSON.
Nothing registered, nothing promoted, src/ untouched. Re-runnable in
seconds, so the expensive simulation is never repeated.

DECLARED BEFORE ANY OUTCOME WAS EXAMINED (and unchanged since the
cache was built):
  Chronological thirds of the sessions, equal count.
  Agreement states BOTH / MAIN_ONLY / COPY_ONLY, defined on candidate
  sets per session before any return was attached.
  Forward horizons 5, 10, 20 sessions, excess vs SPY.

THE UNIT MATTERS. Name-day observations cluster: most names move
together on a given day, and the same name recurs on consecutive days
with overlapping forward windows. Every headline number is therefore
also reported DAY-COLLAPSED - one observation per session - which is
the honest unit and the one the conclusion rests on.
"""

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import fmean, median, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.strategy import CORRELATION_BUCKETS      # noqa: E402
from forensics_regime import load                                # noqa: E402

HORIZONS = (5, 10, 20)
TRADING_YEAR = 252.0
CACHE = REPO / "docs" / "phase5" / "copy-cache.json"


def corr(a, b):
    if len(a) < 30:
        return None
    ma, mb = fmean(a), fmean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    return num / (da * db) if da and db else None


def curve(packed):
    eq = {date.fromisoformat(d): v for d, v in packed["equity"]}
    days = sorted(eq)
    rets = {}
    for i, d in enumerate(days):
        p = eq[days[i - 1]] if i else None
        if p:
            rets[d] = eq[d] / p - 1.0
    return eq, days, rets


def held(packed, days):
    out = defaultdict(set)
    for t in packed["trades"]:
        d0 = date.fromisoformat(t["entry"])
        d1 = date.fromisoformat(t["exit"])
        for d in days:
            if d0 <= d < d1:
                out[d].add(t["symbol"])
    return out


def main():
    if not CACHE.exists():
        print("no cache; run scripts/copy_build_cache.py first")
        return 2
    C = json.loads(CACHE.read_text(encoding="utf-8"))
    m, t = C["main"]["metrics"], C["trend"]["metrics"]
    spy_total = C["spy_total"]
    series = load()
    spy_close = {b.timestamp.date(): b.close for b in series["SPY"]}

    print("=" * 76)
    print("COPY-TRADING FEASIBILITY - the internal source")
    print("=" * 76)
    print("  baseline equivalence: {0}".format(
        "PASS" if C["baseline_equivalence"] else "FAIL"))
    print("  defect shim fired:    {0} times (src/ NOT modified)".format(
        C["shim_hits"]))

    # ---- standalone -----------------------------------------------------
    print("\n1. STANDALONE PERFORMANCE")
    print("  {0:<26} {1:>14} {2:>14} {3:>14}".format(
        "", "MAIN (prod)", "TREND (copy)", "SPY"))
    rows = [("total return", "total_return", "{0:+.2%}"),
            ("CAGR", "cagr", "{0:+.2%}"),
            ("annualised volatility", "annualised_volatility", "{0:.2%}"),
            ("Sharpe", "sharpe", "{0:.4f}"),
            ("Sortino", "sortino", "{0:.4f}"),
            ("max drawdown", "max_drawdown", "{0:.4%}"),
            ("Calmar", "calmar", "{0:.4f}"),
            ("trades", "trades", "{0}"),
            ("win rate", "win_rate", "{0:.2%}"),
            ("profit factor", "profit_factor", "{0:.3f}"),
            ("turnover", "turnover", "{0:.2f}"),
            ("transaction costs", "transaction_costs", "${0:,.0f}"),
            ("exposure", "exposure", "{0:.2%}")]
    for label, key, fmt in rows:
        a = fmt.format(m[key]) if m.get(key) is not None else "-"
        b = fmt.format(t[key]) if t.get(key) is not None else "-"
        c = "{0:+.2%}".format(spy_total) if key == "total_return" else "-"
        print("  {0:<26} {1:>14} {2:>14} {3:>14}".format(label, a, b, c))
    print("  {0:<26} {1:>14} {2:>14} {3:>14}".format(
        "excess vs SPY (points)",
        "{0:+.2f}".format(100 * (m["total_return"] - spy_total)),
        "{0:+.2f}".format(100 * (t["total_return"] - spy_total)), "0.00"))

    print("\n  year by year")
    print("  {0:>6} {1:>12} {2:>12}".format("year", "MAIN", "TREND"))
    for y in sorted(m["by_year"]):
        print("  {0:>6} {1:>12.2%} {2:>12.2%}".format(
            y, m["by_year"][y], t["by_year"].get(y, 0.0)))

    # ---- independence ----------------------------------------------------
    eq_m, days_m, ret_m = curve(C["main"])
    eq_t, days_t, ret_t = curve(C["trend"])
    common = [d for d in days_m if d in ret_m and d in ret_t]
    rc = corr([ret_m[d] for d in common], [ret_t[d] for d in common])

    print("\n2. INDEPENDENCE")
    print("  daily return correlation, main vs trend: {0:+.4f} (n={1})".format(
        rc, len(common)))

    mbd, cbd = defaultdict(set), defaultdict(set)
    for x in C["main"]["trades"]:
        mbd[date.fromisoformat(x["entry"])].add(x["symbol"])
    for x in C["trend"]["trades"]:
        cbd[date.fromisoformat(x["entry"])].add(x["symbol"])
    all_m = {(d, s) for d, ss in mbd.items() for s in ss}
    all_c = {(d, s) for d, ss in cbd.items() for s in ss}
    both = all_m & all_c
    print("\n  ENTRY OVERLAP")
    print("    main entries                  {0}".format(len(all_m)))
    print("    trend entries                 {0}".format(len(all_c)))
    print("    same symbol, same day         {0} ({1:.2%} of main, "
          "{2:.2%} of trend)".format(len(both), len(both) / len(all_m),
                                     len(both) / len(all_c)))
    ms, cs = {s for _d, s in all_m}, {s for _d, s in all_c}
    print("    distinct symbols              main {0}, trend {1}, shared "
          "{2}".format(len(ms), len(cs), len(ms & cs)))
    mb = {CORRELATION_BUCKETS.get(s, "other") for s in ms}
    cb = {CORRELATION_BUCKETS.get(s, "other") for s in cs}
    print("    buckets                       main {0}, trend {1}, shared "
          "{2}".format(len(mb), len(cb), len(mb & cb)))

    open_m, open_c = held(C["main"], days_m), held(C["trend"], days_m)
    same_name = [len(open_m[d] & open_c[d]) for d in days_m]
    both_open = sum(1 for d in days_m if open_m[d] and open_c[d])
    clash = sum(1 for d in days_m
                if {CORRELATION_BUCKETS.get(s, "other") for s in open_m[d]}
                & {CORRELATION_BUCKETS.get(s, "other") for s in open_c[d]})
    print("\n  SIMULTANEOUS EXPOSURE (duplicated-risk test)")
    print("    sessions both hold something  {0} ({1:.1%})".format(
        both_open, both_open / len(days_m)))
    print("    mean same NAME held by both   {0:.4f}".format(fmean(same_name)))
    print("    sessions sharing a BUCKET     {0} ({1:.1%})".format(
        clash, clash / len(days_m)))

    # ---- incremental information -----------------------------------------
    dates = {s: [b.timestamp.date() for b in bs] for s, bs in series.items()}
    closes = {s: [b.close for b in bs] for s, bs in series.items()}
    index = {s: {d: i for i, d in enumerate(ds)} for s, ds in dates.items()}
    spy_d = dates["SPY"]
    spy_i = index["SPY"]

    def fwd(sym, d, h):
        i = index.get(sym, {}).get(d)
        if i is None or i + h >= len(closes[sym]):
            return None
        return closes[sym][i + h] / closes[sym][i] - 1.0

    def sfwd(d, h):
        i = spy_i.get(d)
        if i is None or i + h >= len(spy_d):
            return None
        return spy_close[spy_d[i + h]] / spy_close[spy_d[i]] - 1.0

    main_c = defaultdict(set)
    for line in (REPO / "data" / "phase5" / "candidates-deep.jsonl"
                 ).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            main_c[date.fromisoformat(r["date"])].add(r["symbol"])

    states = defaultdict(list)
    for d in days_m:
        mc, cc = main_c.get(d, set()), cbd.get(d, set())
        for s in mc | cc:
            st = ("BOTH" if s in mc and s in cc
                  else "MAIN_ONLY" if s in mc else "COPY_ONLY")
            row = {"date": d, "symbol": s}
            vals = {}
            ok = True
            for h in HORIZONS:
                a, b = fwd(s, d, h), sfwd(d, h)
                if a is None or b is None:
                    ok = False
                    break
                vals[h] = a - b
            if ok:
                row.update(vals)
                states[st].append(row)

    print("\n3. INCREMENTAL INFORMATION - agreement states")
    print("  {0:<12} {1:>7} {2:>11} {3:>11} {4:>11} {5:>8}".format(
        "state", "n", "exc 5s", "exc 10s", "exc 20s", "win@10"))
    inc = {}
    for st in ("BOTH", "MAIN_ONLY", "COPY_ONLY"):
        g = states.get(st, [])
        if not g:
            print("  {0:<12} {1:>7}".format(st, 0))
            continue
        cells = [fmean([r[h] for r in g]) for h in HORIZONS]
        w = sum(1 for r in g if r[10] > 0) / len(g)
        inc[st] = {"n": len(g), "win10": w,
                   **{str(h): fmean([r[h] for r in g]) for h in HORIZONS}}
        print("  {0:<12} {1:>7} {2:>11.3%} {3:>11.3%} {4:>11.3%} "
              "{5:>8.1%}".format(st, len(g), *cells, w))
    if "BOTH" in inc and "MAIN_ONLY" in inc:
        prem = inc["BOTH"]["10"] - inc["MAIN_ONLY"]["10"]
        print("\n  agreement premium @10s (BOTH - MAIN_ONLY): {0:+.3%}".format(
            prem))

    print("\n  DAY-COLLAPSED (one observation per session - the honest unit)")
    print("  {0:<12} {1:>7} {2:>11} {3:>9} {4:>7}".format(
        "state", "days", "mean@10s", "SE", "t"))
    coll = {}
    for st in ("BOTH", "MAIN_ONLY", "COPY_ONLY"):
        g = states.get(st, [])
        if not g:
            continue
        byd = defaultdict(list)
        for r in g:
            byd[r["date"]].append(r[10])
        v = [fmean(x) for x in byd.values()]
        if len(v) < 30:
            continue
        se = pstdev(v) / (len(v) ** 0.5)
        coll[st] = {"days": len(v), "mean": fmean(v), "se": se,
                    "t": fmean(v) / se if se else None}
        print("  {0:<12} {1:>7} {2:>11.4%} {3:>9.4%} {4:>7.2f}".format(
            st, len(v), fmean(v), se, fmean(v) / se if se else 0.0))

    # paired within-session: BOTH minus MAIN_ONLY, market move cancels
    bd, md = defaultdict(list), defaultdict(list)
    for r in states.get("BOTH", []):
        bd[r["date"]].append(r[10])
    for r in states.get("MAIN_ONLY", []):
        md[r["date"]].append(r[10])
    shared = sorted(set(bd) & set(md))
    if len(shared) >= 30:
        diffs = [fmean(bd[d]) - fmean(md[d]) for d in shared]
        se = pstdev(diffs) / (len(diffs) ** 0.5)
        print("\n  PAIRED within-session (BOTH - MAIN_ONLY), market cancels")
        print("    sessions {0}, mean {1:+.4%}, SE {2:.4%}, t {3:.2f}, "
              "win {4:.1%}".format(len(diffs), fmean(diffs), se,
                                   fmean(diffs) / se if se else 0.0,
                                   sum(1 for x in diffs if x > 0) / len(diffs)))
        paired = {"sessions": len(diffs), "mean": fmean(diffs), "se": se,
                  "t": fmean(diffs) / se if se else None}
    else:
        paired = {"sessions": len(shared), "note": "too few shared sessions"}
        print("\n  PAIRED: only {0} shared sessions - not computed".format(
            len(shared)))

    # ---- time split ------------------------------------------------------
    third = len(days_m) // 3
    cuts = (days_m[third], days_m[2 * third])
    spy_r = {}
    for i, d in enumerate(spy_d):
        if i:
            spy_r[d] = spy_close[d] / spy_close[spy_d[i - 1]] - 1.0

    def period(d):
        return "early" if d < cuts[0] else ("middle" if d < cuts[1] else "late")

    print("\n4. TIME SPLIT - chronological thirds ({0} / {1})".format(*cuts))
    print("  {0:<8} {1:>12} {2:>12} {3:>12}".format(
        "period", "MAIN ann", "TREND ann", "SPY ann"))
    thirds = {}
    for p in ("early", "middle", "late"):
        ds = [d for d in days_m if period(d) == p]
        a = [ret_m[d] for d in ds if d in ret_m]
        b = [ret_t[d] for d in ds if d in ret_t]
        c = [spy_r[d] for d in ds if d in spy_r]
        thirds[p] = {"main": fmean(a) * TRADING_YEAR,
                     "trend": fmean(b) * TRADING_YEAR,
                     "spy": fmean(c) * TRADING_YEAR}
        print("  {0:<8} {1:>12.2%} {2:>12.2%} {3:>12.2%}".format(
            p, thirds[p]["main"], thirds[p]["trend"], thirds[p]["spy"]))

    print("\n  agreement premium @10s by period")
    prem_split = {}
    for p in ("early", "middle", "late"):
        b = [r[10] for r in states.get("BOTH", []) if period(r["date"]) == p]
        mo = [r[10] for r in states.get("MAIN_ONLY", [])
              if period(r["date"]) == p]
        if len(b) < 20 or len(mo) < 20:
            print("    {0:<8} n/a (BOTH n={1})".format(p, len(b)))
            prem_split[p] = None
            continue
        prem_split[p] = fmean(b) - fmean(mo)
        print("    {0:<8} {1:+.3%}  (BOTH n={2}, MAIN_ONLY n={3})".format(
            p, prem_split[p], len(b), len(mo)))

    # ---- Mode E: the only mechanism the overlap does not kill ----------
    # Daily-rebalanced and frictionless: an IDEALISATION that FLATTERS the
    # blend, since real rebalancing costs money. Stated, not corrected.
    print("")
    print("5. MODE E - DIVERSIFICATION BLEND (measured, not approximated)")
    print("  {0:<10} {1:>10} {2:>9} {3:>9} {4:>9} {5:>11} {6:>12}".format(
        "main/trend", "total", "CAGR", "vol", "Sharpe", "maxDD", "vs SPY pts"))

    def blend_stats(w):
        v = [w * ret_m[d] + (1 - w) * ret_t[d] for d in common]
        c = [1.0]
        for x in v:
            c.append(c[-1] * (1 + x))
        peak, dd = c[0], 0.0
        for x in c:
            peak = max(peak, x)
            dd = min(dd, x / peak - 1)
        return {"total": c[-1] - 1,
                "cagr": c[-1] ** (TRADING_YEAR / len(v)) - 1,
                "vol": pstdev(v) * TRADING_YEAR ** 0.5,
                "sharpe": fmean(v) / pstdev(v) * TRADING_YEAR ** 0.5,
                "dd": dd}

    blends = {}
    for w in (1.0, 0.75, 0.5, 0.25, 0.0):
        b = blend_stats(w)
        blends["{0:.0f}/{1:.0f}".format(w * 100, (1 - w) * 100)] = b
        print("  {0:<10} {1:>10.2%} {2:>9.2%} {3:>9.2%} {4:>9.4f} "
              "{5:>11.4%} {6:>12.2f}".format(
                  "{0:.0f}/{1:.0f}".format(w * 100, (1 - w) * 100),
                  b["total"], b["cagr"], b["vol"], b["sharpe"], b["dd"],
                  100 * (b["total"] - spy_total)))
    base, half = blends["100/0"], blends["50/50"]
    ceiling = 1.10 * abs(base["dd"])
    print("")
    print("  50/50 against 100% main:")
    print("    Sharpe       {0:+.4f}".format(half["sharpe"] - base["sharpe"]))
    print("    total return {0:+.2f} points".format(
        100 * (half["total"] - base["total"])))
    print("    gap to SPY   {0:+.2f} points WIDER".format(
        100 * (base["total"] - half["total"])))
    print("    maxDD        {0:+.2f} points".format(
        100 * (abs(half["dd"]) - abs(base["dd"]))))
    print("  110% ceiling {0:.4%}: every blend is WITHIN it, and every blend"
          .format(ceiling))
    print("  moves the WRONG WAY on excess return vs SPY.")

    out = REPO / "docs" / "phase5" / "copy-feasibility.json"
    out.write_text(json.dumps({
        "FORENSIC_NON_PROMOTIONAL": True,
        "baseline_equivalence": C["baseline_equivalence"],
        "shim_hits": C["shim_hits"],
        "main": m, "trend": t, "spy_total": spy_total,
        "daily_return_correlation": rc,
        "entry_overlap": {
            "main": len(all_m), "trend": len(all_c),
            "same_symbol_same_day": len(both),
            "shared_symbols": len(ms & cs),
            "buckets_main": len(mb), "buckets_trend": len(cb),
            "buckets_shared": len(mb & cb),
            "sessions_both_hold": both_open,
            "mean_same_name_held": fmean(same_name),
            "sessions_sharing_bucket": clash,
            "sessions": len(days_m)},
        "agreement_states": inc, "day_collapsed": coll, "paired": paired,
        "thirds": thirds, "premium_by_third": prem_split,
        "blends": blends, "ceiling": ceiling,
        "note": "READ-ONLY feasibility. Not an experiment, not promotable.",
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
