# Where to set take profits and stop losses: the open trades and the evidence

> **Update, later on 2026-10-04: implemented** on the owner's order as EXP-0057.
> The take profit is now the bounce price. A portfolio-level check, which
> this document said was needed, put it ahead of the 2.5-ATR target by +12.0
> to +18.5 points over the decade. The time limits in section 1 were corrected
> by REM-0010 (VZ Oct 20, IWM Oct 21, SCHD Oct 21, MDY Oct 22, SCHW Oct 29).
> See `2026-10-04-bounce-take-profit-live.md`.

*2026-10-04. The owner asked: "Right now there are many trades that are open
and the bot is currently making a profit but it is unrecognized so research
know where to set take profits and stop losses." Research only: nothing
changed, nothing committed, no broker call (the exposed key is not yet
rotated). Every figure comes from the bot's own local records and the
project's data.*

## The answer

**Stops: keep them where they are.** 2.5 × ATR(14) below entry is the
measured best width for this strategy (EXP-0022). For a buy-the-dip trade a
stop is insurance, not a profit tool: tighter stops lowered returns in every
test here and in the literature.

**Take profits: the evidence points to the bounce price, not 2.5 × ATR, but
it is not conclusive.**

- **The bounce price** is where the day's price would push RSI(14) to 60: the
  bot's own "bounce done" sale, so nothing new is fitted. It moves each day.
- **The test.** Replaying the strategy's 698 trades from 2016–2026 (H-0038),
  a resting sell order at the bounce price, refreshed daily, earned:
  - **+0.144R a trade**, against **+0.115R** for the live 2.5-ATR take profit;
  - **+0.029R a trade more**, positive in both halves and under every
    exit-cost assumption;
  - but **t = 1.64**, short of the sealed bar of 2.0.
- **The live take profit was never the best of the placements tried.** It
  sells winners about two sessions sooner and wins more often, but by less.

**"Unrecognized profit".**

- At the bot's last check (Friday 2026-10-02, 3:45 pm ET) the 7 open
  positions were **net −$109**.
- **UNP (+$397) and MDY (+$162)** carry the profit; the other five were down.
- From Monday, when the take profit starts resting at the broker (EXP-0056),
  UNP is sold automatically at $284.97 (+2.4% above Friday's mark) and MDY at
  $682.01 (+1.7%).

**Nothing was changed.** Moving the take profit is the owner's decision. It
would need a portfolio-level test first, and it would restart the forward
evaluation clock (section 5).

## 1. Where each open trade will be sold

As of Friday 2026-10-02, 3:45 pm ET:

- **Entry** is the broker's average fill, which the bot's levels use.
- **Mark** is entry + broker unrealized P&L ÷ shares.
- **Bounce price** uses Friday's 3:45 mark as Friday's close; the bot
  recomputes it every cycle.

| Position | Shares | Entry | Mark | Unrealized | Stop | Take profit (2.5 ATR) | Bounce price, Monday | Time limit |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| UNP | 48 | 269.87 | 278.15 | **+$397** | 254.77 | **284.97** (+2.4%) | 290.39 (+4.4%) | Oct 19 |
| MDY | 26 | 664.57 | 670.80 | **+$162** | 647.13 | **682.01** (+1.7%) | 687.97 (+2.6%) | Oct 21 † |
| IWM | 35 | 282.10 | 281.69 | −$14 | 273.19 | 291.01 (+3.3%) | 293.49 (+4.2%) | Oct 20 † |
| VZ | 174 | 46.34 | 45.85 | −$85 | 43.61 | 49.07 (+7.0%) | 49.79 (+8.6%) | Oct 19 † |
| CVS | 124 | 87.45 | 86.67 | −$96 | 81.71 | 93.19 (+7.5%) | 95.72 (+10.4%) | Oct 19 |
| SCHD | 388 | 33.32 | 32.72 | −$235 | 32.49 | 34.15 (+4.4%) | 34.40 (+5.2%) | Oct 20 † |
| SCHW | 142 | 98.35 | 96.67 | −$238 | 92.84 | 103.85 (+7.4%) | 108.55 (+12.3%) | Oct 28 † |
| **Total** | | | | **−$109** | | | | |

Percentages are distances from Friday's mark.

† One session earlier than the rule intends. Since about 2026-09-22 the bot
stamps a position's opening with the session before its entry (the D−1 stamp
defect, recorded on 2026-10-03 and not fixed).

**What each would make:**

