"""Do stocks that gap up overnight keep gapping up? Buy the close, sell the open.

The premise is already measured and correct: 73.6% of this strategy's entire
return comes from close-to-open moves, and across the universe the overnight
leg averages +0.0548% a session against the intraday leg's +0.0307%. The
money genuinely is made overnight.

The obstacle is arithmetic. Buying the close and selling the next open is ONE
ROUND TRIP - 12bps at the modelled 6bps a side - to capture an average of
5.5bps. That loses on every trade, which is why the earlier write-up rejected
"hold only overnight" outright.

What was NOT tested, and is the whole point here, is SELECTION. If some stocks
reliably gap up more than average, choosing those could beat 5.5bps by enough
to cover 12bps. Overnight return persistence is a documented effect and it has
never been measured on this universe.

THE TEST. Each day, every symbol is ranked by its mean overnight return over a
trailing window - information available that afternoon, nothing from the
future. The forward overnight return of each quintile is then measured. If
persistence exists, the top quintile beats the bottom, and the question
becomes whether it beats 12bps.

Two holding periods, because they have completely different economics:

  ONE NIGHT   buy the close, sell the next open. One round trip per night, so
              the edge must exceed 12bps on its own. This is the version
              described.
  FIVE NIGHTS hold across five, paying one round trip for five overnight
              legs. The cost per night falls to about 2.4bps, but the intraday
              sessions in between are carried too - and those average
              +0.0307%, so they are not a drag.

Costs are charged in full and gross is shown separately, because if the
selection carries no signal at all then no execution improvement can help.
"""
from pathlib import Path
from statistics import mean

from event_aware_trader.data import load_bars
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto

DEEP = Path(__file__).with_name("deep")
ROUND_TRIP = 0.0012
SPLIT = "2021-03-01"


def load():
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        path = DEEP / (symbol + ".csv")
        if path.exists():
            bars = load_bars(path)
            if len(bars) >= 500:
                out[symbol] = bars
    return out


def overnight_series(bars):
    """close[t] -> open[t+1], by index, plus the date of the entry close."""
    out = []
    for i in range(len(bars) - 1):
        previous, nxt = bars[i].close, bars[i + 1].open
        if previous > 0 and nxt > 0:
            out.append((bars[i].timestamp.date(), nxt / previous - 1.0))
        else:
            out.append((bars[i].timestamp.date(), None))
    return out


def multi_night(bars, index, nights):
    """Buy close[index], sell open[index+nights]. One round trip."""
    if index + nights >= len(bars):
        return None
    entry, exit_price = bars[index].close, bars[index + nights].open
    if entry <= 0 or exit_price <= 0:
        return None
    return exit_price / entry - 1.0


def main():
    series = load()
    print("symbols {0}".format(len(series)), flush=True)

    nightly = {s: overnight_series(b) for s, b in series.items()}
    index_of = {s: {bar.timestamp.date(): i for i, bar in enumerate(b)}
                for s, b in series.items()}
    days = sorted({d for rows in nightly.values() for d, _ in rows})

    # Finer slices at the TOP, because the quintile gradient was still
    # climbing at Q5 - 0.033, 0.031, 0.048, 0.064, 0.116 - which means the
    # quintile is averaging over names that may be much better than its mean.
    # If the top few percent clear the 12bps round trip outright, the cost
    # argument becomes unnecessary.
    print("")
    print("#### FINER SLICES AT THE TOP (120-night ranking, 1 night held)",
          flush=True)
    head = "{0:<16}{1:>10}{2:>12}{3:>12}{4:>11}{5:>11}".format(
        "slice", "trades", "gross", "net", "1st half", "2nd half")
    print(head, flush=True)
    print("-" * len(head), flush=True)
    window = 120
    for share, label in ((0.20, "top 20%"), (0.10, "top 10%"),
                         (0.05, "top 5%"), (0.02, "top 2%"),
                         (0.01, "top 1%")):
        rows = []
        for day in days:
            ranked = []
            for symbol, series_rows in nightly.items():
                i = index_of[symbol].get(day)
                if i is None or i < window:
                    continue
                history = [v for _, v in series_rows[i - window:i] if v is not None]
                if len(history) < window * 0.8:
                    continue
                ranked.append((mean(history), symbol, i))
            if len(ranked) < 50:
                continue
            ranked.sort(reverse=True)
            take = max(1, int(len(ranked) * share))
            for _signal, symbol, i in ranked[:take]:
                forward = multi_night(series[symbol], i, 1)
                if forward is not None:
                    rows.append((str(day), forward))
        if not rows:
            continue
        gross = sum(v for _, v in rows) / len(rows)
        net = gross - ROUND_TRIP
        early = [v for d, v in rows if d < SPLIT]
        late = [v for d, v in rows if d >= SPLIT]
        n1 = (sum(early) / len(early) - ROUND_TRIP) if early else 0.0
        n2 = (sum(late) / len(late) - ROUND_TRIP) if late else 0.0
        flag = ""
        if net > 0:
            flag = ("  <- CLEARS COSTS" +
                    (" BOTH HALVES" if n1 > 0 and n2 > 0 else " (one half)"))
        print("{0:<16}{1:>10}{2:>12.4%}{3:>12.4%}{4:>11.4%}{5:>11.4%}{6}".format(
            label, len(rows), gross, net, n1, n2, flag), flush=True)

    for window in (60, 120):
        for nights in (1, 5):
            buckets = [[] for _ in range(5)]
            for day in days:
                ranked = []
                for symbol, rows in nightly.items():
                    i = index_of[symbol].get(day)
                    if i is None or i < window:
                        continue
                    history = [v for _, v in rows[i - window:i] if v is not None]
                    if len(history) < window * 0.8:
                        continue
                    ranked.append((mean(history), symbol, i))
                if len(ranked) < 50:
                    continue
                ranked.sort()
                size = len(ranked) // 5
                for q in range(5):
                    chunk = (ranked[q * size:(q + 1) * size] if q < 4
                             else ranked[4 * size:])
                    for _signal, symbol, i in chunk:
                        forward = multi_night(series[symbol], i, nights)
                        if forward is not None:
                            buckets[q].append((str(day), forward))

            print("\n=== ranked on the last {0} nights, held {1} night(s) ===".format(
                window, nights), flush=True)
            head = "{0:<12}{1:>10}{2:>12}{3:>12}{4:>11}{5:>11}".format(
                "quintile", "trades", "gross", "net", "1st half", "2nd half")
            print(head, flush=True)
            print("-" * len(head), flush=True)
            for q in range(5):
                rows = buckets[q]
                if not rows:
                    continue
                gross = sum(v for _, v in rows) / len(rows)
                net = gross - ROUND_TRIP
                early = [v for d, v in rows if d < SPLIT]
                late = [v for d, v in rows if d >= SPLIT]
                n1 = (sum(early) / len(early) - ROUND_TRIP) if early else 0.0
                n2 = (sum(late) / len(late) - ROUND_TRIP) if late else 0.0
                flag = ""
                if net > 0:
                    flag = ("  <- PROFITABLE" +
                            (" BOTH HALVES" if n1 > 0 and n2 > 0 else " (one half)"))
                label = "Q{0}{1}".format(q + 1, " worst" if q == 0 else
                                         (" BEST" if q == 4 else ""))
                print("{0:<12}{1:>10}{2:>12.4%}{3:>12.4%}{4:>11.4%}{5:>11.4%}{6}".format(
                    label, len(rows), gross, net, n1, n2, flag), flush=True)


if __name__ == "__main__":
    main()
