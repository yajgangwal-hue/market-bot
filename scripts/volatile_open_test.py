"""Does a volatile open predict the rest of the session going DOWN?

The claim, from four charts of held positions: the session opens with a
violent spike, then the stock slides for the rest of the day, so shorting into
that spike would pay.

This is close to two things already tested and identical to neither, which is
why it gets its own measurement:

  * the opening-range breakout test measured BREAKOUTS from the opening range
    and bucketed by relative volume - it found -0.18% a trade before costs and
    an INVERTED gradient, the highest-volume names being worst.
  * the intraday swing test measured RSI reversals through the session - zero
    gross edge over 192,000 trades.

Neither asked the direct question: given a violent open, what does the REST OF
THE SESSION do? That is a volatility-to-direction relationship, and if it
exists it is tradable by shorting at the end of the opening range.

MEASURED, per symbol per session, regular hours only:

    opening volatility   the first 30 minutes' high-low range as a share of
                         the open, and separately the opening volume against
                         that symbol's own 20-session average
    forward return       from the 30-minute mark to the close

Bucketed into quintiles by each measure. The claim predicts the most violent
opens produce the most negative forward returns - a GRADIENT. A flat or
inverted pattern means the volatility carries no directional information, and
one odd bucket means noise.

Costs are shown separately: shorting from the 30-minute mark to the close is
one round trip, 12bps at the modelled 6bps a side. Any edge has to clear that
before it is worth anything.
"""
import json
import os
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto

EASTERN = ZoneInfo("America/New_York")
KEY = os.environ.get("APCA_API_KEY_ID", "").strip()
SECRET = os.environ.get("APCA_API_SECRET_KEY", "").strip()
HEADERS = {"APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SECRET}
START = "2024-01-01"
ONE_WAY = 0.0006
SPLIT = "2025-06-01"


def fetch(symbols):
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
                if not (570 <= minutes < 960):
                    continue
                out[symbol][local.date()].append((minutes, row))
        token = payload.get("next_page_token")
        if not token:
            break
    return out


def sessions_for(sessions):
    """(date, opening range %, opening volume, forward return to the close)."""
    out = []
    history = []
    for day in sorted(sessions):
        bars = sorted(sessions[day], key=lambda pair: pair[0])
        if len(bars) < 20 or bars[0][0] != 570:
            continue
        opening = bars[:2]                       # 09:30-10:00
        open_price = float(opening[0][1]["o"])
        high = max(float(b[1]["h"]) for b in opening)
        low = min(float(b[1]["l"]) for b in opening)
        volume = sum(float(b[1]["v"]) for b in opening)
        if open_price <= 0 or low <= 0:
            continue
        spread = (high - low) / open_price
        mark = float(opening[-1][1]["c"])         # price at the 30-minute mark
        close = float(bars[-1][1]["c"])
        if mark <= 0 or close <= 0:
            continue
        relative_volume = None
        if len(history) >= 20:
            average = sum(history[-20:]) / 20.0
            if average > 0:
                relative_volume = volume / average
        history.append(volume)
        out.append((day, spread, relative_volume, close / mark - 1.0))
    return out


def report(label, rows):
    """Forward return if LONG; the short earns the negative of it."""
    if not rows:
        print("{0:<30}{1:>9}".format(label, "none"), flush=True)
        return
    forward = sum(r[3] for r in rows) / len(rows)
    short_gross = -forward
    short_net = short_gross - 2 * ONE_WAY
    early = [r for r in rows if str(r[0]) < SPLIT]
    late = [r for r in rows if str(r[0]) >= SPLIT]
    n1 = -sum(r[3] for r in early) / len(early) - 2 * ONE_WAY if early else 0.0
    n2 = -sum(r[3] for r in late) / len(late) - 2 * ONE_WAY if late else 0.0
    down = sum(1 for r in rows if r[3] < 0)
    print("{0:<30}{1:>9}{2:>11.4%}{3:>11.4%}{4:>11.4%}{5:>11.4%}{6:>8.0%}".format(
        label, len(rows), forward, short_gross, short_net, n2,
        down / len(rows)), flush=True)


def main():
    universe = sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s))
    rows = []
    batch = 15
    for i in range(0, len(universe), batch):
        chunk = universe[i:i + batch]
        for symbol, sessions in fetch(chunk).items():
            if sessions:
                rows.extend(sessions_for(sessions))
        print("  {0}/{1}".format(min(i + batch, len(universe)), len(universe)),
              flush=True)
        time.sleep(0.2)

    print("\nFrom the 30-minute mark to the close, {0} onward.".format(START),
          flush=True)
    print("'short gross' is the negative of the forward return; 'short net'", flush=True)
    print("charges 12bps for the round trip. A real effect needs a GRADIENT.\n",
          flush=True)
    head = "{0:<30}{1:>9}{2:>11}{3:>11}{4:>11}{5:>11}{6:>8}".format(
        "bucket", "sessions", "fwd ret", "short gross", "short net",
        "2nd half", "down%")
    print(head, flush=True)
    print("-" * len(head), flush=True)
    report("ALL SESSIONS", rows)

    print("\nby OPENING RANGE (first 30 min high-low, as % of the open):", flush=True)
    ordered = sorted(rows, key=lambda r: r[1])
    size = max(1, len(ordered) // 5)
    for q in range(5):
        chunk = ordered[q * size:(q + 1) * size] if q < 4 else ordered[4 * size:]
        if chunk:
            report("Q{0}  range {1:.2%}-{2:.2%}".format(
                q + 1, chunk[0][1], chunk[-1][1]), chunk)

    with_volume = [r for r in rows if r[2] is not None]
    print("\nby OPENING VOLUME vs that symbol's own 20-session average:", flush=True)
    ordered = sorted(with_volume, key=lambda r: r[2])
    size = max(1, len(ordered) // 5)
    for q in range(5):
        chunk = ordered[q * size:(q + 1) * size] if q < 4 else ordered[4 * size:]
        if chunk:
            report("Q{0}  rvol {1:.1f}x-{2:.1f}x".format(
                q + 1, chunk[0][2], chunk[-1][2]), chunk)


if __name__ == "__main__":
    main()