| Position | Sold at the take profit | Sold at the bounce price (if reached Monday) | Sold at the stop |
|---|---:|---:|---:|
| UNP | +$725 | +$985 | −$725 |
| MDY | +$453 | +$609 | −$453 |
| SCHW | +$782 | +$1,449 | −$782 |
| CVS | +$711 | +$1,026 | −$711 |
| VZ | +$475 | +$601 | −$475 |
| SCHD | +$320 | +$418 | −$320 |
| IWM | +$312 | +$399 | −$312 |

**On every position the take profit sits below the bounce price.** So from
Monday the take profit, not the bounce, is what sells a winner on a rise.

The bounce price falls as a stock climbs over several days, because each up
day lifts RSI, so it is not a fixed level. Notes on the inputs:

- **The "last" price in the bot's hold log** is the previous session's close
  by design (the code says so). The exit rule itself uses the live price.
- **No "today's bars unavailable" event** was ever logged, so the exits did
  see Friday's prices.

## 2. What happens from Monday

| Exit | How it works | Visible on TradingView? | Works with the PC off? |
|---|---|---|---|
| Stop, 2.5 ATR | resting GTC order at Alpaca since each entry | yes | yes |
| Take profit, 2.5 ATR | from Monday's first cycle, one OCO order with the stop (EXP-0056); if Alpaca refuses it, the plain stop goes back and the bot checks the take profit every 15 minutes | yes, once the OCO is placed | yes, once placed |
| Bounce done, RSI(14) ≥ 60 | the bot recomputes RSI with the live price every 15 minutes and sells at market | no | **no** |
| Time limit, 20 sessions | sold at market on the date above | no | no |

## 3. H-0038: four take-profit placements, replayed trade by trade

**The test.** The frozen strategy's 698 decade trades kept their entries,
sizes and stops. Each was replayed on its own daily bars under four
placements:

- **A:** no take profit (the original rule).
- **B:** the live take profit at 2.5 ATR.
- **C:** a resting sell at the bounce price, refreshed daily.
- **D:** the lower of B and C.

**The replay is exact.** It reproduced **698 of 698** of the baseline's real
exits: the same day, at the same price to within one part in a million.

**Exit costs.** Sales at market by rule pay an extra cost on top of the 6 bp
spread and slippage. The live figure is uncertain, 0.2% to 0.6% (H-0008,
H-0012), so the test was run three ways:

- 0.3%, the primary;
- 0.652%, the backtest's worst case;
- 0%.

**At the primary 0.3%:**

| Placement | R a trade | Winners | Sessions held | R per session held | Exits |
|---|---:|---:|---:|---:|---|
| A: none | +0.133 | 53% | 14.0 | 0.0095 | stop 239, bounce 221, time 238 |
| B: 2.5 ATR (live) | +0.115 | 58% | 11.3 | 0.0102 | stop 221, target 309, time 158, bounce 10 |
| **C: bounce price** | **+0.144** | 54% | 13.4 | **0.0108** | stop 237, target 253, time 208 |
| D: lower of B and C | +0.113 | 58% | 11.3 | 0.0100 | stop 221, target 325, time 152 |

**Head to head, in R a trade:**

| Comparison | At 0.3% | At 0.652% | At 0% |
|---|---|---|---|
| **C − B: bounce price vs live** | **+0.029 (t 1.64)** | +0.024 (t 1.34) | +0.033 (t 1.90) |
| B − A: live vs none | −0.018 (t −0.92) | +0.017 (t 0.91) | **−0.048 (t −2.42)** |
| C − A: bounce price vs none | +0.011 (t 1.38) | **+0.042 (t 4.83)** | −0.014 (t −1.71) |
| D − B: adding the bounce price to the live take profit | −0.002 | −0.000 | −0.003 |

**C − B by half (0.3%):** +0.044 (2016–2020), +0.019 (2021–2026).

**Verdict: NO DIFFERENCE SHOWN.** The sealed rule needed t ≥ 2.0 at 0.3%, both
halves positive, and the same sign at the other two costs. The last two held,
but t was 1.64.

**How to read it:**

- **C beat B every way it was cut, but not by enough to call.**
  - Every cost assumption and both halves favour the bounce price over the
    live take profit.
  - Year by year, C beat B in 8 of 11 years.
  - The margin is small against the noise in 698 trades.
- **The live take profit only helps if market sales are expensive.**
  - With no extra cost on market sales, it is clearly worse than having none
    (t −2.42).
  - Only under the backtest's worst case (0.652%) does it come out ahead.
  - This matches EXP-0050: a 1R target cut the strategy's annual return from
    5.75% to 4.88%. It also matches EXP-0055's own −$29,230 once its
    execution accounting is removed.
