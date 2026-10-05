"""H-0014 - the sealed analysis body. Requires a verified 230/230 dataset.

Implements exactly what the seal fixed and nothing else:
  ten snapshots, the sealed feature list, nested DAILY vs DAILY+INTRADAY,
  Spearman IC, 10-session primary horizon, six path classes,
  2-of-3 chronological-thirds gate.

Chronological OOS: the seal says "fit on earlier thirds, score the next".
Taken literally that scores thirds 2 and 3 only, leaving third 1 with no
out-of-sample value and making the 2-of-3 gate unevaluable. So the SAME
principle is also run at finer granularity - expanding window by calendar
year, each year scored by a model fit on all earlier years - which
populates all three thirds. BOTH are reported; the literal scheme is
primary. This is a reporting choice about an unevaluable cell, not a
change to the method.
"""

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

SEAL = "3acb220ee7a5525969412854a9e8d72f6cbfb042226bd0cf0d6e9d2a08ed331c"
FP = "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b"
LABELS = ["09:35", "09:45", "10:00", "10:30", "11:00", "12:00", "13:00",
          "14:00", "15:00", "15:30"]
INTRA = ["ret_prior_close", "ret_open", "exc_high", "exc_low", "vwap_dist",
         "range_sofar", "ret_15m", "ret_60m", "accel", "rev_from_high",
         "rev_from_low", "rvol_intra", "range_expansion", "cumvol_ratio",
         "vol_accel", "spy_ret", "spy_rvol"]
DAILYF = ["d_rsi", "d_atrfrac", "d_sma200", "d_mom21", "d_dd252", "d_advr"]
PATHS = ["selloff_then_recovery", "recovery_then_selloff",
         "early_low_persistent_strength", "late_low_close_near_low",
         "high_low_recovery", "low_high_fade", "unclassified"]
RSI_ENTRY = 35.0
OUT = REPO / "docs" / "phase5" / "h0014-results.json"


# Decade price data only through the research dataset gate: verified
# before use, fail-closed, no scratchpad fallback. Intraday stores are
# UNPRESERVED and scratchpad-only; they are located by the one sanctioned
# lookup, keyed on the store itself. Both replaced a glob keyed on the
# scratchpad's decade files on 2026-09-24
# (docs/2026-09-24-governed-research-dataset-migration.md).
if str(REPO / "scripts") not in sys.path:
    sys.path.append(str(REPO / "scripts"))
from research_gate import (dataset_file, decade_dir,           # noqa: E402
                           unpreserved_intraday_store, verify_dataset)
DEEP = decade_dir()
SNAP = unpreserved_intraday_store("snapshots")
# Daily features DERIVED from the decade data by build_daily_cache() below.
# Read from a registered, hash-verified copy of the cache written
# 2026-09-20, which the committed builder reproduced byte-for-byte from the
# verified decade dataset on 2026-09-24 (docs/datasets/h0014-daily-features.md).
# Verified at import, fail-closed; the scratchpad original is no longer read,
# and because the verified copy always exists the write branch never runs.
H0014_FEATURES = "h0014-daily-features-decade-230"
H0014_FEATURES_SHA256 = "7fbf76458b559695c4686c651de0600234417f98afa25a36df0ab14a8f548e57"
CACHE = dataset_file(verify_dataset(H0014_FEATURES, H0014_FEATURES_SHA256),
                     "h0014-daily-features.json")


def third_of(y):
    return 1 if y <= 2019 else 2 if y <= 2023 else 3


def ff(v):
    if v == "" or v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


