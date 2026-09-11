"""Prove, against the real broker, that the bot can sell a PROTECTED position.

WHY THIS EXISTS. Every successful sell in this account's history happened
before protective stops did:

    09-01  entry WMT -> 09-01 exit WMT      no protective stop existed yet
    09-01  entry XOP -> 09-02 exit XOP      no protective stop existed yet
    09-01  entry DBC -> 09-02 exit DBC      no protective stop existed yet
    09-04  first protective_stop_placed (INTC, then EWY)
    09-08  EWY tries to exit -> 403, 403, 404. Its own stop took it out.

So the rule has never once closed a position in the configuration the bot
actually runs in - every live position is protected - and two defects explain
it: the exit path did not cancel at all until 2026-09-08, and the cancel it
was then given was issued as a dry run because `cancel_order` defaults to
dry_run=True and the flag was not passed. Both are fixed. Neither fix has been
observed working against Alpaca.

Unit tests cannot settle that. The broker double was more permissive than the
real broker twice already - it accepted fractional protective stops the real
one refuses, and it freed reserved shares on a dry-run cancel - and each time
the suite certified a path that could not work live. Only the real API settles
it.

WHAT IT DOES, on the paper account, using a symbol OUTSIDE the trading
universe so the bot cannot interact with the test:

    1. buy 1 share at market
    2. rest a GTC protective stop on it, far below the market so it can never
       trigger - this reproduces the exact reserved-shares condition
    3. try to close WITHOUT cancelling, and REQUIRE the 403. If the close
       succeeds here the test proves nothing, because the blocking condition
       it exists to defeat was not present
    4. call `close_out` - the same function run_once calls - and require the
       position to be gone afterwards according to the broker

It cleans up after itself whatever happens: the finally block cancels any
order it left resting and closes any position it left open, and it says so.

    python scripts/verify_sell_path.py            rehearse, submits nothing
    python scripts/verify_sell_path.py --live     really trade 1 share
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from event_aware_trader.autotrade import AutoTradeConfig, close_out
from event_aware_trader.broker import AlpacaPaperBroker, BrokerConfig, BrokerError
from event_aware_trader.strategy import DEFAULT_UNIVERSE

# Liquid, cheap, and deliberately NOT in DEFAULT_UNIVERSE, so the trading loop
# will never look at it and this test can never collide with a real position.
SYMBOL = "F"
QUANTITY = 1


def say(step, message):
    print("[{0}] {1}".format(step, message), flush=True)


def wait_for_position(broker, symbol, timeout=60):
    """Alpaca fills and reports asynchronously; poll rather than assume."""
    for _ in range(timeout):
        for position in broker.positions():
            if position["symbol"] == symbol:
                return position
        time.sleep(1.0)
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true",
                        help="actually submit orders (1 share, paper account)")
    args = parser.parse_args()

    if SYMBOL in set(DEFAULT_UNIVERSE):
        raise SystemExit(
            "{0} is in the trading universe. Pick a symbol the bot does not "
            "trade, or this test can collide with a real position.".format(SYMBOL))

    broker = AlpacaPaperBroker(
        BrokerConfig.from_environment(allow_order_submission=args.live))
    say("setup", "endpoint {0}".format(broker.config.endpoint))

    clock = broker.clock()
    if not clock.get("is_open"):
        raise SystemExit(
            "The market is closed (next open {0}). A market order sent now "
            "queues to the next open and this test would measure nothing."
            .format(clock.get("next_open")))

    if not args.live:
        say("rehearsal", "--live not given. Nothing will be submitted.")
        say("rehearsal", "would buy {0} x {1}, rest a stop, prove the 403, "
                         "then close_out".format(QUANTITY, SYMBOL))
        return 0

    existing = [p for p in broker.positions() if p["symbol"] == SYMBOL]
    if existing:
        raise SystemExit(
            "There is already a {0} position. Refusing to touch it.".format(SYMBOL))

    failures = []
    placed_stop = None
    try:
        # ---- 1. buy ---------------------------------------------------------
        say(1, "buying {0} share(s) of {1} at market".format(QUANTITY, SYMBOL))
        broker.submit_reviewed_candidate(SYMBOL, QUANTITY, dry_run=False)
        position = wait_for_position(broker, SYMBOL)
        if position is None:
            raise SystemExit("the buy never appeared as a position; aborting")
        price = float(position["average_entry_price"])
        say(1, "filled at {0:.2f}".format(price))

        # ---- 2. protect it --------------------------------------------------
        # Far below the market: this must never be able to trigger during the
        # seconds it exists. It is here to RESERVE the shares, nothing else.
        stop_price = round(price * 0.5, 2)
        say(2, "resting a GTC stop at {0:.2f} to reserve the shares".format(
            stop_price))
        placed = broker.submit_protective_stop(
            SYMBOL, QUANTITY, stop_price, dry_run=False)
        placed_stop = placed.get("id")
        for _ in range(30):
            if broker.open_sell_orders().get(SYMBOL):
                break
            time.sleep(1.0)
        resting = broker.open_sell_orders().get(SYMBOL, [])
        if not resting:
            raise SystemExit("the protective stop never appeared; aborting")
        say(2, "stop is resting: {0}".format(resting[0]["id"]))

        # ---- 3. the blocking condition must actually be present -------------
        say(3, "closing WITHOUT cancelling - this must be refused")
        try:
            broker.close_position(SYMBOL, dry_run=False)
        except BrokerError as error:
            if "insufficient qty" in str(error) or "403" in str(error):
                say(3, "refused as expected: {0}".format(str(error)[:90]))
            else:
                failures.append("close failed for the wrong reason: " + str(error))
        else:
            failures.append(
                "the close SUCCEEDED while the stop was resting. The condition "
                "this whole path exists to defeat was not present, so step 4 "
                "proves nothing.")

        # ---- 4. the production path -----------------------------------------
        say(4, "calling close_out - the same function run_once calls")
        config = AutoTradeConfig(
            dry_run=False,
            audit_log=Path("data/verify-sell-path.jsonl"),
            state_file=Path("data/verify-sell-path-state.json"))
        actions = []
        result = close_out(config, broker, SYMBOL, actions)
        say(4, "result: {0}".format(result.get("status")))
        for entry in actions:
            say(4, "  {0}: {1}".format(entry["event"],
                                       str(entry["detail"])[:110]))

        # ---- 5. did it actually go? -----------------------------------------
        gone = None
        for _ in range(30):
            if not any(p["symbol"] == SYMBOL for p in broker.positions()):
                gone = True
                break
            time.sleep(1.0)
        if not gone:
            failures.append("the position is STILL OPEN after close_out")
        else:
            placed_stop = None
            say(5, "the broker reports the position is gone")

    finally:
        # Leave nothing behind, whatever happened above.
        try:
            for order in broker.open_sell_orders().get(SYMBOL, []):
                broker.cancel_order(order["id"], dry_run=False)
                say("cleanup", "cancelled leftover order " + order["id"])
            if any(p["symbol"] == SYMBOL for p in broker.positions()):
                broker.close_position(SYMBOL, dry_run=False)
                say("cleanup", "closed leftover {0} position".format(SYMBOL))
        except BrokerError as error:
            say("cleanup", "FAILED, CHECK THE ACCOUNT BY HAND: {0}".format(error))

    print()
    if failures:
        print("VERDICT: THE BOT CANNOT SELL A PROTECTED POSITION")
        for note in failures:
            print("   - {0}".format(note))
        return 1
    print("VERDICT: the bot CAN sell a protected position.")
    print("   The stop was really cancelled and the close was really accepted,")
    print("   through the same close_out that run_once calls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
