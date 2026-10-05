---
title: "Provenance Rule"
authority: "NAVIGATION"
kind: "policy"
generated: false
sources:
  - "scripts/build_knowledge_base.py"
  - "scripts/validate_knowledge_base.py"
---

# Provenance Rule

> [!abstract] NAVIGATION — non-authoritative
> Organises and links. Asserts nothing beyond its cited sources and never overrides them.

*Snapshot: built 2026-09-23 against repository HEAD `0d9ce4b`.*

**Every factual claim in this vault names its source. An unsourced conclusion
does not belong here.**

## Acceptable sources, in order of preference

1. A **governed ledger row**, by ID and file: `docs/experiments.jsonl`,
   `docs/phase5-research.jsonl`, `docs/preregistrations.jsonl`,
   `docs/remediations.jsonl` — see [[Governance Ledgers]].
2. A **specification clause**: [[SPEC-0001]], by clause number.
3. A **code symbol**, cited as `file::symbol` so that the validator can confirm
   the symbol still exists.
4. A **commit** hash.
5. **Test evidence**: a named test file under `tests/`.
6. A **report** under `docs/`, cited by path — point-in-time, and the weakest
   of these, because later work may supersede it ([[Reports Catalogue]]).

## How quotations are kept honest

- **Curly quotation marks “…” are reserved for verbatim quotations.** Every
  one is checked by the validator against the file linked on the same line,
  or else against a file in the note's `sources`. A quotation that is not
  found fails validation. Straight quotes are used for everything else.
- A quotation ending in “…” was truncated for a table; the validator checks
  the part before the ellipsis.
- A hypothesis's outcome is never paraphrased. It appears as the quotation it
  rests on, and the generator refuses to write anything if one of those
  quotations no longer matches its file.

## When something cannot be verified

Write **UNVERIFIED** and say what is missing. Do not fill the gap with a
plausible value. Examples already in the vault: the population of every
`experiments.jsonl` row (the ledger has no such field), the date and the
sealed statement of [[H-0022]] (it was never registered), and the reason
EXP-0053 does not exist.

## When sources disagree

Preserve both, cite both, and record the disagreement in
[[Conflicts and Ambiguities]]. **Do not silently resolve it**, and do not pick
the one that reads better.

## Snapshot notes and generated notes

- A **generated** note (`generated: true`) is rebuilt from its sources by
  `scripts/build_knowledge_base.py`. Never edit one; edit the source and
  rebuild. The validator fails if a generated note has drifted.
- A **hand-written** note carries a *Snapshot* line with its date and the HEAD
  it was checked against. After that date, treat it as a pointer and re-check
  the facts at its sources.
