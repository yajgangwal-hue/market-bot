---
title: "Conflicts and Ambiguities"
authority: "NAVIGATION"
kind: "conflict-register"
generated: false
sources:
  - "docs/experiments.jsonl"
  - "docs/phase5-research.jsonl"
  - "docs/preregistrations.jsonl"
  - "docs/2026-09-20-h0012-report.md"
  - "docs/2026-09-22-h0019-recognized-gains-news-audit.md"
  - "docs/2026-09-21-h0017-report.md"
  - "docs/2026-09-20-h0011-report.md"
  - "docs/2026-09-20-h0011-validation-gate.md"
  - "docs/2026-09-23-h0025-gain-to-loss-forensics.md"
  - "docs/phase3-forward-evaluation-protocol.md"
  - "docs/phase4-clean-observation-protocol.md"
  - "README.md"
  - "START-HERE.md"
  - "docs/GO-LIVE.md"
  - "scripts/windows/stop-everything.ps1"
  - "src/event_aware_trader/autotrade.py"
  - "docs/2026-09-22-pre-oos-integrity-audit.md"
  - "docs/2026-09-21-h0021-candidate-design.md"
  - "docs/2026-09-20-h0013-report.md"
  - "docs/2026-09-17-h0008-report.md"
  - "docs/2026-09-21-research-gap-inventory.md"
  - "docs/benchmark-units.md"
  - "docs/2026-09-21-h0018-report.md"
  - "docs/2026-09-17-regime-forensics.md"
  - "docs/2026-09-17-bucket-forensics.md"
  - "src/event_aware_trader/research.py"
  - "docs/2026-09-21-h0020-p3-validation.md"
---

# Conflicts and Ambiguities

> [!abstract] NAVIGATION — non-authoritative
> Organises and links. Asserts nothing beyond its cited sources and never overrides them.

*Snapshot: built 2026-09-23 against repository HEAD `0d9ce4b`.*

Every place found where two sources disagree, or where a source is ambiguous.
**Both sides are preserved and quoted; none is resolved here.** Resolving one
is a governed decision — for the owner, or a registered piece of work — not an
edit to this vault.

Status key: **OPEN** — unresolved. **CORRECTED IN SOURCE** — a later governed
source records the correction; both are kept.

## Conflicts

### CONF-1. Take profit — two ledgers disagree · OPEN

- [[EXP-0050]]: “Return falls monotonically as the target tightens” and
  “2.0R costs 0.10” — [experiments.jsonl](../../docs/experiments.jsonl), a CAGR
  figure.
- [[H-0002]] / [[P5-0008]]: “REGISTERED AS EXPECTED TO FAIL, and it did not.” —
  [phase5-research.jsonl](../../docs/phase5-research.jsonl), recorded
  `research_evidence`. For the same 2.0R target, the corrected row
  [[P5-0014]] records `difference_from_baseline` of **+0.026849** cumulative
  return (the "2.7 points" in its text) and **+0.001647 CAGR**.
- In the same unit, then, the two ledgers report opposite signs for a 2.0R
  target.
- P5-0008 names the conflict and offers its own explanation: “This contradicts
  the earlier finding that every binding take-profit level cost return - that
  work predated the haircut and the participation cap.” —
  [phase5-research.jsonl](../../docs/phase5-research.jsonl)
- [[H-0012]] later lists H-0002 among results its repricing affects
  indirectly, with no trade log stored —
  [H-0012 report](../../docs/2026-09-20-h0012-report.md).
- [[H-0021]]'s registration summarises the prior ledger as “take profit
  monotonically negative” — [preregistrations.jsonl](../../docs/preregistrations.jsonl)
  — without citing H-0002.

By P5-0008's own account the two were run on different emulator versions. No
take profit is in production. Deciding which reading stands is not done here.

### CONF-2. H-0022 — one audit, two identifiers · OPEN

