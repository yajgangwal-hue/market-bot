# H-0021 next step — exit candidate design

*Design only. **Outcome: NO NEW CANDIDATE.** Nothing registered, nothing run,
no production change. Two coherence checks were run and are disclosed below as
**outside the H-0021 seal**.*

---

## Verdict

**H-0021 does not support a sufficiently distinct deterministic mechanism.**

Every mechanism that targets the time-exit population and is constructible
from decision-time information either (a) reduces to removing the 0.652%
rule-exit haircut — a charge H-0013 validated and H-0018 explicitly ruled is
not recoverable return — or (b) is `mr_trail` / `mr_momentum_drop` with a time
gate bolted on, which is EXP-0036 restricted, carrying two free parameters
that cannot be derived from existing mechanics.

Per §10, reporting this is preferable to registering a disguised repeat.

---

## 1. What the code says about novelty — checked against source, not the ledger

`run_portfolio` already carries a hook for every prior exit family:

| hook | signature | prior experiment |
|---|---|---|
| `mr_trail` | `(activate_r, multiple)` | EXP-0036 — **already has an activation-gain argument** |
| `mr_partial` | `(at_r, fraction)` | EXP-0036 (scaling out) |
| `mr_momentum_drop` | `float` — fires on `rsi_peak − strength` | EXP-0036 (momentum / RSI-peak deterioration) |
| `mr_regime_exit` | `bool` | EXP-0036 |
| `mr_take_profit_r` | `float` | EXP-0049 / EXP-0050 |
| `mr_take_profit_down_r` / `_up_r` | `float` | EXP-0051 / EXP-0052 |
| `mr_limit_exit` | `(offset, patience)` | H-0011 |

**Every one is time-homogeneous — not one takes `bars_held` as an argument.**
That genuinely *is* the structural gap, and it is why a deadline-aware
mechanism was worth designing toward. The gap is real. What follows is why
nothing constructible fills it.

## 2. Coherence check A — when does the executable peak occur?

*Disclosed: not part of the H-0021 seal. Descriptive; no rule simulated. Run
because a terminal-window mechanism is incoherent if the peak happens early.*

238 time-exit trades, bar of the executable peak (entry = bar 0, cap ≈ bar 20):

| bars | trades | share |
|---|---:|---:|
| 1–5 | 55 | 23.1% |
| 6–10 | 62 | 26.1% |
| 11–15 | 44 | 18.5% |
| 16–20 | 77 | **32.4%** |

Median bar 11, quartiles 6 and 17. **The peak is diffuse.** The last quarter is
the single largest bucket, so a terminal mechanism is not *incoherent* — but
**68% of peaks occur before bar 16**, so no terminal window addresses the bulk.

One-sided hindsight value remaining after bar *k*:

| after bar | mean available | pool |
|---|---:|---:|
| 15 | 1.996% | $73,564 |
| 17 | 1.534% | $57,742 |
| 19 | 0.765% | $33,553 |

## 3. Coherence check B — the terminal value is the haircut

*Also disclosed as outside the seal. This is the check that decided the
outcome.*

The one **zero-parameter** deadline mechanism available is: *the cap bar is
known one session in advance, so sell at its open instead of its close.* It
needs no threshold, uses no future data, and touches only time-exit trades.

| comparison on the 238 cap bars | mean | median | pool |
|---|---:|---:|---:|
| booked exit vs **raw** close | −0.7116% | — | — (the 0.652% haircut + modelled costs) |
| cap **open** vs **booked** exit | **+0.7710%** | +0.7269% | $33,553 |
| cap **open** vs **raw** close | **+0.0539%** | **+0.0101%** | $15,723 |

**93.0% of that apparent terminal gain is purely the modelling charge.** The
cap bar's open is a median **+0.0101%** above its own raw close — indistinguishable
from nothing.

This is precisely the error H-0018 was written to prevent: an effect whose
"entire economic span is a charge H-0013 already validated as approximately
correctly sized." The mechanism is rejected on its own evidence.

## 4. Every other mechanism, and the exact check it fails

