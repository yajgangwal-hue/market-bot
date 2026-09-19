"""FORENSIC_NON_PROMOTIONAL. Run both rules ONCE and persist the result.

READ-ONLY: no production file is edited, nothing is registered.

WHY THIS IS SEPARATE. The trend rule is roughly ten times heavier per
bar than mean reversion, and an earlier attempt did all the analysis in
the same process and persisted only at the end - so when the process
was killed, twenty minutes of compute went with it. The expensive part
now runs once and is written to disk immediately; every question is
then asked of the cache by a second script that takes seconds and can
be re-run freely.

THE DEFECT SHIM, restated where it is used. strategy.generate_candidate
detects `stop <= 0`, appends the blocker "Calculated stop is
non-positive", and then CONTINUES into
costs.round_trip_cost_per_share(entry, stop), which raises
ValueError("price must be positive"). The blocker is recorded and never
reached, so the trend rule cannot run on this universe at all. The shim
catches that raise and returns the REJECT the function was already
assembling; `src/` is NOT modified and every occurrence is counted.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.mean_reversion import conviction as shipped_conviction  # noqa: E402
from event_aware_trader.phase5.metrics import measure          # noqa: E402
from event_aware_trader.research import (                       # noqa: E402
    DATASET_USES, _record_gate_use, production_policy, production_report)
from event_aware_trader.risk import CostModel                   # noqa: E402
from event_aware_trader.strategy import CORRELATION_BUCKETS      # noqa: E402

from forensics_regime import load                                # noqa: E402

_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-400:], c)
_conv = {}
CACHE = REPO / "docs" / "phase5" / "copy-cache.json"
SHIM_HITS = {"n": 0}


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def _guarded(original):
    from event_aware_trader.strategy import _rejected

    def wrapped(symbol, bars, *args, **kwargs):
        try:
            return original(symbol, bars, *args, **kwargs)
        except ValueError as error:
            if "price must be positive" not in str(error):
                raise
            SHIM_HITS["n"] += 1
            return _rejected(symbol, bars[-1].timestamp,
                             CORRELATION_BUCKETS.get(symbol, "other"),
                             [], ["Calculated stop is non-positive"], {})
    return wrapped


def pack(report, label):
    return {
        "metrics": measure(report, label).as_dict(),
        "trades": [{"symbol": t.symbol,
                    "entry": t.entry_time.date().isoformat(),
                    "exit": t.exit_time.date().isoformat(),
                    "qty": t.quantity, "entry_price": t.entry_price,
                    "exit_price": t.exit_price, "net_pnl": t.net_pnl,
                    "reason": t.exit_reason, "bars_held": t.bars_held}
                   for t in report.trades],
        "equity": [[d.date().isoformat(), v] for d, v in report.equity_curve],
        "cash": [[d.date().isoformat(), v] for d, v in report.cash_curve],
        "rejected_for_capacity": report.rejected_for_capacity,
    }


def main():
    series = load()
    spy = series["SPY"]
    print("decade: {0} symbols, SPY {1} -> {2}".format(
        len(series), spy[0].timestamp.date(), spy[-1].timestamp.date()),
        flush=True)

    print("\n[1/2] MAIN (production, mean_reversion) ...", flush=True)
    main_rep = production_report(series, conviction=conviction,
                                 dataset="decade", purpose="diagnostic")
    main_packed = pack(main_rep, "MAIN")
    m = main_packed["metrics"]
    print("  {0:+.10%} over {1} trades".format(m["total_return"], m["trades"]))
    ok = abs(m["total_return"] - 0.585889) <= 5e-7 and m["trades"] == 698
    print("  BASELINE EQUIVALENCE: {0}".format("PASS" if ok else "FAIL"))
    if not ok:
        print("  STOPPED: baseline did not reproduce. Nothing cached.")
        return 2

    print("\n[2/2] TREND (the copy source) - this is the slow one ...",
          flush=True)
    _record_gate_use("decade", "diagnostic", len(series), DATASET_USES)
    original = portfolio_module.generate_candidate
    portfolio_module.generate_candidate = _guarded(original)
    try:
        trend_rep = portfolio_module.run_portfolio(
            series, starting_cash=100_000.0, policy=production_policy(),
            costs=CostModel(), conviction=conviction, entry_rule="trend")
    finally:
        portfolio_module.generate_candidate = original
    trend_packed = pack(trend_rep, "TREND")
    t = trend_packed["metrics"]
    print("  {0:+.4%} over {1} trades".format(t["total_return"], t["trades"]))
    print("  defect shim fired {0} times".format(SHIM_HITS["n"]))

    spy_total = spy[-1].close / spy[0].close - 1.0
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({
        "FORENSIC_NON_PROMOTIONAL": True,
        "baseline_equivalence": ok,
        "spy_total": spy_total,
        "shim_hits": SHIM_HITS["n"],
        "main": main_packed, "trend": trend_packed,
    }, separators=(",", ":"), default=str), encoding="utf-8")
    print("\nwrote {0} ({1:,} bytes)".format(
        CACHE.relative_to(REPO), CACHE.stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
