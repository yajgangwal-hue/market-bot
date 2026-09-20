"""Run and adjudicate H-0012. Yardstick audit, not a strategy.

Equivalence first, then the single sealed repricing, then the
historical impact audit. No decision rule is touched, no production
file is modified, and nothing is rerun under a new execution model -
prior experiments are repriced analytically from their own stored
trade logs exactly as the baseline is.
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
from event_aware_trader.research import production_report       # noqa: E402
from forensics_regime import load                                # noqa: E402

_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-400:], c)
_conv = {}

FINGERPRINT = ("da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537"
               "c237b")
H = 0.00652
PENALTY = 0.02
START = 100_000.0
# Sealed multipliers. Do not recompute from anything but the seal.
MULT = {"reverted": 1.00044706, "time_exit": 1.00768031}
OUT = REPO / "docs" / "phase5" / "h0012-adjudication.json"


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def reprice(trades):
    """Apply the sealed per-reason multiplier. Path held fixed."""
    out = []
    for t in trades:
        m = MULT.get(t["reason"], 1.0)
        xp = t["exit_price"] * m
        out.append(dict(t, exit_price=xp,
                        net_pnl=(xp - t["entry_price"]) * t["qty"],
                        repriced_by=m))
    return out


def summarise(trades, label):
    pnl = [t["net_pnl"] for t in trades]
    wins = [p for p in pnl if p > 0]
    loss = [p for p in pnl if p <= 0]
    eq = START
    peak = START
    dd = 0.0
    for t in sorted(trades, key=lambda x: x["exit"]):
        eq += t["net_pnl"]
        peak = max(peak, eq)
        dd = min(dd, eq / peak - 1.0)
    return {"label": label, "trades": len(trades), "total_pnl": sum(pnl),
            "terminal": eq, "return_on_start": eq / START - 1.0,
            "win_rate": len(wins) / len(pnl) if pnl else 0.0,
            "profit_factor": (sum(wins) / abs(sum(loss))) if loss else None,
            "expectancy": fmean(pnl) if pnl else 0.0,
            "trade_max_drawdown": dd}


def main():
    sealed = [p for p in prereg.load() if p["hypothesis_id"] == "H-0012"]
    if not sealed:
        print("REFUSED: H-0012 is not registered.")
        return 2
    seal = sealed[0]
    if not prereg.verify_chain()["intact"]:
        print("REFUSED: chain broken.")
        return 2
    if (abs(seal["parameters"]["multiplier_reverted"] - MULT["reverted"]) > 1e-9
            or abs(seal["parameters"]["multiplier_time_exit"]
                   - MULT["time_exit"]) > 1e-9):
        print("REFUSED: runner multipliers are not the sealed multipliers.")
        return 2
    if frozen_fingerprint() != FINGERPRINT:
        print("REFUSED: fingerprint moved.")
        return 2
    print("H-0012 seal {0} | commit {1}".format(seal["seal"][:16],
                                                seal["code_commit"][:12]))
    print("sealed multipliers: reverted {0:.8f} | time_exit {1:.8f}".format(
        MULT["reverted"], MULT["time_exit"]))
    print("fingerprint OK | chain intact\n", flush=True)

    # ---- 1. equivalence -------------------------------------------------
    print("EQUIVALENCE: reproducing the frozen baseline before repricing",
          flush=True)
    series = load()
    rep = production_report(series, conviction=conviction, dataset="decade",
                            purpose="rejection_test",
                            mr_config=MeanReversionConfig())
    tot = rep.metrics.total_return if hasattr(rep, "metrics") else None
    from event_aware_trader.phase5.metrics import measure
    m0 = measure(rep, "BASELINE").as_dict()
    print("  {0:+.10%} over {1} trades | registered +58.5889000000% / 698"
          .format(m0["total_return"], m0["trades"]))
    if abs(m0["total_return"] - 0.585889) > 5e-7 or m0["trades"] != 698:
        print("STOPPED: baseline did not reproduce. Nothing repriced.")
        return 2
    print("  IDENTICAL - proceeding\n", flush=True)

    store = json.loads((REPO / "docs" / "phase5" / "h0011-cache.json")
                       .read_text(encoding="utf-8"))
    base = store["BASELINE"]["trades"]
    base_s = summarise(base, "BASELINE original")
    new = reprice(base)
    new_s = summarise(new, "BASELINE repriced")

    # ---- 2. decomposition ----------------------------------------------
    print("=" * 78)
    print("REPRICED BASELINE")
    print("=" * 78)
    print("  {0:<26} {1:>16} {2:>16} {3:>14}".format(
        "", "original", "repriced", "delta"))
    rows = [("realised P&L ($)", "total_pnl", "{0:,.0f}"),
            ("return on start", "return_on_start", "{0:+.4%}"),
            ("trades", "trades", "{0}"),
            ("win rate", "win_rate", "{0:.2%}"),
            ("profit factor", "profit_factor", "{0:.3f}"),
            ("expectancy ($/trade)", "expectancy", "{0:,.2f}"),
            ("trade-level max DD", "trade_max_drawdown", "{0:.4%}")]
    for name, k, fmt in rows:
        a, b = base_s[k], new_s[k]
        dlt = (b - a) if isinstance(a, (int, float)) and isinstance(
            b, (int, float)) else None
        print("  {0:<26} {1:>16} {2:>16} {3:>14}".format(
            name, fmt.format(a), fmt.format(b),
            fmt.format(dlt) if dlt is not None else "-"))
    print("\n  NOTE: trade count, entries, quantities and exposure are")
    print("  IDENTICAL by construction - the path is held fixed, as sealed.")
    print("  Sharpe and daily max drawdown are NOT recomputed: they need a")
    print("  daily mark-to-market curve that a path-fixed reprice cannot")
    print("  produce honestly. The trade-level drawdown above is reported")
    print("  instead and is NOT comparable to the -12.9824% daily figure.")

    per = {}
    for reason in ("reverted", "time_exit", "stop"):
        o = [t for t in base if t["reason"] == reason]
        n = [t for t in new if t["reason"] == reason]
        per[reason] = {"n": len(o),
                       "original_pnl": sum(t["net_pnl"] for t in o),
                       "repriced_pnl": sum(t["net_pnl"] for t in n),
                       "delta": sum(t["net_pnl"] for t in n)
                       - sum(t["net_pnl"] for t in o)}
    print("\n" + "=" * 78)
    print("DECOMPOSITION BY EXIT CATEGORY")
    print("=" * 78)
    print("  {0:<12} {1:>5} {2:>16} {3:>16} {4:>14} {5:>9}".format(
        "reason", "n", "original P&L", "repriced P&L", "delta", "share"))
    tot_d = sum(v["delta"] for v in per.values())
    for r, v in per.items():
        print("  {0:<12} {1:>5} {2:>16,.0f} {3:>16,.0f} {4:>+14,.0f} "
              "{5:>9}".format(r, v["n"], v["original_pnl"], v["repriced_pnl"],
                              v["delta"],
                              "{0:.1%}".format(v["delta"] / tot_d)
                              if tot_d else "-"))
    print("  {0:<12} {1:>5} {2:>16} {3:>16} {4:>+14,.0f}".format(
        "TOTAL", len(base), "", "", tot_d))
    lvl = new_s["return_on_start"] - base_s["return_on_start"]
    print("\n  level change {0:+.4f} points against the {1:.0f}-point "
          "penalty".format(100 * lvl, 100 * PENALTY))

    # ---- 3. historical impact audit -------------------------------------
    print("\n" + "=" * 78)
    print("HISTORICAL IMPACT AUDIT")
    print("=" * 78)
    impact = {}
    caches = {"H-0009": "h0009-cache.json", "H-0010": "h0010-cache.json",
              "H-0011": "h0011-cache.json"}
    for hid, fn in caches.items():
        p = REPO / "docs" / "phase5" / fn
        if not p.exists():
            continue
        st_ = json.loads(p.read_text(encoding="utf-8"))
        b_o = summarise(st_["BASELINE"]["trades"], "base")
        b_n = summarise(reprice(st_["BASELINE"]["trades"]), "base'")
        rowsx = []
        for lab in [k for k in st_ if k != "BASELINE"]:
            t_o = summarise(st_[lab]["trades"], lab)
            t_n = summarise(reprice(st_[lab]["trades"]), lab)
            rowsx.append({
                "config": lab,
                "orig_return": t_o["return_on_start"],
                "orig_delta": t_o["return_on_start"] - b_o["return_on_start"],
                "repr_return": t_n["return_on_start"],
                "repr_delta": t_n["return_on_start"] - b_n["return_on_start"]})
        impact[hid] = {"baseline_orig": b_o["return_on_start"],
                       "baseline_repr": b_n["return_on_start"],
                       "configs": rowsx}
        print("\n  {0}   baseline {1:+.4%} -> {2:+.4%}".format(
            hid, b_o["return_on_start"], b_n["return_on_start"]))
        print("    {0:<16} {1:>12} {2:>12} {3:>12} {4:>12} {5:>10}".format(
            "config", "orig delta", "repr delta", "change", "orig ret",
            "repr ret"))
        order_o = [r["config"] for r in sorted(rowsx,
                                               key=lambda x: -x["orig_delta"])]
        order_n = [r["config"] for r in sorted(rowsx,
                                               key=lambda x: -x["repr_delta"])]
        for r in rowsx:
            print("    {0:<16} {1:>+12.2f} {2:>+12.2f} {3:>+12.2f} "
                  "{4:>12.2%} {5:>10.2%}".format(
                      r["config"], 100 * r["orig_delta"],
                      100 * r["repr_delta"],
                      100 * (r["repr_delta"] - r["orig_delta"]),
                      r["orig_return"], r["repr_return"]))
        impact[hid]["ordering_original"] = order_o
        impact[hid]["ordering_repriced"] = order_n
        impact[hid]["ordering_changed"] = order_o != order_n
        print("    ordering original : {0}".format(" > ".join(order_o)))
        print("    ordering repriced : {0}".format(" > ".join(order_n)))
        print("    ORDERING CHANGED  : {0}".format(order_o != order_n))

    res = {"FORENSIC_NON_PROMOTIONAL": True, "seal": seal["seal"],
           "commit": seal["code_commit"], "multipliers": MULT,
           "baseline_original": base_s, "baseline_repriced": new_s,
           "level_change_points": 100 * lvl, "per_reason": per,
           "impact": impact, "penalty_points": 100 * PENALTY,
           "thirty_year_reads": 13}
    OUT.write_text(json.dumps(res, indent=1, sort_keys=True, default=str),
                   encoding="utf-8")
    print("\nwrote {0}".format(OUT.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
