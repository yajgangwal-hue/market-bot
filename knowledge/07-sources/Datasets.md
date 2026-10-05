---
title: "Datasets"
authority: "NAVIGATION"
kind: "source-guide"
generated: false
sources:
  - "docs/datasets/README.md"
  - "docs/datasets/registry.json"
  - "docs/datasets/decade-2016-2026.md"
  - "docs/datasets/thirty-year-1996-2026.md"
  - "docs/datasets/decade-2016-2026.sha256"
  - "docs/2026-09-24-dataset-preservation-and-research-gate.md"
  - "docs/2026-09-23-research-reproducibility-audit.md"
  - "scripts/research_gate.py"
---

# Datasets

> [!abstract] NAVIGATION — non-authoritative
> Organises and links. Asserts nothing beyond its cited sources and never overrides them.

*Snapshot: 2026-09-24, after the decade dataset was preserved. Not yet
committed to git.*

The price data behind the research, with a content identity for each dataset.
**Sources of record:** [docs/datasets/README.md](../../docs/datasets/README.md)
and [registry.json](../../docs/datasets/registry.json).

## Identity and status

| dataset | status | SHA-256 | reproducibility |
|---|---|---|---|
| `decade-2016-2026-split-adjusted-230` | **preserved**, byte-identical, at `data/research/decade-2016-2026-split-adjusted-230/` (gitignored, read-only, no off-machine backup) | `935fed79de9803f1da2a380c6f3f76ab525b27c5d14830bbea4744a7bf73d4a7` | the data is reproducible; provenance class **B** (not cryptographically tied to runs before 2026-09-23) — [datasheet](../../docs/datasets/decade-2016-2026.md) |
| `thirty-year-1996-2026-229` | **lost** — no raw copy exists | none | **non-reproducible**: 31 experiments, 24 phase-5 rows and 5 registrations carry thirty-year figures that cannot be re-derived; their records stand — [datasheet](../../docs/datasets/thirty-year-1996-2026.md) |

Every generated note for an affected item carries a "Thirty-year data —
non-reproducible" caution.

**The scratchpad original is not yet removable.**

- ~~`scripts/forensics_regime.py` looks the data up in the scratchpad at
  import time and would fail without it.~~ **Fixed later on 2026-09-24:** it
  now loads only through `research_gate.verify_dataset`, fail-closed, with no
  scratchpad fallback. Its 29 importers no longer need the scratchpad —
  [loader audit](../../docs/2026-09-24-research-loader-and-clean-oos-integrity-audit.md) §3–§5.
- ~~**22 other governed scripts** still depend on the scratchpad.~~
  **Migrated later on 2026-09-24:**
  - the 17 that read decade prices now do so only through
    `research_gate.price_dir("deep")`, fail-closed, with identical inputs and
    the 400-bar window unchanged;
  - 3 are intraday-only, and 2 read only derived files — [migration record](../../docs/2026-09-24-governed-research-dataset-migration.md).

  **Classification still B:** H-0014's decade-derived daily-feature cache
  (`h0014-daily-features.json`, in the scratchpad, unverified) is read by
  `h0014_analyse` and `h0014_ic_yearly` in preference to the verified data —
  [migration record](../../docs/2026-09-24-governed-research-dataset-migration.md) §14.1.

  **Closed later the same day — confirmed.** The committed builder
  (`90dc4bd`) reproduced the cache byte-for-byte from the verified decade
  dataset: SHA-256 `b653ac1f…4030`, with 0 of 3,190,344 values different.
  It is registered as `h0014-daily-features-decade-230` (derived features,
  not price data), and H-0014 now reads the verified copy, fail-closed.
  The decade research path is fully gated — [datasheet](../../docs/datasets/h0014-daily-features.md).
- ~~The intraday stores are **not** restored. They are scratchpad-only.~~
  **Preserved later on 2026-09-24:** they are now outside the scratchpad and
  hash-verifiable, byte-identical, read-only, registered and gate-verified —
  [intraday preservation](../../docs/datasets/intraday-preservation-2026-09-24.md):
  - `intraday-exit-sessions-5min-698` (H-0013);
  - `spy-5min-2016-2026-quarterly-43` (H-0013, H-0014);
  - `h0014-intraday-snapshots-230` (H-0014, derived);
  - `h0017-trades-quotes-221` (H-0017).

  **No experiment was re-run**, and the historical runners still read the
  scratchpad originals through `research_gate.unpreserved_intraday_store`.
  Still missing: H-0014's raw 5-minute bars for the 230 symbols (never written
  to disk), H-0008's `intraday_cache/` (gone), and the acquisition code of
  the stop-exit sessions and the SPY store (not in the repository).
- Outside governed research, the class-A seed builder and 7 ungoverned
  class-D scripts still read the scratchpad's decade copy.
- Scratchpad retirement also needs the ungoverned scripts' own lookups gone.
  Of the seven retirement criteria, three are met, one of them only for the
  shared loader — [loader audit](../../docs/2026-09-24-research-loader-and-clean-oos-integrity-audit.md) §11.
- The same scratchpad holds the only copies of the intraday data behind
  [[H-0013]], [[H-0014]] and [[H-0017]].

See [the preservation record](../../docs/2026-09-24-dataset-preservation-and-research-gate.md)
§2.

## The research dataset gate — effective 2026-09-24

A new registration must name its dataset ID and SHA-256 in
`parameters["dataset"]`, and state its population and benchmark in
`parameters`, and its information boundary and execution assumptions in their
existing fields. Its runner must call
[`research_gate.py::def verify_dataset`](../../scripts/research_gate.py) and
load only from the path that call returns.

- **What the gate refuses:** an unknown or lost dataset, a temporary-directory
  path, a missing or extra file, and any hash mismatch. It was negative-tested
  on throwaway copies.
- **Earlier registrations** are grandfathered.
- **Check at any time** with `python scripts/research_gate.py --audit`.

## Three evidence classes — never interchangeable

| class | covers |
|---|---|
| historical in-sample | every research dataset — can reject an idea, never accept one |
| paper operational | everything the paper account records from 2026-09-11, **including the embargo sessions** |
| Clean OOS | only sessions the Phase 4 recorder accepts, from the projected 2026-10-12 |

This resolves the naming half of CONF-10; `research.DATASETS` itself is
unchanged — [[Conflicts and Ambiguities]].

## Quality warnings on the decade dataset — not repaired

| symbol | date | observed | effect on governed results |
|---|---|---|---|
| SPY | 2026-02-02 | low 69.00 (69.005 in the file) versus close 695.41 | unknown |
| NVDA | 2024-06-10 | high 195.95 versus close 121.79 | unknown |
| MRK | 2021-06-11 | low 15.32 versus close 76.27 | unknown |
| VZ | 2026-01-08 | low 10.5999 versus close 40.57 | unknown |

Also 1,065 zero-volume bars. The reasons each is anomalous, and why its effect
is unknown, are on the [datasheet](../../docs/datasets/decade-2016-2026.md).
The emulator fires stops on the bar's low.

## The 400-bar signal window — a methodology dependency

Every traced reproduction of the frozen baseline ran with a monkeypatch that
shows the emulator's signal only the last 400 bars. It lives in 21 scripts,
including `forensics_regime.py`, and not in `src/`. Its effect is analytically
negligible: Wilder smoothing decays by 13/14 per bar, and no other input looks
back 400 bars. That has not been tested. **Future reproduction must keep it** —
[preservation record](../../docs/2026-09-24-dataset-preservation-and-research-gate.md)
§7.
