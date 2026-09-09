"""Crypto trend-following, in the ACCOUNT simulator. The gap in my own work.

The screening pass ranked trend-following top on crypto - above the 20-day
average returned +372.6% and above the 50-day +242.2%, against buy-and-hold's
+265.0% - and I then validated only the MEAN-REVERSION family properly. That
family collapsed from +14.9% screened to -38.6% simulated. Trend was never put
through the same test, which makes it the most promising untested thing left.

Why trend is the right family to expect something from, rather than a guess:

  * Crypto's own literature and every practitioner account points the same
    way. Time-series momentum is the one effect that has survived across
    asset classes for a century (Moskowitz, Ooi & Pedersen), and crypto is
    the most momentum-driven liquid market there is.
  * The mechanism that kills mean reversion here is the mechanism that helps
    trend. Crypto trends hard and gaps through stops; a rule that buys
    weakness gets run over by exactly that, and a rule that follows strength
    is carried by it.
  * The measured evidence from the screen agrees: buying dips lost (-29.7%)
    and following trends won (+372.6%) on the same data, same costs.

WHAT IS DIFFERENT HERE FROM THE SCREEN. One shared cash balance, the position
and correlation caps, real position sizing off a risk budget, and entry at the
NEXT bar's open rather than the signal bar's close. Those four things turned
+14.9% into -38.6% last time, so they are the whole test.

The exit is the hard part, and it is why this needs its own signal rather than
the shipped config. Trend-following exits on trend loss, not on a target or an
oversold reading. The simulator's mean-reversion branch exits on RSI recovery,
the stop, or the holding cap - so the RSI exit is disabled by setting it above
100, the holding cap is set long, and the STOP carries the exit, placed at a
multiple of ATR below the trend line rather than below the entry. That makes
the stop the trend filter, which is what a Donchian or moving-average system
does anyway.

Costs 25bps one way, Alpaca's crypto tier plus spread.
"""
from dataclasses import replace
from datetime import date
from pathlib import Path

from event_aware_trader import portfolio as portfolio_module
from event_aware_trader.data import load_bars
from event_aware_trader.indicators import sma, wilder_atr
from event_aware_trader.mean_reversion import MeanReversionConfig, MeanReversionSignal
from event_aware_trader.portfolio import run_portfolio
from event_aware_trader.risk import CostModel, RiskPolicy

CRYPTO = Path(__file__).with_name("crypto_all")
SPLIT = date(2024, 6, 1)
CASH = 100_000.0
COSTS = CostModel(half_spread_bps=12.5, slippage_bps=12.5)
MEME = ("DOGE", "SHIB", "PEPE", "BONK", "WIF", "TRUMP")

# The config refuses rsi_exit >= 100, so 99.9 is the closest to "never". RSI
# only reaches that after a near-unbroken run of gains, which in a trend system
# is a reasonable place to take something off anyway - so the rare firing is
# not a distortion of the rule being tested. The stop and the holding cap are
# otherwise the only ways out, which is what a trend system wants.
BASE = replace(MeanReversionConfig(),
               rsi_exit=99.9, max_holding_bars=10_000,
               max_atr_fraction=None, min_price=1e-9,
               min_average_dollar_volume=100_000.0)

SETTINGS = {"ma": 50, "stop_atr": 3.0, "confirm": 0}


def _signal(symbol, bars, config):
    """Long while price is above its own N-day average, stop below the line."""
    closes = [b.close for b in bars]
    close = closes[-1] if closes else 0.0

    def stand_aside(why):
        return MeanReversionSignal(symbol.upper(), "STAND_ASIDE", close,
                                   None, None, None, None, [why])

    days = SETTINGS["ma"]
    if len(bars) < days + 30:
        return stand_aside("Not enough history")
    average = sma(closes, days)
    atr = wilder_atr(bars, config.atr_days)
    if average is None or atr is None or close <= 0:
        return stand_aside("Indicators unavailable")
    if close <= average:
        return stand_aside("Below the trend average")
    # Optional confirmation: the average itself must be rising, which filters
    # the chop where price crosses a flat line repeatedly.
    confirm = SETTINGS["confirm"]
    if confirm:
        earlier = sma(closes[:-confirm], days)
        if earlier is None or average <= earlier:
            return stand_aside("Trend average not rising")
    # The stop sits below the TREND LINE, not below the entry, so leaving the
    # trend is what closes the position - the exit a trend system needs, built
    # out of the stop the engine already honours.
    stop = average - SETTINGS["stop_atr"] * atr
    if stop <= 0 or stop >= close:
        return stand_aside("Stop would be non-positive or above price")
    return MeanReversionSignal(symbol.upper(), "BUY", close, stop,
                               None, average, atr / close, [])


