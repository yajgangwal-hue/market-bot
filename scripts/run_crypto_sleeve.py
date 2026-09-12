"""Run one crypto-sleeve cycle against the paper account.

Holds BTC while BTC is above its own 100-day average, and nothing otherwise,
at 5% of total account equity. See event_aware_trader/crypto_sleeve.py for why
this is an allocation rather than a trading strategy, and why 5%.

Deliberately standalone. It does not import or touch the equity loop, and the
equity loop cannot see it either: `owns()` in autotrade.py returns False for
crypto on an equity cycle, so equity cycles ignore BTC entirely and this
ignores every stock. Two books, one account, no shared state.

Defaults to a DRY RUN. Pass --live to submit.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CASH_BUFFER = 25.0          # never spend the account to zero
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.broker import (                          # noqa: E402
    AlpacaPaperBroker, BrokerConfig)
from event_aware_trader.crypto_sleeve import (                   # noqa: E402
    SleeveConfig, plan, risk_on)
from event_aware_trader.data import fetch_alpaca_crypto_bars     # noqa: E402


def log(path, event, detail):
    record = {"at": datetime.now(timezone.utc).isoformat(),
              "event": event, "detail": detail}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")
    return record


def held_value(broker, symbol):
    for position in broker.positions():
        if str(position["symbol"]).upper() == symbol.upper():
            return float(position.get("market_value") or 0.0), \
                float(position["quantity"])
    return 0.0, 0.0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true",
                        help="submit orders; omit for a dry run")
    parser.add_argument("--fraction", type=float, default=0.05)
    parser.add_argument("--trend-days", type=int, default=100)
    parser.add_argument("--audit-log", default=str(REPO / "data" / "crypto-sleeve.jsonl"))
    args = parser.parse_args()

    config = SleeveConfig(fraction=args.fraction, trend_days=args.trend_days)
    audit = Path(args.audit_log)
    dry_run = not args.live

    # BOTH safety flags must be cleared to submit. `dry_run=False` alone is
    # not enough: the broker also refuses unless it was CONSTRUCTED with
    # allow_order_submission=True, and a bare AlpacaPaperBroker() defaults it
    # to False. With --live and a bare constructor every order came back
    # BLOCKED_ORDER_SUBMISSION_DISABLED - a silent no-op that looks like a
    # working cycle in the log.
    broker = AlpacaPaperBroker(
        BrokerConfig.from_environment(allow_order_submission=args.live))
    account = broker.account()
    equity = float(account["equity"])

    # Enough history for the average plus room to spare, so a few missing bars
    # never silently shorten the window and change the signal.
    bars = fetch_alpaca_crypto_bars(config.symbol,
                                    days=config.trend_days * 3)
    on = risk_on(bars, config)
    value, quantity = held_value(broker, config.symbol)
    # Cash, not buying power. Alpaca reports margin buying power on an equity
    # account and spending it is borrowing, which is not what a 5% allocation
    # is for. The sleeve takes what is genuinely free and tops up later.
    cash = float(account.get("cash", 0.0) or 0.0)
    # Never spend the last dollar. The first live cycle bought $700.63 against
    # $702.52 of cash and left the balance at -$0.23 - harmless at that size,
    # but a book that routinely runs the account to zero or below can accrue a
    # margin balance and can block an equity cycle that needs a few dollars to
    # act. The buffer is one minimum order, so the sleeve still converges.
    spendable = max(0.0, cash - CASH_BUFFER)
    decision = plan(equity, value, on, config,
                    available_cash=spendable)

    price = bars[-1].close if bars else 0.0
    print("cash   ${0:,.2f}".format(cash))
    print("equity ${0:,.2f}   {1} ${2:,.2f}   held ${3:,.2f} ({4})".format(
        equity, config.symbol, price, value, quantity))
    print("trend: {0}".format(
        "UNKNOWN - doing nothing" if on is None
        else ("above the {0}-day average".format(config.trend_days) if on
              else "below the {0}-day average".format(config.trend_days))))
    print("plan : {0}  target ${1:,.2f}  delta ${2:,.2f}  ({3})".format(
        decision["action"].upper(), decision["target"], decision["delta"],
        decision["reason"]))

    detail = dict(decision)
    detail.update({"equity": equity, "price": price, "held": value,
                   "quantity": quantity, "risk_on": on, "dry_run": dry_run})

    if decision["action"] == "hold":
        log(audit, "sleeve_hold", detail)
        return 0

    try:
        if decision["action"] == "buy":
            result = broker.submit_reviewed_candidate(
                config.symbol, decision["delta"] / price if price else 0.0,
                dry_run=dry_run)
        else:
            # Sell the shares that cover the delta, never more than is held.
            wanted = min(quantity, abs(decision["delta"]) / price if price else 0.0)
            result = broker.submit_sell(config.symbol, wanted, dry_run=dry_run)
        detail["result"] = result
        log(audit, "sleeve_" + decision["action"], detail)
        print("submitted: {0}".format(result.get("status")))
    except Exception as error:                      # broker or arithmetic
        detail["error"] = str(error)
        log(audit, "sleeve_FAILED", detail)
        print("FAILED: {0}".format(error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
