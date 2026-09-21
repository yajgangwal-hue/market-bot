"""H-0021 - give-back anatomy against a price the bot could actually pay.

READ-ONLY over the frozen baseline's own closed trades. Nothing is
fitted, no rule is simulated, no exit is altered, no trade excluded.

THREE PEAKS, NEVER MERGED:
  PEAK_HIGH      highest intraday high while held. NOT EXECUTABLE.
  PEAK_CLOSE     highest close while held - observable at a decision.
  PEAK_NEXTOPEN  highest open on a session AFTER an observed close -
                 the only peak the bot could have TRANSACTED at, and
                 the headline.

The bot decides on closes and executes at the next open, so
PEAK_NEXTOPEN scans opens at indices entry+1 .. exit, each of which
follows a close the rule could have seen.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import fmean, median

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.forward import frozen_fingerprint        # noqa: E402
from event_aware_trader.mean_reversion import (                  # noqa: E402
    MeanReversionConfig, conviction as shipped_conviction)
from event_aware_trader.modelgov import prereg                   # noqa: E402
from event_aware_trader.phase5.metrics import measure            # noqa: E402
from event_aware_trader.research import production_report        # noqa: E402
from forensics_regime import build_signals, load                  # noqa: E402

SEAL = "563d778ab428a056d898cc50723dbd5071f6927488a0a17c617b97a71feddb64"
FP = "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b"
OUT = REPO / "docs" / "phase5" / "h0021-giveback.json"
BANDS = (0.5, 1.0, 2.0)
THIRDS = (("2016-2019", 2016, 2019), ("2020-2023", 2020, 2023),
          ("2024-2026", 2024, 2026))
_conv = {}


def conviction(symbol, history):
    k = (symbol, len(history), history[0].timestamp if history else None)
    v = _conv.get(k)
    if v is None:
        v = _conv[k] = shipped_conviction(history[-40:])
    return v


def stat(vals):
    if not vals:
        return None
    return {"n": len(vals), "mean": fmean(vals), "median": median(vals),
            "min": min(vals), "max": max(vals)}


def main():
    s = [p for p in prereg.load() if p["hypothesis_id"] == "H-0021"]
    if not s or s[0]["seal"] != SEAL:
        print("REFUSED: H-0021 seal missing or altered.")
        return 2
    if not prereg.verify_chain()["intact"] or frozen_fingerprint() != FP:
        print("REFUSED: chain or fingerprint moved.")
        return 2
    print("H-0021 seal {0} | commit {1}".format(SEAL[:16],
                                                s[0]["code_commit"][:12]))

    series = load()
    regimes = build_signals(series)[0]["trend_dual_ma"]
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
    rows, no_r = [], 0
    for t in rep.trades:
        bars = series.get(t.symbol)
        if not bars:
            continue
        i0 = idx[t.symbol].get(t.entry_time.date())
        i1 = idx[t.symbol].get(t.exit_time.date())
        if i0 is None or i1 is None or i1 < i0:
            continue
        entry = t.entry_price
        if entry <= 0:
            continue
        risk = ((entry - t.initial_stop) / entry
                if 0 < t.initial_stop < entry else None)
        if risk is None:
            no_r += 1
        hold = bars[i0:i1 + 1]
        peak_high = max(b.high for b in hold)
        peak_close = max(b.close for b in hold)
        # Opens on sessions AFTER a close the rule could have observed.
        nxt = [bars[i].open for i in range(i0 + 1, i1 + 1)]
        peak_nextopen = max(nxt) if nxt else bars[i0].open
        trough = min(b.low for b in hold)
        rows.append({
            "symbol": t.symbol, "year": t.entry_time.year,
            "date": t.entry_time.date(), "reason": t.exit_reason,
            "bars": t.bars_held, "qty": t.quantity, "pnl": t.net_pnl,
            "entry": entry, "exit": t.exit_price, "risk": risk,
            "regime": regimes.get(t.entry_time.date()),
            "realised_pct": t.exit_price / entry - 1.0,
            "peak_high_pct": peak_high / entry - 1.0,
            "peak_close_pct": peak_close / entry - 1.0,
            "peak_nextopen_pct": peak_nextopen / entry - 1.0,
            "mae_pct": trough / entry - 1.0,
            "gb_high": (peak_high - t.exit_price) / entry,
            "gb_close": (peak_close - t.exit_price) / entry,
            "gb_nextopen": (peak_nextopen - t.exit_price) / entry,
            "gb_nextopen_usd": max(0.0, peak_nextopen - t.exit_price) * t.quantity,
        })

    print("trades analysed {0} | without a usable R {1}".format(len(rows),
                                                                no_r))
    rule = [r for r in rows if r["reason"] != "stop"]
    stops = [r for r in rows if r["reason"] == "stop"]

    def in_r(r, key):
        return (r[key] / r["risk"]) if r["risk"] else None

    out = {"seal": SEAL, "commit": s[0]["code_commit"],
           "baseline": {"total_return": m["total_return"],
                        "trades": m["trades"]},
           "analysed": len(rows), "without_R": no_r,
           "rule_exits": len(rule), "stop_exits": len(stops)}

    print("\n{0:<16}{1:>10}{2:>12}{3:>12}{4:>12}".format(
        "peak (rule exits)", "n", "mean peak", "mean giveback", "capture"))
    for label, pk, gb in (("HIGH (NOT EXEC)", "peak_high_pct", "gb_high"),
                          ("CLOSE (observ.)", "peak_close_pct", "gb_close"),
                          ("NEXTOPEN (exec)", "peak_nextopen_pct",
                           "gb_nextopen")):
        peaks = [r[pk] for r in rule]
        gbs = [r[gb] for r in rule]
        # AGGREGATE capture, not a mean of ratios. A trade whose peak is
        # 0.01% above entry produces a ratio in the hundreds, so a mean of
        # per-trade ratios is dominated by trades with no peak to speak of.
        sp = sum(p for p in peaks if p > 0)
        sr = sum(r["realised_pct"] for r in rule if r[pk] > 0)
        cap = (sr / sp) if sp > 0 else None
        # and the median ratio over trades with a peak worth measuring
        big = [r for r in rule if r["risk"] and r[pk] / r["risk"] >= 0.5]
        medcap = (median([r["realised_pct"] / r[pk] for r in big])
                  if big else None)
        out[label] = {"peak": stat(peaks), "giveback": stat(gbs),
                      "capture_aggregate": cap,
                      "capture_median_ratio_over_0p5R": medcap,
                      "n_over_0p5R": len(big)}
        print("{0:<16}{1:>10}{2:>+11.3%}{3:>+12.3%}{4:>11}{5:>11}".format(
            label, len(peaks), fmean(peaks), fmean(gbs),
            "n/a" if cap is None else "{0:.1%}".format(cap),
            "n/a" if medcap is None else "{0:.1%}".format(medcap)))

    # ---- the sealed bands, on the executable peak only ------------------
    print("\nEXECUTABLE bands - rule exits whose PEAK_NEXTOPEN reached N x R")
    print("{0:>6}{1:>8}{2:>10}{3:>14}{4:>14}{5:>12}".format(
        "band", "trades", "share", "mean giveback", "median gb", "total $"))
    out["bands"] = {}
    usable = [r for r in rule if r["risk"]]
    for band in BANDS:
        sub = [r for r in usable if in_r(r, "peak_nextopen_pct") >= band]
        if not sub:
            out["bands"][str(band)] = None
            print("{0:>6}{1:>8}".format(band, 0))
            continue
        gb = [in_r(r, "gb_nextopen") for r in sub]
        usd = sum(r["gb_nextopen_usd"] for r in sub)
        out["bands"][str(band)] = {
            "trades": len(sub), "share_of_rule_exits": len(sub) / len(usable),
            "mean_giveback_R": fmean(gb), "median_giveback_R": median(gb),
            "total_giveback_usd": usd,
            "mean_realised_R": fmean([in_r(r, "realised_pct") for r in sub])}
        print("{0:>6}{1:>8}{2:>10.1%}{3:>+13.3f}R{4:>+13.3f}R{5:>12,.0f}"
              .format(band, len(sub), len(sub) / len(usable), fmean(gb),
                      median(gb), usd))

    # ---- splits ---------------------------------------------------------
    def split(rows_, key):
        agg = defaultdict(list)
        for r in rows_:
            agg[str(r[key])].append(r)
        return {k: {"trades": len(v),
                    "mean_gb_nextopen": fmean([x["gb_nextopen"] for x in v]),
                    "total_gb_usd": sum(x["gb_nextopen_usd"] for x in v),
                    "mean_realised": fmean([x["realised_pct"] for x in v])}
                for k, v in sorted(agg.items())}

    out["by_exit_reason"] = split(rows, "reason")
    out["by_regime"] = split(rule, "regime")
    out["by_year"] = split(rule, "year")
    out["thirds"] = {}
    for label, lo, hi in THIRDS:
        sub = [r for r in rule if lo <= r["year"] <= hi]
        out["thirds"][label] = None if not sub else {
            "trades": len(sub),
            "mean_gb_nextopen": fmean([r["gb_nextopen"] for r in sub]),
            "total_gb_usd": sum(r["gb_nextopen_usd"] for r in sub)}
    out["stops_separate"] = {
        "trades": len(stops),
        "mean_gb_nextopen": fmean([r["gb_nextopen"] for r in stops]) if stops else None,
        "note": "a stop fills when hit; the price was not a choice, so this "
                "is not give-back the bot declined to take"}

    total_gb = sum(r["gb_nextopen_usd"] for r in rule)
    net_gb = sum((r["peak_nextopen_pct"] - r["realised_pct"]) * r["entry"]
                 * r["qty"] for r in rule)
    per_sym = defaultdict(float)
    for r in rule:
        per_sym[r["symbol"]] += r["gb_nextopen_usd"]
    top = sorted(per_sym.items(), key=lambda kv: -kv[1])[:5]
    ordered = sorted((r["gb_nextopen_usd"] for r in rule), reverse=True)
    out["concentration"] = {
        "total_giveback_usd": total_gb,
        "top5_symbols": top,
        "top5_symbol_share": sum(v for _, v in top) / total_gb if total_gb else None,
        "top5_trade_share": sum(ordered[:5]) / total_gb if total_gb else None,
        "starting_equity_pts": total_gb / 1000.0,
        "net_two_sided_usd": net_gb,
        "note": "total_giveback_usd counts only trades that gave something back (max(0,..)), so it is a ONE-SIDED recoverable pool and an upper bound, not a net"}

    print("\nby exit reason (all trades)")
    for k, v in out["by_exit_reason"].items():
        print("  {0:<12} n={1:<5} mean gb {2:>+8.3%}  realised {3:>+8.3%}  "
              "$ {4:>10,.0f}".format(k, v["trades"], v["mean_gb_nextopen"],
                                     v["mean_realised"], v["total_gb_usd"]))
    print("\nthirds (rule exits, executable give-back)")
    for k, v in out["thirds"].items():
        print("  {0:<12} n={1:<5} mean {2:>+8.3%}  $ {3:>10,.0f}".format(
            k, v["trades"], v["mean_gb_nextopen"], v["total_gb_usd"]))
    print("\nregime (rule exits)")
    for k, v in out["by_regime"].items():
        print("  {0:<14} n={1:<5} mean {2:>+8.3%}  $ {3:>10,.0f}".format(
            k, v["trades"], v["mean_gb_nextopen"], v["total_gb_usd"]))

    c = out["concentration"]
    print("\nexecutable give-back total ${0:,.0f} = {1:.2f} pts of starting "
          "equity".format(total_gb, c["starting_equity_pts"]))
    print("  top 5 symbols {0:.1%} | top 5 trades {1:.1%}".format(
        c["top5_symbol_share"] or 0, c["top5_trade_share"] or 0))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, default=str))
    print("\nwrote {0}".format(OUT.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
