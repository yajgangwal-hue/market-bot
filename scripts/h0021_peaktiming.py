"""COHERENCE CHECK - disclosed as NOT part of the H-0021 seal.

Purpose: decide whether a deadline-conditional mechanism is even
coherent. If the executable peak of a time-exit trade typically occurs
early in the hold, then by the time any terminal-window rule could act
the give-back has already happened, and the honest answer is NO NEW
CANDIDATE. Descriptive only; no rule is simulated.
"""
import sys
from collections import Counter
from statistics import fmean, median
sys.path.insert(0, "C:/market-bot/src"); sys.path.insert(0, "C:/market-bot/scripts")
from event_aware_trader.mean_reversion import MeanReversionConfig, conviction as sc
from event_aware_trader.phase5.metrics import measure
from event_aware_trader.research import production_report
from forensics_regime import load

_c = {}
def conviction(sym, h):
    k = (sym, len(h), h[0].timestamp if h else None)
    v = _c.get(k)
    if v is None: v = _c[k] = sc(h[-40:])
    return v

series = load()
rep = production_report(series, conviction=conviction, dataset="decade",
                        purpose="rejection_test", mr_config=MeanReversionConfig())
m = measure(rep, "B").as_dict()
assert abs(m["total_return"]-0.585889) < 5e-7 and m["trades"] == 698, "baseline moved"
print("baseline OK  {0:+.6%} / {1}".format(m["total_return"], m["trades"]))

idx = {s: {b.timestamp.date(): i for i, b in enumerate(bs)} for s, bs in series.items()}
rows = []
for t in rep.trades:
    if t.exit_reason != "time_exit": continue
    bs = series[t.symbol]
    i0 = idx[t.symbol].get(t.entry_time.date()); i1 = idx[t.symbol].get(t.exit_time.date())
    if i0 is None or i1 is None or i1 <= i0: continue
    e = t.entry_price
    opens = [(k - i0, bs[k].open) for k in range(i0 + 1, i1 + 1)]   # executable
    if not opens: continue
    kbest, pbest = max(opens, key=lambda kv: kv[1])
    rows.append({"n": i1 - i0, "kbest": kbest, "peak": pbest / e - 1.0,
                 "exit": t.exit_price / e - 1.0, "qty": t.quantity,
                 "e": e, "opens": opens, "xp": t.exit_price})

print("time_exit trades analysed:", len(rows))
ks = [r["kbest"] for r in rows]
print("\nbar of EXECUTABLE peak (entry=bar 0, cap at bar ~20)")
print("  median {0} | mean {1:.1f} | quartiles {2} / {3}".format(
    median(ks), fmean(ks), sorted(ks)[len(ks)//4], sorted(ks)[3*len(ks)//4]))
buckets = Counter()
for k in ks:
    buckets["01-05" if k<=5 else "06-10" if k<=10 else "11-15" if k<=15 else "16-20"] += 1
for b in ("01-05","06-10","11-15","16-20"):
    print("  bars {0}: {1:4d}  ({2:.1%})".format(b, buckets[b], buckets[b]/len(ks)))

print("\nvalue still on the table AFTER bar k (one-sided, hindsight bound)")
print("  {0:>4}{1:>10}{2:>14}{3:>16}".format("k","trades","mean avail","$ pool"))
for k in (0, 5, 10, 13, 15, 17, 18, 19):
    sub = [r for r in rows if r["n"] > k]
    tot, vals = 0.0, []
    for r in sub:
        later = [p for kk, p in r["opens"] if kk > k]
        if not later: continue
        best = max(later)
        vals.append((best - r["xp"]) / r["e"])
        tot += max(0.0, best - r["xp"]) * r["qty"]
    if vals:
        print("  {0:>4}{1:>10}{2:>13.3%}{3:>16,.0f}".format(k, len(vals), fmean(vals), tot))
