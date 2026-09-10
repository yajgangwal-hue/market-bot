"""Short the reversal after a big move UP - the mirror of the shipped rule.

This is a different hypothesis from the one already rejected, and the
distinction matters enough to test rather than wave away.

WHAT WAS ALREADY TESTED AND REJECTED: inverting the bot's own signal, i.e.
shorting the OVERSOLD names it currently buys. 25,643 signals, -0.501% a
trade, no gradient by move violence, and the long side earned +0.903% so the
premise failed outright.

WHAT IS TESTED HERE: shorting the OVERBOUGHT - a stock that has run up hard
and is now expected to fall back. That is the true mirror of a rule which buys
weakness expecting a bounce, and it has never been measured at scale here. The
only prior attempt was 74 trades on the old trend-gate configuration, far too
few to conclude anything from.

The mirror, made exact:

    buy  side (shipped)   RSI <= 35, ABOVE the 200-day, exit at RSI >= 60
    short side (here)     RSI >= 65, BELOW the 200-day, exit at RSI <= 40

with the stop 2.5 ATR ABOVE entry rather than below, the same 20-session
holding cap, and entry at the next open.

Variants sweep the entry threshold and the trend condition, because the
description does not specify either. The "big swing" is made measurable as the
size of the RUN-UP into the signal in ATRs, and results are bucketed by it -
the claim implies the biggest run-ups should short best, which is a gradient,
not a single number.

Costs: 6bps a side plus 0.5%/yr borrow. Every name in this universe is marked
easy_to_borrow on the account, so that is realistic rather than punitive.

The bar is the one every change here faces: profitable NET, in BOTH halves,
with a mechanism visible in the buckets rather than one lucky cell.
"""
from pathlib import Path

from event_aware_trader.data import load_bars
from event_aware_trader.indicators import rsi, sma, wilder_atr
from event_aware_trader.mean_reversion import MeanReversionConfig
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto

DEEP = Path(__file__).with_name("deep")
CONFIG = MeanReversionConfig()
ONE_WAY = 0.0006
BORROW_PER_DAY = 0.005 / 365.0
SPLIT = "2021-03-01"
WINDOW = 400


def load():
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        path = DEEP / (symbol + ".csv")
        if path.exists():
            bars = load_bars(path)
            if len(bars) >= 500:
                out[symbol] = bars
    return out


def short_signals(bars, entry_rsi, trend):
    """Days a short would be taken. `trend` is 'below', 'above' or 'any'."""
    out = []
    closes = [b.close for b in bars]
    for i in range(CONFIG.minimum_history, len(bars) - 1):
        lo = max(0, i - WINDOW + 1)
        strength = rsi(closes[lo:i + 1], CONFIG.rsi_period)
        if strength is None or strength < entry_rsi:
            continue
        close = closes[i]
        atr = wilder_atr(bars[lo:i + 1], CONFIG.atr_days)
        if not atr or close <= 0 or close < CONFIG.min_price:
            continue
        if CONFIG.max_atr_fraction and atr / close > CONFIG.max_atr_fraction:
            continue
        if trend != "any":
            average = sma(closes[lo:i + 1], CONFIG.trend_ma_days)
            if average is None:
                continue
            if trend == "below" and close >= average:
                continue
            if trend == "above" and close <= average:
                continue
        dollar_volume = sum(b.close * b.volume for b in bars[i - 19:i + 1]) / 20.0
        if dollar_volume < CONFIG.min_average_dollar_volume:
            continue
        # The "big swing" made measurable: how far it ran UP into the signal.
        low20 = min(b.low for b in bars[max(0, i - 19):i + 1])
        run_atrs = (close - low20) / atr if atr > 0 else 0.0
        out.append((i, atr, run_atrs))
    return out


