"""Run H-0038 exactly as registered. Research only; nothing here trades.

H-0038 is H-0037 with one defect fixed: H-0037's runner looked up a
"B_minus_C" comparison it never computed, and crashed in the verdict step
before printing or writing any result. The verdict now lives in `decide`,
which reads C - B for both outcomes and is unit-tested."""

import json
import math
import sys
from datetime import date
from pathlib import Path
from statistics import mean, median, stdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader import portfolio as portfolio_module          # noqa: E402
from event_aware_trader.mean_reversion import (                       # noqa: E402
    MeanReversionConfig, conviction as shipped_conviction)
from event_aware_trader.modelgov import prereg                        # noqa: E402
from event_aware_trader.phase5.metrics import measure                 # noqa: E402
from event_aware_trader.research import production_report             # noqa: E402

import h0038_spec as spec                                              # noqa: E402
import h0037_tp_placement as tp                                        # noqa: E402
import research_gate                                                   # noqa: E402
from forensics_regime import load                                      # noqa: E402

RESULTS = REPO / "docs" / "phase5" / "h0038-results.json"


def decide(results):
    """(criteria, verdict) as registered. MOVE: C beats B; KEEP: B beats C.
    Both read the C - B comparison, with the sign of the claimed winner."""
    def holds(winner):
        sign = 1.0 if winner == "C" else -1.0
        p = results["primary"]["C_minus_B"]
        mean_ = sign * (p["all"].get("mean") or 0.0)
        t_ = sign * (p["all"].get("t") or 0.0)
        halves_ok = all(sign * (h.get("mean") or 0.0) > 0 for h in p["halves"].values())
        others = all(sign * (results[l]["C_minus_B"]["all"].get("mean") or 0.0) > 0
                     for l in ("backtest", "none"))
        return mean_ > 0 and t_ >= 2.0 and halves_ok and others

    move, keep = holds("C"), holds("B")
    return ({"MOVE": move, "KEEP": keep},
            "MOVE" if move else ("KEEP" if keep else "NO DIFFERENCE SHOWN"))

# The speed patch H-0010 and H-0026 used, licensed by the baseline reproducing below.
_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-400:], c)
_conv = {}


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def summary(values):
    n = len(values)
    if n < 2:
        return {"n": n}
    m, sd = mean(values), stdev(values)
    return {"n": n, "mean": m, "t": m / (sd / math.sqrt(n)) if sd > 0 else None,
            "median": median(values), "positive_share": sum(1 for v in values if v > 0) / n}


