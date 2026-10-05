---
title: "Agent Instructions"
authority: "NAVIGATION"
kind: "policy"
generated: false
sources:
  - "docs/SPEC-0001-decision-boundary.md"
  - "docs/phase4-clean-observation-protocol.md"
  - "src/event_aware_trader/modelgov/prereg.py"
  - "src/event_aware_trader/phase5/ledger.py"
  - "src/event_aware_trader/research.py"
  - "docs/2026-09-22-pre-oos-integrity-audit.md"
---

# Agent Instructions

> [!abstract] NAVIGATION — non-authoritative
> Organises and links. Asserts nothing beyond its cited sources and never overrides them.

*Snapshot: built 2026-09-23 against repository HEAD `0d9ce4b`.*

How any coding or research agent must use this vault. Each rule names the
governed source it rests on; **the source is the authority, not this page.**

> [!danger] This vault is not permission
> Nothing here authorises a change to the strategy, the money path, the
> broker, risk, the emulator, the benchmark, Clean OOS or any research
> conclusion. A note that seems to suggest a change is at most a pointer to
> evidence, and evidence goes through preregistration before it goes anywhere
> near production.

## The twelve rules

1. **Read the normative specifications first.** [[SPEC-0001]] is the
   decision-boundary contract and [[Clean OOS]] is the forward-evaluation
   contract. “Changing a normative clause of SPEC-0001 is a strategy semantics
   change.” — [SPEC-0001](../../docs/SPEC-0001-decision-boundary.md) (C-26).

2. **Check the frozen strategy before proposing any modification.**
   [[Frozen Strategy]], [[Frozen Parameters]], [[Frozen Fingerprint]] and
   [[Production Truth]] describe what exists. A proposal that does not state
   how it differs from these is not ready.

3. **Search existing research before proposing a new hypothesis.** Use
   [[Do Not Re-Research]], [[Research Index]] and [[Research Gaps]]; then search
   the ledgers and [[Reports Catalogue]] directly. Most areas an agent will
   think of have been tested, several of them more than once.

4. **Do not treat inconclusive evidence as validated.** The phase-5 ledger's
   own definition of its most favourable non-promoted verdict is “promising, on
   contaminated data, proves nothing” —
   [phase5/ledger.py](../../src/event_aware_trader/phase5/ledger.py). See
   [[Authority Levels]].

5. **Do not treat rejected ideas as production rules — or as impossible.** A
   REJECTED note records what was tested and what it showed. Only FROZEN notes,
   and [[Production Truth]] above all, describe behaviour.

6. **Never modify the money path because a research note suggests an idea.**
   Even a correction that brings code into line with an unchanged
   specification “still requires explicit owner approval and a money-path review
   before implementation” when it touches the live money path —
   [SPEC-0001](../../docs/SPEC-0001-decision-boundary.md) (C-27).

7. **Preregister before measuring an outcome.** A registration holds
   “Everything that must be fixed before the outcome is looked at.” —
   [prereg.py](../../src/event_aware_trader/modelgov/prereg.py). Never register
   after seeing a result, and never exceed `max_configurations`.

8. **Preserve information boundaries.** Use only information available at the
   decision timestamp as [[SPEC-0001]] defines it (C-1, C-2, §6). Label every
   price EXECUTABLE, MODEL-AVAILABLE or HINDSIGHT ONLY, and never count a
   hindsight price as an opportunity — see [[H-0025]] and [[H-0021]].

9. **Preserve Clean OOS contamination controls.** “Clean forward observations
   must never reach research code.” —
   [research.py](../../src/event_aware_trader/research.py). Every read of a
   historical dataset is gated and recorded in `docs/dataset-uses.jsonl`, and
   the thirty-year dataset's access count is part of the record. See
   [[Clean OOS]].

10. **Distinguish remediation from optimisation.** A remediation corrects an
    implementation or governance defect and records
    `economic_rules_changed` — every one so far records `false`
    ([[Remediation Index]]). If a change would alter a strategy result, it is
    not a remediation.

11. **Distinguish implementation conformance from strategy improvement.**
    Conformance means the same logical decision from the same permissible
    information (C-4, C-21); it is audited separately and is never a return
    claim. The fingerprint cannot prove conformance — see
    [[Accepted Non-Conformances]].

12. **Never use this vault to bypass governance.** When a note and its source
    disagree, the source governs. When two sources disagree, record it in
    [[Conflicts and Ambiguities]] and stop; do not resolve it silently.

## Before proposing research

Read [[Trading Decision Guardrails]] for the current limits on score
interpretation, exit evidence, shorting, and recognition of gains. It is a
navigation aid only; follow the cited specifications and ledgers.

1. Read [[Do Not Re-Research]] for the area. Name every prior item and state
   exactly how the proposal differs.
2. Read [[Research Gaps]]. If the question is listed as OOS-dependent or
   data-limited, historical re-analysis will not answer it.
3. Carry every prior configuration in the area into the proposal's
   multiple-testing burden.
4. Register it — `src/event_aware_trader/modelgov/prereg.py` — before any
   outcome is computed.
5. **Since 2026-09-24:** name a verified dataset. Put
   `parameters["dataset"] = {"id", "sha256"}` from
   `docs/datasets/registry.json`, plus `parameters["population"]` and
   `parameters["benchmark"]`, in the registration, and make
   `research_gate.check_registration(h)` return no problems before
   registering. The runner must call `research_gate.verify_dataset(...)` and
   load bars only from the path it returns — never from a temporary directory
   — [[Datasets]].

## Before touching code

1. Confirm `frozen_fingerprint()` still equals the value in
   [[Frozen Fingerprint]].
2. Confirm the change is either a registered strategy change or a
   specification-conformance correction with owner approval (C-26, C-27).
3. Record a remediation if it is one; never describe an optimisation as one.

## What an agent must not do with this vault

- Quote a note as if it were the specification.
- Edit a note marked `generated: true`; edit its source and rebuild.
- Add a conclusion without a source ([[Provenance Rule]]).
- Treat an index table, a map grouping or a heading as a finding.
