"""H-0016 - instrumented cash-capacity pass. Read-only, sealed design.

src/ is NOT modified. Production functions are WRAPPED to record and
return their genuine values; baseline equivalence is asserted, which is
the proof the probes are non-invasive.

AVAILABLE CASH IS RECONSTRUCTED, NOT GUESSED. report.cash_curve records
cash at the start of each day's entry loop, before any entry that day.
Within a day cash falls only by accepted outlays, in trace order. So
for the k-th candidate of a session:

    available = day_start_cash - sum(outlays accepted earlier that day)

The reconstruction is VALIDATED against production's own counter: the
number of candidates for which requested outlay exceeds reconstructed
available cash must equal report.rejected_for_capacity exactly. If it
does not, the run stops rather than reporting a reconstruction.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean, median, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader import portfolio as PM                  # noqa: E402
from event_aware_trader.forward import frozen_fingerprint        # noqa: E402
from event_aware_trader.mean_reversion import (                  # noqa: E402
    MeanReversionConfig, conviction as shipped_conviction)
from event_aware_trader.modelgov import prereg                   # noqa: E402
from event_aware_trader.phase5.metrics import measure            # noqa: E402
from event_aware_trader.research import (                        # noqa: E402
    PRODUCTION_CANDIDATE, production_report)
from event_aware_trader.risk import CostModel                    # noqa: E402
from forensics_regime import load                                 # noqa: E402

SEAL = "df03e54cc404abc35d0ffd00439318c352332e1632150971a35e54d6fb17804d"
FP = "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b"
HORIZONS = [1, 5, 10, 20]
PRIMARY = 10
BINS = [(1.0, 1.25), (1.25, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, float("inf"))]
BINLAB = ["(1.0,1.25]", "(1.25,1.5]", "(1.5,2.0]", "(2.0,3.0]", "(3.0,inf)"]
OUT = REPO / "docs" / "phase5" / "h0016-results.json"
TRACE = []
_conv = {}


def conviction(symbol, history):
    k = (symbol, len(history), history[0].timestamp if history else None)
    v = _conv.get(k)
    if v is None:
        v = _conv[k] = shipped_conviction(history[-40:])
    return v


def third_of(y):
    return 1 if y <= 2019 else 2 if y <= 2023 else 3


def main():
    s = [p for p in prereg.load() if p["hypothesis_id"] == "H-0016"]
    if not s or s[0]["seal"] != SEAL:
        print("REFUSED: H-0016 seal missing or altered.")
        return 2
    if not prereg.verify_chain()["intact"] or frozen_fingerprint() != FP:
        print("REFUSED: chain or fingerprint.")
        return 2
    if PRODUCTION_CANDIDATE.get("entry_fill") != "signal_close":
        print("REFUSED: entry_fill is not signal_close; the pending-path "
              "capacity counter at line 387 would become reachable and the "
              "839 could no longer be attributed to the entry cash test.")
        return 2
    print("H-0016 seal {0} | commit {1}".format(SEAL[:16],
                                                s[0]["code_commit"][:12]))
    print("entry_fill=signal_close -> pending capacity path unreachable\n")

    real_sig, real_size = PM.mean_reversion_signal, PM.position_size
    real_buy = CostModel.buy_fill
    real_cap = PM.cap_by_participation

    def sig(symbol, history, cfg):
        r = real_sig(symbol, history, cfg)
        ok = bool(r.is_buy and r.stop is not None and r.stop < r.close)
        if ok:
            TRACE.append({"symbol": symbol,
                          "date": history[-1].timestamp.date().isoformat(),
                          "close": r.close, "stop": r.stop,
                          "qty": None, "qty_presize": None,
                          "risk": None, "fill": None})
        return r

    def size(*a, **k):
        q, planned = real_size(*a, **k)
        if TRACE and TRACE[-1]["qty_presize"] is None:
            TRACE[-1]["qty_presize"] = q
            TRACE[-1]["risk"] = planned
        return q, planned

    def cap(quantity, price, adv, frac):
        """FINAL quantity hook.

        position_size runs BEFORE the conviction multiplier (up to 1.5x)
        and the max_notional ceiling clamp, so its return is NOT what
        production spends. cap_by_participation receives the fully
        scaled and clamped quantity and is the last stage before the
        fill and the cash test, so this is the size that sets outlay.
        Using position_size's value under-stated every outlay and made
        the reconstruction miss 241 rejections.
        """
        allowed = real_cap(quantity, price, adv, frac)
        if TRACE and TRACE[-1]["qty"] is None:
            TRACE[-1]["qty"] = allowed
        return allowed

    def buy(self, price):
        f = real_buy(self, price)
        if TRACE and TRACE[-1]["fill"] is None:
            TRACE[-1]["fill"] = f
        return f

    PM.mean_reversion_signal, PM.position_size = sig, size
    PM.cap_by_participation = cap
    CostModel.buy_fill = buy
    print("running the frozen baseline with recording probes ...", flush=True)
    series = load()
    rep = production_report(series, conviction=conviction, dataset="decade",
                            purpose="rejection_test",
                            mr_config=MeanReversionConfig())
    PM.mean_reversion_signal, PM.position_size = real_sig, real_size
    PM.cap_by_participation = real_cap
    CostModel.buy_fill = real_buy

    m = measure(rep, "BASELINE").as_dict()
    print("  {0:+.10%} over {1} trades | maxDD {2:.4%} | Sharpe {3:.4f}".format(
        m["total_return"], m["trades"], m["max_drawdown"], m["sharpe"]))
    if abs(m["total_return"] - 0.585889) > 5e-7 or m["trades"] != 698:
        print("STOPPED: probes perturbed the baseline.")
        return 2
    print("  IDENTICAL - probes non-invasive\n")

    cash_start = {d.date().isoformat(): c for d, c in rep.cash_curve}
    taken = {}
    for t in rep.trades:
        taken[(t.symbol, t.entry_time.date().isoformat())] = t

    # ---- reconstruct available cash at each decision --------------------
    by_day = defaultdict(list)
    for r in TRACE:
        by_day[r["date"]].append(r)
    rows = []
    denied = 0
    for day, recs in by_day.items():
        avail = cash_start.get(day)
        if avail is None:
            continue
        spent = 0.0
        acc_before = 0
        for r in recs:
            if r["qty"] is None or r["fill"] is None:
                continue
            outlay = r["fill"] * r["qty"]
            av = avail - spent
            is_taken = (r["symbol"], day) in taken
            rec = dict(r, outlay=outlay, available=av,
                       ratio=(outlay / av) if av > 0 else float("inf"),
                       accepted=is_taken, accepted_before=acc_before,
                       day_start_cash=avail)
            if is_taken:
                spent += outlay
                acc_before += 1
            else:
                denied += 1
            rows.append(rec)

    prod_cash = rep.rejected_for_capacity
    recon = sum(1 for r in rows if not r["accepted"] and r["ratio"] > 1.0)
    print("=== RECONSTRUCTION VALIDATION ===")
    print("  production report.rejected_for_capacity   {0}".format(prod_cash))
    print("  reconstructed outlay > available cash     {0}".format(recon))
    print("  traced candidates                         {0}".format(len(rows)))
    print("  not accepted in trace                     {0}".format(denied))
    if recon != prod_cash:
        print("\n  MISMATCH of {0}. The cash reconstruction does not "
              "reproduce production's own counter.".format(recon - prod_cash))
        print("  STOPPING rather than reporting a reconstruction that does "
              "not validate.")
        json.dump({"validation_failed": True, "production": prod_cash,
                   "reconstructed": recon, "traced": len(rows)},
                  open(OUT, "w"), indent=1)
        return 3
    print("  EXACT MATCH - reconstruction validated\n")

    # ---- forward outcomes ----------------------------------------------
    px = {sym: {b.timestamp.date().isoformat(): b.close for b in bars}
          for sym, bars in series.items()}
    dates = {sym: sorted(d) for sym, d in px.items()}
    idx = {sym: {d: i for i, d in enumerate(v)} for sym, v in dates.items()}
    spy, spyd = px["SPY"], dates["SPY"]
    spyi = idx["SPY"]

    def fwd(sym, day, h):
        i = idx[sym].get(day)
        if i is None or i + h >= len(dates[sym]):
            return None, None
        base = px[sym][day]
        r = px[sym][dates[sym][i + h]] / base - 1.0
        j = spyi.get(day)
        sp = (spy[spyd[j + h]] / spy[day] - 1.0
              if j is not None and j + h < len(spyd) else None)
        return r, (r - sp) if sp is not None else None

    def mfe_mae(sym, day, h=20):
        i = idx[sym].get(day)
        if i is None:
            return None, None
        bars = series[sym]
        seg = bars[i + 1:i + 1 + h]
        if not seg:
            return None, None
        base = px[sym][day]
        return (max(b.high for b in seg) / base - 1.0,
                min(b.low for b in seg) / base - 1.0)

    for r in rows:
        for h in HORIZONS:
            a, b = fwd(r["symbol"], r["date"], h)
            r["f{0}".format(h)] = a
            r["s{0}".format(h)] = b
        r["mfe"], r["mae"] = mfe_mae(r["symbol"], r["date"])
        r["year"] = int(r["date"][:4])
        r["third"] = third_of(r["year"])

    acc = [r for r in rows if r["accepted"]]
    den = [r for r in rows if not r["accepted"] and r["ratio"] > 1.0]
    print("  accepted {0} | cash-denied {1}".format(len(acc), len(den)))

    def agg(g):
        o = {"n": len(g)}
        for h in HORIZONS:
            v = [x["f{0}".format(h)] for x in g
                 if x.get("f{0}".format(h)) is not None]
            sv = [x["s{0}".format(h)] for x in g
                  if x.get("s{0}".format(h)) is not None]
            o["f{0}_mean".format(h)] = fmean(v) if v else None
            o["f{0}_med".format(h)] = median(v) if v else None
            o["s{0}_mean".format(h)] = fmean(sv) if sv else None
            o["s{0}_win".format(h)] = (sum(1 for x in sv if x > 0) / len(sv)
                                       if sv else None)
        mf = [x["mfe"] for x in g if x["mfe"] is not None]
        ma = [x["mae"] for x in g if x["mae"] is not None]
        o["mfe"] = fmean(mf) if mf else None
        o["mae"] = fmean(ma) if ma else None
        return o

    res = {"FORENSIC_NON_PROMOTIONAL": True, "seal": SEAL, "baseline": m,
           "production_counter": prod_cash, "reconstruction_matches": True,
           "P_total_traced": len(rows), "accepted": len(acc),
           "cash_denied": len(den),
           "accepted_stats": agg(acc), "denied_stats": agg(den)}

    # intensity bins
    res["bins"] = {}
    for (lo, hi), lab in zip(BINS, BINLAB):
        g = [r for r in den if lo < r["ratio"] <= hi]
        e = agg(g)
        e["pct_of_denied"] = len(g) / len(den) if den else None
        e["mean_outlay"] = fmean([r["outlay"] for r in g]) if g else None
        e["mean_available"] = fmean([r["available"] for r in g]) if g else None
        res["bins"][lab] = e
    # thirds
    res["thirds"] = {}
    for t in (1, 2, 3):
        pt = [r for r in rows if r["third"] == t]
        dt = [r for r in den if r["third"] == t]
        at = [r for r in acc if r["third"] == t]
        res["thirds"][t] = {"P": len(pt), "accepted": len(at),
                            "denied": len(dt),
                            "rate": len(dt) / len(pt) if pt else None,
                            "denied_stats": agg(dt), "accepted_stats": agg(at),
                            "mean_ratio": fmean([r["ratio"] for r in dt
                                                 if r["ratio"] != float("inf")])
                            if dt else None}
    # concentration
    res["concentration"] = {
        "symbols": len({r["symbol"] for r in den}),
        "sessions": len({r["date"] for r in den}),
        "top_symbols": Counter(r["symbol"] for r in den).most_common(10),
        "top_sessions": Counter(r["date"] for r in den).most_common(10),
        "by_year": dict(Counter(r["year"] for r in den)),
    }
    # portfolio-state cause
    cause = Counter()
    for r in den:
        if r["accepted_before"] > 0:
            cause["earlier_accepted_same_session"] += 1
        elif r["day_start_cash"] < r["outlay"]:
            cause["existing_positions_at_day_start"] += 1
        else:
            cause["other"] += 1
    res["cause"] = dict(cause)
    res["rows_sample"] = rows[:5]
    json.dump(res, open(OUT, "w"), indent=1, sort_keys=True, default=str)
    print("\nwrote {0}".format(OUT.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
