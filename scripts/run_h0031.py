"""Run H-0031 exactly as registered: one position at a time, 99% of the account in it.

Refuses unless H-0031 is registered, its seal matches the spec, every code file
hashes to what was sealed, and the frozen baseline reproduces +58.5889% / 698.
"""

import json
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.mean_reversion import MeanReversionConfig        # noqa: E402
from event_aware_trader.modelgov import prereg                          # noqa: E402
from event_aware_trader.portfolio import run_portfolio                  # noqa: E402
from event_aware_trader.research import (PRODUCTION_CANDIDATE,          # noqa: E402
                                         check_dataset_gate, load_tbill_rates,
                                         production_policy, production_report,
                                         with_parked_cash)
from event_aware_trader.risk import CostModel                           # noqa: E402

import h0031_spec as spec                                               # noqa: E402
import run_h0026 as r                                                   # verified loader + speed patch
import run_short_hypotheses as rs                                       # metrics, SPY curves
import short_sleeve_research as sr                                      # noqa: E402

RESULTS = REPO / "docs" / "phase5" / "h0031-results.json"


def all_in(bars, series, rank=True, costs=None, dataset="decade"):
    """The production candidate with the three registered policy changes."""
    check_dataset_gate(bars, dataset, "rejection_test")
    policy = replace(production_policy(), max_open_positions=1,
                     max_notional_fraction=0.99, risk_per_trade=1.0)

    def live_score(symbol, history):
        s = series.get(symbol)
        if s is None or not history:
            return None
        i = s.index.get(history[-1].timestamp.date())
        if i is None or s.rsi[i] is None:
            return None
        return 100.0 - s.rsi[i]

    kwargs = dict(PRODUCTION_CANDIDATE)
    return run_portfolio(bars, starting_cash=100_000.0, policy=policy,
                         costs=costs or CostModel(), conviction=None,
                         candidate_rank=live_score if rank else None,
                         mr_config=MeanReversionConfig(), **kwargs)


def summary(report, rates):
    parked = with_parked_cash(report, rates)
    un = [(t.date(), v) for t, v in report.equity_curve]
    pk = [(t.date(), v) for t, v in parked.equity_curve]
    trades = report.trades
    worst = min(trades, key=lambda t: t.net_pnl) if trades else None
    invested = [1.0 - c / e for (_, e), (_, c) in zip(report.equity_curve, report.cash_curve) if e > 0]
    return {
        "parked": rs.metrics(pk), "unparked": rs.metrics(un),
        "halves_parked_cagr": {
            "first": rs.metrics(rs.slice_curve(pk, pk[0][0], rs.HALF_SPLIT)).get("cagr"),
            "second": rs.metrics(rs.slice_curve(pk, rs.HALF_SPLIT, date(9999, 1, 1))).get("cagr")},
        "trades": len(trades),
        "win_rate": sum(1 for t in trades if t.net_pnl > 0) / len(trades) if trades else None,
        "exposure_mean": sum(invested) / len(invested) if invested else None,
        "gapped_through_stop": report.gapped_through_stop,
        "worst_trade": None if worst is None else {
            "symbol": worst.symbol, "entry": worst.entry_time.date().isoformat(),
            "exit": worst.exit_time.date().isoformat(), "net": worst.net_pnl,
            "pct_of_position": worst.exit_price / worst.entry_price - 1.0,
            "reason": worst.exit_reason},
        "worst_5_trades_dollars": sorted(round(t.net_pnl, 2) for t in trades)[:5],
    }, pk


def main():
    h = spec.hypothesis()
    try:
        registered = prereg.verify("H-0031", h)
    except prereg.RegistrationError as error:
        print("REFUSED: " + str(error))
        return 2
    bars = r.load()
    rates = load_tbill_rates(REPO / "data" / "tbill.csv")
    base = production_report(bars, conviction=r.conviction, dataset="decade",
                             purpose="rejection_test", mr_config=MeanReversionConfig())
    if round(base.equity / base.starting_cash - 1.0, 6) != 0.585889 or len(base.trades) != 698:
        print("REFUSED: the frozen baseline did not reproduce")
        return 2
    print("baseline reproduced: +58.5889% / 698", flush=True)
    series = {sym: sr.Series.from_bars(sym, b) for sym, b in bars.items()}
    ctx = sr.Context(series["SPY"], rates)
    calendar = list(series["SPY"].dates)

    A, a_curve = summary(base, rates)
    primary_report = all_in(bars, series)
    X, x_curve = summary(primary_report, rates)
    print("all-in: {0:.2%} CAGR parked, maxDD {1:.2%}, {2} trades".format(
        X["parked"]["cagr"], X["parked"]["max_drawdown"], X["trades"]), flush=True)

    cost12, _ = summary(all_in(bars, series, costs=CostModel(half_spread_bps=6.0, slippage_bps=6.0)), rates)
    default_order, _ = summary(all_in(bars, series, rank=False), rates)

    etfs = {s: b for s, b in bars.items() if s in rs.ETFS}
    base_etf = production_report(etfs, conviction=r.conviction, dataset="etf_subset",
                                 purpose="rejection_test", mr_config=MeanReversionConfig())
    A_etf, _ = summary(base_etf, rates)
    X_etf, _ = summary(all_in(etfs, series, dataset="etf_subset"), rates)

    spy_price, spy_tr = rs.spy_curves(ctx, calendar)
    criteria = {
        "R1_full": X["parked"]["cagr"] > A["parked"]["cagr"],
        "R1_halves": all(X["halves_parked_cagr"][k] > A["halves_parked_cagr"][k] for k in ("first", "second")),
        "R2_sharpe": (X["parked"]["sharpe"] or 0) >= (A["parked"]["sharpe"] or 0),
        "R3_drawdown": abs(X["parked"]["max_drawdown"]) <= 1.10 * abs(A["parked"]["max_drawdown"]),
        "R4_robustness": (cost12["parked"]["cagr"] > A["parked"]["cagr"]
                          and default_order["parked"]["cagr"] > A["parked"]["cagr"]
                          and X_etf["parked"]["cagr"] > A_etf["parked"]["cagr"]),
    }
    if not (criteria["R1_full"] and criteria["R2_sharpe"] and criteria["R3_drawdown"]):
        verdict = "REJECTED"
    elif not (criteria["R1_halves"] and criteria["R4_robustness"]):
        verdict = "INCONCLUSIVE"
    else:
        verdict = "PROMISING BUT NOT READY FOR OOS"
    out = {"registration": {"seal": registered["seal"], "registered_at": registered["registered_at"]},
           "verdict": verdict, "criteria": criteria,
           "A_frozen_baseline": A, "all_in_one_position": X,
           "robustness": {"one_way_12bp": cost12, "default_candidate_order": default_order,
                          "etf_universe_baseline": A_etf, "etf_universe_all_in": X_etf},
           "spy": {"price": rs.metrics(spy_price), "total_return_approx": rs.metrics(spy_tr)}}
    RESULTS.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("H-0031: " + verdict)
    print("wrote " + str(RESULTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
