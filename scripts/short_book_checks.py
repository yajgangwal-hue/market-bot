"""Accounting checks on the short book before any result from it is believed.

Short accounting inverts almost everything - the stop is above, the exit
compares the high, profit is entry minus exit - and an error in it would
silently invent or destroy money every bar rather than crash. So the engine is
asked questions whose answers are known before it is asked anything useful.
"""
import sys
from datetime import datetime, timedelta

from event_aware_trader.types import Bar

import shortbook


def bars(closes, start=datetime(2020, 1, 1)):
    return [Bar(timestamp=start + timedelta(days=i), open=c, high=c * 1.005,
                low=c * 0.995, close=c, volume=9_000_000.0)
            for i, c in enumerate(closes)]


failures = []


def check(label, condition, detail=""):
    print("  {0:<52} {1}{2}".format(
        label, "OK" if condition else "FAIL", "  " + detail if detail else ""),
        flush=True)
    if not condition:
        failures.append(label)


print("short-book accounting checks\n", flush=True)

# 1. A flat market produces no signal and must not move equity at all.
flat = shortbook.run_short_book({"AAA": bars([100.0] * 300)},
                                starting_cash=100_000.0)
check("flat market: no trades", len(flat.trades) == 0)
check("flat market: equity unchanged", abs(flat.equity - 100_000.0) < 1e-6,
      "equity={0!r}".format(flat.equity))

# 2. A long steady DECLINE with a sharp rally into it is the setup: below the
#    200-day, RSI high. The short should trigger and should PROFIT as the
#    decline resumes.
decline = [300.0 - i * 0.5 for i in range(260)]      # 300 -> 170, below its MA
rally = [decline[-1] * (1.0 + 0.02 * (i + 1)) for i in range(9)]   # sharp pop
resume = [rally[-1] * (1.0 - 0.01 * (i + 1)) for i in range(30)]   # falls again
report = shortbook.run_short_book({"AAA": bars(decline + rally + resume)},
                                  starting_cash=100_000.0)
check("downtrend + rally: a short is taken", len(report.trades) >= 1,
      "trades={0}".format(len(report.trades)))
if report.trades:
    # Aggregate, not trades[0]. The first version of this check asserted on the
    # first trade and failed - correctly, because the rally ran past the stop
    # before the decline resumed, so trade one was a stop-out. The engine was
    # right and the assertion was wrong. What must hold is that the BOOK
    # profits on a fixture that declines, not that every trade in it does; a
    # rule with a 50% win rate is not obliged to win first.
    total = sum(t["net"] for t in report.trades)
    winners = [t for t in report.trades if t["net"] > 0]
    check("the book profits over a resuming decline", total > 0,
          "total=${0:,.2f} over {1} trades".format(total, len(report.trades)))
    check("at least one short closes below its entry",
          any(t["exit"] < t["entry"] for t in report.trades),
          "{0} of {1} did".format(len(winners), len(report.trades)))
    check("equity rose with it", report.equity > 100_000.0,
          "equity=${0:,.2f}".format(report.equity))

# 3. The mirror image: a rally that keeps going must LOSE, and must be stopped
#    out rather than left to run.
keeps_rising = [rally[-1] * (1.0 + 0.02 * (i + 1)) for i in range(30)]
losing = shortbook.run_short_book({"AAA": bars(decline + rally + keeps_rising)},
                                  starting_cash=100_000.0)
if losing.trades:
    trade = losing.trades[0]
    check("a short against a continuing rally loses", trade["net"] < 0,
          "net=${0:,.2f}".format(trade["net"]))
    check("and it is closed by the stop", trade["reason"] == "stop",
          "reason={0}".format(trade["reason"]))
    check("the stop is ABOVE the entry", trade["exit"] > trade["entry"],
          "entry={0:.2f} exit={1:.2f}".format(trade["entry"], trade["exit"]))
else:
    check("a short against a continuing rally loses", False, "no trade taken")

# 4. No position may exceed the risk budget by more than the cap allows.
if report.trades:
    check("loss on a stopped trade is bounded by the risk budget",
          all(t["net"] > -0.05 * 100_000.0 for t in losing.trades),
          "worst=${0:,.2f}".format(min(t["net"] for t in losing.trades)))

print("\n{0}".format("ALL CHECKS PASSED" if not failures
                     else "FAILED: " + ", ".join(failures)), flush=True)
sys.exit(1 if failures else 0)
