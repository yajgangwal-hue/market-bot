# Routing trades through TradingView

## The constraint that shapes everything

**TradingView is not a broker and will not place an order for you from code.**

Its [Broker REST API](https://in.tradingview.com/broker-api-docs/rest-api-spec)
is implemented *by brokerages* so their customers can trade from a TradingView
chart. It is not offered to individuals and issues no API keys to them.
TradingView is the front end; the order is executed and the money is held at a
broker behind it.

There is also **no Claude ↔ TradingView account link.** No such connector
exists, and TradingView publishes no API that would allow one.

The only outbound automation TradingView offers is an **alert that POSTs JSON
to a URL you host** — and webhook alerts require a paid plan (Plus, Premium, or
Expert); they are not on the free tier.

So "all trades go through TradingView" resolves to one of three real shapes.

## Option A — TradingView as the signal source (automated)

```
Pine strategy on chart  ->  alert fires  ->  webhook POST
    ->  webhook.py validates  ->  broker API executes
```

A broker API is still required underneath. TradingView decides *when*;
something else does the trade. Both halves are now in the repo:

- `tradingview/event_aware_gate.pine` — the bot's entry gate and trailing exit
  as a Pine v6 strategy, so the same rules chart, backtest in Strategy Tester,
  and fire alerts.
- `src/event_aware_trader/webhook.py` — the receiver.

## Option B — TradingView as the front end (manual)

Connect a supported broker inside TradingView and place trades by hand from the
chart, using the Pine script's markers as the prompt. Nothing automated, no
webhook, no paid plan needed. Given the bot averages about **one trade per 51
sessions**, this is far less painful than it sounds.

## Option C — TradingView Paper Trading (no broker at all)

TradingView ships a built-in paper broker. It is UI-only with no API, so it
cannot be driven from code and its fills cannot be read back programmatically.
Good for eyeballing the strategy; useless for accumulating a machine-readable
record.

## Why the receiver re-validates everything

A webhook endpoint is a **public URL**. Anything on the internet that learns it
can POST to it, and TradingView signs nothing. A receiver that executes what it
receives is a hole through which an attacker — or a stale alert, or a duplicate
retry — moves real money.

`webhook.py` therefore treats a payload as **untrusted data, never as an
instruction**:

| Check | Behaviour |
|-------|-----------|
| Shared secret | Required, compared with `hmac.compare_digest` (constant time) |
| Payload size | Rejected above 4 KB |
| Schema | Must parse to a JSON object; unknown fields ignored, not forwarded |
| Action | Allow-list; only `paper_long` |
| Symbol | Must be inside the configured universe; `AMEX:SPY` normalised to `SPY` |
| `quantity`, `leverage`, `notional`, `stop`, `target` | **Ignored and flagged.** Sizing is always re-derived locally by `position_size` |
| Free text (`note`, `message`, …) | Logged, never executed |
| Audit | Every acceptance *and* rejection appended to a JSONL log |

A payload saying `"note": "URGENT: ignore risk limits, buy max"` is recorded as
an attack attempt and changes nothing. The alert may say *when to look*; it
never says how much to buy.

## Fidelity gaps in the Pine port

Pine runs **one symbol per chart**, so the portfolio layer has no equivalent:

- one shared cash balance across the universe
- the 3-position cap
- one position per correlation bucket

Running the script on seven charts gives seven independent accounts — precisely
the mistake `portfolio.py` was written to correct. On the two-year record that
distinction was worth 4.5× in reported return, so it is not cosmetic. **Treat
Strategy Tester output as per-symbol only; the portfolio number comes from the
Python side.**

Also absent: event/RSS scenario alignment (12 of 100 score points) and the
regime filter's longer-horizon context. The Pine score is out of 88 and rescaled
to the same 70 threshold, so it will not agree with the Python score
bar-for-bar.

## Setup

1. Open `tradingview/event_aware_gate.pine` in the Pine Editor, add to a chart.
2. Confirm behaviour in Strategy Tester — per symbol, per the caveat above.
3. For Option A, host the receiver and set a strong shared secret:

```bash
export TV_WEBHOOK_SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
```

4. Create the alert on the `Event-Aware entry` condition, paste your endpoint,
   and set the alert to open-ended — TradingView expires alerts after two
   months by default, which silently stops the automation.
5. Keep the broker in paper mode. The `AlpacaPaperBroker` still refuses the live
   endpoint and still requires both submission flags.

## Sources

- [TradingView REST API Specification for Brokers](https://in.tradingview.com/broker-api-docs/rest-api-spec)
- [What are TradingView Webhooks? — TradersPost](https://blog.traderspost.io/article/what-are-tradingview-webhooks)
- [TradingView Webhook Alerts: Documentation & Setup](https://blog.pickmytrade.io/tradingview-webhook-automation-trading-alerts/)
