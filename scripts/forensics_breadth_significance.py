"""FORENSIC_NON_PROMOTIONAL. Is the RSI 35-40 hump real, or clustering?

The band table has 192,392 observations drawn from 2,684 sessions and
230 symbols. Treating those as independent would manufacture
significance: on any given day most names move together, and the same
name appears on consecutive days with overlapping forward windows.

Three honest treatments, all declared here before running:
  1. COLLAPSE TO ONE OBSERVATION PER SESSION. Average the band's excess
     across symbols within a day, then treat days as the unit. This
     removes cross-sectional correlation entirely.
  2. MONTHLY BLOCK BOOTSTRAP on those daily means, which also removes
     the overlap between consecutive days.
  3. THE DIFFERENCE that matters: band (35,40] minus band <=35 computed
     WITHIN each session, so a day's market move cancels exactly.

Treatment 3 is the real test. "Is 35-40 better than <=35" is a paired
question and must be asked as one.
"""

import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from statistics import fmean, median, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

BOOTSTRAP = 4000
random.seed(20260917)
HORIZONS = (5, 10, 20)


def pct(v, p):
    if not v:
        return None
    s = sorted(v)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def boot_ci(by_month, iters=BOOTSTRAP):
    months = list(by_month)
    if not months:
        return None, None, None
    out = []
    for _ in range(iters):
        pick = [random.choice(months) for _ in months]
        vals = [v for m in pick for v in by_month[m]]
        if vals:
            out.append(fmean(vals))
    return pct(out, 2.5), pct(out, 97.5), sum(1 for b in out if b > 0) / len(out)


