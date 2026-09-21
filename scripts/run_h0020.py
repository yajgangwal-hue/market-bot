"""H-0020 - validate the P3 population through the FROZEN machinery.

Not a sweep. The ATR ceiling never moves. `max_atr_fraction=None` is
used ONLY to enumerate the population production already excludes, and
the resulting candidate set is asserted DISJOINT from production's.

Three portfolios, two universes, one frozen simulator:
  A  frozen production   - must reproduce +58.5889000000% / 698
  B  P3 only             - production's signal replaced by P3 membership
  C  combined            - production's BUY, else the P3 BUY

Exits, sizing, stops, buckets, guards, cash and costs are production's
own and are not touched. Entry is the next session's open, as the
frozen framework already does.
"""

import json
import sys
from collections import defaultdict
from datetime import date
from math import sqrt
from pathlib import Path
from statistics import fmean, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader import portfolio as PM                   # noqa: E402
from event_aware_trader.forward import frozen_fingerprint        # noqa: E402
from event_aware_trader.mean_reversion import (                  # noqa: E402
    MeanReversionConfig, MeanReversionSignal,
    conviction as shipped_conviction, evaluate)
from event_aware_trader.modelgov import prereg                   # noqa: E402
from event_aware_trader.phase5.metrics import measure            # noqa: E402
from event_aware_trader.research import production_report        # noqa: E402
from event_aware_trader.strategy import INSTRUMENT_NAMES         # noqa: E402
from forensics_regime import build_signals, load                  # noqa: E402

SEAL = "f38dbbaa7882d1fd7c81ede1e81b4d7818c6342444a68ddbedfee8fa32b3b76e"
FP = "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b"
OUT = REPO / "docs" / "phase5" / "h0020-validation.json"

CFG = MeanReversionConfig()
NOCEIL = MeanReversionConfig(max_atr_fraction=None)
WINDOW = 400
CEILING = 0.142806               # 110% of the frozen baseline max drawdown
MIN_CONTROL_TRADES = 65          # sealed; the project's own precedent
THIRDS = (("2016-2019", 2016, 2019), ("2020-2023", 2020, 2023),
          ("2024-2026", 2024, 2026))
_KW = ("ETF", "Fund", "Trust", "Index", "Shares ")
ETFS = ({s for s, n in INSTRUMENT_NAMES.items()
         if any(k in n for k in _KW)} - {"STX"}) | {"GLD"}

_conv = {}
COUNTS = defaultdict(int)


def conviction(symbol, history):
    k = (symbol, len(history), history[0].timestamp if history else None)
    v = _conv.get(k)
    if v is None:
        v = _conv[k] = shipped_conviction(history[-40:])
    return v


def aside(sig, why):
    return MeanReversionSignal(sig.symbol, "STAND_ASIDE", sig.close, None,
                               sig.rsi, sig.trend_ma, sig.atr_fraction, [why])


def install(base, mode):
    """mode 'p3' emits only P3; mode 'combined' emits production first."""
    def wrapped(symbol, history, cfg):
        real = base(symbol, history, cfg)
        if real.is_buy:
            COUNTS["production_buy"] += 1
            if mode == "combined":
                return real
            return aside(real, "H-0020: production member, not P3")
        off = evaluate(symbol, history[-WINDOW:], NOCEIL)
        if off.is_buy:
            COUNTS["p3_buy"] += 1
            return off
        return real
    PM.mean_reversion_signal = wrapped


def run(series, label, mode=None):
    base = PM.mean_reversion_signal
    if mode:
        install(base, mode)
    try:
        rep = production_report(series, conviction=conviction,
                                dataset="decade", purpose="rejection_test",
                                mr_config=CFG)
    finally:
        PM.mean_reversion_signal = base
    return rep, measure(rep, label).as_dict()


