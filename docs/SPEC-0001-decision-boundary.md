# SPEC-0001 — Canonical decision boundary

| | |
|---|---|
| **Version** | **1.0.0** |
| Status | **NORMATIVE** — the level-1 artefact whose absence allowed two implementations to diverge |
| Created | 2026-09-22 |
| Applies to | `src/event_aware_trader/portfolio.py` (emulator), `src/event_aware_trader/autotrade.py` (live), and any future research harness |
| Authority | Derived from sealed experiment methodology (H-0013), production test contracts (`test_exit_timing_haircut.py`, `test_entry_timing.py`) and implementation comments (`_todays_bars`). It **records** existing intent; it does not invent new behaviour |
| Changes to this file | Any change to a normative clause is a **strategy semantics change** and requires the governance path in §9 |

> **This specification changes no code and authorises no code change.** It states
> what the strategy is *intended* to mean so that a later correction has a
> target. Conformance is audited separately.

---

## 1. The core contract

> **C-1.** On session **D**, the strategy may use information available through
> **the current moment of D**, with the **in-progress price standing in for
> today's close** where the strategy definition requires a current-price proxy.
> The strategy acts on **the cycle in which the condition first becomes true**.

**C-2.** Information from any session after D, and any value from D that is not
yet observable at the decision moment, is **prohibited**.

**C-3.** Nothing in this specification introduces, removes or retunes a
decision *condition*. It governs **timing and observability only**. `rsi_entry`
35, `rsi_exit` 60, `max_atr_fraction` 0.035, `stop_atr_multiple` 2.5,
`max_holding_bars` 20 and every risk limit are out of scope and unchanged.

---

## 2. Decision equivalence vs execution-price equivalence

**C-4. DECISION EQUIVALENCE is the target.** Given the same permissible
information, the emulator and the live system must reach the **same logical
decision** — the same action, on the same symbol, on the same session, for the
same reason.

**C-5. EXECUTION-PRICE EQUIVALENCE is NOT expected and must never be claimed.**
The emulator books rule exits at the session close; live fills at market on the
triggering cycle. That difference is **charged, not modelled**, by the
`rule_exit_timing_haircut` (0.652%). See §8 and SPEC-0001 §10.

**C-6.** A conformance claim must always state which of C-4 and C-5 it refers
to. "The systems agree" without that qualifier is not a valid statement.

---

## 3. The complete-bar proxy, stated once

**C-7.** The emulator observes a session only as one completed OHLCV bar. It
therefore uses **D's completed bar as its proxy for "the current moment of D"**.
This is an approximation of C-1, not a departure from it.

**C-8.** The proxy's error differs by field and must be treated accordingly:

| field | live observes at the decision moment | emulator proxy | proxy error |
|---|---|---|---|
| price | last trade ≈ decision time | D's final close | small; **charged by the haircut for exits**, measured and accepted for entries |
| volume / ADV | volume traded **so far** on D | D's **full-session** volume | **systematically larger in the emulator** — see C-9 |

**C-9.** Because the emulator's volume proxy is systematically larger, any
volume-dependent gate (the `min_average_dollar_volume` floor, the
`max_volume_participation` cap) is **more permissive in the emulator than live
can be**. This is a known, accepted asymmetry; it must be disclosed wherever a
volume-gated quantity is compared between the two systems, and it must never be
described as decision equivalence.

---

## 4. Per-decision boundary

Notation: **D** = the session being decided. *Latest info* = the latest
permissible observation. *In-progress bar allowed* = whether D's forming bar may
be read. *Price proxy* = whether the in-progress price may stand in for D's
close.

### 4.1 Entry signal

| | |
|---|---|
| Latest info | **D, in progress** |
| Decision timestamp | within the entry window — the final `entry_window_minutes` (20) of D |
| Execution timestamp | same instant |
| In-progress bar allowed | **YES — required** |
| Price proxy | **YES** |
| Prohibited | D's final close before it exists; any bar after D; any volume not yet traded |
| Emulator | evaluates on D's completed bar and fills at D's close (`entry_fill="signal_close"`) |
| Live | `daily_bars()` **+ `_with_today()`**, fills at market |
| Equivalence required | **decision** (C-4) |
| Unavoidable execution difference | emulator fills at D's close; live fills at ≈15:40–16:00 |

### 4.2 Rule exit — RSI (`reverted`)

