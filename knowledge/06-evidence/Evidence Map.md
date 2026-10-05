---
title: "Evidence Map"
authority: "NAVIGATION"
kind: "map"
generated: false
sources:
  - "docs/experiments.jsonl"
  - "docs/phase5-research.jsonl"
  - "docs/preregistrations.jsonl"
  - "docs/remediations.jsonl"
  - "docs/SPEC-0001-decision-boundary.md"
  - "docs/2026-09-22-h0024-capability-gap-report.md"
  - "docs/2026-09-22-emulator-live-fidelity-audit.md"
  - "docs/2026-09-22-canonical-decision-boundary-review.md"
  - "docs/2026-09-22-pre-oos-integrity-audit.md"
  - "docs/2026-09-21-h0021-candidate-design.md"
  - "docs/2026-09-23-h0025-gain-to-loss-forensics.md"
  - "docs/phase4-clean-observation-protocol.md"
---

# Evidence Map

> [!abstract] NAVIGATION — non-authoritative
> Organises and links. Asserts nothing beyond its cited sources and never overrides them.

*Snapshot: built 2026-09-23 against repository HEAD `0d9ce4b`.*

How hypotheses became experiments, results, decisions, implementations,
remediations and specification clauses. **Every arrow cites the source that
states it.** Where no source states a link, the step is marked
*chronological only* — it came later, and nothing more is claimed.

Obsidian's graph view and backlinks show every mention; this page shows only
the stated links.

## 1. Entry timing — measurement → accepted change → specification

| step | item | recorded outcome | the link, as stated |
|---|---|---|---|
| measurement | [[EXP-0005]] | measured: “73.6% of return is overnight” — [experiments.jsonl](../../docs/experiments.jsonl) | its reason: “the finding every later entry/exit decision rests on” |
| measurement | [[EXP-0008]] | measured | “the loss was not latency, it was the next-day open” — [experiments.jsonl](../../docs/experiments.jsonl) |
| decision | [[EXP-0016]] | **accepted** | “mechanism is causal (73.6% of return is the gap the bot was sitting out)” — [experiments.jsonl](../../docs/experiments.jsonl) |
| implementation | `entry_fill = "signal_close"` | in `PRODUCTION_CANDIDATE` | “SHIPPED as the 15:45 window” — [experiments.jsonl](../../docs/experiments.jsonl) |
| decision | [[EXP-0017]] | **reverted** — window back to 20 minutes | its date is the research freeze — [[Clean OOS]] |
| specification | [[SPEC-0001]] §4.1 | entry decided in the last 20 minutes of D | pre-OOS audit table: entry signal **PASS** |

## 2. Exit timing — from a haircut to a specification clause to a live correction

| step | item | recorded outcome | the link, as stated |
|---|---|---|---|
| measurement | [[EXP-0039]] → [[EXP-0048]] | registered, then measured: a ceiling, not a gain | EXP-0048 is the “RESULT for EXP-0039” — [experiments.jsonl](../../docs/experiments.jsonl) |
| hypothesis | [[H-0008]] | REJECTED — the haircut stands | *chronological only* |
| hypothesis | [[H-0012]] | INCONCLUSIVE — measurable but unstable | *chronological only* |
| hypothesis | [[H-0013]] | INCONCLUSIVE — partially stable | SPEC-0001: “Derived from sealed experiment methodology (H-0013)” — [SPEC-0001](../../docs/SPEC-0001-decision-boundary.md) |
| hypothesis | [[H-0024]] | INCONCLUSIVE — gap exists, value not established | its one recommended step: “Perform a narrowly defined architecture audit of the emulator/live exit-path divergence.” — [H-0024 report](../../docs/2026-09-22-h0024-capability-gap-report.md) |
| audit | [fidelity audit](../../docs/2026-09-22-emulator-live-fidelity-audit.md) | “Classification: B — FIDELITY GAP EXISTS, ECONOMIC IMPACT UNKNOWN” | “Follows H-0024 (B).” — [fidelity audit](../../docs/2026-09-22-emulator-live-fidelity-audit.md) |
| review | [boundary review](../../docs/2026-09-22-canonical-decision-boundary-review.md) | “Intent status: INTENT ESTABLISHED” | *chronological only* |
| specification | [[SPEC-0001]] v1.0.0 | NORMATIVE | records the intended boundary (C-1) |
| remediation | [[REM-0009]] | C-19 implemented in the live loop | “SPEC-0001 v1.0.0, clauses C-1, C-19” — [remediations.jsonl](../../docs/remediations.jsonl) |
| verification | [pre-OOS integrity audit](../../docs/2026-09-22-pre-oos-integrity-audit.md) | RSI rule exit **PASS** | evidence cell: “REM-0009; 18 tests” |
| later research | [[H-0025]] | INCONCLUSIVE | “Under the CANONICAL SPEC-0001 execution boundary” — [preregistrations.jsonl](../../docs/preregistrations.jsonl) |