- The file is named `docs/2026-09-22-h0019-recognized-gains-news-audit.md`.
- The report says: “This work was commissioned as "H-0019".” and “The next
  free identifier is H-0022” — [report](../../docs/2026-09-22-h0019-recognized-gains-news-audit.md)
- It was never registered: “No experiment registered.” —
  [report](../../docs/2026-09-22-h0019-recognized-gains-news-audit.md). There
  is no H-0022 row in `preregistrations.jsonl`.
- It recommends its own rename, which has not been done.

This vault files it as [[H-0022]], at INCONCLUSIVE (unregistered). The real
[[H-0019]] is a different, sealed audit.

### CONF-3. H-0011's outcome, as reported elsewhere · OPEN

- [[H-0011]]'s own report: “Decision: INCONCLUSIVE.” —
  [H-0011 report](../../docs/2026-09-20-h0011-report.md); its adjudication file
  agrees; its validation gate: “Conclusion: B — H-0011 REPRODUCIBLE BUT
  FRAGILE” — [validation gate](../../docs/2026-09-20-h0011-validation-gate.md).
- [[H-0017]]'s report calls it rejected: “H-0011 was rejected” and “H-0011's
  rejection stands on grounds untouched by this measurement.” —
  [H-0017 report](../../docs/2026-09-21-h0017-report.md)

This vault records H-0011 as INCONCLUSIVE, from its own report.

### CONF-4. H-0017's outcome label vs its registered definition · OPEN

- Report: “Classification: A — EXECUTION QUESTION SUBSTANTIALLY NARROWED” —
  [H-0017 report](../../docs/2026-09-21-h0017-report.md)
- Registration, outcome (A): “GENUINE MICROSTRUCTURE CAPABILITY GAP” —
  [preregistrations.jsonl](../../docs/preregistrations.jsonl)

The wording differs. This vault does **not** judge whether the registered
conditions for A were met; it records the difference. [[H-0017]] is filed at
VALIDATED EVIDENCE of the measured execution facts only.

### CONF-5. H-0021's execution assumption · CORRECTED IN SOURCE

- [[H-0025]]: “H-0021's execution_assumptions say next-open fills are "exactly
  what the frozen entry mechanism already assumes," and they are not” —
  [H-0025 report](../../docs/2026-09-23-h0025-gain-to-loss-forensics.md)
- The same report finds the correction immaterial to H-0021's conclusion:
  “H-0021's conclusion survives its own broken premise.” —
  [H-0025 report](../../docs/2026-09-23-h0025-gain-to-loss-forensics.md)

H-0021's own record is not rewritten; both stand.

### CONF-6. The first clean session date · CORRECTED IN SOURCE

- Phase 3 protocol: “approximately 2026-10-09” —
  [Phase 3 protocol](../../docs/phase3-forward-evaluation-protocol.md)
- Phase 4 protocol: “A correction to the Phase 3 report.” and “2026-10-09 is
  the twentieth embargoed session” —
  [Phase 4 protocol](../../docs/phase4-clean-observation-protocol.md)

The date is computed at run time, not taken from either document — [[Clean OOS]].

### CONF-7. Early documents describe a strategy that is not the frozen one · OPEN

| document | statement | frozen state |
|---|---|---|
| [README.md](../../README.md) | “a signal formed after a daily close enters no earlier than the next daily open” | fills at the signal bar's own close — [[EXP-0016]] |
| [README.md](../../README.md) | “Fixed stop and target are calculated before position size.” | no take-profit target — [[Frozen Parameters]] |
| [START-HERE.md](../../START-HERE.md) | “the trailing stop line the bot uses” | no trailing stop — [[Frozen Strategy]] |
| [docs/GO-LIVE.md](../../docs/GO-LIVE.md) | “A long-only trend rule that stands aside in a” | long-only mean reversion — [[Frozen Strategy]] |

These files are left unedited. [[Reports Catalogue]] marks them SUPERSEDED IN
PART.

### CONF-8. The stop-everything script describes a ratchet the frozen rule does not use · OPEN

- [stop-everything.ps1](../../scripts/windows/stop-everything.ps1): “What stops
  is the ratchet.” — last changed 2026-09-03.
