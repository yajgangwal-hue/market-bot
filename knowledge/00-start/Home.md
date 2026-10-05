---
title: "Home"
authority: "NAVIGATION"
kind: "hub"
generated: false
sources:
  - "docs/preregistrations.jsonl"
  - "docs/phase5-research.jsonl"
  - "docs/experiments.jsonl"
  - "docs/remediations.jsonl"
  - "docs/SPEC-0001-decision-boundary.md"
---

# Market-bot research knowledge base

> [!abstract] NAVIGATION — non-authoritative
> Organises and links. Asserts nothing beyond its cited sources and never overrides them.

*Snapshot: built 2026-09-23 against repository HEAD `0d9ce4b`; registered-hypothesis count updated 2026-09-28 for H-0026 (HEAD `fc6cf5b`); experiments count updated 2026-09-28 for EXP-0055, the owner's adaptive exits (uncommitted).*

This vault indexes the project's governed record — the decision-boundary
specification, the frozen strategy, the research and remediation ledgers, and
the reports — so that a person or an agent can find what is already known
before doing anything.

It is **documentation**. Nothing in the money path reads it, and no note in it
can authorise a change. Where a note and its source disagree, **the source
governs**.

## Read these first

1. [[Agent Instructions]] — mandatory for any coding or research agent.
2. [[Authority Levels]] — what each label on a note means, and how each
   ledger's vocabulary maps onto it.
3. [[Provenance Rule]] — every factual claim names its source, and verbatim
   quotations are machine-checked.

## Map

The folder numbers are the reading order [[Agent Instructions]] requires:
normative and frozen material before research.

| folder | notes | read it when |
|---|---|---|
| `01-frozen` | [[SPEC-0001]], [[SPEC-0001 Clauses]], [[Frozen Strategy]], [[Frozen Parameters]], [[Frozen Fingerprint]], [[Frozen Baseline]], [[Benchmark]], [[Clean OOS]] | before touching anything |
| `02-production` | [[Production Truth]], [[Operational Safeguards]], [[Accepted Non-Conformances]] | to know what the bot does now |
| `03-research` | [[Research Index]], [[Do Not Re-Research]], one note per hypothesis, experiment and phase-5 execution | before proposing research |
| `04-remediation` | [[Remediation Index]], one note per remediation | before changing an implementation |
| `05-open-questions` | [[Research Gaps]] | to see what is genuinely unanswered |
| `06-evidence` | [[Evidence Map]], [[Conflicts and Ambiguities]] | to trace why something is the way it is |
| `07-sources` | [[Governance Ledgers]], [[Datasets]], [[Reports Catalogue]] | to find and verify a source or a dataset |

## Coverage at snapshot

| item | count | source |
|---|---:|---|
| registered hypotheses | 38 | [docs/preregistrations.jsonl](../../docs/preregistrations.jsonl) |
| unregistered hypothesis-numbered audit | 1 (H-0022) | [[Conflicts and Ambiguities]] |
| phase-5 executions | 39 | [docs/phase5-research.jsonl](../../docs/phase5-research.jsonl) |
| experiments | 56 | [docs/experiments.jsonl](../../docs/experiments.jsonl) |
| remediations | 10 | [docs/remediations.jsonl](../../docs/remediations.jsonl) |
| SPEC-0001 clauses | 28 | [docs/SPEC-0001-decision-boundary.md](../../docs/SPEC-0001-decision-boundary.md) |

The validator recomputes these from the ledgers; see below.

## Opening it in Obsidian

Open the **repository root** as the vault, not `knowledge/`. Source links point
into `docs/`, `src/` and `scripts/`, which sit outside `knowledge/`; wikilinks
between notes work either way.

## Keeping it true

- `python scripts/build_knowledge_base.py` regenerates every note marked
  `generated: true` from the ledgers and the code. It never touches a
  hand-written note and refuses to run if it would.
- `python scripts/validate_knowledge_base.py` checks every link, identifier,
  authority label, banner and verbatim quotation, and fails if a generated note
  no longer matches its sources. Run both after any ledger append.
- Hand-written notes carry a *Snapshot* line. They describe the repository as
  of that date; after it, re-check them against their sources rather than
  trusting them.