portfolio_module.mean_reversion_signal = _signal


def load(meme_only=False):
    out = {}
    for path in sorted(CRYPTO.glob("*.csv")):
        symbol = path.stem.replace("-", "/")
        if meme_only and not any(m in symbol for m in MEME):
            continue
        bars = load_bars(path)
        if len(bars) >= 260:
            out[symbol] = bars
    return out


def buy_and_hold(series):
    """Equal weight, one purchase, charged once. The bar to clear."""
    total = 0.0
    for bars in series.values():
        total += (bars[-1].close / bars[0].close) * (1 - 0.0025)
    return total / len(series) - 1.0 if series else 0.0


def run(series, policy, trade_from=None):
    return run_portfolio(series, starting_cash=CASH, policy=policy, costs=COSTS,
                         entry_rule="mean_reversion", mr_config=BASE,
                         trade_from=trade_from)


def line(label, series, policy):
    whole = run(series, policy)
    second = run(series, policy, SPLIT)
    at_split = None
    for stamp, equity in whole.equity_curve:
        if stamp.date() <= SPLIT:
            at_split = equity
    first = (at_split / CASH - 1.0) if at_split else 0.0
    wins = sum(1 for t in whole.trades if t.net_pnl > 0)
    print("{0:<30}{1:>10.1%}{2:>9.1%}{3:>11.1%}{4:>10.1%}{5:>8}{6:>7.0%}".format(
        label, whole.equity / CASH - 1.0, whole.max_drawdown, first,
        second.equity / CASH - 1.0, len(whole.trades),
        wins / len(whole.trades) if whole.trades else 0.0), flush=True)


def header(title):
    print("\n=== {0} ===".format(title), flush=True)
    h = "{0:<30}{1:>10}{2:>9}{3:>11}{4:>10}{5:>8}{6:>7}".format(
        "variant", "total", "maxDD", "to 2024-06", "since", "trades", "win%")
    print(h, flush=True)
    print("-" * len(h), flush=True)


def main():
    series = load()
    wide = RiskPolicy(max_per_bucket=25, max_open_positions=12)
    print("crypto pairs {0}".format(len(series)), flush=True)
    print("equal-weight buy and hold over the same window: {0:+.1%}".format(
        buy_and_hold(series)), flush=True)

    header("trend length (stop 3 ATR below the line)")
    for days in (20, 50, 100, 200):
        SETTINGS["ma"] = days
        line("above {0}-day average".format(days), series, wide)

    SETTINGS["ma"] = 50
    header("stop distance below the trend line (50-day)")
    for multiple in (1.0, 2.0, 3.0, 5.0):
        SETTINGS["stop_atr"] = multiple
        line("stop {0} ATR below line".format(multiple), series, wide)

    SETTINGS["stop_atr"] = 3.0
    header("require the average to be RISING")
    for confirm in (0, 10, 20):
        SETTINGS["confirm"] = confirm
        line("rising over {0} bars".format(confirm) if confirm else "no confirmation",
             series, wide)

    SETTINGS["confirm"] = 0
    header("how many coins at once")
    for bucket, positions in ((1, 12), (4, 12), (25, 6), (25, 12)):
        line("{0}/bucket, {1} positions".format(bucket, positions), series,
             RiskPolicy(max_per_bucket=bucket, max_open_positions=positions))

    memes = load(meme_only=True)
    if memes:
        header("MEME COINS ONLY ({0})".format(", ".join(sorted(memes))))
        print("  buy and hold: {0:+.1%}".format(buy_and_hold(memes)), flush=True)
        for days in (20, 50, 100):
            SETTINGS["ma"] = days
            line("above {0}-day average".format(days), memes, wide)


if __name__ == "__main__":
    main()