def main():
    try:
        sealed = prereg.verify(spec.HYPOTHESIS_ID, spec.hypothesis())
    except prereg.RegistrationError as error:
        print("REFUSED: " + str(error))
        return 2
    problems = research_gate.check_registration(sealed)
    if problems:
        print("REFUSED: dataset gate: " + "; ".join(problems))
        return 2
    series = load()
    report = production_report(series, conviction=conviction, dataset="decade",
                               purpose="rejection_test", mr_config=MeanReversionConfig())
    total = float(measure(report, "BASELINE").as_dict()["total_return"])
    trades = report.trades
    print("baseline %+.10f%% over %d trades (registered +58.5889%% / 698)" % (100 * total, len(trades)),
          flush=True)
    if abs(total - 0.585889) > 5e-7 or len(trades) != 698:
        print("STOPPED: the baseline did not reproduce.")
        RESULTS.write_text(json.dumps({"verdict": "STOPPED", "reason": "baseline"}), encoding="utf-8")
        return 2

    arrays = {}
    for symbol, bars in series.items():
        closes = [b.close for b in bars]
        ag, al = tp.wilder_averages(closes)
        index = {b.timestamp: i for i, b in enumerate(bars)}
        arrays[symbol] = (bars, closes, ag, al, index)

    rows, matched, comparable, entry_ok = [], 0, 0, 0
    for t in trades:
        bars, closes, ag, al, index = arrays[t.symbol]
        i = index[t.entry_time]
        raw_entry = bars[i].close
        if abs(t.entry_price / (raw_entry * (1.0 + tp.SIDE_COST)) - 1.0) < 1e-6:
            entry_ok += 1
        risk = raw_entry - t.initial_stop
        take = raw_entry + risk                       # 2.5 x entry ATR = 1R against the 2.5-ATR stop
        after = bars[i + 1:]
        prev_ag = ag[i:i + len(after)]
        prev_al = al[i:i + len(after)]
        prev_close = closes[i:i + len(after)]
        row = {"symbol": t.symbol, "entry": t.entry_time.date().isoformat(), "risk": risk,
               "baseline_reason": t.exit_reason, "baseline_exit": t.exit_time.date().isoformat(),
               "baseline_r": (t.exit_price - t.entry_price) / risk}
        for label, h in spec.HAIRCUTS.items():
            for policy in tp.POLICIES:
                out = tp.replay(after, prev_ag, prev_al, prev_close, raw_entry, t.initial_stop,
                                take, policy, h)
                if out is None:                       # the data ends inside the window
                    row["%s_%s" % (policy, label)] = None
                    continue
                raw_exit, reason, held = out
                row["%s_%s" % (policy, label)] = {"r": tp.net_r(raw_exit, t.entry_price, risk),
                                                   "reason": reason, "held": held,
                                                   "exit": after[held - 1].timestamp.date().isoformat(),
                                                   "raw_exit": raw_exit}
        a = row.get("A_backtest")
        if a is not None and t.exit_reason in ("stop", "reverted", "time_exit"):
            comparable += 1
            same_day = a["exit"] == row["baseline_exit"]
            expected = t.exit_price / (1.0 - tp.SIDE_COST)
            if same_day and abs(a["raw_exit"] / expected - 1.0) < 1e-6:
                matched += 1
        rows.append(row)

    match_rate = matched / comparable if comparable else 0.0
    out = {"registration": {"seal": sealed["seal"], "registered_at": sealed["registered_at"]},
           "baseline": {"total_return": total, "trades": len(trades)},
           "replay_check": {"comparable": comparable, "matched": matched, "rate": match_rate,
                            "entries_at_signal_close_plus_cost": entry_ok,
                            "baseline_reasons": {}}}
    for t in trades:
        out["replay_check"]["baseline_reasons"][t.exit_reason] = \
            out["replay_check"]["baseline_reasons"].get(t.exit_reason, 0) + 1
    print("replay A reproduces %d of %d comparable baseline exits (%.1f%%)" % (
        matched, comparable, 100 * match_rate), flush=True)
    if match_rate < spec.MATCH_FLOOR:
        out["verdict"] = "STOPPED"
        RESULTS.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
        print("STOPPED: the replay does not represent the strategy.")
        return 2

    split = spec.SPLIT
    usable = [r for r in rows if all(r.get("%s_%s" % (p, l)) is not None
                                     for p in tp.POLICIES for l in spec.HAIRCUTS)]
    out["usable_trades"] = len(usable)
    results = {}
    for label in spec.HAIRCUTS:
        block = {}
        for p in tp.POLICIES:
            rs = [r["%s_%s" % (p, label)]["r"] for r in usable]
            held = [r["%s_%s" % (p, label)]["held"] for r in usable]
            reasons = {}
            for r in usable:
                k = r["%s_%s" % (p, label)]["reason"]
                reasons[k] = reasons.get(k, 0) + 1
            block[p] = {"r": summary(rs), "mean_sessions_held": mean(held),
                        "r_per_session_held": sum(rs) / sum(held), "exits": reasons}
        for x, y in (("C", "B"), ("B", "A"), ("C", "A"), ("D", "B"), ("D", "A"), ("D", "C")):
            diffs = [r["%s_%s" % (x, label)]["r"] - r["%s_%s" % (y, label)]["r"] for r in usable]
            halves = {}
            for name, keep in (("first", lambda r: r["entry"] < split), ("second", lambda r: r["entry"] >= split)):
                d = [r["%s_%s" % (x, label)]["r"] - r["%s_%s" % (y, label)]["r"] for r in usable if keep(r)]
                halves[name] = summary(d)
            by_year = {}
            for r in usable:
                y_ = r["entry"][:4]
                by_year.setdefault(y_, []).append(r["%s_%s" % (x, label)]["r"] - r["%s_%s" % (y, label)]["r"])
            block["%s_minus_%s" % (x, y)] = {"all": summary(diffs), "halves": halves,
                                             "by_year": {k: mean(v) for k, v in sorted(by_year.items())}}
        results[label] = block
    out["results"] = results

    out["criteria"], out["verdict"] = decide(results)
    RESULTS.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    p = results["primary"]
    print("primary h=0.3%: " + "  ".join(
        "%s %s" % (x, p[x]["r"].get("mean")) for x in tp.POLICIES) + " R/trade")
    print("C - B:", p["C_minus_B"]["all"], "halves:",
          {k: v.get("mean") for k, v in p["C_minus_B"]["halves"].items()})
    print("verdict:", out["verdict"])
    print("wrote " + str(RESULTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
