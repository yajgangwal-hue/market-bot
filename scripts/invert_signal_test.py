"""Should the bot SHORT what it currently buys, after a big volatile move?

The hypothesis, stated as given: the bot waits for a large violent move, buys
into it, and by then the move is finished - so it should be shorting those
setups instead of buying them.

There is already evidence pointing this way, which is why it is worth a proper
test rather than an opinion. Since the trend filter came off, the sessions
this rule holds return LESS than the average session of the same universe:
-0.0108% on the overnight leg and -0.0150% intraday. A rule whose picks are
worse than random is a rule whose inverse is worth measuring.

WHAT IS MEASURED. Every day the shipped rule would fire, the forward return is
taken from the NEXT open - the price the bot could actually get - through the
same exit the bot uses: RSI recovery, the 2.5-ATR stop, or twenty sessions.
Then the same trade is scored as a SHORT, with the stop mirrored above entry.

Three costs are charged, because shorting is not the mirror image of buying:

  spread/slippage   6bps a side, both directions, the shipped model
  borrow            0.5%/yr on the short side. These are large liquid names,
                    all marked easy_to_borrow on the account, so this is a
                    realistic rather than punitive figure.
  the drift         not a fee, but the reason shorts start behind: equities
                    rise over time and a short pays that away. It shows up in
                    the numbers rather than being added on.

THE VOLATILITY SPLIT is the actual question. "A huge volatile move" is made
precise as the size of the drop into the signal, measured in ATRs, and results
are bucketed by it. If the hypothesis is right, the biggest moves should be
where the long does worst and the short does best - a gradient, not one bucket.
"""
from pathlib import Path

from event_aware_trader.data import load_bars
from event_aware_trader.indicators import rsi, wilder_atr
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


def signals_for(bars):
    """Days the shipped rule fires, with the drop size that produced them."""
    out = []
    closes = [b.close for b in bars]
    for i in range(CONFIG.minimum_history, len(bars) - 1):
        window = bars[max(0, i - WINDOW + 1):i + 1]
        window_closes = closes[max(0, i - WINDOW + 1):i + 1]
        strength = rsi(window_closes, CONFIG.rsi_period)
        if strength is None or strength > CONFIG.rsi_entry:
            continue
        atr = wilder_atr(window, CONFIG.atr_days)
        close = closes[i]
        if not atr or close <= 0:
            continue
        fraction = atr / close
        if CONFIG.max_atr_fraction is not None and fraction > CONFIG.max_atr_fraction:
            continue
        if close < CONFIG.min_price:
            continue
        dollar_volume = sum(b.close * b.volume for b in bars[i - 19:i + 1]) / 20.0
        if dollar_volume < CONFIG.min_average_dollar_volume:
            continue
        # How violent was the move INTO this signal, in ATRs. This is the
        # "huge volatile move" made measurable.
        high20 = max(b.high for b in bars[max(0, i - 19):i + 1])
        drop_atrs = (high20 - close) / atr if atr > 0 else 0.0
        out.append((i, close, atr, drop_atrs))
    return out


def outcome(bars, index, atr, short):
    """Forward result from the next open, under the bot's own exit rules."""
    entry_index = index + 1
    if entry_index >= len(bars):
        return None
    entry = bars[entry_index].open
    if entry <= 0:
        return None
    stop = entry + CONFIG.stop_atr_multiple * atr if short \
        else entry - CONFIG.stop_atr_multiple * atr
    closes = [b.close for b in bars]
    for step in range(entry_index, min(entry_index + CONFIG.max_holding_bars,
                                       len(bars))):
        bar = bars[step]
        if short and bar.high >= stop:
            exit_price, held = stop, step - entry_index + 1
            break
        if not short and bar.low <= stop:
            exit_price, held = stop, step - entry_index + 1
            break
        strength = rsi(closes[max(0, step - WINDOW + 1):step + 1],
                       CONFIG.rsi_period)
        if strength is not None and strength >= CONFIG.rsi_exit:
            exit_price, held = bar.close, step - entry_index + 1
            break
    else:
        exit_price = bars[min(entry_index + CONFIG.max_holding_bars,
                              len(bars)) - 1].close
        held = CONFIG.max_holding_bars

    gross = (entry / exit_price - 1.0) if short else (exit_price / entry - 1.0)
    net = gross - 2 * ONE_WAY - (BORROW_PER_DAY * held if short else 0.0)
    return gross, net, held, bars[entry_index].timestamp.date().isoformat()


def summarise(label, rows):
    if not rows:
        print("{0:<26}{1:>9}".format(label, "none"), flush=True)
        return
    long_net = sum(r["long_net"] for r in rows) / len(rows)
    short_net = sum(r["short_net"] for r in rows) / len(rows)
    long_gross = sum(r["long_gross"] for r in rows) / len(rows)
    early = [r for r in rows if r["date"] < SPLIT]
    late = [r for r in rows if r["date"] >= SPLIT]
    s1 = sum(r["short_net"] for r in early) / len(early) if early else 0.0
    s2 = sum(r["short_net"] for r in late) / len(late) if late else 0.0
    wins = sum(1 for r in rows if r["short_net"] > 0)
    print("{0:<26}{1:>9}{2:>11.3%}{3:>11.3%}{4:>11.3%}{5:>10.3%}{6:>10.3%}{7:>7.0%}".format(
        label, len(rows), long_gross, long_net, short_net, s1, s2,
        wins / len(rows)), flush=True)


def main():
    series = load()
    print("symbols {0}\n".format(len(series)), flush=True)
    rows = []
    for symbol, bars in series.items():
        for index, close, atr, drop_atrs in signals_for(bars):
            long_side = outcome(bars, index, atr, short=False)
            short_side = outcome(bars, index, atr, short=True)
            if not long_side or not short_side:
                continue
            rows.append({
                "symbol": symbol, "drop_atrs": drop_atrs,
                "long_gross": long_side[0], "long_net": long_side[1],
                "short_gross": short_side[0], "short_net": short_side[1],
                "held": long_side[2], "date": long_side[3],
            })

    head = "{0:<26}{1:>9}{2:>11}{3:>11}{4:>11}{5:>10}{6:>10}{7:>7}".format(
        "bucket", "signals", "long gross", "long net", "SHORT net",
        "shrt 1st", "shrt 2nd", "shrt%")
    print(head, flush=True)
    print("-" * len(head), flush=True)
    summarise("ALL SIGNALS", rows)

    print("\nby how violent the move INTO the signal was:", flush=True)
    ordered = sorted(rows, key=lambda r: r["drop_atrs"])
    size = max(1, len(ordered) // 5)
    for q in range(5):
        chunk = ordered[q * size:(q + 1) * size] if q < 4 else ordered[4 * size:]
        if not chunk:
            continue
        low = chunk[0]["drop_atrs"]
        high = chunk[-1]["drop_atrs"]
        summarise("Q{0}  drop {1:.1f}-{2:.1f} ATR".format(q + 1, low, high), chunk)


if __name__ == "__main__":
    main()
