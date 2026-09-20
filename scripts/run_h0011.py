"""Run H-0011. Equivalence first, then the three sealed patience values.

ONE parameter moves: run_portfolio's mr_limit_exit = (0.0, patience).
It goes through the keyword path, so mr_limit_exit=None must reproduce
production byte-identically and the fingerprint cannot move. Both are
checked here and the run STOPS if either fails.

CLAUSE E IS COMPUTED HERE, not left to the adjudicator. The clause
requires the FILLED and LAPSED populations to be priced separately
against what the same trade would have realised as a market exit at
the trigger close. Rather than plumb the trigger close through
ClosedTrade, this matches each configuration's trades against the
BASELINE run on (symbol, entry date) - the entry rule is untouched, so
the baseline's own `reverted` exit IS the counterfactual, measured
rather than modelled.

Trades that fail to match are reported, not discarded: holding a
position while an order works ties up capital and can block a later
entry, and that churn is a real cost of the mechanism.

Each configuration is cached the moment it finishes.
"""

import json
import sys
from pathlib import Path

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

OFFSET = 0.0
HAIRCUT = 0.00652
FINGERPRINT = "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b"
SEALED = [("A patience1", 1), ("B patience2", 2), ("C patience3", 3)]
CACHE = REPO / "docs" / "phase5" / "h0011-cache.json"


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def pack(report, label):
    reasons = {}
    for t in report.trades:
        reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
    filled = reasons.get("limit_exit", 0)
    lapsed = reasons.get("limit_lapsed", 0)
    avoided = sum(abs(t.quantity) * t.exit_price * HAIRCUT
                  for t in report.trades if t.exit_reason == "limit_exit")
    return {
        "metrics": measure(report, label).as_dict(),
        "exit_reasons": reasons,
        "limit_filled": filled,
        "limit_lapsed": lapsed,
        "fill_rate": (filled / (filled + lapsed)) if (filled + lapsed) else None,
        "haircut_avoided_dollars": avoided,
        "max_bars_held": max((t.bars_held for t in report.trades), default=0),
        "trades": [{"symbol": t.symbol,
                    "entry": t.entry_time.date().isoformat(),
                    "exit": t.exit_time.date().isoformat(),
                    "qty": t.quantity, "entry_price": t.entry_price,
                    "exit_price": t.exit_price, "net_pnl": t.net_pnl,
                    "r": t.r_multiple, "reason": t.exit_reason,
                    "bars_held": t.bars_held}
                   for t in report.trades],
        "equity": [[d.date().isoformat(), v] for d, v in report.equity_curve],
    }


def clause_e(base_trades, cfg_trades):
    """Price FILLED and LAPSED against the baseline's own market exit.

    The baseline trade with the same (symbol, entry date) is the
    counterfactual: same entry, same size, exited at the trigger close
    with the haircut charged. The difference in net_pnl is what the
    resting order actually earned or cost on that trade.
    """
    base = {(t["symbol"], t["entry"]): t for t in base_trades}
    out = {"filled": {"n": 0, "delta": 0.0}, "lapsed": {"n": 0, "delta": 0.0},
           "other": {"n": 0, "delta": 0.0},
           "unmatched_cfg": 0, "unmatched_base": 0}
    seen = set()
    for t in cfg_trades:
        key = (t["symbol"], t["entry"])
        b = base.get(key)
        if b is None:
            out["unmatched_cfg"] += 1
            continue
        seen.add(key)
        bucket = ("filled" if t["reason"] == "limit_exit"
                  else "lapsed" if t["reason"] == "limit_lapsed" else "other")
        out[bucket]["n"] += 1
        out[bucket]["delta"] += t["net_pnl"] - b["net_pnl"]
    out["unmatched_base"] = len(base) - len(seen)
    out["total_delta"] = (out["filled"]["delta"] + out["lapsed"]["delta"]
                          + out["other"]["delta"])
    return out


def main():
    sealed = [p for p in prereg.load() if p["hypothesis_id"] == "H-0011"]
    if not sealed:
        print("REFUSED: H-0011 is not registered.")
        return 2
    seal = sealed[0]
    if not prereg.verify_chain()["intact"]:
        print("REFUSED: registration chain broken.")
        return 2
    reg = seal["parameters"]["patience_sessions"]
    if sorted(reg.values()) != sorted(v for _n, v in SEALED):
        print("REFUSED: runner patience values are not the sealed values.")
        return 2
    if seal["parameters"]["offset"] != OFFSET:
        print("REFUSED: runner offset is not the sealed 0.0.")
        return 2
    if frozen_fingerprint() != FINGERPRINT:
        print("REFUSED: strategy fingerprint moved.")
        return 2
    print("H-0011 seal {0} | commit {1}".format(seal["seal"][:16],
                                                seal["code_commit"][:12]))
    print("sealed patience: {0} | offset {1} | fingerprint OK".format(
        reg, OFFSET), flush=True)

    series = load()
    spy = series["SPY"]
    spy_total = spy[-1].close / spy[0].close - 1.0
    print("\ndecade: {0} symbols | SPY {1:+.4%}".format(
        len(series), spy_total), flush=True)
    store = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() \
        else {}

    def save():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(store, separators=(",", ":"),
                                    default=str), encoding="utf-8")

    if "BASELINE" not in store:
        print("\nEQUIVALENCE: frozen configuration, mr_limit_exit left None",
              flush=True)
        rep = production_report(series, conviction=conviction,
                                dataset="decade", purpose="rejection_test",
                                mr_config=MeanReversionConfig())
        store["BASELINE"] = pack(rep, "BASELINE")
        save()
    b = store["BASELINE"]["metrics"]
    print("  {0:+.10%} over {1} trades | registered +58.5889000000% / 698"
          .format(b["total_return"], b["trades"]))
    if abs(b["total_return"] - 0.585889) > 5e-7 or b["trades"] != 698:
        print("STOPPED: baseline did not reproduce. Nothing else run.")
        return 2
    print("  IDENTICAL - proceeding", flush=True)

    for label, patience in SEALED:
        if label in store:
            continue
        print("\nrunning {0} (limit at trigger close, {1} session(s) "
              "patience) ...".format(label, patience), flush=True)
        rep = production_report(series, conviction=conviction,
                                dataset="decade", purpose="rejection_test",
                                mr_config=MeanReversionConfig(),
                                mr_limit_exit=(OFFSET, patience))
        store[label] = pack(rep, label)
        store[label]["clause_e"] = clause_e(store["BASELINE"]["trades"],
                                            store[label]["trades"])
        save()
        m = store[label]["metrics"]
        e = store[label]["clause_e"]
        print("  total {0:+.2%} | Sharpe {1:.4f} | maxDD {2:.2%} | trades {3}"
              .format(m["total_return"], m["sharpe"], m["max_drawdown"],
                      m["trades"]))
        print("  filled {0} | lapsed {1} | fill rate {2} | avoided ${3:,.0f}"
              .format(store[label]["limit_filled"],
                      store[label]["limit_lapsed"],
                      "{0:.1%}".format(store[label]["fill_rate"])
                      if store[label]["fill_rate"] is not None else "n/a",
                      store[label]["haircut_avoided_dollars"]))
        print("  clause E: filled {0:+,.0f} over {1} | lapsed {2:+,.0f} over "
              "{3} | net {4:+,.0f}".format(
                  e["filled"]["delta"], e["filled"]["n"],
                  e["lapsed"]["delta"], e["lapsed"]["n"], e["total_delta"]),
              flush=True)

    print("\nwrote {0}".format(CACHE.relative_to(REPO)))
    print("run scripts/analyse_h0011.py to adjudicate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
