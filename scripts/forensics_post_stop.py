"""Read-only forensics on post-stop behaviour. NOTHING IS REGISTERED HERE.

The observation under examination: 239 stop exits, and the stopped names
beat SPY by about +0.339% over the following 10 sessions. This asks
which explanation fits, not whether the stop is wrong.

THE SPLIT IS DECLARED HERE, BEFORE ANY NUMBER IS COMPUTED.
  Chronological thirds of the ELIGIBLE stop events ordered by exit date,
  equal COUNT (n/3 each, remainder to the last). Early / middle / late.
  Calendar years are reported separately as a finer, also-predetermined
  view. No other split is computed, and this one is not revisited.

THE REGIME DEFINITION IS DECLARED HERE, AND THERE IS ONLY ONE.
  SPY's close divided by its own 200-day simple moving average, minus 1,
  as of the PRIOR close t-1, ranked by EXPANDING percentile among every
  such reading from the start of the series through t-1. Bottom third
  unfavourable, middle third neutral, top third favourable. No other
  regime family is swept.

TWO REFERENCE POINTS, AND THEY ANSWER DIFFERENT QUESTIONS.
  FROM THE CLOSE of the exit session: "did the name go up afterwards?"
  This reproduces the original observation.
  FROM THE STOP FILL: "what would holding have been worth?" This is the
  actual counterfactual, because the fill is where the money left.
Both are reported and never conflated.

A STOCK RISING AFTER A STOP IS NOT PROOF THE STOP COST ANYTHING. The
capital did not vanish - it returned to cash under a 44% average
exposure, and holding would have consumed a 20%-per-name slot that
another entry might have used. The downside the stop avoided is
measured here too, because a rebound that follows a deeper fall is not
the same thing as a rebound that follows nothing.
"""

import glob
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from statistics import fmean, median, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.data import load_bars                  # noqa: E402
from event_aware_trader.indicators import average_true_range   # noqa: E402
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

HORIZONS = (1, 3, 5, 10, 20)
HEADLINE = 10                      # the horizon the observation was quoted at
SMA_DAYS, VOL_DAYS, MIN_READINGS = 200, 20, 252
BOOTSTRAP = 4000
random.seed(20260917)              # fixed so the report reproduces


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


def pct(values, p):
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def describe(values, label, width=26):
    if not values:
        print("  {0:<{1}} {2:>5}".format(label, width, 0))
        return
    print("  {0:<{1}} {2:>5} {3:>9.3%} {4:>9.3%} {5:>9.3%} {6:>9.3%} "
          "{7:>9.3%} {8:>8.1%}".format(
              label, width, len(values), fmean(values), median(values),
              pct(values, 25), pct(values, 75), pstdev(values),
              sum(1 for v in values if v > 0) / len(values)))


def header(width=26):
    print("  {0:<{1}} {2:>5} {3:>9} {4:>9} {5:>9} {6:>9} {7:>9} {8:>8}".format(
        "", width, "n", "mean", "median", "p25", "p75", "stdev", "win"))


def spy_context(spy):
    """date -> (sma_percentile, vol_percentile), both from the PRIOR close."""
    closes, sma_seen, vol_seen = [], [], []
    sma_rank, vol_rank = {}, {}
    for bar in spy:
        closes.append(bar.close)
        d = bar.timestamp.date()
        if len(closes) >= SMA_DAYS:
            gap = closes[-1] / (sum(closes[-SMA_DAYS:]) / SMA_DAYS) - 1.0
            sma_seen.append(gap)
            sma_rank[d] = (sum(1 for v in sma_seen if v <= gap) / len(sma_seen)
                           if len(sma_seen) >= MIN_READINGS else None)
        if len(closes) >= VOL_DAYS + 1:
            rets = [closes[j] / closes[j - 1] - 1.0
                    for j in range(len(closes) - VOL_DAYS, len(closes))]
            vol = pstdev(rets)
            vol_seen.append(vol)
            vol_rank[d] = (sum(1 for v in vol_seen if v <= vol) / len(vol_seen)
                           if len(vol_seen) >= MIN_READINGS else None)
    days = [b.timestamp.date() for b in spy]
    out = {}
    for i, day in enumerate(days):
        prior = days[i - 1] if i else None
        out[day] = (sma_rank.get(prior), vol_rank.get(prior))
    return out


