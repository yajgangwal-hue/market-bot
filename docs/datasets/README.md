# Governed research datasets

The content identities of the price data behind this project's research. The
data files themselves are never edited; these records make any copy
verifiable and any substitution detectable.

| dataset ID | status | SHA-256 | datasheet |
|---|---|---|---|
| `decade-2016-2026-split-adjusted-230` | **preserved** at `data/research/decade-2016-2026-split-adjusted-230/` | `935fed79de9803f1da2a380c6f3f76ab525b27c5d14830bbea4744a7bf73d4a7` | [decade-2016-2026.md](decade-2016-2026.md) |
| `thirty-year-1996-2026-229` | **lost** | none recorded | [thirty-year-1996-2026.md](thirty-year-1996-2026.md) |
| `h0014-daily-features-decade-230` | **preserved** at `data/research/h0014-daily-features-decade-230/` — **derived features**, not price data; reproduced byte-for-byte from the decade dataset | `7fbf76458b559695c4686c651de0600234417f98afa25a36df0ab14a8f548e57` | [h0014-daily-features.md](h0014-daily-features.md) |
| `intraday-exit-sessions-5min-698` | **preserved** at `data/research/intraday-exit-sessions-5min-698/` — raw 5-minute bars, the 698 baseline exit sessions (H-0013) | `071d519b490219b8b045e89b508960473dfb7ca3782c047fbc6fccdbab2541e6` | [intraday-preservation-2026-09-24.md](intraday-preservation-2026-09-24.md) |
| `spy-5min-2016-2026-quarterly-43` | **preserved** at `data/research/spy-5min-2016-2026-quarterly-43/` — raw SPY 5-minute bars (H-0013, H-0014); runs past the freeze, to 2026-09-18 | `9803ae210c0710960b7aa8c4de12b121a51adfc471643deeac599f6d8230d2c5` | [intraday-preservation-2026-09-24.md](intraday-preservation-2026-09-24.md) |
| `h0014-intraday-snapshots-230` | **preserved** at `data/research/h0014-intraday-snapshots-230/` — **derived** snapshot tables (H-0014) | `b38d525752a11c4515a19039272635cb51f9754f7b1ec35ca47770419c981ec3` | [intraday-preservation-2026-09-24.md](intraday-preservation-2026-09-24.md) |
| `h0017-trades-quotes-221` | **preserved** at `data/research/h0017-trades-quotes-221/` — raw trades and quotes, the 221 reverted exits (H-0017) | `22ea00853653a3fe8ce3bdfa6f25bc22400b7e3a16beaebb5e7e0442254eeb43` | [intraday-preservation-2026-09-24.md](intraday-preservation-2026-09-24.md) |

Machine-readable: [`registry.json`](registry.json), read by
`scripts/research_gate.py`.

## The rule — effective 2026-09-24

Before any **new** registered experiment computes a result:

1. **The registration names its dataset** as
   `parameters["dataset"] = {"id": <dataset ID>, "sha256": <dataset SHA-256>}`,
   with both values from `registry.json`.
2. **It also states:**
   - its population, in `parameters["population"]`;
   - its benchmark, in `parameters["benchmark"]` — the SPY series, price or
     total return, and the window;
   - its information boundary, in the existing `information_boundary` field;
   - its execution assumptions, in the existing `execution_assumptions` field.

   `research_gate.check_registration(h)` must return no problems before
   `register(h)` is called.
