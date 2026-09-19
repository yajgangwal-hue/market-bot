"""FORENSIC_NON_PROMOTIONAL. Form 4 feasibility steps 4, 6 and 7.

Reads the DERIVED index only; the raw SEC tree is never touched here.
No economic hypothesis, no backtest, no trading rule, no future return
is read anywhere in this file.

STEP 4/6  availability and lag, from acceptanceDateTime - the moment
          the filing became public. The transaction date is NEVER the
          information timestamp.

          TIMEZONE, and the bug this version fixes. acceptanceDateTime
          is UTC. A filing accepted at 21:30 Eastern carries a UTC
          stamp on the FOLLOWING calendar day, so comparing it against
          that day's 15:45 ET decision marks an after-close filing as
          same-session. Everything here therefore converts to Eastern
          FIRST and derives the session from the Eastern date.

STEP 7    redundancy. Not "does Form 4 predict returns" - forbidden at
          this stage. The question is whether a filing's arrival is
          already implied by the OHLCV state visible BEFORE it is
          public. Indicators are computed INCREMENTALLY, once per
          symbol, which is both exact and fast.
"""

import json
import sys
from collections import defaultdict, deque
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from statistics import fmean, median, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.phase5.asof import decision_timestamp     # noqa: E402

from forensics_regime import load                                 # noqa: E402

DERIVED = REPO / "data" / "form4" / "derived"
ROWS = DERIVED / "form4_rows.jsonl"
DECISION = time(15, 45)


def eastern(acc):
    """UTC instant -> Eastern wall clock, using the repo's own DST rule."""
    day = acc.date()
    # decision_timestamp(day) is 15:45 Eastern for that day expressed in
    # UTC; subtracting a naive 15:45 UTC leaves exactly the offset.
    off = decision_timestamp(day) - datetime.combine(
        day, DECISION, tzinfo=timezone.utc)
    return acc - off


def pct(v, p):
    if not v:
        return None
    s = sorted(v)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def indicators(bars):
    """RSI(14), ATR(14), SMA200, 20d ADV, 252d high - incremental, O(n)."""
    n = len(bars)
    closes = [b.close for b in bars]
    out = {k: [None] * n for k in
           ("rsi", "atr", "sma200", "adv20", "high252", "relvol")}
    gain = loss = 0.0
    for i in range(1, 15):
        d = closes[i] - closes[i - 1]
        gain += max(d, 0.0)
        loss += max(-d, 0.0)
    ag, al = gain / 14.0, loss / 14.0
    tr_sum = 0.0
    for i in range(1, 15):
        tr_sum += max(bars[i].high - bars[i].low,
                      abs(bars[i].high - closes[i - 1]),
                      abs(bars[i].low - closes[i - 1]))
    atr = tr_sum / 14.0
    run200 = sum(closes[:200]) if n >= 200 else 0.0
    dv = [b.close * b.volume for b in bars]
    run20 = sum(dv[:20]) if n >= 20 else 0.0
    window = deque(closes[:252], maxlen=252) if n >= 252 else None
    for i in range(n):
        if i >= 15:
            d = closes[i] - closes[i - 1]
            ag = (ag * 13 + max(d, 0.0)) / 14.0
            al = (al * 13 + max(-d, 0.0)) / 14.0
            tr = max(bars[i].high - bars[i].low,
                     abs(bars[i].high - closes[i - 1]),
                     abs(bars[i].low - closes[i - 1]))
            atr = (atr * 13 + tr) / 14.0
        if i >= 14:
            out["rsi"][i] = (100.0 if al == 0 else
                             100.0 - 100.0 / (1.0 + ag / al))
            out["atr"][i] = atr / closes[i] if closes[i] else None
        if i >= 200:
            run200 += closes[i] - closes[i - 200]
        if i >= 199:
            out["sma200"][i] = (closes[i] / (run200 / 200.0) - 1.0
                                if run200 else None)
        if i >= 20:
            run20 += dv[i] - dv[i - 20]
        if i >= 19:
            a = run20 / 20.0
            out["adv20"][i] = a
            out["relvol"][i] = dv[i] / a if a else None
        if i >= 252:
            window.append(closes[i])
        if window is not None and i >= 251:
            out["high252"][i] = closes[i] / max(window) - 1.0
    return out


