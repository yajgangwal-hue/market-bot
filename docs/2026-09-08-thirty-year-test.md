# Thirty years, including two real bear markets

**8 September 2026.** Every number this project has ever produced starts in
2016, because that is where Alpaca's data starts. That window contains COVID —
a six-week V that recovered within months — and the 2022 drift. It does not
contain a bear market.

Yahoo has the rest. It rejects Python's default user agent with HTTP 429,
which is what earlier sessions recorded as "Yahoo has stopped answering"; with
a browser header it serves history back to 1970. So the shipped configuration,
unchanged, was run from 1996 to today.

## The answer to the safety question is yes

| year | strategy | SPY | difference |
|---|---|---|---|
| 2000 | −1.8% | −10.7% | **+8.8%** |
| 2001 | +1.7% | −12.9% | **+14.6%** |
| 2002 | −2.2% | −22.8% | **+20.6%** |
| 2008 | **−8.7%** | **−38.3%** | **+29.6%** |
| 2022 | −8.9% | −19.5% | +10.6% |

The strategy lost 8.7% in 2008 while the market lost 38.3%, and was roughly
flat through the entire dot-com bust. **Maximum drawdown over 30.7 years is
−16.3%**, against −15.0% measured on the recent decade — the crises barely
moved it.

That matters more than it looks. The 200-day trend filter is doing exactly
what it was put there to do: in a sustained decline almost nothing is above
its 200-day average, so the rule simply stops buying and the account sits in
cash while the market falls. It is not that the strategy handles crashes well.
It is that it mostly does not participate in them.

## The answer to the profitability question is worse than advertised

**30-year CAGR: 4.57%.** Not the 8.02% the 2016–2026 window shows.

The weak years are the bull markets, and the mechanism is the same one that
protects it in crashes:

| year | strategy | SPY |
|---|---|---|
| 1997 | +1.8% | +31.4% |
| 1998 | −1.2% | +27.0% |
| 1999 | +1.6% | +19.1% |
| 2010 | −9.2% | +12.8% |
| 2024 | +1.8% | +23.3% |

In a melt-up, almost nothing is oversold. The rule needs a stock to be both
oversold and above its 200-day average, and in 1998 that combination barely
existed among the names then trading. The account sat in cash and earned
nothing.

Broken into eras, the recent decade is the best one in the sample:

| era | strategy CAGR |
|---|---|
| 1996–2001 | **0.66%** |
| 2002–2007 | 4.59% |
| 2008–2015 | 2.84% |
| 2016–2026 | **7.91%** |

Anyone reading the 8.02% figure as the expected return is reading the best
seven-year stretch in thirty years.

## What this says the bot actually is

A defensive strategy with crisis alpha. It beats the market in every crash in
the sample and loses to it in every bull run. Over the full period it returned
4.57% a year at a 16.3% maximum drawdown while the market returned far more at
roughly three times the drawdown.

That is a real and reasonably rare profile. It is not the profile that the
recent decade advertises, and it is not a growth strategy.

## The idle cash, priced at rates that actually prevailed

Median idle cash across the 30 years is **73% of equity** — higher than the
decade's 56%, because fewer names existed to trade in the early years.

An earlier estimate applied a flat 4% and produced +1.7 to +2.2 CAGR points.
That is the wrong way to price 30 years in which the short rate went from 5%
to 0.01% and back. Using the actual 13-week Treasury yield for every day, and
charging 2bps every time the cash balance moves:

| | total | CAGR |
|---|---|---|
| as shipped, cash earns nothing | +293.8% | 4.57% |
| idle cash in T-bills, actual rates | +382.7% | **5.27%** |

**+0.70 CAGR points a year over the full period**, drawdown unchanged at
−16.3%, because interest cannot lose money. Interest earned $102,131 against
$13,242 of trading cost for moving in and out.

But the average hides the important part — where it lands:

| era | strategy CAGR | T-bills add (points/yr) |
|---|---|---|
| 1996–2001 | 0.66% | **+4.96** |
| 2002–2007 | 4.59% | +2.31 |
| 2008–2015 | 2.84% | **−0.01** |
| 2016–2026 | 7.91% | +1.35 |

It pays most exactly when the strategy pays least. In 1996–2001 the rule
returned 0.66% a year and cash would have returned nearly 5% on the three
quarters of the account that was sitting idle. In the zero-rate years it
contributed nothing at all and the 2bps of trading cost slightly exceeded the
interest, so an implementation should simply not park below some rate floor.

At today's 3.65%, the relevant figure is the recent decade's **+1.35 points a
year** — roughly a sixth more return, at no additional risk.

## Caveats, all of which make this optimistic

**Survivorship.** The universe is today's 230 names run backwards. No Lehman,
no Enron, no Washington Mutual. The 2008 row is what the strategy would have
done trading only firms we now know survived — not a choice available in 2008.
Real 2008 would be worse.

This asymmetry was the point of running it: a good result proves little, a bad
result proves a lot. The drawdown result is the flattered one and should be
treated with suspicion. The **return** result — 4.57% — is the one that
survives the caveat, because survivorship bias inflates returns, so the true
figure is lower still.

**Delisting.** A stop protects against a price falling, not against a company
that stops trading. This test cannot show that risk at all.

**Fewer names early.** 69 symbols had data by 1990 and 125 by 2000, against
230 today. Some of the weak early returns are thin breadth rather than a
broken rule.

**Split-adjusted, not dividend-adjusted**, on both sides — so the SPY column
understates the market's true total return, and the gap in bull markets is
wider than shown.