- The live loop, under the frozen `mean_reversion` rule, “leaves the stop where
  it was placed and closes when the oversold” condition resolves —
  [autotrade.py](../../src/event_aware_trader/autotrade.py). The ratchet code
  is on the other (trend) branch.

The script's operational claim that stops **remain** after the scheduler stops
is consistent with the code; its description of a raised stop is not.

### CONF-9. Clean OOS recorder principal: committed record vs observed state · OPEN

- The last committed audit: “Clean OOS gate: NOT READY” and “The elevated
  installer has not taken effect.” —
  [pre-OOS integrity audit](../../docs/2026-09-22-pre-oos-integrity-audit.md)
- Observed read-only on 2026-09-23: `EventAwareTraderCleanRecorder` principal
  **S4U**.

No committed artefact yet records a re-verification. Until one does, the
committed record says NOT READY and the observed state differs.

### CONF-10. Two definitions of "clean" forward data · OPEN

- `research.DATASETS["forward"]` declares the window as the paper account from
  `FORWARD_START` (2026-09-11) with status `clean`, and notes “the only unseen
  data for the current candidate” —
  [research.py](../../src/event_aware_trader/research.py).
- The Phase 4 protocol admits nothing before the 20-session embargo ends
  (projected first clean session 2026-10-12): “Sessions before that date are
  refused by the recorder, not filtered later.” —
  [Phase 4 protocol](../../docs/phase4-clean-observation-protocol.md)

The recorder enforces the Phase 4 definition, so nothing is contaminated.
Embargo-period paper results are **not** Clean OOS, whatever the registry
entry says. `scripts/benchmark.py` uses the registry's start date — see
[[Clean OOS]], isolation hazards. Added 2026-09-23. *Update 2026-09-24:* `scripts/benchmark.py` no longer
uses that date. Its forward window now comes from the Phase 4 clean record —
[loader audit](../../docs/2026-09-24-research-loader-and-clean-oos-integrity-audit.md) §8. The registry entry itself is unchanged: the conflict stands.

**Root cause, established 2026-09-24.** The `forward` entry and
`FORWARD_START` date from 2026-09-13 (commit `17a9c80`), when "clean" meant
*unseen*; the purge and embargo arrived on 2026-09-15 (`7958f45`, `dac3a1c`),
after which clean meant *unseen and past the embargo*. The entry was never
updated.

**Naming resolved in documentation, not in code.** The three evidence classes
— historical in-sample, paper operational, Clean OOS — are defined in
[docs/datasets/README.md](../../docs/datasets/README.md). `research.DATASETS`
is in `src/` and unchanged, so this entry stays OPEN until an approved change
renames or splits it —
[preservation record](../../docs/2026-09-24-dataset-preservation-and-research-gate.md) §3.

## Ambiguities

### AMB-1. "Validated" haircut

- [candidate design](../../docs/2026-09-21-h0021-candidate-design.md): “a
  charge H-0013 validated”.
- [[H-0013]]'s verdict: “Verdict: B — PARTIALLY STABLE” and “No model is
  adopted, nothing is promoted, production is unchanged.” —
  [H-0013 report](../../docs/2026-09-20-h0013-report.md)
- [[H-0008]]: “The 0.652% haircut stands unchanged” —
  [H-0008 report](../../docs/2026-09-17-h0008-report.md)

"Validated" is the design document's word, not H-0013's outcome.

### AMB-2. The research-gap inventory's category letters

The inventory classifies rows A–E and states “Category A: empty.” —
[inventory](../../docs/2026-09-21-research-gap-inventory.md) — but never
defines the letters in the file. [[Research Gaps]] does not reuse them.

### AMB-3. EXP-0053 does not exist

`experiments.jsonl` runs EXP-0001 … EXP-0054 with no EXP-0053. Nothing in the
tracked files or git history refers to it, so it is a numbering gap, not a
broken reference. Why it was skipped is UNVERIFIED.

