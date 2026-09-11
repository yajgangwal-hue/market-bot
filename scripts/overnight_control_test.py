"""Is the overnight edge real, or am I just selecting stocks that went up?

The top 1% of stocks ranked on trailing overnight return gained +0.287% a
night gross, comfortably clearing the 0.12% round trip, monotone across every
slice and positive in both halves. Before any of that is built, one thing has
to be ruled out.

THE WORRY. The universe is today's 230 names run backwards over ten years, so
it is already the survivors. If "stocks that gap up overnight" is really just
"stocks that went up", then this ranking is picking decade winners with
hindsight and the overnight framing is decoration. Those names would have
risen in every window - overnight AND intraday - and the result would be
survivorship, not an effect.

THE TEST that separates them. For the same selected names, measure BOTH legs:

    overnight   close[t] -> open[t+1]
    intraday    open[t+1] -> close[t+1]

If the selection is picking winners, both legs are elevated together. If the
effect is genuinely OVERNIGHT, the overnight leg is elevated and the intraday
leg is not - and that asymmetry cannot be produced by survivorship, because a
stock that merely went up has no reason to do it between the close and the
open rather than during the day.

The universe average is the reference: +0.0548% overnight, +0.0307% intraday.

A SECOND CONTROL, on the same principle. Rank the identical universe by
trailing INTRADAY return instead, and look at the forward OVERNIGHT return of
those picks. If overnight persistence is a real and specific property, ranking
on the wrong leg should not find it.
"""
from pathlib import Path
from statistics import mean

from event_aware_trader.data import load_bars
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto

DEEP = Path(__file__).with_name("deep")
SPLIT = "2021-03-01"
WINDOW = 120


def load():
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        path = DEEP / (symbol + ".csv")
        if path.exists():
            bars = load_bars(path)
            if len(bars) >= 500:
                out[symbol] = bars
    return out


def legs(bars):
    """Per index: (date, overnight close->open, intraday open->close)."""
    out = []
    for i in range(len(bars) - 1):
        close_now = bars[i].close
        open_next, close_next = bars[i + 1].open, bars[i + 1].close
        if close_now > 0 and open_next > 0 and close_next > 0:
            out.append((bars[i].timestamp.date(),
                        open_next / close_now - 1.0,
                        close_next / open_next - 1.0))
        else:
            out.append((bars[i].timestamp.date(), None, None))
    return out


def main():
    series = load()
    table = {s: legs(b) for s, b in series.items()}
    index_of = {s: {bar.timestamp.date(): i for i, bar in enumerate(b)}
                for s, b in series.items()}
    days = sorted({d for rows in table.values() for d, _, _ in rows})

    # Universe reference.
    all_on = [o for rows in table.values() for _, o, _ in rows if o is not None]
    all_in = [d for rows in table.values() for _, _, d in rows if d is not None]
    print("universe average: overnight {0:+.4%}, intraday {1:+.4%}\n".format(
        sum(all_on) / len(all_on), sum(all_in) / len(all_in)), flush=True)

    for rank_leg, leg_name in ((1, "OVERNIGHT"), (2, "INTRADAY")):
        print("#### ranked on trailing {0} return, top 5% taken".format(leg_name),
              flush=True)
        picked_on, picked_in = [], []
        for day in days:
            ranked = []
            for symbol, rows in table.items():
                i = index_of[symbol].get(day)
                if i is None or i < WINDOW:
                    continue
                history = [r[rank_leg] for r in rows[i - WINDOW:i]
                           if r[rank_leg] is not None]
                if len(history) < WINDOW * 0.8:
                    continue
                ranked.append((mean(history), symbol, i))
            if len(ranked) < 50:
                continue
            ranked.sort(reverse=True)
            for _signal, symbol, i in ranked[:max(1, int(len(ranked) * 0.05))]:
                row = table[symbol][i]
                if row[1] is not None and row[2] is not None:
                    picked_on.append((str(day), row[1]))
                    picked_in.append((str(day), row[2]))

        if not picked_on:
            print("   no picks\n", flush=True)
            continue
        on = sum(v for _, v in picked_on) / len(picked_on)
        intraday = sum(v for _, v in picked_in) / len(picked_in)
        base_on = sum(all_on) / len(all_on)
        base_in = sum(all_in) / len(all_in)
        print("   picks: {0}".format(len(picked_on)), flush=True)
        print("   forward OVERNIGHT {0:+.4%}   vs universe {1:+.4%}   "
              "lift {2:+.4%}".format(on, base_on, on - base_on), flush=True)
        print("   forward INTRADAY  {0:+.4%}   vs universe {1:+.4%}   "
              "lift {2:+.4%}".format(intraday, base_in, intraday - base_in),
              flush=True)
        verdict = ("OVERNIGHT-SPECIFIC - the intraday leg is not elevated"
                   if (on - base_on) > 2 * abs(intraday - base_in)
                   else "BOTH LEGS ELEVATED - this looks like picking winners")
        print("   -> {0}\n".format(verdict), flush=True)


if __name__ == "__main__":
    main()
