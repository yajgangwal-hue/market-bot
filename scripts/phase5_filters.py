"""Phase 5 §8. Test information as a FILTER on the frozen strategy.

Every variant here runs the production candidate unchanged and removes
candidates through `model_veto`, the hook that can only ever subtract. No
parameter is retuned, no exit is altered, and the portfolio is re-run in
full so that capital freed by a rejected entry is available to the next
one - which is the difference between a real test and a post-hoc average.

WHAT THIS CANNOT ESTABLISH. Both historical windows are contaminated for
the current candidate, so a positive result here is a hypothesis and
never an acceptance. There is no untouched test period left in this
project's history; the only unseen data is Track A's forward record,
which the research track may not spend. Phase 5's honest ceiling is
therefore `research_evidence`.

  python scripts/phase5_filters.py deep
  python scripts/phase5_filters.py deep --only atr_floor
  python scripts/phase5_filters.py long --only atr_floor,trend_margin
"""

import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.data import load_bars                  # noqa: E402
from event_aware_trader.indicators import average_true_range   # noqa: E402
from event_aware_trader.mean_reversion import conviction as shipped_conviction  # noqa: E402
from event_aware_trader.phase5.metrics import compare, measure  # noqa: E402
from event_aware_trader.research import production_report      # noqa: E402
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto  # noqa: E402

# Decade price data comes only through the research dataset gate: verified
# before a bar is read, fail-closed, no scratchpad fallback. It replaced a
# first-match glob over session scratchpads on 2026-09-24
# (docs/2026-09-24-governed-research-dataset-migration.md).
if str(REPO / "scripts") not in sys.path:
    sys.path.append(str(REPO / "scripts"))
from research_gate import dataset_file, price_dir              # noqa: E402

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
             "dataset": "decade", "label": "decade 2016-2026"},
    "long": {"folder": "long", "since": date(1996, 1, 1), "minimum": 400,
             "dataset": "thirty_year", "label": "thirty years 1996-2026"},
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


# ---------------------------------------------------------------------------
# The filters. Each returns True to REMOVE a candidate.
#
# Every one reads only `history`, which the simulator guarantees contains
# bars that have already printed. None of them can add a trade, change a
# size, or move an exit.
# ---------------------------------------------------------------------------

_cache = {}


def _state(symbol, history):
    """ATR fraction, trend margin, 5-day drop and volume ratio at this bar."""
    key = (symbol, len(history))
    hit = _cache.get(key)
    if hit is not None:
        return hit
    closes = [b.close for b in history]
    last = history[-1]
    atr = average_true_range(history[-15:], 14) if len(history) > 14 else None
    ma200 = sum(closes[-200:]) / 200.0 if len(closes) >= 200 else None
    volumes = [b.volume for b in history[-21:-1]]
    average_volume = sum(volumes) / len(volumes) if volumes else None
    hit = {
        "atr_fraction": (atr / last.close if atr and last.close else None),
        "trend_margin": (last.close / ma200 - 1.0 if ma200 else None),
        "drop_5": (closes[-1] / closes[-6] - 1.0
                   if len(closes) >= 6 and closes[-6] else None),
        "volume_ratio": (last.volume / average_volume
                         if average_volume else None),
    }
    _cache[key] = hit
    return hit


def atr_floor(minimum):
    """Skip names whose 2.5-ATR stop sits inside ordinary daily noise.

    The frozen rule caps ATR at 3.5% but has no floor, so a name moving
    0.6% a day gets a stop 1.5% away and is stopped out by nothing at all.
    The decade anatomy found 46 such trades at a 47.8% stop rate against
    34.2% overall.
    """
    def veto(symbol, history):
        value = _state(symbol, history)["atr_fraction"]
        return value is not None and value < minimum
    return veto


def trend_margin(minimum):
    """Require real distance above the 200-day average, not a hairline.

    `close > SMA200` is a binary, and a third of all entries sat within 2%
    of it - the weakest third by median R and the highest by stop rate.
    """
    def veto(symbol, history):
        value = _state(symbol, history)["trend_margin"]
        return value is not None and value < minimum
    return veto


def needs_a_drop(maximum):
    """Require the oversold reading to come with an actual recent fall."""
    def veto(symbol, history):
        value = _state(symbol, history)["drop_5"]
        return value is not None and value > maximum
    return veto


def volume_ceiling(maximum):
    """Skip entries on an extreme volume day - capitulation, not a dip."""
    def veto(symbol, history):
        value = _state(symbol, history)["volume_ratio"]
        return value is not None and value > maximum
    return veto


def combined(*vetoes):
    def veto(symbol, history):
        return any(v(symbol, history) for v in vetoes)
    return veto


VARIANTS = {
    "atr_floor": [("atr_floor {0:.3%}".format(m), atr_floor(m))
                  for m in (0.008, 0.010, 0.0125, 0.015)],
    "trend_margin": [("trend_margin {0:.1%}".format(m), trend_margin(m))
                     for m in (0.01, 0.02, 0.03)],
    "needs_a_drop": [("needs_a_drop {0:.1%}".format(m), needs_a_drop(m))
                     for m in (-0.01, -0.02, -0.03)],
    "volume_ceiling": [("volume_ceiling {0:.1f}x".format(m), volume_ceiling(m))
                       for m in (2.5, 4.0)],
    "combined": [("atr_floor 1.0% + trend_margin 2%",
                  combined(atr_floor(0.010), trend_margin(0.02)))],
}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "deep"
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))

    spec = WINDOWS[which]
    series = load(spec["folder"], spec["since"], spec["minimum"])
    print("{0}  ({1} symbols)".format(spec["label"], len(series)), flush=True)

    base_report = production_report(series, conviction=conviction,
                                    dataset=spec["dataset"],
                                    purpose="rejection_test")
    baseline = measure(base_report, "BASELINE " + spec["label"])
    print("\n{0:<34} {1:>6} {2:>8} {3:>8} {4:>8} {5:>7} {6:>8} {7:>8}".format(
        "variant", "trades", "total", "CAGR", "maxDD", "stop%", "Sharpe", "Calmar"))
    show(baseline)

    results = [baseline.as_dict()]
    for family, variants in VARIANTS.items():
        if only and family not in only:
            continue
        for label, veto in variants:
            report = production_report(series, conviction=conviction,
                                       dataset=spec["dataset"],
                                       purpose="rejection_test",
                                       model_veto=veto)
            scored = measure(report, label)
            show(scored)
            row = scored.as_dict()
            row["family"] = family
            row["difference"] = compare(scored, baseline)
            results.append(row)

    out = REPO / "data" / "phase5" / "filters-{0}.json".format(which)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=1, sort_keys=True, default=str),
                   encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


def show(m):
    print("{0:<34} {1:>6} {2:>8} {3:>8} {4:>8} {5:>7} {6:>8} {7:>8}".format(
        m.label[:34], m.trades,
        "{0:+.1%}".format(m.total_return), "{0:+.2%}".format(m.cagr),
        "{0:.2%}".format(m.max_drawdown),
        "-" if m.stop_rate is None else "{0:.1%}".format(m.stop_rate),
        "-" if m.sharpe is None else "{0:.2f}".format(m.sharpe),
        "-" if m.calmar is None else "{0:.2f}".format(m.calmar)), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