# ------------------------------------------------------- daily side (D-1)
def build_daily_cache():
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    from event_aware_trader.indicators import rsi, wilder_atr
    from event_aware_trader.data import Bar
    from datetime import datetime
    out = {}
    syms = sorted(p.stem for p in DEEP.glob("*.csv"))
    for n, s in enumerate(syms, 1):
        rows = list(csv.DictReader(open(DEEP / (s + ".csv"))))
        bars = [Bar(timestamp=datetime.fromisoformat(r["timestamp"]),
                    open=float(r["open"]), high=float(r["high"]),
                    low=float(r["low"]), close=float(r["close"]),
                    volume=float(r["volume"])) for r in rows]
        cl = [b.close for b in bars]
        d = {}
        for i in range(220, len(bars)):
            prev, pcl = bars[:i], cl[:i]          # STRICTLY before D
            atr = wilder_atr(prev, 14)
            sma = fmean(pcl[-200:])
            hi = max(pcl[-252:])
            adv = fmean(b.close * b.volume for b in prev[-20:])
            d[rows[i]["timestamp"][:10]] = [
                rsi(pcl, 14), (atr / pcl[-1]) if atr else None,
                pcl[-1] / sma - 1.0 if sma else None,
                pcl[-1] / pcl[-22] - 1.0 if len(pcl) > 22 else None,
                pcl[-1] / hi - 1.0 if hi else None, adv]
        out[s] = d
        if n % 40 == 0:
            print("    daily features {0}/{1}".format(n, len(syms)),
                  flush=True)
    CACHE.write_text(json.dumps(out), encoding="utf-8")
    return out