def main():
    rows = [json.loads(l) for l in ROWS.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    print("Form 4/4A records in window: {0:,}".format(len(rows)), flush=True)

    # ---- STEP 4 / 6 ------------------------------------------------------
    print("\n" + "=" * 78)
    print("STEP 4 & 6 - POINT-IN-TIME AVAILABILITY AND FILING LAG")
    print("=" * 78)
    lags, tod, bad = [], defaultdict(int), 0
    same, nxt = 0, 0
    parsed = []
    for r in rows:
        try:
            acc = datetime.fromisoformat(
                r["acceptanceDateTime"].replace("Z", "+00:00"))
            txn = date.fromisoformat(r["reportDate"])
        except Exception:                                   # noqa: BLE001
            bad += 1
            continue
        loc = eastern(acc)
        lags.append((loc.date() - txn).days)
        t = loc.time()
        if t < time(9, 30):
            tod["pre-market (before 09:30 ET)"] += 1
        elif t < DECISION:
            tod["intraday (09:30-15:45 ET)"] += 1
        elif t < time(16, 0):
            tod["late session (15:45-16:00 ET)"] += 1
        else:
            tod["after close (16:00+ ET)"] += 1
        if t < DECISION:
            same += 1
        else:
            nxt += 1
        parsed.append({"ticker": r["ticker"], "eastern": loc,
                       "before_decision": t < DECISION})
    n = len(lags)
    print("  parsed {0:,} | unparseable {1}".format(n, bad))
    print("\n  TRANSACTION DATE -> ACCEPTANCE (calendar days, Eastern)")
    for lab, p in (("p25", 25), ("median", 50), ("p75", 75), ("p90", 90),
                   ("p99", 99)):
        print("    {0:<8} {1:.0f}".format(lab, pct(lags, p)))
    print("    {0:<8} {1:.2f}".format("mean", fmean(lags)))
    print("    {0:<8} {1}  <- a single very late filing".format(
        "max", max(lags)))
    for k, v in (("<= 2 calendar days", sum(1 for x in lags if x <= 2)),
                 ("<= 4 calendar days", sum(1 for x in lags if x <= 4)),
                 ("> 30 days (late or amended)",
                  sum(1 for x in lags if x > 30))):
        print("    {0:<30} {1:>8,} ({2:.2%})".format(k, v, v / n))

    print("\n  ACCEPTANCE TIME OF DAY (Eastern, DST-aware)")
    for k in ("pre-market (before 09:30 ET)", "intraday (09:30-15:45 ET)",
              "late session (15:45-16:00 ET)", "after close (16:00+ ET)"):
        v = tod.get(k, 0)
        print("    {0:<36} {1:>8,} ({2:.1%})".format(k, v, v / n))
    print("\n  USABLE AT WHICH DECISION (15:45 ET entry window)")
    print("    {0:<36} {1:>8,} ({2:.1%})".format(
        "SAME session", same, same / n))
    print("    {0:<36} {1:>8,} ({2:.1%})".format(
        "NEXT session or later", nxt, nxt / n))

    # ---- STEP 7 ----------------------------------------------------------
    print("\n" + "=" * 78)
    print("STEP 7 - REDUNDANCY AGAINST THE EXISTING OHLCV STATE")
    print("=" * 78)
    print("  No forward return is read in this section.", flush=True)
    series = load()
    dates = {s: [b.timestamp.date() for b in bs] for s, bs in series.items()}

    events = defaultdict(set)
    unmatched = 0
    for p in parsed:
        sym = p["ticker"]
        ds = dates.get(sym)
        if ds is None:
            unmatched += 1
            continue
        d = p["eastern"].date()
        for day in ds:
            if day > d or (day == d and p["before_decision"]):
                events[sym].add(day)
                break
    print("  filing-days mapped: {0:,} across {1} symbols".format(
        sum(len(v) for v in events.values()), len(events)))
    print("  filings whose ticker has no price series: {0:,}".format(
        unmatched), flush=True)

    names = ("RSI(14)", "ATR fraction", "momentum 21d",
             "distance to 200d SMA", "drawdown from 252d high",
             "relative volume (x ADV)", "is an RSI<=35 candidate")
    feats = {k: {"with": [], "without": []} for k in names}
    for sym, bars in series.items():
        ev = events.get(sym)
        if not ev:
            continue
        ind = indicators(bars)
        closes = [b.close for b in bars]
        ds = dates[sym]
        for i in range(252, len(bars)):
            if ind["rsi"][i] is None or ind["sma200"][i] is None \
                    or ind["atr"][i] is None or ind["relvol"][i] is None \
                    or ind["high252"][i] is None:
                continue
            key = "with" if ds[i] in ev else "without"
            feats["RSI(14)"][key].append(ind["rsi"][i])
            feats["ATR fraction"][key].append(ind["atr"][i])
            feats["momentum 21d"][key].append(closes[i] / closes[i - 21] - 1.0)
            feats["distance to 200d SMA"][key].append(ind["sma200"][i])
            feats["drawdown from 252d high"][key].append(ind["high252"][i])
            feats["relative volume (x ADV)"][key].append(ind["relvol"][i])
            feats["is an RSI<=35 candidate"][key].append(
                1.0 if ind["rsi"][i] <= 35.0 else 0.0)

    print("\n  {0:<28} {1:>10} {2:>12} {3:>12} {4:>10}".format(
        "feature", "n with", "mean WITH", "mean WITHOUT", "Cohen d"))
    redundancy = {}
    for name in names:
        w, o = feats[name]["with"], feats[name]["without"]
        if len(w) < 100 or len(o) < 100:
            continue
        pooled = pstdev(w + o) or 1.0
        d = (fmean(w) - fmean(o)) / pooled
        redundancy[name] = {"n_with": len(w), "n_without": len(o),
                            "mean_with": fmean(w), "mean_without": fmean(o),
                            "cohen_d": d}
        print("  {0:<28} {1:>10,} {2:>12.4f} {3:>12.4f} {4:>10.3f}".format(
            name, len(w), fmean(w), fmean(o), d))
    print("\n  Cohen's d is the gap in pooled standard deviations.")
    print("  |d| < 0.1 negligible, 0.2 small, 0.5 medium.")
    big = sorted(k for k, v in redundancy.items() if abs(v["cohen_d"]) >= 0.2)
    print("  features separating filing days at |d| >= 0.2: {0}".format(
        big or "NONE"))
    share_w = fmean(feats["is an RSI<=35 candidate"]["with"])
    share_o = fmean(feats["is an RSI<=35 candidate"]["without"])
    print("\n  share of filing-days that are ALSO an RSI<=35 candidate: "
          "{0:.2%}".format(share_w))
    print("  share of non-filing-days that are:                       "
          "{0:.2%}".format(share_o))

    out = REPO / "docs" / "phase5" / "form4-feasibility.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "FORENSIC_NON_PROMOTIONAL": True,
        "records": len(rows), "parsed": n, "unparseable": bad,
        "lag_days": {"p25": pct(lags, 25), "median": pct(lags, 50),
                     "p75": pct(lags, 75), "p90": pct(lags, 90),
                     "p99": pct(lags, 99), "mean": fmean(lags),
                     "max": max(lags),
                     "within_2": sum(1 for x in lags if x <= 2) / n,
                     "within_4": sum(1 for x in lags if x <= 4) / n,
                     "over_30": sum(1 for x in lags if x > 30) / n},
        "time_of_day": dict(tod),
        "usable_same_session": same / n, "usable_next_session": nxt / n,
        "events_mapped": sum(len(v) for v in events.values()),
        "symbols_with_events": len(events),
        "filings_ticker_absent": unmatched,
        "redundancy": redundancy,
        "separating_features_d_ge_0.2": big,
        "note": "feasibility only; no forward return was read",
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
