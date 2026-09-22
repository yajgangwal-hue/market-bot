"""H-0023 step 1 - acquire daily bars for DELISTED US equities.

DATA INVENTORY ONLY. No return is computed here, no strategy is run,
nothing is registered. This exists so the H-0023 seal can be written
against a known population rather than a guess.

WHAT IS COLLECTED. Every asset Alpaca reports as `status=inactive`,
`asset_class=us_equity`, on a MAJOR exchange (NYSE, NASDAQ, ARCA,
AMEX, BATS) - 2,868 symbols. OTC is excluded: the production universe
floors are $20 and $50m of 20-day dollar volume, which no OTC name
reaches, and 16,307 OTC symbols would be pure acquisition cost.

WHY THIS IS THE RIGHT POPULATION. The bars for a delisted name STOP at
its last trading session - verified on five known cases: CELG ends
2019-11-20, XLNX 2022-02-11, RTN 2020-04-02, MYL 2020-11-16, ESRX
2018-12-20. So the bar history itself carries the delisting date that
the asset record does not.

WHAT THE ASSET RECORD DOES NOT CARRY, and it matters: no listing date,
no delisting date, and no delisting REASON. An acquisition at a premium
and a bankruptcy both simply stop producing bars. That distinction is
the difference between a winner and a total loss, and it is recorded
here as a limitation rather than guessed at.
"""

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.broker import (                            # noqa: E402
    AlpacaPaperBroker, BrokerConfig)
from event_aware_trader.data import fetch_alpaca_equity_bars       # noqa: E402

MAJOR = ("NYSE", "NASDAQ", "ARCA", "AMEX", "BATS")
OUT = REPO / "data" / "phase5" / "h0023-delisted-bars.jsonl"
BATCH = 50
DAYS = 4000                      # covers the 2016-01-04 decade start


def main():
    broker = AlpacaPaperBroker(BrokerConfig.from_environment())
    inactive = broker._request(
        "GET", "/v2/assets?status=inactive&asset_class=us_equity")
    symbols = sorted({a["symbol"] for a in inactive
                      if a.get("exchange") in MAJOR
                      and "/" not in a["symbol"]})
    print("inactive us_equity on a major exchange: {0}".format(len(symbols)))

    done = set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["symbol"])
        print("already acquired: {0}".format(len(done)))
    todo = [s for s in symbols if s not in done]
    print("to acquire: {0}".format(len(todo)))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with OUT.open("a", encoding="utf-8") as handle:
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            try:
                got = fetch_alpaca_equity_bars(chunk, days=DAYS,
                                               interval="1d",
                                               adjustment="split")
            except Exception as error:                        # noqa: BLE001
                print("  batch {0} failed: {1}".format(i // BATCH, error))
                time.sleep(2.0)
                continue
            for symbol in chunk:
                bars = got.get(symbol) or []
                # Store only what the universe rules need, plus the first
                # and last session, which is the delisting evidence.
                handle.write(json.dumps({
                    "symbol": symbol,
                    "n": len(bars),
                    "first": bars[0].timestamp.date().isoformat() if bars else None,
                    "last": bars[-1].timestamp.date().isoformat() if bars else None,
                    "bars": [[b.timestamp.date().isoformat(), b.close, b.volume]
                             for b in bars],
                }, separators=(",", ":")) + "\n")
                written += 1
            print("  {0}/{1} symbols".format(min(i + BATCH, len(todo)),
                                             len(todo)), flush=True)
            time.sleep(0.25)
    print("\nwrote {0} symbol records to {1}".format(written, OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
