---
title: "Research Gaps"
authority: "OPEN QUESTION"
kind: "gap-register"
generated: false
sources:
  - "docs/2026-09-21-research-gap-inventory.md"
  - "docs/2026-09-22-h0023-survivorship-ceiling-audit.md"
  - "docs/2026-09-22-h0024-capability-gap-report.md"
  - "docs/2026-09-22-h0019-recognized-gains-news-audit.md"
  - "docs/2026-09-23-h0025-gain-to-loss-forensics.md"
  - "docs/2026-09-22-pre-oos-integrity-audit.md"
  - "docs/phase4-clean-observation-protocol.md"
  - "docs/2026-09-22-emulator-live-fidelity-audit.md"
  - "docs/2026-09-18-copy-trading-feasibility.md"
  - "docs/experiments.jsonl"
---

# Research Gaps

> [!warning] NOT A PRODUCTION RULE
> Authority: **OPEN QUESTION**. This note records an unresolved question. It does not describe, change or authorise any trading behaviour. What the bot does: [[Production Truth]]. What governs it: [[SPEC-0001]] and [[Frozen Strategy]].

*Snapshot: built 2026-09-23 against repository HEAD `0d9ce4b`.*

**Conservative by construction.** Every entry below is placed by a governed
item that already said so — the research-gap inventory of 2026-09-21 and the
work registered after it. Nothing is listed to fill a category, and an entry
here is **not** a proposal: each still needs its own preregistration.

The inventory's own verdict still stands: “No research direction currently
available with existing data is strong enough to justify a new experiment.” —
[research-gap inventory](../../docs/2026-09-21-research-gap-inventory.md).
It also reports “Category A: empty.” — no direction that was both testable with
existing data and genuinely novel.

> [!note] About the inventory's category letters
> The inventory marks each row A–E but never defines the letters in the file.
> They are not reused here; each row below is placed from its own recorded
> text. See [[Conflicts and Ambiguities]].

## Closed — answered sufficiently with existing data

Tested, with the recorded decision value "none". Details and every item:
[[Do Not Re-Research]].

| question | answered by | inventory row |
|---|---|---|
| entry filters on ATR floor, trend margin, pullback, volume, and their composition | [[P5-0001]] … [[P5-0005]] | 1 |
| insider transactions (Form 4) | the Form 4 study | 5 |
| exit-rule redesign, any family | [[Do Not Re-Research]] — exits | 6 |
| queue resolution / depth of book | [[H-0017]], [[H-0018]] | 8 |
| regime gating, sizing and exits | [[P5-0022]], [[EXP-0042]], [[EXP-0043]], [[EXP-0044]], [[EXP-0045]], [[EXP-0047]], [[H-0007]] | 9 |
| news as an entry filter | [[EXP-0041]], [[P5-0011]] … [[P5-0013]] | 10 |
| cross-sectional ranking / relative strength | [[EXP-0025]], [[H-0019]] (P4) | 11 |
| the ATR ceiling / P3 population | [[H-0019]], [[H-0020]] | 12 |
| portfolio capacity, cash and slots | [[H-0015]], [[H-0016]], [[H-0020]] | 13 |
| candidate allocation order | [[EXP-0025]] | 14 |
| idle-cash deployment | [[EXP-0014]], [[EXP-0028]], [[H-0006]] | 15 |
| shorting / the inverse signal | [[EXP-0011]], [[EXP-0012]], [[EXP-0013]], [[EXP-0026]] | 18 |
| crypto sleeve expansion | [[EXP-0003]], [[EXP-0032]] … [[EXP-0035]] | 19 |
| a learned-model veto | [[EXP-0029]] | 20 |
| give-back / profit realisation | [[H-0021]] (in row 6), then [[H-0025]] | 6, and after the inventory |
| recognised-gain accounting | [[H-0022]] — **unregistered**; its own report says “Both branches close.” — [H-0022 report](../../docs/2026-09-22-h0019-recognized-gains-news-audit.md) | after the inventory |

Added 2026-09-23 by the research reproducibility audit — closed with existing
evidence, previously missing from this table:

