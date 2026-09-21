"""H-0019 - what the candidate generator structurally refuses to look at.

READ-ONLY. No strategy, no portfolio, no trade, no production change.

EVERY indicator comes from production's OWN mean_reversion.evaluate().
Nothing is reimplemented. evaluate() returns rsi, trend_ma,
atr_fraction, close and stop on the signal object whether it says BUY
or STAND_ASIDE, so one call per symbol-session yields both the
production population and the suppressed populations from identical
arithmetic. The only quantity computed here is the 20-day dollar
volume, copied verbatim from the line inside evaluate().

The 400-bar window matches the frozen baseline harness exactly
(forensics_regime patches mean_reversion_signal to h[-400:], and the
baseline equivalence assertion below runs through that same patch).

Forward returns are OUTCOMES. They are measured from the decision
session's close forward and never touch a probe condition.
"""

import json
import sys
from collections import defaultdict
from math import sqrt
from pathlib import Path
from statistics import fmean, stdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.forward import frozen_fingerprint        # noqa: E402
from event_aware_trader.mean_reversion import (                  # noqa: E402
    MeanReversionConfig, conviction as shipped_conviction, evaluate)
from event_aware_trader.modelgov import prereg                   # noqa: E402
from event_aware_trader.phase5.metrics import measure            # noqa: E402
from event_aware_trader.research import production_report        # noqa: E402
from forensics_regime import load                                 # noqa: E402

SEAL = "6d04c81876cd60a2acacf5a4061802da3ad826fe7ee7240a690632aea26ea4c7"
FP = "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b"
OUT = REPO / "docs" / "phase5" / "h0019-opportunity-classes.json"

CFG = MeanReversionConfig()
WINDOW = 400
HORIZONS = (5, 10, 20)
PRIMARY = 10
# The project's own cost model: 2 bps half spread + 4 bps slippage, one
# way. A round trip is therefore 12 bps. Not a new threshold.
ROUND_TRIP = 0.0012
THIRDS = (("2016-2019", 2016, 2019), ("2020-2023", 2020, 2023),
          ("2024-2026", 2024, 2026))
PROBES = ("PROD", "P1_discarded_half", "P2_momentum",
          "P3_volatility_excluded", "P4_cross_sectional", "P5_volume_shock")

_conv = {}


def conviction(symbol, history):
    k = (symbol, len(history), history[0].timestamp if history else None)
    v = _conv.get(k)
    if v is None:
        v = _conv[k] = shipped_conviction(history[-40:])
    return v


def tstat(values):
    n = len(values)
    if n < 3:
        return None
    s = stdev(values)
    if s == 0:
        return None
    return fmean(values) / (s / sqrt(n))


def collapse(rows, horizon):
    """Day-collapse, the standing treatment for clustered observations."""
    by_day = defaultdict(list)
    for r in rows:
        v = r["fwd"].get(horizon)
        if v is not None:
            by_day[r["date"]].append(v)
    return {d: fmean(v) for d, v in by_day.items()}


def describe(rows, horizon):
    daily = collapse(rows, horizon)
    if not daily:
        return None
    series = list(daily.values())
    flat = [r["fwd"][horizon] for r in rows
            if r["fwd"].get(horizon) is not None]
    return {
        "observations": len(flat),
        "days": len(series),
        "mean_per_observation": fmean(flat),
        "mean_per_day": fmean(series),
        "t_day_collapsed": tstat(series),
        "win_rate": sum(1 for v in flat if v > 0) / len(flat),
        "clears_round_trip": fmean(flat) > ROUND_TRIP,
    }


