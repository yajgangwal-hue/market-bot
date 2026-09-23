"""H-0025 - gain-to-loss forensics under the canonical SPEC-0001 boundary.

READ-ONLY over the frozen baseline's own closed trades. Nothing is fitted, no
rule is simulated, no exit is altered, no trade excluded, no band selected.

THE EXECUTION BOUNDARY, CORRECTED. research.PRODUCTION_CANDIDATE fixes
entry_fill="signal_close" and portfolio.py books every rule exit at
bar.close*(1-0.00652). So the price the frozen strategy can actually transact
at, on any bar it can observe, is that bar's own close less the haircut:

  EXECUTABLE       close(t) * (1 - 0.00652)
  MODEL_AVAILABLE  raw close(t); next open(t+1)   [H-0021's headline]
  HINDSIGHT_ONLY   high(t)                        [never an opportunity]

A position entered at the close of bar i0 has its exit first evaluated at bar
i0+1 - portfolio.py increments bars_held at the top of the bar loop and fills
signal_close entries after exit management - so the decision set is [i0+1, i1].
"""

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import fmean, median

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.forward import frozen_fingerprint          # noqa: E402
from event_aware_trader.indicators import (                        # noqa: E402
    rsi, sma, wilder_atr)
from event_aware_trader.mean_reversion import (                    # noqa: E402
    MeanReversionConfig, conviction as shipped_conviction)
from event_aware_trader.modelgov import prereg                     # noqa: E402
from event_aware_trader.phase5.metrics import measure              # noqa: E402
from event_aware_trader.research import production_report          # noqa: E402
from forensics_regime import load                                   # noqa: E402

SEAL = "165fccd43ea4d039845ba047efdd6d0011641c2891f48edcbe96596ed7dd9266"
FP = "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b"
OUT = REPO / "docs" / "phase5" / "h0025-gain-to-loss.json"
HAIRCUT = 0.00652
BANDS = (0.005, 0.01, 0.02, 0.03, 0.05, 0.10)
THIRDS = (("2016-2019", 2016, 2019), ("2020-2023", 2020, 2023),
          ("2024-2026", 2024, 2026))
# Reporting convention, declared here and not tuned: a profitable trade that
# kept less than half its executable peak is "excessive give-back" (B), one
# that kept at least half is "normal development" (A). The full retention
# distribution is printed beside it so the cut does not drive the conclusion.
RETENTION_CUT = 0.50
_conv = {}


def conviction(symbol, history):
    k = (symbol, len(history), history[0].timestamp if history else None)
    v = _conv.get(k)
    if v is None:
        v = _conv[k] = shipped_conviction(history[-40:])
    return v


