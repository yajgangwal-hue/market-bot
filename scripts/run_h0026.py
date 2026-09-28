"""Run H-0026. Registration and code first, equivalence second, then the one sealed rule.

Order, and every refusal:
1. The registration chain must be intact, H-0026 must verify against
   h0026_spec.hypothesis() (same seal), the dataset gate must accept it, and
   the H-0026 code files must be unchanged since the registered commit.
2. The frozen baseline must reproduce +58.5889000000% / 698 through the same
   override path, or nothing else runs.
3. Walk-forward calibration: k*(Y) for every year from 2018, from baseline
   paths that ended at least 20 sessions before Y began.
4. The variant: the frozen candidate plus mr_take_profit_atr_by_year and 5 bp
   trade-through. Then the touch-fill bound, which cannot pass or fail
   anything.
5. Every sealed clause computed here, nothing chosen. Outcome A, B, C or
   STOPPED, exactly as registered.

Each emulator run is cached the moment it finishes, keyed by the seal.
"""

import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader import portfolio as portfolio_module          # noqa: E402
from event_aware_trader.exit_placement import (                       # noqa: E402
    ar1_profit_paths, evaluate_rules)
from event_aware_trader.mean_reversion import (                       # noqa: E402
    MeanReversionConfig, conviction as shipped_conviction)
from event_aware_trader.modelgov import prereg                        # noqa: E402
from event_aware_trader.phase5.metrics import measure                 # noqa: E402
from event_aware_trader.research import deflated_sharpe, production_report  # noqa: E402

import h0026_spec as spec                                              # noqa: E402
import research_gate                                                   # noqa: E402
from forensics_regime import load                                      # noqa: E402

# The same speed patch H-0010 used; the baseline equivalence below is what
# licenses it - if truncating the signal history changed anything, the
# baseline would not reproduce and nothing would run.
_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-400:], c)
_conv = {}

CACHE = REPO / "docs" / "phase5" / "h0026-cache.json"
RESULTS = REPO / "docs" / "phase5" / "h0026-results.json"
CODE_FILES = spec.CODE_FILES


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def refuse(message):
    print("REFUSED: " + message)
    return 2


def code_unchanged_since(commit):
    changed = subprocess.run(["git", "diff", "--name-only", commit, "--"] + CODE_FILES,
                             capture_output=True, text=True, cwd=REPO).stdout.split()
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "--"]
                               + CODE_FILES, capture_output=True, text=True,
                               cwd=REPO).stdout.split()
    return changed + untracked


def pack(report, label, by_year=None):
    reasons = {}
    for t in report.trades:
        reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
    avoided = sum(abs(t.quantity) * t.exit_price * spec.HAIRCUT
                  for t in report.trades if t.exit_reason == "take_profit")
    return {
        "label": label,
        # Round-tripped through JSON so a cached run and a fresh one have the
        # same key types (by_year's years become strings either way).
        "metrics": json.loads(json.dumps(measure(report, label).as_dict(), default=str)),
        "exit_reasons": reasons,
        "take_profit_exits": reasons.get("take_profit", 0),
        "haircut_avoided_dollars": avoided,
        "take_profit_atr_by_year": by_year,
        "trades": [{"symbol": t.symbol, "entry": t.entry_time.isoformat(),
                    "exit": t.exit_time.isoformat(), "qty": t.quantity,
                    "entry_price": t.entry_price, "exit_price": t.exit_price,
                    "initial_stop": t.initial_stop, "net_pnl": t.net_pnl,
                    "reason": t.exit_reason, "bars_held": t.bars_held}
                   for t in report.trades],
        "equity": [[d.isoformat(), v] for d, v in report.equity_curve],
    }


