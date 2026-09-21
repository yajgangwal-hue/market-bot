"""H-0019 validity controls. NOT IN THE SEAL - and deliberately so.

WHY THESE EXIST. The sealed measurement ranked the probes almost
exactly in order of their volatility, which is what beta in a rising
decade looks like. Two rival explanations have to be killed before any
class is nominated:

  SYMBOL EFFECT  the probe fires on high-beta names, which beat SPY on
                 average over a decade the market spent rising, whether
                 or not any signal is present
  DATE EFFECT    the probe fires on stressed days, and the whole market
                 bounced afterwards

Both are removed with an additive two-way control. For every
gate-passing observation the predicted SPY-relative return is
    grand mean + (symbol mean - grand) + (date mean - grand)
and the LIFT is what the probe earned above that. The symbol and date
effects are estimated on the FULL gate-passing sample, which includes
the probe's own observations, so each probe partly predicts itself and
its measured lift is understated. That bias runs AGAINST a positive
finding, which is the direction an honest control should err in.

SURVIVORSHIP. The 230-symbol universe was selected as of 2026. A
high-volatility name that was oversold in 2017 and is still here is a
survivor; the ones that went to zero are absent - and the suppressed
populations are exactly where that bias concentrates. The ETF subset
is this project's standing survivorship control, because a sector or
index fund is not dropped from the list for having fallen.

NEITHER CONTROL CAN CREATE AN EFFECT. Both can only shrink one. That
is why adding them after seeing the sealed result is not a probe swap:
no control here could turn a null into a nomination.
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
from event_aware_trader.strategy import INSTRUMENT_NAMES         # noqa: E402
from forensics_regime import load                                 # noqa: E402

SEAL = "6d04c81876cd60a2acacf5a4061802da3ad826fe7ee7240a690632aea26ea4c7"
FP = "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b"
OUT = REPO / "docs" / "phase5" / "h0019-controls.json"

CFG = MeanReversionConfig()
WINDOW = 400
PRIMARY = 10
HURDLES = (0.0012, 0.0025, 0.0050)
THIRDS = (("2016-2019", 2016, 2019), ("2020-2023", 2020, 2023),
          ("2024-2026", 2024, 2026))
PROBES = ("PROD", "P1_discarded_half", "P2_momentum",
          "P3_volatility_excluded", "P4_cross_sectional", "P5_volume_shock")

# Keyword match with its two known errors fixed: STX is "Ordinary
# Shares" (Seagate, an operating company) and GLD is "SPDR Gold Shares"
# (a fund the keyword missed).
_KW = ("ETF", "Fund", "Trust", "Index", "Shares ")
ETFS = ({s for s, n in INSTRUMENT_NAMES.items()
         if any(k in n for k in _KW)} - {"STX"}) | {"GLD"}

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


def day_t(rows, key):
    """Day-collapse `key` then t-test across days."""
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["date"]].append(r[key])
    series = [fmean(v) for v in by_day.values()]
    if not series:
        return None, None, 0
    return fmean(series), tstat(series), len(series)


def build():
    series = load()
    spy = {b.timestamp.date(): b.close for b in series["SPY"]}
    obs = []
    for symbol, bars in sorted(series.items()):
        closes = [b.close for b in bars]
        dvs = [b.close * b.volume for b in bars]
        n = len(bars)
        for i in range(200, n):
            sig = evaluate(symbol, bars[max(0, i - WINDOW + 1):i + 1], CFG)
            if (sig.rsi is None or sig.trend_ma is None
                    or sig.atr_fraction is None or sig.stop is None):
                continue
            close = sig.close
            if close < CFG.min_price:
                continue
            if sum(dvs[max(0, i - 19):i + 1]) / 20.0 < \
                    CFG.min_average_dollar_volume:
                continue
            d = bars[i].timestamp.date()
            j = i + PRIMARY
            if d not in spy or j >= n:
                continue
            dj = bars[j].timestamp.date()
            if dj not in spy:
                continue
            trail = (sum(dvs[i - 20:i]) / 20.0) if i >= 20 else None
            obs.append({
                "symbol": symbol, "date": d,
                "rsi": sig.rsi, "above_ma": close > sig.trend_ma,
                "atrf": sig.atr_fraction,
                "ret21": (close / closes[i - 21] - 1.0) if i >= 21 else None,
                "dv_shock": (dvs[i] >= 3.0 * trail) if trail else False,
                "fwd": ((closes[j] / close - 1.0)
                        - (spy[dj] / spy[d] - 1.0))})
    return series, obs


def classify(obs):
    by_date = defaultdict(list)
    for r in obs:
        if r["ret21"] is not None:
            by_date[r["date"]].append(r)
    for rows in by_date.values():
        if len(rows) < 10:
            continue
        rows.sort(key=lambda r: r["ret21"])
        for r in rows[:max(1, len(rows) // 10)]:
            r["bottom_decile"] = True
    pops = {k: [] for k in PROBES}
    for r in obs:
        low, high = r["rsi"] <= CFG.rsi_entry, r["rsi"] >= 65.0
        calm, up = r["atrf"] <= CFG.max_atr_fraction, r["above_ma"]
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
    return pops


def two_way(pool):
    """grand + (symbol - grand) + (date - grand), fitted on the pool."""
    grand = fmean([r["fwd"] for r in pool])
    sym, dat = defaultdict(list), defaultdict(list)
    for r in pool:
        sym[r["symbol"]].append(r["fwd"])
        dat[r["date"]].append(r["fwd"])
    a = {s: fmean(v) - grand for s, v in sym.items()}
    b = {d: fmean(v) - grand for d, v in dat.items()}
    for r in pool:
        r["pred"] = grand + a[r["symbol"]] + b[r["date"]]
        r["lift"] = r["fwd"] - r["pred"]
    return grand


def report(label, pool, pops, out):
    grand = two_way(pool)
    print("\n" + "=" * 78)
    print("{0}  |  pool {1} gate-passing observations  |  grand mean "
          "{2:+.4%}".format(label, len(pool), grand))
    print("=" * 78)
    print("{0:<24} {1:>7} {2:>10} {3:>10} {4:>10} {5:>7}".format(
        "population", "obs", "raw", "predicted", "LIFT", "t(day)"))
    block = {}
    for name in PROBES:
        rows = [r for r in pops[name] if "lift" in r]
        if not rows:
            print("{0:<24} {1:>7}".format(name, 0))
            block[name] = None
            continue
        raw = fmean([r["fwd"] for r in rows])
        pred = fmean([r["pred"] for r in rows])
        lift, t, days = day_t(rows, "lift")
        print("{0:<24} {1:>7} {2:>+9.4%} {3:>+9.4%} {4:>+9.4%} {5:>7}".format(
            name, len(rows), raw, pred, lift,
            "n/a" if t is None else "{0:+.2f}".format(t)))
        thirds = {}
        for tl, lo, hi in THIRDS:
            sub = [r for r in rows if lo <= r["date"].year <= hi]
            m, tt, dd = day_t(sub, "lift")
            thirds[tl] = None if m is None else {
                "lift": m, "t": tt, "days": dd, "observations": len(sub)}
        block[name] = {
            "observations": len(rows), "days": days,
            "raw": raw, "predicted": pred, "lift": lift, "t_day": t,
            "lift_clears": {"{0:.2%}".format(h): lift > h for h in HURDLES},
            "thirds": thirds}
    out[label] = {"pool": len(pool), "grand_mean": grand, "probes": block}
    print("\n{0:<24} {1:>14} {2:>14} {3:>14}".format(
        "LIFT by third", *[t[0] for t in THIRDS]))
    for name in PROBES:
        if not block[name]:
            continue
        cells = []
        for tl, _, _ in THIRDS:
            t = block[name]["thirds"][tl]
            if not t:
                cells.append("n/a")
            elif t["t"] is None:
                cells.append("{0:+.3%} n={1}".format(t["lift"],
                                                     t["observations"]))
            else:
                cells.append("{0:+.3%} t{1:+.1f}".format(t["lift"], t["t"]))
        print("{0:<24} {1:>14} {2:>14} {3:>14}".format(name, *cells))

    # ---- concentration: is a mean carried by a handful of rows? ---------
    print("\n{0:<24} {1:>9} {2:>9} {3:>10} {4:>9} {5:>9}".format(
        "concentration (raw)", "median", "trim5%", "top5 share", "top sym",
        "top day"))
    for name in PROBES:
        rows = [r for r in pops[name] if "lift" in r]
        if len(rows) < 20:
            print("{0:<24} {1:>9}".format(name, "n<20"))
            continue
        vals = sorted(r["fwd"] for r in rows)
        n = len(vals)
        k = max(1, n // 20)
        med = vals[n // 2]
        trim = fmean(vals[k:n - k])
        total = sum(vals)
        top5 = sum(vals[-5:]) / total if total else float("nan")
        cs = defaultdict(int)
        cd = defaultdict(int)
        for r in rows:
            cs[r["symbol"]] += 1
            cd[r["date"]] += 1
        out[label]["probes"][name]["concentration"] = {
            "median": med, "trimmed_mean_5pct": trim,
            "top5_share_of_total": top5,
            "top_symbol_share": max(cs.values()) / n,
            "top_day_share": max(cd.values()) / n}
        print("{0:<24} {1:>+8.3%} {2:>+8.3%} {3:>9.1%} {4:>8.1%} {5:>8.1%}"
              .format(name, med, trim, top5,
                      max(cs.values()) / n, max(cd.values()) / n))


def main():
    s = [p for p in prereg.load() if p["hypothesis_id"] == "H-0019"]
    if not s or s[0]["seal"] != SEAL:
        print("REFUSED: H-0019 seal missing or altered.")
        return 2
    if not prereg.verify_chain()["intact"]:
        print("REFUSED: chain broken.")
        return 2
    if frozen_fingerprint() != FP:
        print("REFUSED: fingerprint moved.")
        return 2
    print("H-0019 seal {0} | controls are NOT part of the seal".format(
        SEAL[:16]))

    series = load()
    rep = production_report(series, conviction=conviction, dataset="decade",
                            purpose="rejection_test", mr_config=CFG)
    m = measure(rep, "BASELINE").as_dict()
    print("baseline {0:+.10%} / {1} trades".format(m["total_return"],
                                                   m["trades"]))
    if abs(m["total_return"] - 0.585889) > 5e-7 or m["trades"] != 698:
        print("STOPPED: baseline not reproduced.")
        return 2

    print("\nrebuilding the gate-passing set ...", flush=True)
    _, obs = build()
    pops = classify(obs)
    out = {"seal": SEAL, "etf_count": len(ETFS & {r["symbol"] for r in obs}),
           "hurdles": list(HURDLES)}

    report("FULL UNIVERSE", obs, pops, out)

    etf_obs = [r for r in obs if r["symbol"] in ETFS]
    etf_pops = {k: [r for r in v if r["symbol"] in ETFS]
                for k, v in pops.items()}
    report("ETF SUBSET (survivorship control)", etf_obs, etf_pops, out)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, default=str))
    print("\nhurdles {0} | wrote {1}".format(
        ", ".join("{0:.2%}".format(h) for h in HURDLES),
        OUT.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
