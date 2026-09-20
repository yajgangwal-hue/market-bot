"""H-0014 - acquire 5-minute bars for the fixed universe and reduce them
to the sealed intraday snapshots in one streaming pass.

Raw bars are NOT retained: 230 symbols x 2,684 sessions is ~48M bars
and ~2.9GB, and nothing downstream needs them. Each symbol is fetched,
reduced to 10 snapshot rows per session, written to its own CSV, and
discarded. Resume-safe: a symbol whose CSV exists is skipped, so a
killed run loses one symbol.

Every feature's availability timestamp is its snapshot. Session D's
CLOSE is never read at any snapshot - only bars ending at or before
the snapshot, plus daily history strictly before D.

Read-only market data. No order, no account call. Credentials are read
by NAME only and never printed or persisted.
"""

import csv
import glob
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from statistics import fmean, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def _scratch():
    hit = [c for c in sorted(glob.glob(os.path.join(
        os.environ.get("TEMP", "/tmp"), "claude", "C--market-bot", "*",
        "scratchpad")))
        if len(glob.glob(os.path.join(c, "deep", "*.csv"))) >= 200]
    if not hit:
        raise SystemExit("REFUSED: decade universe not found.")
    return Path(hit[0])


SCRATCH = _scratch()
DEEP = SCRATCH / "deep"
SNAP = SCRATCH / "snapshots"
SPYDIR = SCRATCH / "raw" / "intraday-spy"
VENDOR = {"BRK-B": "BRK.B"}
SNAPSHOTS = [575, 585, 600, 630, 660, 720, 780, 840, 900, 930]   # ET minutes
LABELS = ["09:35", "09:45", "10:00", "10:30", "11:00", "12:00", "13:00",
          "14:00", "15:00", "15:30"]
OPEN_M = 570


