"""Did removing the trend filter cost SELECTION QUALITY as well as buying breadth?

The first decomposition produced an uncomfortable number. With the filter off,
the sessions this rule holds return LESS than the average session of the same
universe - overnight and intraday both. That is negative selection skill: the
+157.4% would then be beta on the market's own drift, earned on about
three-quarters of the capital, rather than an edge in choosing what to buy.

If that is also true with the filter ON, the finding is about the rule and was
always true. If it is only true with the filter OFF, then the 200-day filter
was doing something no return column revealed - supplying the selection - and
removing it converted a small edge into leveraged drift. That would be a
serious argument for putting it back, and it is not visible in any of the
tables that informed the decision.

Measured per SESSION HELD, against the average session of the same universe
over the same decade, so the comparison controls for the market itself.
"""
from dataclasses import replace
from pathlib import Path

from event_aware_trader import portfolio as portfolio_module
from event_aware_trader.data import load_bars
from event_aware_trader.mean_reversion import MeanReversionConfig
from event_aware_trader.mean_reversion import conviction as shipped_conviction
from event_aware_trader.portfolio import run_portfolio
from event_aware_trader.risk import RiskPolicy
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto

DEEP = Path(__file__).with_name("deep")
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


def legs(bars, start, end):
    overnight = intraday = 0.0
    sessions = 0
    previous = None
    for bar in bars:
        day = bar.timestamp.date()
        if day < start:
            previous = bar.close
            continue
        if day > end:
            break
        if previous and previous > 0 and bar.open > 0:
            overnight += bar.open / previous - 1.0
            intraday += bar.close / bar.open - 1.0
            sessions += 1
        previous = bar.close
    return overnight, intraday, sessions


def analyse(label, series, config):
    report = run_portfolio(series, starting_cash=CASH, policy=RiskPolicy(),
                           entry_rule="mean_reversion", mr_config=config,
                           conviction=conviction)
    overnight = intraday = 0.0
    sessions = 0
    for trade in report.trades:
        bars = series.get(trade.symbol)
        if not bars:
            continue
        on, day, n = legs(bars, trade.entry_time.date(), trade.exit_time.date())
        overnight += on
        intraday += day
        sessions += n
    return {"label": label, "ret": report.equity / CASH - 1.0,
            "trades": len(report.trades), "sessions": sessions,
            "on": overnight / sessions if sessions else 0.0,
            "in": intraday / sessions if sessions else 0.0}


def main():
    series = load()
    uni_on = uni_in = 0.0
    uni_sessions = 0
    for bars in series.values():
        previous = None
        for bar in bars:
            if previous and previous > 0 and bar.open > 0:
                uni_on += bar.open / previous - 1.0
                uni_in += bar.close / bar.open - 1.0
                uni_sessions += 1
            previous = bar.close
    base_on, base_in = uni_on / uni_sessions, uni_in / uni_sessions

    shipped = MeanReversionConfig()
    rows = [analyse("filter OFF (shipped today)", series, shipped),
            analyse("filter ON  (200-day)", series,
                    replace(shipped, trend_ma_days=200))]

    print("Per SESSION HELD vs the average session of the same universe.")
    print("Positive advantage = the rule picked better-than-random days.\n")
    head = "{0:<28}{1:>9}{2:>8}{3:>11}{4:>11}{5:>11}{6:>11}".format(
        "config", "decade", "trades", "overnite", "intraday", "on adv", "in adv")
    print(head, flush=True)
    print("-" * len(head), flush=True)
    for row in rows:
        print("{0:<28}{1:>9.1%}{2:>8}{3:>11.4%}{4:>11.4%}{5:>+11.4%}{6:>+11.4%}".format(
            row["label"], row["ret"], row["trades"], row["on"], row["in"],
            row["on"] - base_on, row["in"] - base_in), flush=True)
    print("{0:<28}{1:>9}{2:>8}{3:>11.4%}{4:>11.4%}".format(
        "the universe (control)", "-", uni_sessions, base_on, base_in), flush=True)
    print("\nuniverse overnight share of its total: {0:.1%}".format(
        uni_on / (uni_on + uni_in)), flush=True)


if __name__ == "__main__":
    main()