| question | answered by | source |
|---|---|---|
| RSI threshold direction (entry and exit) | [[H-0009]] (RSI 36–38 admission rejected), [[EXP-0006]], [[EXP-0023]] | [[Do Not Re-Research]] |
| sizing — risk per trade, per-name cap, names per bucket, regime-tilted size | [[EXP-0046]], [[EXP-0021]], [[EXP-0001]], [[EXP-0045]] → [[EXP-0047]]; “size multiplies edge and there is not much edge to multiply” — [experiments.jsonl](../../docs/experiments.jsonl) | experiments ledger |
| copy trading | “H-COPY is not justified.” — [copy-trading feasibility](../../docs/2026-09-18-copy-trading-feasibility.md) | unregistered feasibility study |
| the existing intraday economic hypothesis | “the only intraday economic question has been sealed and answered by H-0014” — [H-0024 report](../../docs/2026-09-22-h0024-capability-gap-report.md); also [[H-0011]] (INCONCLUSIVE), [[EXP-0007]] | [[H-0014]], [[H-0024]] |
| exposure levers already tested | [[EXP-0009]] (volatility targeting), [[EXP-0028]] and [[H-0006]] (idle cash in the index), [[EXP-0046]] (larger risk) | see AMB-5 in [[Conflicts and Ambiguities]] |

"Closed" means *these configurations, on this data, were tested*. It is not a
claim that the idea is impossible.

## Untested, and not open

| question | status | why it is not open |
|---|---|---|
| volatility-triggered exits | **never registered or run as a rule** — not adjudicated | the only relevant measurement points the other way — [[H-0025]]: crossing-time ATR/price is positively associated with outcome — and the exit family already carries ~77 configurations ([[Do Not Re-Research]]) |

## Data-limited — cannot be answered with the data that exists

| question | why it is blocked | source |
|---|---|---|
| **How large is the edge on a survivorship-free universe?** | the point-in-time universe could not be reconstructed | [[H-0023]] — outcome D |
| **Does news carry economic information?** | “That sub-branch is blocked by D (data limitation)” — [H-0022 report](../../docs/2026-09-22-h0019-recognized-gains-news-audit.md) | [[H-0022]] |
| **Can a rule locate the time-exit peak in real time?** | needs an intraday path the daily data does not have; [[H-0014]] caps the expected value near zero | inventory row 7 |

H-0023's operative consequence applies to everything above and below it:
“Until then, no further economic search should treat +58.5889% as a validated
baseline.” — [H-0023 report](../../docs/2026-09-22-h0023-survivorship-ceiling-audit.md)

## New-data-required — needs a new vendor or source

Each item names the minimum data its source recorded. None is authorised; each
is a licensing decision left to the owner.

| question | minimum data the source recorded | source |
|---|---|---|
| survivorship-free universe | a delisting-complete security master; delisting reason and terminal value; point-in-time symbol mapping | [[H-0023]] §G |
| news information | article bodies; a true availability timestamp; stationary coverage; deletion/revision provenance | [[H-0022]], next step |
| options-implied volatility and skew at entry | a point-in-time options vendor | inventory row 2 |
| short interest / borrow | a point-in-time short-interest feed | inventory row 3 |
| fundamentals / estimate revisions | point-in-time fundamentals with restatement history | inventory row 4 |

The inventory ranks the survivorship-free universe highest because it would
**resize** the existing edge rather than propose a new one; H-0022 and H-0023
record the same ranking.

## OOS-dependent (holdout-limited) — to be answered by Clean OOS, not by historical re-analysis

This also governs **every future candidate**: contaminated data can reject a
proposal but never accept it, so any newly proposed strategy is holdout-limited
by construction — [[Clean OOS]].

| question | how Clean OOS answers it | source |
|---|---|---|
| does the frozen strategy's result persist out of sample? | the forward record itself — “Nothing historical can substitute” — [inventory](../../docs/2026-09-21-research-gap-inventory.md) | inventory row 17; [[Clean OOS]] |
| does live trigger-to-close drift on rule exits match the 0.652% bound? | live `reverted` and `time` exits are measured and reported **beside** the frozen bound, never in place of it | [Phase 4 protocol](../../docs/phase4-clean-observation-protocol.md) §7 |

## Monitoring — watch, do not act

| item | what to watch | source |
|---|---|---|
| gain-to-loss share across time | “Gain-to-loss share by chronological third at +2%: 14.3% / 23.2% / 24.4%” — [H-0025 report](../../docs/2026-09-23-h0025-gain-to-loss-forensics.md). H-0025 records it as unsettled, a monitoring item and not a hypothesis | [[H-0025]] |
| recorder principal re-verification | observed S4U on 2026-09-23, but no committed artefact re-verifies it after the last audit's NOT READY | [[Clean OOS]], [[Conflicts and Ambiguities]] |