def pct(values, q):
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def spearman(pairs):
    """Rank correlation with average ranks for ties."""
    n = len(pairs)
    if n < 8:
        return None

    def ranks(vals):
        order = sorted(range(n), key=lambda i: vals[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            r = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                out[order[k]] = r
            i = j + 1
        return out

    rx = ranks([p[0] for p in pairs])
    ry = ranks([p[1] for p in pairs])
    mx, my = fmean(rx), fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def day_collapse(rows, feature_key, outcome_key):
    """One observation per calendar day: clustered positions must not vote
    several times for the same market move."""
    buckets = defaultdict(list)
    for r in rows:
        f, o = r["features"].get(feature_key), r.get(outcome_key)
        if f is None or o is None:
            continue
        buckets[r["cross_date"]].append((f, o))
    return [(fmean([p[0] for p in v]), fmean([p[1] for p in v]))
            for v in buckets.values()]


def main():
    s = [p for p in prereg.load() if p["hypothesis_id"] == "H-0025"]
    if not s or s[0]["seal"] != SEAL:
        print("REFUSED: H-0025 seal missing or altered.")
        return 2
    if not prereg.verify_chain()["intact"] or frozen_fingerprint() != FP:
        print("REFUSED: chain or fingerprint moved.")
        return 2
    print("H-0025 seal {0} | commit {1}".format(SEAL[:16],
                                                s[0]["code_commit"][:12]))

    series = load()
    rep = production_report(series, conviction=conviction, dataset="decade",
                            purpose="rejection_test",
                            mr_config=MeanReversionConfig())
    m = measure(rep, "BASELINE").as_dict()
    print("baseline {0:+.10%} / {1} trades".format(m["total_return"],
                                                   m["trades"]))
    if abs(m["total_return"] - 0.585889) > 5e-7 or m["trades"] != 698:
        print("STOPPED: baseline not reproduced.")
        return 2
    print("MATCH\n")

    idx = {sym: {b.timestamp.date(): i for i, b in enumerate(bars)}
           for sym, bars in series.items()}
    spy = series.get("SPY")
    spy_idx = {b.timestamp.date(): i for i, b in enumerate(spy)} if spy else {}

    trades, skipped = [], 0
    for t in rep.trades:
        bars = series.get(t.symbol)
        if not bars:
            skipped += 1
            continue
        i0 = idx[t.symbol].get(t.entry_time.date())
        i1 = idx[t.symbol].get(t.exit_time.date())
        entry = t.entry_price
        if i0 is None or i1 is None or i1 <= i0 or entry <= 0:
            skipped += 1
            continue
        obs = list(range(i0 + 1, i1 + 1))          # decision set
        x_exec = {j: bars[j].close * (1 - HAIRCUT) / entry - 1 for j in obs}
        x_close = {j: bars[j].close / entry - 1 for j in obs}
        x_open = {j: bars[j].open / entry - 1 for j in obs}
        x_high = {j: bars[j].high / entry - 1 for j in obs}
        realized = t.exit_price / entry - 1
        trades.append({
            "symbol": t.symbol, "year": t.entry_time.year,
            "exit_reason": t.exit_reason, "i0": i0, "i1": i1,
            "entry": entry, "realized": realized, "bars": bars,
            "obs": obs, "x_exec": x_exec, "x_close": x_close,
            "x_open": x_open, "x_high": x_high,
            "peak_exec": max(x_exec.values()),
            "peak_close": max(x_close.values()),
            "peak_open": max(x_open.values()),
            "peak_high": max(x_high.values()),
            "mae_low": min(b.low for b in bars[i0 + 1:i1 + 1]) / entry - 1,
            "net_pnl": t.net_pnl,
        })
    print("trades reconstructed {0} | skipped {1}\n".format(len(trades),
                                                            skipped))

    # ---------------------------------------------------------------- bands
    band_rows = {}
    for band in BANDS:
        rows = []
        for tr in trades:
            star = None
            for j in tr["obs"]:
                if tr["x_exec"][j] >= band:
                    star = j
                    break
            if star is None:
                continue
            after = [j for j in tr["obs"] if j >= star]
            strictly = [j for j in tr["obs"] if j > star]
            peak_after = max(tr["x_exec"][j] for j in after)
            worst_after = min(tr["x_exec"][j] for j in after)
            realized = tr["realized"]
            rows.append({
                "symbol": tr["symbol"], "year": tr["year"],
                "exit_reason": tr["exit_reason"],
                "cross_date": tr["bars"][star].timestamp.date().isoformat(),
                "x_star": tr["x_exec"][star],
                "peak_after": peak_after,
                "giveback": peak_after - realized,
                "worst_after": worst_after,
                "realized": realized,
                "bars_to_exit": tr["i1"] - star,
                "continued": (max(tr["x_exec"][j] for j in strictly)
                              > tr["x_exec"][star]) if strictly else False,
                "retention": (realized / peak_after) if peak_after > 0 else None,
                "net_pnl": tr["net_pnl"],
                "features": features_at(tr, star, spy, spy_idx),
            })
        band_rows[band] = rows

    report = {"seal": SEAL, "fingerprint": FP,
              "baseline": {"total_return": m["total_return"],
                           "trades": m["trades"]},
              "n_trades": len(trades), "skipped": skipped,
              "haircut": HAIRCUT, "retention_cut": RETENTION_CUT,
              "bands": {}, "features": {}, "boundary": {}, "thirds": {}}

    print("=" * 78)
    print("C. GIVE-BACK BY PREDECLARED EXECUTABLE GAIN BAND")
    print("   EXECUTABLE = close(t) x (1 - 0.652%). Forward-looking from the")
    print("   FIRST bar that crossed the band. No band is nominated as best.")
    print("=" * 78)
    hdr = ("band   n    %prof  %loss   med_gb   p75     p90     p95    "
           " med_ret  worst   med_bars  cont%")
    print(hdr)
    for band in BANDS:
        rows = band_rows[band]
        if not rows:
            print("{0:+.1%}  0".format(band))
            continue
        gb = [r["giveback"] for r in rows]
        ret = [r["realized"] for r in rows]
        loss = [r for r in rows if r["realized"] <= 0]
        cont = [r for r in rows if r["continued"]]
        report["bands"]["{0:.3f}".format(band)] = {
            "n": len(rows),
            "pct_profitable": 100.0 * (len(rows) - len(loss)) / len(rows),
            "pct_losing": 100.0 * len(loss) / len(rows),
            "median_giveback": median(gb), "p75": pct(gb, .75),
            "p90": pct(gb, .90), "p95": pct(gb, .95),
            "median_final_return": median(ret),
            "max_subsequent_loss": min(r["worst_after"] for r in rows),
            "worst_realized": min(ret),
            "median_bars_to_exit": median([r["bars_to_exit"] for r in rows]),
            "pct_continued_higher": 100.0 * len(cont) / len(rows),
        }
        b = report["bands"]["{0:.3f}".format(band)]
        print("{0:+.1%} {1:4d}  {2:5.1f}%  {3:5.1f}%  {4:+.2%}  {5:+.2%} "
              " {6:+.2%}  {7:+.2%}  {8:+.2%}  {9:+.2%}  {10:5.1f}    "
              "{11:4.1f}%".format(
                  band, b["n"], b["pct_profitable"], b["pct_losing"],
                  b["median_giveback"], b["p75"], b["p90"], b["p95"],
                  b["median_final_return"], b["worst_realized"],
                  b["median_bars_to_exit"], b["pct_continued_higher"]))

    # ------------------------------------------------- populations A / B / C
    print()
    print("=" * 78)
    print("D. THREE POPULATIONS, NEVER MERGED")
    print("   A normal development (profitable, kept >= 50% of exec peak)")
    print("   B excessive give-back (profitable, kept < 50% of exec peak)")
    print("   C gain-to-loss      (crossed the band, realised a LOSS)")
    print("=" * 78)
    print("band     A    B    C   |  C dollars      C med ret  C med bars"
          "  C stop%")
    for band in BANDS:
        rows = band_rows[band]
        if not rows:
            continue
        A = [r for r in rows if r["realized"] > 0
             and r["retention"] is not None and r["retention"] >= RETENTION_CUT]
        B = [r for r in rows if r["realized"] > 0
             and (r["retention"] is None or r["retention"] < RETENTION_CUT)]
        C = [r for r in rows if r["realized"] <= 0]
        cdollars = sum(r["net_pnl"] for r in C)
        cstop = [r for r in C if r["exit_reason"] == "stop"]
        report["bands"]["{0:.3f}".format(band)].update({
            "pop_A": len(A), "pop_B": len(B), "pop_C": len(C),
            "C_dollars": cdollars,
            "C_median_return": median([r["realized"] for r in C]) if C else None,
            "C_median_bars": median([r["bars_to_exit"] for r in C]) if C else None,
            "C_pct_stop": (100.0 * len(cstop) / len(C)) if C else None,
        })
        print("{0:+.1%} {1:5d} {2:4d} {3:4d}   | {4:12,.0f}   {5}   {6}"
              "      {7}".format(
                  band, len(A), len(B), len(C), cdollars,
                  "{0:+.2%}".format(median([r["realized"] for r in C]))
                  if C else "   n/a ",
                  "{0:5.1f}".format(median([r["bars_to_exit"] for r in C]))
                  if C else "  n/a",
                  "{0:5.1f}%".format(100.0 * len(cstop) / len(C))
                  if C else " n/a"))

    # ------------------------------------------------ thirds on the C class
    print()
    print("   Gain-to-loss share by chronological third (2-of-3 rule):")
    for band in BANDS:
        rows = band_rows[band]
        if not rows:
            continue
        line, shares = [], []
        for name, lo, hi in THIRDS:
            sub = [r for r in rows if lo <= r["year"] <= hi]
            if not sub:
                line.append("{0} n/a".format(name))
                continue
            sh = 100.0 * len([r for r in sub if r["realized"] <= 0]) / len(sub)
            shares.append(sh)
            line.append("{0} {1:.1f}% (n={2})".format(name, sh, len(sub)))
        report["thirds"]["{0:.3f}".format(band)] = shares
        print("   {0:+.1%}  {1}".format(band, "   ".join(line)))

    # ------------------------------------------------------ concentration
    print()
    print("   Concentration of the gain-to-loss loss pool (band +2%):")
    rows2 = band_rows[0.02]
    C2 = [r for r in rows2 if r["realized"] <= 0]
    if C2:
        bysym = defaultdict(float)
        for r in C2:
            bysym[r["symbol"]] += r["net_pnl"]
        tot = sum(bysym.values())
        top = sorted(bysym.items(), key=lambda kv: kv[1])[:5]
        print("   total {0:,.0f} over {1} trades | top 5 symbols {2:.1f}% "
              "({3})".format(tot, len(C2),
                             100.0 * sum(v for _, v in top) / tot if tot else 0,
                             ", ".join(k for k, _ in top)))
        worst = sorted(C2, key=lambda r: r["net_pnl"])[:5]
        print("   top 5 trades {0:.1f}%".format(
            100.0 * sum(r["net_pnl"] for r in worst) / tot if tot else 0))
        report["concentration_2pct"] = {
            "total": tot, "n": len(C2),
            "top5_symbols_pct": 100.0 * sum(v for _, v in top) / tot if tot else 0,
            "top5_trades_pct": 100.0 * sum(r["net_pnl"] for r in worst) / tot
            if tot else 0,
            "top5_symbols": [k for k, _ in top]}

    # -------------------------------------------------------- exit reasons
    print()
    print("   Band +2% crossings by exit reason:")
    byreason = defaultdict(list)
    for r in rows2:
        byreason[r["exit_reason"]].append(r)
    report["by_reason_2pct"] = {}
    for reason, rs in sorted(byreason.items()):
        L = [r for r in rs if r["realized"] <= 0]
        report["by_reason_2pct"][reason] = {
            "n": len(rs), "pct_loss": 100.0 * len(L) / len(rs),
            "median_giveback": median([r["giveback"] for r in rs]),
            "median_realized": median([r["realized"] for r in rs])}
        print("   {0:12s} n={1:4d}  loss {2:5.1f}%  med give-back {3:+.2%}"
              "  med realised {4:+.2%}".format(
                  reason, len(rs), 100.0 * len(L) / len(rs),
                  median([r["giveback"] for r in rs]),
                  median([r["realized"] for r in rs])))

    # ---------------------------------------------------- boundary compare
    print()
    print("=" * 78)
    print("F. THE H-0021 COMPARISON - same trades, four price boundaries")
    print("=" * 78)
    rule = [tr for tr in trades if tr["exit_reason"] != "stop"]
    report["boundary"] = {}
    for name, key, label in (
            ("HIGH        HINDSIGHT ONLY", "peak_high", "unexecutable"),
            ("CLOSE       model-available", "peak_close", "observable"),
            ("NEXT OPEN   model-available", "peak_open", "H-0021 headline"),
            ("CLOSE-h     EXECUTABLE", "peak_exec", "canonical SPEC-0001")):
        peaks = [tr[key] for tr in rule]
        gbs = [tr[key] - tr["realized"] for tr in rule]
        sp = sum(tr[key] for tr in rule)
        sr = sum(tr["realized"] for tr in rule)
        rets = [tr["realized"] / tr[key] for tr in rule if tr[key] > 0]
        report["boundary"][key] = {
            "label": label, "n": len(rule), "mean_peak": fmean(peaks),
            "median_peak": median(peaks), "mean_giveback": fmean(gbs),
            "median_giveback": median(gbs),
            "aggregate_capture": sr / sp if sp else None,
            "median_capture": median(rets) if rets else None}
        b = report["boundary"][key]
        print("{0:32s} peak {1:+.3%}  give-back {2:+.3%}  capture agg "
              "{3:5.1%}  med {4:5.1%}".format(
                  name, b["mean_peak"], b["mean_giveback"],
                  b["aggregate_capture"], b["median_capture"]))
    print("   (rule exits only, n={0} - H-0021's population, so the rows are"
          " comparable)".format(len(rule)))

    # ------------------------------------------------------------ features
    print()
    print("=" * 78)
    print("E. CROSSING-TIME FEATURES - Spearman IC vs realised return")
    print("   Day-collapsed. Information at or before t* only. NO MODEL FIT.")
    print("=" * 78)
    feat_names = ["x_star", "rsi", "atr_frac", "bars_held", "dd_from_peak",
                  "vol_ratio", "spy_rel", "spy_rsi", "px_sma200"]
    for band in (0.01, 0.02, 0.03):
        rows = band_rows[band]
        print("\n   band {0:+.1%}  (n={1} crossings)".format(band, len(rows)))
        report["features"]["{0:.3f}".format(band)] = {}
        for f in feat_names:
            pairs = day_collapse(rows, f, "realized")
            ic = spearman(pairs)
            sub = []
            for name, lo, hi in THIRDS:
                pr = day_collapse([r for r in rows if lo <= r["year"] <= hi],
                                  f, "realized")
                sub.append(spearman(pr))
            report["features"]["{0:.3f}".format(band)][f] = {
                "ic": ic, "n_days": len(pairs), "thirds": sub}
            same = None
            if ic is not None and all(x is not None for x in sub):
                same = sum(1 for x in sub if (x > 0) == (ic > 0))
            print("   {0:13s} IC {1}  days {2:4d}   thirds {3}  {4}".format(
                f,
                "{0:+.4f}".format(ic) if ic is not None else "  n/a  ",
                len(pairs),
                " ".join("{0:+.3f}".format(x) if x is not None else " n/a "
                         for x in sub),
                "{0}/3 agree".format(same) if same is not None else ""))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str),
                   encoding="utf-8")
    print("\nwrote {0}".format(OUT))
    print("fingerprint {0} | chain {1}".format(
        frozen_fingerprint()[:16], prereg.verify_chain()["intact"]))
    return 0