def main():
    raw = json.loads((REPO / "docs" / "phase5" / "breadth-observations.json")
                     .read_text(encoding="utf-8"))
    rows = raw["observations"]
    print("observations: {0:,} over {1:,} sessions".format(
        len(rows), len({r["date"] for r in rows})))

    # ---- 1. collapse to one observation per session --------------------
    print("\n" + "=" * 76)
    print("1. ONE OBSERVATION PER SESSION (cross-sectional correlation gone)")
    print("=" * 76)
    bands = ["<=35 QUALIFIES", "(35,37.5]", "(37.5,40]", "(40,45]",
             "(45,50]", "(50,60]"]
    daily = {b: defaultdict(dict) for b in bands}
    for r in rows:
        b = r["band"]
        if b not in daily:
            continue
        for h in HORIZONS:
            daily[b][h].setdefault(r["date"], []).append(
                r["fwd"][str(h)] - r["spy"][str(h)])
    out = {}
    for h in HORIZONS:
        print("\n  {0}-session excess, day as the unit".format(h))
        print("  {0:<16} {1:>7} {2:>11} {3:>11} {4:>9} {5:>7} {6:>22}".format(
            "band", "days", "mean", "median", "SE", "t", "95% CI (monthly boot)"))
        for b in bands:
            per_day = {d: fmean(v) for d, v in daily[b][h].items()}
            if len(per_day) < 60:
                continue
            vals = list(per_day.values())
            se = pstdev(vals) / (len(vals) ** 0.5)
            by_month = defaultdict(list)
            for d, v in per_day.items():
                by_month[d[:7]].append(v)
            lo, hi, share = boot_ci(by_month)
            out.setdefault(b, {})[h] = {
                "days": len(vals), "mean": fmean(vals), "se": se,
                "t": fmean(vals) / se if se else None,
                "ci_low": lo, "ci_high": hi, "share_above_zero": share}
            print("  {0:<16} {1:>7,} {2:>11.4%} {3:>11.4%} {4:>9.4%} "
                  "{5:>7.2f} {6:>22}".format(
                      b, len(vals), fmean(vals), median(vals), se,
                      fmean(vals) / se if se else 0.0,
                      "[{0:+.3%}, {1:+.3%}]".format(lo, hi)))

    # ---- 2. the paired question ----------------------------------------
    print("\n" + "=" * 76)
    print("2. THE PAIRED TEST - (35,40] minus <=35, WITHIN each session")
    print("=" * 76)
    print("  Only sessions where BOTH bands have at least one name. The")
    print("  day's market move cancels exactly, so this isolates the")
    print("  question 'is the near-miss band better than the qualifying")
    print("  band'. This is the comparison that decides the pass.")
    paired = {}
    for h in HORIZONS:
        near = defaultdict(list)
        qual = defaultdict(list)
        for r in rows:
            if r["band"] in ("(35,37.5]", "(37.5,40]"):
                near[r["date"]].append(r["fwd"][str(h)] - r["spy"][str(h)])
            elif r["band"] == "<=35 QUALIFIES":
                qual[r["date"]].append(r["fwd"][str(h)] - r["spy"][str(h)])
        both = sorted(set(near) & set(qual))
        diffs = {d: fmean(near[d]) - fmean(qual[d]) for d in both}
        vals = list(diffs.values())
        se = pstdev(vals) / (len(vals) ** 0.5)
        by_month = defaultdict(list)
        for d, v in diffs.items():
            by_month[d[:7]].append(v)
        lo, hi, share = boot_ci(by_month)
        paired[h] = {"days": len(vals), "mean": fmean(vals),
                     "median": median(vals), "se": se,
                     "t": fmean(vals) / se if se else None,
                     "ci_low": lo, "ci_high": hi, "share_above_zero": share,
                     "win": sum(1 for v in vals if v > 0) / len(vals)}
        print("\n  {0} sessions, {1}-session horizon".format(len(vals), h))
        print("    mean difference   {0:+.4%}   median {1:+.4%}".format(
            fmean(vals), median(vals)))
        print("    SE / t            {0:.4%} / {1:.2f}".format(
            se, fmean(vals) / se if se else 0))
        print("    95% CI (monthly)  [{0:+.4%}, {1:+.4%}]".format(lo, hi))
        print("    CI excludes zero  {0}".format(lo > 0 or hi < 0))
        print("    sessions where near-miss beat qualifying: {0:.1%}".format(
            sum(1 for v in vals if v > 0) / len(vals)))

    # ---- 3. paired, by chronological third -----------------------------
    print("\n" + "=" * 76)
    print("3. THE PAIRED DIFFERENCE BY CHRONOLOGICAL THIRD")
    print("=" * 76)
    alldays = sorted({r["date"] for r in rows})
    third = len(alldays) // 3
    cuts = (alldays[third], alldays[2 * third])
    print("  boundaries {0} and {1}".format(*cuts))
    thirds = {}
    for h in HORIZONS:
        near, qual = defaultdict(list), defaultdict(list)
        for r in rows:
            if r["band"] in ("(35,37.5]", "(37.5,40]"):
                near[r["date"]].append(r["fwd"][str(h)] - r["spy"][str(h)])
            elif r["band"] == "<=35 QUALIFIES":
                qual[r["date"]].append(r["fwd"][str(h)] - r["spy"][str(h)])
        both = sorted(set(near) & set(qual))
        print("\n  {0}-session horizon".format(h))
        print("    {0:<8} {1:>7} {2:>12} {3:>12} {4:>8}".format(
            "period", "days", "mean diff", "median", "win"))
        thirds[h] = {}
        for name, sel in (("early", lambda d: d < cuts[0]),
                          ("middle", lambda d: cuts[0] <= d < cuts[1]),
                          ("late", lambda d: d >= cuts[1])):
            ds = [d for d in both if sel(d)]
            if len(ds) < 40:
                continue
            v = [fmean(near[d]) - fmean(qual[d]) for d in ds]
            thirds[h][name] = {"days": len(v), "mean": fmean(v),
                               "win": sum(1 for x in v if x > 0) / len(v)}
            print("    {0:<8} {1:>7,} {2:>12.4%} {3:>12.4%} {4:>8.1%}".format(
                name, len(v), fmean(v), median(v),
                sum(1 for x in v if x > 0) / len(v)))

    # ---- 4. how much bigger would the candidate pool get? --------------
    print("\n" + "=" * 76)
    print("4. WHAT RELAXING TO RSI 40 WOULD ACTUALLY DO TO THE FUNNEL")
    print("=" * 76)
    counts = defaultdict(int)
    for r in rows:
        counts[r["band"]] += 1
    q = counts["<=35 QUALIFIES"]
    extra = counts["(35,37.5]"] + counts["(37.5,40]"]
    print("  qualifying today (RSI<=35)        {0:,}".format(q))
    print("  would be added by RSI<=40         {0:,}".format(extra))
    print("  new pool                          {0:,}  ({1:.2f}x)".format(
        q + extra, (q + extra) / q))
    print("\n  This is NOT {0:.2f}x the trades. The bucket forensics found"
          .format((q + extra) / q))
    print("  59.5% of today's candidates are already blocked as correlated")
    print("  duplicates, and raising the per-bucket cap cost 27.8 points of")
    print("  return and breached the drawdown ceiling. A larger pool competes")
    print("  for the SAME slots. Whether that improves SELECTION within the")
    print("  slots is a different question from whether it adds trades, and")
    print("  this pass does not answer it.")

    out_path = REPO / "docs" / "phase5" / "breadth-significance.json"
    out_path.write_text(json.dumps({
        "FORENSIC_NON_PROMOTIONAL": True,
        "per_session": out, "paired": paired, "paired_thirds": thirds,
        "pool": {"qualifying": q, "added_to_40": extra,
                 "multiple": (q + extra) / q},
        "note": "READ-ONLY. Clustering-aware restatement of the band table.",
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out_path.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
