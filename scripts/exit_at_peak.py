"""Close named positions into intraday strength, at the top of the day's range.

Asked for by the account owner on 2026-09-14: close the losing positions, but
"when the bot thinks that it is at its daily peak" rather than at whatever
price happens to be showing. See event_aware_trader/peak_exit.py for the
judgement and its honest limits; this file is only the plumbing around it.

It is a DIRECTED tool, not a rule: it exits the symbols you name and nothing
else. Exiting losers early is the most destructive change ever measured on
this project (rescue exit, 09-11: win rate 53% -> 67%, CAGR 7.83% -> 6.41%),
so nothing in the bot calls this on its own.

Two things it reuses rather than reimplements, both deliberately:
  close_out   the SAME exit path run_once uses, which cancels the resting GTC
              stop first and waits for Alpaca to actually free the shares. A
              hand-rolled close here would hit the 403 that took a week to
              find the first time.
  the clock   the BROKER's, for the deadline, because it knows half-days.

Defaults to a DRY RUN. Pass --live to submit.

  python scripts/exit_at_peak.py --losers            # see what it would do
  python scripts/exit_at_peak.py --losers --live     # do it
  python scripts/exit_at_peak.py RTX VNQ LIN --live
"""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.autotrade import (                      # noqa: E402
    AutoTradeConfig, _minutes_to_close, close_out)
from event_aware_trader.broker import (                         # noqa: E402
    AlpacaPaperBroker, BrokerConfig, BrokerError)
from event_aware_trader.data import fetch_alpaca_equity_bars    # noqa: E402
from event_aware_trader.peak_exit import decide                 # noqa: E402

LOG = REPO / "data" / "peak-exit.log"


def say(message):
    line = "[{0}] {1}".format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message)
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def losing_equity_positions(broker):
    out = {}
    for position in broker.positions():
        symbol = str(position["symbol"]).upper()
        if position.get("asset_class") == "crypto" or "/" in symbol:
            continue                       # the sleeve is a different book
        pnl = float(position.get("unrealized_pnl") or 0.0)
        if pnl < 0:
            out[symbol] = pnl
    return out


def held(broker, symbol):
    for position in broker.positions():
        if str(position["symbol"]).upper() == symbol.upper():
            return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbols", nargs="*", help="positions to close")
    parser.add_argument("--losers", action="store_true",
                        help="every equity position currently showing a loss")
    parser.add_argument("--live", action="store_true",
                        help="submit orders; omit for a dry run")
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--tolerance", type=float, default=0.0015)
    parser.add_argument("--deadline-minutes", type=float, default=12.0)
    args = parser.parse_args()

    broker = AlpacaPaperBroker(
        BrokerConfig.from_environment(allow_order_submission=args.live))
    config = AutoTradeConfig(
        dry_run=not args.live,
        audit_log=REPO / "data" / "autotrade-audit.jsonl",
        state_file=REPO / "data" / "peak-exit-state.json")

    targets = [s.upper() for s in args.symbols]
    if args.losers:
        found = losing_equity_positions(broker)
        for symbol in sorted(found, key=lambda s: found[s]):
            if symbol not in targets:
                targets.append(symbol)
        say("losers right now: " + (", ".join(
            "{0} {1:,.2f}".format(s, found[s]) for s in found) or "none"))
    if not targets:
        say("nothing to do")
        return 0

    say("watching {0} for the day's peak (tolerance {1:.2%}, deadline {2:.0f} "
        "min before the close, {3})".format(
            ", ".join(targets), args.tolerance, args.deadline_minutes,
            "LIVE" if args.live else "dry run"))

    remaining = list(targets)
    while remaining:
        try:
            clock = broker.clock()
            left = _minutes_to_close(clock)
        except BrokerError as error:
            left = None
            say("clock unavailable ({0}); the deadline cannot fire this "
                "cycle".format(error))

        if left is not None and left <= 0:
            say("the session is closed; {0} still open. Re-run tomorrow."
                .format(", ".join(remaining)))
            return 1

        try:
            bars = fetch_alpaca_equity_bars(remaining, days=3, interval="5m",
                                            include_today=True)
        except Exception as error:                 # network, auth, rate limit
            say("bar fetch failed ({0}); retrying next cycle".format(error))
            time.sleep(args.poll_seconds)
            continue

        # Who is still actually held, asked ONCE per cycle. Without this the
        # loop only noticed a position had gone at the moment it decided to
        # sell it, so a position closed by hand - or by its own stop, or by
        # the equity loop's own rule - kept being reported as "waiting" for a
        # peak it no longer had any stake in. Harmless to the account, because
        # the close path checks again before submitting, but the log lied.
        try:
            open_symbols = {str(p["symbol"]).upper() for p in broker.positions()}
        except BrokerError as error:
            open_symbols = None            # unknown; fall through to the
            say("position lookup failed ({0}); assuming unchanged".format(error))

        session_date = datetime.now(timezone.utc).date()
        for symbol in list(remaining):
            if open_symbols is not None and symbol not in open_symbols:
                say("{0} is no longer held (closed elsewhere); dropping it"
                    .format(symbol))
                remaining.remove(symbol)
                continue
            series = bars.get(symbol) or []
            verdict = decide(series, session_date, minutes_to_close=left,
                             tolerance=args.tolerance,
                             deadline_minutes=args.deadline_minutes)
            say("{0:<6} {1:<5} {2}".format(symbol, verdict.action,
                                           verdict.reason))
            if not verdict.should_sell:
                continue
            if not held(broker, symbol):
                say("{0} is no longer held; dropping it".format(symbol))
                remaining.remove(symbol)
                continue

            actions = []
            result = close_out(config, broker, symbol, actions)
            for entry in actions:
                say("  {0}: {1}".format(entry["event"],
                                        str(entry["detail"])[:140]))
            status = (result or {}).get("status")
            say("  close {0} -> {1}".format(symbol, status))
            if args.live and held(broker, symbol):
                say("  STILL HELD after close_out; will retry next cycle")
            else:
                remaining.remove(symbol)

        if remaining:
            time.sleep(args.poll_seconds)

    say("done; every named position is closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
