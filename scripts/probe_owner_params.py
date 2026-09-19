"""FORENSIC. Measure the owner's requested parameters before setting them.

READ-ONLY: production is NOT modified. Every configuration is passed
through run_portfolio's existing `mr_config` override, exactly as
H-0009 did, so src/ is untouched and the frozen fingerprint cannot move.

WHAT WAS ASKED FOR, and how each piece maps to the code.

  max hold ~2 days  -> MeanReversionConfig.max_holding_bars = 2
                       exact, directly supported.

  stop loss 2%      -> NOT DIRECTLY EXPRESSIBLE. The stop is
                       entry - stop_atr_multiple * ATR(14), so its
                       distance is volatility-dependent: 2.99% of
                       price in the tightest ATR quartile, 7.73% in
                       the widest, ~5.45% on average. The closest
                       config-only approximation is a multiple of
                       0.917, which puts the AVERAGE stop at ~2% but
                       leaves it ranging ~1.1% to ~2.8% by name. An
                       exact fixed 2% would require editing
                       mean_reversion.evaluate, i.e. a production
                       change, and is therefore not done here.

  take profit 5%    -> mr_take_profit_r is denominated in R, not
                       percent, and R is the stop distance. With the
                       ~2% stop above, 5% is 2.5R. Quoted that way.

Configurations are run one at a time and cached as each finishes.
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
from event_aware_trader.phase5.metrics import measure           # noqa: E402
from event_aware_trader.research import production_report       # noqa: E402

from forensics_regime import load                                # noqa: E402

_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-400:], c)
_conv = {}
CACHE = REPO / "docs" / "phase5" / "owner-params-cache.json"

#: 2.5 x ATR is the frozen stop. Mean ATR fraction across taken trades
#: is 2.18%, so this multiple puts the AVERAGE stop near 2% of price.
STOP_MULT_FOR_2PCT = 0.917

CONFIGS = [
    ("BASELINE", {}, {}),
    ("hold 2 days only", {"max_holding_bars": 2}, {}),
    ("stop ~2% only", {"stop_atr_multiple": STOP_MULT_FOR_2PCT}, {}),
    ("stop ~2% + TP 5%", {"stop_atr_multiple": STOP_MULT_FOR_2PCT},
     {"mr_take_profit_r": 2.5}),
    ("ALL THREE as asked", {"stop_atr_multiple": STOP_MULT_FOR_2PCT,
                            "max_holding_bars": 2},
     {"mr_take_profit_r": 2.5}),
]


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def main():
    series = load()
    spy = series["SPY"]
    spy_total = spy[-1].close / spy[0].close - 1.0
    print("decade: {0} symbols | SPY {1:+.4%}".format(len(series), spy_total),
          flush=True)
    store = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() \
        else {}

    for label, cfg_over, run_over in CONFIGS:
        if label in store:
            continue
        cfg = replace(MeanReversionConfig(), **cfg_over) if cfg_over else None
        kwargs = dict(run_over)
        if cfg is not None:
            kwargs["mr_config"] = cfg
        print("\nrunning {0} ...".format(label), flush=True)
        rep = production_report(series, conviction=conviction,
                                dataset="decade", purpose="rejection_test",
                                **kwargs)
        m = measure(rep, label).as_dict()
        reasons = {}
        for t in rep.trades:
            reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
        m["exit_reasons"] = reasons
        m["vs_spy_points"] = 100.0 * (m["total_return"] - spy_total)
        store[label] = m
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(store, indent=1, sort_keys=True,
                                    default=str), encoding="utf-8")
        print("  total {0:+.2%} | Sharpe {1:.4f} | maxDD {2:.2%} | "
              "trades {3} | hold {4:.1f}d".format(
                  m["total_return"], m["sharpe"], m["max_drawdown"],
                  m["trades"], m["average_hold_days"]), flush=True)

    b = store["BASELINE"]
    print("\n" + "=" * 86)
    print("OWNER-REQUESTED PARAMETERS, MEASURED (production NOT changed)")
    print("=" * 86)
    labels = [c[0] for c in CONFIGS]
    rows = [("total return", "total_return", "{0:+.2%}"),
            ("CAGR", "cagr", "{0:+.2%}"),
            ("Sharpe", "sharpe", "{0:.4f}"),
            ("max drawdown", "max_drawdown", "{0:.2%}"),
            ("trades", "trades", "{0}"),
            ("win rate", "win_rate", "{0:.2%}"),
            ("profit factor", "profit_factor", "{0:.3f}"),
            ("avg hold (days)", "average_hold_days", "{0:.2f}"),
            ("stop rate", "stop_rate", "{0:.2%}"),
            ("turnover", "turnover", "{0:.2f}"),
            ("transaction costs", "transaction_costs", "${0:,.0f}"),
            ("exposure", "exposure", "{0:.2%}"),
            ("vs SPY (points)", "vs_spy_points", "{0:+.1f}")]
    w = 20
    print("  {0:<{1}}".format("", w) + "".join(
        "{0:>17}".format(x[:17]) for x in labels))
    for name, key, fmt in rows:
        cells = []
        for L in labels:
            v = store[L].get(key)
            cells.append(fmt.format(v) if v is not None else "-")
        print("  {0:<{1}}".format(name, w) + "".join(
            "{0:>17}".format(c) for c in cells))
    print("\n  delta vs baseline (points of total return)")
    for L in labels[1:]:
        print("    {0:<24} {1:+.2f}".format(
            L, 100 * (store[L]["total_return"] - b["total_return"])))
    print("\n  exit-reason mix")
    for L in labels:
        print("    {0:<24} {1}".format(L, store[L]["exit_reasons"]))
    print("\nwrote {0}".format(CACHE.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
