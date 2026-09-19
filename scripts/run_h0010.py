"""Run H-0010. Equivalence first, then the three sealed stop widths.

Two parameters move together and nothing else does:
MeanReversionConfig.stop_atr_multiple, and run_portfolio's existing
mr_take_profit_r held at 2.5 throughout. Both go through the override
path, so src/ is untouched and the fingerprint cannot move.

CLAUSE E IS COMPUTED HERE, not left to the adjudicator's imagination.
A take profit is a resting limit and pays no 0.652% rule-exit haircut,
while 'reverted' and 'time_exit' do. For every take_profit exit this
records what the haircut WOULD have cost had that exit been a rule
exit, so the adjudicator can subtract it and ask whether anything
survives.

Each configuration is cached the moment it finishes.
"""

import json
import sys
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.mean_reversion import (                 # noqa: E402
    MeanReversionConfig, conviction as shipped_conviction)
from event_aware_trader.modelgov import prereg                  # noqa: E402
from event_aware_trader.phase5.metrics import measure           # noqa: E402
from event_aware_trader.research import production_report       # noqa: E402

from forensics_regime import load                                # noqa: E402

_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-400:], c)
_conv = {}

TAKE_PROFIT_R = 2.5
HAIRCUT = 0.00652
SEALED = [("A stop0.917", 0.917), ("B stop1.25", 1.25), ("C stop1.75", 1.75)]
CACHE = REPO / "docs" / "phase5" / "h0010-cache.json"


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
    # CLAUSE E: what the take-profit exits avoided by being limits.
    avoided = sum(abs(t.quantity) * t.exit_price * HAIRCUT
                  for t in report.trades if t.exit_reason == "take_profit")
    return {
        "metrics": measure(report, label).as_dict(),
        "exit_reasons": reasons,
        "take_profit_exits": reasons.get("take_profit", 0),
        "haircut_avoided_dollars": avoided,
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


def main():
    sealed = [p for p in prereg.load() if p["hypothesis_id"] == "H-0010"]
    if not sealed:
        print("REFUSED: H-0010 is not registered.")
        return 2
    seal = sealed[0]
    if not prereg.verify_chain()["intact"]:
        print("REFUSED: registration chain broken.")
        return 2
    reg = seal["parameters"]["stop_atr_multiple"]
    if sorted(reg.values()) != sorted(v for _n, v in SEALED):
        print("REFUSED: runner multiples are not the sealed multiples.")
        return 2
    if seal["parameters"]["take_profit_r"] != TAKE_PROFIT_R:
        print("REFUSED: runner take profit is not the sealed 2.5R.")
        return 2
    print("H-0010 seal {0} | commit {1}".format(seal["seal"][:16],
                                                seal["code_commit"][:12]))
    print("sealed stop multiples: {0} | take profit {1}R".format(
        reg, TAKE_PROFIT_R), flush=True)

    series = load()
    spy = series["SPY"]
    spy_total = spy[-1].close / spy[0].close - 1.0
    print("\ndecade: {0} symbols | SPY {1:+.4%}".format(len(series),
                                                        spy_total), flush=True)
    store = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() \
        else {}

    def save():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(store, separators=(",", ":"),
                                    default=str), encoding="utf-8")

    if "BASELINE" not in store:
        print("\nEQUIVALENCE: the frozen configuration through the same "
              "override path", flush=True)
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

    for label, mult in SEALED:
        if label in store:
            continue
        print("\nrunning {0} (stop {1} x ATR, TP {2}R) ...".format(
            label, mult, TAKE_PROFIT_R), flush=True)
        cfg = replace(MeanReversionConfig(), stop_atr_multiple=mult)
        rep = production_report(series, conviction=conviction,
                                dataset="decade", purpose="rejection_test",
                                mr_config=cfg,
                                mr_take_profit_r=TAKE_PROFIT_R)
        store[label] = pack(rep, label)
        save()
        m = store[label]["metrics"]
        print("  total {0:+.2%} | Sharpe {1:.4f} | maxDD {2:.2%} | "
              "trades {3} | TP exits {4} | haircut avoided ${5:,.0f}".format(
                  m["total_return"], m["sharpe"], m["max_drawdown"],
                  m["trades"], store[label]["take_profit_exits"],
                  store[label]["haircut_avoided_dollars"]), flush=True)

    print("\nwrote {0}".format(CACHE.relative_to(REPO)))
    print("run scripts/analyse_h0010.py to adjudicate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
