"""Run H-0007. Equivalence first, then the three sealed cutoffs.

The abstention is applied through `model_veto`, which can only remove a
candidate. Open positions, sizing, stops, exits and the holding cap are
untouched by construction.

THE LEAKAGE GUARD, stated where it is implemented. For session t the
allow/deny decision is looked up by t's date but was COMPUTED from SPY
closes through t-1. `allowance()` builds that map once and shifts it
forward by one session deliberately; a version keyed on t's own close
would decide today's entry using today's price.

  python scripts/run_h0007.py --check-only
  python scripts/run_h0007.py
  python scripts/run_h0007.py --thirty-year CUTOFF   # clause D, conditional
"""

import glob
import json
import sys
from datetime import date
from pathlib import Path
from statistics import pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.data import load_bars                  # noqa: E402
from event_aware_trader.mean_reversion import conviction as shipped_conviction  # noqa: E402
from event_aware_trader.modelgov import prereg                 # noqa: E402
from event_aware_trader.phase5.metrics import measure          # noqa: E402
from event_aware_trader.research import production_report      # noqa: E402
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto  # noqa: E402

SCRATCH = Path(glob.glob(
    "C:/Users/yajga/AppData/Local/Temp/claude/**/scratchpad/deep",
    recursive=True)[0]).parent
WINDOW = 400
_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-WINDOW:], c)
_conv = {}

CUTOFFS = [("A tercile", 1.0 / 3.0), ("B quartile", 0.25), ("C quintile", 0.20)]
VOL_DAYS = 20
MIN_READINGS = 252


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def load(folder="deep", since=None, minimum=500):
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        path = SCRATCH / folder / (symbol + ".csv")
        if not path.exists():
            continue
        try:
            bars = load_bars(path)
        except Exception:
            continue
        if since:
            bars = [b for b in bars if b.timestamp.date() >= since]
        if len(bars) >= minimum:
            out[symbol] = bars
    return out


def allowance(spy, cutoff):
    """date -> may new entries be opened, from closes through the PRIOR day.

    Returns (allow_map, ranks_by_date, sessions_denied).
    """
    closes, vols, seen = [], [], []
    rank_at = {}
    for bar in spy:
        closes.append(bar.close)
        if len(closes) >= VOL_DAYS + 1:
            rets = [closes[j] / closes[j - 1] - 1.0
                    for j in range(len(closes) - VOL_DAYS, len(closes))
                    if closes[j - 1]]
            if len(rets) > 1:
                vol = pstdev(rets)
                seen.append(vol)
                rank = (sum(1 for v in seen if v <= vol) / len(seen)
                        if len(seen) >= MIN_READINGS else None)
                rank_at[bar.timestamp.date()] = rank
    days = [b.timestamp.date() for b in spy]
    allow, denied = {}, 0
    for i, day in enumerate(days):
        if i == 0:
            allow[day] = True
            continue
        rank = rank_at.get(days[i - 1])          # STRICTLY the prior close
        if rank is None:
            allow[day] = True                    # percentile not yet trusted
        else:
            allow[day] = rank >= cutoff
            if not allow[day]:
                denied += 1
    return allow, rank_at, denied


def veto_for(allow):
    def veto(symbol, history):
        return not allow.get(history[-1].timestamp.date(), True)
    return veto


def attribute(report, series, spy_close):
    """market / selection / timing dollars, and the trade key set."""
    closes = {s: {b.timestamp.date(): b.close for b in bars}
              for s, bars in series.items()}
    rows, keys = [], {}
    for t in report.trades:
        d0, d1 = t.entry_time.date(), t.exit_time.date()
        c = closes.get(t.symbol, {})
        if d0 not in c or d1 not in c or d0 not in spy_close or d1 not in spy_close:
            continue
        notional = abs(t.quantity) * t.entry_price
        r_sym = c[d1] / c[d0] - 1.0
        r_spy = spy_close[d1] / spy_close[d0] - 1.0
        row = {"key": (t.symbol, d0), "notional": notional, "pnl": t.net_pnl,
               "market": notional * r_spy,
               "selection": notional * (r_sym - r_spy),
               "timing": t.net_pnl - notional * r_sym,
               "reason": t.exit_reason}
        rows.append(row)
        keys[row["key"]] = row
    return rows, keys


def totals(rows):
    n = sum(r["notional"] for r in rows) or 1.0
    return {"market": sum(r["market"] for r in rows),
            "selection": sum(r["selection"] for r in rows),
            "timing": sum(r["timing"] for r in rows),
            "notional": n,
            "market_per": sum(r["market"] for r in rows) / n,
            "selection_per": sum(r["selection"] for r in rows) / n,
            "timing_per": sum(r["timing"] for r in rows) / n}


