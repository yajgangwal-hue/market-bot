---
title: "Frozen Fingerprint"
authority: "FROZEN"
kind: "identity"
generated: false
sources:
  - "src/event_aware_trader/forward.py"
  - "docs/remediations.jsonl"
  - "docs/SPEC-0001-decision-boundary.md"
  - "docs/2026-09-22-pre-oos-integrity-audit.md"
  - "docs/phase4-clean-observation-protocol.md"
---

# Frozen Fingerprint

> [!note] FROZEN — the frozen strategy as implemented
> Read from the linked sources at build time. If this note and a source differ, **the source governs**.

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

```
448170c3364935560663048c59647dfb5b204c6e6c724ce603f0d61c476e0f29
```

*Until 2026-10-04: `ab33087cf80958d74e3b8d593e454f0dc5200bd98c6c25a32547e4be1d0a0758` (EXP-0056). Until 2026-10-03: `da857ab7b85e20f9e458b769f1d587f0b59eba5c8686e9a0b9c002480f542a8c` (EXP-0055). Until 2026-09-28: `da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b`.*

The value [`forward.py::def frozen_fingerprint`](../../src/event_aware_trader/forward.py)
returned at snapshot. It is the SHA-256 digest computed by
[`forward.py::def config_digest`](../../src/event_aware_trader/forward.py) over
the frozen configuration: the mean-reversion config, the risk policy, the cost
model, eight named live settings, the production candidate, the embargo and the
benchmark block. The eight live settings and every covered value are listed in
[[Frozen Parameters]].

## What it is for

- **Clean OOS refuses a foreign fingerprint.** Gate G23 fails on “the
  fingerprint moving from da22011e…” —
  [Phase 4 protocol](../../docs/phase4-clean-observation-protocol.md). A
  session produced under a changed configuration is refused, not filed — see
  [[Clean OOS]].
- **Research runners check it before computing.** For example
  `scripts/run_h0011.py` through `scripts/run_h0015.py` and
  `scripts/run_h0025.py` stop if the value differs.
- **Every remediation records it before and after.** All nine rows record the
  same value on both sides — [[Remediation Index]].

## What it cannot do

It cannot prove that an implementation conforms to [[SPEC-0001]]. Two
implementations can share a configuration and still make different decisions.
That limitation is item 6 of [[Accepted Non-Conformances]], and conformance is
audited separately (SPEC-0001 C-21, C-22).

## History

- [[REM-0001]] — the runner passed `--interval 15m` and the fingerprint hashed
  defaults.
- [[REM-0002]] — the fingerprint became an observation of the run.
- [[SPEC-0001]] C-28 — the specification leaves the fingerprint unaffected.

## How to check it

```bash
python -c "import sys; sys.path.insert(0, 'src'); from event_aware_trader.forward import frozen_fingerprint; print(frozen_fingerprint())"
```

It must print the value above. If it does not, the configuration has changed,
and nothing may be recorded to Clean OOS under it.
