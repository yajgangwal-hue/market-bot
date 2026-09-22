# H-0024 — intraday strategy capability gap audit

*Sealed `17b89d9fc9b5ad699d6767391c9036e1870bc17edcee42326d9f2e18c023b504`
at commit `93d3289a`, before any result. Read-only. **No economic quantity was
computed.** No strategy, no indicator, no sweep, no model, no production
change, no promotion, no live order.*

---

## K. Classification: **B — CAPABILITY GAP EXISTS, ECONOMIC VALUE NOT ESTABLISHED**

The architectural gap is **real and precisely located**: the emulator has one
decision point per symbol per session, and the live loop — despite running 26
cycles a session — evaluates its exit rule on bars **through yesterday**.

But the information that architecture would unlock has already been bounded by
**H-0014 (B)**: the intraday increment is sign-stable at 3/3 yet collapses
~85% under a properly fitted daily baseline, its one large apparent
opportunity is not identifiable in real time, and portfolio constraints absorb
almost all of what remains. **H-0020** then showed independently that even a
class with **+2.4359%** forward SPY-relative return, 3-of-3 thirds and *zero*
symbol-session overlap **destroyed 16.9 points** at portfolio level through
crowding.

Not **A**, because no intraday class has demonstrated economic value.
Not **C**, because the architectural limitation is genuine and I can name the line.

---

## A. Governance

| check | state |
|---|---|
| identifier | **H-0024** — verified free before use (H-0023 occupied, H-0025 free) |
| seal / commit | `17b89d9f…b504` / `93d3289a` |
| registrations / declared / chain | **23 / 63 / intact** |
| **baseline equivalence** | **+58.5889000000% / 698 — PASS** |
| fingerprint | `da22011e…c237b` — unchanged |
| RSI 35/60 · ATR 0.035 · stop 2.5× · cap 20 · entries/day 3 · positions 12 · risk 0.005 · haircut 0.652% · `mr_limit_exit` None | all verified unchanged |
| ranker / veto / learned | OFF |
| H-0009 … H-0023 | sealed, frozen, none reopened |
| clean OOS | **0 sessions**, untouched |
| production diff | **none** |

*Ledger note:* the recognized-gains/news audit was documented as "H-0022" but
never registered (that directive said not to). H-0022 remains **free** in the
prereg ledger. Flagged so the docs and the ledger are not read as disagreeing.

---

## B. The decision pipeline, from source

### The emulator (`portfolio.py`)

```
for stamp in timeline:                      # ONE iteration per session
    todays_bars = {s: by_stamp[s][stamp]}   # ONE bar per symbol
    §1  fill queued entries at today's open      (:356)
    §2  manage open positions against today's range (:411)
    §3  after the close, form signals            (:728)
        order = list(todays_bars.items())        (:853)
        for symbol, bar in order:                (:865)   # ONE pass
```

**One decision point per symbol per session.** Production runs
`entry_fill="signal_close"`, so the decision and the fill are the same instant.

### Which exits can fire before the close

| exit | trigger | intraday-reachable? |
|---|---|---|
| **stop** | `bar.low <= position.stop` (:503), gap fill at `bar.open` (:515) | **YES** |
| `reverted` (RSI) | `closes + [bar.close]` (:520), exit at `bar.close` (:653) | **no** |
| `time_exit` | `bar.close` (:653) | **no** |
| take-profit / limit / partial / momentum / regime | various | **all OFF in production** |

**In production the only exit that can fire intraday is the protective stop.**

### The live loop (`autotrade.py`) — and a divergence

The live task runs every 15 minutes (verified: seven `run_complete` events on
2026-09-22 at 13:30, 13:45, 14:00, 14:15, 14:30, 14:45, 15:00 UTC). That looks
like 26 decision points a session. **It is not.**

| path | data source | sees today? |
|---|---|---|
| **entry** (:1900) | `daily_bars(symbol)` **+ `_with_today(...)`** | **yes** — today's partial bar |
| **exit** (:1691) | `daily_bars(symbol)` — **no `_with_today`** | **no** |

`_with_today` appears at exactly one call site in the whole file: line 1900,
the entry path. And the daily price files deliberately exclude the session in
progress — `_todays_bars` records that "a partial daily bar written into the
price files is the defect that corrupted 59 of them." Verified live: today is
**2026-09-22** and the local SPY/CVS/UNP files end **2026-09-21**.

**Consequence:** the live RSI and holding-cap exits are evaluated on bars
through *yesterday*. Twenty-six cycles re-evaluate one unchanged series and
reach the same answer. Entries can see today; exits cannot.