def main():
    check_only = "--check-only" in sys.argv
    thirty = "--thirty-year" in sys.argv
    sealed = [p for p in prereg.load() if p["hypothesis_id"] == "H-0007"]
    if not sealed:
        print("REFUSED: H-0007 is not registered.")
        return 2
    seal = sealed[0]
    if not prereg.verify_chain()["intact"]:
        print("REFUSED: registration chain broken.")
        return 2
    registered = seal["parameters"]["cutoffs"]
    if sorted(round(v, 6) for v in registered.values()) != \
            sorted(round(c, 6) for _n, c in CUTOFFS):
        print("REFUSED: this runner's cutoffs are not the sealed cutoffs.")
        return 2
    print("H-0007 seal {0} | commit {1}".format(seal["seal"][:16],
                                                seal["code_commit"][:12]))
    print("sealed cutoffs: {0}".format(registered))

    folder, since, minimum, dataset = (
        ("long", date(1996, 1, 1), 400, "thirty_year") if thirty
        else ("deep", None, 500, "decade"))
    series = load(folder, since, minimum)
    spy = series["SPY"]
    spy_close = {b.timestamp.date(): b.close for b in spy}
    print("\n{0}: {1} symbols, SPY {2} -> {3}".format(
        dataset, len(series), spy[0].timestamp.date(), spy[-1].timestamp.date()),
        flush=True)

    base_report = production_report(series, conviction=conviction,
                                    dataset=dataset, purpose="rejection_test")
    baseline = measure(base_report, "BASELINE").as_dict()
    spy_total = spy[-1].close / spy[0].close - 1.0
    base_rows, base_keys = attribute(base_report, series, spy_close)
    base_attr = totals(base_rows)
    print("baseline: {0} trades, total {1:+.4%}, Sharpe {2:.4f}, "
          "maxDD {3:.4%}".format(baseline["trades"], baseline["total_return"],
                                 baseline["sharpe"], baseline["max_drawdown"]))
    print("SPY price-only over the identical window: {0:+.4%}".format(spy_total))

    # ---- equivalence: an all-allow veto must reproduce the baseline -----
    print("\nEQUIVALENCE: a veto that never fires must reproduce the baseline")
    same = measure(production_report(series, conviction=conviction,
                                     dataset=dataset, purpose="rejection_test",
                                     model_veto=lambda s, h: False),
                   "equivalence").as_dict()
    drift = abs(same["total_return"] - baseline["total_return"])
    print("  baseline {0:+.10%} | never-veto {1:+.10%} | drift {2:.12f}".format(
        baseline["total_return"], same["total_return"], drift))
    if drift > 1e-12 or same["trades"] != baseline["trades"]:
        print("STOPPED: the execution path is not equivalent. Nothing else run.")
        return 2
    print("  IDENTICAL - proceeding")
    if check_only:
        return 0

    # ---- the three sealed cutoffs ---------------------------------------
    print("\nSEALED CONFIGURATIONS")
    rows = []
    for name, cutoff in CUTOFFS:
        allow, _ranks, denied = allowance(spy, cutoff)
        report = production_report(series, conviction=conviction,
                                   dataset=dataset, purpose="rejection_test",
                                   model_veto=veto_for(allow))
        scored = measure(report, name).as_dict()
        attr_rows, keys = attribute(report, series, spy_close)
        attr = totals(attr_rows)
        removed = [r for k, r in base_keys.items() if k not in keys]
        added = [r for k, r in keys.items() if k not in base_keys]
        scored.update({
            "cutoff": cutoff, "sessions_denied": denied,
            "vs_spy_points": 100.0 * (scored["total_return"] - spy_total),
            "attr": attr,
            "removed_n": len(removed), "added_n": len(added),
            "removed_winners": sum(1 for r in removed if r["pnl"] > 0),
            "removed_losers": sum(1 for r in removed if r["pnl"] <= 0),
            "removed_winner_pnl": sum(r["pnl"] for r in removed if r["pnl"] > 0),
            "removed_loser_pnl": sum(r["pnl"] for r in removed if r["pnl"] <= 0),
            "added_pnl": sum(r["pnl"] for r in added),
        })
        rows.append(scored)
        print("  {0:<12} cut {1:.4f}  denied {2:>4}  trades {3:>4}  "
              "total {4:+8.2%}  Sharpe {5:6.3f}  maxDD {6:7.2%}  vol {7:5.1%}"
              .format(name, cutoff, denied, scored["trades"],
                      scored["total_return"], scored["sharpe"],
                      scored["max_drawdown"], scored["annualised_volatility"]),
              flush=True)

    out_name = ("h0007-thirtyyear.json" if thirty else "h0007-results.json")
    out = REPO / "docs" / "phase5" / out_name
    out.write_text(json.dumps({
        "seal": seal["seal"], "dataset": dataset, "baseline": baseline,
        "baseline_attr": base_attr, "spy_total": spy_total,
        "configurations": rows,
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
