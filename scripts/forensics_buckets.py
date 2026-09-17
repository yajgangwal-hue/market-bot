"""FORENSIC, NON-PROMOTIONAL. The correlation-bucket constraint.

READ-ONLY. Nothing registered, nothing tuned, no production file
touched. No configuration here is a candidate for anything.

THE QUESTION. The bucket rule blocks 59.5% of all candidates. Is it
refusing valuable opportunities, or refusing duplicated risk?

THE SPLIT IS DECLARED HERE, BEFORE ANY NUMBER IS COMPUTED.
  Chronological thirds of the reconstructed blocked events, ordered by
  date, equal count. Early / middle / late. Nothing else.

WHAT THE BUCKET ACTUALLY IS, established before anything is measured:
`CORRELATION_BUCKETS` in strategy.py is a STATIC HAND-WRITTEN SECTOR
MAP. There is no lookback, no correlation computation, no threshold and
no update. It therefore cannot drift out of date with the market - it
was never derived from the market. Whether a sector label is a good
proxy for realised correlation is an empirical question, and this file
measures it rather than assuming it either way.

POINT-IN-TIME. Candidate conviction, ATR and liquidity are recomputed
from bars strictly up to the decision date. Forward returns are
MEASUREMENT of what happened afterwards and can never become features.
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
from event_aware_trader.indicators import average_true_range   # noqa: E402
from event_aware_trader.mean_reversion import conviction as shipped_conviction  # noqa: E402
from event_aware_trader.phase5.metrics import measure          # noqa: E402
from event_aware_trader.research import production_report      # noqa: E402
from event_aware_trader.strategy import CORRELATION_BUCKETS     # noqa: E402

from forensics_regime import build_signals, load, STATES        # noqa: E402

_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-400:], c)
_conv = {}

HORIZONS = (1, 3, 5, 10, 20)
HEADLINE = 10
MAX_POSITIONS, MAX_PER_BUCKET = 12, 1


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def pct(values, p):
    if not values:
        return None
    s = sorted(values)
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


def describe(vals, label, width=22):
    if not vals:
        print("  {0:<{1}} {2:>5}".format(label, width, 0))
        return
    print("  {0:<{1}} {2:>5} {3:>9.3%} {4:>9.3%} {5:>9.3%} {6:>9.3%} "
          "{7:>8.1%}".format(label, width, len(vals), fmean(vals),
                             median(vals), pct(vals, 25), pct(vals, 75),
                             sum(1 for v in vals if v > 0) / len(vals)))


def header(width=22):
    print("  {0:<{1}} {2:>5} {3:>9} {4:>9} {5:>9} {6:>9} {7:>8}".format(
        "", width, "n", "mean", "median", "p25", "p75", "win"))


def main():
    series = load()
    spy_close = {b.timestamp.date(): b.close for b in series["SPY"]}
    print("decade: {0} symbols".format(len(series)), flush=True)
    report = production_report(series, conviction=conviction,
                               dataset="decade", purpose="diagnostic")
    scored = measure(report, "baseline").as_dict()
    print("baseline: {0} trades, total {1:+.4%}, maxDD {2:.4%}, exposure "
          "{3:.2%}\n".format(scored["trades"], scored["total_return"],
                             scored["max_drawdown"], scored["exposure"]),
          flush=True)

    dates = {s: [b.timestamp.date() for b in bs] for s, bs in series.items()}
    closes = {s: [b.close for b in bs] for s, bs in series.items()}
    index = {s: {d: i for i, d in enumerate(ds)} for s, ds in dates.items()}
    spy_d = dates["SPY"]
    spy_i = index["SPY"]

    # ---- 0. what the bucket is, and does it track correlation? ---------
    print("=" * 76)
    print("0. WHAT THE BUCKET ACTUALLY IS (item 9)")
    print("=" * 76)
    buckets = defaultdict(list)
    for s in series:
        buckets[CORRELATION_BUCKETS.get(s, "other")].append(s)
    print("  construction        STATIC hand-written sector/theme map in")
    print("                      strategy.py; a literal dict")
    print("  lookback window     NONE - no prices are read")
    print("  data frequency      n/a          correlation calc   NONE")
    print("  threshold           n/a          update frequency   NEVER")
    print("  point-in-time       trivially yes - no market data is used, so")
    print("                      no price look-ahead is possible")
    print("  static or dynamic   STATIC; assignment never changes")
    print("  survivorship        the LABELS encode today's understanding of")
    print("                      each business, applied to all history")
    print("  buckets present     {0} over {1} symbols".format(
        len(buckets), len(series)))
    print("  unmapped -> 'other' {0}".format(
        sum(1 for s in series if s not in CORRELATION_BUCKETS)))

    print("\n  DOES THE LABEL TRACK REALISED CORRELATION?")
    print("  Daily returns, full decade, mean pairwise Pearson.")
    rets = {}
    for s, cl in closes.items():
        rets[s] = {dates[s][i]: cl[i] / cl[i - 1] - 1.0
                   for i in range(1, len(cl)) if cl[i - 1]}
    common = sorted(set(spy_d) & set.intersection(
        *[set(rets[s]) for s in list(rets)[:5]]))

    def pair_corr(a, b):
        days = [d for d in common if d in rets[a] and d in rets[b]]
        if len(days) < 250:
            return None
        return corr([rets[a][d] for d in days], [rets[b][d] for d in days])

    within, across = [], []
    per_bucket = {}
    names = sorted(series)
    for b, members in sorted(buckets.items()):
        if len(members) < 2:
            continue
        vals = []
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                c = pair_corr(members[i], members[j])
                if c is not None:
                    vals.append(c)
        if vals:
            per_bucket[b] = {"n_pairs": len(vals), "mean": fmean(vals),
                             "min": min(vals), "max": max(vals),
                             "members": len(members)}
            within.extend(vals)
    step = max(1, len(names) // 40)
    sample = names[::step]
    for i in range(len(sample)):
        for j in range(i + 1, len(sample)):
            if CORRELATION_BUCKETS.get(sample[i], "other") == \
                    CORRELATION_BUCKETS.get(sample[j], "other"):
                continue
            c = pair_corr(sample[i], sample[j])
            if c is not None:
                across.append(c)
    print("    within-bucket pairs   {0:>5}  mean {1:+.4f}  median {2:+.4f}"
          .format(len(within), fmean(within), median(within)))
    print("    across-bucket pairs   {0:>5}  mean {1:+.4f}  median {2:+.4f}"
          .format(len(across), fmean(across), median(across)))
    print("    separation            {0:+.4f}".format(
        fmean(within) - fmean(across)))
    print("\n    buckets whose members are LEAST correlated (label may be")
    print("    grouping things the market does not):")
    print("    {0:<18} {1:>7} {2:>8} {3:>8} {4:>8}".format(
        "bucket", "members", "pairs", "mean r", "min r"))
    for b, v in sorted(per_bucket.items(), key=lambda kv: kv[1]["mean"])[:8]:
        print("    {0:<18} {1:>7} {2:>8} {3:>8.4f} {4:>8.4f}".format(
            b, v["members"], v["n_pairs"], v["mean"], v["min"]))
    print("\n    most correlated buckets:")
    for b, v in sorted(per_bucket.items(),
                       key=lambda kv: -kv[1]["mean"])[:5]:
        print("    {0:<18} {1:>7} {2:>8} {3:>8.4f} {4:>8.4f}".format(
            b, v["members"], v["n_pairs"], v["mean"], v["min"]))
    high_cross = []
    for i in range(len(sample)):
        for j in range(i + 1, len(sample)):
            if CORRELATION_BUCKETS.get(sample[i], "other") == \
                    CORRELATION_BUCKETS.get(sample[j], "other"):
                continue
            c = pair_corr(sample[i], sample[j])
            if c is not None and c > 0.75:
                high_cross.append((sample[i], sample[j], c))
    print("\n    pairs in DIFFERENT buckets with r > 0.75 (the rule lets")
    print("    these sit together): {0} of {1} sampled cross pairs".format(
        len(high_cross), len(across)))
    for a, b, c in sorted(high_cross, key=lambda x: -x[2])[:5]:
        print("      {0:<6} {1:<6} r={2:.3f}  ({3} / {4})".format(
            a, b, c, CORRELATION_BUCKETS.get(a, "other"),
            CORRELATION_BUCKETS.get(b, "other")))

    # ---- 1. reconstruct the blocks -------------------------------------
    print("\n" + "=" * 76)
    print("1. RECONSTRUCTING EVERY BLOCK (item 1)")
    print("=" * 76)
    cands = defaultdict(list)
    for line in (REPO / "data" / "phase5" / "candidates-deep.jsonl"
                 ).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            cands[date.fromisoformat(r["date"])].append(r["symbol"])
    taken_by_day = defaultdict(set)
    trade_at = {}
    for t in report.trades:
        taken_by_day[t.entry_time.date()].add(t.symbol)
        trade_at[(t.symbol, t.entry_time.date())] = t

    equity = {t.date(): v for t, v in report.equity_curve}
    cash = {t.date(): v for t, v in report.cash_curve}
    eq_days = sorted(equity)
    open_on = defaultdict(list)
    for t in report.trades:
        d0, d1 = t.entry_time.date(), t.exit_time.date()
        for d in eq_days:
            if d0 <= d < d1:
                open_on[d].append(t)

    def forward(sym, day, h):
        i = index.get(sym, {}).get(day)
        if i is None or i + h >= len(closes[sym]):
            return None
        return closes[sym][i + h] / closes[sym][i] - 1.0

    def spy_forward(day, h):
        i = spy_i.get(day)
        if i is None or i + h >= len(spy_d):
            return None
        return spy_close[spy_d[i + h]] / spy_close[spy_d[i]] - 1.0

    events, misses = [], defaultdict(int)
    for day in sorted(cands):
        if day not in equity:
            misses["candidate day not in the equity curve"] += len(cands[day])
            continue
        got = taken_by_day.get(day, set())
        held = open_on.get(day, [])
        occupants = {}
        for t in held:
            occupants.setdefault(
                CORRELATION_BUCKETS.get(t.symbol, "other"), t)
        for sym in got:                       # same-day fills also occupy
            occupants.setdefault(CORRELATION_BUCKETS.get(sym, "other"),
                                 trade_at.get((sym, day)))
        for sym in cands[day]:
            if sym not in index or day not in index[sym]:
                misses["candidate symbol/day absent from bars"] += 1
                continue
            bkt = CORRELATION_BUCKETS.get(sym, "other")
            if sym in got:
                status = "taken"
            elif len(held) >= MAX_POSITIONS:
                status = "position_cap"
            elif bkt in occupants:
                status = "bucket"
            elif cash.get(day, 0.0) < 0.05 * equity.get(day, 1.0):
                status = "cash"
            else:
                status = "other"
            i = index[sym][day]
            bars = series[sym][:i + 1]
            atr = average_true_range(bars[-60:]) if len(bars) >= 30 else None
            vol20 = (pstdev([closes[sym][k] / closes[sym][k - 1] - 1.0
                             for k in range(i - 19, i + 1)])
                     if i >= 20 else None)
            adv = (fmean([b.close * b.volume for b in bars[-20:]])
                   if len(bars) >= 20 else None)
            occ = occupants.get(bkt)
            row = {
                "date": day.isoformat(), "symbol": sym, "bucket": bkt,
                "status": status, "year": day.year,
                "conviction": shipped_conviction(bars[-40:])
                if len(bars) >= 40 else None,
                "atr_frac": (atr / closes[sym][i]) if atr else None,
                "vol20": vol20, "adv": adv,
                "fwd": {h: forward(sym, day, h) for h in HORIZONS},
                "spy": {h: spy_forward(day, h) for h in HORIZONS},
                "occ_symbol": occ.symbol if occ is not None else None,
            }
            if occ is not None and status == "bucket":
                oi = index.get(occ.symbol, {}).get(day)
                row["occ_age"] = (day - occ.entry_time.date()).days
                row["occ_unrealised"] = (
                    closes[occ.symbol][oi] / occ.entry_price - 1.0
                    if oi is not None else None)
                ob = series[occ.symbol][:oi + 1] if oi is not None else []
                row["occ_conviction"] = (shipped_conviction(ob[-40:])
                                         if len(ob) >= 40 else None)
                row["occ_fwd"] = {h: forward(occ.symbol, day, h)
                                  for h in HORIZONS}
            events.append(row)

    by_status = defaultdict(list)
    for e in events:
        by_status[e["status"]].append(e)
    print("  candidates reconstructed: {0}".format(len(events)))
    for why, n in misses.items():
        print("    not reconstructed - {0}: {1}".format(why, n))
    print("  {0:<16} {1:>7} {2:>8}".format("status", "n", "share"))
    for st in sorted(by_status, key=lambda k: -len(by_status[k])):
        print("  {0:<16} {1:>7} {2:>8.1%}".format(
            st, len(by_status[st]), len(by_status[st]) / len(events)))

    usable = [e for e in events if e["fwd"][HEADLINE] is not None
              and e["spy"][HEADLINE] is not None]
    print("\n  with a full {0}-session forward window: {1}".format(
        HEADLINE, len(usable)))

    # ---- 2/3/4. taken vs blocked ---------------------------------------
    print("\n" + "=" * 76)
    print("2. TAKEN vs BLOCKED - is the blocked candidate better? (items 3,4,14)")
    print("=" * 76)
    groups = defaultdict(list)
    for e in usable:
        groups[e["status"]].append(e)
    order = ["taken", "bucket", "cash", "other", "position_cap"]
    for h in HORIZONS:
        print("\n  EXCESS vs SPY over {0} session(s)".format(h))
        header()
        for st in order:
            g = [x for x in groups.get(st, [])
                 if x["fwd"][h] is not None and x["spy"][h] is not None]
            describe([x["fwd"][h] - x["spy"][h] for x in g], st)

    print("\n  POINT-IN-TIME QUALITY AT THE DECISION (no forward data)")
    print("  {0:<16} {1:>7} {2:>12} {3:>12} {4:>14}".format(
        "status", "n", "conviction", "ATR frac", "ADV $m"))
    for st in order:
        g = groups.get(st, [])
        if not g:
            continue
        cv = [x["conviction"] for x in g if x["conviction"] is not None]
        af = [x["atr_frac"] for x in g if x["atr_frac"] is not None]
        ad = [x["adv"] for x in g if x["adv"] is not None]
        print("  {0:<16} {1:>7} {2:>12.4f} {3:>12.4%} {4:>14,.0f}".format(
            st, len(g), fmean(cv) if cv else 0.0, fmean(af) if af else 0.0,
            (fmean(ad) / 1e6) if ad else 0.0))

    # ---- the key counterfactual: blocked vs its occupant ---------------
    print("\n" + "=" * 76)
    print("3. THE KEY COUNTERFACTUAL - blocked candidate vs the position")
    print("   that displaced it, from the SAME day forward (items 1,2,11)")
    print("=" * 76)
    pairs = [e for e in groups.get("bucket", [])
             if e.get("occ_fwd") and e["occ_fwd"].get(HEADLINE) is not None]
    print("  reconstructable pairs: {0}".format(len(pairs)))
    print("\n  {0:>4} {1:>7} {2:>12} {3:>12} {4:>12} {5:>10}".format(
        "h", "pairs", "blocked", "occupant", "difference", "blocked>occ"))
    marg = {}
    for h in HORIZONS:
        p = [e for e in pairs if e["fwd"][h] is not None
             and e["occ_fwd"].get(h) is not None]
        if not p:
            continue
        b = [e["fwd"][h] for e in p]
        o = [e["occ_fwd"][h] for e in p]
        d = [x - y for x, y in zip(b, o)]
        marg[h] = {"n": len(p), "blocked": fmean(b), "occupant": fmean(o),
                   "diff": fmean(d),
                   "win": sum(1 for x in d if x > 0) / len(d)}
        print("  {0:>4} {1:>7} {2:>12.3%} {3:>12.3%} {4:>12.3%} "
              "{5:>10.1%}".format(h, len(p), fmean(b), fmean(o), fmean(d),
                                  marg[h]["win"]))

    print("\n  HOW DUPLICATED IS THE SECOND POSITION? (item 11)")
    print("  correlation between the blocked candidate's forward return and")
    print("  its bucket occupant's, over the same window:")
    for h in (5, 10, 20):
        p = [e for e in pairs if e["fwd"][h] is not None
             and e["occ_fwd"].get(h) is not None]
        if len(p) < 30:
            continue
        c = corr([e["fwd"][h] for e in p], [e["occ_fwd"][h] for e in p])
        print("    {0:>3} sessions   r = {1:+.4f}   n = {2}".format(h, c, len(p)))
    print("\n  occupant state when it blocked something:")
    ages = [e["occ_age"] for e in pairs if e.get("occ_age") is not None]
    unre = [e["occ_unrealised"] for e in pairs
            if e.get("occ_unrealised") is not None]
    print("    occupant age (calendar days)   mean {0:.1f}  median {1:.0f}"
          .format(fmean(ages), median(ages)))
    print("    occupant unrealised            mean {0:+.3%}  median {1:+.3%}"
          .format(fmean(unre), median(unre)))
    print("    occupant was under water       {0:.1%} of the time".format(
        sum(1 for v in unre if v < 0) / len(unre)))
    cvp = [(e["conviction"], e["occ_conviction"]) for e in pairs
           if e["conviction"] is not None and e["occ_conviction"] is not None]
    print("    blocked conviction > occupant's at ITS entry: {0:.1%} of {1}"
          .format(sum(1 for a, b in cvp if a > b) / len(cvp), len(cvp)))

    # ---- 5. concentration -----------------------------------------------
    print("\n" + "=" * 76)
    print("4. BUCKET CONCENTRATION (item 5)")
    print("=" * 76)
    blocked = groups.get("bucket", [])
    per = defaultdict(lambda: {"blocked": 0, "taken": 0, "exc": []})
    for e in usable:
        if e["status"] == "bucket":
            per[e["bucket"]]["blocked"] += 1
            per[e["bucket"]]["exc"].append(e["fwd"][HEADLINE]
                                           - e["spy"][HEADLINE])
        elif e["status"] == "taken":
            per[e["bucket"]]["taken"] += 1
    tot_blocked = sum(v["blocked"] for v in per.values())
    ranked = sorted(per.items(), key=lambda kv: -kv[1]["blocked"])
    print("  buckets with any blocking: {0}".format(
        sum(1 for v in per.values() if v["blocked"])))
    print("  {0:<18} {1:>8} {2:>8} {3:>8} {4:>12} {5:>12}".format(
        "bucket", "blocked", "share", "taken", "mean exc", "median exc"))
    cum = 0
    for b, v in ranked[:12]:
        cum += v["blocked"]
        print("  {0:<18} {1:>8} {2:>8.1%} {3:>8} {4:>12.3%} {5:>12.3%}".format(
            b, v["blocked"], v["blocked"] / tot_blocked, v["taken"],
            fmean(v["exc"]) if v["exc"] else 0.0,
            median(v["exc"]) if v["exc"] else 0.0))
    print("  top 12 buckets carry {0:.1%} of all blocking".format(
        cum / tot_blocked))

    # ---- 6. time split ---------------------------------------------------
    print("\n" + "=" * 76)
    print("5. TIME STABILITY - chronological thirds, declared beforehand")
    print("=" * 76)
    ordered = sorted(blocked, key=lambda e: e["date"])
    third = len(ordered) // 3
    parts = [("early", ordered[:third]), ("middle", ordered[third:2 * third]),
             ("late", ordered[2 * third:])]
    print("  {0:<8} {1:>6} {2:<25} {3:>12} {4:>12} {5:>8}".format(
        "period", "n", "dates", "mean exc", "median", "win"))
    thirds = []
    for name, part in parts:
        e = [x["fwd"][HEADLINE] - x["spy"][HEADLINE] for x in part]
        thirds.append({"period": name, "n": len(e), "mean": fmean(e),
                       "median": median(e),
                       "win": sum(1 for v in e if v > 0) / len(e)})
        print("  {0:<8} {1:>6} {2:<25} {3:>+12.3%} {4:>+12.3%} {5:>8.1%}".format(
            name, len(e), "{0} -> {1}".format(part[0]["date"],
                                              part[-1]["date"]),
            fmean(e), median(e), sum(1 for v in e if v > 0) / len(e)))
    print("\n  all thirds same sign: {0}".format(
        len({t["mean"] > 0 for t in thirds}) == 1))

    print("\n  by calendar year:")
    byyear = defaultdict(list)
    for e in blocked:
        byyear[e["year"]].append(e["fwd"][HEADLINE] - e["spy"][HEADLINE])
    print("  {0:>6} {1:>7} {2:>12} {3:>12}".format("year", "n", "mean exc",
                                                   "sum exc"))
    for y in sorted(byyear):
        v = byyear[y]
        print("  {0:>6} {1:>7} {2:>+12.3%} {3:>+12.3%}".format(
            y, len(v), fmean(v), sum(v)))

    # ---- 7. regime ------------------------------------------------------
    print("\n" + "=" * 76)
    print("6. REGIME INTERACTION - descriptive only (item 7)")
    print("=" * 76)
    labels, _days, _diag = build_signals(series)
    lab = labels["trend_dual_ma"]
    print("  blocking rate and blocked-candidate value, by market state")
    print("  {0:<14} {1:>8} {2:>9} {3:>9} {4:>12} {5:>10}".format(
        "state", "cands", "blocked", "rate", "mean exc", "win"))
    for st in STATES:
        g = [e for e in events if lab.get(date.fromisoformat(e["date"])) == st]
        if not g:
            continue
        bl = [e for e in g if e["status"] == "bucket"
              and e["fwd"][HEADLINE] is not None
              and e["spy"][HEADLINE] is not None]
        exc = [e["fwd"][HEADLINE] - e["spy"][HEADLINE] for e in bl]
        print("  {0:<14} {1:>8} {2:>9} {3:>9.1%} {4:>12.3%} {5:>10.1%}".format(
            st, len(g), len(bl), len(bl) / len(g),
            fmean(exc) if exc else 0.0,
            (sum(1 for v in exc if v > 0) / len(exc)) if exc else 0.0))

    # ---- 8. cash decomposition ------------------------------------------
    print("\n" + "=" * 76)
    print("7. WHAT IS THE CASH ACTUALLY DOING? (items 12, 13)")
    print("=" * 76)
    cand_days = set(cands)
    no_cand = [d for d in eq_days if d not in cand_days]
    blocked_days = {date.fromisoformat(e["date"]) for e in blocked}
    print("  sessions simulated                       {0}".format(len(eq_days)))
    print("  sessions with NO candidate at all        {0} ({1:.1%})".format(
        len(no_cand), len(no_cand) / len(eq_days)))
    print("  sessions with a bucket-blocked candidate {0} ({1:.1%})".format(
        len(blocked_days), len(blocked_days) / len(eq_days)))
    print("  mean cash share, all sessions            {0:.1%}".format(
        fmean([cash[d] / equity[d] for d in eq_days if equity.get(d)])))
    print("  mean cash, sessions with NO candidate    {0:.1%}".format(
        fmean([cash[d] / equity[d] for d in no_cand if equity.get(d)])))
    print("  mean cash, sessions WITH a block         {0:.1%}".format(
        fmean([cash[d] / equity[d] for d in blocked_days if equity.get(d)])))
    print("  mean positions held                      {0:.2f} of {1}".format(
        fmean([len(open_on.get(d, [])) for d in eq_days]), MAX_POSITIONS))
    notional = fmean([abs(t.quantity) * t.entry_price
                      for t in report.trades])
    mean_eq = fmean([equity[d] for d in eq_days])
    print("")
    print("  A blocked candidate is worth roughly one position slot.")
    print("  Mean notional per trade {0:,.0f} on {1:,.0f} of equity:"
          .format(notional, mean_eq))
    print("  each extra concurrent position is about {0:.1%} of the"
          .format(notional / mean_eq))
    print("  account.")

    out = REPO / "docs" / "phase5" / "bucket-forensics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "FORENSIC_NON_PROMOTIONAL": True,
        "baseline": scored,
        "bucket_construction": {
            "kind": "static hand-written sector map", "lookback": None,
            "correlation_calc": None, "threshold": None, "updates": "never",
            "buckets": len(buckets)},
        "within_bucket_corr": {"pairs": len(within), "mean": fmean(within),
                               "median": median(within)},
        "across_bucket_corr": {"pairs": len(across), "mean": fmean(across),
                               "median": median(across)},
        "per_bucket_corr": per_bucket,
        "high_cross_pairs": [[a, b, c] for a, b, c in high_cross],
        "status_counts": {k: len(v) for k, v in by_status.items()},
        "usable": len(usable),
        "excess_by_status": {
            st: {str(h): fmean([x["fwd"][h] - x["spy"][h]
                                for x in groups.get(st, [])
                                if x["fwd"][h] is not None
                                and x["spy"][h] is not None] or [0])
                 for h in HORIZONS} for st in order if groups.get(st)},
        "marginal_vs_occupant": marg,
        "bucket_concentration": {b: {"blocked": v["blocked"],
                                     "taken": v["taken"],
                                     "mean_exc": fmean(v["exc"]) if v["exc"]
                                     else None}
                                 for b, v in ranked},
        "thirds": thirds,
        "by_year": {str(y): {"n": len(v), "mean": fmean(v)}
                    for y, v in byyear.items()},
        "note": "READ-ONLY FORENSICS. Not an experiment, not promotable.",
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
