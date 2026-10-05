---
title: "Clean OOS"
authority: "NORMATIVE"
kind: "protocol"
generated: false
sources:
  - "docs/phase4-clean-observation-protocol.md"
  - "docs/phase3-forward-evaluation-protocol.md"
  - "src/event_aware_trader/forward.py"
  - "src/event_aware_trader/purge.py"
  - "src/event_aware_trader/research.py"
  - "scripts/record_clean_session.py"
  - "docs/2026-09-22-pre-oos-integrity-audit.md"
  - "scripts/benchmark.py"
  - "docs/2026-09-16-phase2-acceptance-report.md"
  - "docs/2026-09-24-research-loader-and-clean-oos-integrity-audit.md"
  - "docs/2026-09-24-governed-research-dataset-migration.md"
---

# Clean OOS — the forward-evaluation contract

> [!important] NORMATIVE — pointer note
> The governing text is the linked source. This note indexes it; if the two ever differ, **the source governs**.

> [!warning] Updated 2026-09-28 — EXP-0055 changed the strategy
> The owner's adaptive volatility exits are live from the session of 2026-09-29.
> - **Take profit:** every position also has one. Since 2026-10-04 (EXP-0057)
>   it is the session's bounce price - the close that would put RSI(14) at 60 -
>   refreshed each session; before that, k_tp × its entry ATR (2.5). It is
>   checked against the broker's mark after the stop, the bounce exit and the
>   20-session cap, and rests at the broker (EXP-0056).
> - **Learning:** a slow rule may move the stop multiple one step at a time
>   (and k_tp too, in the take-profit mode "atr" that EXP-0057 replaced).
> - **Freeze:** moved to 2026-09-28, to 2026-10-03 by EXP-0056 (the take profit
>   rests at the broker with the stop as one OCO order), then to 2026-10-04 by
>   EXP-0057 (the take profit is the bounce price).
> - **Fingerprint:** now `448170c3364935560663048c59647dfb5b204c6e6c724ce603f0d61c476e0f29`
>   (EXP-0057; `ab33087c…758` under EXP-0056, `da857ab7…a8c` under EXP-0055)
>   (was `da22011e…c237b`).
> - **First clean session:** still 2026-11-02 under EXP-0057 (2026-10-27 under EXP-0055; was 2026-10-12).
>
> Where this note says otherwise below, [the change record](../../docs/2026-09-28-adaptive-exits.md)
> and EXP-0055, EXP-0056 and EXP-0057 in `docs/experiments.jsonl` govern;
> the take-profit change is recorded in [its implementation note](../../docs/2026-10-04-bounce-take-profit-live.md).

*Snapshot: built 2026-09-23 against repository HEAD `0d9ce4b`.*

**Governing text:**
[docs/phase4-clean-observation-protocol.md](../../docs/phase4-clean-observation-protocol.md),
building on
[docs/phase3-forward-evaluation-protocol.md](../../docs/phase3-forward-evaluation-protocol.md).
Clean OOS is the only uncontaminated evidence this project can obtain about the
frozen strategy: every historical dataset was used to build it.

## When recording begins

“Derived from the real trading calendar at run time, never hard-coded.” —
[Phase 4 protocol](../../docs/phase4-clean-observation-protocol.md) §1

| element | value | how it is determined |
|---|---|---|
| research freeze | **2026-09-11** | “2026-09-11 — the registry's last config-changing entry (EXP-0017)” — [Phase 4 protocol](../../docs/phase4-clean-observation-protocol.md); computed by [`purge.py::def freeze_date`](../../src/event_aware_trader/purge.py) |
| embargo | **20 sessions** | the strategy's holding cap, `max_holding_bars` — [`purge.py::def embargo_sessions`](../../src/event_aware_trader/purge.py) |
| first clean session | **2026-10-12, projected** | “2026-10-12, projected” — [Phase 4 protocol](../../docs/phase4-clean-observation-protocol.md); resolved at run time by [`forward.py::def first_clean_session`](../../src/event_aware_trader/forward.py) |

The Phase 3 protocol's "approximately 2026-10-09" is corrected by the Phase 4
protocol — see [[Conflicts and Ambiguities]].

## How long it runs

There is **no end date**. The protocol defines checkpoints at 1, 20, 60 and 120
clean sessions; the first with any performance report is **C, at 60
sessions**; B, at 20, is integrity only. “A checkpoint below its threshold is
not produced” —
[Phase 4 protocol](../../docs/phase4-clean-observation-protocol.md) §6.

## The rules that make it clean

- **Nothing is backfilled.** “Sessions before that date are refused by the
  recorder, not filtered later.” — [Phase 4 protocol](../../docs/phase4-clean-observation-protocol.md)
