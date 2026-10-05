"""EXP-0057 disclosure: the bounce-price take profit at PORTFOLIO level.

Owner, 2026-10-04: "ok now implement everything into the bot". H-0038
compared take-profit placements trade by trade, which cannot see an earlier
sale's freed cash being redeployed. This runs the whole account on the decade
for each placement - purpose 'diagnostic', no accept/reject attached, the
same disclosure EXP-0055 made - so the change ships with its portfolio-level
numbers stated.

  A  the frozen candidate (no take profit)          must reproduce +58.5889% / 698
  B  + a take profit at 2.5 x entry ATR (EXP-0055)  its own disclosure: +67.21% / 756
  C  + the bounce-price take profit (EXP-0057)

each at the production rule-exit haircut (0.652%) and at 0.3%. Take-profit
exits are resting limits and pay no haircut; the rule exits do.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader import portfolio as portfolio_module          # noqa: E402
from event_aware_trader.mean_reversion import (                       # noqa: E402
    MeanReversionConfig, conviction as shipped_conviction)
from event_aware_trader.phase5.metrics import measure                 # noqa: E402
from event_aware_trader.research import production_report             # noqa: E402

from forensics_regime import load                                      # noqa: E402

OUT = REPO / "docs" / "phase5" / "exp0057-portfolio-diagnostic.json"

# The speed patch H-0010, H-0026 and H-0038 used, licensed by A reproducing.
_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-400:], c)
_conv = {}


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def pack(report, label, haircut):
    reasons = {}
    for t in report.trades:
        reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
    avoided = sum(abs(t.quantity) * t.exit_price * haircut
                  for t in report.trades if t.exit_reason == "take_profit")
    m = measure(report, label).as_dict()
    keep = ("total_return", "cagr", "annualised_volatility", "sharpe", "max_drawdown",
            "profitable_years", "trades", "win_rate")
    net = sum(t.net_pnl for t in report.trades)
    return {"label": label, "haircut": haircut,
            "metrics": {k: m.get(k) for k in keep}, "exits": reasons,
            "realised_pnl": net, "haircut_avoided_by_take_profits": avoided,
            "realised_pnl_net_of_haircut_avoided": net - avoided}


def main():
    series = load()
    years = sorted({b.timestamp.year for bars in series.values() for b in bars})
    variants = {
        "A_frozen": {},
        "B_atr_2.5": {"mr_take_profit_atr_by_year": {y: 2.5 for y in years}},
        "C_bounce": {"mr_take_profit_bounce": True},
    }
    out = {}
    for haircut in (0.00652, 0.003):
        for name, overrides in variants.items():
            label = "{0}@{1:g}".format(name, haircut)
            report = production_report(series, conviction=conviction, dataset="decade",
                                       purpose="diagnostic", mr_config=MeanReversionConfig(),
                                       rule_exit_timing_haircut=haircut, **overrides)
            out[label] = pack(report, label, haircut)
            m = out[label]["metrics"]
            print("{0:18s} total {1:+.4%}  CAGR {2:+.3%}  maxDD {3:+.2%}  Sharpe {4:.3f}  trades {5}  exits {6}".format(
                label, m["total_return"], m["cagr"], m["max_drawdown"], m["sharpe"], m["trades"],
                out[label]["exits"]), flush=True)
            OUT.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    a = out["A_frozen@0.00652"]["metrics"]
    if abs(a["total_return"] - 0.585889) > 5e-7 or a["trades"] != 698:
        print("WARNING: the frozen baseline did not reproduce; the comparison is not valid.")
    print("wrote " + str(OUT))


if __name__ == "__main__":
    main()