| | |
|---|---|
| Latest info | **D, in progress** |
| Decision timestamp | **the first cycle on which RSI ≥ `rsi_exit` becomes true**, using the in-progress price as D's close proxy |
| Execution timestamp | same instant |
| In-progress bar allowed | **YES — required** |
| Price proxy | **YES — this is the clause H-0013's sealed trigger definition states** |
| Prohibited | any bar after D; a *completed* D close before the close has occurred |
| Emulator | RSI over closes including D's close; books at D's close × (1 − haircut) |
| Live | **must** evaluate on `daily_bars() + _with_today()` |
| Equivalence required | **decision** (C-4) |
| Unavoidable execution difference | emulator books at D's close; live fills at market on the triggering cycle — **this is exactly what the haircut charges** |

### 4.3 Time-based exit (`time_exit` / `time`)

| | |
|---|---|
| Latest info | **D** — the condition is a count, known at the bell |
| Decision timestamp | the first cycle of the session on which `bars_held ≥ max_holding_bars` |
| Execution timestamp | same instant |
| In-progress bar allowed | yes, for `bars_held` to include D |
| Price proxy | not applicable — the condition is not price-dependent |
| Emulator | fires on the session where `bars_held` reaches 20; books at D's close × (1 − haircut) |
| Live | must reach the same count on the same session (§5) |
| Equivalence required | **decision** (C-4) |
| Unavoidable execution difference | as 4.2 |

### 4.4 Protective stop

