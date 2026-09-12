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

CRYPTO IS WHY THIS CAN RUN TODAY. The equity market is shut at weekends, which
left this check waiting on Monday. Crypto never shuts, and it exercises the
same `close_out` the equity path uses - through a DIFFERENT protective order
type (Alpaca refuses a plain stop on crypto and accepts stop_limit), which
makes it a stronger test of the close path rather than a weaker one.

WHAT IT DOES, on the paper account, with a symbol chosen so it cannot collide
with anything the trading loop holds:

    1. buy a small position
    2. rest a protective stop on it, far from the market so it can never
       trigger - this reproduces the reserved-quantity condition
    3. try to close WITHOUT cancelling, and REQUIRE the refusal. If the close
       succeeds here the test proves nothing, because the blocking condition
       it exists to defeat was not present
    4. call `close_out` - the same function run_once calls - and require the
       position to be gone afterwards according to the broker

It cleans up after itself whatever happens: the finally block cancels any
order it left resting and closes any position it left open, and says so.

    python scripts/verify_sell_path.py                     rehearse, equities
    python scripts/verify_sell_path.py --crypto            rehearse, crypto
    python scripts/verify_sell_path.py --crypto --live     really trade
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from event_aware_trader.autotrade import AutoTradeConfig, close_out
from event_aware_trader.broker import AlpacaPaperBroker, BrokerConfig, BrokerError
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto

# Ford is liquid and deliberately NOT in DEFAULT_UNIVERSE, so the equity loop
# cannot collide with the test. ETH is in the universe but the crypto sleeve is
# not scheduled, so nothing else is trading it - and it carries the tightest
# spread of the ten pairs (2.4bps), which makes the test nearly free.
EQUITY_SYMBOL = "F"
CRYPTO_SYMBOL = "ETH/USD"
CRYPTO_NOTIONAL = 60.0


def crypto_ask(symbol):
    """Live ask for a crypto pair.

    The broker class has no price lookup - it is an order-submission surface -
    and `submit_notional_buy` deliberately refuses crypto, so the quantity has
    to be computed here. The ask, not the mid: this is about to cross the
    spread and the size should be honest about that.
    """
    import json
    import os
    import urllib.parse
    import urllib.request

    headers = {"APCA-API-KEY-ID": os.environ.get("APCA_API_KEY_ID", "").strip(),
               "APCA-API-SECRET-KEY": os.environ.get(
                   "APCA_API_SECRET_KEY", "").strip()}
    url = ("https://data.alpaca.markets/v1beta3/crypto/us/latest/quotes"
           "?symbols=" + urllib.parse.quote(symbol))
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    quote = (payload.get("quotes") or {}).get(symbol)
    if not quote or not quote.get("ap"):
        raise SystemExit("no live quote for {0}; aborting".format(symbol))
    return float(quote["ap"])


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
                        help="actually submit orders on the paper account")
    parser.add_argument("--crypto", action="store_true",
                        help="test on crypto, which is open at weekends")
    args = parser.parse_args()

    symbol = CRYPTO_SYMBOL if args.crypto else EQUITY_SYMBOL
    crypto = is_crypto(symbol)
    if not crypto and symbol in set(DEFAULT_UNIVERSE):
        raise SystemExit(
            "{0} is in the trading universe. Pick a symbol the bot does not "
            "trade, or this test can collide with a real position.".format(symbol))

    broker = AlpacaPaperBroker(
        BrokerConfig.from_environment(allow_order_submission=args.live))
    say("setup", "endpoint {0}".format(broker.config.endpoint))
    say("setup", "symbol {0} ({1})".format(
        symbol, "crypto, open 24/7" if crypto else "equity"))

    if not crypto:
        clock = broker.clock()
        if not clock.get("is_open"):
            raise SystemExit(
                "The equity market is closed (next open {0}). Re-run with "
                "--crypto to test now.".format(clock.get("next_open")))

    if not args.live:
        say("rehearsal", "--live not given. Nothing will be submitted.")
        return 0

    if any(p["symbol"] == symbol for p in broker.positions()):
        raise SystemExit(
            "There is already a {0} position. Refusing to touch it.".format(symbol))

    failures = []
    try:
        # ---- 1. buy ---------------------------------------------------------
        if crypto:
            # Size from the live quote. Crypto is fractional, so a small
            # notional is a real position rather than a rounding artefact.
            price = crypto_ask(symbol)
            quantity = round(CRYPTO_NOTIONAL / price, 6)
            say(1, "buying {0} {1} (~${2:.0f}) at about {3:,.2f}".format(
                quantity, symbol, CRYPTO_NOTIONAL, price))
        else:
            quantity = 1
            say(1, "buying 1 share of {0} at market".format(symbol))
        broker.submit_reviewed_candidate(symbol, quantity, dry_run=False)
        position = wait_for_position(broker, symbol)
        if position is None:
            raise SystemExit("the buy never appeared as a position; aborting")
        filled = float(position["average_entry_price"])
        held = float(position["quantity"])
        say(1, "filled {0} at {1:,.4f}".format(held, filled))

        # ---- 2. protect it --------------------------------------------------
        # Far below the market: this exists to RESERVE the quantity and must
        # never be able to trigger in the seconds it is alive.
        stop_price = round(filled * 0.5, 2)
        say(2, "resting a protective stop at {0:,.2f} to reserve the "
               "quantity".format(stop_price))
        broker.submit_protective_stop(symbol, held, stop_price, dry_run=False)
        for _ in range(30):
            if broker.open_sell_orders().get(symbol):
                break
            time.sleep(1.0)
        resting = broker.open_sell_orders().get(symbol, [])
        if not resting:
            raise SystemExit("the protective stop never appeared; aborting")
        say(2, "stop is resting: {0} ({1})".format(
            resting[0]["id"], resting[0]["type"]))

        # ---- 3. the blocking condition must actually be present -------------
        say(3, "closing WITHOUT cancelling - this must be refused")
        try:
            broker.close_position(symbol, dry_run=False)
        except BrokerError as error:
            if "insufficient qty" in str(error) or "403" in str(error):
                say(3, "refused as expected: {0}".format(str(error)[:100]))
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
        result = close_out(config, broker, symbol, actions)
        say(4, "result: {0}".format(result.get("status")))
        for entry in actions:
            say(4, "  {0}: {1}".format(entry["event"],
                                       str(entry["detail"])[:120]))

        # ---- 5. did it actually go? -----------------------------------------
        gone = False
        for _ in range(30):
            if not any(p["symbol"] == symbol for p in broker.positions()):
                gone = True
                break
            time.sleep(1.0)
        if not gone:
            failures.append("the position is STILL OPEN after close_out")
        else:
            say(5, "the broker reports the position is gone")

    finally:
        try:
            for order in broker.open_sell_orders().get(symbol, []):
                broker.cancel_order(order["id"], dry_run=False)
                say("cleanup", "cancelled leftover order " + order["id"])
            if any(p["symbol"] == symbol for p in broker.positions()):
                broker.close_position(symbol, dry_run=False)
                say("cleanup", "closed leftover {0} position".format(symbol))
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
