# Phase 4 checkpoint reports

Checkpoint reports land in this directory as their thresholds are reached.
They are generated, not written by hand:

```
python scripts/phase4_checkpoint.py
```

| report | needs | scope |
|---|---|---|
| `checkpoint-a.md` | 1 clean session | confirm the embargo genuinely expired and the first observation is clean |
| `checkpoint-b.md` | 20 clean sessions | infrastructure and data integrity only |
| `checkpoint-c.md` | 60 clean sessions | correctness acceptance plus a descriptive performance report |
| `checkpoint-d.md` | 120 clean sessions | repeat the descriptive report and compare stability |

**A checkpoint below its threshold is refused.** The script will not render
an early report on a thin sample, because an early report is the mechanism
by which an experiment gets stopped on a convenient quarter.

## State as of 2026-09-16

| | |
|---|---|
| clean sessions recorded | **0** |
| eligible clean sessions so far | **0** |
| research freeze | 2026-09-11 |
| embargo | 20 sessions |
| elapsed since freeze | 2 (2026-09-14, 2026-09-15) |
| first clean session | **2026-10-12**, projected from the real calendar |
| fingerprint | `da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b` |

No checkpoint is due. The directory is empty of reports by design, not by
omission: there is nothing yet to report on, and generating a placeholder
would be the first fabricated observation in a record whose entire value is
that it contains none.

The recorder runs on its own schedule
(`EventAwareTraderCleanRecorder`, weekdays after the close) and refuses
every day until 2026-10-12, logging the refusal to
`data/clean-recorder.log`.
