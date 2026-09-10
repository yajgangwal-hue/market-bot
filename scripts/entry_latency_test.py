"""Does entering LATER in the session cost money on the bot's signal days?

The claim: the bot is good at finding the big moves and bad at acting on them,
arriving after the move is done.

There is a concrete mechanism behind that, and it is not a metaphor. The
BACKTEST fills every entry at the OPEN of the next session. The LIVE bot fills
whenever its cycle happens to run - and today's entries printed at 14:26 UTC,
which is 10:26 New York, nearly an hour after the bell. Yesterday's were later
still. If a signal day's move happens early, the backtest banks it and the
live account pays up for it, and every measured return in this project would
be describing a fill nobody actually gets.

So this measures the intraday path of the bot's OWN signal days: the return
from the 09:30 open to each later point in the session. If it drifts up, every
minute of delay is a real cost and the fix is to enter earlier. If it drifts
down, the delay is quietly buying a discount and the current behaviour is
better than the backtest assumes.

Signal days come from the daily files using the shipped rule. Intraday paths
come from Alpaca 15-minute bars, regular hours only. A control - the same
measurement on ALL days rather than signal days - separates "this is what
oversold stocks do" from "this is what every stock does".
"""
import json
import os
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from event_aware_trader.data import load_bars
from event_aware_trader.indicators import rsi, wilder_atr
from event_aware_trader.mean_reversion import MeanReversionConfig
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto

EASTERN = ZoneInfo("America/New_York")
DEEP = Path(__file__).with_name("deep")
CONFIG = MeanReversionConfig()
KEY = os.environ.get("APCA_API_KEY_ID", "").strip()
SECRET = os.environ.get("APCA_API_SECRET_KEY", "").strip()
HEADERS = {"APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SECRET}
START = "2025-01-01"
WINDOW = 400
# Minutes from midnight, New York. 570 = 09:30.
CHECKPOINTS = [(585, "+15m"), (600, "+30m"), (630, "+1h"), (690, "+2h"),
               (750, "+3h"), (810, "+4h"), (955, "close")]


def signal_days():
    """Dates the shipped rule fires, per symbol, from the daily files."""
    out = defaultdict(set)
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        path = DEEP / (symbol + ".csv")
        if not path.exists():
            continue
        bars = load_bars(path)
        if len(bars) < 500:
            continue
        closes = [b.close for b in bars]
        for i in range(CONFIG.minimum_history, len(bars) - 1):
            if bars[i].timestamp.date().isoformat() < START:
                continue
            lo = max(0, i - WINDOW + 1)
            strength = rsi(closes[lo:i + 1], CONFIG.rsi_period)
            if strength is None or strength > CONFIG.rsi_entry:
                continue
            atr = wilder_atr(bars[lo:i + 1], CONFIG.atr_days)
            close = closes[i]
            if not atr or close <= 0 or close < CONFIG.min_price:
                continue
            if CONFIG.max_atr_fraction and atr / close > CONFIG.max_atr_fraction:
                continue
            # The rule fires on bar i, so the bot trades the NEXT session.
            out[symbol].add(bars[i + 1].timestamp.date())
    return out


def fetch(symbols):
    as_api = {s.replace("-", "."): s for s in symbols}
    out = {s: defaultdict(dict) for s in symbols}
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
                if not (570 <= minutes < 960):
                    continue
                out[symbol][local.date()][minutes] = (float(row["o"]),
                                                      float(row["c"]))
        token = payload.get("next_page_token")
        if not token:
            break
    return out


def path_for(session):
    """Return from the 09:30 OPEN to each checkpoint, or None."""
    if 570 not in session:
        return None
    open_price = session[570][0]
    if open_price <= 0:
        return None
    out = []
    for minutes, _ in CHECKPOINTS:
        candidates = [m for m in session if m <= minutes]
        if not candidates:
            out.append(None)
            continue
        price = session[max(candidates)][1]
        out.append(price / open_price - 1.0 if price > 0 else None)
    return out


def main():
    print("finding signal days from the daily files...", flush=True)
    wanted = signal_days()
    total = sum(len(v) for v in wanted.values())
    print("{0} signal days across {1} symbols\n".format(total, len(wanted)),
          flush=True)

    on_signal = [[] for _ in CHECKPOINTS]
    all_days = [[] for _ in CHECKPOINTS]
    symbols = sorted(wanted)
    batch = 15
    for i in range(0, len(symbols), batch):
        chunk = symbols[i:i + batch]
        for symbol, sessions in fetch(chunk).items():
            days = wanted.get(symbol, set())
            for day, session in sessions.items():
                path = path_for(session)
                if path is None:
                    continue
                target = on_signal if day in days else None
                for k, value in enumerate(path):
                    if value is None:
                        continue
                    all_days[k].append(value)
                    if target is not None:
                        target[k].append(value)
        print("  {0}/{1}".format(min(i + batch, len(symbols)), len(symbols)),
              flush=True)
        time.sleep(0.2)

    print("\nReturn from the 09:30 OPEN, averaged.", flush=True)
    print("Positive means the price rose after the open - so waiting COSTS.\n",
          flush=True)
    head = "{0:<10}{1:>12}{2:>10}{3:>14}{4:>10}".format(
        "point", "signal days", "n", "all days", "n")
    print(head, flush=True)
    print("-" * len(head), flush=True)
    for k, (_, label) in enumerate(CHECKPOINTS):
        sig = on_signal[k]
        every = all_days[k]
        print("{0:<10}{1:>12}{2:>10}{3:>14}{4:>10}".format(
            label,
            "{0:+.4%}".format(sum(sig) / len(sig)) if sig else "-", len(sig),
            "{0:+.4%}".format(sum(every) / len(every)) if every else "-",
            len(every)), flush=True)


if __name__ == "__main__":
    main()
