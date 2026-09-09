"""Is the tighter stop real, or the best cell out of twenty-five tries?

The re-tune swept five dials over one decade. Two variants beat the baseline
on both halves, which is roughly what pure luck would produce from that many
attempts, so neither is evidence on its own. They are separated by asking
different questions of them.

rsi_entry 45 is rejected already: its first-half column reads 18.7, 44.2,
59.9, 49.0, 82.4 - non-monotone, with 40 WORSE than the shipped 35 before 45
leaps. That is a lucky cell.

The stop is the opposite shape. Across the whole tested range tighter is
better at every step - 275.6, 235.5, 157.4, 153.9, 77.3 - and the drawdown at
1.5 ATR is BETTER than the baseline. It also has a mechanism that was written
down before the numbers arrived: with the trend filter off the rule now buys
stocks in genuine downtrends, where a tight stop cuts a falling knife fast and
a wide one lets it keep falling.

Three things have to hold before that ships.

FINER GRID, to find whether there is a peak or whether the sweep simply
stopped at its own boundary. A parameter that keeps improving to the edge of
what was tested usually means the range was wrong, and shipping the edge value
is how a strategy ends up at an extreme nobody chose.

THE CRASH TEST, which is the one that matters. A tight stop in a bear market
means being stopped out repeatedly on the way down. The thirty-year window
contains two, and the shipped configuration already gives up -25.8% in 2008
now that the trend filter is off. If a tighter stop makes that materially
worse it is not a profit improvement, it is a leverage increase wearing one.

COST SENSITIVITY. A tighter stop means more round trips. At 6bps a side that
is a real charge, and a result that only survives at optimistic costs is not a
result.
"""
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from event_aware_trader import portfolio as portfolio_module
from event_aware_trader.data import load_bars
from event_aware_trader.mean_reversion import MeanReversionConfig
from event_aware_trader.mean_reversion import conviction as shipped_conviction
from event_aware_trader.portfolio import run_portfolio
from event_aware_trader.risk import CostModel, RiskPolicy
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto

HERE = Path(__file__).parent
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
    days = {}
    for trade in report.trades:
        day, last = trade.entry_time.date(), trade.exit_time.date()
        while day <= last:
            days[day] = days.get(day, 0) + 1
            day += timedelta(days=1)
    stamps = [s.date() for s, _ in report.equity_curve]
    live = [days.get(d, 0) for d in stamps] or [0]
    return sum(live) / len(live)


def year_returns(curve):
    last = {}
    for stamp, equity in curve:
        last[stamp.year] = equity
    out, previous = {}, CASH
    for year in sorted(last):
        out[year] = last[year] / previous - 1.0
        previous = last[year]
    return out


def go(series, config, costs=CostModel(), trade_from=None):
    return run_portfolio(series, starting_cash=CASH, policy=RiskPolicy(),
                         costs=costs, entry_rule="mean_reversion",
                         mr_config=config, conviction=conviction,
                         trade_from=trade_from)


def main():
    shipped = MeanReversionConfig()
    decade = load("deep")

    print("=== FINER GRID on the decade: is there a peak, or a boundary? ===",
          flush=True)
    head = "{0:<22}{1:>10}{2:>9}{3:>10}{4:>10}{5:>8}{6:>7}".format(
        "stop", "decade", "maxDD", "1st half", "2nd half", "trades", "avgPos")
    print(head, flush=True)
    print("-" * len(head), flush=True)
    for multiple in (0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5):
        config = replace(shipped, stop_atr_multiple=multiple)
        whole = go(decade, config)
        second = go(decade, config, trade_from=SPLIT)
        at = None
        for stamp, equity in whole.equity_curve:
            if stamp.date() <= SPLIT:
                at = equity
        tag = "  <- SHIPPED" if multiple == shipped.stop_atr_multiple else ""
        print("{0:<22}{1:>10.1%}{2:>9.1%}{3:>10.1%}{4:>10.1%}{5:>8}{6:>7.1f}{7}".format(
            "{0} ATR".format(multiple), whole.equity / CASH - 1.0,
            whole.max_drawdown, at / CASH - 1.0, second.equity / CASH - 1.0,
            len(whole.trades), concurrency(whole), tag), flush=True)

    print("\n=== COST SENSITIVITY: a tighter stop trades more ===", flush=True)
    head2 = "{0:<22}{1:>12}{2:>12}{3:>12}".format(
        "one-way cost", "stop 2.5", "stop 1.5", "difference")
    print(head2, flush=True)
    print("-" * len(head2), flush=True)
    for bps in (6.0, 9.0, 12.0, 18.0):
        costs = CostModel(half_spread_bps=bps / 3.0, slippage_bps=bps * 2.0 / 3.0)
        wide = go(decade, shipped, costs).equity / CASH - 1.0
        tight = go(decade, replace(shipped, stop_atr_multiple=1.5), costs)
        tight_return = tight.equity / CASH - 1.0
        print("{0:<22}{1:>12.1%}{2:>12.1%}{3:>+12.1f}".format(
            "{0:.0f} bps".format(bps), wide, tight_return,
            (tight_return - wide) * 100), flush=True)

    print("\n=== THE CRASH TEST, thirty years ===", flush=True)
    long_series = load("long", since=date(1996, 1, 1))
    head3 = "{0:<22}{1:>9}{2:>9}{3:>9}{4:>9}{5:>9}{6:>7}".format(
        "stop", "CAGR", "maxDD", "2000-02", "2008", "2022", "avgPos")
    print(head3, flush=True)
    print("-" * len(head3), flush=True)
    for multiple in (1.0, 1.5, 2.0, 2.5):
        config = replace(shipped, stop_atr_multiple=multiple)
        report = go(long_series, config)
        curve = report.equity_curve
        years = (curve[-1][0] - curve[0][0]).days / 365.25
        cagr = (report.equity / CASH) ** (1 / years) - 1.0 if report.equity > 0 else -1.0
        by_year = year_returns(curve)
        dot_com = 1.0
        for year in (2000, 2001, 2002):
            dot_com *= (1.0 + by_year.get(year, 0.0))
        tag = "  <- SHIPPED" if multiple == shipped.stop_atr_multiple else ""
        print("{0:<22}{1:>9.2%}{2:>9.1%}{3:>9.1%}{4:>9.1%}{5:>9.1%}{6:>7.1f}{7}".format(
            "{0} ATR".format(multiple), cagr, report.max_drawdown,
            dot_com - 1.0, by_year.get(2008, 0.0), by_year.get(2022, 0.0),
            concurrency(report), tag), flush=True)


if __name__ == "__main__":
    main()
