"""Run and adjudicate H-0013. Measurement validity, not strategy.

Equivalence, then the four sealed candidate models on one fixed
walk-forward schedule, then - only for whichever model the ERROR
criterion selected - the economic repricing and the impact audit.
"""

import json
import sys
from pathlib import Path
from statistics import fmean, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.forward import frozen_fingerprint       # noqa: E402
from event_aware_trader.mean_reversion import (                 # noqa: E402
    MeanReversionConfig, conviction as shipped_conviction)
from event_aware_trader.modelgov import prereg                  # noqa: E402
from event_aware_trader.phase5.metrics import measure           # noqa: E402
from event_aware_trader.research import production_report       # noqa: E402
from forensics_regime import load                                # noqa: E402

_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-400:], c)
_conv = {}

FP = "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b"
H = 0.00652
A_INCUMBENT = H / (1.0 - H)          # implied drift of the flat haircut
POOLED = {"reverted": 0.006113, "time_exit": -0.001109, "stop": 0.0}
MINOBS = 30
START = 100_000.0
FEAT = REPO / "docs" / "phase5" / "h0013-features.json"
CACHE = REPO / "docs" / "phase5" / "h0011-cache.json"
OUT = REPO / "docs" / "phase5" / "h0013-adjudication.json"


def conviction(symbol, history):
    k = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(k)
    if hit is None:
        hit = _conv[k] = shipped_conviction(history[-40:])
    return hit