### AMB-4. Which way the benchmark biases point

- [benchmark-units.md](../../docs/benchmark-units.md) concludes: “The direction
  of every known bias in this comparison favours SPY.”
- Its own table lists SPY dividends as excluded, so that “the benchmark is
  understated by roughly 1.3-1.5 CAGR points per year” —
  [benchmark-units.md](../../docs/benchmark-units.md). An understated SPY
  favours the strategy in the comparison. Its other listed biases — SPY paying
  no costs, idle cash earning 0% — favour SPY.

The biases point both ways, and their net direction is not measured. The same
sentence's other claim, “The real gap is wider than reported” —
[benchmark-units.md](../../docs/benchmark-units.md) — is consistent with the
dividend item. Added 2026-09-23.

### AMB-5. Is exposure "untested"?

- [[H-0018]] lists exposure as “untested, and see caution below” —
  [H-0018 report](../../docs/2026-09-21-h0018-report.md) — and its caution
  says the unused exposure is more likely correct refusal than missed alpha.
- Deploying idle capital into the index **was** tested: [[H-0006]] — “Failed
  clauses: volatility within 110% of baseline, drawdown within 110% of
  baseline.” — [phase5-research.jsonl](../../docs/phase5-research.jsonl); and
  [[EXP-0028]] — “risk-adjusted 3x worse” —
  [experiments.jsonl](../../docs/experiments.jsonl).

H-0018 may mean exposure raised *inside* the strategy rather than idle cash
deployed beside it; the report does not say. Added 2026-09-23.

### AMB-6. The Calmar quoted for the frozen strategy

- The research-gap inventory: the strategy wins on drawdown only “Calmar 0.75
  vs 0.45 decade” — [inventory](../../docs/2026-09-21-research-gap-inventory.md).
- The ledger's frozen baseline Calmar is **0.340829** (`baseline_metrics`,
  [phase5-research.jsonl](../../docs/phase5-research.jsonl)), with idle cash at
  0%.

The source of 0.75 is UNVERIFIED; it does not match the current frozen
baseline. On the ledger's figure the strategy's Calmar is below SPY's decade
0.45 ([[Benchmark]]). Added 2026-09-23.

### AMB-7. Which constraint rejects candidates — two stage definitions

- Regime forensics: “The correlation bucket is the constraint — 59.5% of all
  candidates” and “Cash blocks 3.2% of candidates.” —
  [regime forensics](../../docs/2026-09-17-regime-forensics.md)
- The research-gap inventory, from H-0015's sealed attribution: cash rejects
  841 of 1,539 evaluated candidates, and “Guard-level rejections (buckets,
  position count, 3-per-day) resolve earlier” —
  [inventory](../../docs/2026-09-21-research-gap-inventory.md)

The two count different populations at different stages, which the inventory
states; the exact reconciliation of the two percentages is UNVERIFIED. Both
sources agree that capacity is not the bottleneck: the bucket rule is “refusing
duplicated risk” — [bucket forensics](../../docs/2026-09-17-bucket-forensics.md)
— and [[H-0016]] found cash refuses the worse candidates. Added 2026-09-23.

### AMB-8. Two ETF survivorship controls

- The dataset registry defines the control as “46 broad ETFs, both windows” —
  [research.py](../../src/event_aware_trader/research.py) (`etf_subset`).
- [[H-0019]] and [[H-0020]] built a 67-ETF control by keyword match on
  instrument names: “The 67 broad ETFs are therefore the only survivorship-safe
  control available” —
  [H-0020 report](../../docs/2026-09-21-h0020-p3-validation.md). Their three
  reads are recorded under dataset `decade` with 67 symbols.

Both are subsets of the same 230 decade files. Which list "the ETF control"
means must be stated per experiment. Added 2026-09-23.

## Not conflicts

Older reports give counts that were true on their date — registrations,
declared configurations, experiments, sessions remaining. They are
point-in-time, not contradictions; check the ledgers for the current count
([[Governance Ledgers]]).
