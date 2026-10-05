"""Run H-0008. Equivalence, then reconstruct the trigger-to-close drift.

EXECUTION CALIBRATION. Nothing here trades differently and nothing here
may become a feature.

THE TRIGGER, and why it is found by walking forward. The live bot holds
a daily series whose LAST element is today's still-forming bar, so its
close is the current price. As the price moves intraday, RSI(14) moves
with it, and `should_exit` fires 'reverted' the first moment RSI reaches
60. To reconstruct that instant this walks the session's five-minute
bars in order and HALTS at the first crossing - no later bar can move
where the trigger is. The holding cap has no intraday component: it is
already true when the bell rings, so its trigger is the session's first
regular bar.
"""

import json
import sys
from collections import defaultdict
from datetime import date, time
from pathlib import Path
from statistics import fmean, median, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.data import load_bars                  # noqa: E402
from event_aware_trader.mean_reversion import conviction as shipped_conviction  # noqa: E402
from event_aware_trader.mean_reversion import rsi              # noqa: E402
from event_aware_trader.modelgov import prereg                 # noqa: E402
from event_aware_trader.phase5.metrics import measure          # noqa: E402
from event_aware_trader.research import production_report      # noqa: E402
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto  # noqa: E402

# Decade price data comes only through the research dataset gate: verified
# before a bar is read, fail-closed, no scratchpad fallback. It replaced a
# first-match glob over session scratchpads on 2026-09-24
# (docs/2026-09-24-governed-research-dataset-migration.md).
if str(REPO / "scripts") not in sys.path:
    sys.path.append(str(REPO / "scripts"))
from research_gate import (dataset_file, price_dir,          # noqa: E402
                           unpreserved_intraday_store)
WINDOW = 400
_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-WINDOW:], c)
_conv = {}

CURRENT_HAIRCUT = 0.00652
PERCENTILES = [("A p75", 75), ("B p90", 90), ("C p95", 95)]
RSI_PERIOD, RSI_EXIT = 14, 60.0
#: Regular session in UTC. The cache stamps bars in UTC and carries
#: pre- and post-market, which the bot's cycle does not trade.
OPEN_UTC, CLOSE_UTC = time(13, 30), time(20, 0)


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def load_daily():
    base = price_dir("deep")        # verified before any bar is read
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        bars = load_bars(dataset_file(base, symbol + ".csv"))
        if len(bars) >= 500:
            out[symbol] = bars
    return out


def load_intraday(symbol):
    # UNPRESERVED intraday store: scratchpad-only, never verified. It is no
    # longer present anywhere, so this now raises; before 2026-09-24 every
    # symbol silently returned None.
    path = unpreserved_intraday_store("intraday_cache") / (symbol + ".json")
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    by_day = defaultdict(list)
    for b in raw:
        stamp = b["t"]
        day = date.fromisoformat(stamp[:10])
        hhmm = time(int(stamp[11:13]), int(stamp[14:16]))
        if OPEN_UTC <= hhmm < CLOSE_UTC:
            by_day[day].append((hhmm, b["c"]))
    for day in by_day:
        by_day[day].sort()
    return by_day


def percentile(values, p):
    """Linear-interpolated percentile. Registered as 'the Nth percentile'."""
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def find_trigger(reason, session, prior_closes):
    """(trigger_time, trigger_price) or None. Forward walk, first crossing."""
    if not session:
        return None
    if reason != "reverted":
        return session[0]                       # cap is true at the bell
    for hhmm, price in session:
        strength = rsi(prior_closes + [price], RSI_PERIOD)
        if strength is not None and strength >= RSI_EXIT:
            return hhmm, price
    return None                                 # never crossed intraday