def calibrate(series, trades, year):
    """k*(Y) and the fitted AR(1), exactly as the registration's rule states."""
    spy_dates = [b.timestamp.date() for b in series["SPY"]]
    first = next(i for i, d in enumerate(spy_dates) if d.year == year)
    if first - spec.PURGE_SESSIONS < 0:
        raise ValueError("no purge room before {0}".format(year))
    cutoff = spy_dates[first - spec.PURGE_SESSIONS]
    index = {}
    xs, ys, used, unmatched, short, nonpositive = [], [], 0, 0, 0, 0
    for t in trades:
        bars = series[t["symbol"]]
        if t["symbol"] not in index:
            index[t["symbol"]] = {b.timestamp.isoformat(): i for i, b in enumerate(bars)}
        i = index[t["symbol"]].get(t["entry"])
        if i is None:
            unmatched += 1
            continue
        if i + spec.TIME_BARRIER >= len(bars):
            short += 1
            continue
        if bars[i + spec.TIME_BARRIER].timestamp.date() > cutoff:
            continue
        close0 = bars[i].close
        atr = (close0 - t["initial_stop"]) / spec.STOP_ATR
        if atr <= 0:
            nonpositive += 1
            continue
        path = [(bars[i + s].close - close0) / atr for s in range(spec.TIME_BARRIER + 1)]
        for s in range(1, spec.TIME_BARRIER + 1):
            xs.append(path[s - 1])
            ys.append(path[s])
        used += 1
    n = len(xs)
    if used < 2 or n < 3:
        raise ValueError("{0}: only {1} qualifying paths - nothing to calibrate "
                         "on".format(year, used))
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    phi = sxy / sxx
    a = my - phi * mx
    sigma = math.sqrt(sum((y - a - phi * x) ** 2 for x, y in zip(xs, ys)) / (n - 2))

    profit = ar1_profit_paths(a, phi, sigma, spec.TIME_BARRIER, spec.SYNTHETIC_PATHS, year)
    rules = evaluate_rules(profit, spec.GRID_ATR + [math.inf], [spec.STOP_ATR])
    best = max(r.mean for r in rules)
    chosen = max((r for r in rules if r.mean >= best - 1e-12), key=lambda r: r.profit_take)
    k = None if math.isinf(chosen.profit_take) else chosen.profit_take
    return {
        "year": year, "cutoff": cutoff.isoformat(), "paths": used, "observations": n,
        "unmatched_entries": unmatched, "too_short": short, "nonpositive_atr": nonpositive,
        "a": a, "phi": phi, "sigma": sigma,
        "half_life": (-math.log(2) / math.log(phi)) if 0 < phi < 1 else None,
        "fair_level_atr": (a / (1 - phi)) if phi < 1 else None,
        "k_star": k,
        "grid_means": {("none" if math.isinf(r.profit_take) else r.profit_take): r.mean
                       for r in rules},
    }


