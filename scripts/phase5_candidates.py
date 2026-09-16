"""Every entry the frozen rule would consider, not only the ones it took.

A filter tested only on the trades the strategy ACTUALLY took cannot be
re-run as a portfolio: rejecting an entry frees capital, and the next
candidate the simulator reaches may be one the baseline never bought. To
test a news filter honestly the archive has to cover every candidate the
rule could have acted on, so this enumerates them.

It runs the shipped signal function over each symbol independently. That
is far cheaper than a portfolio simulation because there is no cash, no
concurrency limit and no position bookkeeping - and it deliberately
applies no capacity rule, because the point is the superset.

  python scripts/phase5_candidates.py deep
"""

import glob
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.data import load_bars                  # noqa: E402
from event_aware_trader.mean_reversion import (                # noqa: E402
    MeanReversionConfig, evaluate as mean_reversion_signal)
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto  # noqa: E402

WINDOW = 400
WINDOWS = {
    "deep": {"folder": "deep", "since": None, "minimum": 500},
    "long": {"folder": "long", "since": date(1996, 1, 1), "minimum": 400},
}

SCRATCH = Path(glob.glob(
    "C:/Users/yajga/AppData/Local/Temp/claude/**/scratchpad/deep",
    recursive=True)[0]).parent


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "deep"
    spec = WINDOWS[which]
    config = MeanReversionConfig()
    out = []
    symbols = sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s))
    for n, symbol in enumerate(symbols, 1):
        path = SCRATCH / spec["folder"] / (symbol + ".csv")
        if not path.exists():
            continue
        try:
            bars = load_bars(path)
        except Exception:
            continue
        if spec["since"]:
            bars = [b for b in bars if b.timestamp.date() >= spec["since"]]
        if len(bars) < spec["minimum"]:
            continue
        for i in range(200, len(bars)):
            history = bars[max(0, i - WINDOW + 1):i + 1]
            signal = mean_reversion_signal(symbol, history, config)
            if signal.is_buy and signal.stop is not None \
                    and signal.stop < signal.close:
                out.append({"symbol": symbol,
                            "date": bars[i].timestamp.date().isoformat()})
        if n % 40 == 0:
            print("  {0}/{1} symbols, {2} candidates".format(
                n, len(symbols), len(out)), flush=True)

    path = REPO / "data" / "phase5" / "candidates-{0}.jsonl".format(which)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in out),
                    encoding="utf-8")
    days = {(r["symbol"], r["date"]) for r in out}
    print("{0} candidate signals, {1} distinct symbol-days".format(
        len(out), len(days)))
    print("wrote {0}".format(path.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