- **Nothing changes during it** — parameters, thresholds, limits, universe,
  indicators, the haircut, benchmark methodology, evaluation dates or embargo
  length (Phase 4 §5). “No stopping because results are unfavourable and no
  restarting because they are favourable.” —
  [Phase 4 protocol](../../docs/phase4-clean-observation-protocol.md)
- **Results do not license optimisation.** “A poor clean result is evidence. A
  good clean result is not permission to optimise.” —
  [Phase 4 protocol](../../docs/phase4-clean-observation-protocol.md)
- **A changed configuration is refused, not filed.** Every session must carry
  the [[Frozen Fingerprint]] (gate G23).
- **Forward data never reaches research code.** “Clean forward observations
  must never reach research code.” —
  [research.py](../../src/event_aware_trader/research.py), enforced by
  [`forward.py::def reject_forward_data`](../../src/event_aware_trader/forward.py).
- **Gates G19–G23** — fingerprint, timestamp, append-only and isolation;
  reconciliation; no look-ahead; no stopping on performance; frozen strategy
  and benchmark unchanged. “The gates are not modified to make a failure
  disappear.” — [Phase 4 protocol](../../docs/phase4-clean-observation-protocol.md)

## What is recorded

One append-only, hash-chained row per session in `data/forward-evaluation.jsonl`
([`forward.py::FORWARD_LOG`](../../src/event_aware_trader/forward.py)),
written by `scripts/record_clean_session.py`. The headline candidate metric is
the equity sleeve's return — [[REM-0005]]. The benchmark is SPY total return —
[[Benchmark]], [[REM-0003]].

## State at snapshot

| item | value | how it was read |
|---|---|---|
| clean sessions recorded | **0** | `forward.load_sessions()` at build time |
| clean record chain | intact | `forward.verify_chain()` at build time |
| embargo progress | 8 of 20 sessions elapsed | the recorder's own output on 2026-09-23 at 20:15 UTC, which ended `REFUSED: embargo has not expired; 8 of 20 sessions elapsed.` (`data/clean-recorder.log` — not tracked by git, so not linked) |
| recorder scheduled-task principal | observed **S4U** on 2026-09-23 | read-only `Get-ScheduledTask` at build time. The last committed audit still records NOT READY on this item — see [[Conflicts and Ambiguities]] |

**Before relying on any of this, re-read it at the source.** The state changes
every session.

## Isolation hazards found 2026-09-23 — none has contaminated anything

No Clean OOS session has occurred, so nothing can yet have consumed one, and
the decade research dataset ends 2026-09-04. Three paths could nonetheless let
the holdout be read outside the protocol once it opens:

1. **A second, ungoverned forward read.** `scripts/benchmark.py` compares the
   paper account with SPY from `research.FORWARD_START` =
   2026-09-11, from the audit log, outside the recorder and its checkpoints.
   Its docstring then called the result NOT A FINDING until the record was long
   enough — wording replaced on 2026-09-24. Run after 2026-10-12, it is an
   early look the checkpoints exist to prevent. *(Guarded on 2026-09-24 —
   see below.)*
2. **The learning loop keeps training on live outcomes.** It retrained on
   2026-09-14, 09-15, 09-21 and 09-22. The model is observe-only and not
   consulted, so it cannot affect a decision — but any model trained after
   2026-10-12 has seen holdout outcomes and must never be treated as a
   pre-holdout model.
3. **The risk-free convention for holdout reports is unsettled.** *(Wrong —
   corrected below: the Phase 3 protocol fixed it on 2026-09-15.)* The
   fingerprint declares `risk_free 0.0230`; no code path consumes it; research
   Sharpe uses zero; the checkpoint script computes no Sharpe. It must be fixed
   before checkpoint C.

Source: [research reproducibility audit](../../docs/2026-09-23-research-reproducibility-audit.md).

### Update 2026-09-24 — sharpened, still none realised

From the [preservation record](../../docs/2026-09-24-dataset-preservation-and-research-gate.md)
§3–§5 and §8:

- **The retrain list above is incomplete.** The model file shows a further
  retrain at 2026-09-23 19:45:53 UTC, through a path the audit log does not
  record. Retrains run in-cycle, at session close and weekly.
- **The one barrier keeping the learned model out of trading,
  `LEARNED_RANKING_ENABLED = False`, is not covered by the frozen
  fingerprint.** Flipping it would not make the recorder refuse a session.
  It must stay `False` for the whole evaluation, and every checkpoint must
  verify it. Any model trained on examples dated on or after the first clean
  session is holdout-exposed.
- **`benchmark.py`** counts its 60-session "finding" threshold from 2026-09-11,
  so it would present a holdout read as judgeable after about 40 clean
  sessions. **Do not run it on or after 2026-10-12** until its forward window
  is capped at the last embargoed session. That guard is proposed, not
  implemented.
- **The risk-free decision must be recorded before 2026-10-12.** The declared
  `risk_free 0.0230` sits inside the frozen fingerprint, and Phase 4 §5
  forbids changing benchmark methodology during the phase.
