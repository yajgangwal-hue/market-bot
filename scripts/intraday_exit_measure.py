"""PHASES 4 and 5 - measure the real rule-exit trigger and drift.

WHAT IS BEING MEASURED, AND WHY IT IS NOT THE SAME AS THE HAIRCUT.

The simulator prices `reverted` and `time_exit` at the session CLOSE and
then charges 0.652% because the live bot does not wait for the close - it
sells on whichever 15-minute cycle the rule first fires. That charge has
never been measured against the trades it is charged on. This measures it.

For each of the 459 rule exits the exit session's 5-minute bars are
replayed forward, regular hours only:

  reverted   the live bot recomputes RSI(14) each cycle with the CURRENT
             price standing in for today's close. The trigger is the first
             RTH bar at which that RSI reaches rsi_exit. Prior closes come
             only from sessions STRICTLY BEFORE the exit session.

  time_exit  bars_held >= max_holding_bars is already true when the
             session opens, so the first cycle of the day fires it. The
             trigger is the first RTH bar.

Three drifts are then computed and DELIBERATELY NOT COLLAPSED:

  A trigger -> session close    what the haircut actually models
  B trigger -> next bar open    the earliest realistically tradable print
  C trigger -> conservative     next bar, filled at its LOW (a bad fill)

Sign convention: NEGATIVE means selling at the trigger would have been
BETTER than the comparison price, i.e. the haircut direction.

No strategy is changed. No parameter is recalibrated. Read-only.
"""

import csv
import glob
import json
import os
import statistics as st
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.indicators import rsi                  # noqa: E402
from event_aware_trader.mean_reversion import (                 # noqa: E402
    MeanReversionConfig)


def _scratch_with_deep():
    hit = [c for c in sorted(glob.glob(os.path.join(
        os.environ.get("TEMP", "/tmp"), "claude", "C--market-bot", "*",
        "scratchpad")))
        if len(glob.glob(os.path.join(c, "deep", "*.csv"))) >= 200]
    if not hit:
        raise SystemExit("REFUSED: decade universe not found.")
    return Path(hit[0])


SCRATCH = _scratch_with_deep()
DEEP = SCRATCH / "deep"
RAW = SCRATCH / "raw" / "intraday-exits"
CACHE = REPO / "docs" / "phase5" / "h0011-cache.json"
OUT = REPO / "docs" / "phase5" / "intraday-exit-measurement.json"
HAIRCUT = 0.00652
ONE_WAY = 0.0006


