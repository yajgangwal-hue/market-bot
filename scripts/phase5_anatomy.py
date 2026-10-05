"""Phase 5 §7. Where the frozen strategy's trades actually fail.

Runs the production candidate unchanged, then describes every trade by the
state that preceded its entry. No parameter is altered and nothing is
optimised here - the output is a description, and a description is not a
finding until it survives the other window.

The purpose declared to the contamination gate is `diagnostic`: this run
attaches no accept/reject to anything. Both windows are spent for the
current candidate, so nothing measured here can ACCEPT a change; it can
only point at where to look.

  python scripts/phase5_anatomy.py deep
  python scripts/phase5_anatomy.py long
"""

import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.data import load_bars                  # noqa: E402
from event_aware_trader.evaluation import evaluate             # noqa: E402
from event_aware_trader.mean_reversion import conviction as shipped_conviction  # noqa: E402
from event_aware_trader.phase5.features import (               # noqa: E402
    anatomise, bucket, market_context, split_by, split_by_flag, split_by_key)
from event_aware_trader.research import production_report      # noqa: E402
from event_aware_trader.strategy import (                      # noqa: E402
    CORRELATION_BUCKETS, DEFAULT_UNIVERSE, is_crypto)

# Decade price data comes only through the research dataset gate: verified
# before a bar is read, fail-closed, no scratchpad fallback. It replaced a
# first-match glob over session scratchpads on 2026-09-24
# (docs/2026-09-24-governed-research-dataset-migration.md).
if str(REPO / "scripts") not in sys.path:
    sys.path.append(str(REPO / "scripts"))
from research_gate import dataset_file, price_dir              # noqa: E402

# The same 400-bar signal window and cached conviction the earlier baselines
# used. Not an optimisation: without them a 30-year run recomputes the full
# history on every bar and takes hours.
WINDOW = 400
_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-WINDOW:], c)
_conv = {}


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


WINDOWS = {
    "deep": {"folder": "deep", "since": None, "minimum": 500,
             "dataset": "decade", "label": "THE DECADE 2016-2026"},
    "long": {"folder": "long", "since": date(1996, 1, 1), "minimum": 400,
             "dataset": "thirty_year", "label": "THIRTY YEARS 1996-2026"},
}


def load(folder, since=None, minimum=500):
    base = price_dir(folder)        # verified before any bar is read
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        bars = load_bars(dataset_file(base, symbol + ".csv"))
        if since:
            bars = [b for b in bars if b.timestamp.date() >= since]
        if len(bars) >= minimum:
            out[symbol] = bars
    return out


def show(title, buckets):
    print("\n  {0}".format(title))
    print("    {0:<34} {1:>6} {2:>12} {3:>9} {4:>9} {5:>8}".format(
        "bucket", "n", "P&L", "median R", "mean R", "win%"))
    for b in buckets:
        if not b.trades:
            continue
        print("    {0:<34} {1:>6} {2:>12,.0f} {3:>9} {4:>9} {5:>8}".format(
            b.label, b.trades, b.total_pnl,
            "-" if b.median_r is None else "{0:+.3f}".format(b.median_r),
            "-" if b.mean_r is None else "{0:+.3f}".format(b.mean_r),
            "-" if b.win_rate is None else "{0:.1%}".format(b.win_rate)))


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "deep"
    spec = WINDOWS[which]
    series = load(spec["folder"], spec["since"], spec["minimum"])
    print("{0}  ({1} symbols)".format(spec["label"], len(series)), flush=True)

    report = production_report(series, conviction=conviction,
                               dataset=spec["dataset"], purpose="diagnostic")
    scored = evaluate(report, spec["label"])
    print("baseline: {0} trades, total return {1:+.2%}, CAGR {2:+.2%}, "
          "maxDD {3:.2%}, win {4:.1%}".format(
              scored.trades, scored.total_return, scored.cagr,
              scored.max_drawdown, scored.win_rate), flush=True)

    market = market_context(series.get("SPY", []))
    rows = anatomise(report.trades, series, market, CORRELATION_BUCKETS)
    print("anatomised {0} of {1} trades".format(len(rows), len(report.trades)))

    overall = bucket(rows, "ALL")
    show("overall", [overall])
    show("by exit reason", split_by_key(rows, "exit_reason", minimum=1))
    show("market trend at entry", split_by_flag(rows, "market_above_ma50"))
    show("market trend at entry (200d)", split_by_flag(rows, "market_above_ma200"))
    show("market drawdown at entry",
         split_by(rows, "market_drawdown", [-0.10, -0.05, -0.02]))
    show("market volatility at entry",
         split_by(rows, "market_volatility_20", [0.008, 0.014]))
    show("own volatility (ATR fraction)",
         split_by(rows, "atr_fraction", [0.015, 0.025]))
    show("distance above the 200-day average",
         split_by(rows, "above_ma200_by", [0.02, 0.10, 0.25]))
    show("size of the 5-session drop",
         split_by(rows, "drop_5", [-0.10, -0.05, -0.02]))
    show("gap into the entry bar", split_by(rows, "gap", [-0.02, 0.0, 0.02]))
    show("entry-day volume vs its 20-day average",
         split_by(rows, "volume_ratio", [1.0, 1.5, 2.5]))
    show("60-session relative strength vs the index",
         split_by(rows, "relative_strength_60", [-0.15, 0.0, 0.15]))
    show("holding period", split_by(rows, "bars_held", [3, 8, 15]))
    show("worst sectors (>=20 trades)", split_by_key(rows, "sector")[:8])
    show("best sectors (>=20 trades)", split_by_key(rows, "sector")[-8:])

    out = REPO / "data" / "phase5" / "anatomy-{0}.jsonl".format(which)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(dict(r.__dict__), sort_keys=True) + "\n"
                           for r in rows), encoding="utf-8")
    print("\nwrote {0} ({1} rows)".format(out.relative_to(REPO), len(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
