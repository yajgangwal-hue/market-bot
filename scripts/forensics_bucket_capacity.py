"""FORENSIC, NON-PROMOTIONAL. Portfolio counterfactual for the bucket cap.

READ-ONLY IN INTENT: no production file is edited and nothing here is a
registered experiment or a promotion candidate. It DOES run the
simulator at different `max_per_bucket` values, so each run is recorded
against the decade in the usual way.

WHY ONLY THESE THREE. The cap is an integer. 1 is production, 2 is the
smallest possible relaxation, 3 is the next. No threshold is being
chosen and nothing is being optimised - the point is the SHAPE of the
tradeoff, not a best value. Anything requiring a fitted threshold is
named as a future pre-registration question instead of being searched.

WHAT WOULD MAKE A RESULT HERE MEANINGLESS. A higher cap mechanically
deploys more capital, and this strategy sits ~56% in cash while the
index compounds. More exposure will raise return on a decade when the
market rose. The only figures that matter are the RISK-ADJUSTED ones
and the drawdown against the standing 110% ceiling, which is
1.10 x 12.9824% = 14.2806% and is NOT relaxed here for any reason.
"""

import glob
import json
import sys
from dataclasses import replace
from pathlib import Path
from statistics import fmean, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.mean_reversion import conviction as shipped_conviction  # noqa: E402
from event_aware_trader.phase5.metrics import measure          # noqa: E402
from event_aware_trader.portfolio import run_portfolio          # noqa: E402
from event_aware_trader.research import (                       # noqa: E402
    PRODUCTION_CANDIDATE, _record_gate_use, DATASET_USES, production_policy)
from event_aware_trader.risk import CostModel                   # noqa: E402
from event_aware_trader.strategy import CORRELATION_BUCKETS      # noqa: E402

from forensics_regime import load                                # noqa: E402

_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-400:], c)
_conv = {}

CEILING_MULTIPLE = 1.10
CAPS = (1, 2, 3)


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def run(series, cap):
    _record_gate_use("decade", "diagnostic", len(series), DATASET_USES)
    policy = replace(production_policy(), max_per_bucket=cap)
    return run_portfolio(series, starting_cash=100_000.0, policy=policy,
                         costs=CostModel(), conviction=conviction,
                         **PRODUCTION_CANDIDATE)


def concurrency(report, eq_days):
    """Positions open per session, and same-bucket doubling."""
    per_day = {d: [] for d in eq_days}
    for t in report.trades:
        d0, d1 = t.entry_time.date(), t.exit_time.date()
        for d in eq_days:
            if d0 <= d < d1:
                per_day[d].append(t.symbol)
    counts = [len(v) for v in per_day.values()]
    doubled = 0
    worst = 0
    for v in per_day.values():
        bs = [CORRELATION_BUCKETS.get(s, "other") for s in v]
        dup = len(bs) - len(set(bs))
        if dup:
            doubled += 1
        worst = max(worst, max([bs.count(b) for b in set(bs)] or [0]))
    return {"mean_positions": fmean(counts), "max_positions": max(counts),
            "sessions_with_a_doubled_bucket": doubled,
            "share_doubled": doubled / len(eq_days),
            "worst_same_bucket_count": worst}


