"""Pre-OOS diagnostic: is the 15m -> 1d runner change economically inert?

READ-ONLY. No order, no state file, no observation, no registration.

WHAT IS BEING COMPARED. run_once reads the cycle's bar fetch
(`bars_by_symbol`) at three places under mean reversion, and at all
three only its PRESENCE and LENGTH matter:

    autotrade.py:1394  position management  `if not bars: continue`
    autotrade.py:1705  entry gate           `len(bars) < strategy.minimum_history`
    autotrade.py:1823  order placement      `if not bars: continue`

Every number the rule uses comes from daily_bars() or from
_todays_bars(), which makes its own interval="1d" call. So the only
way the runner change can alter behaviour is by flipping one of those
three gates.

This script measures the gates under both configurations and then
evaluates the FROZEN signal on the daily series, so any candidate-set
difference is attributable to the gate and to nothing else.

Nothing here is a strategy test and nothing here may be quoted as one.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.autotrade import daily_bars, _todays_bars, _with_today  # noqa: E402
from event_aware_trader.data import fetch_alpaca_equity_bars          # noqa: E402
from event_aware_trader.mean_reversion import (                       # noqa: E402
    MeanReversionConfig, evaluate)
from event_aware_trader.strategy import (                             # noqa: E402
    DEFAULT_UNIVERSE, StrategyConfig, is_crypto)

# Exactly the mapping run_once uses: autotrade.py:1358
PERIOD_DAYS = {"1mo": 35, "2mo": 65, "3mo": 95, "6mo": 190,
               "1y": 370, "2y": 760}
BEFORE = ("15m", "1mo")
AFTER = ("1d", "2y")
MR = MeanReversionConfig()


class _Cfg:
    """Minimal stand-in so _todays_bars can log without a real config."""
    audit_log = None
    dry_run = True


def gate_counts(symbols, interval, period):
    days = PERIOD_DAYS[period]
    got = fetch_alpaca_equity_bars(symbols, days=days, interval=interval)
    return {s: len(got.get(s, [])) for s in symbols}


def main():
    equities = sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s))
    print("universe: {0} equities".format(len(equities)))
    print("BEFORE interval={0} period={1} -> days={2}".format(
        BEFORE[0], BEFORE[1], PERIOD_DAYS[BEFORE[1]]))
    print("AFTER  interval={0} period={1} -> days={2}".format(
        AFTER[0], AFTER[1], PERIOD_DAYS[AFTER[1]]))

    s_before = StrategyConfig.for_interval(BEFORE[0])
    s_after = StrategyConfig.for_interval(AFTER[0])
    print("minimum_history: before {0} | after {1}".format(
        s_before.minimum_history, s_after.minimum_history))

    print("\nfetching AFTER (1d/2y) ...", flush=True)
    n_after = gate_counts(equities, *AFTER)
    print("fetching BEFORE (15m/1mo) ...", flush=True)
    n_before = gate_counts(equities, *BEFORE)

    # ---- the frozen signal, identical in both worlds -------------------
    print("\nevaluating the frozen signal on daily bars ...", flush=True)
    todays = _todays_bars(_Cfg(), equities)
    buys, no_history = set(), 0
    for symbol in equities:
        series = daily_bars(symbol)
        if not series:
            continue
        series = _with_today(series, todays.get(symbol))
        if len(series) < MR.minimum_history:
            no_history += 1
            continue
        if evaluate(symbol, series, MR).is_buy:
            buys.add(symbol)

    g_before = {s for s in equities
                if n_before.get(s, 0) >= s_before.minimum_history}
    g_after = {s for s in equities
               if n_after.get(s, 0) >= s_after.minimum_history}

    cand_before = buys & g_before
    cand_after = buys & g_after

    print("\n--- GATE ---")
    print("  symbols passing BEFORE gate : {0}/{1}".format(
        len(g_before), len(equities)))
    print("  symbols passing AFTER  gate : {0}/{1}".format(
        len(g_after), len(equities)))
    fail_before = sorted(set(equities) - g_before)
    fail_after = sorted(set(equities) - g_after)
    print("  fail BEFORE : {0}{1}".format(
        len(fail_before), " " + str(fail_before[:12]) if fail_before else ""))
    print("  fail AFTER  : {0}{1}".format(
        len(fail_after), " " + str(fail_after[:12]) if fail_after else ""))

    flipped = sorted(g_before ^ g_after)
    print("\n  symbols whose GATE differs: {0}".format(len(flipped)))
    for s in flipped[:25]:
        print("    {0:<7} 15m_bars={1:<7} 1d_bars={2:<5} daily_history={3} "
              "would_buy={4}".format(
                  s, n_before.get(s, 0), n_after.get(s, 0),
                  len(daily_bars(s)), s in buys))

    print("\n--- FROZEN SIGNAL ---")
    print("  symbols with < {0} daily bars (rule cannot fire): {1}".format(
        MR.minimum_history, no_history))
    print("  BUY signals today (gate-independent): {0}  {1}".format(
        len(buys), sorted(buys)[:15]))

    print("\n--- CANDIDATE SET ---")
    print("  BEFORE (15m/1mo): {0}  {1}".format(
        len(cand_before), sorted(cand_before)[:15]))
    print("  AFTER  (1d/2y)  : {0}  {1}".format(
        len(cand_after), sorted(cand_after)[:15]))
    lost = sorted(cand_before - cand_after)
    gained = sorted(cand_after - cand_before)
    print("  DISAPPEAR : {0}  {1}".format(len(lost), lost))
    print("  APPEAR    : {0}  {1}".format(len(gained), gained))

    for s in lost:
        print("    lost {0}: 1d_bars={1} (< {2}) -> insufficient history"
              .format(s, n_after.get(s, 0), s_after.minimum_history))

    print("\n--- VERDICT ---")
    if not lost and not gained:
        print("  Candidate sets are IDENTICAL. The gate difference does not "
              "reach the frozen signal today.")
    else:
        print("  CANDIDATE SET DIFFERS. Do not change the runner; report.")
    print("\n  NOTE: this is one session's snapshot of the gate, not a "
          "backtest. The structural argument is that the gate needs "
          "{0} bars while the rule needs {1}.".format(
              s_after.minimum_history, MR.minimum_history))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
