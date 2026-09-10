"""Two untested levers that act on EXPOSURE rather than on stock selection.

Every parameter inside the rule has been swept and none survived. These two do
not touch the rule at all - they change how much of the account is at risk,
which is a different question and one this project has never asked.

1. VOLATILITY TARGETING. Scale position size by target_vol / realised_vol, so
   the book carries roughly constant risk instead of constant dollars. When
   the market is calm it leans in; when the market is violent it steps back.
   This is among the better-supported findings in the literature (Moreira &
   Muir, volatility-managed portfolios) and it has a plain mechanism: realised
   volatility is strongly autocorrelated - a violent week predicts a violent
   week - while returns are not, so scaling on volatility uses the part that
   IS predictable.

   The bot currently sizes by risk-per-trade over stop distance, which
   equalises risk ACROSS positions at a point in time but does nothing about
   risk across TIME. In a calm year and a panic year it carries the same
   nominal exposure.

2. A MARKET REGIME FILTER. Refuse new entries while SPY is below its own
   200-day average. This is NOT the per-stock trend filter that already
   ships - that asks whether each stock is in an uptrend, this asks whether
   the MARKET is - and the distinction matters because the two can disagree
   for months. It is also exactly the shape that worked on crypto, where
   holding the basket only while BTC was above its average cut the 2018 bear
   from -74% to -40% and 2022 from -79% to -24%.

Both are applied through the conviction callable and a signal wrapper, so the
rule itself is untouched and any difference is attributable to exposure alone.

Judged on the decade with both halves AND on thirty years including two real
bear markets, because that is the window that has killed every promising
decade result this week.
"""
from datetime import date, timedelta
from pathlib import Path

from event_aware_trader import portfolio as portfolio_module
from event_aware_trader.data import load_bars
from event_aware_trader.indicators import sma
from event_aware_trader.mean_reversion import MeanReversionSignal
from event_aware_trader.mean_reversion import conviction as drawdown_conviction
from event_aware_trader.portfolio import run_portfolio
from event_aware_trader.risk import RiskPolicy
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto

HERE = Path(__file__).parent
CASH = 100_000.0
WINDOW = 400

_full = portfolio_module.mean_reversion_signal
_base = lambda s, h, c: _full(s, h[-WINDOW:], c)
portfolio_module.mean_reversion_signal = _base
_conv = {}


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


def market_tables(series, vol_days=20, trend_days=200):
    """Realised SPY volatility and its 200-day trend, by DATE.

    Both use data up to and including that date, never after it, so a lookup
    at the signal bar sees only what the bot would have seen.
    """
    spy = series.get("SPY")
    if not spy:
        return {}, {}
    closes = [b.close for b in spy]
    vol, trend = {}, {}
    for i, bar in enumerate(spy):
        day = bar.timestamp.date()
        if i >= vol_days:
            rets = []
            for k in range(i - vol_days + 1, i + 1):
                if closes[k - 1] > 0:
                    rets.append(closes[k] / closes[k - 1] - 1.0)
            if len(rets) > 2:
                mean = sum(rets) / len(rets)
                var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
                vol[day] = (var ** 0.5) * (252 ** 0.5)
        if i >= trend_days:
            average = sma(closes[:i + 1], trend_days)
            if average is not None:
                trend[day] = closes[i] > average
    return vol, trend


def vol_scaled(vol_by_day, target, floor, ceiling, with_drawdown=True):
    """target_vol / realised_vol, clamped, times the shipped conviction."""
    def weights(symbol, history):
        key = (symbol, len(history))
        base = _conv.get(key)
        if base is None:
            base = _conv[key] = drawdown_conviction(history[-40:])
        scale = base if with_drawdown else 1.0
        realised = vol_by_day.get(history[-1].timestamp.date())
        if realised and realised > 0:
            scale *= max(floor, min(ceiling, target / realised))
        return scale
    return weights


def plain_conviction(symbol, history):
    key = (symbol, len(history))
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = drawdown_conviction(history[-40:])
    return hit