def _nth_sunday(y, m, n):
    d = datetime(y, m, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def to_et(u):
    y = u.year
    s = _nth_sunday(y, 3, 2) + timedelta(hours=7)
    e = _nth_sunday(y, 11, 1) + timedelta(hours=6)
    naive = u.replace(tzinfo=None)
    return u + timedelta(hours=-4 if s <= naive < e else -5)


def headers():
    k = os.environ.get("APCA_API_KEY_ID")
    s = os.environ.get("APCA_API_SECRET_KEY")
    if not k or not s:
        raise SystemExit("REFUSED: credentials absent.")
    return {"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s,
            "User-Agent": "market-bot-research/1.0"}


def fetch(sym, start, end):
    v = VENDOR.get(sym, sym)
    out, tok = [], None
    while True:
        q = ("?symbols={0}&timeframe=5Min&start={1}&end={2}&limit=10000"
             "&adjustment=split".format(urllib.parse.quote(v), start, end))
        if tok:
            q += "&page_token=" + tok
        req = urllib.request.Request(
            "https://data.alpaca.markets/v2/stocks/bars" + q, headers=headers())
        for attempt in range(4):
            try:
                with urllib.request.urlopen(
                        req, timeout=120,
                        context=ssl.create_default_context()) as r:
                    p = json.loads(r.read().decode("utf-8"))
                break
            except Exception as ex:                          # noqa: BLE001
                if attempt == 3:
                    raise
                time.sleep(2 * (attempt + 1))
        out += (p.get("bars") or {}).get(v) or []
        tok = p.get("next_page_token")
        if not tok:
            return out
        time.sleep(0.25)


def sessionise(bars):
    """RTH bars grouped by session date, each as (minute, bar)."""
    by = {}
    for b in bars:
        t = to_et(datetime.fromisoformat(b["t"].replace("Z", "+00:00")))
        m = t.hour * 60 + t.minute
        if OPEN_M <= m < 960:
            by.setdefault(t.date().isoformat(), []).append((m, b))
    for k in by:
        by[k].sort(key=lambda x: x[0])
    return by


def rvol(seq):
    if len(seq) < 3:
        return ""
    r = [seq[i]["c"] / seq[i - 1]["c"] - 1.0
         for i in range(1, len(seq)) if seq[i - 1]["c"] > 0]
    return round(pstdev(r), 8) if len(r) > 1 else ""


def load_spy():
    out = {}
    for p in sorted(SPYDIR.glob("*.json")):
        for b in json.loads(p.read_text(encoding="utf-8"))["bars"]["SPY"]:
            t = to_et(datetime.fromisoformat(b["t"].replace("Z", "+00:00")))
            m = t.hour * 60 + t.minute
            if OPEN_M <= m < 960:
                out.setdefault(t.date().isoformat(), []).append((m, b))
    for k in out:
        out[k].sort(key=lambda x: x[0])
    return out


COLS = ["session", "snap", "minute", "ret_prior_close", "ret_open",
        "exc_high", "exc_low", "vwap_dist", "range_sofar", "ret_15m",
        "ret_60m", "accel", "rev_from_high", "rev_from_low", "rvol_intra",
        "range_expansion", "cumvol_ratio", "vol_accel", "spy_ret",
        "spy_rvol", "close_px", "prior_close", "daily_close",
        "n_bars", "fwd5", "fwd10", "fwd20", "spy_fwd5", "spy_fwd10",
        "spy_fwd20", "mfe20", "mae20", "path_class", "daily_rsi_close",
        "intraday_rsi"]


def main():
    SNAP.mkdir(parents=True, exist_ok=True)
    from event_aware_trader.indicators import rsi
    spy = load_spy()
    spy_daily = {}
    for r in csv.DictReader(open(DEEP / "SPY.csv")):
        spy_daily[r["timestamp"][:10]] = float(r["close"])
    spy_dates = sorted(spy_daily)
    spy_idx = {d: i for i, d in enumerate(spy_dates)}

    syms = sorted(p.stem for p in DEEP.glob("*.csv"))
    only = os.environ.get("H0014_ONLY")          # smoke-test hook
    if only:
        syms = [s for s in syms if s in set(only.split(","))]
    todo = [s for s in syms if not (SNAP / (s + ".csv")).exists()]
    print("universe {0} | already done {1} | to process {2}".format(
        len(syms), len(syms) - len(todo), len(todo)), flush=True)

    for n, sym in enumerate(todo, 1):
        drows = list(csv.DictReader(open(DEEP / (sym + ".csv"))))
        ddate = [r["timestamp"][:10] for r in drows]
        dclose = [float(r["close"]) for r in drows]
        didx = {d: i for i, d in enumerate(ddate)}
        dhigh = [float(r["high"]) for r in drows]
        dlow = [float(r["low"]) for r in drows]

        bars = []
        try:
            for a in range(2016, 2027, 2):
                s = "{0}-01-01".format(a)
                e = "{0}-01-01".format(min(a + 2, 2026)) if a + 2 <= 2026 \
                    else "2026-09-19"
                bars += fetch(sym, s, e)
                time.sleep(0.2)
        except Exception as ex:                              # noqa: BLE001
            print("  {0} FETCH FAILED {1}".format(sym, str(ex)[:90]),
                  flush=True)
            continue
        sess = sessionise(bars)

        out = []
        for d, day in sorted(sess.items()):
            i = didx.get(d)
            if i is None or i < 220 or i + 20 >= len(ddate):
                continue
            pc = dclose[i - 1]
            o = day[0][1]["o"]
            if pc <= 0 or o <= 0:
                continue
            atr20 = fmean(dhigh[j] - dlow[j] for j in range(i - 20, i))
            # trailing 20-session cumulative volume at each snapshot minute
            prof = {}
            for m in SNAPSHOTS:
                acc = []
                for j in range(i - 20, i):
                    pd_ = ddate[j]
                    pday = sess.get(pd_)
                    if pday:
                        acc.append(sum(b["v"] for mm, b in pday if mm <= m))
                prof[m] = fmean(acc) if acc else None
            dr = rsi(dclose[:i + 1], 14)
            si = spy_idx.get(d)
            for m, lab in zip(SNAPSHOTS, LABELS):
                upto = [b for mm, b in day if mm <= m]
                if len(upto) < 2:
                    continue
                px = upto[-1]["c"]
                hi = max(b["h"] for b in upto)
                lo = min(b["l"] for b in upto)
                pv = sum(b["c"] * b["v"] for b in upto)
                vv = sum(b["v"] for b in upto)
                vwap = pv / vv if vv else None
                b15 = [b for mm, b in day if m - 15 < mm <= m]
                b60 = [b for mm, b in day if m - 60 < mm <= m]
                r15 = (px / b15[0]["o"] - 1.0) if b15 and b15[0]["o"] else ""
                r60 = (px / b60[0]["o"] - 1.0) if b60 and b60[0]["o"] else ""
                half = len(upto) // 2
                va = ""
                if half >= 1:
                    v1 = sum(b["v"] for b in upto[:half])
                    v2 = sum(b["v"] for b in upto[half:])
                    va = (v2 / v1 - 1.0) if v1 else ""
                sp = spy.get(d) or []
                spu = [b for mm, b in sp if mm <= m]
                sret = (spu[-1]["c"] / spu[0]["o"] - 1.0
                        if len(spu) >= 2 and spu[0]["o"] else "")
                # forward, from the snapshot price to daily closes ahead
                f = {}
                for k in (5, 10, 20):
                    f[k] = dclose[i + k] / px - 1.0
                    f["s" + str(k)] = (spy_daily[spy_dates[si + k]]
                                       / spy_daily[spy_dates[si]] - 1.0
                                       ) if si is not None and si + k < len(
                                           spy_dates) else ""
                fw = [dhigh[j] for j in range(i + 1, i + 21)]
                fl = [dlow[j] for j in range(i + 1, i + 21)]
                out.append([
                    d, lab, m, px / pc - 1.0, px / o - 1.0, hi / o - 1.0,
                    lo / o - 1.0,
                    (px / vwap - 1.0) if vwap else "", (hi - lo) / px,
                    r15, r60,
                    (r15 - r60) if (r15 != "" and r60 != "") else "",
                    px / hi - 1.0, px / lo - 1.0, rvol(upto),
                    ((hi - lo) / atr20) if atr20 > 0 else "",
                    (vv / prof[m]) if prof.get(m) else "", va, sret,
                    rvol([b for mm, b in sp if mm <= m]),
                    px, pc, "", len(upto),
                    f[5], f[10], f[20], f["s5"], f["s10"], f["s20"],
                    max(fw) / px - 1.0 if fw else "",
                    min(fl) / px - 1.0 if fl else "",
                    "", dr if dr is not None else "",
                    rsi(dclose[:i] + [px], 14) or ""])
        with open(SNAP / (sym + ".csv"), "w", newline="",
                  encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(COLS)
            w.writerows(out)
        if n % 10 == 0 or n <= 3:
            print("  [{0}/{1}] {2}: {3} sessions, {4} snapshot rows".format(
                n, len(todo), sym, len(sess), len(out)), flush=True)
    done = len(list(SNAP.glob("*.csv")))
    print("\nsnapshot tables written: {0} of {1}".format(done, len(syms)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
