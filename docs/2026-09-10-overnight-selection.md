# Overnight persistence — the first cost-clearing effect found here

**10 September 2026.** Proposed by the account owner from watching his own
charts: the market consistently gaps up overnight, so buy stocks that
*consistently* gap up, hold through the night, sell at the open.

The premise was already confirmed by this project's own work — 73.6% of the
strategy's return comes from close-to-open moves, and the universe averages
+0.0548% overnight against +0.0307% intraday. What had been rejected was
holding *only* overnight: one round trip at 0.12% to capture 0.055% loses on
every trade.

The untested part was **selection**. If some stocks reliably gap up more than
average, choosing those could beat the cost.

## Persistence exists, and it is strong

Each day every symbol is ranked by its mean overnight return over a trailing
window — information available that afternoon, nothing from the future — and
the forward overnight return measured. Quintiles, 120-night ranking, one night
held:

| quintile | trades | gross | net |
|---|---|---|---|
| Q1 worst | 110,159 | 0.0327% | −0.0873% |
| Q2 | 110,159 | 0.0311% | −0.0889% |
| Q3 | 110,159 | 0.0481% | −0.0719% |
| Q4 | 110,159 | 0.0643% | −0.0557% |
| Q5 best | 113,858 | **0.1157%** | −0.0043% |

Monotone, 3.5× from bottom to top, stable across both halves. The top quintile
lands within **0.004%** of the round trip — real, and exactly out of reach.

## Tighter selection clears it

The gradient was still climbing at Q5, so the top was sliced finer:

| slice | trades | gross | net | 1st half | 2nd half |
|---|---|---|---|---|---|
| top 20% | 110,159 | 0.1173% | −0.0027% | −0.0077% | 0.0011% |
| top 10% | 54,580 | 0.1470% | **+0.0270%** | +0.0112% | +0.0392% |
| top 5% | 26,783 | 0.1875% | **+0.0675%** | +0.0429% | +0.0865% |
| top 2% | 10,170 | 0.2353% | **+0.1153%** | +0.0676% | +0.1551% |
| top 1% | 5,044 | 0.2870% | **+0.1670%** | +0.1151% | +0.2095% |

Everything from the top 10% down clears the full 0.12% cost in **both halves**.

## Two checks that had to pass first

**Is the "open" tradeable?** The result uses the daily bar's open. Alpaca
serves 04:00–20:00 on intraday bars, so a naive first bar is a 4am pre-market
print — if daily bars behaved the same way this would measure a price nobody
can trade. Across 852 symbol-sessions the daily open matched the 09:30
regular-session open with a **median gap of 0.0000% and 66% exact matches**,
against a 0.3567% median gap to the pre-market price. The daily open is the
regular-session open.

(A first version of this check declared the result VOID because one row of
twelve differed by 0.09%. That was a binary threshold applied to noisy price
data, and it nearly discarded a valid finding on a test-design flaw rather
than on evidence.)

**Is it just picking winners?** The universe is today's 230 names run back ten
years, so it is already the survivors. If "gaps up overnight" merely means
"went up", this is hindsight. The test: measure **both legs** of the same
selected names.

| ranked on | forward overnight | lift | forward intraday | lift |
|---|---|---|---|---|
| trailing **overnight** | +0.1875% | **+0.1327%** | +0.0445% | +0.0138% |
| trailing **intraday** | +0.1269% | +0.0720% | +0.0619% | +0.0312% |

Ranking on overnight lifts the overnight leg **9.6× more** than the intraday
leg. Survivorship cannot produce that asymmetry: a stock that merely rose has
no reason to do it specifically between the close and the open.

## The qualification that matters

Ranking on **intraday** return also lifts forward overnight returns, by
+0.0720%. So roughly half the +0.1327% lift is a generic winners-keep-winning
effect and only about +0.061% is overnight-specific. Strip the generic half
and the top 5% sits near +0.116% against a 0.12% cost — back at breakeven.

Against that, one piece of evidence points away from survivorship: the effect
is **stronger in the recent half** (+0.0865% net) than the early half
(+0.0429%). Survivorship bias should be strongest in the oldest data, where
there has been most time to select winners. It runs the other way here.

Separating the two cleanly needs a universe including delisted names, which
this project does not have.

## Where it stands

| question | answer |
|---|---|
| Is the effect real? | Yes — the asymmetry is solid and the gradient is monotone |
| Does it clear costs as measured? | Yes, top 10% and tighter, both halves |
| Confident in the *size*? | **No** — half the lift may be generic momentum |
| Build it? | As a small bounded experiment. Not at size. |

Other open items before any build: **capacity** — the top 1% of 230 names is
two stocks a night, concentrated enough that a single bad gap dominates — and
**auction fills**, since the whole result assumes transacting at the opening
and closing prints, where the 6bps/side model (2bps spread + 4bps slippage) is
arguably pessimistic because an auction has one clearing price and no spread
to cross.

This is the strongest finding in the project. It is also the one most worth
being careful with, because it is the first thing in six days of testing that
did not simply fail.
