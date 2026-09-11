# The rescue exit: more wins, smaller drawdown, less money

**11 September 2026.** The account owner's rule, in his words:

> "when it turns on for the day trading it should check the night before how
> [much] it was and if it goes from a loss to profitable it should just sell it
> there"

A position that was under water at last night's close and opens above its
entry has been handed its loss back overnight. Take it.

## Why it should work, and why it should not

It fits everything this project has measured. The return lives in the
close-to-open gap, and a gap that hands a loser back its money is the single
most favourable overnight move a held position can make. The rule sells into
exactly that.

It also cuts against something this project has measured. This rule exits at
RSI 60, and exiting at 55 instead cost 2.3 points of holdout return **because
it left part of the recovery on the table**. The rescue exits far earlier than
either — at break-even. It should truncate winners hard.

Which force wins is not knowable by argument, so it was built and run.

## Built

`portfolio.run_portfolio(rescue_exit=True)`, checked **before** the stop. That
ordering is not a detail: the open is the first print of the session, so a
position that opens in profit cannot have hit its stop yet. Running the stop
first would book a loss on a bar that started green, purely because a daily
bar's low says nothing about *when* in the session it happened.

`rescue_min_bars` exists because of how this interacts with the new close-filled
entry. There, last night's close **is** the purchase price, so entry costs
alone make every position "losing" on its first morning and the rule
degenerates from a rescue into a one-night scalp. Setting it to 2 leaves the
first night alone.

## Measured, decade, 6bps

| | total | CAGR | maxDD | 1st half | 2nd half | trades | win% | rescued |
|---|---|---|---|---|---|---|---|---|
| next open, no rescue (old shipped) | +123.1% | 7.83% | −14.1% | +66.1% | +34.3% | 710 | 53% | 0 |
| next open + rescue | +93.7% | 6.41% | **−11.8%** | +48.6% | +30.3% | 851 | **67%** | 296 |
| next open + rescue, 1st night free | +93.7% | 6.41% | −11.8% | +48.6% | +30.3% | 851 | 67% | 296 |
| **signal close, no rescue (shipped)** | **+153.9%** | **9.14%** | −13.7% | +68.3% | +50.8% | 713 | 55% | 0 |
| signal close + rescue | +76.3% | 5.47% | **−9.2%** | +43.9% | +22.5% | 1,305 | **82%** | 897 |
| signal close + rescue, 1st night free | +87.9% | 6.10% | −13.4% | +48.0% | +26.9% | 844 | 66% | 275 |

**It works exactly as described, and it costs money.** Every variant:

* fires often — 296 to 897 rescues, between a third and two thirds of all exits;
* is profitable *per rescue* — +$99 to +$122 average;
* raises the win rate enormously — 53% → 67%, and to **82%** on the aggressive
  version;
* lowers maximum drawdown — −14.1% → −11.8%, and to −9.2%;
* and lowers return in **both halves**, by 1.4 to 3.7 CAGR points.

Risk-adjusted it is still slightly behind: CAGR ÷ maxDD is 0.67 for the shipped
configuration against 0.54 for the best rescue variant.

The aggressive version (`rescue_min_bars=1` on close-filled entries) is the
clearest illustration: 82% of trades win, 69% of exits are rescues, 1,305
trades instead of 713 — and it earns 5.47% against 9.14%. It has turned the
strategy into a one-night scalp that is right almost every time and paid almost
nothing for being right.

## Verdict

**Off by default. Not rejected.**

This is not a failed idea, it is a *preference*, and it is a legitimate one:
1.4 CAGR points is the price of a 2.3-point smaller drawdown and a win rate
that goes from barely-better-than-a-coin-flip to two in three. That trade is
the account owner's to make, not this file's, and the switch is built and
tested either way.

What it is not is free, and the thing it buys is comfort rather than money.
