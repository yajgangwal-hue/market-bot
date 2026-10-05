---
title: "Frozen Baseline"
authority: "FROZEN"
kind: "baseline"
generated: false
sources:
  - "docs/phase5-research.jsonl"
  - "docs/SPEC-0001-decision-boundary.md"
  - "docs/benchmark-units.md"
  - "docs/2026-09-21-research-gap-inventory.md"
  - "src/event_aware_trader/research.py"
  - "docs/2026-09-22-h0023-survivorship-ceiling-audit.md"
  - "src/event_aware_trader/evaluation.py"
  - "scripts/forensics_regime.py"
---

# Frozen Baseline

> [!note] FROZEN — the frozen strategy as implemented
> Read from the linked sources at build time. If this note and a source differ, **the source governs**.

*Snapshot: built 2026-09-23 against repository HEAD `0d9ce4b`.*

The frozen strategy's result on the development ("decade") dataset — the
reference every research runner must reproduce before computing anything else.

| metric | value |
|---|---|
| cumulative return | **+58.5889000000%** (0.585889) |
| CAGR | 4.4248% |
| trades | **698** |
| Sharpe | 0.5107 — zero risk-free rate |
| annualised volatility | 9.3372% |
| maximum drawdown | −12.9824% |
| Calmar | 0.3408 |
| exposure | 44.2794% |
| idle cash | earns **0%** in this figure |

Sharpe is mean over standard deviation of daily returns × √252 with no
risk-free deduction — [`evaluation.py::def _ratio`](../../src/event_aware_trader/evaluation.py);
“the simulator holds idle cash at 0%” — [benchmark-units.md](../../docs/benchmark-units.md).
Window: 2016-01-04 … 2026-09-04.

**Source of record:** `baseline_metrics` on 28 rows of
[docs/phase5-research.jsonl](../../docs/phase5-research.jsonl), the first
P5-0001 and the last P5-0038, all carrying exactly these values (the other
eleven rows record a different or partial baseline block). [[SPEC-0001]] C-28 states that the
specification leaves it unaffected.

## How it is used

- **Equivalence gate.** Research runners reproduce it first and stop if the
  total return differs by more than 5×10⁻⁷ or the trade count is not 698. See,
  for example, `scripts/run_h0025.py`.
- **Units.** It is a *cumulative* return over the decade window, not a CAGR.
  [docs/benchmark-units.md](../../docs/benchmark-units.md) defines the five
  quantities and gives the same baseline as a CAGR of +4.42%. Always name the
  unit — [[Benchmark]].

## Reproducibility — the data is identified and preserved (2026-09-24)

**Preserved 2026-09-24**, byte-identical: `data/research/decade-2016-2026-split-adjusted-230/`,
verified against the checksum list by two independent tools. It is gitignored
and has no off-machine backup yet. Every traced baseline run used a 400-bar
signal window that future reproduction must keep, and four bad vendor prints
are recorded, not repaired — [[Datasets]].

**The shared loader is gated (later on 2026-09-24).** `scripts/forensics_regime.py`
now loads only through
[`forensics_regime.py::verify_dataset(DECADE_DATASET, DECADE_SHA256)`](../../scripts/forensics_regime.py).
It fails closed and has no scratchpad fallback. The 400-bar window lines are
byte-identical, and the loaded input is identical: 230 symbols, 582,324 bars.
So the equivalence gate of every runner importing that loader, including
`run_h0025.py`, no longer needs the scratchpad —
[loader audit](../../docs/2026-09-24-research-loader-and-clean-oos-integrity-audit.md) §3–§5.
Later the same day, the 17 other governed scripts that read decade prices were
routed through the same gate, with identical inputs and an unchanged 400-bar
window. They include the H-0005 … H-0008 runners, the phase-5 scripts that
wrote `baseline_metrics`, and `run_sealed_exits`. The one decade-derived gap, H-0014's daily-feature cache, was closed the same
day: the committed builder reproduced it byte-for-byte from the verified
dataset, and H-0014 now reads a registered, verified copy — [datasheet](../../docs/datasets/h0014-daily-features.md).

The section below is the 2026-09-23 record, kept as written apart from one
citation. It named a line of the loader that the 2026-09-24 change removed,
and now points to the loader as it was at commit `0d9ce4b`.

## Reproducibility — the data is identified but not preserved (2026-09-23)

The decade dataset the baseline is reproduced from is **not version-controlled**.
Research scripts locate it with a glob over Claude session scratchpads in the
operating system's temp directory — `scripts/forensics_regime.py` at `0d9ce4b`,
`glob(".../scratchpad/deep")[0]` — and take the first match. Observed on 2026-09-23: exactly one copy (230 files)
inside one session's scratchpad; the thirty-year `long/` dataset no longer
present. If that directory is cleaned, the equivalence gate cannot be run and
thirty-year results cannot be reproduced.

**Identity recorded 2026-09-23:** dataset
`decade-2016-2026-split-adjusted-230`, SHA-256
`935fed79de9803f1da2a380c6f3f76ab525b27c5d14830bbea4744a7bf73d4a7`, 230 files —
[manifest](../../docs/datasets/decade-2016-2026.manifest.json),
[per-file checksums](../../docs/datasets/decade-2016-2026.sha256). Provenance
class **B**: identifiable, but not cryptographically tied to runs before
2026-09-23 — [research reproducibility audit](../../docs/2026-09-23-research-reproducibility-audit.md).
See [[Governance Ledgers]].

## What it is not

- **Not a forecast and not an out-of-sample result.** The decade dataset is
  contaminated for this candidate, so it can reject an idea but never accept
  one: “data this candidate was tuned on can still REJECT an idea” —
  [research.py](../../src/event_aware_trader/research.py). Only [[Clean OOS]]
  can produce uncontaminated evidence.
- **Reproducible, not validated.** Research runners reproduce it as a
  reference; that is not a claim it is correct. [[H-0023]] records: “Until
  then, no further economic search should treat +58.5889% as a validated
  baseline.” —
  [H-0023 report](../../docs/2026-09-22-h0023-survivorship-ceiling-audit.md)
- **Not survivorship-free.** The universe is today's listed names. The size of
  that bias is bounded but not measured: “EXP-0031: decade CAGR 9.14 → 3.82,
  thirty-year 5.66 → 2.24, positive in both halves.” —
  [research-gap inventory](../../docs/2026-09-21-research-gap-inventory.md);
  a point-in-time universe could not be reconstructed — [[H-0023]].
- **Not a claim to beat SPY** — [[Benchmark]].
