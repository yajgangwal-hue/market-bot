---
title: "Authority Levels"
authority: "NAVIGATION"
kind: "policy"
generated: false
sources:
  - "src/event_aware_trader/phase5/ledger.py"
  - "src/event_aware_trader/purge.py"
  - "docs/preregistrations.jsonl"
  - "docs/experiments.jsonl"
  - "docs/phase5-research.jsonl"
  - "docs/SPEC-0001-decision-boundary.md"
---

# Authority Levels

> [!abstract] NAVIGATION — non-authoritative
> Organises and links. Asserts nothing beyond its cited sources and never overrides them.

*Snapshot: built 2026-09-23 against repository HEAD `0d9ce4b`.*

Every note carries exactly one `authority` in its frontmatter. The label
describes the **subject** of the note — never the note itself. A NORMATIVE
note is a pointer to a normative source; the source is what governs.

## The levels

| level | meaning | may a note at this level describe what the bot does? |
|---|---|---|
| **NORMATIVE** | governs implementation. Here only [[SPEC-0001]], [[SPEC-0001 Clauses]] and the [[Clean OOS]] contract | no — it states what must be true; [[Production Truth]] states what is |
| **FROZEN** | describes the frozen strategy as implemented | yes — and only these notes do |
| **VALIDATED EVIDENCE** | a measurement that passed its registered controls, or an experiment the ledger records as `accepted`. **Every instance to date is in-sample on contaminated historical data**; none is out-of-sample (clarified 2026-09-23) | no. It validates the stated measurement — never a trading change, never future performance |
| **MEASUREMENT** | a recorded descriptive measurement with no accept/reject decision (`experiments.jsonl` decision `measured`) | no |
| **INCONCLUSIVE** | evidence exists but is insufficient for a production conclusion | no |
| **REJECTED** | an idea rejected under its documented criteria | no |
| **REMEDIATION** | an implementation or governance correction that was made | it records a change; it authorises none |
| **OPEN QUESTION** | an unresolved issue requiring future evidence | no |
| **HISTORICAL** | point-in-time or superseded material kept for provenance | no |
| **NAVIGATION** | indexes, maps and policy pages that organise and link | no — they assert nothing beyond their sources |

Every note at VALIDATED EVIDENCE, MEASUREMENT, INCONCLUSIVE, REJECTED, OPEN
QUESTION or HISTORICAL carries a **NOT A PRODUCTION RULE** banner. The
validator fails any such note without one.

**Two levels were added** to the owner's list, and why:

- **MEASUREMENT** — 12 experiments are recorded with decision `measured`. That
  is neither accepted nor rejected, and whether each passed "the applicable
  research controls" is not recorded, so labelling them VALIDATED EVIDENCE
  would claim something the ledger does not say.
- **NAVIGATION** — indexes and policy pages must carry a level, and none of the
  owner's levels describes a page whose only job is to point at sources.

## How each ledger's vocabulary maps

### `docs/experiments.jsonl` — field `decision`

| decision | count at snapshot | level | why |
|---|---:|---|---|
| `accepted` | 3 | VALIDATED EVIDENCE | adopted into the shipped configuration; config-changing per `purge.CONFIG_CHANGING` |
| `reverted` | 2 | REJECTED | adopted, then undone for a recorded reason; config-changing |
| `rejected` | 30 | REJECTED | the ledger's own word |
| `measured` | 12 | MEASUREMENT | descriptive; no decision recorded |
| `inconclusive` | 6 | INCONCLUSIVE | the ledger's own word. All six are registration rows whose result is a later row (“RESULT for EXP-…”); each note links its pair |

Only `accepted` and `reverted` ever moved the shipped configuration:
“The last date any experiment changed the shipped configuration.” —
[purge.py](../../src/event_aware_trader/purge.py) (`freeze_date`, reading
`CONFIG_CHANGING`).

### `docs/phase5-research.jsonl` — field `verdict`

| verdict | level | the ledger's own definition — [phase5/ledger.py](../../src/event_aware_trader/phase5/ledger.py) |
|---|---|---|
| `rejected` | REJECTED | “measured, and worse or no different” |
| `inconclusive` | INCONCLUSIVE | “the measurement could not separate the outcomes” |
| `research_evidence` | INCONCLUSIVE | “promising, on contaminated data, proves nothing” |
| `promotion_candidate` | VALIDATED EVIDENCE | “survived validation AND an untouched test period” — **no row has it** |

Phase-5 verdicts can never change production: “nothing here can "accept"
anything” — [phase5/ledger.py](../../src/event_aware_trader/phase5/ledger.py).

### `docs/preregistrations.jsonl` — hypotheses H-0001 … H-0025

A registration holds the sealed plan, not the outcome. The outcome is taken from
the source that records it — the phase-5 ledger for H-0001 … H-0010, the report
for H-0007 onward — as a **verbatim quotation**, checked against that file at
build time. Where a registration defines lettered outcomes (A/B/C/D), the level
follows the **registered meaning of the letter**, never the letter itself:

| registered meaning of the outcome | level |
|---|---|
| the measured thing exists or is material (typically A) | VALIDATED EVIDENCE — of that measurement only |
| exists but not established; partially stable; inconclusive (typically B) | INCONCLUSIVE |
| not important; no evidence; not the bottleneck (typically C) | REJECTED — the hypothesis's claim was not supported under its own criteria |
| a data or measurement limitation (typically D) | INCONCLUSIVE |
| stopped before any outcome was reached | INCONCLUSIVE |

Each hypothesis note prints the rule it applied and the registration's own
definition of its letter, so the classification can be audited.

### Two fixed rules

1. **Unregistered work is never classified above INCONCLUSIVE**, whatever its
   own report concludes, because it did not pass preregistration. This applies
   to [[H-0022]].
2. **A remediation is never evidence for a strategy change.** Its level is
   REMEDIATION, and every remediation row records `economic_rules_changed`.

## What a level cannot do

No level — including VALIDATED EVIDENCE — licenses a production change. Changing
a normative clause of the specification is a strategy semantics change with its
own governance path (C-26), and bringing an implementation into conformance
with it still needs explicit owner approval when it touches the money path
(C-27). See [[SPEC-0001]] and [[Agent Instructions]].
