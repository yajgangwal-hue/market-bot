"""H-0013 section 3 - the raw exit dataset with point-in-time features.

EVERY feature is computed from bars at or BEFORE the trigger bar's close.
The trigger bar's own close is the availability timestamp, and nothing
later than it enters any feature. The TARGET (drift to the session
close) is of course later - that is the thing being predicted, and it
is never used as an input.

Trigger definition by reason, matching how the live bot would act:
  reverted   first RTH bar whose RSI(14), recomputed with the current
             price standing in for today's close, reaches rsi_exit
  time_exit  the first RTH bar - the condition is already true at the bell
  stop       the first RTH bar whose LOW touches the recovered stop
             level (stop = exit_price / (1 - one_way), exact inverse of
             sell_fill)

Read-only. No strategy, no registration, no production change.
"""

import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import fmean, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.indicators import rsi                   # noqa: E402
from event_aware_trader.mean_reversion import (                 # noqa: E402
    MeanReversionConfig)
from event_aware_trader.risk import CostModel                    # noqa: E402


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
RAW = unpreserved_intraday_store("raw/intraday-exits")
SPYDIR = unpreserved_intraday_store("raw/intraday-spy")
CACHE = REPO / "docs" / "phase5" / "h0011-cache.json"
OUT = REPO / "docs" / "phase5" / "h0013-features.json"
COSTS = CostModel()


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


def rth(bars):
    out = []
    for b in bars:
        t = to_et(datetime.fromisoformat(b["t"].replace("Z", "+00:00")))
        m = t.hour * 60 + t.minute
        if 570 <= m < 960:
            out.append((t, b))
    out.sort(key=lambda x: x[0])
    return out


def rvol(bars):
    if len(bars) < 3:
        return None
    r = [bars[i]["c"] / bars[i - 1]["c"] - 1.0
         for i in range(1, len(bars)) if bars[i - 1]["c"] > 0]
    return pstdev(r) if len(r) > 1 else None