def main():
    sealed = [p for p in prereg.load() if p["hypothesis_id"] == "H-0008"]
    if not sealed:
        print("REFUSED: H-0008 is not registered.")
        return 2
    seal = sealed[0]
    if not prereg.verify_chain()["intact"]:
        print("REFUSED: registration chain broken.")
        return 2
    if sorted(seal["parameters"]["percentiles"].values()) != \
            sorted(p for _n, p in PERCENTILES):
        print("REFUSED: this runner's percentiles are not the sealed ones.")
        return 2
    print("H-0008 seal {0} | commit {1}".format(seal["seal"][:16],
                                                seal["code_commit"][:12]))

    series = load_daily()
    print("\ndecade: {0} symbols".format(len(series)), flush=True)
    report = production_report(series, conviction=conviction,
                               dataset="decade", purpose="diagnostic")
    base = measure(report, "BASELINE").as_dict()
    print("EQUIVALENCE: baseline must reproduce its registered result")
    print("  {0:+.10%} over {1} trades | registered +58.5889000000%".format(
        base["total_return"], base["trades"]))
    if abs(base["total_return"] - 0.585889) > 5e-7 or base["trades"] != 698:
        print("STOPPED: baseline did not reproduce. Nothing measured.")
        return 2
    print("  reproduced - proceeding\n")

    rule_exits = [t for t in report.trades
                  if t.exit_reason in ("reverted", "time_exit")]
    print("rule exits in the decade run: {0}".format(len(rule_exits)))

    daily_closes = {s: [(b.timestamp.date(), b.close) for b in bs]
                    for s, bs in series.items()}
    cache, rows, misses = {}, [], defaultdict(int)
    for t in rule_exits:
        s, day = t.symbol, t.exit_time.date()
        if s not in cache:
            cache[s] = load_intraday(s)
        book = cache[s]
        if book is None:
            misses["symbol not in intraday cache"] += 1
            continue
        session = book.get(day)
        if not session:
            misses["exit date outside the intraday window"] += 1
            continue
        prior = [c for d, c in daily_closes[s] if d < day]
        if len(prior) < RSI_PERIOD + 1:
            misses["insufficient prior daily closes"] += 1
            continue
        hit = find_trigger(t.exit_reason, session, prior)
        if hit is None:
            misses["RSI never reached 60 intraday"] += 1
            continue
        hhmm, trigger = hit
        close = session[-1][1]
        rows.append({
            "symbol": s, "day": day, "reason": t.exit_reason,
            "trigger_time": hhmm.isoformat(timespec="minutes"),
            "trigger": trigger, "close": close,
            "drift": close / trigger - 1.0,
            "year": day.year,
        })

    print("reconstructed: {0}".format(len(rows)))
    for why, n in sorted(misses.items(), key=lambda kv: -kv[1]):
        print("  not reconstructed - {0}: {1}".format(why, n))
    if not rows:
        print("STOPPED: nothing reconstructable.")
        return 2

    drifts = [r["drift"] for r in rows]
    print("\nTRIGGER-TO-CLOSE DRIFT  (positive = close ABOVE trigger = the")
    print("simulator overstates, which is what the haircut corrects)")
    print("  n                     {0}".format(len(drifts)))
    print("  mean                  {0:+.4%}".format(fmean(drifts)))
    print("  median                {0:+.4%}".format(median(drifts)))
    print("  stdev                 {0:.4%}".format(pstdev(drifts)))
    print("  adverse (drift > 0)   {0:.1%}".format(
        sum(1 for d in drifts if d > 0) / len(drifts)))
    print("  worst single          {0:+.4%}".format(max(drifts)))
    print("  best single           {0:+.4%}".format(min(drifts)))
    for p in (5, 25, 50, 75, 90, 95, 99):
        print("  p{0:<20} {1:+.4%}{2}".format(
            p, percentile(drifts, p),
            "   <- currently charged 0.6520%" if p == 90 else ""))

    def block(title, keyfn, sort=None):
        print("\n{0}".format(title))
        groups = defaultdict(list)
        for r in rows:
            groups[keyfn(r)].append(r["drift"])
        print("  {0:<16} {1:>5} {2:>11} {3:>11} {4:>11}".format(
            "", "n", "mean", "median", "p90"))
        for k in (sorted(groups) if sort is None else sort(groups)):
            g = groups[k]
            print("  {0:<16} {1:>5} {2:>11.4%} {3:>11.4%} {4:>11.4%}".format(
                str(k), len(g), fmean(g), median(g), percentile(g, 90)))
        return groups

    block("BY EXIT REASON", lambda r: r["reason"])
    block("BY TRIGGER TIME (UTC half-hours; 13:30 UTC is the 09:30 ET bell)",
          lambda r: r["trigger_time"][:2] + (":00" if int(r["trigger_time"][3:]) < 30
                                             else ":30"))
    block("BY YEAR", lambda r: r["year"])
    syms = block("BY SYMBOL (ten largest contributors)", lambda r: r["symbol"],
                 sort=lambda g: sorted(g, key=lambda k: -len(g[k]))[:10])

    # ---- the registered acceptance clauses ------------------------------
    half = len(rows) // 2
    ordered = sorted(rows, key=lambda r: (r["day"], r["trigger_time"]))
    first = [r["drift"] for r in ordered[:half]]
    second = [r["drift"] for r in ordered[half:]]
    by_symbol = defaultdict(int)
    by_year = defaultdict(int)
    for r in rows:
        by_symbol[r["symbol"]] += 1
        by_year[r["year"]] += 1
    top_symbol = max(by_symbol.items(), key=lambda kv: kv[1])
    top_year = max(by_year.items(), key=lambda kv: kv[1])

    print("\nREGISTERED ACCEPTANCE CLAUSES")
    print("  (A) sample >= 100:              {0} -> {1}".format(
        len(rows), "pass" if len(rows) >= 100 else "FAIL"))
    print("  (C) largest symbol <= 15%:      {0} {1}/{2} = {3:.1%} -> {4}".format(
        top_symbol[0], top_symbol[1], len(rows), top_symbol[1] / len(rows),
        "pass" if top_symbol[1] / len(rows) <= 0.15 else "FAIL"))
    print("      largest year <= 50%:        {0} {1}/{2} = {3:.1%} -> {4}".format(
        top_year[0], top_year[1], len(rows), top_year[1] / len(rows),
        "pass" if top_year[1] / len(rows) <= 0.50 else "FAIL"))

    print("\n  per registered percentile:")
    print("  {0:<8} {1:>10} {2:>11} {3:>11} {4:>9} {5:>9} {6:>7}".format(
        "config", "value", "1st half", "2nd half", "|diff|", "(B)", "(D)"))
    results = []
    for name, p in PERCENTILES:
        v, v1, v2 = (percentile(drifts, p), percentile(first, p),
                     percentile(second, p))
        diff = abs(v1 - v2)
        b_ok, d_ok = diff <= 0.0025, v < CURRENT_HAIRCUT
        results.append({"label": name, "percentile": p, "value": v,
                        "first_half": v1, "second_half": v2, "half_gap": diff,
                        "B_stability": b_ok, "D_below_current": d_ok,
                        "passes": bool(len(rows) >= 100
                                       and top_symbol[1] / len(rows) <= 0.15
                                       and top_year[1] / len(rows) <= 0.50
                                       and b_ok and d_ok)})
        print("  {0:<8} {1:>10.4%} {2:>11.4%} {3:>11.4%} {4:>9.4%} {5:>9} "
              "{6:>7}".format(name, v, v1, v2, diff,
                              "pass" if b_ok else "FAIL",
                              "pass" if d_ok else "FAIL"))

    # ---- the ceiling on this whole exercise ----------------------------
    # Registered secondary measurement. The simulator decides on COMPLETED
    # daily closes; the live bot can cross RSI 60 intraday on a day that
    # closes back below 60, exit, and leave the simulator still holding.
    # No haircut at any value models that, so counting it bounds how much
    # of the live/simulated gap this exercise could ever close.
    print("")
    print("UNMODELLABLE CROSSINGS - days the live bot would have exited")
    print("and the simulator did not (no haircut can represent these)")
    held = crossed = checked = 0
    for t in rule_exits:
        s_, book = t.symbol, cache.get(t.symbol)
        if book is None:
            continue
        prior_all = daily_closes[s_]
        for day, _c in prior_all:
            if not (t.entry_time.date() < day < t.exit_time.date()):
                continue
            session = book.get(day)
            if not session:
                continue
            prior = [c for d, c in prior_all if d < day]
            if len(prior) < RSI_PERIOD + 1:
                continue
            held += 1
            close_rsi = rsi(prior + [session[-1][1]], RSI_PERIOD)
            if close_rsi is not None and close_rsi >= RSI_EXIT:
                continue            # the simulator saw it too; not a miss
            checked += 1
            if find_trigger("reverted", session, prior) is not None:
                crossed += 1
    print("  held sessions inside the intraday window     {0}".format(held))
    print("  of those, closing BELOW RSI 60               {0}".format(checked))
    print("  of those, crossing RSI 60 INTRADAY           {0}{1}".format(
        crossed, "" if not checked else
        "  ({0:.1%})".format(crossed / checked)))
    print("  -> the live bot would have exited on these days and the")
    print("     simulator held. This is a MODEL GAP, not a haircut value.")

    out = REPO / "docs" / "phase5" / "h0008-drift.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "seal": seal["seal"], "current_haircut": CURRENT_HAIRCUT,
        "baseline_total_return": base["total_return"],
        "rule_exits_in_run": len(rule_exits), "reconstructed": len(rows),
        "not_reconstructed": dict(misses),
        "mean": fmean(drifts), "median": median(drifts),
        "stdev": pstdev(drifts), "worst": max(drifts), "best": min(drifts),
        "adverse_share": sum(1 for d in drifts if d > 0) / len(drifts),
        "percentiles": {str(p): percentile(drifts, p)
                        for p in (5, 25, 50, 75, 90, 95, 99)},
        "top_symbol": {"symbol": top_symbol[0], "n": top_symbol[1],
                       "share": top_symbol[1] / len(rows)},
        "top_year": {"year": top_year[0], "n": top_year[1],
                     "share": top_year[1] / len(rows)},
        "configurations": results,
        "by_reason": {k: {"n": len(v), "mean": fmean(v),
                          "p90": percentile(v, 90)}
                      for k, v in
                      {r: [x["drift"] for x in rows if x["reason"] == r]
                       for r in {y["reason"] for y in rows}}.items()},
        "unmodellable": {"held_sessions": held,
                         "closed_below_60": checked,
                         "crossed_intraday": crossed},
 "observations": rows,
        "note": "execution calibration measurement; never a feature",
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
