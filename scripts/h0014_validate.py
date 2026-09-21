"""H-0014 - validate snapshot tables against the sealed schema.

Usage:
  python scripts/h0014_validate.py            validate every present symbol
  python scripts/h0014_validate.py SYM [SYM]  validate only those

Checks, all of them leakage-relevant:
  - 35 sealed columns, exact order
  - only sealed snapshot labels, at most ten per session
  - daily_close column EMPTY   (session D's close is never read)
  - no snapshot carries more bars than its time of day permits
  - prior_close equals the D-1 daily close

Exits non-zero if any symbol fails. Never modifies data.
"""

import csv
import glob
import os
import sys
from pathlib import Path

COLS = ["session", "snap", "minute", "ret_prior_close", "ret_open",
        "exc_high", "exc_low", "vwap_dist", "range_sofar", "ret_15m",
        "ret_60m", "accel", "rev_from_high", "rev_from_low", "rvol_intra",
        "range_expansion", "cumvol_ratio", "vol_accel", "spy_ret",
        "spy_rvol", "close_px", "prior_close", "daily_close", "n_bars",
        "fwd5", "fwd10", "fwd20", "spy_fwd5", "spy_fwd10", "spy_fwd20",
        "mfe20", "mae20", "path_class", "daily_rsi_close", "intraday_rsi"]
LABELS = {"09:35", "09:45", "10:00", "10:30", "11:00", "12:00", "13:00",
          "14:00", "15:00", "15:30"}
MAXBARS = {575: 2, 585: 4, 600: 7, 630: 13, 660: 19, 720: 31, 780: 43,
           840: 55, 900: 67, 930: 73}


def scratch():
    hit = [c for c in sorted(glob.glob(os.path.join(
        os.environ.get("TEMP", "/tmp"), "claude", "C--market-bot", "*",
        "scratchpad")))
        if len(glob.glob(os.path.join(c, "deep", "*.csv"))) >= 200]
    if not hit:
        raise SystemExit("REFUSED: decade universe not found.")
    return Path(hit[0])


def validate(sym, snap, deep):
    p = snap / (sym + ".csv")
    if not p.exists():
        return ["missing file"], 0, 0
    rows = list(csv.DictReader(open(p)))
    if not rows:
        return ["empty"], 0, 0
    prob = []
    if list(rows[0].keys()) != COLS:
        prob.append("schema mismatch ({0} cols)".format(len(rows[0])))
    dc = {r["timestamp"][:10]: float(r["close"])
          for r in csv.DictReader(open(deep / (sym + ".csv")))}
    dates = sorted(dc)
    di = {d: i for i, d in enumerate(dates)}
    by = {}
    for r in rows:
        by.setdefault(r["session"], []).append(r)
    if any(len(v) > 10 for v in by.values()):
        prob.append(">10 snapshots in a session")
    if any(r["snap"] not in LABELS for r in rows):
        prob.append("unsealed snapshot label")
    if any(r["daily_close"] != "" for r in rows):
        prob.append("D-CLOSE PRESENT (leak)")
    nb = sum(1 for r in rows if r["n_bars"]
             and int(r["n_bars"]) > MAXBARS[int(r["minute"])])
    if nb:
        prob.append("{0} rows exceed the snapshot bar ceiling".format(nb))
    pc = 0
    for r in rows:
        i = di.get(r["session"])
        if not i:
            continue
        if abs(float(r["prior_close"]) - dc[dates[i - 1]]) > 1e-6:
            pc += 1
    if pc:
        prob.append("{0} rows where prior_close != D-1 close".format(pc))
    return prob, len(rows), len(by)


def main():
    scr = scratch()
    snap, deep = scr / "snapshots", scr / "deep"
    universe = sorted(p.stem for p in deep.glob("*.csv"))
    want = sys.argv[1:] or sorted(p.stem for p in snap.glob("*.csv"))
    outside = [s for s in want if s not in universe]
    if outside:
        print("REFUSED: not in the sealed universe: {0}".format(outside))
        return 2
    bad, rows, sess = [], 0, 0
    for s in want:
        prob, n, k = validate(s, snap, deep)
        rows += n
        sess += k
        if prob:
            bad.append((s, "; ".join(prob)))
    print("  symbols validated : {0}".format(len(want)))
    print("  passed            : {0}".format(len(want) - len(bad)))
    print("  failed            : {0}".format(len(bad)))
    print("  snapshot rows     : {0:,}".format(rows))
    print("  sessions          : {0:,}".format(sess))
    for s, w in bad:
        print("    FAIL {0:<8} {1}".format(s, w))
    if not bad:
        print("  all conform: sealed columns, sealed snapshot labels, "
              "daily_close EMPTY,")
        print("  no snapshot over its bar ceiling, prior_close == D-1 close")
    print("  coverage          : {0}/{1} of the sealed universe".format(
        len(list(snap.glob("*.csv"))), len(universe)))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