- **The naming contradiction** (CONF-10) is resolved in the dataset
  documentation by three evidence classes — [[Datasets]].

**Clean OOS is not declared ready.** Preserving the dataset does not change
that.

### Update 2026-09-24, later — corrections, and one guard implemented

From the [loader and Clean OOS integrity audit](../../docs/2026-09-24-research-loader-and-clean-oos-integrity-audit.md)
§7–§10. This section supersedes the risk-free, `benchmark.py` and retrain
bullets above; they are kept as the record of what was believed.

- **The risk-free rate is fixed, not open — confirmed.** The Phase 3
  protocol's frozen configuration reads: “strategy dividends as cash, never
  reinvested; rf = 2.30%; 365.25-day annualisation.” —
  [Phase 3 protocol](../../docs/phase3-forward-evaluation-protocol.md) §1.
  Phase 2 defines it as “2.30% (measured mean 3-month bill over the window),
  never 0” —
  [Phase 2 acceptance report](../../docs/2026-09-16-phase2-acceptance-report.md);
  Sharpe and Sortino are daily, ×252 and ×√252, excess over the bill, the same
  `metrics()` for both legs. The fingerprint's `risk_free 0.0230` is that
  declaration. **What is missing is the implementation:** no committed code
  computes these for Clean OOS, and the Phase 2 `metrics()` was never
  committed. It must be built to that specification before checkpoint C.
- **`benchmark.py` is guarded — confirmed.** Its forward section now takes its
  window and count only from the Phase 4 clean record, after
  `verify_chain()`. It reports nothing below 60 clean sessions and refuses a
  broken chain; the embargo is never counted —
  [`benchmark.py::def clean_window`](../../scripts/benchmark.py). This matters
  because the live task's `session-run.ps1` runs it at **every session close**
  and writes the output to `data\BENCHMARK.txt`. The comparison method, the
  in-sample section and `src/` are unchanged. At 60 clean sessions it prints
  `src`'s `judgeable` label; Phase 3 §8 still says outperformance does not
  count as evidence “at any sample this phase can produce” —
  [Phase 3 protocol](../../docs/phase3-forward-evaluation-protocol.md).
- **Retrains: the 2026-09-23 19:45:53 UTC retrain is not unrecorded — it is
  the latest of 15 session-close retrains** (`session-run.ps1` → `cli
  retrain`, 2026-09-03 to 2026-09-23). They are logged only to
  `data/session.log`, not to the audit log. **The model-lineage ledger has no
  row for any live retrain since 2026-09-16** — a confirmed gap, not filled,
  because writing its fields would be inference.
- **There are two learned models, and two unfingerprinted switches.** The
  live ranking model (`LEARNED_RANKING_ENABLED = False`) cannot promote itself:
  deployment also needs a promotion record naming it, and none exists. The
  **trade veto model** (`data/trade-model.json`, retrained every Friday) is
  gated by `LEARNED_VETO_ENABLED = False`
  ([`trade_learning.py::LEARNED_VETO_ENABLED = False`](../../src/event_aware_trader/trade_learning.py)),
  but its trainer **sets `USABLE_AS_VETO` itself**, so only that flag keeps it
  out of trading. Both are UNPROVEN and unusable today.
- **The pre-Clean-OOS learned state is recorded** —
  [docs/model-state/pre-clean-oos-2026-09-24.json](../../docs/model-state/pre-clean-oos-2026-09-24.json):
  hashes, row counts and information cutoffs of both models and their data.
  Live training rows are keyed by decision time (`at`), with the latest
  ≤ 2026-09-21T19:30Z; trade examples by `as_of`, with the latest ≤ 2026-09-15.
- **The learning loop is not isolated from holdout outcomes, by design.** Both
  protocols count “every exit produced a training example” as a correctness
  claim — [Phase 4 protocol](../../docs/phase4-clean-observation-protocol.md)
  §9. Isolation is therefore on **deployment and evaluation**:
  - both flags stay `False`, and every checkpoint verifies them;
  - no model trained on rows dated on or after the first clean session is
    evaluated on Clean OOS, or treated as pre-holdout.

- **After the snapshot, the gap recurred — confirmed.** The scheduled session
  close retrained the live ranking model again at 2026-09-24T19:45:53Z. The
  file's hash changed; it is still UNPROVEN, on the same 3,063 examples, with
  `live-training.jsonl` unchanged. Again it is in neither lineage nor the
  audit log. The snapshot keeps the state before it. The same session close
  ran the guarded `benchmark.py`, and its forward section reported nothing
  (0 clean sessions) —
  [migration record](../../docs/2026-09-24-governed-research-dataset-migration.md)
  §12–§13.

**Clean OOS is still untouched: 0 sessions, chain intact.** It is still not
declared ready.