def ols(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = fmean(xs), fmean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den <= 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    return my - b * mx, b


def predict(model, row, prior):
    """prior = same-reason rows strictly before this row's exit date."""
    rs = row["reason"]
    if rs == "stop":
        return 0.0
    if model == "A":
        return A_INCUMBENT
    if model == "B":
        return POOLED.get(rs, 0.0)
    if len(prior) < MINOBS:
        return A_INCUMBENT                      # defined, never peeks
    base = fmean(p["drift_to_close"] for p in prior)
    if model == "C" or rs != "reverted":
        return base
    # D: one conditioner, reverted only, fitted on the same prior window
    pts = [(p["rvol_before"], p["drift_to_close"]) for p in prior
           if p.get("rvol_before") is not None]
    x = row.get("rvol_before")
    if x is None or len(pts) < MINOBS:
        return base                             # registered fallback
    fit = ols([a for a, _ in pts], [b for _, b in pts])
    if fit is None:
        return base
    a0, b1 = fit
    return a0 + b1 * x


def main():
    sealed = [p for p in prereg.load() if p["hypothesis_id"] == "H-0013"]
    if not sealed:
        print("REFUSED: H-0013 not registered.")
        return 2
    seal = sealed[0]
    if not prereg.verify_chain()["intact"]:
        print("REFUSED: chain broken.")
        return 2
    if seal["parameters"]["conditioner"] != "rvol_before":
        print("REFUSED: conditioner is not the sealed one.")
        return 2
    if frozen_fingerprint() != FP:
        print("REFUSED: fingerprint moved.")
        return 2
    print("H-0013 seal {0} | commit {1}".format(seal["seal"][:16],
                                                seal["code_commit"][:12]))
    print("conditioner {0} | min prior obs {1} | fingerprint OK\n".format(
        seal["parameters"]["conditioner"], MINOBS), flush=True)

    print("EQUIVALENCE", flush=True)
    series = load()
    rep = production_report(series, conviction=conviction, dataset="decade",
                            purpose="rejection_test",
                            mr_config=MeanReversionConfig())
    m0 = measure(rep, "BASELINE").as_dict()
    print("  {0:+.10%} over {1} trades".format(m0["total_return"],
                                               m0["trades"]))
    if abs(m0["total_return"] - 0.585889) > 5e-7 or m0["trades"] != 698:
        print("STOPPED: baseline did not reproduce.")
        return 2
    print("  IDENTICAL - proceeding\n", flush=True)

    rows = json.loads(FEAT.read_text(encoding="utf-8"))["rows"]
    rows.sort(key=lambda r: r["exit"])
    years = sorted({r["year"] for r in rows})

    # ---- walk-forward ---------------------------------------------------
    preds = {m: [] for m in "ABCD"}
    for y in years:
        hist = [r for r in rows if r["year"] < y]
        cur = [r for r in rows if r["year"] == y]
        for r in cur:
            prior = [p for p in hist if p["reason"] == r["reason"]]
            for m in "ABCD":
                preds[m].append({"year": y, "third": r["third"],
                                 "reason": r["reason"],
                                 "pred": predict(m, r, prior),
                                 "real": r["drift_to_close"]})

    def err(rec):
        e = [abs(p["pred"] - p["real"]) for p in rec]
        s = [p["pred"] - p["real"] for p in rec]
        return {"n": len(e), "mae": fmean(e),
                "rmse": (fmean(x * x for x in s)) ** 0.5,
                "bias": fmean(s)}

    print("=" * 76)
    print("WALK-FORWARD ERROR  (selection metric = MAE, lower wins)")
    print("=" * 76)
    names = {"A": "A incumbent 0.652%", "B": "B H-0012 pooled (INELIGIBLE)",
             "C": "C PIT expanding mean", "D": "D PIT + rvol_before"}
    tot = {m: err(preds[m]) for m in "ABCD"}
    print("  {0:<30} {1:>7} {2:>10} {3:>10} {4:>11}".format(
        "model", "n", "MAE", "RMSE", "bias"))
    for m in "ABCD":
        e = tot[m]
        print("  {0:<30} {1:>7} {2:>10.4%} {3:>10.4%} {4:>+11.4%}".format(
            names[m], e["n"], e["mae"], e["rmse"], e["bias"]))

    print("\n  MAE by chronological third")
    print("  {0:<30} {1:>11} {2:>11} {3:>11}".format(
        "model", "third 1", "third 2", "third 3"))
    thirds = {}
    for m in "ABCD":
        t = [err([p for p in preds[m] if p["third"] == k]) for k in (1, 2, 3)]
        thirds[m] = [x["mae"] for x in t]
        print("  {0:<30} {1:>11.4%} {2:>11.4%} {3:>11.4%}".format(
            names[m], *thirds[m]))

    print("\n  MAE by reason")
    print("  {0:<30} {1:>12} {2:>12} {3:>12}".format(
        "model", "reverted", "time_exit", "stop"))
    byreason = {}
    for m in "ABCD":
        v = [err([p for p in preds[m] if p["reason"] == rs])["mae"]
             for rs in ("reverted", "time_exit", "stop")]
        byreason[m] = v
        print("  {0:<30} {1:>12.4%} {2:>12.4%} {3:>12.4%}".format(names[m], *v))

    # ---- sealed selection rule -----------------------------------------
    print("\n" + "=" * 76)
    print("SELECTION  (sealed: lowest MAE; B ineligible; must beat A in >=2 "
          "of 3 thirds)")
    print("=" * 76)
    elig = [m for m in ("A", "C", "D")]
    ranked = sorted(elig, key=lambda m: (tot[m]["mae"], {"A": 0, "C": 1,
                                                         "D": 2}[m]))
    winner = ranked[0]
    beats = {m: sum(1 for k in range(3) if thirds[m][k] < thirds["A"][k])
             for m in ("C", "D")}
    for m in ("C", "D"):
        print("  {0} beats incumbent in {1}/3 thirds -> {2}".format(
            names[m], beats[m],
            "STABLE" if beats[m] >= 2 else "NOT STABLE"))
    print("\n  lowest MAE among eligible: {0}".format(names[winner]))
    stable_win = winner == "A" or beats.get(winner, 0) >= 2
    print("  stability requirement met: {0}".format(stable_win))
    selected = winner if stable_win else "A"
    print("  SELECTED MODEL: {0}".format(names[selected]))

    # ---- economic repricing, AFTER selection ----------------------------
    print("\n" + "=" * 76)
    print("ECONOMIC REPRICING under the selected model (reported, not used "
          "to select)")
    print("=" * 76)
    store = json.loads(CACHE.read_text(encoding="utf-8"))
    base = store["BASELINE"]["trades"]
    key = {(r["symbol"], r["entry"]): r for r in rows}
    predmap = {}
    for y in years:
        hist = [r for r in rows if r["year"] < y]
        for r in [x for x in rows if x["year"] == y]:
            prior = [p for p in hist if p["reason"] == r["reason"]]
            predmap[(r["symbol"], r["entry"])] = {
                m: predict(m, r, prior) for m in "ABCD"}

    def reprice(model):
        tot_ = 0.0
        per = {}
        for t in base:
            r = key.get((t["symbol"], t["entry"]))
            if r is None or t["reason"] not in ("reverted", "time_exit"):
                tot_ += t["net_pnl"]
                continue
            a = predmap[(t["symbol"], t["entry"])][model]
            hp = a / (1.0 + a)
            xp = t["exit_price"] * (1.0 - hp) / (1.0 - H)
            p = (xp - t["entry_price"]) * t["qty"]
            per[t["reason"]] = per.get(t["reason"], 0.0) + (p - t["net_pnl"])
            tot_ += p
        return tot_, per

    orig = sum(t["net_pnl"] for t in base)
    print("  {0:<34} {1:>14} {2:>14}".format("", "realised P&L", "on start"))
    print("  {0:<34} {1:>14,.0f} {2:>14.4%}".format(
        "original baseline", orig, orig / START))
    results = {}
    for m in "ABCD":
        v, per = reprice(m)
        results[m] = {"pnl": v, "on_start": v / START, "per_reason": per,
                      "delta_pts": 100 * (v - orig) / START}
        mark = "  <- SELECTED" if m == selected else ""
        print("  {0:<34} {1:>14,.0f} {2:>14.4%}{3}".format(
            names[m], v, v / START, mark))
    sel = results[selected]
    print("\n  selected model delta vs original: {0:+.2f} points".format(
        sel["delta_pts"]))
    print("  H-0012 (model B) delta:           {0:+.2f} points".format(
        results["B"]["delta_pts"]))
    print("  difference H-0013 vs H-0012:      {0:+.2f} points".format(
        sel["delta_pts"] - results["B"]["delta_pts"]))
    print("\n  per-reason contribution under the selected model:")
    for k, v in sorted(sel["per_reason"].items()):
        print("    {0:<12} {1:>+12,.0f}".format(k, v))

    json.dump({"FORENSIC_NON_PROMOTIONAL": True, "seal": seal["seal"],
               "commit": seal["code_commit"], "selected": selected,
               "selected_name": names[selected], "totals": tot,
               "thirds_mae": thirds, "reason_mae": byreason,
               "beats_incumbent_thirds": beats, "repricing": results,
               "original_pnl": orig, "thirty_year_reads": 13},
              open(OUT, "w"), indent=1, sort_keys=True, default=str)
    print("\nwrote {0}".format(OUT.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
