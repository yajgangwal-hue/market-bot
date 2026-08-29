# More data, a carried balance, and the 2026 Iran war test

## More data made the model worse, and that is the finding

Training set went from 781 examples (7 ETFs, 2 years) to **10,794** (20 ETFs,
10 years, 50,280 bars).

| Dataset | Examples | Out-of-sample | AUC | Status |
|---------|---------|--------------|-----|--------|
| 7 ETFs / 2y | 781 | 235 | **0.6192** | USABLE_AS_VETO |
| 20 ETFs / 10y | 10,794 | 3,239 | **0.5001** | **UNPROVEN** |

AUC 0.5001 is an exact coin flip. This is not a tuning problem — a 24-point
sweep over learning rate, epochs, and L2 on the larger set produced a best AUC
of **0.5165**. All twelve weights collapsed toward zero, which is a heavily
regularized model reporting that it cannot find anything.

**The 0.619 was overfitting to a narrow, favourable slice.** Seven correlated
ETFs over one benign two-year stretch is not 781 independent observations; it
is a handful of market episodes sampled repeatedly. Widening to 20 ETFs and ten
years — which includes 2018, the 2020 crash, and the 2022 bear market — made
the apparent signal disappear.

The safety design is what made this discoverable rather than expensive: the
model is now correctly `UNPROVEN`, so it is ignored and vetoes nothing. Had it
been allowed to authorise trades, a coin flip would have been driving them.

Asking for "more data so it gets smarter" is the right instinct, and here it
produced the opposite of the hoped-for result. That is what more data is *for*.

## A balance that carries between runs

`ledger.py` keeps one balance on disk. A run that ends at $1,035 is the run the
next one begins with.

```bash
event-aware-trader ledger              # show it
event-aware-trader ledger --reset      # start over at $1,000
```

Compounding is the point and also the risk: sizing is a percentage of equity,
so a growing balance grows the next run's absolute risk, and a losing sequence
compounds downward too. There is a test for that direction specifically.

`run_portfolio` also gained `trade_from`, so earlier bars supply indicator
warmup while entries begin only inside the window under study. Without it a
phase test silently measures everything that led up to the phase as well.

## The 2026 Iran war

Real dates from the conflict: strikes began 2026-02-28, ceasefire 2026-04-08
after 40 days, further US strikes 2026-05-07. Five sequential tests, one
balance carried through all of them.

| Phase | From | To | Trades | Won | Open $ | Close $ | Change |
|-------|------|-----|-------|-----|--------|---------|--------|
| 1 run-up | 01-15 | 02-27 | 0 | 0 | 1000.00 | 1016.90 | +1.69% |
| 2 strikes begin | 02-28 | 03-20 | 1 | 0 | 1016.90 | 1018.45 | +0.15% |
| 3 Hormuz closed | 03-21 | 04-07 | 1 | 1 | 1018.45 | 1019.49 | +0.10% |
| 4 ceasefire | 04-08 | 05-06 | 0 | 0 | 1019.49 | 1019.49 | 0.00% |
| 5 strikes resume | 05-07 | 06-15 | 1 | 0 | 1019.49 | 1017.95 | −0.15% |

**Final: $1,017.95 (+1.80%)** over five months.

Trades:

- `XLB` and `XLI` were open going into the strikes, entered early February.
- `XLI` stopped out **the same day the strikes began**, −$2.43.
- `XLE` +$1.04 during the Hormuz closure — right instrument, right direction.
- `QQQ` −$1.54 after strikes resumed.

Same window, buy and hold:

| | Return |
|---|-------|
| Bot | **+1.80%** |
| SPY | +8.68% |
| **XLE** | **+16.63%** |
| GLD | −6.26% |

### What it got right

It **did not blow up**. Worst phase was −0.15%, and it spent phase 4 entirely
in cash. A long-only trend system in a geopolitical shock standing aside is the
designed behaviour, and it worked.

It also picked the right instrument: energy, during a Strait of Hormuz closure.

### What it got wrong

It captured **+$1.04 of a +16.63% move** in the one sector the event was
actually about. The trend and ADX filters keep it out until a move is
established, and a war-driven energy spike is over before "established" is
true. This is the cost of the filters, in a case where it is unusually visible.

## The event model's biggest assumption is wrong

`IMPACT_MAP` encodes `geopolitics/risk_off → GLD +0.45`, the strongest bullish
entry in the whole table — the folk belief that gold rallies on geopolitical
fear. Measured against the one real geopolitical shock in ten years of data:

| Assumption | Coded | Actual, 40-day strike phase |
|-----------|-------|----------------------------|
| GLD on risk-off | **+0.45** | **−11.34%** |
| XLE on risk-off | +0.30 | +0.48% |
| SPY on risk-off | −0.40 | −0.40% |

Gold fell **11%** during the strikes. The direction the table is most confident
about is the one it got most wrong. The equity and energy signs were directionally
right.

This is one event, so it is not proof the mapping is broken — but it is the
only real test available, and the table failed it on its strongest claim.
Nothing in `IMPACT_MAP` was fitted to data; it was written down from
plausibility.

## Seeing live trades in TradingView

**Yes.** Alpaca is a TradingView-integrated broker, and the integration supports
**paper** accounts, not only live ones.

Open a chart → Trading Panel → find **Alpaca** → connect → sign in and pick the
paper account. Positions, orders, and fills placed by `autotrade` then appear in
TradingView's panel and on the chart, because both are views onto the same
Alpaca account.

To be exact about what that does and does not mean:

| | |
|---|---|
| See bot positions and fills on the chart | **Yes** |
| Place manual trades from the chart into the same account | Yes |
| Have TradingView *execute* the bot's orders | No — orders go to Alpaca's API; TradingView displays them |
| Automate TradingView's own built-in paper trading | No — it has no API |

So the arrangement is: the bot trades through Alpaca, and TradingView is your
window onto it.

## Sources

- [Timeline of the 2026 Iran war](https://en.wikipedia.org/wiki/Timeline_of_the_2026_Iran_war)
- [7 May 2026 United States strikes on Iran](https://en.wikipedia.org/wiki/7_May_2026_United_States_strikes_on_Iran)
- [Trade with Alpaca on TradingView](https://alpaca.markets/learn/trade-with-alpaca-on-tradingview)
- [Alpaca — Connect to TradingView](https://alpaca.markets/tradingview)
