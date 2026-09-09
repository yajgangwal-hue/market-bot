"""Re-tune the rule now that the trend filter is off.

Every parameter in MeanReversionConfig - rsi_entry 35, rsi_exit 60,
stop_atr_multiple 2.5, max_holding_bars 20, max_atr_fraction 0.035 - was
chosen by sweeps run WITH the 200-day filter in place. The comments in that
file document each sweep and each is honest about its own evidence. But every
one of them optimised a different strategy from the one now shipped: the
filter was doing a large part of the selection, and removing it changes what
the other dials are compensating for.

The most likely place for the optimum to have moved is the volatility ceiling
and the stop. With the filter on, a stock oversold AND above its 200-day
average is a pullback in an uptrend; with it off, the same RSI reading is
often a stock in a genuine decline. Those want different stops and a different
tolerance for volatility, and the shipped values were tuned against the first
population.

DISCIPLINE. One dial at a time from the shipped baseline, both halves
reported, and nothing ships that does not beat the baseline on BOTH. Sweeping
five dials over one dataset guarantees that the best-looking cell is partly
luck; the both-halves rule is what has kept this project from shipping that
kind of result all week, and it stays.
"""
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from event_aware_trader import portfolio as portfolio_module
from event_aware_trader.data import load_bars
from event_aware_trader.mean_reversion import MeanReversionConfig
from event_aware_trader.mean_reversion import conviction as shipped_conviction
from event_aware_trader.portfolio import run_portfolio
from event_aware_trader.risk import RiskPolicy
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto

DEEP = Path(__file__).with_name("deep")
SPLIT = date(2021, 3, 1)
CASH = 100_000.0
_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-400:], c)
_conv = {}


def conviction(symbol, history):
    key = (symbol, len(history))
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def load():
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        path = DEEP / (symbol + ".csv")
        if path.exists():
            bars = load_bars(path)
            if len(bars) >= 500:
                out[symbol] = bars
    return out


def concurrency(report):
    days = {}
    for trade in report.trades:
        day, last = trade.entry_time.date(), trade.exit_time.date()
        while day <= last:
            days[day] = days.get(day, 0) + 1
            day += timedelta(days=1)
    stamps = [s.date() for s, _ in report.equity_curve]
    live = [days.get(d, 0) for d in stamps] or [0]
    return sum(live) / len(live)


BASE = None


def row(label, series, config):
    whole = run_portfolio(series, starting_cash=CASH, policy=RiskPolicy(),
                          entry_rule="mean_reversion", mr_config=config,
                          conviction=conviction)
    second = run_portfolio(series, starting_cash=CASH, policy=RiskPolicy(),
                           entry_rule="mean_reversion", mr_config=config,
                           conviction=conviction, trade_from=SPLIT)
    at = None
    for stamp, equity in whole.equity_curve:
        if stamp.date() <= SPLIT:
            at = equity
    first = at / CASH - 1.0
    late = second.equity / CASH - 1.0
    mark = ""
    if BASE is not None:
        mark = "  <-- beats baseline on BOTH" if (
            first > BASE[0] and late > BASE[1]) else ""
    print("{0:<30}{1:>10.1%}{2:>9.1%}{3:>10.1%}{4:>10.1%}{5:>8}{6:>7.1f}{7}".format(
        label, whole.equity / CASH - 1.0, whole.max_drawdown, first, late,
        len(whole.trades), concurrency(whole), mark), flush=True)
    return first, late


def header(title):
    print("\n=== {0} ===".format(title), flush=True)
    h = "{0:<30}{1:>10}{2:>9}{3:>10}{4:>10}{5:>8}{6:>7}".format(
        "variant", "decade", "maxDD", "1st half", "2nd half", "trades", "avgPos")
    print(h, flush=True)
    print("-" * len(h), flush=True)


def main():
    global BASE
    series = load()
    shipped = MeanReversionConfig()
    header("baseline (trend filter off, everything else as shipped)")
    BASE = row("SHIPPED", series, shipped)

    header("entry threshold - tuned when the filter still selected for us")
    for value in (25.0, 30.0, 35.0, 40.0, 45.0):
        row("rsi_entry {0:.0f}".format(value), series,
            replace(shipped, rsi_entry=value))

    header("exit threshold")
    for value in (50.0, 55.0, 60.0, 65.0, 70.0):
        row("rsi_exit {0:.0f}".format(value), series,
            replace(shipped, rsi_exit=value))

    header("stop distance - the population it protects has changed")
    for value in (1.5, 2.0, 2.5, 3.0, 4.0):
        row("stop {0} ATR".format(value), series,
            replace(shipped, stop_atr_multiple=value))

    header("holding cap")
    for value in (10, 15, 20, 30, 40):
        row("hold {0} days".format(value), series,
            replace(shipped, max_holding_bars=value))

    header("volatility ceiling - most likely to have moved")
    for value in (0.02, 0.025, 0.035, 0.05, 0.08, None):
        label = "atr ceiling {0}".format(
            "none" if value is None else "{0:.1%}".format(value))
        row(label, series, replace(shipped, max_atr_fraction=value))


if __name__ == "__main__":
    main()
