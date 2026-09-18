"""FORENSIC_NON_PROMOTIONAL. Entry-signal breadth: the opportunity funnel.

READ-ONLY. No production file is edited, no threshold is moved, nothing
is registered, nothing is promotable.

THE QUESTION. The strategy has no entry on roughly half of all
sessions. Is the entry signal correctly finding little worth buying, or
is the qualification boundary discarding useful opportunity?

WHAT THE BOUNDARY ACTUALLY IS. `conviction()` is NOT a gate - it is a
sizing multiplier in [0.5, 1.5] driven by drawdown from the 20-day
high, applied AFTER a name already qualifies. The qualification
boundary is the filter set inside `mean_reversion.evaluate`, and the
one that does the discarding is `rsi_entry = 35.0`. So "just below the
threshold" means RSI just ABOVE 35, and that is what is measured.

FIDELITY. The real `evaluate` is called on every symbol-session, with
the same 400-bar window the research harness uses. Nothing is
reimplemented, so the funnel cannot drift from production.

DECLARED BEFORE ANY OUTCOME IS EXAMINED
  RSI bands: <=35 (qualifies), (35,37.5], (37.5,40], (40,45], (45,50],
             (50,60], >60
  Time split: chronological thirds of the sessions, equal count.
  Forward horizons: 5, 10, 20 sessions, raw and excess vs SPY.
Nothing below re-chooses any of these.

A STOCK RISING AFTER BEING REJECTED IS NOT PROOF THE REJECTION WAS
WRONG. Forward returns here are measurement of what happened; they are
never inputs to a decision and can never become features.
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
from event_aware_trader.mean_reversion import (                 # noqa: E402
    MeanReversionConfig, conviction as shipped_conviction, evaluate)
from event_aware_trader.phase5.metrics import measure          # noqa: E402
from event_aware_trader.research import production_report      # noqa: E402
from event_aware_trader.strategy import CORRELATION_BUCKETS     # noqa: E402

from forensics_regime import build_signals, load, STATES        # noqa: E402

_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-400:], c)
_conv = {}

CFG = MeanReversionConfig()
WINDOW = 400
HORIZONS = (5, 10, 20)
BANDS = [("<=35 QUALIFIES", -1e9, 35.0), ("(35,37.5]", 35.0, 37.5),
         ("(37.5,40]", 37.5, 40.0), ("(40,45]", 40.0, 45.0),
         ("(45,50]", 45.0, 50.0), ("(50,60]", 50.0, 60.0),
         (">60", 60.0, 1e9)]
#: The pipeline, in the order `evaluate` tests it.
STAGES = ("history", "price", "liquidity", "trend_200d", "rsi_35",
          "atr_ceiling", "stop_positive")


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def band_of(r):
    for name, lo, hi in BANDS:
        if lo < r <= hi:
            return name
    return BANDS[0][0]


def pct(values, p):
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def classify(sig, bars_len):
    """Which stage killed this name, in pipeline order. None = survived."""
    if bars_len < CFG.minimum_history:
        return "history"
    joined = " | ".join(sig.reasons)
    if "Price below" in joined:
        return "price"
    if "dollar volume" in joined:
        return "liquidity"
    if "day average" in joined:
        return "trend_200d"
    if "RSI" in joined:
        return "rsi_35"
    if "ATR" in joined:
        return "atr_ceiling"
    if "stop" in joined:
        return "stop_positive"
    return None


def main():
    series = load()
    spy_bars = series["SPY"]
    print("decade: {0} symbols".format(len(series)), flush=True)
    report = production_report(series, conviction=conviction,
                               dataset="decade", purpose="diagnostic")
    scored = measure(report, "baseline").as_dict()
    print("baseline: {0} trades, total {1:+.4%}, exposure {2:.2%}\n".format(
        scored["trades"], scored["total_return"], scored["exposure"]),
        flush=True)

    dates = {s: [b.timestamp.date() for b in bs] for s, bs in series.items()}
    closes = {s: [b.close for b in bs] for s, bs in series.items()}
    index = {s: {d: i for i, d in enumerate(ds)} for s, ds in dates.items()}
    spy_d, spy_c = dates["SPY"], closes["SPY"]
    spy_i = index["SPY"]
    sessions = spy_d

    taken_by_day = defaultdict(set)
    for t in report.trades:
        taken_by_day[t.entry_time.date()].add(t.symbol)

    def fwd(sym, i, h):
        if i + h >= len(closes[sym]):
            return None
        return closes[sym][i + h] / closes[sym][i] - 1.0

    def spy_fwd(day, h):
        i = spy_i.get(day)
        if i is None or i + h >= len(spy_c):
            return None
        return spy_c[i + h] / spy_c[i] - 1.0

    # ---- one pass over every symbol-session ----------------------------
    print("reconstructing the funnel over {0} sessions x {1} symbols..."
          .format(len(sessions), len(series)), flush=True)
    per_session = {}
    eligible = []          # passed everything except possibly RSI, rsi<=60
    verify = []
    for n, day in enumerate(sessions):
        if n % 400 == 0:
            print("  {0}/{1}".format(n, len(sessions)), flush=True)
        stage_fail = defaultdict(int)
        survivors, near = [], []
        considered = 0
        for sym, bars in series.items():
            i = index[sym].get(day)
            if i is None:
                continue
            considered += 1
            window = bars[max(0, i - WINDOW + 1):i + 1]
            sig = evaluate(sym, window, CFG)
            killed = classify(sig, len(window))
            if killed:
                stage_fail[killed] += 1
            if sig.action == "BUY":
                survivors.append((sym, i, sig))
            # eligible-but-for-RSI: everything else passed
            if killed == "rsi_35" and sig.rsi is not None and sig.rsi <= 60.0:
                near.append((sym, i, sig))
            if (killed is None or killed == "rsi_35") and sig.rsi is not None \
                    and sig.rsi <= 60.0:
                sfwd = {h: spy_fwd(day, h) for h in HORIZONS}
                if all(v is not None for v in sfwd.values()):
                    f = {h: fwd(sym, i, h) for h in HORIZONS}
                    if all(v is not None for v in f.values()):
                        eligible.append({
                            "date": day.isoformat(), "symbol": sym,
                            "rsi": sig.rsi, "band": band_of(sig.rsi),
                            "qualified": killed is None,
                            "atr_frac": sig.atr_fraction,
                            "bucket": CORRELATION_BUCKETS.get(sym, "other"),
                            "fwd": f, "spy": sfwd,
                        })
        if len(verify) < 40 and survivors:
            s, i, sig = survivors[0]
            verify.append((s, day, sig.action))
        conv = sorted(
            ((shipped_conviction(series[s][max(0, i - 39):i + 1]), s)
             for s, i, _g in survivors), reverse=True)
        per_session[day] = {
            "considered": considered, "fail": dict(stage_fail),
            "candidates": len(survivors),
            "near_misses": len(near),
            "best_conviction": conv[0][0] if conv else None,
            "second_conviction": conv[1][0] if len(conv) > 1 else None,
            "entries": len(taken_by_day.get(day, set())),
            "best_near_rsi": min((g.rsi for _s, _i, g in near), default=None),
        }
    print("  done", flush=True)

    # ---- 1. the funnel ---------------------------------------------------
    print("\n" + "=" * 76)
    print("1. OPPORTUNITY FUNNEL - pipeline order, as `evaluate` tests it")
    print("=" * 76)
    tot = sum(v["considered"] for v in per_session.values())
    agg = defaultdict(int)
    for v in per_session.values():
        for k, c in v["fail"].items():
            agg[k] += c
    print("  symbol-sessions considered: {0:,}".format(tot))
    print("\n  {0:<16} {1:>14} {2:>9} {3:>14} {4:>9}".format(
        "stage", "killed here", "of total", "surviving", "survive%"))
    alive = tot
    funnel = []
    for st in STAGES:
        k = agg.get(st, 0)
        alive -= k
        funnel.append({"stage": st, "killed": k, "surviving": alive})
        print("  {0:<16} {1:>14,} {2:>9.2%} {3:>14,} {4:>9.2%}".format(
            st, k, k / tot, alive, alive / tot))
    print("\n  final candidates: {0:,} ({1:.3%} of symbol-sessions)".format(
        alive, alive / tot))
    print("  entries actually taken: {0:,}".format(
        sum(v["entries"] for v in per_session.values())))

    print("\n  per session:")
    cands = [v["candidates"] for v in per_session.values()]
    print("    sessions                      {0:,}".format(len(per_session)))
    print("    mean candidates per session   {0:.2f}".format(fmean(cands)))
    print("    median                        {0:.0f}".format(median(cands)))
    print("    sessions with ZERO candidates {0:,} ({1:.1%})".format(
        sum(1 for c in cands if c == 0),
        sum(1 for c in cands if c == 0) / len(cands)))

    # ---- 2. why was there no entry? -------------------------------------
    print("\n" + "=" * 76)
    print("2. NO-TRADE SESSIONS - signal or portfolio?")
    print("=" * 76)
    no_entry = [d for d, v in per_session.items() if v["entries"] == 0]
    empty = [d for d in no_entry if per_session[d]["candidates"] == 0]
    blocked = [d for d in no_entry if per_session[d]["candidates"] > 0]
    print("  sessions                                     {0:,}".format(
        len(per_session)))
    print("  sessions with at least one entry             {0:,} ({1:.1%})"
          .format(len(per_session) - len(no_entry),
                  1 - len(no_entry) / len(per_session)))
    print("  sessions with NO entry                       {0:,} ({1:.1%})"
          .format(len(no_entry), len(no_entry) / len(per_session)))
    print("    ...because the SIGNAL produced nothing     {0:,} ({1:.1%} of"
          " all sessions)".format(len(empty), len(empty) / len(per_session)))
    print("    ...because PORTFOLIO RULES blocked it      {0:,} ({1:.1%} of"
          " all sessions)".format(len(blocked),
                                  len(blocked) / len(per_session)))
    if blocked:
        print("       candidates available on those days: mean {0:.2f}, "
              "max {1}".format(
                  fmean([per_session[d]["candidates"] for d in blocked]),
                  max(per_session[d]["candidates"] for d in blocked)))

    print("\n  THE NEAREST MISS on signal-empty sessions")
    print("  (lowest RSI among names that passed price, liquidity, trend and")
    print("  ATR and failed ONLY the RSI <= 35 test)")
    nm = [per_session[d]["best_near_rsi"] for d in empty
          if per_session[d]["best_near_rsi"] is not None]
    print("    sessions with any near miss   {0:,} of {1:,}".format(
        len(nm), len(empty)))
    print("    nearest-miss RSI: mean {0:.2f}  median {1:.2f}".format(
        fmean(nm), median(nm)))
    for p in (5, 25, 50, 75, 95):
        print("      p{0:<3} {1:.2f}".format(p, pct(nm, p)))
    for edge in (36.0, 37.5, 40.0, 45.0):
        print("    nearest miss within {0:.1f} RSI of the gate: {1:,} "
              "({2:.1%} of signal-empty sessions)".format(
                  edge, sum(1 for r in nm if r <= edge),
                  sum(1 for r in nm if r <= edge) / len(empty)))

    # ---- 3. the crux: forward outcome by RSI band -----------------------
    print("\n" + "=" * 76)
    print("3. FORWARD OUTCOME BY RSI BAND - the crux")
    print("=" * 76)
    print("  Population: symbol-sessions passing price, liquidity, trend and")
    print("  ATR. Only the RSI test separates them. Bands declared in the")
    print("  docstring before any outcome was examined.")
    by_band = defaultdict(list)
    for e in eligible:
        by_band[e["band"]].append(e)
    print("\n  observations: {0:,}".format(len(eligible)))
    band_out = {}
    for h in HORIZONS:
        print("\n  EXCESS vs SPY over {0} sessions".format(h))
        print("  {0:<16} {1:>9} {2:>10} {3:>10} {4:>10} {5:>10} {6:>8}".format(
            "band", "n", "mean", "median", "p25", "p75", "win"))
        for name, _lo, _hi in BANDS:
            g = by_band.get(name, [])
            if not g:
                continue
            x = [e["fwd"][h] - e["spy"][h] for e in g]
            band_out.setdefault(name, {})[h] = {
                "n": len(x), "mean": fmean(x), "median": median(x),
                "win": sum(1 for v in x if v > 0) / len(x)}
            print("  {0:<16} {1:>9,} {2:>10.3%} {3:>10.3%} {4:>10.3%} "
                  "{5:>10.3%} {6:>8.1%}".format(
                      name, len(x), fmean(x), median(x), pct(x, 25),
                      pct(x, 75), sum(1 for v in x if v > 0) / len(x)))

    print("\n  RAW forward return by band (for reference; the excess above")
    print("  is the comparison that counts)")
    print("  {0:<16} {1:>9} {2:>12} {3:>12} {4:>12}".format(
        "band", "n", "raw 5s", "raw 10s", "raw 20s"))
    for name, _lo, _hi in BANDS:
        g = by_band.get(name, [])
        if not g:
            continue
        print("  {0:<16} {1:>9,} {2:>12.3%} {3:>12.3%} {4:>12.3%}".format(
            name, len(g), *[fmean([e["fwd"][h] for e in g])
                            for h in HORIZONS]))

    # ---- 4. time split ---------------------------------------------------
    print("\n" + "=" * 76)
    print("4. TIME SPLIT - chronological thirds, declared beforehand")
    print("=" * 76)
    third = len(sessions) // 3
    cuts = (sessions[third].isoformat(), sessions[2 * third].isoformat())
    print("  boundaries: {0} and {1}".format(*cuts))

    def period(dstr):
        return "early" if dstr < cuts[0] else (
            "middle" if dstr < cuts[1] else "late")

    print("\n  10-session excess vs SPY, by band and period")
    print("  {0:<16} {1:>18} {2:>18} {3:>18}".format(
        "band", "early", "middle", "late"))
    split_out = {}
    for name, _lo, _hi in BANDS[:5]:
        g = by_band.get(name, [])
        if not g:
            continue
        cells, row = [], {}
        for p in ("early", "middle", "late"):
            x = [e["fwd"][10] - e["spy"][10] for e in g
                 if period(e["date"]) == p]
            if len(x) < 50:
                cells.append("n/a")
                continue
            row[p] = {"n": len(x), "mean": fmean(x)}
            cells.append("{0:+.3%} (n={1:,})".format(fmean(x), len(x)))
        split_out[name] = row
        print("  {0:<16} {1:>18} {2:>18} {3:>18}".format(name, *cells))

    print("\n  signal-empty session rate, by period")
    print("  {0:<10} {1:>10} {2:>14} {3:>16}".format(
        "period", "sessions", "signal-empty", "mean candidates"))
    for p in ("early", "middle", "late"):
        ds = [d for d in sessions if period(d.isoformat()) == p]
        e = [d for d in ds if per_session[d]["candidates"] == 0]
        print("  {0:<10} {1:>10,} {2:>14} {3:>16.2f}".format(
            p, len(ds), "{0:,} ({1:.1%})".format(len(e), len(e) / len(ds)),
            fmean([per_session[d]["candidates"] for d in ds])))

    # ---- 5. regime, using ONLY already-defined states -------------------
    print("\n" + "=" * 76)
    print("5. ALREADY-DEFINED MARKET STATES (no new regime is introduced)")
    print("=" * 76)
    labels, _days, _diag = build_signals(series)
    lab = labels["trend_dual_ma"]
    print("  {0:<14} {1:>9} {2:>14} {3:>16} {4:>14}".format(
        "state", "sessions", "signal-empty", "mean candidates",
        "(35,40] exc 10s"))
    for st in STATES:
        ds = [d for d in sessions if lab.get(d) == st]
        if not ds:
            continue
        e = [d for d in ds if per_session[d]["candidates"] == 0]
        dset = {d.isoformat() for d in ds}
        near_g = [x for x in eligible
                  if x["band"] in ("(35,37.5]", "(37.5,40]")
                  and x["date"] in dset]
        exc = [x["fwd"][10] - x["spy"][10] for x in near_g]
        print("  {0:<14} {1:>9,} {2:>14} {3:>16.2f} {4:>14}".format(
            st, len(ds), "{0:.1%}".format(len(e) / len(ds)),
            fmean([per_session[d]["candidates"] for d in ds]),
            "{0:+.3%}".format(fmean(exc)) if exc else "n/a"))

    # ---- 6. the counterfactual ------------------------------------------
    print("\n" + "=" * 76)
    print("6. COUNTERFACTUAL - take the single nearest miss on each")
    print("   signal-empty session. DESCRIPTIVE ONLY, not a backtest.")
    print("=" * 76)
    best = {}
    for e in eligible:
        d = e["date"]
        if e["qualified"]:
            continue
        if d not in best or e["rsi"] < best[d]["rsi"]:
            best[d] = e
    empty_set = {d.isoformat() for d in empty}
    picks = [v for k, v in best.items() if k in empty_set]
    print("  signal-empty sessions with a usable nearest miss: {0:,}".format(
        len(picks)))
    print("  {0:>4} {1:>9} {2:>12} {3:>12} {4:>10}".format(
        "h", "n", "raw", "excess", "win"))
    cf = {}
    for h in HORIZONS:
        x = [p["fwd"][h] - p["spy"][h] for p in picks]
        r = [p["fwd"][h] for p in picks]
        cf[h] = {"n": len(x), "raw": fmean(r), "excess": fmean(x),
                 "win": sum(1 for v in x if v > 0) / len(x)}
        print("  {0:>4} {1:>9,} {2:>12.3%} {3:>12.3%} {4:>10.1%}".format(
            h, len(x), fmean(r), fmean(x),
            sum(1 for v in x if v > 0) / len(x)))
    print("\n  mean RSI of the pick: {0:.2f}".format(
        fmean([p["rsi"] for p in picks])))
    qual = [e for e in eligible if e["qualified"]]
    print("  for comparison, ALL qualifying signals (RSI<=35):")
    print("  {0:>4} {1:>9} {2:>12} {3:>12} {4:>10}".format(
        "h", "n", "raw", "excess", "win"))
    for h in HORIZONS:
        x = [e["fwd"][h] - e["spy"][h] for e in qual]
        print("  {0:>4} {1:>9,} {2:>12.3%} {3:>12.3%} {4:>10.1%}".format(
            h, len(x), fmean([e["fwd"][h] for e in qual]), fmean(x),
            sum(1 for v in x if v > 0) / len(x)))

    obs = REPO / "docs" / "phase5" / "breadth-observations.json"
    obs.parent.mkdir(parents=True, exist_ok=True)
    obs.write_text(json.dumps({
        "FORENSIC_NON_PROMOTIONAL": True,
        "note": "one row per symbol-session passing every filter except "
                "possibly RSI, with RSI <= 60. Forward returns are "
                "MEASUREMENT and may never become features.",
        "observations": [
            {"date": e["date"], "symbol": e["symbol"], "rsi": e["rsi"],
             "band": e["band"], "qualified": e["qualified"],
             "fwd": {str(h): e["fwd"][h] for h in HORIZONS},
             "spy": {str(h): e["spy"][h] for h in HORIZONS}}
            for e in eligible],
    }, separators=(",", ":"), default=str), encoding="utf-8")
    print("wrote {0} ({1:,} rows)".format(obs.relative_to(REPO),
                                          len(eligible)))

    out = REPO / "docs" / "phase5" / "breadth-forensics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "FORENSIC_NON_PROMOTIONAL": True,
        "baseline": scored, "symbol_sessions": tot, "funnel": funnel,
        "sessions": len(per_session),
        "sessions_no_entry": len(no_entry),
        "sessions_signal_empty": len(empty),
        "sessions_portfolio_blocked": len(blocked),
        "nearest_miss_rsi": {"mean": fmean(nm), "median": median(nm),
                             "p25": pct(nm, 25), "p75": pct(nm, 75)},
        "bands": band_out, "time_split": {"cuts": cuts, "bands": split_out},
        "counterfactual": cf,
        "qualifying_excess": {str(h): fmean([e["fwd"][h] - e["spy"][h]
                                             for e in qual])
                              for h in HORIZONS},
        "note": "READ-ONLY. Not an experiment. No threshold moved.",
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
