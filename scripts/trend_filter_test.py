"""The 200-day filter: the last untested lever for holding more positions.

Today the bot holds one position, and the reason is countable rather than
arguable. Of 230 symbols, exactly ONE qualifies. Seventy-five are below their
200-day average and the trend filter rejects every one - including TJX at RSI
19.3, SYK at 24.7 and RCL at 25.2, all deeply oversold. The position cap of 12
is not binding and never was.

So the filter is the constraint, and loosening it is the only remaining way to
hold more names. The question is what it costs.

WHY THIS HAS TO BE TESTED AGAINST 2008 AND NOT ONLY THE DECADE.

The 30-year test showed this filter is the entire reason the strategy survives
crashes: down 8.7% in 2008 against the market's 38.3%, roughly flat through
the dot-com bust, 30-year maximum drawdown of 16.3%. The mechanism is exactly
what is being proposed for removal - in a sustained decline almost nothing is
above its 200-day average, so the rule stops buying and sits in cash.

Loosening it is therefore not a return trade-off, it is a survival one. A
variant that looks better on 2016-2026 and turns 2008 into a 40% loss is a
worse strategy that happens to have been measured on a kind decade. Both
windows are reported, and the crash years are broken out on their own.

Variants:
  200-day          shipped
  150 / 100 / 50   shorter trend, more names qualify
  none             oversold alone, no trend condition at all
  within 5%        above the average OR no more than 5% below it - the
                   softened version, which admits a stock that has just
                   crossed while still refusing one in a real downtrend

Everything runs on the validated 400-bar signal window, which reproduces
full-history results to the cent.
"""
from dataclasses import replace
from datetime import date
from pathlib import Path

from event_aware_trader import portfolio as portfolio_module
from event_aware_trader.data import load_bars
from event_aware_trader.indicators import rsi, sma, wilder_atr
from event_aware_trader.mean_reversion import (
    MeanReversionConfig, MeanReversionSignal, conviction as shipped_conviction)
from event_aware_trader.portfolio import run_portfolio
from event_aware_trader.risk import RiskPolicy
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto

HERE = Path(__file__).parent
CASH = 100_000.0
WINDOW = 400
CONFIG = MeanReversionConfig()

# (trend_days, tolerance) - tolerance 0.05 means "or within 5% below the line"
MODE = {"days": 200, "tol": 0.0}
_conv = {}


def conviction(symbol, history):
    key = (symbol, len(history))
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def _signal(symbol, bars, config):
    """The shipped rule with the trend condition made adjustable."""
    bars = bars[-WINDOW:]
    closes = [b.close for b in bars]
    close = closes[-1] if closes else 0.0

    def aside(why):
        return MeanReversionSignal(symbol.upper(), "STAND_ASIDE", close,
                                   None, None, None, None, [why])

    if len(bars) < config.minimum_history:
        return aside("Not enough history")
    strength = rsi(closes, config.rsi_period)
    atr = wilder_atr(bars, config.atr_days)
    if strength is None or atr is None or close <= 0:
        return aside("Indicators unavailable")
    if close < config.min_price:
        return aside("Price below floor")
    dollar_volume = sum(b.close * b.volume for b in bars[-20:]) / 20.0
    if dollar_volume < config.min_average_dollar_volume:
        return aside("Illiquid")
    if strength > config.rsi_entry:
        return aside("RSI not low enough")
    fraction = atr / close
    if config.max_atr_fraction is not None and fraction > config.max_atr_fraction:
        return aside("Too volatile")
    days = MODE["days"]
    if days:
        average = sma(closes, days)
        if average is None:
            return aside("No trend average")
        floor_price = average * (1.0 - MODE["tol"])
        if close <= floor_price:
            return aside("Below the trend average")
    stop = close - config.stop_atr_multiple * atr
    if stop <= 0 or stop >= close:
        return aside("Stop unusable")
    return MeanReversionSignal(symbol.upper(), "BUY", close, stop,
                               strength, None, fraction, [])


portfolio_module.mean_reversion_signal = _signal


