# The learning loop: fixed, bootstrapped, and worth nothing so far

**12 September 2026.** The account owner asked to make sure the bot learns
from every trade it makes and keeps getting more profitable. Three separate
faults meant it had never learned from a single one. All three are fixed, the
loop is now seeded and running daily — and what it has learned so far, when
acted on, **loses money**.

Both halves of that are the finding.

---

## Part 1: the loop was dead three ways

`retrain` had run daily since 09-03 and reported the same thing every time:
`{"have": 0, "status": "not_enough_examples"}`.

**1. No exits.** `append_example` is called from the exit path, so a bot that
cannot close a position cannot learn from one. The sell path was broken from
09-04 to 09-11 and not one trade closed. Fixed, and verified against the live
API on 09-12 using crypto, since the equity market is shut at weekends.

**2. A deadlock.**

```python
snapshot = build_snapshot(bars_by_symbol) if estimator is not None else None
```

The snapshot was built only once a trained model existed. It supplies **nine
of the sixteen** features the model trains on, and those nine are the entire
reason the cross-sectional model scores above chance. Without it they record
at their neutral defaults — which is exactly what every open position was
carrying when this was found:

| | value | meaning |
|---|---|---|
| `rank_mom21/63/126`, `rank_pos52`, `rank_vol` | 0.5 | "no information" |
| `breadth`, `mkt_ret21`, `mkt_vol`, `rel_to_mkt` | 0.0 | absent |

So a completed trade would have carried nine constants into the training file,
the model could never learn the features that are its advantage, it could
never become usable, and `estimator` stayed `None` for ever. **The condition
that skipped the work required the outcome the work produces.**

**3. The wrong timeframe** — the same defect that made overnight stops 9.4×
too tight, in a different module. `build_snapshot` and `live_features` count
in **bars**, and the loop handed them the cycle's 15-minute candles:

| feature | what it measured | what the name claims |
|---|---|---|
| `mom21` | 5.2 hours | 21 days |
| `mom63` | 15.8 hours | 63 days |
| `mom126` | 31.5 hours (~2.4 sessions) | 126 days |

Every time-based feature wrong by roughly the 26 candles in a session, feeding
a model fitted on daily bars. All four call sites now take daily bars.
Verified on the real universe: COST's ranks are now 0.3283 / 0.1717 / 0.1413 /
0.2804 / 0.1891 instead of five 0.5 placeholders.

## Part 2: bootstrapped, because 7.5 years is not a plan

`train_live_model` needs 500 examples; the rule closes about 67 trades a year.
`cli.py retrain` has always accepted `--seed data/big-dataset.jsonl` and the
file had never existed.

`scripts/build_training_seed.py` replays the shipped rule over thirty years and
records, for every trade it would have taken, the features as they stood at
entry paired with what the trade actually returned — using **the same
`live_features`, the same `build_snapshot`, the same daily bars** as the live
path, because a seed built any other way trains a model on one thing and
scores it on another. One snapshot per entry date, sliced to that date.

```
replayed 1526 trades -> 1526 rows, 0 skipped, 29% base rate,
                        1,117 distinct entry dates
retrain: examples 1526, holdout_auc 0.5501, model_status USABLE
```

The loop is now live: `retrain` runs daily and folds each newly closed trade
into that base, `learn` runs weekly.

## Part 3: and it is worth nothing — measured, not assumed

An AUC is not a profit. To find out whether the model helps, it first had to
be **possible** to find out: the simulator's `veto` hook sat in the trend
branch and was unreachable under mean reversion, the rule the bot trades. So
`model_veto` was wired into that branch, and the question became answerable.

Strictly walk-forward — fit on trades before 2015, veto from 2015 on,
thresholds taken from the model's own score distribution rather than guessed:

| | CAGR | worst DD | trades | vetoed | vs no veto |
|---|---|---|---|---|---|
| **no veto (shipped)** | **9.12%** | −13.7% | 824 | 0% | |
| veto bottom 10% (<0.0505) | 8.67% | −13.4% | 814 | 9% | −0.45 |
| veto bottom 20% (<0.0821) | 7.57% | −12.7% | 792 | 19% | −1.55 |
| veto bottom 30% (<0.1156) | 7.26% | −13.9% | 747 | 31% | −1.86 |
| veto bottom 40% (<0.1497) | 6.60% | −14.5% | 720 | 41% | −2.52 |

**Monotone.** Every additional trade the model removes costs money, and the
drawdown does not reliably improve either. The trades it scores lowest are not
the losers.

### The AUC was the trap

| fit | holdout period | AUC | status |
|---|---|---|---|
| full seed, 1,526 rows | ~2022-2026 | **0.5501** | USABLE |
| pre-2015 only, 705 rows | ~2013-2015 | **0.5056** | UNPROVEN |

Same model, same features, different holdout — on a metric whose usability bar
sits 0.03 above chance. "USABLE" is partly an artefact of which period was
held out. Running only the first command would have produced the sentence "the
AI works"; it does not.

This is recorded in the comment beside `live_model_floor`, because that is the
one dial that would let the model remove trades, and a future reader looking
at `status: USABLE` has every reason to raise it. Any raise needs a fresh
walk-forward showing a **positive** result — not a good AUC.

## Where it leaves the AI

| question | answer |
|---|---|
| Can it learn from every trade? | **Yes** — fixed, seeded, running daily |
| Is the learning continuous? | **Yes** — `retrain` daily, `learn` weekly, no prompting |
| Does what it learns make money? | **No** — costs 0.45 to 2.52 CAGR points |
| Should it be allowed to act? | **No**, and the guard is now written down |

A dead loop can never help; a live one might. That is the whole of what was
bought today. The 18,574-example trade model already sitting at AUC 0.4867 —
below chance — is the honest prior for how this usually goes.

The one change that made money this week was not learned. It was an hour on a
clock.