3. **The runner verifies before computing.** It calls
   `research_gate.verify_dataset(<id>, <sha256>)` and loads bars **only** from
   the path that returns. The call refuses an unknown dataset, a lost dataset,
   a copy under a temporary directory, a missing or extra file, any per-file
   mismatch, and a dataset-hash mismatch. Since 2026-09-24 the shared decade
   loader, `scripts/forensics_regime.load()`, does exactly this and fails
   closed. A runner that imports it complies; one that finds data any other
   way does not.

   Runners that load prices themselves call `research_gate.price_dir(folder)`
   (`"deep"` → the verified decade directory; `"long"` → refused, because the
   thirty-year data is lost) and `research_gate.dataset_file(dir, name)`.
   Every governed class-B script that reads decade prices now does this —
   [migration record](../2026-09-24-governed-research-dataset-migration.md).

   The only sanctioned scratchpad access is
   `research_gate.unpreserved_intraday_store(path)`, for the listed intraday
   stores below. It is allow-listed, verifies nothing, and cannot return
   decade data. Since the later 2026-09-24 preservation, four of its five stores have
   verified copies, registered above. The historical H-0013, H-0014 and H-0017
   runners were deliberately left pointing at the scratchpad originals, and
   none of those experiments has been re-run from the preserved copies.

This reuses the existing registration fields: `parameters` and the two named
fields are already sealed, so no schema changes and nothing in `src/` changes.
Registrations before 2026-09-24 are grandfathered, and the audit lists them
rather than failing them.

Audit at any time; this command is read-only:

```bash
python scripts/research_gate.py --audit
```

## Evidence classes

Three names, never interchangeable:

| class | what it is | may it accept a change? |
|---|---|---|
| **historical in-sample** | every dataset here, and every `research.DATASETS` name except `forward` | no — it can only reject |
| **paper operational** | what the live paper account records from 2026-09-11 (`research.FORWARD_START`): the audit log, equity readings, fills. **This includes the embargo sessions** | no — operational evidence only, never validation |
| **Clean OOS** | only the sessions the Phase 4 recorder accepts into `data/forward-evaluation.jsonl`, from `forward.first_clean_session()` — projected 2026-10-12 | only through the Phase 4 checkpoints |

`research.DATASETS["forward"]` labels the paper account from 2026-09-11
`clean`. That label predates the embargo; in the terms above it covers
paper-operational sessions first and Clean OOS sessions only after the embargo
(CONF-10; [preservation record](../2026-09-24-dataset-preservation-and-research-gate.md) §3).

## Not covered here

- **`etf_subset`** is not a separate file set. It is a subset of the decade
  and thirty-year files: 46 ETFs per `research.DATASETS`, and a 67-ETF variant
  built by H-0019 and H-0020 (AMB-8).
- **`crypto`** research data was not inventoried by this work.
- ~~**The intraday raw stores** behind H-0013, H-0014 and H-0017 remain **only**
  in the session scratchpad.~~ **Preserved later on 2026-09-24:** the four
  stores are now durable and hash-verifiable (the four rows above;
  [datasheet](intraday-preservation-2026-09-24.md)). **Input data preserved —
  no experiment re-run.** Still not preserved:
  - H-0014's raw 5-minute bars for the 230 symbols, which were never written
    to disk (the snapshots are the earliest retained form);
  - H-0008's `intraday_cache/`, which exists nowhere;
  - the Phase 1 probe store `raw/intraday-probe`, which no H-0013, H-0014
    or H-0017 code reads.

  The earlier text is kept below:

  > - **The intraday raw stores** behind H-0013, H-0014 and H-0017 remain **only**
  >   in the session scratchpad: `raw/` (980 files, 2.22 GB) and `snapshots/`
  >   (230 files, 3.03 GB). They are not preserved, have no
  >   manifest, and those hypotheses are not reproducible if the scratchpad is
  >   lost. Two more were recorded on 2026-09-24:
  >   - H-0008's five-minute store, `intraday_cache/`, is no longer present
  >     anywhere;
  >   - H-0014's daily-feature cache, `h0014-daily-features.json`, sits beside
  >     `snapshots/`. It is derived from the decade data. **Resolved later on
  >     2026-09-24:** the committed builder reproduced it byte-for-byte from the
  >     verified decade dataset. It is now registered as
  >     `h0014-daily-features-decade-230`, and H-0014 reads a verified copy
  >     ([datasheet](h0014-daily-features.md)). The scratchpad original is kept,
  >     untouched.