def market_gated(trend_by_day):
    """Refuse new entries while the MARKET is below its own 200-day."""
    def rule(symbol, history, config):
        signal = _base(symbol, history, config)
        if signal.is_buy:
            day = history[-1].timestamp.date()
            if trend_by_day.get(day) is False:
                return MeanReversionSignal(
                    symbol.upper(), "STAND_ASIDE", signal.close, None, None,
                    None, None, ["Market below its 200-day"])
        return signal
    return rule


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


def run(series, conviction, signal=None, trade_from=None):
    portfolio_module.mean_reversion_signal = signal or _base
    try:
        return run_portfolio(series, starting_cash=CASH, policy=RiskPolicy(),
                             entry_rule="mean_reversion", conviction=conviction,
                             trade_from=trade_from)
    finally:
        portfolio_module.mean_reversion_signal = _base


def line(label, series, conviction, signal=None, split=None, base=None):
    whole = run(series, conviction, signal)
    curve = whole.equity_curve
    years = (curve[-1][0] - curve[0][0]).days / 365.25 if len(curve) > 1 else 1
    cagr = ((whole.equity / CASH) ** (1 / years) - 1.0
            if years > 0 and whole.equity > 0 else -1.0)
    first = late = 0.0
    if split:
        second = run(series, conviction, signal, split)
        at = None
        for stamp, value in curve:
            if stamp.date() <= split:
                at = value
        first = (at / CASH - 1.0) if at else 0.0
        late = second.equity / CASH - 1.0
    mark = ""
    if base and split and first > base[0] and late > base[1]:
        mark = "  <- beats baseline BOTH halves"
    print("{0:<32}{1:>10.1%}{2:>8.2%}{3:>9.1%}{4:>10.1%}{5:>10.1%}{6:>7}{7:>7.1f}{8}".format(
        label, whole.equity / CASH - 1.0, cagr, whole.max_drawdown, first, late,
        len(whole.trades), concurrency(whole), mark), flush=True)
    return first, late


def header(title):
    print("\n=== {0} ===".format(title), flush=True)
    h = "{0:<32}{1:>10}{2:>8}{3:>9}{4:>10}{5:>10}{6:>7}{7:>7}".format(
        "variant", "total", "CAGR", "maxDD", "1st half", "2nd half", "trades", "avgPos")
    print(h, flush=True)
    print("-" * len(h), flush=True)


def suite(series, split, label):
    vol_by_day, trend_by_day = market_tables(series)
    if not vol_by_day:
        print("no SPY in {0}; skipping".format(label), flush=True)
        return
    ordered = sorted(vol_by_day.values())
    median_vol = ordered[len(ordered) // 2]
    print("\n#### {0} - median SPY realised vol {1:.1%}".format(label, median_vol),
          flush=True)

    header("baseline")
    base = line("shipped", series, plain_conviction, None, split)

    header("volatility targeting (x drawdown conviction)")
    for target in (0.10, 0.12, 0.15, 0.20):
        line("target {0:.0%} vol, clamp 0.5-2.0x".format(target), series,
             vol_scaled(vol_by_day, target, 0.5, 2.0), None, split, base)
    line("target 12%, clamp 0.5-1.0x (cut only)", series,
         vol_scaled(vol_by_day, 0.12, 0.5, 1.0), None, split, base)

    header("market regime filter (SPY vs its own 200-day)")
    line("no entries while SPY below 200d", series, plain_conviction,
         market_gated(trend_by_day), split, base)
    line("market gate + vol target 12%", series,
         vol_scaled(vol_by_day, 0.12, 0.5, 2.0),
         market_gated(trend_by_day), split, base)


def main():
    suite(load("deep"), date(2021, 3, 1), "DECADE 2016-2026")
    suite(load("long", since=date(1996, 1, 1)), date(2011, 1, 1),
          "THIRTY YEARS 1996-2026")


if __name__ == "__main__":
    main()
