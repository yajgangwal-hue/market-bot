"""Which rule family, if any, makes money on crypto? Screening pass.

The equity rule does not work here and the reason is structural, not a
setting: it needs oversold AND above the 200-day average at once, and in
crypto the price has usually broken the 200-day long before RSI reaches 35.
Eight trades in five years, none in the last two and a half.

So this tests DIFFERENT families rather than different parameters, long-only
because Alpaca has no crypto borrow - shortable, marginable and
easy_to_borrow are all false on all 73 crypto assets.

WHAT THIS IS AND IS NOT. This is a screening pass: each symbol gets an equal
slice of capital and is simulated independently. That is exactly the design
this project has already been burned by - `run_backtest` gave every symbol its
own private cash balance and produced years of numbers that "answer a question
nobody has". It is used here only to rank families cheaply. Anything that
survives gets re-run through the account simulator with one shared balance
before it goes anywhere near the bot.

The benchmark is equal-weight buy and hold. A crypto strategy that does not
beat holding the coins is not a strategy, it is a fee generator - and crypto
buy-and-hold over this window is a very high bar.

Costs are 25bps one way, Alpaca's crypto fee tier plus spread, charged on
every entry and exit.
"""
from datetime import date, datetime
from pathlib import Path

from event_aware_trader.data import load_bars
from event_aware_trader.indicators import rsi, sma

CRYPTO = Path(__file__).with_name("crypto_all")
ONE_WAY = 0.0025
SPLIT = date(2024, 6, 1)
MEME = ("DOGE", "SHIB", "PEPE", "BONK", "WIF", "TRUMP")


def load():
    out = {}
    for path in sorted(CRYPTO.glob("*.csv")):
        bars = load_bars(path)
        if len(bars) >= 260:
            out[path.stem.replace("-", "/")] = bars
    return out


# ---- rules: each returns a list of (in_market: bool) aligned to bars --------

def hold(bars):
    return [True] * len(bars)


def ts_momentum(days):
    """Long while the close is above its own N-day average. Classic trend."""
    def rule(bars):
        closes = [b.close for b in bars]
        out = []
        for i in range(len(bars)):
            average = sma(closes[:i + 1], days)
            out.append(bool(average is not None and closes[i] > average))
        return out
    rule.__name__ = "ts_momentum_{0}".format(days)
    return rule


def breakout(entry_days, exit_days):
    """Long on a new N-day high, out on a new M-day low. Donchian."""
    def rule(bars):
        out, live = [], False
        for i in range(len(bars)):
            if i < entry_days:
                out.append(False)
                continue
            highs = max(b.high for b in bars[i - entry_days:i])
            lows = min(b.low for b in bars[max(0, i - exit_days):i])
            if not live and bars[i].close > highs:
                live = True
            elif live and bars[i].close < lows:
                live = False
            out.append(live)
        return out
    rule.__name__ = "breakout_{0}_{1}".format(entry_days, exit_days)
    return rule


def mean_reversion(period, entry, exit_level, trend_days=0):
    """Buy weakness, sell recovery. trend_days=0 removes the trend filter."""
    def rule(bars):
        closes = [b.close for b in bars]
        out, live = [], False
        for i in range(len(bars)):
            strength = rsi(closes[:i + 1], period)
            if strength is None:
                out.append(False)
                continue
            allowed = True
            if trend_days:
                average = sma(closes[:i + 1], trend_days)
                allowed = average is not None and closes[i] > average
            if not live and strength <= entry and allowed:
                live = True
            elif live and strength >= exit_level:
                live = False
            out.append(live)
        return out
    rule.__name__ = "mr_{0}_{1}_{2}_t{3}".format(period, entry, exit_level, trend_days)
    return rule


# ---- evaluation ------------------------------------------------------------