## Reproducibility risk — bounds every item on this page

The decade price dataset lives outside version control, in a session
scratchpad, and the thirty-year dataset was not present on 2026-09-23. Added
2026-09-23 — [[Governance Ledgers]], [[Frozen Baseline]].

Updated the same day by the
[research reproducibility audit](../../docs/2026-09-23-research-reproducibility-audit.md):
the decade dataset now has a recorded content identity (SHA-256 `935fed79…73d4a7`)
but is still **not preserved** outside the temporary scratchpad; the
thirty-year raw data is **unrecoverable**, so the thirty-year results in the
ledgers are non-reproducible from retained raw data. Their records stand
unedited.

**Updated 2026-09-24:** the decade dataset is now **preserved**, byte-identical,
outside the scratchpad, and a research dataset gate requires every new
registration to name a verified dataset — [[Datasets]]. The thirty-year data is
still lost. One shared loader, `scripts/forensics_regime.py`, still reads the
scratchpad: it is the minimum correction before a new governed experiment can
run reproducibly.

**Updated later on 2026-09-24:** that loader now loads only through the gate,
fail-closed, with no scratchpad fallback and the 400-bar window unchanged. Its
29 importers — every runner of H-0009 … H-0025 that uses it — reach the
preserved dataset through a verified path. **Still outside the gate:** 22
other governed scripts, the H-0005 … H-0008 runners, the phase-5 ledger
scripts, the H-0003 audit and the H-0013 / H-0014 / H-0017 pipelines. Of
these, 20 locate the scratchpad themselves or at import, and 2 read files
derived from it. Many also need the lost thirty-year data or the unpreserved
intraday stores, so their historical results stay non-reproducible whatever
the loader does — [loader audit](../../docs/2026-09-24-research-loader-and-clean-oos-integrity-audit.md) §4.

**Updated again, later on 2026-09-24:** those 22 were migrated —
[migration record](../../docs/2026-09-24-governed-research-dataset-migration.md):
- the 17 that read decade prices now read them only through the gate, with
  identical inputs and the 400-bar window unchanged;
- the thirty-year `long` label is always refused;
- 3 are intraday-only, and 2 read only derived files.

**Still open:**
1. ~~**Decade:** H-0014's daily-feature cache is unverified.~~ **Closed later
   the same day:** reproduced byte-for-byte from the verified dataset by the
   committed builder, registered, and now read as a verified copy — [datasheet](../../docs/datasets/h0014-daily-features.md).
   No decade-data gap remains in governed research.
2. **Intraday:** ~~no intraday result is reproducible without the
   scratchpad.~~ **Updated later on 2026-09-24:**
   - The inputs H-0013, H-0014 and H-0017 read are preserved outside the
     scratchpad and hash-verifiable — [intraday preservation](../../docs/datasets/intraday-preservation-2026-09-24.md).
   - **The experiments were not re-run, and are not claimed reproducible.**
   - Still missing:
     - H-0014's raw 5-minute bars (never retained; the snapshots are the
       earliest retained form);
     - H-0008's intraday store (gone);
     - the acquisition code of the 239 stop-exit sessions and of the SPY
       store (not in the repository).
3. **External:** the phase-5 news archive is an external pull with no
   preserved copy.

None of this reopens a result; the caveats above still hold.

## Recorded engineering ideas — not research, not proposed

The pre-OOS integrity audit recorded two possible changes and proposed neither:
an atomic order replace to remove the cancel-before-submit window, and a
conformance assertion the fingerprint cannot provide. See
[[Accepted Non-Conformances]].

## Superseded as a gap

| question | what closed it | source |
|---|---|---|
| does the emulator's exit path match the live bot's? | [[H-0024]] recommended the audit; the fidelity audit found “Classification: B — FIDELITY GAP EXISTS, ECONOMIC IMPACT UNKNOWN” — [fidelity audit](../../docs/2026-09-22-emulator-live-fidelity-audit.md); [[SPEC-0001]] defined the boundary; [[REM-0009]] implemented C-19 | [[Evidence Map]] |
