---
title: "Accepted Non-Conformances"
authority: "FROZEN"
kind: "production-status"
generated: false
sources:
  - "docs/2026-09-22-pre-oos-integrity-audit.md"
  - "docs/remediations.jsonl"
  - "docs/SPEC-0001-decision-boundary.md"
---

# Accepted Non-Conformances

> [!note] FROZEN — the frozen strategy as implemented
> Read from the linked sources at build time. If this note and a source differ, **the source governs**.

*Snapshot: built 2026-09-23 against repository HEAD `0d9ce4b`.*

Known differences between the implementation and [[SPEC-0001]] (or the ideal),
each explicitly accepted with a recorded reason. **Source:**
[pre-OOS integrity audit](../../docs/2026-09-22-pre-oos-integrity-audit.md) §I,
2026-09-22. The item wording below is quoted from that table; the SPEC column
is a pointer added here.

| # | item | recorded reason for accepting it | related |
|---|---|---|---|
| 1 | C-9 partial-vs-complete volume | “non-binding: H-0015 found cash the sole first-binding reason across 1,539 candidates” | [[SPEC-0001]] C-9; [[H-0015]] |
| 2 | legacy `bars_held` fallback would over-count by one | unreachable: all 4 live positions carried `opened_at_ts`, and every new position is stamped at entry | [[SPEC-0001]] §5; [[REM-0009]] |
| 3 | cancel-before-submit window | “Alpaca provides no atomic replace; telemetry cannot report a false "protected"” | [[Operational Safeguards]] |
| 4 | crash spanning the close | “bounded, documented; recovery is guaranteed at the next cycle” | [[Operational Safeguards]] |
| 5 | crypto has no broker-resident stop | “separate authorised track, out of scope” | [[Frozen Strategy]] |
| 6 | fingerprint cannot prove implementation conformance | documented governance limitation; conformance audited independently | [[Frozen Fingerprint]]; [[SPEC-0001]] C-21, C-22 |
| 7 | `test_learned_component_disabled.py:358` unguarded `data/` read | “test hygiene only; cannot affect the money path or OOS” | — |

The audit's own conclusion: “None of items 1–7 can change decision semantics,
invalidate equity protection, contaminate OOS, or make results
non-reproducible.” —
[pre-OOS integrity audit](../../docs/2026-09-22-pre-oos-integrity-audit.md)

## Reading these correctly

- **Item 4 is about recovery, not continuous protection.** Its wording is
  quoted exactly; it says recovery happens at the next cycle, and it does not
  claim that positions are protected during the window.
- **Item 2** is also recorded by the remediation that created the condition:
  “Verified unreachable: all 4 live positions carry opened_at_ts” —
  [remediations.jsonl](../../docs/remediations.jsonl) ([[REM-0009]]). The
  count of 4 is as of 2026-09-22.
- **Accepted is not fixed.** Each item is a known limit. Two possible future
  changes the audit recorded — an atomic order replace for item 3, and a
  conformance assertion for item 6 — are listed there as not implemented and
  not proposed; they appear in [[Research Gaps]] only as recorded, not as
  recommendations.
