---
title: "Governance Ledgers"
authority: "NAVIGATION"
kind: "source-guide"
generated: false
sources:
  - "docs/experiments.jsonl"
  - "docs/phase5-research.jsonl"
  - "docs/preregistrations.jsonl"
  - "docs/remediations.jsonl"
  - "docs/model-lineage.jsonl"
  - "docs/dataset-uses.jsonl"
  - "src/event_aware_trader/modelgov/prereg.py"
  - "src/event_aware_trader/phase5/ledger.py"
  - "scripts/record_remediation.py"
  - "scripts/forensics_regime.py"
  - "src/event_aware_trader/data.py"
---

# Governance Ledgers

> [!abstract] NAVIGATION — non-authoritative
> Organises and links. Asserts nothing beyond its cited sources and never overrides them.

*Snapshot: built 2026-09-23 against repository HEAD `0d9ce4b`.*

The append-only records this vault is built from. **These are the sources of
record; every generated note is a rendering of one of their rows.**

| ledger | holds | rows at snapshot | integrity | vault notes |
|---|---|---:|---|---|
| [docs/preregistrations.jsonl](../../docs/preregistrations.jsonl) | sealed hypotheses H-0001 … H-0025 | 24 | hash-chained (`digest`, `previous`); each row sealed | [[Research Index]] |
| [docs/phase5-research.jsonl](../../docs/phase5-research.jsonl) | phase-5 executions P5-0001 … P5-0039 | 39 | append-only | one note per row |
| [docs/experiments.jsonl](../../docs/experiments.jsonl) | experiments EXP-0001 … EXP-0054 (no EXP-0053) | 53 | append-only; drives `purge.freeze_date` | one note per row |
| [docs/remediations.jsonl](../../docs/remediations.jsonl) | remediations REM-0001 … REM-0009 | 9 | hash-chained | [[Remediation Index]] |
| [docs/model-lineage.jsonl](../../docs/model-lineage.jsonl) | trained models and their trust status | 3 | hash-chained | [[Production Truth]] |
| [docs/dataset-uses.jsonl](../../docs/dataset-uses.jsonl) | every gated read of a historical dataset | grows with each run | append-only | [[Agent Instructions]] rule 9 |

## Datasets — outside version control

The ledgers are tracked; the price data behind most of them is not.

| dataset | where it is | state observed 2026-09-23 |
|---|---|---|
| decade, 2016–2026, 230 symbols | a Claude session scratchpad under the OS temp directory, found by glob — `scripts/forensics_regime.py` at `0d9ce4b` (that glob was removed on 2026-09-24) | one copy, 230 files, written 2026-09-08, unmodified since. Identity: `decade-2016-2026-split-adjusted-230`, SHA-256 `935fed79…73d4a7` — [manifest](../../docs/datasets/decade-2016-2026.manifest.json) |
| thirty-year, 1996–2026, 229 symbols per recorded read | same mechanism, `long/`; source Yahoo per the 2026-09-08 report | **not present anywhere on the machine**; no checksum or manifest was ever recorded. The recorded acquisition (Yahoo with a browser header, 1996 onward) is not in the repository; `data.fetch_yahoo_bars` is a generic yfinance fetcher (`auto_adjust=False`), not proven to be that acquisition, so the lost data's adjustment basis is UNVERIFIED |

Full inventory, dependency table and provenance classification:
[research reproducibility audit](../../docs/2026-09-23-research-reproducibility-audit.md).

**Updated 2026-09-24:** the decade dataset is **preserved** at
`data/research/decade-2016-2026-split-adjusted-230/`, verified byte-identical.
Dataset identities now live in
[docs/datasets/registry.json](../../docs/datasets/registry.json) and are
checked by `scripts/research_gate.py` — [[Datasets]]. Later that day the shared loader,
`scripts/forensics_regime.py`, was routed through that gate, fail-closed —
[loader audit](../../docs/2026-09-24-research-loader-and-clean-oos-integrity-audit.md).

The frozen baseline's equivalence gate and every thirty-year result depend on
these files. The dataset-use ledger records **how often** they were read
(decade 149, thirty-year 13 in the working tree on 2026-09-23), not **what**
they contained: no content hash of either price dataset is recorded in the
repository. (The only dataset fingerprints, in `docs/model-lineage.jsonl`,
cover the learned model's training rows.) [[Frozen Baseline]] states the
consequence.

## Verifying them

Read-only commands; none of them writes.

```bash
python -c "import sys; sys.path.insert(0, 'src'); from event_aware_trader.modelgov import prereg; print(prereg.verify_chain())"
```

```bash
python scripts/record_remediation.py --verify
```

```bash
python -c "import sys; sys.path.insert(0, 'src'); from event_aware_trader import research, purge; r = research.load_registry(); print(len(r), purge.freeze_date(r))"
```

`record_remediation.py` **without** `--verify` appends rows. Use the flag.

## Vocabulary

Each ledger has its own outcome vocabulary, and the vault maps each onto one
authority level — [[Authority Levels]]. The phase-5 ledger's vocabulary is
defined in [phase5/ledger.py](../../src/event_aware_trader/phase5/ledger.py);
the registration schema in
[`prereg.py::class Hypothesis`](../../src/event_aware_trader/modelgov/prereg.py).