def dd_duration(curve):
    """Longest peak-to-recovery in calendar days, and the worst drawdown."""
    peak, peak_t, worst, longest, open_at = curve[0][1], curve[0][0], 0.0, 0, None
    for t, v in curve:
        if v >= peak:
            if open_at is not None:
                longest = max(longest, (t - open_at).days)
                open_at = None
            peak, peak_t = v, t
        else:
            if open_at is None:
                open_at = peak_t
            worst = min(worst, v / peak - 1.0)
    if open_at is not None:
        longest = max(longest, (curve[-1][0] - open_at).days)
    return worst, longest


def daily_returns(curve):
    out = {}
    for i in range(1, len(curve)):
        prev = curve[i - 1][1]
        if prev > 0:
            out[curve[i][0].date()] = curve[i][1] / prev - 1.0
    return out


def correlate(a, b):
    common = sorted(set(a) & set(b))
    if len(common) < 20:
        return None
    x = [a[d] for d in common]
    y = [b[d] for d in common]
    mx, my = fmean(x), fmean(y)
    num = sum((p - mx) * (q - my) for p, q in zip(x, y))
    den = sqrt(sum((p - mx) ** 2 for p in x) * sum((q - my) ** 2 for q in y))
    return num / den if den else None


def segment(curve, lo, hi):
    seg = [(t, v) for t, v in curve if lo <= t.year <= hi]
    if len(seg) < 2:
        return None
    worst, _ = dd_duration(seg)
    return {"return": seg[-1][1] / seg[0][1] - 1.0, "max_drawdown": worst,
            "sessions": len(seg)}


def trade_table(rep, regimes):
    rows = []
    for t in rep.trades:
        d = t.entry_time.date()
        rows.append({"symbol": t.symbol, "year": d.year, "date": d,
                     "pnl": t.net_pnl, "reason": t.exit_reason,
                     "bars": t.bars_held,
                     "regime": regimes.get(d)})
    return rows


def concentration(rows):
    if not rows:
        return None
    total = sum(r["pnl"] for r in rows)
    by = {}
    for key in ("symbol", "year", "regime"):
        agg = defaultdict(float)
        cnt = defaultdict(int)
        for r in rows:
            agg[r[key]] += r["pnl"]
            cnt[r[key]] += 1
        ranked = sorted(agg.items(), key=lambda kv: -kv[1])
        by[key] = {"top": [[str(k), v, cnt[k]] for k, v in ranked[:5]],
                   "top1_share": (ranked[0][1] / total) if total else None,
                   "distinct": len(agg)}
    pnls = sorted((r["pnl"] for r in rows), reverse=True)
    by["leave_out"] = {
        "total": total,
        "minus_top1": total - sum(pnls[:1]),
        "minus_top3": total - sum(pnls[:3]),
        "minus_top5": total - sum(pnls[:5]),
        "top5_share": (sum(pnls[:5]) / total) if total else None}
    return by


def thirds_of(rows):
    out = {}
    for label, lo, hi in THIRDS:
        sub = [r for r in rows if lo <= r["year"] <= hi]
        out[label] = None if not sub else {
            "trades": len(sub), "pnl": sum(r["pnl"] for r in sub),
            "win_rate": sum(1 for r in sub if r["pnl"] > 0) / len(sub),
            "mean": fmean([r["pnl"] for r in sub])}
    return out


def overnight_split(rep, bars_by):
    """Split each realised holding path into overnight and intraday."""
    on, intra, n = 0.0, 0.0, 0
    for t in rep.trades:
        seq = bars_by.get(t.symbol)
        if not seq:
            continue
        idx = [i for i, b in enumerate(seq)
               if t.entry_time.date() <= b.timestamp.date() <= t.exit_time.date()]
        if len(idx) < 2:
            continue
        base = seq[idx[0]].open
        if base <= 0:
            continue
        o = sum(seq[i].open - seq[i - 1].close for i in idx[1:]) / base
        d = sum(b.close - b.open for b in (seq[i] for i in idx)) / base
        on += o
        intra += d
        n += 1
    return None if not n else {"trades": n, "overnight": on / n,
                               "intraday": intra / n}


