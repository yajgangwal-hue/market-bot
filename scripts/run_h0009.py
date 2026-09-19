"""Run H-0009. Equivalence first, then the three sealed thresholds.

ONE PARAMETER MOVES. `MeanReversionConfig.rsi_entry`, passed through
run_portfolio's existing `mr_config` argument. It has exactly one
decision call site - mean_reversion.evaluate line 417 - so entry
eligibility is the only thing that changes. No production file is
touched and no ranking mechanism is introduced.

THE CENTRAL ANALYSIS IS DISPLACEMENT, not the return column. Every
entry a configuration makes is classified against what the BASELINE
did on that same session:

  KEPT      the baseline took this name on this day too
  EMPTY     the baseline took nothing at all that session, so this
            entry occupies a slot that was genuinely idle
  EXTRA     the baseline traded that session but not this name, and
            did not lose one of its own - added alongside
  DISPLACED the baseline took a name this configuration did NOT, and
            this configuration took a different one instead

Only EMPTY additions are free. A DISPLACED pair is a swap, and its
worth is the realised P&L of what was taken minus the realised P&L of
what the baseline took instead - measured, not assumed. The registered
clause D fails a configuration that profits by evicting better names.

The cache is written per configuration as soon as it finishes, so a
killed process never costs more than one run.
"""

import json
import sys
from collections import defaultdict
from dataclasses import replace
from datetime import date
from pathlib import Path
from statistics import fmean, median, pstdev

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

BASELINE_RSI = 35.0
SEALED = [("A rsi36", 36.0), ("B rsi37", 37.0), ("C rsi38", 38.0)]
CEILING_MULTIPLE = 1.10
CACHE = REPO / "docs" / "phase5" / "h0009-cache.json"


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def pack(report, label):
    return {
        "metrics": measure(report, label).as_dict(),
        "trades": [{"symbol": t.symbol,
                    "entry": t.entry_time.date().isoformat(),
                    "exit": t.exit_time.date().isoformat(),
                    "qty": t.quantity, "entry_price": t.entry_price,
                    "exit_price": t.exit_price, "net_pnl": t.net_pnl,
                    "r": t.r_multiple, "reason": t.exit_reason,
                    "bars_held": t.bars_held,
                    "highest_high": t.highest_high,
                    "lowest_low": t.lowest_low}
                   for t in report.trades],
        "equity": [[d.date().isoformat(), v] for d, v in report.equity_curve],
        "cash": [[d.date().isoformat(), v] for d, v in report.cash_curve],
        "rejected_for_capacity": report.rejected_for_capacity,
    }


def run(series, rsi, label):
    cfg = replace(MeanReversionConfig(), rsi_entry=rsi)
    rep = production_report(series, conviction=conviction, dataset="decade",
                            purpose="rejection_test", mr_config=cfg)
    return pack(rep, label)


def main():
    sealed = [p for p in prereg.load() if p["hypothesis_id"] == "H-0009"]
    if not sealed:
        print("REFUSED: H-0009 is not registered.")
        return 2
    seal = sealed[0]
    if not prereg.verify_chain()["intact"]:
        print("REFUSED: registration chain broken.")
        return 2
    registered = seal["parameters"]["configurations"]
    if sorted(registered.values()) != sorted(v for _n, v in SEALED):
        print("REFUSED: runner thresholds are not the sealed thresholds.")
        return 2
    print("H-0009 seal {0} | commit {1}".format(seal["seal"][:16],
                                                seal["code_commit"][:12]))
    print("sealed thresholds: {0}".format(registered), flush=True)

    series = load()
    spy = series["SPY"]
    spy_total = spy[-1].close / spy[0].close - 1.0
    print("\ndecade: {0} symbols, SPY {1:+.4%}".format(len(series), spy_total),
          flush=True)

    store = {}
    if CACHE.exists():
        store = json.loads(CACHE.read_text(encoding="utf-8"))
        print("resuming from cache: {0}".format(sorted(store)), flush=True)

    def save():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(store, separators=(",", ":"),
                                    default=str), encoding="utf-8")

    # ---- equivalence -----------------------------------------------------
    if "BASELINE" not in store:
        print("\nEQUIVALENCE: rsi_entry=35.0 passed explicitly through the "
              "same override path", flush=True)
        store["BASELINE"] = run(series, BASELINE_RSI, "BASELINE")
        save()
    b = store["BASELINE"]["metrics"]
    print("  {0:+.10%} over {1} trades | registered +58.5889000000% / 698"
          .format(b["total_return"], b["trades"]))
    if abs(b["total_return"] - 0.585889) > 5e-7 or b["trades"] != 698:
        print("STOPPED: baseline did not reproduce. Nothing else run.")
        return 2
    print("  IDENTICAL - proceeding", flush=True)

    for label, rsi in SEALED:
        if label in store:
            continue
        print("\nrunning {0} (rsi_entry={1}) ...".format(label, rsi),
              flush=True)
        store[label] = run(series, rsi, label)
        save()
        m = store[label]["metrics"]
        print("  {0:+.4%} over {1} trades, maxDD {2:.4%}".format(
            m["total_return"], m["trades"], m["max_drawdown"]), flush=True)

    print("\nwrote {0}".format(CACHE.relative_to(REPO)))
    print("run scripts/analyse_h0009.py to adjudicate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
