"""H-0014 - expanding-window-by-year IC, so all three thirds get an
out-of-sample value and the sealed 2-of-3 gate can be evaluated.

Same principle as the sealed "fit on earlier thirds, score the next",
at finer granularity: each calendar year is scored by a model fit on
ALL earlier years only. Years are then grouped into the sealed thirds.
Nothing else changes - same features, same target, same model form.
"""

import csv
import glob
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from statistics import fmean, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from h0014_analyse import (INTRA, DAILYF, LABELS, spearman, fit,  # noqa: E402
                           standardise, third_of, ff, scratch,
                           build_daily_cache)

SCR = scratch()
DEEP = SCR / "deep"
SNAP = SCR / "snapshots"
OUT = REPO / "docs" / "phase5" / "h0014-ic-yearly.json"
MINTRAIN = 3000


def main():
    syms = sorted(p.stem for p in DEEP.glob("*.csv"))
    if len({p.stem for p in SNAP.glob("*.csv")}) != len(syms):
        print("REFUSED: coverage is not 230/230.")
        return 2
    print("expanding-window-by-year IC | 230/230", flush=True)
    daily = build_daily_cache()

    per = {L: {"X": [], "y": [], "yr": []} for L in LABELS}
    for n, sym in enumerate(syms, 1):
        dmap = daily.get(sym, {})
        for r in csv.DictReader(open(SNAP / (sym + ".csv"))):
            df = dmap.get(r["session"])
            if not df:
                continue
            t = ff(r["spy_fwd10"])
            f10 = ff(r["fwd10"])
            if t is None or f10 is None:
                continue
            L = r["snap"]
            per[L]["X"].append(list(df) + [ff(r[k]) for k in INTRA])
            per[L]["y"].append(f10 - t)
            per[L]["yr"].append(int(r["session"][:4]))
        if n % 50 == 0:
            print("  {0}/{1}".format(n, len(syms)), flush=True)

    nd = len(DAILYF)
    res = {}
    print("\n  {0:<7} {1:>9} {2:>9} {3:>9} {4:>9} {5:>12}".format(
        "snap", "incr T1", "incr T2", "incr T3", "pooled", "2-of-3"))
    for L in LABELS:
        d = per[L]
        Z = standardise(d["X"], nd + len(INTRA))
        byyear = defaultdict(list)
        for i, y in enumerate(d["yr"]):
            byyear[y].append(i)
        years = sorted(byyear)
        preds = {"daily": defaultdict(list), "daily_intraday": defaultdict(list)}
        acts = defaultdict(list)
        for y in years:
            tr = [i for yy in years if yy < y for i in byyear[yy]]
            te = byyear[y]
            if len(tr) < MINTRAIN or len(te) < 200:
                continue
            t3 = third_of(y)
            for name, k in (("daily", nd),
                            ("daily_intraday", nd + len(INTRA))):
                X = [[Z[i][j] for j in range(k)] for i in tr]
                b = fit(X, [d["y"][i] for i in tr])
                preds[name][t3] += [sum(Z[i][j] * b[j] for j in range(k))
                                    for i in te]
            acts[t3] += [d["y"][i] for i in te]
        row = {}
        for t3 in (1, 2, 3):
            if not acts[t3]:
                row[t3] = None
                continue
            a = spearman(preds["daily"][t3], acts[t3])
            c = spearman(preds["daily_intraday"][t3], acts[t3])
            row[t3] = {"daily": a, "daily_intraday": c,
                       "incr": (c - a) if (a is not None and c is not None)
                       else None, "n": len(acts[t3])}
        allp_d = [x for t3 in (1, 2, 3) for x in preds["daily"][t3]]
        allp_i = [x for t3 in (1, 2, 3) for x in preds["daily_intraday"][t3]]
        alla = [x for t3 in (1, 2, 3) for x in acts[t3]]
        pa = spearman(allp_d, alla) if alla else None
        pc = spearman(allp_i, alla) if alla else None
        pooled = (pc - pa) if (pa is not None and pc is not None) else None
        pos = sum(1 for t3 in (1, 2, 3)
                  if row.get(t3) and row[t3]["incr"] is not None
                  and row[t3]["incr"] > 0)
        res[L] = {"thirds": row, "pooled_daily": pa,
                  "pooled_daily_intraday": pc, "pooled_incr": pooled,
                  "positive_thirds": pos, "passes_2of3": pos >= 2}
        g = lambda t3: ("{0:+.4f}".format(row[t3]["incr"])
                        if row.get(t3) and row[t3]["incr"] is not None
                        else "     n/a")
        print("  {0:<7} {1:>9} {2:>9} {3:>9} {4:>9} {5:>12}".format(
            L, g(1), g(2), g(3),
            "{0:+.4f}".format(pooled) if pooled is not None else "   n/a",
            "PASS {0}/3".format(pos) if pos >= 2 else "FAIL {0}/3".format(pos)))
    OUT.write_text(json.dumps(res, indent=1, sort_keys=True, default=str),
                   encoding="utf-8")
    print("\nwrote {0}".format(OUT.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