def main():
    cfg = MeanReversionConfig()
    store = json.loads(CACHE.read_text(encoding="utf-8"))
    trades = store["BASELINE"]["trades"]

    # SPY intraday indexed by session
    spy = {}
    for p in sorted(SPYDIR.glob("*.json")):
        for b in json.loads(p.read_text(encoding="utf-8"))["bars"]["SPY"]:
            t = to_et(datetime.fromisoformat(b["t"].replace("Z", "+00:00")))
            m = t.hour * 60 + t.minute
            if 570 <= m < 960:
                spy.setdefault(t.date().isoformat(), []).append((m, b))
    for k in spy:
        spy[k].sort(key=lambda x: x[0])
    print("SPY sessions indexed: {0:,}".format(len(spy)))

    dailies = {}
    rows = []
    skipped = {}
    for t in trades:
        sym, day = t["symbol"], t["exit"]
        f = RAW / "{0}_{1}.json".format(sym, day)
        if not f.exists():
            skipped["no_raw"] = skipped.get("no_raw", 0) + 1
            continue
        bars = (json.loads(f.read_text(encoding="utf-8")).get("bars")
                or {}).get(sym) or []
        sess = rth(bars)
        if len(sess) < 10:
            skipped["short_session"] = skipped.get("short_session", 0) + 1
            continue
        if sym not in dailies:
            dailies[sym] = [(r["timestamp"][:10], float(r["close"]))
                            for r in csv.DictReader(open(DEEP / (sym + ".csv")))]
        prior = [c for d, c in dailies[sym] if d < day]
        if len(prior) < cfg.rsi_period + 5:
            skipped["short_history"] = skipped.get("short_history", 0) + 1
            continue
        prev_close = prior[-1]
        s_open = sess[0][1]["o"]
        day_close = sess[-1][1]["c"]

        # ---- trigger, by reason -------------------------------------
        i = None
        if t["reason"] == "time_exit":
            i = 0
        elif t["reason"] == "reverted":
            for j, (_ts, b) in enumerate(sess):
                r = rsi(prior + [b["c"]], cfg.rsi_period)
                if r is not None and r >= cfg.rsi_exit:
                    i = j
                    break
        elif t["reason"] == "stop":
            # exact inverse of sell_fill
            lvl = t["exit_price"] / (1.0 - COSTS.one_way_bps / 10_000.0)
            for j, (_ts, b) in enumerate(sess):
                if b["l"] <= lvl:
                    i = j
                    break
        if i is None:
            skipped["no_trigger_" + t["reason"]] = skipped.get(
                "no_trigger_" + t["reason"], 0) + 1
            continue

        ts, tb = sess[i]
        tp = tb["c"]
        before = [b for _s, b in sess[:i + 1]]          # INCLUSIVE of trigger
        nxt = sess[i + 1][1] if i + 1 < len(sess) else None
        pv = sum(b["c"] * b["v"] for b in before)
        vv = sum(b["v"] for b in before)
        vwap = pv / vv if vv else None
        mins = (ts.hour * 60 + ts.minute) - 570

        sp = spy.get(day) or []
        sp_before = [b for m, b in sp if m <= (ts.hour * 60 + ts.minute)]
        spy_ret = (sp_before[-1]["c"] / sp_before[0]["o"] - 1.0
                   if len(sp_before) >= 2 and sp_before[0]["o"] else None)
        spy_vol = rvol(sp_before)

        y = int(day[:4])
        third = 1 if y <= 2019 else 2 if y <= 2023 else 3
        rows.append({
            "symbol": sym, "entry": t["entry"], "exit": day,
            "reason": t["reason"], "entry_price": t["entry_price"],
            "exit_price_recorded": t["exit_price"], "qty": t["qty"],
            "trigger_price": tp, "session_close": day_close,
            "next_print": nxt["o"] if nxt else None,
            "charged_haircut": 0.00652,
            # TARGET - later than the availability timestamp, never an input
            "drift_to_close": (day_close - tp) / tp,
            "drift_to_next_print": ((nxt["o"] - tp) / tp) if nxt else None,
            # timing
            "trigger_et": ts.strftime("%H:%M"),
            "minutes_from_open": mins,
            "weekday": ts.weekday(), "month": ts.month, "year": y,
            "third": third, "bars_remaining": len(sess) - i - 1,
            # point-in-time intraday state, availability = trigger bar close
            "availability_et": ts.isoformat(),
            "ret_into_trigger": tp / s_open - 1.0 if s_open else None,
            "excursion_high_before": (max(b["h"] for b in before) / s_open
                                      - 1.0) if s_open else None,
            "excursion_low_before": (min(b["l"] for b in before) / s_open
                                     - 1.0) if s_open else None,
            "rvol_before": rvol(before),
            "vwap_distance": (tp / vwap - 1.0) if vwap else None,
            "dist_prior_close": tp / prev_close - 1.0,
            "dist_session_open": tp / s_open - 1.0 if s_open else None,
            "gap_open": s_open / prev_close - 1.0,
            "volume_before": vv,
            "volume_ratio_bar": (tb["v"] / fmean(b["v"] for b in before)
                                 if before and fmean(b["v"] for b in before)
                                 else None),
            "spy_ret_to_trigger": spy_ret,
            "spy_rvol_before": spy_vol,
        })

    print("built {0} rows | skipped {1}".format(len(rows), skipped or "none"))
    by = {}
    for r in rows:
        by[r["reason"]] = by.get(r["reason"], 0) + 1
    print("by reason: {0}".format(by))
    OUT.write_text(json.dumps({
        "FORENSIC_NON_PROMOTIONAL": True,
        "note": "every feature's availability timestamp is the trigger bar "
                "close; drift_to_close is the TARGET and is never an input",
        "rows": rows, "skipped": skipped}, indent=1, sort_keys=True,
        default=str), encoding="utf-8")
    print("wrote {0}".format(OUT.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