- **Selling sooner "recognizes" more winners but makes less.**
  - B wins 58% of trades against C's 54%.
  - B's average is lower because it caps the winners that would have kept
    going: 81.2% of trades that reach +2% go on to a higher gain (H-0021).
- **Capital efficiency does not rescue the live take profit.** C also earns
  the most per session held (0.0108R against B's 0.0102R), so freeing capital
  two sessions sooner does not make up for the smaller wins.
- **Keeping both is worse than either.** D is the worst placement: adding the
  bounce price as a second sell order on top of the live take profit only
  sells earlier still.

**Two caveats:**

- **Per-trade replay.** Money freed by an earlier sale is not redeployed. A
  portfolio-level test would settle it; this engine cannot run one without a
  change to the backtester.
- **Contaminated data.** These are the decade data the strategy was built on,
  so a result here can only nominate a change, never prove one.

**H-0037 never completed.** It was the same test, registered first (seal
`06ac2c80…`). Its runner crashed in the verdict step, on a lookup of a
comparison it had not computed, before printing or writing any result.
H-0038 is H-0037 with that line fixed and the verdict logic unit-tested;
nothing else changed.

## 4. Why "lock in the profit sooner" keeps losing here

The project has asked this question in about 80 configurations
(`2026-09-27-exit-placement-research.md` §4):

- **Fixed targets** (EXP-0050): 1.0R gave 4.88% a year against 5.75%; 1.5R
  gave 5.15%; 2.0R gave 5.65%. Tighter costs more.
- **Locking in at break-even** (H-0003, H-0005): a spike at one setting,
  rejected.
- **Trailing stops** (P5-0007, EXP-0036) and **partial sales** (P5-0010):
  rejected.
- **The +0.5% / −0.2% pair** (H-0030): −0.02% a trade against +0.57%.

**Why it keeps losing.** The strategy buys a dip and is paid when the bounce
completes. Selling before the bounce is done takes the small part of the move
and leaves the large part.

- **Stops** (Kaminski & Lo, 2014): on a random walk, stop rules always lower
  expected return. They add value only when losses tend to continue, the
  opposite of a bounce trade.
- **Targets** (Leung & Li, 2015; Carr & López de Prado): for a trade that
  reverts to a fair level, the best target sits at or above that level, not
  below it.

## 5. If the owner wants the take profit moved

**The change the evidence points to:**

- set the OCO's take-profit leg to the **bounce price**, recomputed each
  morning before the open;
- keep the 2.5-ATR stop as the other leg;
- drop the fixed 2.5-ATR target.

**What it would give:**

- the bot's real profit exit becomes a visible order on TradingView;
- the exit works with the PC off;
- the market-order cost of the bounce exit goes away.

**What it would need, in order:**

1. A portfolio-level registered test: extend the backtester with this exit,
   since money freed early is part of the answer.
2. Owner approval.
3. The code change, under the same daily refresh as the stop reconciler. An
   OCO order would be cancelled and replaced each morning, which is the churn
   risk the EXP-0056 notes flag.
4. A fingerprint change, which restarts the forward evaluation clock.

**Until then:** nothing changes. The stop and the 2.5-ATR take profit go live
as OCO orders from Monday's first cycle, as EXP-0056 set.

## Records

- H-0038: `scripts/h0037_tp_placement.py` (engine), `scripts/h0038_spec.py`,
  `scripts/run_h0038.py`, `tests/test_h0037_tp_placement.py`,
  `tests/test_h0038_decide.py`, and `docs/phase5/h0038-results.json`. Seal
  `96c6f712…`, registered 2026-10-04 22:47 UTC.
- H-0037: `scripts/h0037_spec.py` and `scripts/run_h0037.py`. Seal
  `06ac2c80…`; did not complete, and no results file exists.
- The open-position figures come from `data/autotrade-state.json` and the
  last `hold` and `stop_coverage` events in `data/autotrade-audit.jsonl`
  (2026-10-02 19:45 UTC). The bounce prices come from `data/<symbol>.csv`
  through 2026-10-01 plus Friday's mark, using the bot's own
  `indicators.rsi`.
- Earlier exit research: `2026-09-27-exit-placement-research.md`,
  `2026-09-28-adaptive-exits.md` (EXP-0055), `2026-09-28-h0026-report.md`,
  `2026-09-21-h0021-giveback-anatomy.md` and
  `2026-10-03-take-profit-at-broker.md` (EXP-0056).
