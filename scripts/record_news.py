"""Record the news the bot can see right now, point-in-time.

Runs alongside the trading loop and writes data/news/<date>.jsonl. It does
NOT feed an entry or an exit: measuring the owner's own example first
(EXP-0040/0041) showed that buying a product launch on the day is the wrong
half of the trade - the drift is +5.11% in the thirty sessions BEFORE an
Apple launch and -0.58% on the day after, positive in only 3 years of 10.

What it is for is the corpus. A news signal cannot be tested honestly on
news you did not have at the time, and a vendor's history is revised and
back-filled in ways that are invisible afterwards. Every row here carries
the moment it was fetched, so a future test can replay exactly what was
visible and nothing else.

  python scripts/record_news.py            # held positions + the universe
  python scripts/record_news.py AAPL MSFT  # named symbols
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.broker import (                     # noqa: E402
    AlpacaPaperBroker, BrokerConfig, BrokerError)
from event_aware_trader.news import fetch_news, record      # noqa: E402
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto  # noqa: E402

# One request covers many symbols, but the whole universe in one query
# returns mostly noise about names the bot will never hold today. Held
# positions always; a slice of the universe so the corpus is not only about
# what was already owned, which would bias any later study toward winners.
UNIVERSE_SLICE = 40


def main():
    named = [s.upper() for s in sys.argv[1:]]
    symbols = list(named)
    if not symbols:
        try:
            broker = AlpacaPaperBroker(BrokerConfig.from_environment())
            symbols = [str(p["symbol"]).upper() for p in broker.positions()
                       if "/" not in str(p["symbol"])]
        except BrokerError as error:
            print("position lookup failed ({0}); using the universe only"
                  .format(error))
            symbols = []
        rest = [s for s in DEFAULT_UNIVERSE
                if not is_crypto(s) and s not in symbols]
        # Rotated by day so the whole universe is covered over time without
        # one long request every cycle.
        offset = (datetime.now(timezone.utc).toordinal() * UNIVERSE_SLICE) % max(1, len(rest))
        symbols += (rest + rest)[offset:offset + UNIVERSE_SLICE]

    if not symbols:
        print("no symbols to record")
        return 0

    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=1)).date().isoformat()
    end = now.date().isoformat()
    try:
        items = fetch_news(symbols, start, end)
    except Exception as error:                    # network, auth, rate limit
        print("news fetch failed: {0}".format(error))
        return 1                                  # nothing else is affected

    path = record(items, REPO / "data" / "news", now)
    total = sum(1 for _ in path.open(encoding="utf-8")) if path.exists() else 0
    print("news: {0} items fetched for {1} symbols -> {2} ({3} rows today)"
          .format(len(items), len(symbols), path.name, total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