def load(folder, since=None):
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        path = HERE / folder / (symbol + ".csv")
        if not path.exists():
            continue
        bars = load_bars(path)
        if since:
            bars = [b for b in bars if b.timestamp.date() >= since]
        if len(bars) >= 400:
            out[symbol] = bars
    return out


def concurrency(report):
    from datetime import timedelta
    days = {}
    for trade in report.trades:
        day, last = trade.entry_time.date(), trade.exit_time.date()
        while day <= last:
            days[day] = days.get(day, 0) + 1
            day += timedelta(days=1)
    stamps = [s.date() for s, _ in report.equity_curve]
    live = [days.get(d, 0) for d in stamps] or [0]
    return sum(live) / len(live), max(live)


def year_returns(curve):
    last = {}
    for stamp, equity in curve:
        last[stamp.year] = equity
    out, previous = {}, CASH
    for year in sorted(last):
        out[year] = last[year] / previous - 1.0
        previous = last[year]
    return out


def run(series, trade_from=None):
    return run_portfolio(series, starting_cash=CASH, policy=RiskPolicy(),
                         entry_rule="mean_reversion", conviction=conviction,
                         trade_from=trade_from)


def main():
    variants = [("200-day  SHIPPED", 200, 0.0),
                ("150-day", 150, 0.0),
                ("100-day", 100, 0.0),
                ("50-day", 50, 0.0),
                ("200-day, within 5%", 200, 0.05),
                ("200-day, within 10%", 200, 0.10),
                ("no trend filter", 0, 0.0)]

    decade = load("deep")
    print("=== DECADE 2016-2026, {0} symbols ===".format(len(decade)), flush=True)
    head = "{0:<24}{1:>10}{2:>9}{3:>10}{4:>10}{5:>8}{6:>8}{7:>6}".format(
        "trend filter", "decade", "maxDD", "1st half", "2nd half", "trades",
        "avgPos", "peak")
    print(head, flush=True)
    print("-" * len(head), flush=True)
    for label, days, tol in variants:
        MODE["days"], MODE["tol"] = days, tol
        whole = run(decade)
        second = run(decade, date(2021, 3, 1))
        at_split = None
        for stamp, equity in whole.equity_curve:
            if stamp.date() <= date(2021, 3, 1):
                at_split = equity
        avg, peak = concurrency(whole)
        print("{0:<24}{1:>10.1%}{2:>9.1%}{3:>10.1%}{4:>10.1%}{5:>8}{6:>8.1f}{7:>6}".format(
            label, whole.equity / CASH - 1.0, whole.max_drawdown,
            at_split / CASH - 1.0, second.equity / CASH - 1.0,
            len(whole.trades), avg, peak), flush=True)

    long_series = load("long", since=date(1996, 1, 1))
    print("\n=== THIRTY YEARS, and what each does in a crash ===", flush=True)
    head2 = "{0:<24}{1:>9}{2:>9}{3:>9}{4:>9}{5:>9}{6:>8}".format(
        "trend filter", "CAGR", "maxDD", "2000-02", "2008", "2022", "avgPos")
    print(head2, flush=True)
    print("-" * len(head2), flush=True)
    for label, days, tol in variants:
        MODE["days"], MODE["tol"] = days, tol
        report = run(long_series)
        curve = report.equity_curve
        years = (curve[-1][0] - curve[0][0]).days / 365.25
        cagr = (report.equity / CASH) ** (1 / years) - 1.0 if report.equity > 0 else -1
        by_year = year_returns(curve)
        dot_com = 1.0
        for year in (2000, 2001, 2002):
            dot_com *= (1.0 + by_year.get(year, 0.0))
        avg, _ = concurrency(report)
        print("{0:<24}{1:>9.2%}{2:>9.1%}{3:>9.1%}{4:>9.1%}{5:>9.1%}{6:>8.1f}".format(
            label, cagr, report.max_drawdown, dot_com - 1.0,
            by_year.get(2008, 0.0), by_year.get(2022, 0.0), avg), flush=True)


if __name__ == "__main__":
    main()