## 3. Give-back — measurement → no candidate → correction

| step | item | recorded outcome | the link, as stated |
|---|---|---|---|
| hypothesis | [[H-0001]] | REJECTED — trailing stop on holding-cap trades | *chronological only* |
| hypothesis | [[H-0021]] | VALIDATED EVIDENCE of the give-back measurement | — |
| design | [candidate design](../../docs/2026-09-21-h0021-candidate-design.md) | “Outcome: NO NEW CANDIDATE.” | follows H-0021 |
| hypothesis | [[H-0025]] | INCONCLUSIVE — “Evidence is weak / inconclusive.” | “H-0021 measured give-back but” — [preregistrations.jsonl](../../docs/preregistrations.jsonl) |

What H-0025 changed about H-0021, in its own words, is on the [[H-0025]] note:
it reproduced H-0021's figures, corrected the execution boundary, and found
H-0021's conclusion survives. **No implementation followed either one.**

## 4. Profit lock — a promising result that did not survive

| step | item | recorded outcome | the link, as stated |
|---|---|---|---|
| hypothesis | [[H-0003]] → [[P5-0009]] | INCONCLUSIVE (`research_evidence`) | “it earns a new registration.” — [phase5-research.jsonl](../../docs/phase5-research.jsonl) |
| hypothesis | [[H-0005]] → [[P5-0015]] … [[P5-0018]] | REJECTED — a spike, not a gradient | “The breakeven lock's +13.71 points at a 1.0R trigger” — [preregistrations.jsonl](../../docs/preregistrations.jsonl) |

No implementation followed.

## 5. Opportunity generation — a nomination that did not validate

| step | item | recorded outcome | the link, as stated |
|---|---|---|---|
| hypothesis | [[H-0015]] | stopped at the governance gate | *chronological only* |
| hypothesis | [[H-0016]] | REJECTED — cash constraint not economically important | *chronological only* |
| hypothesis | [[H-0019]] | VALIDATED EVIDENCE of a gap; nominated P3 | — |
| hypothesis | [[H-0020]] | REJECTED — “Classification: C — NO EVIDENCE” — [H-0020 report](../../docs/2026-09-21-h0020-p3-validation.md) | “The P3 population excluded by the 3.5% ATR ceiling” — [preregistrations.jsonl](../../docs/preregistrations.jsonl) |

No implementation followed; the ATR ceiling is unchanged.

## 6. Take profit — two ledgers that disagree

[[EXP-0049]] → [[EXP-0050]] (measured), [[EXP-0051]] → [[EXP-0052]] (measured),
[[H-0002]] ([[P5-0008]], [[P5-0014]] — INCONCLUSIVE) and [[H-0010]] (REJECTED).
The disagreement is preserved, not resolved: [[Conflicts and Ambiguities]].
No take profit is in production — [[Frozen Parameters]].

## 7. Stop safety — a live defect to a remediation to a test

| step | item | the link, as stated |
|---|---|---|
| defect | 2026-09-21 BAC entry: 229 shares filled, stop sized from a stale read of 219 | [[REM-0007]] `what_was_wrong` |
| remediation | [[REM-0007]] | the settled fill, not the position read, now sizes the stop |
| test evidence | `tests/test_stop_coverage_race.py` | “tests/test_stop_coverage_race.py, 21 tests” — [remediations.jsonl](../../docs/remediations.jsonl) |
| safeguard | [[Operational Safeguards]] | — |

## 8. Clean OOS measurement integrity

[[REM-0003]] (benchmark on total return), [[REM-0004]] (positions recorded),
[[REM-0005]] (equity sleeve separated from the BTC sleeve), [[REM-0006]]
(continuity checked at record time) — all corrections to the recorder, all
made while it held zero observations. See [[Clean OOS]] and
[[Remediation Index]].

## 9. Fingerprint governance

[[REM-0001]] → [[REM-0002]] → [[Frozen Fingerprint]].

## 10. Survivorship

[[EXP-0031]] (measured) → [[H-0023]] (INCONCLUSIVE — a data limitation) →
[[Research Gaps]] (new data required) and [[Frozen Baseline]] (reproducible,
not validated).