**This is an emulator/live divergence.** The emulator's RSI exit fires on
today's close (`bar.close`, :653). The live bot's cannot fire until the next
session. I am **not** attaching an economic number to that — doing so needs a
counterfactual this audit is forbidden to run — and I am **not** modifying it.
Stated as a fact with its line reference.

---

## C–D. Capability inventory

Four states, kept distinct: **DATA AVAILABLE → FEATURE COMPUTABLE → DECISION
ACCESSIBLE → STRATEGY USES IT.**

| Capability | Data | Computable | Decision-accessible | Strategy uses it | Closed by |
|---|---|---|---|---|---|
| Daily OHLCV | yes | yes | yes | **YES** | — |
| 5-minute OHLCV | yes (5,252,811 rows) | yes | **no** | no | H-0014 **B** |
| Intraday range / path | yes | yes | **no** | no | H-0014 (7 path classes) |
| Opening behaviour / gap | yes | yes | partial | no | EXP-0005, EXP-0010, EXP-0027 |
| Volume curve / relative volume | yes | yes | no | no | H-0019 **P5**, lift −0.3797% |
| VWAP relationship | yes | yes | no | no | **NOT TESTED** |
| Intraday momentum / reversal | yes | yes | no | no | H-0014 |
| Volatility expansion | yes | yes | yes (daily proxy) | no | H-0019 **P3** → H-0020 **C** |
| Volatility contraction | yes | yes | yes | no | H-0007 rejected |
| Market-relative | yes | yes | yes | no | P5-0022, EXP-0042/43/44 |
| Sector-relative | yes | yes | no | no | **NOT TESTED** |
| Cross-sectional relative strength | yes | yes | no | no | H-0019 **P4**, lift +0.0407% t=+0.64 |
| Breadth | yes | yes | no | no | forensics only |
| Dispersion / correlation change | yes | yes | no | no | **NOT TESTED** |
| Gap continuation / reversal | yes | yes | no | no | EXP-0027 (23.6%/yr → −1.5% on ETFs) |
| Opening-range / failed breakouts | yes | yes | no | no | **NOT TESTED** |
| Intraday liquidity | yes | yes | no | no | H-0017 |
| NBBO / spread | yes | yes | no | no | H-0017 (median 1.63 bps) |
| Trade intensity | yes (16.99M prints) | yes | no | no | H-0017 |
| **Order-book depth** | **NO — HTTP 404 at every tier** | no | no | no | H-0017 / H-0018 **B** |
| News / event timestamps | headline-only, 0 bodies | partial | no | no | feasibility **A — NO EVIDENCE**; P5-0011/12/13 |
| Insider filings (Form 4) | yes | yes | no | no | all \|d\| < 0.2 |
| Earnings calendar | via headlines | weak | no | no | P5-0006 |

**Availability of data is not capability.** Every row marked *decision-
accessible: no* is blocked by the same single-decision-point architecture in §B,
not by the data.

---

## E. Information boundary

The emulator's `KNOWABLE_AT` for every production feature is **the session
close** — RSI(14), SMA(200), ATR(14) and 20-day dollar volume are all computed
from closed daily bars, and production fills at that same close. The live
entry path extends this to the in-progress session's partial bar at ≈15:40 ET;
the live exit path does not extend it at all.

---

## F. Opportunity-generation funnel

From frozen artefacts (H-0019 scan; H-0015 attribution) — **not recomputed**:

| stage | count | share of prior |
|---|---:|---:|
| symbol-sessions scanned | 536,324 | — |
| passed price / liquidity / positive stop | 487,919 | 91.0% |
| **production BUY signals** | **5,081** | **1.04%** |
| reached portfolio evaluation | 1,539 | 30.3% |
| **accepted trades** | **698** | **45.4%** |

**0.13% of symbol-sessions become a trade.** The funnel is narrow — but
H-0019/H-0020 established that widening it is not the same as improving it.
Language kept precise: these are *information not represented* and *candidates
not generated*, **not** "missed profitable trades."

---

## G–H. Incremental information and stability — cited, not recomputed

**H-0014**, sealed `3acb220e…` at commit `4da278fa`, ran exactly the nested
design this directive specifies: DAILY vs DAILY+INTRADAY, Spearman rank IC
out-of-sample by chronological third, the 2-of-3 rule, seven predeclared path
classes, 5,252,811 snapshot rows over 525,712 sessions, 230/230 symbols.

**Result: B.** The increment is sign-stable — **3 of 3 thirds on all ten
snapshots** — and then fails economically at three separate points: it
collapses ~85% once the daily baseline is properly fitted; the one large
apparent opportunity is **not identifiable in real time**; portfolio
constraints absorb almost all of the remainder.