def features_at(tr, star, spy, spy_idx):
    """Everything computable from bars at or before t*. Nothing after."""
    bars = tr["bars"]
    hist = bars[:star + 1]
    closes = [b.close for b in hist]
    d = bars[star].timestamp.date()
    out = {"x_star": tr["x_exec"][star], "bars_held": star - tr["i0"]}
    out["rsi"] = rsi(closes, 14)
    a = wilder_atr(hist, 14)
    out["atr_frac"] = (a / bars[star].close) if a and bars[star].close else None
    prior = [j for j in tr["obs"] if j <= star]
    peak_so_far = max(tr["x_exec"][j] for j in prior)
    out["dd_from_peak"] = peak_so_far - tr["x_exec"][star]
    vols = [b.volume for b in bars[max(0, star - 20):star]]
    mv = fmean(vols) if vols else None
    out["vol_ratio"] = (bars[star].volume / mv) if mv else None
    out["px_sma200"] = ((bars[star].close / sma(closes, 200) - 1)
                        if sma(closes, 200) else None)
    out["spy_rel"] = None
    out["spy_rsi"] = None
    if spy and d in spy_idx:
        si = spy_idx[d]
        d0 = bars[tr["i0"]].timestamp.date()
        if d0 in spy_idx:
            s0 = spy_idx[d0]
            if s0 < si:
                sret = spy[si].close / spy[s0].close - 1
                out["spy_rel"] = (bars[star].close / tr["entry"] - 1) - sret
        out["spy_rsi"] = rsi([b.close for b in spy[:si + 1]], 14)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