def main():
    series = load()
    print("decade: {0} symbols".format(len(series)), flush=True)
    out = {}
    base_dd = None
    for cap in CAPS:
        report = run(series, cap)
        m = measure(report, "max_per_bucket={0}".format(cap)).as_dict()
        eq_days = sorted({t.date() for t, _v in report.equity_curve})
        eq = {t.date(): v for t, v in report.equity_curve}
        cash = {t.date(): v for t, v in report.cash_curve}
        rets = []
        for i, d in enumerate(eq_days):
            if i and eq[eq_days[i - 1]]:
                rets.append(eq[d] / eq[eq_days[i - 1]] - 1.0)
        down = [r for r in rets if r < 0]
        con = concurrency(report, eq_days)
        m.update({
            "cap": cap,
            "downside_deviation": pstdev(down) * (252 ** 0.5) if down else None,
            "worst_day": min(rets), "best_day": max(rets),
            "worst_week": min(
                [eq[eq_days[i]] / eq[eq_days[i - 5]] - 1.0
                 for i in range(5, len(eq_days)) if eq[eq_days[i - 5]]]),
            "mean_cash_share": fmean([cash[d] / eq[d] for d in eq_days
                                      if eq.get(d)]),
            "rejected_for_capacity": report.rejected_for_capacity,
        })
        m.update(con)
        if cap == 1:
            base_dd = abs(m["max_drawdown"])
        out[cap] = m
        print("  cap {0}: done".format(cap), flush=True)

    ceiling = CEILING_MULTIPLE * base_dd
    print("\n" + "=" * 76)
    print("PORTFOLIO COUNTERFACTUAL - one position per bucket, then two,")
    print("then three. FORENSIC ONLY. Nothing here is a candidate.")
    print("=" * 76)
    print("  standing drawdown ceiling: 1.10 x {0:.4%} = {1:.4%}".format(
        base_dd, ceiling))
    print("\n  {0:<26} {1:>12} {2:>12} {3:>12}".format(
        "", "cap 1 (prod)", "cap 2", "cap 3"))
    rows = [
        ("total return", "total_return", "{0:+.2%}"),
        ("CAGR", "cagr", "{0:+.2%}"),
        ("annualised volatility", "annualised_volatility", "{0:.2%}"),
        ("downside deviation", "downside_deviation", "{0:.2%}"),
        ("Sharpe", "sharpe", "{0:.4f}"),
        ("Sortino", "sortino", "{0:.4f}"),
        ("MAX DRAWDOWN", "max_drawdown", "{0:.4%}"),
        ("Calmar", "calmar", "{0:.4f}"),
        ("worst day", "worst_day", "{0:.2%}"),
        ("worst 5-session", "worst_week", "{0:.2%}"),
        ("trades", "trades", "{0}"),
        ("turnover", "turnover", "{0:.2f}"),
        ("transaction costs", "transaction_costs", "${0:,.0f}"),
        ("exposure", "exposure", "{0:.2%}"),
        ("mean cash share", "mean_cash_share", "{0:.1%}"),
        ("mean positions", "mean_positions", "{0:.2f}"),
        ("max positions", "max_positions", "{0}"),
        ("win rate", "win_rate", "{0:.2%}"),
        ("profit factor", "profit_factor", "{0:.3f}"),
        ("sessions w/ doubled bucket", "share_doubled", "{0:.1%}"),
        ("worst same-bucket count", "worst_same_bucket_count", "{0}"),
    ]
    for label, key, fmt in rows:
        cells = []
        for cap in CAPS:
            v = out[cap].get(key)
            cells.append(fmt.format(v) if v is not None else "-")
        print("  {0:<26} {1:>12} {2:>12} {3:>12}".format(label, *cells))

    print("\n  DRAWDOWN AGAINST THE STANDING CEILING (not relaxed)")
    for cap in CAPS:
        dd = abs(out[cap]["max_drawdown"])
        print("    cap {0}: {1:.4%}  vs ceiling {2:.4%}  -> {3}".format(
            cap, dd, ceiling, "WITHIN" if dd <= ceiling else "BREACH"))

    print("\n  RISK-ADJUSTED VERDICT (the only comparison that matters here)")
    for cap in CAPS[1:]:
        d = out[cap]
        b = out[1]
        print("    cap {0}: return {1:+.2f} pts, Sharpe {2:+.4f}, Sortino "
              "{3:+.4f}, Calmar {4:+.4f}, maxDD {5:+.2f} pts".format(
                  cap,
                  100 * (d["total_return"] - b["total_return"]),
                  d["sharpe"] - b["sharpe"], d["sortino"] - b["sortino"],
                  d["calmar"] - b["calmar"],
                  100 * (abs(d["max_drawdown"]) - abs(b["max_drawdown"]))))

    path = REPO / "docs" / "phase5" / "bucket-capacity.json"
    path.write_text(json.dumps({
        "FORENSIC_NON_PROMOTIONAL": True,
        "ceiling_multiple": CEILING_MULTIPLE, "ceiling": ceiling,
        "configurations": out,
        "note": "READ-ONLY FORENSICS. Not registered, not promotable. "
                "Mechanical integer caps only; no threshold was chosen.",
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(path.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
