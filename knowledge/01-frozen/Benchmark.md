---
title: "Benchmark"
authority: "FROZEN"
kind: "benchmark"
generated: false
sources:
  - "docs/benchmark-units.md"
  - "docs/remediations.jsonl"
  - "scripts/record_clean_session.py"
  - "src/event_aware_trader/forward.py"
  - "docs/experiments.jsonl"
  - "docs/phase5-research.jsonl"
  - "docs/phase3-forward-evaluation-protocol.md"
  - "docs/2026-09-16-phase2-acceptance-report.md"
---

# Benchmark

> [!note] FROZEN — the frozen strategy as implemented
> Read from the linked sources at build time. If this note and a source differ, **the source governs**.

*Snapshot: built 2026-09-23 against repository HEAD `0d9ce4b`. Corrected the
same day: an earlier version said only "SPY, on total return", which is true of
the forward record and not of the historical comparison.*

**The benchmark is SPY.** The governing definitions are in
[docs/benchmark-units.md](../../docs/benchmark-units.md). **Which SPY series is
used depends on the period, and the two must never be mixed.**

## Two bases, by period

| period | strategy side | SPY side | source |
|---|---|---|---|
| **historical research** — the decade window 2016-01-04 … 2026-09-04 | price data with no dividend adjustment; idle cash at 0% | **price only** — “the benchmark is understated by roughly 1.3-1.5 CAGR points per year” — [benchmark-units.md](../../docs/benchmark-units.md) | benchmark-units.md, worked example |
| **forward — Clean OOS** | the account's actual return, equity sleeve as headline ([[REM-0005]]) | **total return**: “The benchmark now uses adjustment='all', matching the declaration already inside the digest” — [remediations.jsonl](../../docs/remediations.jsonl) | [[REM-0003]], [`record_clean_session.py::adjustment="all"`](../../scripts/record_clean_session.py) |

The frozen fingerprint's own benchmark block declares `risk_free 0.0230`,
`basis_pre_2016 "price_vs_price"` and `basis_post_2016 "total_vs_total"` —
[`forward.py::"basis_post_2016": "total_vs_total"`](../../src/event_aware_trader/forward.py).
**Risk-free rate — fixed at 2.30% for Clean OOS (confirmed).** The Phase 3
protocol freezes the Phase 2 benchmark methodology with “rf = 2.30%;
365.25-day annualisation.” —
[Phase 3 protocol](../../docs/phase3-forward-evaluation-protocol.md) §1. Phase 2
specifies Sharpe and Sortino on daily returns, ×252 and ×√252, as excess over
that bill rate, “never over zero”, both legs through one `metrics()` —
[Phase 2 acceptance report](../../docs/2026-09-16-phase2-acceptance-report.md)
§6. The fingerprint's `risk_free 0.0230` is this declaration.

**Not yet implemented:** no committed code consumes it, and the Phase 2
`metrics()` was never committed. Research Sharpe ratios, including the
baseline's 0.5107, use zero — a research-emulator convention, not the Clean
OOS one — [[Frozen Baseline]], [[Clean OOS]].

*Corrected 2026-09-24:* an earlier version of this note said the rate was
unsettled and no rate had been chosen. That was wrong: the choice was made on
2026-09-15 —
[loader and Clean OOS audit](../../docs/2026-09-24-research-loader-and-clean-oos-integrity-audit.md)
§7.

REM-0003 measured the size of the difference: “SPY price return understates its
total return by about 1.58 points a year.” —
[remediations.jsonl](../../docs/remediations.jsonl)

## The current comparison, decade window

From [benchmark-units.md](../../docs/benchmark-units.md) unless marked:

| series | cumulative | CAGR | max drawdown |
|---|---:|---:|---:|
| SPY, price only | +283.14% | +13.42% | — |
| SPY, total return | — | +15.00% ¹ | −33.8% ² |
| frozen baseline (idle cash at 0%) | +58.59% | +4.42% | −12.98% |

¹ “SPY total return 15.00% (Alpaca adjustment=all, 2016-01-04..2026-09-14, CONFIRMED)” —
[experiments.jsonl](../../docs/experiments.jsonl) ([[EXP-0037]]). Its window
ends ten days later than the others.
² [[EXP-0038]]'s decade SPY figure.

- **Gap to SPY price return:** −224.55 points of cumulative return; −9.00 CAGR
  points a year — benchmark-units.md.
- **Gap to SPY total return:** about −10.6 CAGR points a year (4.42 against
  15.00, on windows that end ten days apart). Not separately registered.
- **Other frozen-baseline figures:** Sharpe 0.5107 (zero risk-free rate),
  annualised volatility 9.34%, Calmar 0.3408 — [[Frozen Baseline]].

**Use EXP-0037 and EXP-0038 for their SPY figures only.** Their strategy figures
predate the 2026-09-16 emulator correction recorded by [[EXP-0054]] and are not
the current baseline. Their recorded conclusion is that no configuration beats
SPY on total return: “No configuration in this project beats SPY on total
return.” — [experiments.jsonl](../../docs/experiments.jsonl); and “'Risk-adjusted
outperformance' is true only if risk means drawdown.” —
[experiments.jsonl](../../docs/experiments.jsonl).

## Why the two are not directly comparable

Stated in [benchmark-units.md](../../docs/benchmark-units.md), and none of it
corrected in the numbers above:

- the baseline holds idle cash at **0%** (the T-bill overlay is separate, and
  no post-correction decade figure with it exists in the ledgers);
- the strategy pays modelled costs and SPY buy-and-hold pays none;
- the strategy is invested 44.28% of the time and SPY 100%;
- the strategy's universe is today's survivors and SPY is not — [[H-0023]].

The document's summary sentence about the direction of these biases is
ambiguous — see [[Conflicts and Ambiguities]], AMB-4.

## The rules

From [benchmark-units.md](../../docs/benchmark-units.md):

1. “Every benchmark comparison names its reference asset and its unit.”
2. The comparison period is the strategy's own evaluation window, fixed before
   results are seen.
3. The benchmark definition does not change because a change would move the
   gap; a better SPY series is registered as its own change.
4. “SPY is a benchmark, not an optimisation target. No parameter may be chosen
   to improve a comparison against it.”

Changing the benchmark or its methodology is prohibited during Clean OOS —
[[Clean OOS]].
