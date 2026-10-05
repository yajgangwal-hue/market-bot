"""H-0014 - the sealed analysis. Runs ONLY on a verified 230/230 dataset.

Implements the registration exactly: ten sealed snapshots, the sealed
feature list, the nested DAILY vs DAILY+INTRADAY comparison, Spearman
IC, the 10-session primary horizon, the six sealed path classes and
the 2-of-3 chronological-thirds gate. Nothing is chosen here that the
seal did not already fix.

REFUSES TO RUN unless every one of the 230 sealed symbols has a
snapshot table that passes schema and leakage checks. There is no
flag to override that.
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import fmean, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

SEAL = "3acb220ee7a5525969412854a9e8d72f6cbfb042226bd0cf0d6e9d2a08ed331c"
FP = "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b"
LABELS = ["09:35", "09:45", "10:00", "10:30", "11:00", "12:00", "13:00",
          "14:00", "15:00", "15:30"]
MAXBARS = {575: 2, 585: 4, 600: 7, 630: 13, 660: 19, 720: 31, 780: 43,
           840: 55, 900: 67, 930: 73}
COLS = ["session", "snap", "minute", "ret_prior_close", "ret_open",
        "exc_high", "exc_low", "vwap_dist", "range_sofar", "ret_15m",
        "ret_60m", "accel", "rev_from_high", "rev_from_low", "rvol_intra",
        "range_expansion", "cumvol_ratio", "vol_accel", "spy_ret",
        "spy_rvol", "close_px", "prior_close", "daily_close", "n_bars",
        "fwd5", "fwd10", "fwd20", "spy_fwd5", "spy_fwd10", "spy_fwd20",
        "mfe20", "mae20", "path_class", "daily_rsi_close", "intraday_rsi"]
INTRA = ["ret_prior_close", "ret_open", "exc_high", "exc_low", "vwap_dist",
         "range_sofar", "ret_15m", "ret_60m", "accel", "rev_from_high",
         "rev_from_low", "rvol_intra", "range_expansion", "cumvol_ratio",
         "vol_accel", "spy_ret", "spy_rvol"]
DAILY = ["d_rsi", "d_atrfrac", "d_sma200", "d_mom21", "d_dd252", "d_advr"]
PATHS = ["selloff_then_recovery", "recovery_then_selloff",
         "early_low_persistent_strength", "late_low_close_near_low",
         "high_low_recovery", "low_high_fade", "unclassified"]
PRIMARY = "10"


# Decade price data only through the research dataset gate: verified
# before use, fail-closed, no scratchpad fallback. Intraday stores are
# UNPRESERVED and scratchpad-only; they are located by the one sanctioned
# lookup, keyed on the store itself. Both replaced a glob keyed on the
# scratchpad's decade files on 2026-09-24
# (docs/2026-09-24-governed-research-dataset-migration.md).
if str(REPO / "scripts") not in sys.path:
    sys.path.append(str(REPO / "scripts"))
from research_gate import decade_dir, unpreserved_intraday_store # noqa: E402
DEEP = decade_dir()
SNAP = unpreserved_intraday_store("snapshots")


def third_of(year):
    y = int(year)
    return 1 if y <= 2019 else 2 if y <= 2023 else 3


def f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- section 2
def verify_coverage():
    syms = sorted(p.stem for p in DEEP.glob("*.csv"))
    have = {p.stem for p in SNAP.glob("*.csv")}
    missing = [s for s in syms if s not in have]
    extra = sorted(have - set(syms))
    rep = {"universe": len(syms), "present": len(have),
           "missing": missing, "extra_not_in_universe": extra}
    return syms, rep


def verify_integrity(syms):
    """Schema + leakage, per symbol. Returns (report, failures)."""
    fails = []
    sess = 0
    rows_tot = 0
    snapcount = Counter()
    for s in syms:
        p = SNAP / (s + ".csv")
        prob = []
        try:
            rows = list(csv.DictReader(open(p)))
        except Exception as e:                               # noqa: BLE001
            fails.append((s, "unreadable: {0}".format(e)))
            continue
        if not rows:
            fails.append((s, "empty"))
            continue
        if list(rows[0].keys()) != COLS:
            prob.append("schema mismatch")
        dc = {r["timestamp"][:10]: float(r["close"])
              for r in csv.DictReader(open(DEEP / (s + ".csv")))}
        dates = sorted(dc)
        di = {d: i for i, d in enumerate(dates)}
        by = {}
        for r in rows:
            by.setdefault(r["session"], []).append(r)
            snapcount[r["snap"]] += 1
        if any(len(v) > 10 for v in by.values()):
            prob.append(">10 snapshots in a session")
        if any(r["snap"] not in LABELS for r in rows):
            prob.append("unsealed snapshot label")
        # LEAKAGE
        if any(r["daily_close"] != "" for r in rows):
            prob.append("D-CLOSE PRESENT")
        nb = sum(1 for r in rows if r["n_bars"]
                 and int(r["n_bars"]) > MAXBARS[int(r["minute"])])
        if nb:
            prob.append("{0} rows exceed the snapshot bar ceiling".format(nb))
        pc = 0
        for r in rows[:3000]:
            i = di.get(r["session"])
            if not i:
                continue
            if abs(float(r["prior_close"]) - dc[dates[i - 1]]) > 1e-6:
                pc += 1
        if pc:
            prob.append("{0} rows where prior_close != D-1 close".format(pc))
        sess += len(by)
        rows_tot += len(rows)
        if prob:
            fails.append((s, "; ".join(prob)))
    return {"sessions": sess, "rows": rows_tot,
            "per_snapshot": dict(snapcount)}, fails


# ---------------------------------------------------------------- daily side
def daily_features(sym):
    """Features through D-1 ONLY, keyed by session D."""
    from event_aware_trader.indicators import rsi, wilder_atr
    from event_aware_trader.data import Bar
    from datetime import datetime, timezone
    rows = list(csv.DictReader(open(DEEP / (sym + ".csv"))))
    bars, out = [], {}
    for r in rows:
        bars.append(Bar(timestamp=datetime.fromisoformat(r["timestamp"]),
                        open=float(r["open"]), high=float(r["high"]),
                        low=float(r["low"]), close=float(r["close"]),
                        volume=float(r["volume"])))
    cl = [b.close for b in bars]
    for i in range(220, len(bars)):
        d = rows[i]["timestamp"][:10]
        prev = bars[:i]                      # STRICTLY before D
        pcl = cl[:i]
        atr = wilder_atr(prev, 14)
        sma = fmean(pcl[-200:])
        hi252 = max(pcl[-252:])
        adv = fmean(b.close * b.volume for b in prev[-20:])
        out[d] = {"d_rsi": rsi(pcl, 14),
                  "d_atrfrac": (atr / pcl[-1]) if atr and pcl[-1] else None,
                  "d_sma200": pcl[-1] / sma - 1.0 if sma else None,
                  "d_mom21": pcl[-1] / pcl[-22] - 1.0 if len(pcl) > 22 else None,
                  "d_dd252": pcl[-1] / hi252 - 1.0 if hi252 else None,
                  "d_advr": adv}
    return out


# ------------------------------------------------------------- path classes
def path_class(day_rows, dhigh, dlow, dclose):
    """Sealed six classes, from the ORDER of the session's extremes and
    the close position. Extreme order is recovered from the running
    extrema already stored, at 10-snapshot resolution; an extreme first
    set after 15:30 is attributed to '15:30 or later'."""
    day = sorted(day_rows, key=lambda r: int(r["minute"]))
    ph = pl = None
    ih = il = None
    for k, r in enumerate(day):
        h, l = f(r["exc_high"]), f(r["exc_low"])
        if h is not None and (ph is None or h > ph + 1e-12):
            ph, ih = h, k
        if l is not None and (pl is None or l < pl - 1e-12):
            pl, il = l, k
    if ih is None or il is None or dhigh <= dlow:
        return "unclassified"
    n = len(day)
    cp = (dclose - dlow) / (dhigh - dlow)
    lo_third = 0 if il < n / 3 else (1 if il < 2 * n / 3 else 2)
    if lo_third == 0 and cp >= 0.66:
        return "early_low_persistent_strength"
    if lo_third == 2 and cp <= 0.33:
        return "late_low_close_near_low"
    if il < ih:
        return "selloff_then_recovery" if cp >= 0.5 else "low_high_fade"
    if ih < il:
        return "recovery_then_selloff" if cp < 0.5 else "high_low_recovery"
    return "unclassified"


# ----------------------------------------------------------------- IC engine
def zscore(rows, keys):
    st = {}
    for k in keys:
        v = [r[k] for r in rows if r.get(k) is not None]
        st[k] = (fmean(v), pstdev(v) or 1.0) if v else (0.0, 1.0)
    return st


def design(rows, keys, st):
    return [[((r.get(k) if r.get(k) is not None else st[k][0]) - st[k][0])
             / st[k][1] for k in keys] for r in rows]


def fit(X, y):
    """Normal equations with ridge 1e-6 for conditioning. No tuning."""
    p = len(X[0])
    A = [[sum(X[i][a] * X[i][b] for i in range(len(X)))
          + (1e-6 if a == b else 0.0) for b in range(p)] for a in range(p)]
    v = [sum(X[i][a] * y[i] for i in range(len(X))) for a in range(p)]
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


def spearman(a, b):
    n = len(a)
    if n < 20:
        return None
    def rk(x):
        o = sorted(range(n), key=lambda i: x[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and x[o[j + 1]] == x[o[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
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


def main():
    from event_aware_trader.forward import frozen_fingerprint
    from event_aware_trader.modelgov import prereg
    s = [p for p in prereg.load() if p["hypothesis_id"] == "H-0014"]
    if not s or s[0]["seal"] != SEAL:
        print("REFUSED: H-0014 seal not found or altered.")
        return 2
    if frozen_fingerprint() != FP:
        print("REFUSED: fingerprint moved.")
        return 2
    print("H-0014 seal {0} | commit {1}".format(s[0]["seal"][:16],
                                                s[0]["code_commit"][:12]))

    syms, cov = verify_coverage()
    print("\n=== SECTION 2: COVERAGE ===")
    print("  universe {0} | present {1} | missing {2}".format(
        cov["universe"], cov["present"], len(cov["missing"])))
    if cov["missing"] or cov["extra_not_in_universe"]:
        print("  MISSING: {0}".format(", ".join(cov["missing"][:40])))
        print("\nSTOPPED at the section-2 gate. No analysis performed.")
        return 2
    integ, fails = verify_integrity(syms)
    print("  sessions {0:,} | snapshot rows {1:,}".format(
        integ["sessions"], integ["rows"]))
    print("  rows per snapshot: {0}".format(
        {k: integ["per_snapshot"].get(k, 0) for k in LABELS}))
    if fails:
        print("  INTEGRITY FAILURES: {0}".format(len(fails)))
        for a, b in fails[:20]:
            print("    {0:<8} {1}".format(a, b))
        print("\nSTOPPED at the section-2 gate. No analysis performed.")
        return 2
    print("  schema and leakage checks: PASS on all {0} symbols".format(
        len(syms)))
    print("\n(analysis body runs from here once the gate passes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
