"""Check a proposed take-profit / stop-loss before anyone trades it.

Read-only. It places no order and calls no API. Given a symbol, it reads that
symbol's price file in data/ - the same daily bars the bot uses, which stop at
the previous session - for the stock's volatility. Given --daily-vol, it
reads nothing. Prepared 2026-09-27; nothing in the trading loop uses it. The
reasoning behind every line is in docs/2026-09-27-exit-placement-research.md.

    python scripts/exit_check.py --target 0.5 --stop 0.2 --symbol UNP
    python scripts/exit_check.py --target 0.5 --stop 0.2 --daily-vol 1.5
    python scripts/exit_check.py --target 3 --stop 5 --symbol UNP --edge 0.05

Figures are in percent: 0.5 means 0.5%.
"""

import argparse
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.data import load_bars, price_file                  # noqa: E402
from event_aware_trader.exit_placement import (                            # noqa: E402
    PROJECT_ROUND_TRIP_COST, assess)
from event_aware_trader.indicators import wilder_atr                       # noqa: E402

FROZEN_STOP_ATR = 2.5       # the frozen rule's stop, in ATRs (Frozen Parameters)
VOL_SESSIONS = 60


def _daily_vol(closes):
    """Standard deviation of daily log returns over the last 60 sessions."""
    recent = closes[-(VOL_SESSIONS + 1):]
    moves = [math.log(b / a) for a, b in zip(recent, recent[1:]) if a > 0 and b > 0]
    if len(moves) < 20:
        raise SystemExit("not enough price history to measure volatility")
    mean = sum(moves) / len(moves)
    return math.sqrt(sum((m - mean) ** 2 for m in moves) / (len(moves) - 1))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", type=float, required=True, help="take profit, percent above entry")
    parser.add_argument("--stop", type=float, required=True, help="stop loss, percent below entry")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--symbol", help="read this symbol's daily bars from data/")
    source.add_argument("--daily-vol", type=float, help="daily volatility, percent")
    parser.add_argument("--edge", type=float, default=0.0,
                        help="assumed expected return per day, percent (default 0: no edge)")
    parser.add_argument("--cost", type=float, default=100 * PROJECT_ROUND_TRIP_COST,
                        help="round-trip cost, percent (default: the project's 0.12)")
    parser.add_argument("--data-dir", default=str(REPO / "data"))
    args = parser.parse_args(argv)

    lines = []
    if args.symbol:
        path = price_file(Path(args.data_dir), args.symbol)
        if not path.exists():
            raise SystemExit("no price file for {0} in {1}".format(args.symbol, args.data_dir))
        bars = load_bars(path)
        closes = [b.close for b in bars]
        vol = _daily_vol(closes)
        atr = wilder_atr(bars, 14)
        lines.append("{0}: daily volatility {1:.2%} (last {2} sessions to {3})".format(
            args.symbol, vol, VOL_SESSIONS, bars[-1].timestamp.date()))
        if atr:
            frozen = FROZEN_STOP_ATR * atr / closes[-1]
            lines.append("For a new {0} entry today the bot's own stop would be {1} x ATR "
                         "= {2:.2%} below entry.".format(args.symbol, FROZEN_STOP_ATR, frozen))
    else:
        vol = args.daily_vol / 100.0

    result = assess(args.target / 100.0, args.stop / 100.0, daily_vol=vol,
                    drift_per_day=args.edge / 100.0, round_trip_cost=args.cost / 100.0)
    lines.append("Proposed: take profit +{0:.2f}%, stop -{1:.2f}%".format(args.target, args.stop))
    lines += ["  - " + note for note in result.notes]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