def short_outcome(bars, index, atr, exit_rsi):
    """Forward result of a short from the next open, mirrored exits."""
    entry_index = index + 1
    if entry_index >= len(bars):
        return None
    entry = bars[entry_index].open
    if entry <= 0:
        return None
    stop = entry + CONFIG.stop_atr_multiple * atr
    closes = [b.close for b in bars]
    exit_price = None
    for step in range(entry_index, min(entry_index + CONFIG.max_holding_bars,
                                       len(bars))):
        bar = bars[step]
        if bar.high >= stop:
            exit_price, held = stop, step - entry_index + 1
            break
        strength = rsi(closes[max(0, step - WINDOW + 1):step + 1],
                       CONFIG.rsi_period)
        if strength is not None and strength <= exit_rsi:
            exit_price, held = bar.close, step - entry_index + 1
            break
    if exit_price is None:
        last = min(entry_index + CONFIG.max_holding_bars, len(bars)) - 1
        exit_price, held = bars[last].close, CONFIG.max_holding_bars
    gross = entry / exit_price - 1.0
    net = gross - 2 * ONE_WAY - BORROW_PER_DAY * held
    return gross, net, bars[entry_index].timestamp.date().isoformat(), held


def summarise(label, rows, note=""):
    if not rows:
        print("{0:<30}{1:>9}".format(label, "none"), flush=True)
        return
    gross = sum(r[0] for r in rows) / len(rows)
    net = sum(r[1] for r in rows) / len(rows)
    early = [r for r in rows if r[2] < SPLIT]
    late = [r for r in rows if r[2] >= SPLIT]
    n1 = sum(r[1] for r in early) / len(early) if early else 0.0
    n2 = sum(r[1] for r in late) / len(late) if late else 0.0
    wins = sum(1 for r in rows if r[1] > 0)
    flag = "  <- profitable BOTH halves" if (n1 > 0 and n2 > 0) else ""
    print("{0:<30}{1:>9}{2:>11.3%}{3:>11.3%}{4:>11.3%}{5:>11.3%}{6:>7.0%}{7}{8}".format(
        label, len(rows), gross, net, n1, n2, wins / len(rows), note, flag),
        flush=True)


def header(title):
    print("\n=== {0} ===".format(title), flush=True)
    h = "{0:<30}{1:>9}{2:>11}{3:>11}{4:>11}{5:>11}{6:>7}".format(
        "variant", "signals", "gross", "net", "1st half", "2nd half", "win%")
    print(h, flush=True)
    print("-" * len(h), flush=True)


def main():
    series = load()
    print("symbols {0}".format(len(series)), flush=True)
    print("shorting the OVERBOUGHT - the mirror never tested at scale here",
          flush=True)

    header("entry threshold, BELOW the 200-day (true mirror)")
    best = None
    for entry_rsi in (60.0, 65.0, 70.0, 75.0):
        rows = []
        for symbol, bars in series.items():
            for index, atr, _run in short_signals(bars, entry_rsi, "below"):
                result = short_outcome(bars, index, atr, 40.0)
                if result:
                    rows.append(result)
        summarise("rsi >= {0:.0f}, below 200d".format(entry_rsi), rows)
        if entry_rsi == 65.0:
            best = rows

    header("the trend condition, at rsi >= 65")
    keep = {}
    for trend in ("below", "any", "above"):
        rows = []
        for symbol, bars in series.items():
            for index, atr, _run in short_signals(bars, 65.0, trend):
                result = short_outcome(bars, index, atr, 40.0)
                if result:
                    rows.append(result)
        keep[trend] = rows
        summarise("rsi >= 65, {0} the 200d".format(trend), rows)

    header("by how big the RUN-UP into the signal was (rsi>=65, any trend)")
    tagged = []
    for symbol, bars in series.items():
        for index, atr, run in short_signals(bars, 65.0, "any"):
            result = short_outcome(bars, index, atr, 40.0)
            if result:
                tagged.append((run,) + result)
    tagged.sort()
    size = max(1, len(tagged) // 5)
    for q in range(5):
        chunk = tagged[q * size:(q + 1) * size] if q < 4 else tagged[4 * size:]
        if not chunk:
            continue
        summarise("Q{0}  run-up {1:.1f}-{2:.1f} ATR".format(
            q + 1, chunk[0][0], chunk[-1][0]), [r[1:] for r in chunk])


if __name__ == "__main__":
    main()