def thirds(base_curve, var_curve):
    """Growth over three consecutive equal-session thirds, variant against baseline."""
    if [d for d, _v in base_curve] != [d for d, _v in var_curve]:
        raise ValueError("the equity curves are not on the same sessions")
    n = len(base_curve)
    edges = [0, n // 3, (2 * n) // 3, n - 1]
    out = []
    for j in range(3):
        s, e = edges[j], edges[j + 1]
        gb = base_curve[e][1] / base_curve[s][1]
        gv = var_curve[e][1] / var_curve[s][1]
        out.append({"from": base_curve[s][0], "to": base_curve[e][0],
                    "baseline_growth": gb, "variant_growth": gv, "variant_ahead": gv > gb})
    return out


def ambiguous_stops(series, packed):
    """Stop exits on a bar that also reached the limit - given to the stop, as sealed."""
    by_year = {int(y): k for y, k in (packed["take_profit_atr_by_year"] or {}).items()}
    count = 0
    for t in packed["trades"]:
        k = by_year.get(int(t["entry"][:4]))
        if t["reason"] != "stop" or k is None:
            continue
        bars = {b.timestamp.isoformat(): b for b in series[t["symbol"]]}
        entry_bar, exit_bar = bars.get(t["entry"]), bars.get(t["exit"])
        if entry_bar is None or exit_bar is None:
            continue
        atr = (entry_bar.close - t["initial_stop"]) / spec.STOP_ATR
        if exit_bar.high >= entry_bar.close + k * atr:
            count += 1
    return count


def main():
    if not prereg.verify_chain()["intact"]:
        return refuse("registration chain broken.")
    running = spec.hypothesis()
    try:
        sealed = prereg.verify(spec.HYPOTHESIS_ID, running)
    except prereg.RegistrationError as error:
        return refuse(str(error))
    problems = research_gate.check_registration(sealed)
    if problems:
        return refuse("dataset gate: " + "; ".join(problems))
    dirty = code_unchanged_since(sealed["code_commit"])
    if dirty:
        return refuse("H-0026 code changed since the registered commit: " + ", ".join(dirty))
    print("H-0026 seal {0} | commit {1} | registered {2}".format(
        sealed["seal"][:16], sealed["code_commit"][:12], sealed["registered_at"]), flush=True)

    series = load()
    spy = series["SPY"]
    spy_total = spy[-1].close / spy[0].close - 1.0
    print("decade: {0} symbols | SPY price {1:+.4%}".format(len(series), spy_total), flush=True)

    store = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    if store.get("seal") != sealed["seal"]:
        store = {"seal": sealed["seal"]}

    def save():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(store, separators=(",", ":"), default=str),
                         encoding="utf-8")

    if "BASELINE" not in store:
        print("\nEQUIVALENCE: the frozen configuration through the same override path",
              flush=True)
        rep = production_report(series, conviction=conviction, dataset="decade",
                                purpose="rejection_test", mr_config=MeanReversionConfig())
        store["BASELINE"] = pack(rep, "BASELINE")
        store["BASELINE_DSR"] = [deflated_sharpe(rep, trials=spec.DSR_TRIALS).probability,
                                 deflated_sharpe(rep, trials=78).probability]
        save()
    base = store["BASELINE"]
    b = base["metrics"]
    print("  {0:+.10%} over {1} trades | registered +58.5889000000% / 698".format(
        b["total_return"], b["trades"]), flush=True)
    if abs(b["total_return"] - 0.585889) > 5e-7 or b["trades"] != 698:
        print("STOPPED: baseline did not reproduce. Nothing else run.")
        return 2
    print("  IDENTICAL - proceeding", flush=True)

    last_year = spy[-1].timestamp.year
    calibration = [calibrate(series, base["trades"], y)
                   for y in range(spec.FIRST_YEAR, last_year + 1)]
    for c in calibration:
        print("  {0}: {1} paths, phi {2:.4f}, a {3:+.4f}, sigma {4:.4f}, half-life {5}, "
              "fair level {6} ATR -> k* {7}".format(
                  c["year"], c["paths"], c["phi"], c["a"], c["sigma"],
                  "-" if c["half_life"] is None else "{0:.2f}".format(c["half_life"]),
                  "-" if c["fair_level_atr"] is None else "{0:+.3f}".format(c["fair_level_atr"]),
                  "none" if c["k_star"] is None else c["k_star"]), flush=True)
    by_year = {c["year"]: c["k_star"] for c in calibration if c["k_star"] is not None}

    result = {"hypothesis_id": spec.HYPOTHESIS_ID, "seal": sealed["seal"],
              "code_commit": sealed["code_commit"], "registered_at": sealed["registered_at"],
              "run_at": datetime.now(timezone.utc).isoformat(), "spy_price_return": spy_total,
              "baseline": {k: base[k] for k in ("metrics", "exit_reasons")},
              "baseline_dsr": store["BASELINE_DSR"], "calibration": calibration,
              "take_profit_atr_by_year": by_year}

    if not by_year:
        result["outcome"] = "C"
        result["classification"] = ("C - NO TARGET: the calibrated process chose 'none' "
                                    "in every year; the rule is the baseline.")
    else:
        for label, through in (("PRIMARY", spec.TRADE_THROUGH), ("TOUCH_BOUND", 0.0)):
            if label in store:
                continue
            print("\nrunning {0} (trade-through {1}) ...".format(label, through), flush=True)
            rep = production_report(series, conviction=conviction, dataset="decade",
                                    purpose="rejection_test", mr_config=MeanReversionConfig(),
                                    mr_take_profit_atr_by_year=by_year,
                                    mr_take_profit_trade_through=through)
            store[label] = pack(rep, label, by_year)
            if label == "PRIMARY":
                store["PRIMARY_DSR"] = [deflated_sharpe(rep, trials=spec.DSR_TRIALS).probability,
                                        deflated_sharpe(rep, trials=78).probability]
            save()

        p, t = store["PRIMARY"], store["TOUCH_BOUND"]
        pm, tm = p["metrics"], t["metrics"]
        delta = pm["total_return"] - b["total_return"]
        gain = spec.START * (1 + pm["total_return"]) - spec.START * (1 + b["total_return"])
        net_of_haircut = gain - p["haircut_avoided_dollars"]
        third_rows = thirds(base["equity"], p["equity"])
        binding = p["take_profit_exits"] / pm["trades"] if pm["trades"] else 0.0
        dsr = store["PRIMARY_DSR"][0]
        clauses = {
            "A": delta >= spec.PENALTY,
            "E": net_of_haircut >= spec.PENALTY * spec.START,
            "B": abs(pm["max_drawdown"]) <= spec.CEILING,
            "D": sum(1 for r in third_rows if r["variant_ahead"]) >= 2,
            "F": binding >= spec.BINDING_MIN,
            "G": dsr is not None and dsr >= spec.DSR_MIN,
        }
        failed = [k for k, ok in clauses.items() if not ok]
        result.update({
            "primary": {k: p[k] for k in ("metrics", "exit_reasons", "take_profit_exits",
                                          "haircut_avoided_dollars")},
            "touch_bound": {k: t[k] for k in ("metrics", "exit_reasons", "take_profit_exits",
                                              "haircut_avoided_dollars")},
            "primary_minus_baseline_points": 100 * delta,
            "touch_minus_baseline_points": 100 * (tm["total_return"] - b["total_return"]),
            "gain_dollars": gain, "net_of_avoided_haircut_dollars": net_of_haircut,
            "thirds": third_rows, "binding_share": binding,
            "primary_dsr": store["PRIMARY_DSR"],
            "ambiguous_stop_bars": ambiguous_stops(series, p),
            "by_year_delta": {str(y): pm["by_year"].get(str(y), 0.0)
                              - b["by_year"].get(str(y), 0.0)
                              for y in sorted({str(k) for k in b["by_year"]}
                                              | {str(k) for k in pm["by_year"]})},
            "clauses": clauses, "failed": failed,
            "outcome": "A" if not failed else "B",
            "classification": ("A - PASSES every sealed clause (research_evidence only)"
                               if not failed else
                               "B - REJECTED on clause(s) " + ", ".join(failed)),
        })
        print("\nPRIMARY  total {0:+.4%} vs baseline {1:+.4%} -> {2:+.2f} points".format(
            pm["total_return"], b["total_return"], 100 * delta))
        print("  max drawdown {0:.4%} | trades {1} | take-profit exits {2} ({3:.1%})".format(
            pm["max_drawdown"], pm["trades"], p["take_profit_exits"], binding))
        print("  gain ${0:,.0f} | haircut avoided ${1:,.0f} | net ${2:,.0f}".format(
            gain, p["haircut_avoided_dollars"], net_of_haircut))
        print("  thirds ahead: {0} of 3 | DSR {1}".format(
            sum(1 for r in third_rows if r["variant_ahead"]), dsr))
        print("TOUCH BOUND (unexecutable) {0:+.2f} points".format(
            result["touch_minus_baseline_points"]))

    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print("\nOUTCOME {0}: {1}".format(result["outcome"], result["classification"]))
    print("wrote {0}".format(RESULTS.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
