"""The deterministic input behind the golden master.

Synthetic, not real market data, and deliberately so. A golden master's job
is to answer one question - "did this code change alter behaviour?" - and
for that the input only has to be FIXED, not realistic. Synthetic bars are
generated from an explicit seed, so the fixture reproduces on any machine
with no dependency on the scratchpad datasets (which are gitignored and
would make the test pass locally and fail on a fresh clone).

Two traps avoided here, both of which would make the master silently
useless:

  `hash(symbol)` as a seed. Python randomises string hashing per process
  unless PYTHONHASHSEED is pinned, so a fixture seeded that way produces
  different bars on every run and the master can never match.

  A series the rule never trades. The gate needs RSI <= 35 while price is
  still above its own 200-day average, so a flat or falling series produces
  zero trades and the master asserts nothing. The drift below is positive
  and the shocks are large enough to produce oversold dips inside it - the
  prototype yields 21 trades across all three exit reasons.
"""

import random
from datetime import datetime, timedelta, timezone

from event_aware_trader.data import Bar

# One explicit seed per symbol. Never hash().
SEEDS = {
    "AAA": 11, "BBB": 22, "CCC": 33, "DDD": 44, "EEE": 55,
    "FFF": 66, "GGG": 77, "HHH": 88, "III": 99, "SPY": 1010,
}
BARS = 900
START_PRICE = 100.0
DRIFT = 0.0004
SHOCK = 0.013
VOLUME = 3_000_000
FIRST_DAY = datetime(2016, 1, 4, tzinfo=timezone.utc)


def make_series(seed: int, bars: int = BARS, start: float = START_PRICE):
    rng = random.Random(seed)
    price = start
    out = []
    for i in range(bars):
        price = max(5.0, price * (1 + DRIFT + rng.gauss(0, SHOCK)))
        high = price * (1 + abs(rng.gauss(0, 0.004)))
        low = price * (1 - abs(rng.gauss(0, 0.004)))
        open_ = low + (high - low) * rng.random()
        out.append(Bar(timestamp=FIRST_DAY + timedelta(days=i),
                       open=round(open_, 4), high=round(high, 4),
                       low=round(low, 4), close=round(price, 4),
                       volume=VOLUME))
    return out


def golden_series():
    """The fixed universe the golden master runs against."""
    return {symbol: make_series(seed) for symbol, seed in sorted(SEEDS.items())}


def fingerprint(report):
    """Every field a behaviour change could move, rounded to survive float noise."""
    return [
        {
            "symbol": t.symbol,
            "entry": t.entry_time.date().isoformat(),
            "exit": t.exit_time.date().isoformat(),
            "quantity": round(float(t.quantity), 6),
            "entry_price": round(float(t.entry_price), 6),
            "exit_price": round(float(t.exit_price), 6),
            "reason": t.exit_reason,
            "net_pnl": round(float(t.net_pnl), 4),
        }
        for t in report.trades
    ]
