# Four dials swept after the entry moved. None of them turned.

**11 September 2026, evening.** Moving entries to the session close was worth
+1.3 CAGR points on the decade and +1.1 over thirty years. Every other
parameter in this rule was tuned *before* that change, against a different
distribution of outcomes, so they were all re-swept.

The account owner's framing was the right one to work from:

> "individually there is more things losing money compared to making money but
> the amount of money made is more"

That is correct, and it is worth writing down precisely, because it is the
shape the whole strategy has:

| | n | win% | avg win | avg loss | payoff | total P&L | avg days |
|---|---|---|---|---|---|---|---|
| **all trades** | 713 | 55% | 1,188 | −963 | 1.23 | **+152,234** | 13.8 |
| `reverted` | 227 | 100% | 1,635 | 0 | ∞ | +371,154 | 13.1 |
| `time_exit` | 236 | 69% | 566 | −386 | 1.46 | +64,002 | 20.0 |
| `stop` | 250 | **0%** | 0 | −1,132 | 0.00 | **−282,922** | 8.6 |

250 trades of 713 are total losses costing 1.86× everything the strategy nets.
They are paid for by 227 RSI-recovery exits that are winners 100% of the time
by construction. And the profit is concentrated:

| | share of all profit |
|---|---|
| top 10 trades of 713 | 21.4% |
| top 25 trades of 713 | 47.8% |
| top 50 trades of 713 | **85.9%** |

This is why the rescue exit cost 1.4 CAGR points. Selling at break-even raises
the win rate to 67% and truncates trades out of the bucket carrying 86% of the
money. **Fewer losers is not more money** — and that lesson arrives twice more
below, from two unrelated directions.

## Position size: 20% is the peak

| cap per name | decade CAGR | 30-year CAGR | trades | declined |
|---|---|---|---|---|
| 10% | 7.89% | 4.64% | 841 | 567 |
| 15% | 8.63% | 5.16% | 742 | 1,020 |
| **20% (live)** | **9.14%** | **5.66%** | 713 | 1,061 |
| 25% | 8.17% | — | 706 | 1,092 |

Smaller positions take *more* trades and decline *fewer* — and earn less. The
marginal signal is worth less than concentrating on the best ones, which is
what the profit concentration above predicts. A clean peak, and the same peak
on both windows.

## Stop width: 2.5 ATR is the peak

| | decade CAGR | stopped | win% |
|---|---|---|---|
| 2.0 ATR | 8.24% | 43% | 49% |
| **2.5 ATR (live)** | **9.14%** | 35% | 55% |
| 3.0 ATR | 7.90% | 29% | 56% |
| 3.5 ATR | 6.45% | 23% | 58% |
| 4.0 ATR | 5.90% | 17% | 59% |

The second lesson, from the opposite direction: widening the stop cuts the
stop-out rate from 43% to 17% and lifts the win rate to 59% — and the account
earns a third less. Confirmed over thirty years, where 3.0 and 3.5 ATR both
lose badly to 2.5.

## The RSI exit looked like a large win and was not

This is the one that nearly shipped.

| decade | total | CAGR | maxDD | 1st half | 2nd half | reverted |
|---|---|---|---|---|---|---|
| exit 55 | 109.7% | 7.20% | −14.7% | +52.3% | +37.7% | 45% |
| **exit 60 (live)** | 153.9% | 9.14% | −13.7% | +68.3% | +50.8% | 32% |
| exit 65 | 182.9% | **10.26%** | −13.6% | +75.3% | +61.4% | 16% |
| exit 70 | 191.6% | **10.57%** | −14.0% | +82.6% | +59.7% | 6% |

+1.12 and +1.43 CAGR points, better in both halves, drawdown flat. On the
decade this is the largest improvement found since the entry change, and it was
written up as such before the thirty-year run finished.

Then the thirty-year run finished:

| 30 years | total | CAGR | maxDD | 1st half | 2nd half |
|---|---|---|---|---|---|
| **live (2.5 / 60)** | 440.4% | 5.66% | **−14.2%** | **+39.0%** | +288.8% |
| 2.5 ATR / 65 | 467.3% | 5.83% | −15.3% | +34.6% | +321.6% |
| 2.5 ATR / 70 | 456.9% | 5.77% | −15.1% | +34.1% | +315.2% |

The +1.12 collapses to +0.17. The first half gets **worse**. The drawdown gets
**worse**. It fails the bar this project applies to everything — beat both
halves without costing drawdown — and it fails it on the window that contains
two real bear markets.

There was also a structural warning visible on the decade alone, in the
`reverted` column: at exit 70 only **6%** of trades ever reach the exit. The
rule stops being "buy oversold, sell the recovery" and becomes "buy oversold,
hold 20 days", with the holding cap doing the work. Shipping that under the old
name would have been measuring one thing and trading another.

## And holding longer does not capture it either

If the gain were really "hold longer", raising the cap at the shipped exit
would find it. It does not:

| holding cap, exit 60 | decade CAGR | maxDD | reverted | time |
|---|---|---|---|---|
| **20 days (live)** | **9.14%** | −13.7% | 32% | 33% |
| 25 days | 8.48% | −14.3% | 38% | 24% |
| 30 days | 8.62% | −14.0% | 42% | 17% |
| 40 days | 8.27% | −14.2% | 48% | 8% |
| 60 days | 8.29% | −14.7% | 51% | 1% |

Every longer cap is worse. Combining the two (exit 65 with a 30- or 40-day cap)
is worse than either alone on drawdown.

## Where this leaves it

Four dials — position size, stop width, exit level, holding cap — and the
shipped setting won all four once the thirty-year test was applied. There is
nothing to turn. The money available today came from the *entry clock*, and
that is already in.

One methodological note worth keeping. Three times today a decade result looked
like a clear improvement and the thirty-year window reversed it or halved it.
Each time the error ran in the same direction: toward believing the good
number. The decade contains no sustained bear market, and a parameter that
earns more without one is not the same as a parameter that earns more.