def _nth_sunday(y, m, n):
    d = datetime(y, m, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def to_et(dt_utc):
    """US Eastern. tzdata is not installed here, so the post-2007 rule is
    implemented explicitly: DST from 2nd Sun Mar 02:00 to 1st Sun Nov 02:00."""
    y = dt_utc.year
    start = _nth_sunday(y, 3, 2) + timedelta(hours=7)
    end = _nth_sunday(y, 11, 1) + timedelta(hours=6)
    naive = dt_utc.replace(tzinfo=None)
    return dt_utc + timedelta(hours=-4 if start <= naive < end else -5)


def rth(bars):
    out = []
    for b in bars:
        t = to_et(datetime.fromisoformat(b["t"].replace("Z", "+00:00")))
        m = t.hour * 60 + t.minute
        if 570 <= m < 960:
            out.append((t, b))
    out.sort(key=lambda x: x[0])
    return out


def daily_closes(symbol):
    p = DEEP / (symbol + ".csv")
    if not p.exists():
        return []
    return [(r["timestamp"][:10], float(r["close"]))
            for r in csv.DictReader(open(p))]


def pct(a, b):
    return (a - b) / b if b else None


def dist(v, name):
    v = sorted(x for x in v if x is not None)
    if not v:
        return {"n": 0}
    q = st.quantiles(v, n=10)
    return {"n": len(v), "mean": st.fmean(v), "median": st.median(v),
            "sd": st.pstdev(v) if len(v) > 1 else 0.0,
            "p10": q[0], "p25": st.quantiles(v, n=4)[0],
            "p75": st.quantiles(v, n=4)[2], "p90": q[8],
            "min": v[0], "max": v[-1],
            "worst_decile_mean": st.fmean(v[:max(1, len(v) // 10)]),
            "label": name}


def main():
    store = json.loads(CACHE.read_text(encoding="utf-8"))
    cfg = MeanReversionConfig()
    exits = [t for t in store["BASELINE"]["trades"]
             if t["reason"] in ("reverted", "time_exit")]
    print("PHASES 4-5  rule exits to reconstruct: {0}".format(len(exits)))
    print("  rsi_exit {0} | rsi_period {1} | charged haircut {2:.3%}\n".format(
        cfg.rsi_exit, cfg.rsi_period, HAIRCUT), flush=True)

    recs = []
    missing = nobars = notrigger = 0
    for t in exits:
        f = RAW / "{0}_{1}.json".format(t["symbol"], t["exit"])
        if not f.exists():
            missing += 1
            continue
        payload = json.loads(f.read_text(encoding="utf-8"))
        bars = (payload.get("bars") or {}).get(t["symbol"]) or []
        session = rth(bars)
        if len(session) < 10:
            nobars += 1
            continue
        closes = daily_closes(t["symbol"])
        prior = [c for d, c in closes if d < t["exit"]]
        if len(prior) < cfg.rsi_period + 5:
            missing += 1
            continue
        day_close = session[-1][1]["c"]

        trig_i = None
        if t["reason"] == "time_exit":
            trig_i = 0                      # true the moment the bell rings
        else:
            for i, (_ts, b) in enumerate(session):
                r = rsi(prior + [b["c"]], cfg.rsi_period)
                if r is not None and r >= cfg.rsi_exit:
                    trig_i = i
                    break
        if trig_i is None:
            notrigger += 1
            continue

        ts, tb = session[trig_i]
        tp = tb["c"]
        nxt = session[trig_i + 1][1] if trig_i + 1 < len(session) else None
        after = [b for _s, b in session[trig_i:]]
        recs.append({
            "symbol": t["symbol"], "session": t["exit"], "reason": t["reason"],
            "trigger_et": ts.strftime("%H:%M"),
            "trigger_minutes_from_open": (ts.hour * 60 + ts.minute) - 570,
            "trigger_price": tp, "session_close": day_close,
            "bars_remaining": len(session) - trig_i - 1,
            # A: what the haircut models - trigger vs the close the sim uses
            "A_trigger_to_close": pct(day_close, tp),
            # B: earliest realistically tradable print after the trigger
            "B_trigger_to_next_open": pct(nxt["o"], tp) if nxt else None,
            # C: conservative - next bar, filled at its low
            "C_trigger_to_next_low": pct(nxt["l"], tp) if nxt else None,
            "max_adverse_after": pct(min(b["l"] for b in after), tp),
            "max_favourable_after": pct(max(b["h"] for b in after), tp),
            "session_range_pct": pct(max(b["h"] for b in after),
                                     min(b["l"] for b in after)),
            "volume_after": sum(b["v"] for b in after),
        })

    print("  reconstructed {0} | missing {1} | too few bars {2} | "
          "no intraday trigger {3}".format(len(recs), missing, nobars,
                                           notrigger))
    print("  coverage {0:.1%}\n".format(len(recs) / len(exits)), flush=True)

    res = {"FORENSIC_NON_PROMOTIONAL": True,
           "charged_haircut": HAIRCUT, "one_way": ONE_WAY,
           "exits_in_baseline": len(exits), "reconstructed": len(recs),
           "coverage": len(recs) / len(exits),
           "missing": missing, "too_few_bars": nobars,
           "no_intraday_trigger": notrigger,
           "note": "measurement only; the haircut was NOT changed",
           "records": recs}

    for key, label in (("A_trigger_to_close", "A trigger -> session close"),
                       ("B_trigger_to_next_open", "B trigger -> next bar open"),
                       ("C_trigger_to_next_low", "C trigger -> next bar LOW")):
        res[key] = dist([r[key] for r in recs], label)
        for reason in ("reverted", "time_exit"):
            res[key + "__" + reason] = dist(
                [r[key] for r in recs if r["reason"] == reason], label)
    res["max_adverse_after"] = dist([r["max_adverse_after"] for r in recs], "MAE")
    res["max_favourable_after"] = dist([r["max_favourable_after"] for r in recs],
                                       "MFE")
    # time of day
    buckets = {}
    for r in recs:
        h = int(r["trigger_et"][:2])
        k = ("09:30-10:59" if h < 11 else "11:00-12:59" if h < 13
             else "13:00-14:59" if h < 15 else "15:00-16:00")
        buckets.setdefault(k, []).append(r["A_trigger_to_close"])
    res["by_time_of_day"] = {k: dist(v, k) for k, v in sorted(buckets.items())}
    res["trigger_time_histogram"] = {
        k: len(v) for k, v in sorted(buckets.items())}

    OUT.write_text(json.dumps(res, indent=1, sort_keys=True, default=str),
                   encoding="utf-8")
    print("wrote {0}".format(OUT.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