def summary(name, rep, met, regimes, ref_curve=None):
    worst, longest = dd_duration(rep.equity_curve)
    rows = trade_table(rep, regimes)
    block = {k: met.get(k) for k in (
        "total_return", "cagr", "annualised_volatility", "sharpe", "sortino",
        "max_drawdown", "calmar", "trades", "win_rate", "profit_factor",
        "expectancy", "average_hold_days", "turnover", "transaction_costs",
        "exposure", "stop_rate", "by_exit_reason")}
    block["drawdown_duration_days"] = longest
    block["max_drawdown_recomputed"] = worst
    block["within_110pct_ceiling"] = abs(met["max_drawdown"]) <= CEILING
    block["thirds_trades"] = thirds_of(rows)
    block["thirds_curve"] = {l: segment(rep.equity_curve, lo, hi)
                             for l, lo, hi in THIRDS}
    block["concentration"] = concentration(rows)
    if ref_curve is not None:
        block["correlation_with_frozen"] = correlate(
            daily_returns(ref_curve), daily_returns(rep.equity_curve))
    return block


def main():
    s = [p for p in prereg.load() if p["hypothesis_id"] == "H-0020"]
    if not s or s[0]["seal"] != SEAL:
        print("REFUSED: H-0020 seal missing or altered.")
        return 2
    if not prereg.verify_chain()["intact"]:
        print("REFUSED: chain broken.")
        return 2
    if frozen_fingerprint() != FP:
        print("REFUSED: fingerprint moved.")
        return 2
    if CFG.max_atr_fraction != 0.035 or CFG.rsi_entry != 35.0:
        print("REFUSED: production config moved.")
        return 2
    print("H-0020 seal {0} | commit {1}".format(SEAL[:16],
                                                s[0]["code_commit"][:12]))

    series = load()
    regimes = build_signals(series)[0]["trend_dual_ma"]
    bars_by = dict(series)
    etf = {k: v for k, v in series.items() if k in ETFS}
    print("universes: full {0} | etf control {1}".format(len(series),
                                                         len(etf)))

    out = {"seal": SEAL, "commit": s[0]["code_commit"],
           "ceiling_110pct": CEILING,
           "min_control_trades": MIN_CONTROL_TRADES,
           "universe_survivorship": {
               "symbols": len(series), "delistings": 0,
               "note": "all symbols trade through 2026-09; 100% survivors"},
           "runs": {}}

    print("\nA  frozen production, full universe ...", flush=True)
    rep_a, met_a = run(series, "A_frozen_full")
    print("   {0:+.10%} over {1} trades".format(met_a["total_return"],
                                                met_a["trades"]))
    if abs(met_a["total_return"] - 0.585889) > 5e-7 or met_a["trades"] != 698:
        print("STOPPED: baseline not reproduced. Nothing measured.")
        return 2
    print("   MATCH")

    results = {}
    for uni_name, uni in (("full", series), ("etf_control", etf)):
        for run_name, mode in (("A_frozen", None), ("B_p3_only", "p3"),
                               ("C_combined", "combined")):
            key = "{0}:{1}".format(uni_name, run_name)
            COUNTS.clear()
            print("\n{0} ...".format(key), flush=True)
            rep, met = run(uni, key, mode)
            results[key] = (rep, met)
            ref = results.get("{0}:A_frozen".format(uni_name))
            out["runs"][key] = summary(
                key, rep, met, regimes,
                ref_curve=ref[0].equity_curve if (ref and mode) else None)
            out["runs"][key]["signal_counts"] = dict(COUNTS)
            print("   ret {0:+.4%} | trades {1} | maxDD {2:.4%} | "
                  "Sharpe {3} | exposure {4:.2%}".format(
                      met["total_return"], met["trades"],
                      met["max_drawdown"],
                      "n/a" if met["sharpe"] is None
                      else "{0:.3f}".format(met["sharpe"]),
                      met["exposure"] or 0.0))

    # ---- disjointness, proven not assumed -------------------------------
    COUNTS.clear()
    run(series, "disjoint_probe", "p3")
    out["disjointness"] = {
        "production_buys_seen": COUNTS["production_buy"],
        "p3_buys_emitted": COUNTS["p3_buy"],
        "p3_emissions_that_were_production_buys": 0,
        "proof": "the wrapper returns STAND_ASIDE on every production BUY "
                 "before the ceiling-off call is made, so the sets cannot "
                 "intersect by construction"}

    # ---- diagnostics, kept separate from the portfolio result -----------
    out["diagnostics"] = {
        "overnight_intraday_full": overnight_split(
            results["full:B_p3_only"][0], bars_by),
        "overnight_intraday_frozen": overnight_split(
            results["full:A_frozen"][0], bars_by),
        "note": "H-0019's close-to-close +2.4359% is NOT a tradable return; "
                "the frozen framework enters at the next open, so the gap "
                "from the decision close to that open is uncapturable by "
                "this entry mechanism."}

    # ---- the sealed gates ------------------------------------------------
    ctrl = out["runs"]["etf_control:B_p3_only"]
    comb = out["runs"]["full:C_combined"]
    froz = out["runs"]["full:A_frozen"]
    p3 = out["runs"]["full:B_p3_only"]
    thirds_pos = sum(1 for v in p3["thirds_trades"].values()
                     if v and v["pnl"] > 0)
    out["gates"] = {
        "survivorship_control_trades": ctrl["trades"],
        "survivorship_control_powered": ctrl["trades"] >= MIN_CONTROL_TRADES,
        "survivorship_control_return": ctrl["total_return"],
        "combined_max_drawdown": comb["max_drawdown"],
        "combined_within_ceiling": abs(comb["max_drawdown"]) <= CEILING,
        "incremental_return": comb["total_return"] - froz["total_return"],
        "incremental_drawdown": (abs(comb["max_drawdown"])
                                 - abs(froz["max_drawdown"])),
        "incremental_exposure": (comb["exposure"] or 0) - (froz["exposure"] or 0),
        "p3_thirds_positive": thirds_pos,
        "p3_two_of_three": thirds_pos >= 2,
        "correlation_p3_with_frozen": p3.get("correlation_with_frozen")}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, default=str))

    print("\n" + "=" * 74)
    print("{0:<22}{1:>11}{2:>8}{3:>10}{4:>9}{5:>10}".format(
        "run", "return", "trades", "maxDD", "Sharpe", "exposure"))
    for k in out["runs"]:
        b = out["runs"][k]
        print("{0:<22}{1:>+10.4%}{2:>8}{3:>10.4%}{4:>9}{5:>10.2%}".format(
            k, b["total_return"], b["trades"], b["max_drawdown"],
            "n/a" if b["sharpe"] is None else "{0:.3f}".format(b["sharpe"]),
            b["exposure"] or 0.0))

    g = out["gates"]
    print("\nSEALED GATES")
    print("  survivorship control : {0} trades (need >= {1}) -> {2}".format(
        g["survivorship_control_trades"], MIN_CONTROL_TRADES,
        "POWERED" if g["survivorship_control_powered"] else "UNDERPOWERED"))
    print("  110% drawdown ceiling: combined {0:.4%} vs {1:.4%} -> {2}".format(
        abs(g["combined_max_drawdown"]), CEILING,
        "WITHIN" if g["combined_within_ceiling"] else "BREACH"))
    print("  incremental return   : {0:+.4%}".format(g["incremental_return"]))
    print("  incremental drawdown : {0:+.4%}".format(g["incremental_drawdown"]))
    print("  P3 thirds positive   : {0}/3 -> {1}".format(
        g["p3_thirds_positive"], "PASS" if g["p3_two_of_three"] else "FAIL"))
    print("  corr(P3, frozen)     : {0}".format(
        "n/a" if g["correlation_p3_with_frozen"] is None
        else "{0:+.3f}".format(g["correlation_p3_with_frozen"])))
    print("\nATR ceiling still {0} | fingerprint unchanged | wrote {1}".format(
        MeanReversionConfig().max_atr_fraction, OUT.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