def equity_for(bars, flags, start=None):
    """Compound one symbol's slice, charging a cost every time the state flips.

    Entry is at the NEXT bar's open, never this bar's close, because the rule
    is decided from a close that has already happened.
    """
    value = 1.0
    live = False
    trades = 0
    for i in range(1, len(bars)):
        if start is not None and bars[i].timestamp.date() < start:
            live = False
            continue
        if live:
            value *= bars[i].close / bars[i - 1].close
        want = flags[i - 1]
        if want != live:
            value *= (1.0 - ONE_WAY)
            live = want
            trades += 1
    return value, trades


def drawdown_for(bars, flags, start=None):
    value, peak, worst, live = 1.0, 1.0, 0.0, False
    for i in range(1, len(bars)):
        if start is not None and bars[i].timestamp.date() < start:
            continue
        if live:
            value *= bars[i].close / bars[i - 1].close
        want = flags[i - 1]
        if want != live:
            value *= (1.0 - ONE_WAY)
            live = want
        peak = max(peak, value)
        worst = min(worst, value / peak - 1.0)
    return worst


def evaluate(series, rule):
    """Equal-weight across symbols; each contributes its own compounded slice."""
    whole, first, second, trades, dds = [], [], [], 0, []
    for symbol, bars in series.items():
        flags = rule(bars)
        value, n = equity_for(bars, flags)
        whole.append(value)
        trades += n
        dds.append(drawdown_for(bars, flags))
        split_index = next((i for i, b in enumerate(bars)
                            if b.timestamp.date() >= SPLIT), None)
        if split_index and split_index > 30 and split_index < len(bars) - 30:
            a, _ = equity_for(bars[:split_index], flags[:split_index])
            b, _ = equity_for(bars, flags, start=SPLIT)
            first.append(a)
            second.append(b)
    def mean(values):
        return sum(values) / len(values) - 1.0 if values else 0.0
    return (mean(whole), mean(first), mean(second), trades,
            sum(dds) / len(dds) if dds else 0.0)


def report(title, series, rules):
    print("\n=== {0} ({1} coins) ===".format(title, len(series)), flush=True)
    head = "{0:<26}{1:>12}{2:>12}{3:>12}{4:>9}{5:>10}".format(
        "rule", "total", "to 2024-06", "since", "trades", "avg maxDD")
    print(head, flush=True)
    print("-" * len(head), flush=True)
    for label, rule in rules:
        total, first, second, trades, dd = evaluate(series, rule)
        print("{0:<26}{1:>+12.1%}{2:>+12.1%}{3:>+12.1%}{4:>9}{5:>10.1%}".format(
            label, total, first, second, trades, dd), flush=True)


def main():
    series = load()
    print("loaded {0} pairs".format(len(series)), flush=True)
    memes = {s: b for s, b in series.items() if any(m in s for m in MEME)}
    print("of which meme coins: {0}".format(sorted(memes)), flush=True)

    rules = [
        ("buy and hold (BENCHMARK)", hold),
        ("trend: above 20d", ts_momentum(20)),
        ("trend: above 50d", ts_momentum(50)),
        ("trend: above 100d", ts_momentum(100)),
        ("trend: above 200d", ts_momentum(200)),
        ("breakout 20d / exit 10d", breakout(20, 10)),
        ("breakout 50d / exit 20d", breakout(50, 20)),
        ("MR rsi14 35/60 no trend", mean_reversion(14, 35, 60)),
        ("MR rsi14 35/60 + 200d", mean_reversion(14, 35, 60, 200)),
        ("MR rsi2  10/70 no trend", mean_reversion(2, 10, 70)),
        ("MR rsi2  10/70 + 50d", mean_reversion(2, 10, 70, 50)),
        ("MR rsi7  20/65 + 50d", mean_reversion(7, 20, 65, 50)),
    ]
    report("ALL CRYPTO", series, rules)
    if memes:
        report("MEME COINS ONLY", memes, rules)


if __name__ == "__main__":
    main()