| proposed mechanism | fails | why |
|---|---|---|
| Sell at the cap bar's open | §16 (and arguably audit 2) | 93% haircut accounting; real price content is +0.0539% mean, +0.0101% median |
| Retracement from running peak, gated on `bars_held ≥ W` | audit 3, audit 11 | This is `mr_trail` restricted to a window. EXP-0036 tested 11 configurations of the ungated form and rejected them. **W and the retracement threshold are both free parameters** derivable from nothing in existing mechanics — a two-dimensional sweep in disguise |
| Exit on RSI progress toward 60, or on `rsi_peak` deterioration near the cap | audit 5, audit 7 | `mr_momentum_drop` is exactly `rsi_peak − strength`; EXP-0036. A level version is EXP-0023 |
| Resting limit at the cap (H-0011's device on `time_exit`) | audit 15 | H-0011's mechanism with two free parameters; and the cap **lapses a working order by construction**, so patience cannot operate there |
| Partial exit approaching the cap | audit 6 | `mr_partial`; EXP-0036 |
| Conditional extension of the cap | audit 2 | EXP-0024, and it is the wrong direction — extending cannot recover a peak already passed |
| Exit early to free a slot | audit 2 | EXP-0019: monotone in holding period, "the edge is overnight." H-0020 measured +1.011% overnight vs −1.183% intraday per trade — cutting holding removes the nights that carry the return |

## 5. Why the residual cannot be captured by any reactive rule

After the haircut is set aside, the recoverable content sits in bars 16–20 and
requires knowing *where inside that window* the peak falls. A reactive rule
learns the peak has passed only by observing the retracement, and therefore
pays that retracement as its cost. EXP-0048 already recorded the arithmetic:
such a rule "gives back its threshold by construction… That eats a third to a
half before anything is captured."

Against a genuine, haircut-free terminal content of roughly 1.3% (the 1.996%
available after bar 15, less the 0.71% charge), a reactive threshold wide
enough not to fire on noise consumes most of it — and the fat tail is
unprotected, which is what defeated all 11 EXP-0036 configurations.

## 6. What would change this answer

Not a new threshold on daily bars. The residual is an **intraday path**
question: the give-back is intraday (H-0020: −1.183% intraday vs +1.011%
overnight per trade) and daily bars cannot locate it. H-0014 measured intraday
incremental information at ≈ +0.006 IC and H-0017 found full-universe quote
acquisition infeasible, so that route is already priced and closed.

**I am not proposing it.** It is recorded so the boundary is explicit.

## 7. Audit result

| # | check | state |
|---|---|---|
| 1 | targets the time-exit population | *no candidate registered* |
| 2 | not a shorter fixed time exit | — |
| 3 | not a generic trailing stop | **would fail** for the windowed-retracement form |
| 4 | not a fixed take-profit | — |
| 5 | not another RSI threshold | **would fail** for the RSI-progress form |
| 6 | not scaling out | **would fail** for the partial form |
| 7 | not a regime-varying prior exit | — |
| 8–9 | no future data; decision-time only | both coherence checks are forensic, not rule inputs |
| 10 | exactly one deterministic mechanism | none survives |
| 11 | no hidden parameter sweep | **would fail** for the windowed form (W and threshold free) |
| 12 | 54 prior exit configurations + H-0011 remain in DSR | **unchanged — nothing spent** |
| 13 | 110% MDD ceiling (14.2806%) | unchanged |
| 14 | clean OOS untouched | untouched; 0 sessions; opens 2026-10-12 |
| 15 | genuinely distinct from priors | **the decisive failure** |
| 16 | hypothesis about give-back, not raw return | the surviving mechanism was 93% accounting |
| 17 | no production code or parameters changed | confirmed |

## 8. Governance

No registration. Nothing added to `preregistrations.jsonl`; the count stays at
**21** and declared configurations at **60**. No economic configuration spent,
so the DSR history is unchanged at 54 prior exit configurations plus H-0011.
Three decade dataset accesses were consumed by the two coherence checks
(baseline re-verified at **+58.5889000000% / 698** in each).

Production unchanged: ATR ceiling 0.035 · RSI 35/60 · 20-bar cap · stop 2.5× ·
sizing, buckets, cash, guards, broker, learned models — all untouched.
Fingerprint `da22011e…c237b` unchanged. Clean OOS untouched. No live trading
change. Thirty-year reads 13.