def main():
    series = load()
    spy_bars = series["SPY"]
    print("decade: {0} symbols, SPY {1} -> {2}".format(
        len(series), spy_bars[0].timestamp.date(),
        spy_bars[-1].timestamp.date()), flush=True)

    report = production_report(series, conviction=conviction,
                               dataset="decade", purpose="diagnostic")
    scored = measure(report, "baseline")
    print("baseline: {0} trades, total {1:+.4%}\n".format(
        scored.trades, scored.total_return))

    dates = {s: [b.timestamp.date() for b in bs] for s, bs in series.items()}
    closes = {s: [b.close for b in bs] for s, bs in series.items()}
    index = {s: {d: i for i, d in enumerate(ds)} for s, ds in dates.items()}
    spy_d, spy_c, spy_i = dates["SPY"], closes["SPY"], index["SPY"]
    ctx = spy_context(spy_bars)

    stops = [t for t in report.trades if t.exit_reason == "stop"]
    print("=" * 74)
    print("DATA QUALITY")
    print("=" * 74)
    print("  total stop events                      {0}".format(len(stops)))

    rows, dropped = [], defaultdict(int)
    for t in stops:
        s, day = t.symbol, t.exit_time.date()
        if s not in index or day not in index[s]:
            dropped["exit date absent from the symbol series"] += 1
            continue
        if day not in spy_i:
            dropped["exit date absent from the SPY calendar"] += 1
            continue
        i, si = index[s][day], spy_i[day]
        if i + max(HORIZONS) >= len(closes[s]) or \
                si + max(HORIZONS) >= len(spy_c):
            dropped["fewer than 20 forward sessions available"] += 1
            continue
        bars_to_entry = [b for b in series[s]
                         if b.timestamp.date() <= t.entry_time.date()]
        atr = average_true_range(bars_to_entry[-60:]) if len(
            bars_to_entry) >= 30 else None
        sma_p, vol_p = ctx.get(day, (None, None))
        row = {
            "symbol": s, "exit_date": day.isoformat(), "year": day.year,
            "entry_date": t.entry_time.date().isoformat(),
            "qty": t.quantity, "entry_price": t.entry_price,
            "fill": t.exit_price, "close_at_exit": closes[s][i],
            "net_pnl": t.net_pnl, "r_multiple": t.r_multiple,
            "bars_held": t.bars_held,
            "stop_distance": ((t.entry_price - t.initial_stop) / t.entry_price
                              if t.initial_stop else None),
            "stop_atr": ((t.entry_price - t.initial_stop) / atr
                         if atr and t.initial_stop else None),
            "mfe": (t.highest_high / t.entry_price - 1.0
                    if t.highest_high else None),
            "conviction": shipped_conviction(bars_to_entry[-40:])
            if len(bars_to_entry) >= 40 else None,
            "sma_pct": sma_p, "vol_pct": vol_p,
            "fwd": {}, "fwd_from_fill": {}, "spy": {}, "worst": {},
            "align": {},
        }
        for h in HORIZONS:
            sym_end, spy_end = dates[s][i + h], spy_d[si + h]
            row["align"][h] = abs((sym_end - spy_end).days)
            row["fwd"][h] = closes[s][i + h] / closes[s][i] - 1.0
            row["fwd_from_fill"][h] = closes[s][i + h] / t.exit_price - 1.0
            row["spy"][h] = spy_c[si + h] / spy_c[si] - 1.0
            row["worst"][h] = (min(closes[s][i + 1:i + h + 1]) / t.exit_price
                               - 1.0)
        rows.append(row)

    print("  eligible stop events                   {0}".format(len(rows)))
    for why, n in sorted(dropped.items(), key=lambda kv: -kv[1]):
        print("    dropped - {0}: {1}".format(why, n))
    if not rows:
        print("nothing eligible.")
        return 2
    syms = {r["symbol"] for r in rows}
    print("  symbols contributing                   {0} of {1} in universe"
          .format(len(syms), len(series)))
    print("  exit dates span                        {0} -> {1}".format(
        min(r["exit_date"] for r in rows), max(r["exit_date"] for r in rows)))
    mis = [r["align"][HEADLINE] for r in rows]
    print("  calendar alignment, symbol vs SPY      max {0} days, mean {1:.3f}"
          .format(max(mis), fmean(mis)))
    print("  missing conviction / ATR               {0} / {1}".format(
        sum(1 for r in rows if r["conviction"] is None),
        sum(1 for r in rows if r["stop_atr"] is None)))
    print("  regime label unavailable (early)       {0}".format(
        sum(1 for r in rows if r["sma_pct"] is None)))

    # ---- 1. the headline, reproduced and extended -----------------------
    print("\n" + "=" * 74)
    print("FORWARD PERFORMANCE AFTER A STOP")
    print("=" * 74)
    print("\nA. FROM THE EXIT SESSION'S CLOSE - 'did the name go up?'")
    print("   (this is the reference the +0.339% observation used)")
    header()
    for h in HORIZONS:
        describe([r["fwd"][h] for r in rows], "raw, {0} sessions".format(h))
    print()
    header()
    excess = {}
    for h in HORIZONS:
        excess[h] = [r["fwd"][h] - r["spy"][h] for r in rows]
        describe(excess[h], "EXCESS vs SPY, {0}s".format(h))
    print("\n   percentiles of the {0}-session excess:".format(HEADLINE))
    print("     " + "  ".join("p{0} {1:+.3%}".format(p, pct(excess[HEADLINE], p))
                              for p in (5, 25, 50, 75, 95)))

    print("\nB. FROM THE STOP FILL - 'what would holding have been worth?'")
    print("   (the actual counterfactual: the fill is where money left)")
    header()
    for h in HORIZONS:
        describe([r["fwd_from_fill"][h] for r in rows],
                 "raw from fill, {0}s".format(h))
    header()
    for h in HORIZONS:
        describe([r["fwd_from_fill"][h] - r["spy"][h] for r in rows],
                 "EXCESS from fill, {0}s".format(h))

    print("\nC. THE DOWNSIDE THE STOP AVOIDED - worst close in the window,")
    print("   measured from the fill. Holding means bearing this.")
    header()
    for h in HORIZONS:
        describe([r["worst"][h] for r in rows], "worst dip, {0}s".format(h))
    for h in (10, 20):
        w = [r["worst"][h] for r in rows]
        print("   at {0} sessions: {1:.1%} of positions traded at least 5% "
              "below the fill".format(
                  h, sum(1 for v in w if v <= -0.05) / len(w)))

    # ---- 2. dollars ------------------------------------------------------
    print("\n" + "=" * 74)
    print("AGGREGATE DOLLAR IMPACT (from the fill; upper bound - see note)")
    print("=" * 74)
    print("  {0:>4} {1:>15} {2:>15} {3:>15}".format(
        "h", "hold instead $", "same $ in SPY", "difference"))
    dollars = {}
    for h in HORIZONS:
        hold = sum(r["qty"] * (r["close_at_exit"] * 0 + 0) for r in rows)
        hold = sum(r["qty"] * r["fill"] * r["fwd_from_fill"][h] for r in rows)
        spy_alt = sum(r["qty"] * r["fill"] * r["spy"][h] for r in rows)
        dollars[h] = {"hold": hold, "spy": spy_alt, "diff": hold - spy_alt}
        print("  {0:>4} {1:>15,.0f} {2:>15,.0f} {3:>15,.0f}".format(
            h, hold, spy_alt, hold - spy_alt))
    print("\n  NOTE. This is an UPPER BOUND on what holding could have added.")
    print("  The freed capital did not vanish: average exposure is 44%, so it")
    print("  returned to cash earning 0%, and holding would have occupied a")
    print("  20%-per-name slot that a later entry might have used. Neither")
    print("  effect is priced here. Against the {0:,.0f} of realised stop "
          "losses,".format(sum(r["net_pnl"] for r in rows)))
    print("  the {0}-session difference is {1:,.0f}.".format(
        HEADLINE, dollars[HEADLINE]["diff"]))

    # ---- 3. time stability ----------------------------------------------
    print("\n" + "=" * 74)
    print("TIME STABILITY - chronological thirds, declared before computing")
    print("=" * 74)
    ordered = sorted(rows, key=lambda r: r["exit_date"])
    third = len(ordered) // 3
    parts = [("early", ordered[:third]), ("middle", ordered[third:2 * third]),
             ("late", ordered[2 * third:])]
    print("  {0:<8} {1:>5} {2:<25} {3:>10} {4:>10} {5:>8}".format(
        "period", "n", "dates", "mean exc", "median", "win"))
    thirds_out = []
    for name, part in parts:
        e = [r["fwd"][HEADLINE] - r["spy"][HEADLINE] for r in part]
        thirds_out.append({"period": name, "n": len(part), "mean": fmean(e),
                           "median": median(e),
                           "win": sum(1 for v in e if v > 0) / len(e),
                           "from": part[0]["exit_date"],
                           "to": part[-1]["exit_date"]})
        print("  {0:<8} {1:>5} {2:<25} {3:>+10.3%} {4:>+10.3%} {5:>8.1%}".format(
            name, len(part),
            "{0} -> {1}".format(part[0]["exit_date"], part[-1]["exit_date"]),
            fmean(e), median(e), sum(1 for v in e if v > 0) / len(e)))
    signs = {t["mean"] > 0 for t in thirds_out}
    print("\n  all three thirds same sign: {0}".format(len(signs) == 1))

    # ---- 4. year concentration ------------------------------------------
    print("\n" + "=" * 74)
    print("YEAR CONCENTRATION")
    print("=" * 74)
    by_year = defaultdict(list)
    for r in rows:
        by_year[r["year"]].append(r)
    total_excess = sum(excess[HEADLINE])
    print("  {0:>6} {1:>5} {2:>11} {3:>11} {4:>13} {5:>11}".format(
        "year", "n", "mean exc", "median", "sum excess", "share"))
    year_rows = []
    for y in sorted(by_year):
        e = [r["fwd"][HEADLINE] - r["spy"][HEADLINE] for r in by_year[y]]
        year_rows.append({"year": y, "n": len(e), "mean": fmean(e),
                          "sum": sum(e),
                          "share": sum(e) / total_excess if total_excess else 0})
        print("  {0:>6} {1:>5} {2:>+11.3%} {3:>+11.3%} {4:>+13.3%} "
              "{5:>11.1%}".format(y, len(e), fmean(e), median(e), sum(e),
                                  sum(e) / total_excess if total_excess else 0))
    strongest = max(year_rows, key=lambda r: r["sum"])
    rest = [r["fwd"][HEADLINE] - r["spy"][HEADLINE] for r in rows
            if r["year"] != strongest["year"]]
    print("\n  strongest year {0} contributes {1:.1%} of the aggregate".format(
        strongest["year"], strongest["share"]))
    print("  removing it:  n {0}, mean {1:+.4%}  (all years {2:+.4%})".format(
        len(rest), fmean(rest), fmean(excess[HEADLINE])))

    # ---- 5. symbol concentration ----------------------------------------
    print("\n" + "=" * 74)
    print("SYMBOL CONCENTRATION")
    print("=" * 74)
    by_sym = defaultdict(list)
    for r in rows:
        by_sym[r["symbol"]].append(r["fwd"][HEADLINE] - r["spy"][HEADLINE])
    contrib = sorted(((s, sum(v), len(v)) for s, v in by_sym.items()),
                     key=lambda x: -x[1])
    print("  symbols contributing: {0}; events per symbol max {1}".format(
        len(by_sym), max(len(v) for v in by_sym.values())))
    print("\n  ten largest positive contributors:")
    print("  {0:<8} {1:>4} {2:>13} {3:>11}".format("sym", "n", "sum excess",
                                                   "share"))
    for s, tot, n in contrib[:10]:
        print("  {0:<8} {1:>4} {2:>+13.3%} {3:>11.1%}".format(
            s, n, tot, tot / total_excess if total_excess else 0))
    print("\n  removing the largest contributors, in order:")
    print("  {0:<26} {1:>5} {2:>11}".format("", "n", "mean excess"))
    removal = []
    for k in (0, 1, 3, 5, 10):
        drop = {s for s, _t, _n in contrib[:k]}
        kept = [r["fwd"][HEADLINE] - r["spy"][HEADLINE] for r in rows
                if r["symbol"] not in drop]
        removal.append({"removed": k, "n": len(kept), "mean": fmean(kept)})
        print("  {0:<26} {1:>5} {2:>+11.4%}".format(
            "top {0} symbols removed".format(k) if k else "all symbols",
            len(kept), fmean(kept)))
    loo = []
    for s in by_sym:
        kept = [r["fwd"][HEADLINE] - r["spy"][HEADLINE] for r in rows
                if r["symbol"] != s]
        loo.append((s, fmean(kept)))
    loo.sort(key=lambda x: x[1])
    print("\n  leave-one-symbol-out, {0} refits: mean ranges {1:+.4%} "
          "(drop {2}) to {3:+.4%} (drop {4})".format(
              len(loo), loo[0][1], loo[0][0], loo[-1][1], loo[-1][0]))
    print("  leave-one-out means all positive: {0}".format(
        all(v > 0 for _s, v in loo)))

    # ---- 6. regime -------------------------------------------------------
    print("\n" + "=" * 74)
    print("MARKET REGIME AT THE STOP - one definition, point-in-time")
    print("=" * 74)
    print("  SPY / its own 200-day SMA - 1, expanding-percentile terciles,")
    print("  read from the PRIOR close. No future information.")
    buckets = defaultdict(list)
    for r in rows:
        p = r["sma_pct"]
        if p is None:
            buckets["unlabelled (pre-252)"].append(
                r["fwd"][HEADLINE] - r["spy"][HEADLINE])
        else:
            name = ("unfavourable" if p < 1 / 3 else
                    "neutral" if p < 2 / 3 else "favourable")
            buckets[name].append(r["fwd"][HEADLINE] - r["spy"][HEADLINE])
    header()
    for name in ("unfavourable", "neutral", "favourable",
                 "unlabelled (pre-252)"):
        if name in buckets:
            describe(buckets[name], name)

    print("\n  SPY 20-day realised-volatility terciles, same construction:")
    vbuckets = defaultdict(list)
    for r in rows:
        p = r["vol_pct"]
        name = ("unlabelled" if p is None else
                "calm" if p < 1 / 3 else
                "middling" if p < 2 / 3 else "turbulent")
        vbuckets[name].append(r["fwd"][HEADLINE] - r["spy"][HEADLINE])
    header()
    for name in ("calm", "middling", "turbulent", "unlabelled"):
        if name in vbuckets:
            describe(vbuckets[name], name)

    # ---- 7. trade characteristics ---------------------------------------
    print("\n" + "=" * 74)
    print("TRADE CHARACTERISTICS AT THE STOP - attribution only")
    print("=" * 74)

    def split_by(field, label, cuts=(1 / 3, 2 / 3)):
        vals = sorted(r[field] for r in rows if r.get(field) is not None)
        if len(vals) < 30:
            print("\n  {0}: too few values ({1})".format(label, len(vals)))
            return
        lo, hi = pct(vals, cuts[0] * 100), pct(vals, cuts[1] * 100)
        g = defaultdict(list)
        for r in rows:
            v = r.get(field)
            if v is None:
                continue
            k = ("low" if v < lo else "mid" if v < hi else "high")
            g[k].append(r["fwd"][HEADLINE] - r["spy"][HEADLINE])
        print("\n  {0}  (terciles: <{1:.4g}, <{2:.4g}, rest)".format(
            label, lo, hi))
        header()
        for k in ("low", "mid", "high"):
            if k in g:
                describe(g[k], k)

    split_by("stop_distance", "stop distance as a fraction of entry price")
    split_by("stop_atr", "stop distance in ATRs at entry")
    split_by("bars_held", "sessions held before the stop")
    split_by("conviction", "entry conviction (recomputed point-in-time)")
    split_by("mfe", "peak unrealised gain before the stop (MFE)")

    print("\n  had the position ever been in profit before stopping?")
    header()
    for name, sel in (("never above entry", lambda r: (r["mfe"] or 0) <= 0.0),
                      ("was up < 2%", lambda r: 0.0 < (r["mfe"] or 0) <= 0.02),
                      ("was up >= 2%", lambda r: (r["mfe"] or 0) > 0.02)):
        describe([r["fwd"][HEADLINE] - r["spy"][HEADLINE]
                  for r in rows if sel(r)], name)

    # ---- 8. overlap and significance ------------------------------------
    print("\n" + "=" * 74)
    print("OVERLAPPING WINDOWS - can these be treated as independent?")
    print("=" * 74)
    for h in (10, 20):
        spans = []
        for r in rows:
            si = spy_i[__import__("datetime").date.fromisoformat(r["exit_date"])]
            spans.append(set(range(si, si + h + 1)))
        covered = set().union(*spans)
        counts = defaultdict(int)
        for sp in spans:
            for d in sp:
                counts[d] += 1
        print("  {0}-session windows: {1} events x {2} sessions = {3} "
              "event-sessions".format(h, len(rows), h + 1, len(rows) * (h + 1)))
        print("     distinct calendar sessions covered   {0}".format(
            len(covered)))
        print("     overlap ratio                        {0:.2f}x".format(
            len(rows) * (h + 1) / len(covered)))
        print("     busiest session carries              {0} open windows"
              .format(max(counts.values())))
        same_day = defaultdict(int)
        for r in rows:
            same_day[r["exit_date"]] += 1
        print("     stops sharing an exit date           {0} of {1} events"
              .format(sum(v for v in same_day.values() if v > 1), len(rows)))

    e = excess[HEADLINE]
    naive_se = pstdev(e) / (len(e) ** 0.5)
    print("\n  {0}-session excess: mean {1:+.4%}, naive SE {2:.4%}, "
          "naive t {3:.2f}".format(HEADLINE, fmean(e), naive_se,
                                   fmean(e) / naive_se if naive_se else 0))
    print("  The naive figure assumes independence, which the overlap above")
    print("  contradicts. A monthly block bootstrap respects the clustering:")
    by_month = defaultdict(list)
    for r in rows:
        by_month[r["exit_date"][:7]].append(
            r["fwd"][HEADLINE] - r["spy"][HEADLINE])
    months = list(by_month)
    boots = []
    for _ in range(BOOTSTRAP):
        pick = [random.choice(months) for _ in months]
        vals = [v for m in pick for v in by_month[m]]
        if vals:
            boots.append(fmean(vals))
    lo, hi = pct(boots, 2.5), pct(boots, 97.5)
    print("     {0} months resampled, {1} iterations".format(
        len(months), BOOTSTRAP))
    print("     95% CI on the mean excess   [{0:+.4%}, {1:+.4%}]".format(lo, hi))
    print("     share of resamples above 0  {0:.1%}".format(
        sum(1 for b in boots if b > 0) / len(boots)))
    print("     CI excludes zero            {0}".format(lo > 0 or hi < 0))

    out = REPO / "docs" / "phase5" / "post-stop-forensics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "total_stops": len(stops), "eligible": len(rows),
        "dropped": dict(dropped), "symbols": len(syms),
        "headline_horizon": HEADLINE,
        "excess_by_horizon": {str(h): {
            "n": len(rows), "mean": fmean([r["fwd"][h] - r["spy"][h]
                                           for r in rows]),
            "median": median([r["fwd"][h] - r["spy"][h] for r in rows]),
            "win": sum(1 for r in rows if r["fwd"][h] > r["spy"][h]) / len(rows),
        } for h in HORIZONS},
        "thirds": thirds_out, "years": year_rows,
        "strongest_year": strongest,
        "mean_excluding_strongest_year": fmean(rest),
        "symbol_removal": removal,
        "leave_one_out_min": {"symbol": loo[0][0], "mean": loo[0][1]},
        "leave_one_out_max": {"symbol": loo[-1][0], "mean": loo[-1][1]},
        "leave_one_out_all_positive": all(v > 0 for _s, v in loo),
        "dollars": dollars,
        "bootstrap": {"months": len(months), "iterations": BOOTSTRAP,
                      "ci_low": lo, "ci_high": hi,
                      "share_above_zero": sum(1 for b in boots if b > 0)
                      / len(boots)},
        "naive_t": fmean(e) / naive_se if naive_se else None,
        "note": "read-only forensics; nothing registered, nothing changed",
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