| | |
|---|---|
| Latest info | **continuous live tape** |
| Decision timestamp | **on any trade at or through the stop price**, between decision cycles |
| Execution timestamp | immediate |
| In-progress bar allowed | n/a — the stop does not read bars |
| Price proxy | n/a |
| Prohibited | using a bar low from before the position existed (see `should_exit`'s `entry_time` gate) |
| Emulator | `bar.low <= stop`, with `realistic_stop_fills` giving the open on a gap |
| Live | **broker-resident GTC stop** |
| Equivalence required | **decision** (C-4) |
| Unavoidable execution difference | gap fills differ in detail; the emulator models this explicitly |

**C-10. A broker-resident protective stop may execute between strategy decision
cycles, and that is required behaviour, not a divergence.** The stop is a
continuous safety mechanism and is **operationally distinct from a rule exit**.

**C-11.** This specification **does not** authorise moving stop execution into
the 15-minute decision cycle. The in-process stop check in `should_exit` is a
redundant backstop; the broker-resident order is the protection.

### 4.5 Position sizing

| | |
|---|---|
| Latest info | **D, in progress** — equity, cash, price, ATR, ADV as observable now |
| Decision timestamp | same instant as the entry decision |
| In-progress bar allowed | **YES** |
| Prohibited | equity marked at a price not yet observed; volume not yet traded |
| Emulator | equity = cash + positions marked at D's closes; ADV over `history[-20:]` including D's complete bar |
| Live | equity from the broker in real time; ADV over `series[-20:]` including D's **partial** bar |
| Equivalence required | **decision** (C-4), **subject to C-9** |
| Unavoidable difference | the volume proxy (C-8, C-9) |

### 4.6 Portfolio and risk checks

Applies to: daily loss guard, weekly loss guard, `max_open_positions`,
correlation-bucket cap, `max_entries_per_day`, cash sufficiency.

| | |
|---|---|
| Latest info | **D, in progress** — current equity and current portfolio state |
| Decision timestamp | evaluated at the decision moment, before the action |
| In-progress bar allowed | **YES** |
| Prohibited | end-of-session equity before the session ends; realised P&L from trades not yet closed |
| Emulator | guards read D-close-marked equity against D's open-marked equity |
| Live | guards read live broker equity against the session's opening equity |
| Equivalence required | **decision** (C-4) |

### 4.7 News decisions — **PLACEHOLDER, NOT ACTIVE**

**C-12.** News is **not** in the money path and this specification does not put
it there. If it is ever admitted, the boundary is:

> an item may inform a decision on D only if its **availability timestamp**
> — not its publication timestamp — is strictly earlier than the decision
> timestamp, with realistic ingestion latency applied.

**C-13.** Prohibited: revised article text against an original timestamp;
post-decision items; hindsight sentiment or event labels; any item whose
availability time cannot be established.

### 4.8 Regime decisions — **PLACEHOLDER, NOT ACTIVE**

**C-14.** Same principle: a regime label for session D must be constructed only
from information observable at the decision moment. The existing leakage-free
convention — `trend_dual_ma`, built from closes through **D−1** and shifted
forward — remains the reference if a regime is ever admitted. Not active.

---

## 5. `bars_held` — one definition

**C-15.**

> **`bars_held` is the number of completed trading sessions strictly after the
> entry session, evaluated as of the current session.**

**C-16.** Under `entry_fill="signal_close"` (entry at D's close):

| on session | `bars_held` |
|---|---|
| D | 0 |
| D+1 | 1 |
| D+k | k |
| **cap (`max_holding_bars` = 20) fires** | **D+20** |

**C-17. Edge cases.**
- Weekends and holidays are irrelevant: the count is over **bars**, never calendar days.
- Same-session entry and exit cannot occur under `signal_close` — entry happens after the exit pass.
- A live entry during session D (≈15:45) makes D the entry session; counting starts at D+1.
- The entry session's own bar is **never** counted, in either system.

**C-18. ONE IMPLEMENTATION CONTRACT.** Known implementations:

| site | expression | conforms? |
|---|---|---|
| `portfolio.py:415` | `position.bars_held += 1` per session with a bar | **yes** |
| `autotrade.py:1719` | `sum(1 for bar in series if bar.timestamp.date() > entry_day)` | **the expression conforms; the series does not** — it ends D−1, so it returns k−1 |
| `autotrade.py:1723-1726` | `len(series) - opened_days` (legacy) | returns k; retained only for positions opened before the preferred path existed |

**C-19.** `autotrade.py:1719` must **not** receive an independent correction.
Supplying it a series that includes D makes it return k automatically. A
separate adjustment on top would double-count.

---

## 6. Prohibited information — summary

**C-20.** Across every decision above, the following are prohibited:

1. any bar dated after D;
2. D's completed close, high, low or volume before the session ends;
3. a stop comparison against a bar low from before the position existed;
4. forward returns, forward excursions, or any outcome of the decision;
5. revised or retroactively restated data presented under an original timestamp;
6. vendor-restated adjusted series used to reconstruct a past decision without storing the values actually used;
7. universe membership determined by knowledge available only today (see H-0023, classification D).

---

## 7. Conformance

**C-21.** A system conforms to SPEC-0001 when, for every decision type in §4,
it observes no information later than the stated boundary and reaches the same
logical decision as the reference emulator given the same permissible
information (C-4), with C-9's volume asymmetry disclosed.

**C-22.** Conformance is audited separately and is **not** asserted by this
document. At version 1.0.0 **neither implementation fully conforms**; see the
companion implementation audit.

---

## 8. Relationship to the exit-timing haircut

**C-23.** `rule_exit_timing_haircut` = 0.652% exists **because of C-5**: it
charges the difference between the emulator's close-priced booking and the
live fill at the triggering moment. It is an **uncertainty adjustment, not a
price**, per `test_exit_timing_haircut.py`.

**C-24.** The haircut must **never** be presented as live slippage, live
transaction cost, intraday opportunity cost, or evidence of an intraday edge.

**C-25.** H-0013 calibrated the haircut against a *model* of live behaviour
that assumed §4.2's boundary. If the live implementation did not honour that
boundary at the time of calibration, the haircut's numeric value is calibrated
against assumed rather than observed live semantics. **This is disclosed, not
corrected here**; H-0013's result stands unaltered.

---

## 9. Governance

**C-26.** Changing a normative clause of SPEC-0001 is a **strategy semantics
change**. If it would alter historical results it requires a separately
registered baseline-redefinition experiment before any code moves.

**C-27.** Bringing an implementation **into** conformance with an unchanged
SPEC-0001 is an **implementation correction**, not a strategy change — but if
it touches the live money path it still requires explicit owner approval and a
money-path review before implementation.

**C-28.** The frozen baseline **+58.5889000000% / 698** and the fingerprint
`da22011e…c237b` are unaffected by this document. Publishing SPEC-0001 changes
no code, no parameter and no result.

---

## 10. Version history

| version | date | change |
|---|---|---|
| 1.0.0 | 2026-09-22 | Initial. Records existing intent from H-0013's sealed trigger definition, `test_exit_timing_haircut.py`, `test_entry_timing.py` and `_todays_bars`. No behaviour invented, no code changed. |
