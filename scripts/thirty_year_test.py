"""Thirty years, with the idle cash earning what cash actually earned.

The bear test answered the safety question and raised a bigger one. The
strategy survives crises convincingly - down 8.7% in 2008 against the market's
38.3%, roughly flat through the whole dot-com bust, and a 30-year maximum
drawdown of 16.3% that is barely worse than the recent decade's 15.0%.

But its 30-year CAGR is 4.57%, not the 8.02% the 2016-2026 window shows. The
weak years are the bull markets: 1997, 1998 and 1999 returned +1.8%, -1.2% and
+1.6% while the market returned +31.4%, +27.0% and +19.1%.

The reason those years are weak is the reason the cash finding matters. This
rule needs a stock to be oversold AND above its 200-day average, and in a
melt-up almost nothing is oversold - so the account sits in cash. Median idle
cash is 56% of equity.

And in 1997 cash paid 5%.

So the flat-rate estimate used earlier is exactly wrong in the way that
matters: it applies today's rate to a history where the rate moved from 5% to
0.01% and back. This uses the actual 13-week Treasury yield for every day,
which is the only version of this number worth quoting - and it lands hardest
precisely in the decades the strategy is weakest.

Charged at 2bps every time the cash balance moves, as before.
"""
import csv
from datetime import date, datetime
from pathlib import Path

from event_aware_trader import portfolio as portfolio_module
from event_aware_trader.data import load_bars
from event_aware_trader.mean_reversion import conviction as shipped_conviction
from event_aware_trader.portfolio import run_portfolio
from event_aware_trader.risk import RiskPolicy
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto

HERE = Path(__file__).parent
LONG = HERE / "long"
FROM = date(1996, 1, 1)
CASH = 100_000.0
PARK_COST = 0.0002
WINDOW = 400

_full = portfolio_module.mean_reversion_signal
_conv = {}
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-WINDOW:], c)


def conviction(symbol, history):
    key = (symbol, len(history))
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def load():
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        path = LONG / (symbol + ".csv")
        if not path.exists():
            continue
        bars = [b for b in load_bars(path) if b.timestamp.date() >= FROM]
        if len(bars) >= 400:
            out[symbol] = bars
    return out


def tbill_rates():
    """13-week Treasury yield by date, as a decimal. Yahoo quotes percent."""
    rates = {}
    with (HERE / "tbill.csv").open() as handle:
        for row in csv.DictReader(handle):
            rates[date.fromisoformat(row["date"])] = float(row["yield"]) / 100.0
    return rates


def rate_on(rates, day, last):
    """The most recent published yield on or before `day`."""
    for back in range(0, 8):
        probe = date.fromordinal(day.toordinal() - back)
        if probe in rates:
            return rates[probe]
    return last


def parked_sleeve(report, rates):
    """Interest on the idle balance at the rate that actually prevailed."""
    sleeve = 0.0
    charges = 0.0
    previous_stamp = previous_cash = None
    current = 0.05
    by_year = {}
    for stamp, cash in report.cash_curve:
        day = stamp.date()
        current = rate_on(rates, day, current)
        if previous_stamp is not None:
            years = max(0.0, (stamp - previous_stamp).days / 365.25)
            growth = (1.0 + current) ** years - 1.0
            earned = sleeve * growth + previous_cash * growth
            sleeve += earned
            by_year[day.year] = by_year.get(day.year, 0.0) + earned
            moved = abs(cash - previous_cash)
            if moved > 1.0:
                charge = moved * PARK_COST
                sleeve -= charge
                charges += charge
                by_year[day.year] = by_year[day.year] - charge
        previous_stamp, previous_cash = stamp, cash
    return sleeve, charges, by_year


def main():
    series = load()
    print("symbols {0}, from {1}".format(len(series), FROM), flush=True)
    report = run_portfolio(series, starting_cash=CASH, policy=RiskPolicy(),
                           entry_rule="mean_reversion", conviction=conviction)
    rates = tbill_rates()
    sleeve, charges, by_year = parked_sleeve(report, rates)

    curve = report.equity_curve
    years = (curve[-1][0] - curve[0][0]).days / 365.25
    base = (report.equity / CASH) ** (1 / years) - 1.0
    with_cash = ((report.equity + sleeve) / CASH) ** (1 / years) - 1.0

    cash_by_stamp = dict(report.cash_curve)
    shares = sorted(cash_by_stamp.get(s, 0.0) / e for s, e in curve if e > 0)

    print("\nidle cash: median {0:.0%} of equity".format(shares[len(shares) // 2]),
          flush=True)
    print("\n{0:<34}{1:>12}{2:>10}".format("", "total", "CAGR"), flush=True)
    print("-" * 56, flush=True)
    print("{0:<34}{1:>12.1%}{2:>10.2%}".format(
        "as shipped, cash earns nothing", report.equity / CASH - 1.0, base), flush=True)
    print("{0:<34}{1:>12.1%}{2:>10.2%}".format(
        "idle cash in T-bills (actual rates)",
        (report.equity + sleeve) / CASH - 1.0, with_cash), flush=True)
    print("\ninterest earned ${0:,.0f}, trading cost of parking ${1:,.0f}".format(
        sleeve + charges, charges), flush=True)
    print("CAGR gain: {0:+.2f} percentage points a year".format(
        (with_cash - base) * 100), flush=True)
    print("maximum drawdown is UNCHANGED at {0:.1%} - interest cannot lose "
          "money".format(report.max_drawdown), flush=True)

    print("\nwhere the interest lands, by era:", flush=True)
    print("{0:<14}{1:>16}{2:>18}".format("era", "strategy CAGR", "T-bill adds"),
          flush=True)
    print("-" * 48, flush=True)
    last_of_year = {}
    for stamp, equity in curve:
        last_of_year[stamp.year] = equity
    for lo, hi in ((1996, 2001), (2002, 2007), (2008, 2015), (2016, 2026)):
        start = last_of_year.get(lo - 1, CASH)
        end = last_of_year.get(hi)
        if not end or start <= 0:
            continue
        span = hi - lo + 1
        era_cagr = (end / start) ** (1.0 / span) - 1.0
        added = sum(v for y, v in by_year.items() if lo <= y <= hi)
        # Interest as an annualised share of the equity it was earned on.
        mid = (start + end) / 2.0
        print("{0:<14}{1:>15.2%}{2:>17.2f}".format(
            "{0}-{1}".format(lo, hi), era_cagr, (added / span) / mid * 100), flush=True)


if __name__ == "__main__":
    main()
