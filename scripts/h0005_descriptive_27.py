"""The registered 27-trade descriptive analysis. NON-DECISION-MAKING.

Population: trades that were winners under the baseline and losers under
the G=1.00R lock.

This cannot and does not alter the H-0005 verdict, which was determined
by the family classification before this ran. It may report counts,
distributions, standardised differences and descriptive summaries. It
may not rank or select features, choose thresholds, derive rules,
produce p-value-based decisions, or select a configuration. Anything
interesting here becomes a future hypothesis with its own registration
and its own data.

The permitted variables were fixed in the registration before the
identities of these trades were known - the earlier attribution recorded
only their count and aggregate P&L.
"""

import glob
import json
import sys
from pathlib import Path
from statistics import fmean, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.data import load_bars                  # noqa: E402
from event_aware_trader.mean_reversion import conviction as shipped_conviction  # noqa: E402
from event_aware_trader.phase5.features import (               # noqa: E402
    anatomise, market_context)
from event_aware_trader.research import production_report      # noqa: E402
from event_aware_trader.strategy import (                      # noqa: E402
    CORRELATION_BUCKETS, DEFAULT_UNIVERSE, is_crypto)

SCRATCH = Path(glob.glob(
    "C:/Users/yajga/AppData/Local/Temp/claude/**/scratchpad/deep",
    recursive=True)[0]).parent
WINDOW = 400
_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-WINDOW:], c)
_conv = {}

#: Registered permitted entry-time variables. Nothing outside this list.
PERMITTED_ENTRY_TIME = [
    "atr_fraction", "above_ma200_by", "drop_5", "volume_ratio",
    "market_drawdown", "market_volatility_20", "relative_strength_60"]
PERMITTED_FLAGS = ["market_above_ma50", "market_above_ma200"]

#: Registered but NOT MEASURED here. The simulator does not expose the
#: moment the lock armed, and adding that instrumentation is a change to
#: the money-path simulator on the evening of a verdict. Reported as
#: unmeasured rather than approximated.
NOT_MEASURED = ["sessions_from_entry_to_arming",
                "r_multiple_of_prior_high_at_arming",
                "atr_fraction_at_arming", "sessions_arming_to_stop",
                "index_fell_over_that_span", "gap_on_stop_session"]


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def load():
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        path = SCRATCH / "deep" / (symbol + ".csv")
        if path.exists():
            try:
                bars = load_bars(path)
            except Exception:
                continue
            if len(bars) >= 500:
                out[symbol] = bars
    return out


def standardised_difference(a, b):
    """Cohen's d. A DESCRIPTIVE effect size, not a test and not a decision."""
    a = [v for v in a if v is not None]
    b = [v for v in b if v is not None]
    if len(a) < 2 or len(b) < 2:
        return None
    sa, sb = pstdev(a), pstdev(b)
    pooled = (((len(a) - 1) * sa ** 2 + (len(b) - 1) * sb ** 2)
              / (len(a) + len(b) - 2)) ** 0.5
    return None if pooled == 0 else (fmean(a) - fmean(b)) / pooled


def main():
    series = load()
    print("decade: {0} symbols".format(len(series)), flush=True)
    base = production_report(series, conviction=conviction, dataset="decade",
                             purpose="diagnostic")
    lock = production_report(series, conviction=conviction, dataset="decade",
                             purpose="diagnostic", mr_lock_at_r=1.00)

    key = lambda t: (t.symbol, t.entry_time.date())
    b = {key(t): t for t in base.trades}
    l = {key(t): t for t in lock.trades}
    shared = set(b) & set(l)
    became_losers = sorted(k for k in shared
                           if b[k].net_pnl > 0 and l[k].net_pnl <= 0)
    others = sorted(k for k in shared if k not in set(became_losers))
    print("\nPOPULATION")
    print("  winner under baseline, loser under the lock : {0}".format(
        len(became_losers)))
    print("  all other shared trades                     : {0}".format(
        len(others)))

    market = market_context(series.get("SPY", []))
    rows = {key(t): r for t, r in
            zip(lock.trades, anatomise(lock.trades, series, market,
                                       CORRELATION_BUCKETS))}
    group_a = [rows[k] for k in became_losers if k in rows]
    group_b = [rows[k] for k in others if k in rows]
    print("  anatomised: {0} and {1}".format(len(group_a), len(group_b)))

    print("\nDESCRIPTIVE COMPARISON - NON-DECISION-MAKING")
    print("  {0:<24} {1:>10} {2:>10} {3:>9}".format(
        "permitted variable", "mean A", "mean B", "std diff"))
    out = {}
    for name in PERMITTED_ENTRY_TIME:
        a = [getattr(r, name) for r in group_a]
        bb = [getattr(r, name) for r in group_b]
        d = standardised_difference(a, bb)
        out[name] = {"mean_a": (fmean([v for v in a if v is not None])
                                if any(v is not None for v in a) else None),
                     "mean_b": (fmean([v for v in bb if v is not None])
                                if any(v is not None for v in bb) else None),
                     "std_diff": d, "n_a": len(a), "n_b": len(bb)}
        print("  {0:<24} {1:>10} {2:>10} {3:>9}".format(
            name,
            "-" if out[name]["mean_a"] is None else "{0:.4f}".format(out[name]["mean_a"]),
            "-" if out[name]["mean_b"] is None else "{0:.4f}".format(out[name]["mean_b"]),
            "-" if d is None else "{0:+.3f}".format(d)))

    print("\n  {0:<24} {1:>10} {2:>10}".format("flag (share true)", "A", "B"))
    for name in PERMITTED_FLAGS:
        a = [getattr(r, name) for r in group_a if getattr(r, name) is not None]
        bb = [getattr(r, name) for r in group_b if getattr(r, name) is not None]
        sa = sum(1 for v in a if v) / len(a) if a else None
        sb = sum(1 for v in bb if v) / len(bb) if bb else None
        out[name] = {"share_a": sa, "share_b": sb}
        print("  {0:<24} {1:>10} {2:>10}".format(
            name, "-" if sa is None else "{0:.1%}".format(sa),
            "-" if sb is None else "{0:.1%}".format(sb)))

    sectors = {}
    for r in group_a:
        sectors[r.sector] = sectors.get(r.sector, 0) + 1
    print("\n  sectors in group A: {0}".format(
        dict(sorted(sectors.items(), key=lambda kv: -kv[1]))))

    print("\n  NOT MEASURED (registered, but the simulator does not expose")
    print("  the arming moment; instrumenting it is a separate change):")
    for name in NOT_MEASURED:
        print("    - {0}".format(name))

    print("\n  STATUS: descriptive only. No feature was ranked or selected, "
          "no threshold chosen, no rule derived, and the H-0005 verdict "
          "(SPIKE, not accepted) was fixed before this ran.")

    path = REPO / "data" / "phase5" / "h0005-descriptive-27.json"
    path.write_text(json.dumps(
        {"n_group_a": len(group_a), "n_group_b": len(group_b),
         "variables": out, "sectors_group_a": sectors,
         "not_measured": NOT_MEASURED,
         "status": "descriptive only; cannot alter the H-0005 verdict"},
        indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(path.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
