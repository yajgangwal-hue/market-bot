"""FORENSIC_NON_PROMOTIONAL. What can this repository actually copy?

READ-ONLY. Nothing registered, nothing promoted, src/ untouched.

STEP 1 OF THE BRIEF: audit the available sources and measure whether
they are INDEPENDENT, before asking whether they are profitable.

WHAT THIS IS NOT. There is no external trader feed in this repository:
no signal-provider history, no copied portfolios, no third-party
rankings. `data/news/` holds five days. `social.py` fetches live and
archives nothing. So "copy trading" in the retail sense - mirroring
other people's positions - has NO DATA and is not testable here. That
is reported as a finding, not worked around.

WHAT IS AVAILABLE is the repository's own second entry rule. The
simulator accepts entry_rule in {"trend", "mean_reversion"}; production
is mean_reversion. The trend rule is a complete, independently written
entry AND exit system that runs through the identical portfolio engine
on the identical bars, so it can be run standalone and its signals
compared day by day against production's.

THE INDEPENDENCE QUESTION IS THE POINT. Different code is not
independence. Both rules read the same daily OHLCV for the same 230
names and both compute moving averages, ATR and RSI from it. If their
signals overlap heavily, copying one duplicates risk rather than adding
information - and that is measured here rather than assumed.

DECLARED BEFORE ANY OUTCOME IS EXAMINED
  Chronological thirds of the sessions, equal count.
  Agreement states: BOTH, MAIN_ONLY, COPY_ONLY, NEITHER - defined on
  candidate sets per session, before any return is attached.
  Forward horizons 5, 10, 20 sessions, raw and excess vs SPY.
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
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.mean_reversion import conviction as shipped_conviction  # noqa: E402
from event_aware_trader.phase5.metrics import measure          # noqa: E402
from event_aware_trader.research import (                       # noqa: E402
    DATASET_USES, PRODUCTION_CANDIDATE, _record_gate_use,
    production_policy, production_report)
from event_aware_trader.risk import CostModel                   # noqa: E402
from event_aware_trader.strategy import CORRELATION_BUCKETS      # noqa: E402

from forensics_regime import build_signals, load, STATES         # noqa: E402

_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-400:], c)
_conv = {}
HORIZONS = (5, 10, 20)
TRADING_YEAR = 252.0


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


#: A DEFECT IN THE COPY SOURCE, shimmed here and NOT fixed in src/.
#: strategy.generate_candidate detects `stop <= 0` and appends the
#: blocker "Calculated stop is non-positive", then CONTINUES and hands
#: that same negative stop to costs.round_trip_cost_per_share, which
#: raises ValueError. The blocker is recorded and then never reached.
#: The shim catches the raise and returns the REJECT the function was
#: already trying to produce, so behaviour matches the code's evident
#: intent. Every occurrence is counted and reported.
SHIM_HITS = {"n": 0}


def _guarded_generate(original):
    from event_aware_trader.strategy import _rejected

    def wrapped(symbol, bars, *args, **kwargs):
        try:
            return original(symbol, bars, *args, **kwargs)
        except ValueError as error:
            if "price must be positive" not in str(error):
                raise
            SHIM_HITS["n"] += 1
            return _rejected(
                symbol, bars[-1].timestamp,
                CORRELATION_BUCKETS.get(symbol, "other"),
                [], ["Calculated stop is non-positive"], {})
    return wrapped


def run_trend(series):
    """The other entry rule, through the identical engine and costs."""
    _record_gate_use("decade", "diagnostic", len(series), DATASET_USES)
    original = portfolio_module.generate_candidate
    portfolio_module.generate_candidate = _guarded_generate(original)
    try:
        return portfolio_module.run_portfolio(
            series, starting_cash=100_000.0, policy=production_policy(),
            costs=CostModel(), conviction=conviction, entry_rule="trend")
    finally:
        portfolio_module.generate_candidate = original


def curve_stats(report):
    eq = {t.date(): v for t, v in report.equity_curve}
    days = sorted(eq)
    rets = {}
    for i, d in enumerate(days):
        p = eq[days[i - 1]] if i else None
        if p:
            rets[d] = eq[d] / p - 1.0
    return eq, days, rets


def corr(a, b):
    if len(a) < 30:
        return None
    ma, mb = fmean(a), fmean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    return num / (da * db) if da and db else None


def main():
    series = load()
    spy = series["SPY"]
    spy_close = {b.timestamp.date(): b.close for b in spy}
    spy_total = spy[-1].close / spy[0].close - 1.0
    print("decade: {0} symbols, SPY {1} -> {2}".format(
        len(series), spy[0].timestamp.date(), spy[-1].timestamp.date()),
        flush=True)

    # ---- 0. source audit ------------------------------------------------
    print("\n" + "=" * 76)
    print("0. SOURCE AUDIT - what exists, and when it is available")
    print("=" * 76)
    print("  {0:<22} {1:<34} {2}".format("source", "what it provides", "usable?"))
    audit = [
        ("external trader feed", "copied positions / provider signals",
         "ABSENT - no data of any kind"),
        ("social.py", "live posts, REVIEW_REQUIRED alerts",
         "NO - live fetch, zero archive"),
        ("data/news/", "live headline feed", "NO - 5 days only"),
        ("news archive (phase5)", "11,852 headlines, no bodies",
         "CLOSED - classified A on 2026-09-18"),
        ("TREND RULE", "full entry+exit rule, same engine",
         "YES - runnable on the decade"),
        ("smc.py", "structure detectors, confirmation-lagged",
         "features, not a strategy"),
        ("cross_sectional.py", "peer-rank features",
         "features, not a strategy"),
        ("regime_shorts.py", "short-only in confirmed bear tape",
         "NO - long-only book"),
        ("crypto_sleeve.py", "BTC allocation", "NO - different asset"),
        ("peak_exit.py", "intraday exit timing", "exit only, not a signal"),
        ("live_model / trade_learning", "learned rank + veto",
         "DISABLED, and not independent"),
    ]
    for a, b, c in audit:
        print("  {0:<22} {1:<34} {2}".format(a, b, c))

    # ---- 1. baseline equivalence ---------------------------------------
    print("\n" + "=" * 76)
    print("1. BASELINE EQUIVALENCE (mandatory, before anything else)")
    print("=" * 76)
    main_rep = production_report(series, conviction=conviction,
                                 dataset="decade", purpose="diagnostic")
    m = measure(main_rep, "MAIN").as_dict()
    print("  main strategy  {0:+.10%} over {1} trades".format(
        m["total_return"], m["trades"]))
    print("  registered     +58.5889000000% over 698 trades")
    if abs(m["total_return"] - 0.585889) > 5e-7 or m["trades"] != 698:
        print("  STOPPED: baseline did not reproduce.")
        return 2
    print("  reproduced - proceeding")

    # ---- 2. the copy source standalone ---------------------------------
    print("\n" + "=" * 76)
    print("2. THE TREND RULE, STANDALONE (item 6)")
    print("=" * 76, flush=True)
    trend_rep = run_trend(series)
    t = measure(trend_rep, "TREND").as_dict()
    print("  DEFECT SHIM: generate_candidate raised on a non-positive stop "
          "{0} times".format(SHIM_HITS["n"]))
    print("  (recorded as a finding; src/ was NOT modified)")
    eq_m, days_m, ret_m = curve_stats(main_rep)
    eq_t, days_t, ret_t = curve_stats(trend_rep)
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

    print("\n  year by year (total return)")
    print("  {0:>6} {1:>12} {2:>12}".format("year", "MAIN", "TREND"))
    for y in sorted(m["by_year"]):
        print("  {0:>6} {1:>12.2%} {2:>12.2%}".format(
            y, m["by_year"][y], t["by_year"].get(y, 0.0)))

    # ---- 3. independence -------------------------------------------------
    print("\n" + "=" * 76)
    print("3. INDEPENDENCE AUDIT (item 4) - different code is not enough")
    print("=" * 76)
    print("  {0:<24} {1:<26} {2}".format("dimension", "MAIN", "TREND"))
    dims = [
        ("underlying data", "daily OHLCV, 230 names", "daily OHLCV, 230 names"),
        ("shared substrate", "SAME BARS", "SAME BARS"),
        ("direction", "buy weakness (RSI<=35)", "buy strength (breakout/ADX)"),
        ("trend filter", "close > 200-day SMA", "20/50 SMA + ADX>=18 + R2>=0.4"),
        ("entry trigger", "RSI(14) <= 35", "score >= 70 composite"),
        ("exit", "RSI>=60 / 2.5ATR stop / 20 bars",
         "trailing 2.5ATR from 0.5R / 20 bars"),
        ("stop", "2.5 x ATR(14)", "2.0 x ATR(14)"),
        ("liquidity floor", "$50M ADV, $20", "$50M ADV, $20"),
        ("universe", "same 230", "same 230"),
        ("benchmark", "SPY", "SPY"),
        ("holding cap", "20 bars", "20 bars"),
    ]
    for a, b, c in dims:
        print("  {0:<24} {1:<26} {2}".format(a, b, c))

    common = [d for d in days_m if d in ret_m and d in ret_t]
    rc = corr([ret_m[d] for d in common], [ret_t[d] for d in common])
    print("\n  DAILY RETURN CORRELATION, main vs trend: {0:+.4f} "
          "(n={1})".format(rc, len(common)))

    main_by_day = defaultdict(set)
    for tr in main_rep.trades:
        main_by_day[tr.entry_time.date()].add(tr.symbol)
    copy_by_day = defaultdict(set)
    for tr in trend_rep.trades:
        copy_by_day[tr.entry_time.date()].add(tr.symbol)
    all_main = {(d, s) for d, ss in main_by_day.items() for s in ss}
    all_copy = {(d, s) for d, ss in copy_by_day.items() for s in ss}
    both = all_main & all_copy
    print("\n  ENTRY OVERLAP (item 5)")
    print("    main entries            {0}".format(len(all_main)))
    print("    trend entries           {0}".format(len(all_copy)))
    print("    SAME symbol same day    {0} ({1:.2%} of main, {2:.2%} of "
          "trend)".format(len(both), len(both) / len(all_main),
                          len(both) / len(all_copy)))
    ms = {s for _d, s in all_main}
    cs = {s for _d, s in all_copy}
    print("    distinct symbols        main {0}, trend {1}, shared {2}".format(
        len(ms), len(cs), len(ms & cs)))
    mb = defaultdict(int)
    cb = defaultdict(int)
    for _d, s in all_main:
        mb[CORRELATION_BUCKETS.get(s, "other")] += 1
    for _d, s in all_copy:
        cb[CORRELATION_BUCKETS.get(s, "other")] += 1
    shared_b = set(mb) & set(cb)
    print("    buckets                 main {0}, trend {1}, shared {2}".format(
        len(mb), len(cb), len(shared_b)))

    # simultaneous exposure
    open_m = defaultdict(set)
    open_c = defaultdict(set)
    for tr in main_rep.trades:
        d0, d1 = tr.entry_time.date(), tr.exit_time.date()
        for d in days_m:
            if d0 <= d < d1:
                open_m[d].add(tr.symbol)
    for tr in trend_rep.trades:
        d0, d1 = tr.entry_time.date(), tr.exit_time.date()
        for d in days_m:
            if d0 <= d < d1:
                open_c[d].add(tr.symbol)
    sim = [len(open_m[d] & open_c[d]) for d in days_m]
    both_open = sum(1 for d in days_m if open_m[d] and open_c[d])
    print("    sessions both hold something  {0} ({1:.1%})".format(
        both_open, both_open / len(days_m)))
    print("    mean simultaneously-held SAME name  {0:.3f}".format(fmean(sim)))
    bucket_clash = sum(
        1 for d in days_m
        if {CORRELATION_BUCKETS.get(s, "other") for s in open_m[d]}
        & {CORRELATION_BUCKETS.get(s, "other") for s in open_c[d]})
    print("    sessions sharing a BUCKET           {0} ({1:.1%})".format(
        bucket_clash, bucket_clash / len(days_m)))

    # ---- 4. incremental information -------------------------------------
    print("\n" + "=" * 76)
    print("4. INCREMENTAL INFORMATION (item 7) - agreement states")
    print("=" * 76)
    print("  Candidate sets per session, then forward excess vs SPY of the")
    print("  names in each state. States defined before outcomes were seen.")
    main_c = defaultdict(set)
    for line in (REPO / "data" / "phase5" / "candidates-deep.jsonl"
                 ).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            main_c[date.fromisoformat(r["date"])].add(r["symbol"])
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

    states = defaultdict(list)
    for d in days_m:
        mc, cc = main_c.get(d, set()), copy_by_day.get(d, set())
        for s in mc | cc:
            st = ("BOTH" if s in mc and s in cc
                  else "MAIN_ONLY" if s in mc else "COPY_ONLY")
            row = {"date": d, "symbol": s, "state": st}
            ok = True
            for h in HORIZONS:
                a, b = fwd(s, d, h), sfwd(d, h)
                if a is None or b is None:
                    ok = False
                    break
                row[h] = a - b
            if ok:
                states[st].append(row)
    print("\n  {0:<12} {1:>7} {2:>11} {3:>11} {4:>11} {5:>8}".format(
        "state", "n", "exc 5s", "exc 10s", "exc 20s", "win@10"))
    inc = {}
    for st in ("BOTH", "MAIN_ONLY", "COPY_ONLY"):
        g = states.get(st, [])
        if not g:
            print("  {0:<12} {1:>7}".format(st, 0))
            continue
        inc[st] = {"n": len(g)}
        cells = []
        for h in HORIZONS:
            v = [r[h] for r in g]
            inc[st][h] = {"mean": fmean(v),
                          "win": sum(1 for x in v if x > 0) / len(v)}
            cells.append(fmean(v))
        print("  {0:<12} {1:>7} {2:>11.3%} {3:>11.3%} {4:>11.3%} "
              "{5:>8.1%}".format(st, len(g), *cells, inc[st][10]["win"]))
    if "BOTH" in inc and "MAIN_ONLY" in inc:
        print("\n  agreement premium @10s (BOTH - MAIN_ONLY): {0:+.3%}".format(
            inc["BOTH"][10]["mean"] - inc["MAIN_ONLY"][10]["mean"]))

    # day-collapsed, the honest unit
    print("\n  DAY-COLLAPSED (one observation per session, clustering removed)")
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

    # ---- 5. time split ---------------------------------------------------
    print("\n" + "=" * 76)
    print("5. TIME SPLIT - chronological thirds, declared beforehand")
    print("=" * 76)
    third = len(days_m) // 3
    cuts = (days_m[third], days_m[2 * third])
    print("  boundaries {0} and {1}".format(*cuts))

    def period(d):
        return "early" if d < cuts[0] else ("middle" if d < cuts[1] else "late")

    print("\n  annualised return by period")
    print("  {0:<8} {1:>12} {2:>12} {3:>12}".format(
        "period", "MAIN", "TREND", "SPY"))
    spy_r = {}
    for i, d in enumerate(spy_d):
        if i:
            spy_r[d] = spy_close[d] / spy_close[spy_d[i - 1]] - 1.0
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

    print("\n  agreement premium @10s by period (BOTH - MAIN_ONLY)")
    for p in ("early", "middle", "late"):
        b = [r[10] for r in states.get("BOTH", []) if period(r["date"]) == p]
        mo = [r[10] for r in states.get("MAIN_ONLY", [])
              if period(r["date"]) == p]
        if len(b) < 20 or len(mo) < 20:
            print("    {0:<8} n/a (BOTH n={1})".format(p, len(b)))
            continue
        print("    {0:<8} {1:+.3%}   (BOTH n={2}, MAIN_ONLY n={3})".format(
            p, fmean(b) - fmean(mo), len(b), len(mo)))

    # ---- 6. regime -------------------------------------------------------
    print("\n" + "=" * 76)
    print("6. REGIME (already-defined states, no new definition)")
    print("=" * 76)
    labels, _d, _g = build_signals(series)
    lab = labels["trend_dual_ma"]
    print("  {0:<14} {1:>8} {2:>12} {3:>12} {4:>12}".format(
        "state", "sessions", "MAIN ann", "TREND ann", "SPY ann"))
    for st in STATES:
        ds = [d for d in days_m if lab.get(d) == st]
        a = [ret_m[d] for d in ds if d in ret_m]
        b = [ret_t[d] for d in ds if d in ret_t]
        c = [spy_r[d] for d in ds if d in spy_r]
        if len(a) < 40:
            continue
        print("  {0:<14} {1:>8} {2:>12.2%} {3:>12.2%} {4:>12.2%}".format(
            st, len(ds), fmean(a) * TRADING_YEAR, fmean(b) * TRADING_YEAR,
            fmean(c) * TRADING_YEAR))

    out = REPO / "docs" / "phase5" / "copy-source-forensics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "FORENSIC_NON_PROMOTIONAL": True,
        "audit": [{"source": a, "provides": b, "usable": c}
                  for a, b, c in audit],
        "main": m, "trend": t, "spy_total": spy_total,
        "daily_return_correlation": rc,
        "entry_overlap": {"main": len(all_main), "trend": len(all_copy),
                          "same_symbol_same_day": len(both),
                          "shared_symbols": len(ms & cs),
                          "shared_buckets": len(shared_b),
                          "sessions_both_hold": both_open,
                          "sessions_sharing_bucket": bucket_clash},
        "agreement_states": inc, "day_collapsed": coll,
        "thirds": thirds,
        "note": "READ-ONLY. Not an experiment, not promotable.",
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