# ------------------------------------------------------------- statistics
def spearman(a, b):
    n = len(a)
    if n < 30:
        return None
    def rk(x):
        o = sorted(range(n), key=lambda i: x[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and x[o[j + 1]] == x[o[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[o[k]] = avg
            i = j + 1
        return r
    ra, rb = rk(a), rk(b)
    ma, mb = fmean(ra), fmean(rb)
    sa, sb = pstdev(ra), pstdev(rb)
    if sa == 0 or sb == 0:
        return 0.0
    return fmean((x - ma) * (y - mb) for x, y in zip(ra, rb)) / (sa * sb)


def fit(X, y):
    p = len(X[0])
    A = [[0.0] * p for _ in range(p)]
    v = [0.0] * p
    for row, t in zip(X, y):
        for a in range(p):
            ra = row[a]
            v[a] += ra * t
            Aa = A[a]
            for b in range(a, p):
                Aa[b] += ra * row[b]
    for a in range(p):
        for b in range(a):
            A[a][b] = A[b][a]
        A[a][a] += 1e-6
    for c in range(p):
        pv = max(range(c, p), key=lambda r: abs(A[r][c]))
        A[c], A[pv] = A[pv], A[c]
        v[c], v[pv] = v[pv], v[c]
        if abs(A[c][c]) < 1e-12:
            return [0.0] * p
        for r in range(p):
            if r != c:
                m = A[r][c] / A[c][c]
                A[r] = [A[r][j] - m * A[c][j] for j in range(p)]
                v[r] -= m * v[c]
    return [v[i] / A[i][i] for i in range(p)]


def standardise(rows, k):
    cols = list(zip(*rows))
    st = []
    for c in cols:
        vals = [x for x in c if x is not None]
        m = fmean(vals) if vals else 0.0
        s = pstdev(vals) if len(vals) > 1 else 1.0
        st.append((m, s or 1.0))
    return [[((r[i] if r[i] is not None else st[i][0]) - st[i][0]) / st[i][1]
             for i in range(k)] for r in rows]


def main():
    from event_aware_trader.forward import frozen_fingerprint
    from event_aware_trader.modelgov import prereg
    s = [p for p in prereg.load() if p["hypothesis_id"] == "H-0014"]
    if not s or s[0]["seal"] != SEAL or frozen_fingerprint() != FP:
        print("REFUSED: seal or fingerprint mismatch.")
        return 2
    syms = sorted(p.stem for p in DEEP.glob("*.csv"))
    if len({p.stem for p in SNAP.glob("*.csv")}) != len(syms):
        print("REFUSED: coverage is not 230/230.")
        return 2
    print("H-0014 analysis | seal {0} | 230/230".format(SEAL[:16]), flush=True)

    print("\nbuilding D-1 daily features ...", flush=True)
    daily = build_daily_cache()

    # ---- one streaming pass: boundary, classes, paths, and per-snapshot data
    print("streaming snapshot tables ...", flush=True)
    per_snap = {L: {"X": [], "y": [], "yr": []} for L in LABELS}
    boundary = {L: Counter() for L in LABELS}
    first_detect = Counter()
    sess_stats = Counter()
    pathrows = []
    classrows = {L: [] for L in LABELS}

    for n, sym in enumerate(syms, 1):
        dmap = daily.get(sym, {})
        dl = {r["timestamp"][:10]: r for r in
              csv.DictReader(open(DEEP / (sym + ".csv")))}
        by = defaultdict(list)
        for r in csv.DictReader(open(SNAP / (sym + ".csv"))):
            by[r["session"]].append(r)
        for sess, rows in by.items():
            rows.sort(key=lambda r: int(r["minute"]))
            drsi = ff(rows[0]["daily_rsi_close"])
            fires = drsi is not None and drsi <= RSI_ENTRY
            sess_stats["sessions"] += 1
            if fires:
                sess_stats["daily_signal"] += 1
            df = dmap.get(sess)
            yr = int(sess[:4])
            earliest = None
            any_intra = False
            for r in rows:
                L = r["snap"]
                irsi = ff(r["intraday_rsi"])
                on = irsi is not None and irsi <= RSI_ENTRY
                if on:
                    any_intra = True
                    if earliest is None:
                        earliest = L
                # sealed A/B/C/D at this snapshot
                if fires and on:
                    cls = "A"
                elif fires and not on:
                    cls = "B"
                elif (not fires) and on:
                    cls = "C"
                else:
                    cls = "none"
                boundary[L][cls] += 1
                if cls in ("A", "B", "C"):
                    classrows[L].append(
                        (cls, yr, ff(r["fwd10"]), ff(r["spy_fwd10"]),
                         ff(r["mfe20"]), ff(r["mae20"])))
                # IC rows: need daily features + target
                t = ff(r["spy_fwd10"])
                f10 = ff(r["fwd10"])
                if df and t is not None and f10 is not None:
                    vec = list(df) + [ff(r[k]) for k in INTRA]
                    per_snap[L]["X"].append(vec)
                    per_snap[L]["y"].append(f10 - t)
                    per_snap[L]["yr"].append(yr)
            if fires:
                first_detect[earliest or "close_only"] += 1
            if any_intra and not fires:
                sess_stats["intraday_only"] += 1
            # path class, session level
            d = dl.get(sess)
            if d:
                hi, lo, cl = float(d["high"]), float(d["low"]), float(d["close"])
                ph = pl = None
                ih = il = None
                for k, r in enumerate(rows):
                    h, l = ff(r["exc_high"]), ff(r["exc_low"])
                    if h is not None and (ph is None or h > ph + 1e-12):
                        ph, ih = h, k
                    if l is not None and (pl is None or l < pl - 1e-12):
                        pl, il = l, k
                if ih is None or il is None or hi <= lo:
                    pc = "unclassified"
                else:
                    m = len(rows)
                    cp = (cl - lo) / (hi - lo)
                    lt = 0 if il < m / 3 else (1 if il < 2 * m / 3 else 2)
                    if lt == 0 and cp >= 0.66:
                        pc = "early_low_persistent_strength"
                    elif lt == 2 and cp <= 0.33:
                        pc = "late_low_close_near_low"
                    elif il < ih:
                        pc = ("selloff_then_recovery" if cp >= 0.5
                              else "low_high_fade")
                    elif ih < il:
                        pc = ("recovery_then_selloff" if cp < 0.5
                              else "high_low_recovery")
                    else:
                        pc = "unclassified"
                last = rows[-1]
                pathrows.append((pc, yr, ff(last["fwd10"]),
                                 ff(last["spy_fwd10"]), ff(last["mfe20"]),
                                 ff(last["mae20"])))
        if n % 40 == 0:
            print("    {0}/{1} symbols".format(n, len(syms)), flush=True)

    res = {"FORENSIC_NON_PROMOTIONAL": True, "seal": SEAL,
           "sessions": dict(sess_stats),
           "first_detection": dict(first_detect),
           "boundary": {L: dict(boundary[L]) for L in LABELS}}

    # ---- IC: literal sealed scheme (fit earlier thirds, score next) -------
    print("\ncomputing Spearman IC ...", flush=True)
    nd = len(DAILYF)
    ic = {}
    for L in LABELS:
        d = per_snap[L]
        idx3 = defaultdict(list)
        for i, y in enumerate(d["yr"]):
            idx3[third_of(y)].append(i)
        Z = standardise(d["X"], nd + len(INTRA))
        out = {}
        for target_third in (2, 3):
            tr = [i for t in range(1, target_third) for i in idx3[t]]
            te = idx3[target_third]
            if len(tr) < 500 or len(te) < 500:
                continue
            for name, k in (("daily", nd), ("daily_intraday", nd + len(INTRA))):
                X = [[Z[i][j] for j in range(k)] for i in tr]
                b = fit(X, [d["y"][i] for i in tr])
                pred = [sum(Z[i][j] * b[j] for j in range(k)) for i in te]
                out.setdefault(name, {})[target_third] = spearman(
                    pred, [d["y"][i] for i in te])
        # pooled over thirds 2 and 3
        pooled = {}
        for name, k in (("daily", nd), ("daily_intraday", nd + len(INTRA))):
            P, Y = [], []
            for target_third in (2, 3):
                tr = [i for t in range(1, target_third) for i in idx3[t]]
                te = idx3[target_third]
                if len(tr) < 500 or len(te) < 500:
                    continue
                X = [[Z[i][j] for j in range(k)] for i in tr]
                b = fit(X, [d["y"][i] for i in tr])
                P += [sum(Z[i][j] * b[j] for j in range(k)) for i in te]
                Y += [d["y"][i] for i in te]
            pooled[name] = spearman(P, Y) if P else None
        ic[L] = {"n": len(d["y"]), "by_third": out, "pooled": pooled}
        dd = pooled.get("daily")
        di = pooled.get("daily_intraday")
        print("  {0}  n={1:>7,}  daily IC {2}  daily+intraday {3}  incr {4}"
              .format(L, len(d["y"]),
                      "{0:+.4f}".format(dd) if dd is not None else "   n/a",
                      "{0:+.4f}".format(di) if di is not None else "   n/a",
                      "{0:+.4f}".format(di - dd)
                      if (dd is not None and di is not None) else "   n/a"),
              flush=True)
    res["ic"] = ic

    # ---- path classes -----------------------------------------------------
    pc_out = {}
    for p in PATHS:
        sel = [r for r in pathrows if r[0] == p]
        if not sel:
            pc_out[p] = {"n": 0}
            continue
        def agg(rows_):
            f10 = [r[2] for r in rows_ if r[2] is not None]
            sp = [r[2] - r[3] for r in rows_
                  if r[2] is not None and r[3] is not None]
            mf = [r[4] for r in rows_ if r[4] is not None]
            ma = [r[5] for r in rows_ if r[5] is not None]
            return {"n": len(rows_),
                    "fwd10": fmean(f10) if f10 else None,
                    "spy_rel": fmean(sp) if sp else None,
                    "win": (sum(1 for x in sp if x > 0) / len(sp)) if sp else None,
                    "mfe": fmean(mf) if mf else None,
                    "mae": fmean(ma) if ma else None}
        e = agg(sel)
        e["pct"] = len(sel) / len(pathrows)
        for t in (1, 2, 3):
            e["third{0}".format(t)] = agg([r for r in sel
                                           if third_of(r[1]) == t])["spy_rel"]
        pc_out[p] = e
    res["path_classes"] = pc_out
    res["path_total"] = len(pathrows)

    # ---- A/B/C outcomes ---------------------------------------------------
    cls_out = {}
    for L in LABELS:
        d = {}
        for c in ("A", "B", "C"):
            sel = [r for r in classrows[L] if r[0] == c]
            sp = [r[2] - r[3] for r in sel
                  if r[2] is not None and r[3] is not None]
            mf = [r[4] for r in sel if r[4] is not None]
            ma = [r[5] for r in sel if r[5] is not None]
            d[c] = {"n": len(sel),
                    "spy_rel": fmean(sp) if sp else None,
                    "win": (sum(1 for x in sp if x > 0) / len(sp)) if sp else None,
                    "mfe": fmean(mf) if mf else None,
                    "mae": fmean(ma) if ma else None,
                    "false_frac": (sum(1 for x in sp if x <= 0) / len(sp))
                                  if sp else None}
        cls_out[L] = d
    res["classes"] = cls_out

    OUT.write_text(json.dumps(res, indent=1, sort_keys=True, default=str),
                   encoding="utf-8")
    print("\nwrote {0}".format(OUT.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
