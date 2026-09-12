"""Seed the learning loop from history, so it does not need 7.5 years to start.

THE PROBLEM. `train_live_model` needs 500 examples before it produces anything,
and a training row is written only when a trade CLOSES. The rule closes about
67 trades a year, so the loop needs roughly seven and a half years of live
trading before it can fit its first model. Until then `retrain` reports
`not_enough_examples` every single day, `live-model.json` never appears, and
the bot has no learned component at all.

`cli.py retrain` already accepts `--seed data/big-dataset.jsonl` for exactly
this reason. The file has never existed. This builds it.

WHAT IT DOES. Replays the shipped rule over the historical bars, and for every
trade it would have taken, records the features as they stood at entry paired
with what the trade actually returned. That is the same (features -> outcome)
pair `append_example` writes live, so the seed and the live rows are the same
kind of thing and can be trained on together.

THE THING THAT MATTERS MOST HERE. The features must be computed exactly as the
live path computes them - same sixteen `LIVE_FEATURES`, same `build_snapshot`,
same DAILY bars. A seed built any other way trains a model on one thing and
scores it on another, which is the defect that was just removed from the live
path (15-minute candles feeding functions that count in days). So this script
calls the same `live_features` the bot calls, and builds one snapshot per entry
date from bars sliced to that date - never later ones.

NO LOOK-AHEAD. Every snapshot is built only from bars whose timestamp is on or
before the entry date, and the label comes from the trade's realised R, which
is by construction in the future of the features. That is supervised learning,
not leakage: the model sees the past and is scored on whether it predicted the
future - and `train_live_model` then splits chronologically and reports AUC on
a segment it never fitted.

    python scripts/build_training_seed.py --window deep   (the decade)
    python scripts/build_training_seed.py --window long   (thirty years)

Writes data/big-dataset.jsonl. Trains nothing - run `retrain` after.
"""

import argparse
import glob
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from event_aware_trader import portfolio as portfolio_module
from event_aware_trader.cross_sectional import build_snapshot
from event_aware_trader.data import load_bars
from event_aware_trader.live_model import LIVE_FEATURES, live_features
from event_aware_trader.mean_reversion import conviction as shipped_conviction
from event_aware_trader.portfolio import run_portfolio
from event_aware_trader.risk import CostModel, RiskPolicy
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto

OUT = Path("data/big-dataset.jsonl")
WINDOW = 400

_full = portfolio_module.mean_reversion_signal
_conv = {}
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-WINDOW:], c)


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def scratch_dir():
    matches = glob.glob(
        "C:/Users/yajga/AppData/Local/Temp/claude/**/scratchpad/deep",
        recursive=True)
    if not matches:
        raise SystemExit(
            "historical bars not found. This needs the deep/ and long/ price "
            "folders the research scripts use.")
    return Path(matches[0]).parent


def load(folder, since=None, minimum=500):
    root = scratch_dir() / folder
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        path = root / (symbol + ".csv")
        if not path.exists():
            continue
        try:
            bars = load_bars(path)
        except Exception:
            continue
        if since:
            bars = [b for b in bars if b.timestamp.date() >= since]
        if len(bars) >= minimum:
            out[symbol] = bars
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", choices=("deep", "long"), default="long")
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()

    since = date(1996, 1, 1) if args.window == "long" else None
    minimum = 400 if args.window == "long" else 500
    series = load(args.window, since, minimum)
    print("loaded {0} symbols".format(len(series)), flush=True)

    report = run_portfolio(series, starting_cash=100_000.0, policy=RiskPolicy(),
                           costs=CostModel(), entry_rule="mean_reversion",
                           conviction=conviction, entry_fill="signal_close")
    print("replayed {0} trades".format(len(report.trades)), flush=True)

    index = {s: {b.timestamp.date(): i for i, b in enumerate(bars)}
             for s, bars in series.items()}

    # One snapshot per entry date, built from bars sliced to that date. Cached,
    # because several trades usually open on the same day and a snapshot over
    # 230 symbols is the expensive part.
    snapshots = {}

    def snapshot_for(day):
        hit = snapshots.get(day)
        if hit is not None:
            return hit if hit != "none" else None
        sliced = {}
        for symbol, bars in series.items():
            cut = index[symbol].get(day)
            if cut is None:
                # Not a trading day for this name; take everything before it.
                usable = [b for b in bars if b.timestamp.date() <= day]
            else:
                usable = bars[:cut + 1]
            if len(usable) >= 130:
                sliced[symbol] = usable
        built = build_snapshot(sliced)
        snapshots[day] = built if built is not None else "none"
        return built

    written = skipped = 0
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for trade in report.trades:
            day = trade.entry_time.date()
            bars = series.get(trade.symbol)
            cut = index.get(trade.symbol, {}).get(day)
            if bars is None or cut is None:
                skipped += 1
                continue
            snapshot = snapshot_for(day)
            feats = live_features(trade.symbol, bars[:cut + 1], snapshot)
            if not feats:
                skipped += 1
                continue
            handle.write(json.dumps({
                "d": day.isoformat(),
                "s": trade.symbol,
                "f": {k: float(feats.get(k, 0.0)) for k in LIVE_FEATURES},
                "r": float(trade.r_multiple),
                "label": 1 if trade.r_multiple >= 1.0 else 0,
            }, sort_keys=True) + "\n")
            written += 1

    labels = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            labels += json.loads(line)["label"]
    print("\nwrote {0} rows to {1} ({2} skipped)".format(written, path, skipped),
          flush=True)
    print("   winners (>= 1R): {0}  ({1:.0%} base rate)".format(
        labels, labels / written if written else 0.0), flush=True)
    print("   snapshots built: {0} distinct entry dates".format(len(snapshots)),
          flush=True)
    print("\nnow run:  event-aware-trader retrain", flush=True)
    print("It trains on this seed PLUS every live trade closed so far, and", flush=True)
    print("reports holdout AUC. The model is only used if that clears 0.53.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
