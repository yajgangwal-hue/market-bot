"""Two names per correlation bucket at half size: does breadth pay?

The measurement that prompted this: the rule holds 4.6 of 12 allowed positions
on average, and 36% of qualifying signals were rejected because another
position already occupied that correlation bucket - nearly twice as many as
the position cap rejected. So the bucket rule, not the cap, is what keeps
concurrency at four.

The proposal is to allow two names per bucket at half the risk each. Sector
exposure is then unchanged in the saturated case while the number of names
roughly doubles, which is precisely the breadth term in Grinold's law.

Three things have to be separated, or a win means nothing:

  * SIZE. Half-size bets alone change the trade SET, because a smaller
    position leaves cash for the next signal. Variant 2 holds the bucket rule
    at one and halves size, so any improvement that comes from bet size alone
    shows up there and not in the comparison.
  * EXPOSURE. Two per bucket at FULL size is simply more money at risk in a
    sector. Included as a diagnostic, not as a candidate.
  * THE BUCKETS THEMSELVES. If the sector map carries no information then
    shuffling symbols into random buckets should do just as well. That is the
    random control, and it is the one that caught the conviction-weighting
    artefact last time.

The bar to ship: beat the shipped config on BOTH halves, and beat the
half-size control on both halves.

SPEED. The signal is O(n^2) per symbol - every bar rebuilds the close list and
re-smooths RSI and ATR from the start of the series - so one decade run over
230 symbols takes half an hour, and nine of them take a working day. But the
variants differ only in SIZING and CAPS; the signal at a given symbol and bar
is identical in all of them. Memoising it on (symbol, bars seen) makes the
first run pay the full cost and the remaining eight nearly free. This is exact
rather than an approximation: `run_portfolio` appends every bar to history
whether or not it trades, so a given length always names the same bars.
"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from event_aware_trader import portfolio as portfolio_module
from event_aware_trader.data import load_bars
from event_aware_trader.mean_reversion import conviction as shipped_conviction
from event_aware_trader.portfolio import run_portfolio
from event_aware_trader.risk import RiskPolicy
from event_aware_trader.strategy import CORRELATION_BUCKETS, DEFAULT_UNIVERSE, is_crypto

DEEP = Path(__file__).with_name("deep")
SPLIT = date(2021, 3, 1)          # the decade's midpoint
CASH = 100_000.0

_signals = {}
_convictions = {}
_uncached = portfolio_module.mean_reversion_signal


def cached_signal(symbol, history, config):
    key = (symbol, len(history))
    hit = _signals.get(key)
    if hit is None:
        hit = _signals[key] = _uncached(symbol, history, config)
    return hit


def cached_conviction(symbol, history):
    key = (symbol, len(history))
    hit = _convictions.get(key)
    if hit is None:
        hit = _convictions[key] = shipped_conviction(history)
    return hit


portfolio_module.mean_reversion_signal = cached_signal


def load():
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        path = DEEP / (symbol + ".csv")
        if not path.exists():
            continue
        bars = load_bars(path)
        if len(bars) >= 500:
            out[symbol] = bars
    return out


def concurrency(report):
    """Average open positions per trading day, counted from the trade log.

    Deployed-capital fraction was the earlier proxy; this counts the thing the
    request actually asked about.
    """
    days = {}
    for trade in report.trades:
        day = trade.entry_time.date()
        last = trade.exit_time.date()
        while day <= last:
            days[day] = days.get(day, 0) + 1
            day += timedelta(days=1)
    stamps = [stamp.date() for stamp, _ in report.equity_curve]
    if not stamps:
        return 0.0, 0, 0.0
    live = [days.get(d, 0) for d in stamps]
    return (sum(live) / len(live), max(live),
            sum(1 for n in live if n == 0) / len(live))


def run(series, policy, trade_from=None):
    return run_portfolio(series, starting_cash=CASH, policy=policy,
                         entry_rule="mean_reversion", conviction=cached_conviction,
                         trade_from=trade_from)


def cagr(report):
    curve = report.equity_curve
    if len(curve) < 2:
        return 0.0
    years = (curve[-1][0] - curve[0][0]).days / 365.25
    if years <= 0:
        return 0.0
    return (report.equity / report.starting_cash) ** (1.0 / years) - 1.0


def line(label, series, policy):
    whole = run(series, policy)
    second = run(series, policy, SPLIT)
    at_split = None
    for stamp, equity in whole.equity_curve:
        if stamp.date() <= SPLIT:
            at_split = equity
    first_half = (at_split / CASH - 1.0) if at_split else 0.0
    avg, peak, idle = concurrency(whole)
    print("{0:<30}{1:>9.1%}{2:>8.2%}{3:>9.1%}{4:>10.1%}{5:>10.1%}{6:>8}{7:>8.1f}{8:>6}{9:>7.0%}".format(
        label, whole.equity / CASH - 1.0, cagr(whole), whole.max_drawdown,
        first_half, second.equity / CASH - 1.0,
        len(whole.trades), avg, peak, idle), flush=True)


def main():
    series = load()
    print("symbols {0}\n".format(len(series)), flush=True)
    header = "{0:<30}{1:>9}{2:>8}{3:>9}{4:>10}{5:>10}{6:>8}{7:>8}{8:>6}{9:>7}".format(
        "variant", "decade", "CAGR", "maxDD", "1st half", "2nd half",
        "trades", "avgPos", "peak", "idle")
    print(header, flush=True)
    print("-" * len(header), flush=True)

    line("1/bucket 0.50%  SHIPPED", series, RiskPolicy())
    line("1/bucket 0.25%  size ctrl", series, RiskPolicy(risk_per_trade=0.0025))
    line("2/bucket 0.25%  PROPOSAL", series,
         RiskPolicy(risk_per_trade=0.0025, max_per_bucket=2))
    line("2/bucket 0.50%  more expo", series, RiskPolicy(max_per_bucket=2))
    line("3/bucket 0.167%", series,
         RiskPolicy(risk_per_trade=0.00167, max_per_bucket=3))
    line("3/bucket 0.50%  more expo", series, RiskPolicy(max_per_bucket=3))

    print("\nrandom bucket maps - same shape, sectors shuffled:", flush=True)
    real = dict(CORRELATION_BUCKETS)
    names = sorted(real)
    labels = [real[n] for n in names]
    try:
        for seed in (7, 19, 41):
            gen = random.Random(seed)
            shuffled = list(labels)
            gen.shuffle(shuffled)
            portfolio_module.CORRELATION_BUCKETS = dict(zip(names, shuffled))
            line("  random buckets seed {0}".format(seed), series,
                 RiskPolicy(risk_per_trade=0.0025, max_per_bucket=2))
    finally:
        portfolio_module.CORRELATION_BUCKETS = real


if __name__ == "__main__":
    main()
