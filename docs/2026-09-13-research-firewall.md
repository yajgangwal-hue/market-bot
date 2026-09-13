# The research firewall

*2026-09-13. Commits 17a9c80, d8f0b5e, c8eff2e.*

The instruction was to inspect the repository, find the single highest-impact
weakness that could be improved without compromising the integrity of the
evaluation framework, and work on that first.

The weakness is the evaluation framework.

## The diagnosis

Between 09-08 and 09-13 this project evaluated **36 experiments, 134
configurations** — 117 of them on the equity windows — and took every
decision on the same two datasets. The decade (2016–2026) was the
development set. The thirty-year window (1996–2026) was called "the test that
decides", and about twenty accept/reject decisions were taken on it. Both
halves of both windows were seen for every one.

By this project's own rule — once a holdout is used to make a decision it is
contaminated and the boundary moves forward — every historical dataset here
is spent for the current production candidate. Nothing further can be judged
on them without saying so. And there was nothing to say it with:

- **No registry.** Which ideas had been tried, how many times, and with what
  result lived in twenty markdown files and a commit log. Nobody could count
  the related attempts before an experiment, so nobody did.
- **No multiple-comparison correction.** `deflated_sharpe_ratio` existed in
  `stats.py`; nothing called it. The best of forty tries is expected to look
  good by luck, and no reported number had paid for the search.
- **The "honest baseline" was not the bot.** It omitted whole shares, the
  three-entries-a-day cap, the mark-to-market guard, and the cash the bot
  parks in SGOV — every comparison was against something the bot does not run.
- **One number per window.** A CAGR and a drawdown. Not a worst year, not a
  share of years positive, not what 2008 or 2022 did to the account.

Every other candidate weakness — the stop's give-back, the sleeve's size, the
model's veto — can only be *measured* through this framework. Fixing any of
them first would have produced another number nobody could trust.

## What was built

`src/event_aware_trader/research.py`. Nothing in it is a strategy; it only
decides how strategies are judged.

**`PRODUCTION_CANDIDATE`** — the simulator configuration that mirrors live:
`entry_fill="signal_close"` (the 15:45 window), `realistic_stop_fills` (a
gapped stop fills at the open), `max_entries_per_day=3`,
`mark_to_market_guard`, whole shares. `production_report(series,
**overrides)` runs it; an experiment is exactly the override dict, which is
what goes in the registry. **`with_parked_cash`** applies the one live
behaviour the simulator has no parameter for — idle cash above the $2,000
floor, less the 5% crypto reserve, earning the 3-month bill rate that
prevailed each day (`data/tbill.csv`, 1970 on), 2bps per move. The candidate
is not mirrored until it has been applied.

**`DATASETS` / `FORWARD_START`** — the contamination ledger. Decade,
thirty-year, ETF control and crypto: contaminated. The only clean data for
the current candidate is the paper account from **2026-09-11**.

**`walk_forward_years`** — one result per calendar year from one run of a
fixed rule, and `summarize_periods` gives the distribution: median, quartiles,
worst, share positive, worst period. The per-fold *refit* hook is named and
deliberately refused with `NotImplementedError` — slicing a single run would
leak later folds' fits into earlier ones, and nobody should be able to fake a
walk-forward on a tuned component by accident.

**`record_experiment`** — the append-only registry, `docs/experiments.jsonl`.
Every row carries the fields the standard asks for: id, hypothesis, config,
features, parameters, data periods, validation and holdout results, decision,
evidence class, reason, contamination, and `related_before` — computed from
the registry, so nobody has to remember. Two fields the standard did not ask
for but the correction needs: `configurations` (a sweep of five stops is one
hypothesis and five configurations) and `trial_sharpes`, one per
configuration where it was written down.

**`deflated_sharpe`** — the multiple-comparison correction, and it returns a
`Deflation` that names its inputs: how many configurations it paid for and
whether the spread across them was *observed* from the registry or the
*unit default*. A number never travels without its assumption.

`scripts/backfill_experiments.py` wrote the week into the registry — 36
experiments, failed ones with the same care as the one that shipped. A test
asserts the registry is well-formed, that no row claims forward data, and
that a spread of trial Sharpes exists, so a registry that had silently fallen
back to the unit default would fail the suite.

## The candidate as a distribution

Thirty years, 229 names, every live constraint. **This is in-sample for the
parameters** — they were chosen on this data — and the ledger says so. What
it is out-of-sample for is each year's trades, which used only bars that had
printed.

Strategy alone, cash at zero:

| | CAGR | maxDD | Sharpe | ruin (25%) | trades |
|---|---|---|---|---|---|
| production candidate | 5.18% | −12.9% | 0.66 | 18.0% | 1,501 |

With idle cash parked in SGOV, as the account actually holds it (median idle
cash: 74% of equity):

| | CAGR | maxDD | Sharpe* | ruin (25%) | end value |
|---|---|---|---|---|---|
| strategy alone | 5.17% | −12.9% | 0.66 | 18.0% | $469,266 |
| **+ parked cash (live)** | **5.75%** | **−11.2%** | 0.87 | **2.2%** | $554,833 |

*The parked Sharpe includes the risk-free return and is not the strategy's
Sharpe; the deflation below uses the un-parked 0.66.*

Year by year, parked:

| year | return | maxDD | | year | return | maxDD | | year | return | maxDD |
|---|---|---|---|---|---|---|---|---|---|---|
| 1996 | 6.8% | −1.1% | | 2006 | 6.3% | −7.5% | | 2016 | 4.5% | −6.2% |
| 1997 | 7.1% | −3.4% | | 2007 | 6.7% | −4.2% | | 2017 | 9.1% | −3.2% |
| 1998 | 3.6% | −3.9% | | **2008** | **−5.1%** | −6.1% | | 2018 | 7.3% | −6.9% |
| 1999 | 4.8% | −1.4% | | 2009 | 7.8% | −1.0% | | 2019 | 10.5% | −7.0% |
| 2000 | 3.8% | −2.2% | | 2010 | −1.7% | −7.7% | | 2020 | 4.0% | −9.9% |
| 2001 | 4.4% | −1.4% | | 2011 | −1.9% | −5.6% | | 2021 | 24.4% | −4.6% |
| 2002 | −0.3% | −3.0% | | 2012 | 7.3% | −5.9% | | **2022** | **−8.0%** | **−10.9%** |
| 2003 | 6.3% | −2.1% | | 2013 | 14.5% | −3.8% | | 2023 | 10.7% | −5.8% |
| 2004 | 7.8% | −4.2% | | 2014 | 6.0% | −4.8% | | 2024 | 6.0% | −5.3% |
| 2005 | 4.5% | −3.3% | | 2015 | 0.2% | −6.2% | | 2025 | 10.9% | −10.8% |
| | | | | | | | | 2026* | 12.9% | −5.2% |

*partial, to September.*

| distribution over 30 full years | parked | strategy alone |
|---|---|---|
| median year | 6.1% | 4.7% |
| quartiles | 3.8% … 7.8% | 0.5% … 9.7% |
| worst year | −8.0% (2022) | −10.5% (2022) |
| 2008 | −5.1% | −8.1% |
| best year | 24.4% (2021) | 29.0% (2021) |
| years positive | 25 of 30 | 23 of 30 |
| median within-year drawdown | −4.7% | −5.9% |
| worst within-year drawdown | −10.9% | −12.9% |
| first half / second half | 4.12% / 6.79% a year | — |

Three things the one-number version hid:

- **Before 2003 the account is mostly a bill fund.** The rule fired 3–29
  times a year (the universe had few names with two hundred days of history
  yet); the 4–7% those years show is the T-bill rate. The strategy's own
  record is effectively 2003 on — 23 years, not 30.
- **The bad years are shallow.** Two years below −5% in thirty, neither past
  −8%, and the worst within-year drawdown is −10.9%. Ruin at a 25% drawdown
  falls from 18% to 2.2% once the idle three-quarters of the account earns
  interest, because the interest is what refills the drawdowns.
- **The second half is better than the first** — 6.8% against 4.1% — and
  most of the difference is the rule trading more (50–89 exits a year after
  2010 against 3–59 before). That is also the half every parameter was
  tuned on. It is the number most likely to shrink forward.

## The search it came from

Sharpe 0.66 on 7,719 daily returns. Probabilistic Sharpe against zero: 0.9999
— the edge is not noise. Against the search that produced it:

| trials paid for | spread of trial Sharpes | DSR |
|---|---|---|
| 117 configurations | 0.081 — observed, the 11-variant exit sweep | **0.993** |
| 117 | 0.15 — assumed | 0.932 |
| 117 | 0.20 — assumed | 0.783 |
| 117 | 0.25 — assumed | 0.530 |
| 117 | 1.00 — the unit default | 0.000 |

The verdict depends entirely on the spread, which is why it is now recorded.
The observed 0.081 comes from variants of *one* rule — trailing stops,
partials, regime exits — which inherit its edge and therefore cluster. The
week also tried genuinely different strategies (short books, overnight
gappers, meme allocations, SPY parking) whose Sharpes were far worse and were
never written down; had they been, the spread would be wider and the DSR
lower. So the honest reading has two halves:

- **Within the family, the parameters are not a lucky pick.** At any spread
  up to ~0.15 the candidate's Sharpe pays for the sweeps that produced it.
- **Whether the family itself is the lucky one of many cannot be settled on
  this data.** Only the forward record can, and it starts 2026-09-11.

## What changes from here

1. Every idea is a registry row *before* its result is known — hypothesis,
   config, data periods — and the row is completed with the result, the
   evidence class, and the reason. Failed ones included.
2. Every comparison starts from `production_report` and states its overrides.
   A comparison run without a live constraint is a comparison against
   something the bot does not do.
3. A result is a distribution across years, not a CAGR. The promotion gate
   reads the worst year and the share positive, not the mean.
4. Every sweep records its trial Sharpes. The deflation is only as honest as
   that column.
5. The historical windows are contaminated for the current candidate. They
   remain useful for *rejecting* ideas — a change that loses money on data it
   was tuned on will not win elsewhere — but they cannot *accept* one for this
   family any more. Acceptance needs the forward record.

## What is not claimed

- Not that the candidate has an out-of-sample record. It has thirty in-sample
  years, honestly sliced, and two forward sessions.
- Not that 117 is the true trial count. It is the count of what was written
  down; a week of ad-hoc runs surely tried more.
- Not that the ETF-only control (2.24%) has been superseded. The candidate's
  5.18% is on a survivor universe; the honest range is still the ETF floor to
  the survivor ceiling.

## Next

- Let the forward record accumulate. Every live exit already writes its
  captured/gave-back; the first forward evaluation is a distribution over
  sessions, not a P&L.
- When a tuned component is proposed (a model, a regime classifier), the
  per-fold refit harness gets built *then*, as one run per fold — not before,
  and not by slicing.
- Monday, market hours: equity spreads across the 230 names, and
  `verify_sell_path.py --live` on an equity.