def main():
    seal = [p for p in prereg.load() if p["hypothesis_id"] == "H-0019"]
    if not seal or seal[0]["seal"] != SEAL:
        print("REFUSED: H-0019 seal missing or altered.")
        return 2
    if not prereg.verify_chain()["intact"]:
        print("REFUSED: chain broken.")
        return 2
    if frozen_fingerprint() != FP:
        print("REFUSED: fingerprint moved.")
        return 2
    print("H-0019 seal {0} | commit {1}".format(
        SEAL[:16], seal[0]["code_commit"][:12]))

    series = load()
    print("universe: {0} symbols".format(len(series)))

    print("\nbaseline equivalence ...", flush=True)
    rep = production_report(series, conviction=conviction, dataset="decade",
                            purpose="rejection_test", mr_config=CFG)
    m = measure(rep, "BASELINE").as_dict()
    print("  {0:+.10%} over {1} trades | required +58.5889000000% / 698"
          .format(m["total_return"], m["trades"]))
    if abs(m["total_return"] - 0.585889) > 5e-7 or m["trades"] != 698:
        print("STOPPED: baseline not reproduced. Nothing measured.")
        return 2
    print("  MATCH\n", flush=True)

    spy = {b.timestamp.date(): b.close for b in series["SPY"]}

    # ---- one pass: production's own evaluate() on every symbol-session ---
    obs = []                       # gate-passing symbol-sessions
    scanned = 0
    for si, (symbol, bars) in enumerate(sorted(series.items()), 1):
        closes = [b.close for b in bars]
        dvs = [b.close * b.volume for b in bars]
        n = len(bars)
        for i in range(200, n):
            scanned += 1
            sig = evaluate(symbol, bars[max(0, i - WINDOW + 1):i + 1], CFG)
            if sig.rsi is None or sig.trend_ma is None:
                continue
            if sig.atr_fraction is None or sig.stop is None:
                continue                      # positive-stop gate
            close = sig.close
            if close < CFG.min_price:
                continue                      # price gate
            dv20 = sum(dvs[max(0, i - 19):i + 1]) / 20.0
            if dv20 < CFG.min_average_dollar_volume:
                continue                      # liquidity gate
            d = bars[i].timestamp.date()
            if d not in spy:
                continue
            fwd = {}
            for h in HORIZONS:
                j = i + h
                if j >= n:
                    continue
                dj = bars[j].timestamp.date()
                if dj not in spy:
                    continue
                fwd[h] = ((closes[j] / close - 1.0)
                          - (spy[dj] / spy[d] - 1.0))
            trail = (sum(dvs[i - 20:i]) / 20.0) if i >= 20 else None
            obs.append({
                "symbol": symbol, "date": d, "i": i,
                "rsi": sig.rsi, "above_ma": close > sig.trend_ma,
                "atrf": sig.atr_fraction,
                "ret21": (close / closes[i - 21] - 1.0) if i >= 21 else None,
                "dv_shock": (dvs[i] >= 3.0 * trail) if trail else False,
                "fwd": fwd})
        if si % 50 == 0:
            print("  {0}/{1} symbols | {2} gate-passing sessions"
                  .format(si, len(series), len(obs)), flush=True)

    print("\nscanned {0} symbol-sessions | {1} passed price/liquidity/stop"
          .format(scanned, len(obs)))

    # ---- P4 needs the cross-section, so deciles come after the pass -----
    by_date = defaultdict(list)
    for r in obs:
        if r["ret21"] is not None:
            by_date[r["date"]].append(r)
    for d, rows in by_date.items():
        if len(rows) < 10:
            continue
        rows.sort(key=lambda r: r["ret21"])
        cut = max(1, len(rows) // 10)
        for r in rows[:cut]:
            r["bottom_decile"] = True

    # ---- classify -------------------------------------------------------
    pops = {k: [] for k in PROBES}
    for r in obs:
        low, high = r["rsi"] <= CFG.rsi_entry, r["rsi"] >= 65.0
        calm = r["atrf"] <= CFG.max_atr_fraction
        up = r["above_ma"]
        if low and up and calm:
            pops["PROD"].append(r)
        if low and not up and calm:
            pops["P1_discarded_half"].append(r)
        if high and up and calm:
            pops["P2_momentum"].append(r)
        if low and up and not calm:
            pops["P3_volatility_excluded"].append(r)
        if r.get("bottom_decile"):
            pops["P4_cross_sectional"].append(r)
        if r["dv_shock"]:
            pops["P5_volume_shock"].append(r)

    prod_keys = {(r["symbol"], r["date"]) for r in pops["PROD"]}
    prod_days = {r["date"] for r in pops["PROD"]}
    prod_daily = collapse(pops["PROD"], PRIMARY)

    result = {"seal": SEAL, "commit": seal[0]["code_commit"],
              "universe": len(series), "scanned": scanned,
              "gate_passing": len(obs), "round_trip_hurdle": ROUND_TRIP,
              "baseline": {"total_return": m["total_return"],
                           "trades": m["trades"]},
              "probes": {}}

    for name in PROBES:
        rows = pops[name]
        entry = {"share_of_gated": len(rows) / len(obs) if obs else 0.0,
                 "horizons": {}}
        for h in HORIZONS:
            entry["horizons"][str(h)] = describe(rows, h)
        entry["thirds"] = {}
        for label, lo, hi in THIRDS:
            sub = [r for r in rows if lo <= r["date"].year <= hi]
            entry["thirds"][label] = describe(sub, PRIMARY)
        # independence
        overlap = sum(1 for r in rows if (r["symbol"], r["date"]) in prod_keys)
        days = {r["date"] for r in rows}
        no_prod = [r for r in rows if r["date"] not in prod_days]
        d_probe = collapse(rows, PRIMARY)
        common = sorted(set(d_probe) & set(prod_daily))
        corr = None
        if len(common) >= 3:
            a = [d_probe[d] for d in common]
            b = [prod_daily[d] for d in common]
            ma, mb = fmean(a), fmean(b)
            num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
            den = sqrt(sum((x - ma) ** 2 for x in a)
                       * sum((y - mb) ** 2 for y in b))
            corr = num / den if den else None
        entry["independence"] = {
            "symbol_session_overlap_with_prod": overlap,
            "symbol_session_overlap_share": (overlap / len(rows)
                                             if rows else 0.0),
            "probe_days": len(days),
            "day_overlap_share": (len(days & prod_days) / len(days)
                                  if days else 0.0),
            "daily_return_correlation_with_prod": corr,
            "common_days": len(common),
            "on_days_prod_had_no_candidate": describe(no_prod, PRIMARY)}
        result["probes"][name] = entry

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1, default=str))

    # ---- print ----------------------------------------------------------
    print("\n{0:<24} {1:>8} {2:>7} {3:>13} {4:>8} {5:>8}".format(
        "population", "obs", "days", "fwd10 SPY-rel", "t(day)", "win%"))
    for name in PROBES:
        h = result["probes"][name]["horizons"][str(PRIMARY)]
        if not h:
            print("{0:<24} {1:>8}".format(name, "none"))
            continue
        print("{0:<24} {1:>8} {2:>7} {3:>+12.4%} {4:>8} {5:>7.1%}".format(
            name, h["observations"], h["days"], h["mean_per_observation"],
            "n/a" if h["t_day_collapsed"] is None
            else "{0:+.2f}".format(h["t_day_collapsed"]), h["win_rate"]))

    print("\n{0:<24} {1:>12} {2:>12} {3:>12}".format(
        "fwd10 by third", *[t[0] for t in THIRDS]))
    for name in PROBES:
        cells = []
        for label, _, _ in THIRDS:
            t = result["probes"][name]["thirds"][label]
            cells.append("n/a" if not t
                         else "{0:+.3%}".format(t["mean_per_observation"]))
        print("{0:<24} {1:>12} {2:>12} {3:>12}".format(name, *cells))

    print("\n{0:<24} {1:>9} {2:>9} {3:>9} {4:>16}".format(
        "independence", "sym-sess", "day-ovl", "corr", "no-prod-day fwd10"))
    for name in PROBES:
        ind = result["probes"][name]["independence"]
        npd = ind["on_days_prod_had_no_candidate"]
        print("{0:<24} {1:>8.1%} {2:>8.1%} {3:>9} {4:>16}".format(
            name, ind["symbol_session_overlap_share"],
            ind["day_overlap_share"],
            "n/a" if ind["daily_return_correlation_with_prod"] is None
            else "{0:+.3f}".format(ind["daily_return_correlation_with_prod"]),
            "n/a" if not npd
            else "{0:+.3%} n={1}".format(npd["mean_per_observation"],
                                         npd["observations"])))

    print("\nround-trip cost hurdle {0:.2%} | wrote {1}".format(
        ROUND_TRIP, OUT.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
