"""Adjudicate H-0009 against the sealed clauses. Nothing is chosen here.

The five clauses are applied in the registered order: (A) return above
baseline by more than the 2-point complexity penalty, (B) drawdown
within 1.10 x the baseline's 12.9824%, (C) gradient rather than spike,
(D) displacement - the gain must not come from evicting better names,
(E) survives removal of the single best calendar year.

CLAUSE D IS THE CENTRAL ONE. Each configuration's entries are
classified against what the BASELINE did on the same session, and only
the EMPTY class is a free addition. A swap is worth what it took minus
what the baseline took instead, measured trade by trade.
"""

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import fmean, median, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.modelgov import prereg                  # noqa: E402
from forensics_regime import build_signals, load, STATES         # noqa: E402

CACHE = REPO / "docs" / "phase5" / "h0009-cache.json"
PENALTY = 0.02
CEILING_MULTIPLE = 1.10
DOMINANCE = 2.5
ORDER = [("A rsi36", 36.0), ("B rsi37", 37.0), ("C rsi38", 38.0)]
HORIZONS = (5, 10, 20)


def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos + 1.0
        return r
    rx, ry = rank(xs), rank(ys)
    mx, my = fmean(rx), fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def main():
    if not CACHE.exists():
        print("no cache; run scripts/run_h0009.py first")
        return 2
    store = json.loads(CACHE.read_text(encoding="utf-8"))
    missing = [lab for lab, _r in ORDER if lab not in store]
    if "BASELINE" not in store or missing:
        print("cache incomplete; missing {0}".format(
            (["BASELINE"] if "BASELINE" not in store else []) + missing))
        return 2
    seal = [p for p in prereg.load() if p["hypothesis_id"] == "H-0009"][0]
    base = store["BASELINE"]
    bm = base["metrics"]
    ceiling = CEILING_MULTIPLE * abs(bm["max_drawdown"])

    series = load()
    spy = series["SPY"]
    spy_total = spy[-1].close / spy[0].close - 1.0
    spy_close = {b.timestamp.date(): b.close for b in spy}
    closes = {s: {b.timestamp.date(): b.close for b in bs}
              for s, bs in series.items()}
    dates = {s: [b.timestamp.date() for b in bs] for s, bs in series.items()}
    index = {s: {d: i for i, d in enumerate(ds)} for s, ds in dates.items()}
    spy_d, spy_i = dates["SPY"], index["SPY"]

    print("H-0009 seal {0}".format(seal["seal"][:16]))
    print("baseline  total {0:+.4%}  maxDD {1:.4%}  trades {2}".format(
        bm["total_return"], bm["max_drawdown"], bm["trades"]))
    print("clause B ceiling: 1.10 x {0:.4%} = {1:.4%}".format(
        abs(bm["max_drawdown"]), ceiling))
    print("clause A needs:   total return > {0:+.4%}".format(
        bm["total_return"] + PENALTY))
    print("SPY price-only over the identical window: {0:+.4%}\n".format(
        spy_total))

    # ---- economic table --------------------------------------------------
    print("=" * 78)
    print("1. ECONOMIC PERFORMANCE")
    print("=" * 78)
    labels = ["BASELINE"] + [lab for lab, _r in ORDER]
    rows = [("total return", "total_return", "{0:+.2%}"),
            ("CAGR", "cagr", "{0:+.2%}"),
            ("annualised volatility", "annualised_volatility", "{0:.2%}"),
            ("Sharpe", "sharpe", "{0:.4f}"),
            ("Sortino", "sortino", "{0:.4f}"),
            ("max drawdown", "max_drawdown", "{0:.4%}"),
            ("Calmar", "calmar", "{0:.4f}"),
            ("trades", "trades", "{0}"),
            ("win rate", "win_rate", "{0:.2%}"),
            ("average winner", "average_winner", "${0:,.0f}"),
            ("average loser", "average_loser", "${0:,.0f}"),
            ("profit factor", "profit_factor", "{0:.3f}"),
            ("turnover", "turnover", "{0:.2f}"),
            ("transaction costs", "transaction_costs", "${0:,.0f}"),
            ("exposure", "exposure", "{0:.2%}"),
            ("stop rate", "stop_rate", "{0:.2%}")]
    print("  {0:<24} {1:>12} {2:>12} {3:>12} {4:>12}".format("", *labels))
    for lab, key, fmt in rows:
        cells = []
        for L in labels:
            v = store[L]["metrics"].get(key)
            cells.append(fmt.format(v) if v is not None else "-")
        print("  {0:<24} {1:>12} {2:>12} {3:>12} {4:>12}".format(lab, *cells))
    print("  {0:<24} {1:>12} {2:>12} {3:>12} {4:>12}".format(
        "excess vs SPY (pts)",
        *["{0:+.2f}".format(100 * (store[L]["metrics"]["total_return"]
                                   - spy_total)) for L in labels]))
    print("  {0:<24} {1:>12} {2:>12} {3:>12} {4:>12}".format(
        "delta vs baseline (pts)", "-",
        *["{0:+.2f}".format(100 * (store[L]["metrics"]["total_return"]
                                   - bm["total_return"]))
          for L, _r in [(x, y) for x, y in ORDER]]))

    print("\n  year by year")
    years = sorted(bm["by_year"])
    print("  {0:>6} {1:>12} {2:>12} {3:>12} {4:>12}".format("year", *labels))
    for y in years:
        print("  {0:>6} {1:>12.2%} {2:>12.2%} {3:>12.2%} {4:>12.2%}".format(
            y, *[store[L]["metrics"]["by_year"].get(y, 0.0) for L in labels]))

    # ---- displacement ----------------------------------------------------
    print("\n" + "=" * 78)
    print("2. SLOT COMPETITION AND DISPLACEMENT  (clause D, the central one)")
    print("=" * 78)
    b_by_day = defaultdict(dict)
    for t in base["trades"]:
        b_by_day[date.fromisoformat(t["entry"])][t["symbol"]] = t
    b_days = set(b_by_day)

    def band(sym, day):
        """RSI band of an entry, recomputed point-in-time is unnecessary:
        the configuration admitted it, so <=35 means the baseline could
        have too. Membership is decided by whether the BASELINE's own
        candidate set contained it."""
        return "<=35" if sym in base_cands.get(day, set()) else "35-38"

    base_cands = defaultdict(set)
    for line in (REPO / "data" / "phase5" / "candidates-deep.jsonl"
                 ).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            base_cands[date.fromisoformat(r["date"])].add(r["symbol"])

    disp = {}
    for lab, _rsi in ORDER:
        cfg = store[lab]
        c_by_day = defaultdict(dict)
        for t in cfg["trades"]:
            c_by_day[date.fromisoformat(t["entry"])][t["symbol"]] = t
        kept = empty = extra = 0
        kept_pnl = empty_pnl = extra_pnl = 0.0
        swaps = []
        for day, taken in sorted(c_by_day.items()):
            bl = b_by_day.get(day, {})
            lost = [s for s in bl if s not in taken]
            gained = [s for s in taken if s not in bl]
            for s in taken:
                if s in bl:
                    kept += 1
                    kept_pnl += taken[s]["net_pnl"]
            for i, s in enumerate(gained):
                if not bl:
                    empty += 1
                    empty_pnl += taken[s]["net_pnl"]
                elif i < len(lost):
                    swaps.append({"day": day.isoformat(), "took": s,
                                  "took_pnl": taken[s]["net_pnl"],
                                  "took_band": band(s, day),
                                  "lost": lost[i],
                                  "lost_pnl": bl[lost[i]]["net_pnl"]})
                else:
                    extra += 1
                    extra_pnl += taken[s]["net_pnl"]
        swap_gain = sum(s["took_pnl"] - s["lost_pnl"] for s in swaps)
        new_band = sum(1 for t in cfg["trades"]
                       if t["symbol"] not in base_cands.get(
                           date.fromisoformat(t["entry"]), set()))
        disp[lab] = {
            "kept": kept, "kept_pnl": kept_pnl,
            "empty": empty, "empty_pnl": empty_pnl,
            "extra": extra, "extra_pnl": extra_pnl,
            "swaps": len(swaps), "swap_gain": swap_gain,
            "newly_admitted_35_38": new_band,
            "total_trades": len(cfg["trades"]),
        }
        print("\n  {0}  ({1} trades, baseline {2})".format(
            lab, len(cfg["trades"]), bm["trades"]))
        print("    entries newly eligible (RSI 35-38)   {0}".format(new_band))
        print("    {0:<34} {1:>6} {2:>14}".format("class", "n", "net P&L"))
        print("    {0:<34} {1:>6} {2:>14,.0f}".format(
            "KEPT   (baseline took it too)", kept, kept_pnl))
        print("    {0:<34} {1:>6} {2:>14,.0f}".format(
            "EMPTY  (baseline traded nothing)", empty, empty_pnl))
        print("    {0:<34} {1:>6} {2:>14,.0f}".format(
            "EXTRA  (added alongside)", extra, extra_pnl))
        print("    {0:<34} {1:>6} {2:>14,.0f}".format(
            "SWAPS  (took X, baseline took Y)", len(swaps), swap_gain))
        if swaps:
            won = sum(1 for s in swaps if s["took_pnl"] > s["lost_pnl"])
            print("      swap won {0} of {1} ({2:.1%}); took "
                  "{3:,.0f} vs lost {4:,.0f}".format(
                      won, len(swaps), won / len(swaps),
                      sum(s["took_pnl"] for s in swaps),
                      sum(s["lost_pnl"] for s in swaps)))
            worst = sorted(swaps, key=lambda s: s["took_pnl"] - s["lost_pnl"])
            print("      worst swap: {0} took {1} ({2:+,.0f}) instead of "
                  "{3} ({4:+,.0f})".format(
                      worst[0]["day"], worst[0]["took"], worst[0]["took_pnl"],
                      worst[0]["lost"], worst[0]["lost_pnl"]))
        total_delta = (store[lab]["metrics"]["total_return"]
                       - bm["total_return"])
        print("    total return delta {0:+.2f} points".format(
            100 * total_delta))

    # ---- candidate quality by band --------------------------------------
    print("\n" + "=" * 78)
    print("3. CANDIDATE QUALITY - realised outcomes by band")
    print("=" * 78)
    print("  {0:<12} {1:<10} {2:>6} {3:>10} {4:>9} {5:>8} {6:>8} {7:>9} "
          "{8:>9}".format("config", "band", "n", "mean $", "med R", "win",
                          "stop%", "mean MFE", "mean MAE"))
    quality = {}
    for lab, _rsi in ORDER:
        quality[lab] = {}
        for bname in ("<=35", "35-38"):
            g = [t for t in store[lab]["trades"]
                 if band(t["symbol"], date.fromisoformat(t["entry"])) == bname]
            if not g:
                continue
            mfe = [t["highest_high"] / t["entry_price"] - 1.0
                   for t in g if t["highest_high"]]
            mae = [t["lowest_low"] / t["entry_price"] - 1.0
                   for t in g if t["lowest_low"]]
            quality[lab][bname] = {
                "n": len(g), "mean_pnl": fmean([t["net_pnl"] for t in g]),
                "median_r": median([t["r"] for t in g]),
                "win": sum(1 for t in g if t["net_pnl"] > 0) / len(g),
                "stop": sum(1 for t in g if t["reason"] == "stop") / len(g),
                "mfe": fmean(mfe) if mfe else None,
                "mae": fmean(mae) if mae else None}
            q = quality[lab][bname]
            print("  {0:<12} {1:<10} {2:>6} {3:>10,.0f} {4:>9.3f} {5:>8.1%} "
                  "{6:>8.1%} {7:>9.2%} {8:>9.2%}".format(
                      lab, bname, q["n"], q["mean_pnl"], q["median_r"],
                      q["win"], q["stop"], q["mfe"] or 0.0, q["mae"] or 0.0))

    # ---- adjudication ----------------------------------------------------
    print("\n" + "=" * 78)
    print("4. ADJUDICATION against the sealed clauses")
    print("=" * 78)
    deltas = [store[lab]["metrics"]["total_return"] - bm["total_return"]
              for lab, _r in ORDER]
    positive = sorted([d for d in deltas if d > 0], reverse=True)
    if len(positive) >= 2:
        clause_c = positive[0] <= DOMINANCE * positive[1]
        c_note = "largest {0:+.2f} vs second {1:+.2f} pts".format(
            100 * positive[0], 100 * positive[1])
    elif len(positive) == 1:
        clause_c = False
        c_note = "only ONE positive delta - a spike by definition"
    else:
        clause_c = False
        c_note = "no positive delta at all"
    rho = spearman([r for _l, r in ORDER], deltas)

    print("  {0:<12} {1:>10} {2:>12} {3:>8} {4:>8} {5:>8} {6:>8}".format(
        "config", "delta pts", "maxDD", "A", "B", "D", "verdict"))
    results = []
    for (lab, rsi), d in zip(ORDER, deltas):
        m = store[lab]["metrics"]
        a = d > PENALTY
        bb = abs(m["max_drawdown"]) <= ceiling
        dd = disp[lab]
        d_ok = dd["empty_pnl"] > 0 and dd["swap_gain"] >= 0
        ok = a and bb and clause_c and d_ok
        results.append({"label": lab, "rsi": rsi, "delta": d,
                        "max_drawdown": m["max_drawdown"],
                        "A": a, "B": bb, "C": clause_c, "D": d_ok,
                        "passes_abcd": ok})
        print("  {0:<12} {1:>+10.2f} {2:>12.4%} {3:>8} {4:>8} {5:>8} "
              "{6:>8}".format(lab, 100 * d, m["max_drawdown"],
                              "pass" if a else "FAIL",
                              "pass" if bb else "FAIL",
                              "pass" if d_ok else "FAIL",
                              "pass" if ok else "FAIL"))
    print("\n  CLAUSE C (gradient, not spike): {0}  [{1}]".format(
        "PASS" if clause_c else "FAIL", c_note))
    print("    Spearman(threshold, delta) = {0:+.4f}".format(rho))

    survivors = [r for r in results if r["passes_abcd"]]
    print("\n  passing A, B, C and D: {0}".format(
        ", ".join(r["label"] for r in survivors) or "NONE"))

    clause_e = None
    if survivors:
        print("\n  CLAUSE E - leave out the single best calendar year")
        for r in survivors:
            by = store[r["label"]]["metrics"]["by_year"]
            best = max(by, key=lambda y: by[y])
            kept = sum(1 for y in by if y != best)
            rebuilt = 1.0
            for y in sorted(by):
                if y != best:
                    rebuilt *= (1 + by[y])
            bb = 1.0
            for y in sorted(bm["by_year"]):
                if y != best:
                    bb *= (1 + bm["by_year"][y])
            ok = rebuilt > bb
            print("    {0}: best year {1}, without it {2:+.2%} vs baseline "
                  "{3:+.2%} -> {4}".format(r["label"], best, rebuilt - 1,
                                           bb - 1, "pass" if ok else "FAIL"))
            r["E"] = ok
        clause_e = all(r.get("E") for r in survivors)
        survivors = [r for r in survivors if r.get("E")]

    verdict = "ACCEPTED" if survivors else "REJECTED"
    print("\n  VERDICT: H-0009 {0}".format(verdict))
    if not survivors:
        print("  The frozen rsi_entry = 35.0 STANDS, UNCHANGED.")

    out = REPO / "docs" / "phase5" / "h0009-adjudication.json"
    out.write_text(json.dumps({
        "FORENSIC_NON_PROMOTIONAL": True,
        "seal": seal["seal"], "verdict": verdict,
        "baseline": bm, "spy_total": spy_total, "ceiling": ceiling,
        "penalty": PENALTY,
        "configurations": {lab: store[lab]["metrics"] for lab, _r in ORDER},
        "deltas_points": [100 * d for d in deltas],
        "clause_c": clause_c, "clause_c_note": c_note, "spearman": rho,
        "clause_e": clause_e,
        "displacement": disp, "quality": quality,
        "per_configuration": results,
        "thirty_year_reads": 13,
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
