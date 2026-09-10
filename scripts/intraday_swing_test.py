"""Can the bot sell the intraday peaks and buy the troughs, repeatedly?

The request came with a chart of the open RTX position: a day of large,
repeated up-and-down swings ending in a drop, and the observation that selling
near each top and buying near each bottom would have made money many times
over instead of losing $91.

Every one of those turns is obvious pointing at the chart afterwards. The only
question that matters is whether they are identifiable BEFORE they happen, on
information available at the time, after paying to trade them. This measures
that on real 15-minute bars across the whole universe.

WHY THE COSTS DECIDE IT. An intraday swing in a large-cap is a few tenths of a
percent. A round trip costs 12bps at the modelled 6bps a side. So a rule has
to capture more than 0.12% per swing NET, and the swings themselves are often
only two or three times that. This is not a small tax on the idea, it is the
central obstacle, so gross and net are reported separately - if the gross edge
is negative, no execution improvement can rescue it and the idea is dead
regardless of costs.

THE RULE TESTED is the most direct reading of the request: a short-horizon
RSI on intraday bars, buy when it is oversold, sell when it has recovered,
repeat, flat by the close. Thresholds and lookbacks are swept because the
request is about a shape of behaviour rather than a specific number, and a
single parameter choice failing would prove nothing about the shape.

Both halves are reported. A rule that only works in one half is the thing this
project has rejected all week.
"""
import json
import os
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from event_aware_trader.indicators import rsi
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto

EASTERN = ZoneInfo("America/New_York")
KEY = os.environ.get("APCA_API_KEY_ID", "").strip()
SECRET = os.environ.get("APCA_API_SECRET_KEY", "").strip()
HEADERS = {"APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SECRET}
START = "2024-01-01"
ONE_WAY = 0.0006
SPLIT = "2025-06-01"


def fetch(symbols):
    """Regular-hours 15-minute bars, batched, grouped per symbol per day."""
    as_api = {s.replace("-", "."): s for s in symbols}
    out = {s: defaultdict(list) for s in symbols}
    token = None
    while True:
        url = ("https://data.alpaca.markets/v2/stocks/bars?symbols={0}"
               "&timeframe=15Min&start={1}&limit=10000&adjustment=split".format(
                   urllib.parse.quote(",".join(as_api)), START))
        if token:
            url += "&page_token=" + urllib.parse.quote(token)
        payload = None
        for attempt in range(4):
            try:
                request = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(request, timeout=120) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except Exception:
                if attempt == 3:
                    return out
                time.sleep(2 * (attempt + 1))
        for api_symbol, rows in (payload.get("bars") or {}).items():
            symbol = as_api.get(api_symbol)
            if symbol is None:
                continue
            for row in rows:
                stamp = datetime.fromisoformat(row["t"].replace("Z", "+00:00"))
                local = stamp.astimezone(EASTERN)
                minutes = local.hour * 60 + local.minute
                # Regular hours only. Alpaca serves 04:00-20:00 by default and
                # pre-market prints would invent swings nobody could trade.
                if not (570 <= minutes < 960):
                    continue
                out[symbol][local.date()].append((minutes, float(row["c"])))
        token = payload.get("next_page_token")
        if not token:
            break
    return out


def trades_for(sessions, period, entry, exit_level):
    """Buy oversold, sell recovered, repeat, flat by the close."""
    out = []
    for day in sorted(sessions):
        bars = [close for _, close in sorted(sessions[day])]
        if len(bars) < period + 6:
            continue
        holding = None
        for i in range(period + 1, len(bars)):
            strength = rsi(bars[:i + 1], period)
            if strength is None:
                continue
            price = bars[i]
            if holding is None:
                if strength <= entry and i < len(bars) - 2:
                    holding = price
            else:
                last_bar = (i == len(bars) - 1)
                if strength >= exit_level or last_bar:
                    gross = price / holding - 1.0
                    out.append((day, gross, gross - 2 * ONE_WAY))
                    holding = None
    return out


def report(label, trades):
    if not trades:
        print("{0:<28}{1:>10}".format(label, "no trades"), flush=True)
        return
    gross = sum(t[1] for t in trades) / len(trades)
    net = sum(t[2] for t in trades) / len(trades)
    wins = sum(1 for t in trades if t[2] > 0)
    early = [t for t in trades if str(t[0]) < SPLIT]
    late = [t for t in trades if str(t[0]) >= SPLIT]
    first_net = sum(t[2] for t in early) / len(early) if early else 0.0
    last_net = sum(t[2] for t in late) / len(late) if late else 0.0
    print("{0:<28}{1:>9}{2:>11.4%}{3:>11.4%}{4:>10.4%}{5:>10.4%}{6:>8.0%}".format(
        label, len(trades), gross, net, first_net, last_net,
        wins / len(trades)), flush=True)


def main():
    universe = sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s))
    variants = [(7, 25, 65), (7, 30, 70), (14, 30, 70), (14, 25, 60),
                (14, 35, 65), (21, 30, 70)]
    collected = {v: [] for v in variants}

    batch = 15
    for i in range(0, len(universe), batch):
        chunk = universe[i:i + batch]
        for symbol, sessions in fetch(chunk).items():
            if not sessions:
                continue
            for variant in variants:
                collected[variant].extend(trades_for(sessions, *variant))
        print("  {0}/{1} symbols".format(min(i + batch, len(universe)),
                                         len(universe)), flush=True)
        time.sleep(0.2)

    print("\nIntraday swing trading, 15-minute bars, {0} onward".format(START),
          flush=True)
    print("Gross is BEFORE costs. If gross is negative the idea is dead "
          "however well it is executed.\n", flush=True)
    head = "{0:<28}{1:>9}{2:>11}{3:>11}{4:>10}{5:>10}{6:>8}".format(
        "rule", "trades", "gross/trd", "net/trd", "1st half", "2nd half", "win%")
    print(head, flush=True)
    print("-" * len(head), flush=True)
    for variant in variants:
        period, entry, exit_level = variant
        report("rsi{0} buy {1} sell {2}".format(period, entry, exit_level),
               collected[variant])


if __name__ == "__main__":
    main()