Re-running it would repeat a sealed experiment with the same data and the same
method. **It was not re-run, and no IC was recomputed here.**

---

## I. The four levels, not collapsed

| level | intraday temporal resolution | the exit-path divergence |
|---|---|---|
| **1 Information** | **YES** — stable 3/3 (H-0014) | n/a — a correctness question, not information |
| **2 Decision** | **NO** — architecture has one decision point per session | **NO** — exits cannot see today |
| **3 Strategy** | not established (H-0014's three failures) | untested |
| **4 Portfolio** | **contradicted** — H-0020 showed a far larger per-observation class lose 16.9 pts to crowding | untested |

The jump this audit refuses to make is 1 → 4. H-0020 is the standing proof of
why: information value, strategy value and portfolio value are different
quantities, and in this book the portfolio has repeatedly been the binding one.

---

## J. The architectural bottleneck, exactly

1. **`portfolio.py:865`** — `for symbol, bar in order` runs once per session.
   There is no second pass, so no candidate can be generated after the
   session's single decision point.
2. **`portfolio.py:653`** — rule exits read `bar.close`. Only the stop
   (`:503`, `bar.low`) can resolve before the session ends.
3. **`autotrade.py:1691`** — the live exit calls `daily_bars(symbol)` with no
   `_with_today`, while the entry at **`:1900`** adds it. The live exit rule is
   structurally blind to the current session.
4. **`portfolio.py:853`** — candidate order is `list(todays_bars.items())`
   with `candidate_rank=None` in production; EXP-0025 measured that ordering
   as noise that "flips between windows."

Answering §16 directly: generate a candidate after the morning signal — **no**;
update one during the session — **no**; cancel/replace a pending decision —
only under `next_open`, which production does not use; enter after an intraday
event — **no**; exit before the close — **only via the stop**; compare
simultaneous opportunities — **yes**, within one session's pass; reprioritise —
hook exists, disabled.

### Category placement (§19)

| capability | category |
|---|---|
| Intraday temporal resolution | **3** by the letter — stable information value — but H-0014 already took it to the economic gate and it failed on three counts, so it is **closed in practice** |
| Cross-sectional, volume shock, volatility expansion, market-relative, gap, news, insider | **1 / 2** — closed by the branches cited in §C |
| Order-book depth | **5** — data does not exist at any tier (HTTP 404) |
| **Live exit-path staleness** | **4 — ARCHITECTURAL LIMITATION**, mechanism documented above, production unmodified |
| VWAP, sector-relative, dispersion, correlation change, opening-range, failed breakouts | **NOT TESTED** — and all would enter through the same single decision point, so H-0014's aggregate bounds what the class can add |

---

## L. Recommended next step — exactly one

**Perform a narrowly defined architecture audit of the emulator/live exit-path
divergence.**

Not an economic experiment: outcome B does not justify one, and the only
intraday economic question has been sealed and answered by H-0014. Not a data
acquisition: depth is unavailable, and nothing else is missing. Not "close and
move on" alone, because §J item 3 is a *fidelity* defect — the emulator's RSI
exit fires on today's close while the live bot's cannot — and every economic
number this project holds was produced by the emulator.

That audit is narrow, needs no new data, and answers a correctness question
rather than searching for edge. It should be scoped to: how often the two
paths would diverge, whether `bars_held` accounting differs, and whether the
H-0012/H-0013 exit-timing work describes the live system or only the emulator.
**It must not change production without separate authorisation.**

---

## Final conclusion

**The largest remaining capability gap supported by the evidence is
architectural, not informational: the emulator makes one decision per symbol
per session, and the live loop's exit rule cannot see the session it is
trading in.** The information such an architecture would unlock is already
bounded — stable but ~85% redundant with daily features, its largest component
not identifiable in real time, and demonstrably absorbed by portfolio
constraints that killed a far larger effect in H-0020.

**The smallest defensible next research action is the narrow emulator/live
exit-path fidelity audit above** — a correctness question about whether the
backtest describes the system that trades, answerable from code and existing
data, with no economic claim attached.

---

## Production status

Fingerprint `da22011e…c237b` unchanged · RSI 35/60 · ATR 0.035 · 20-bar cap ·
2.5× ATR stop · risk 0.005 · 12 positions · bucket 1 · 3 entries/day · haircut
0.652% · `mr_limit_exit` None · ranker/veto/learned OFF · benchmark unchanged ·
no leverage · clean OOS untouched at 0 sessions, opening 2026-10-12 ·
**23 registrations, 63 declared configurations, chain intact** · thirty-year
reads 13 · **no economic result computed, nothing promoted, no live order, no
performance claim.**
