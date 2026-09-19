# Risk-model, allocation-order and Form 4 audits

*2026-09-19. **FORENSIC_NON_PROMOTIONAL.** Nothing registered. No
production file modified. H-0010 closed without sealing.*

---

## A. H-0010 closure

**Closed without sealing, on the owner's decision. Recorded as
RESEARCH EVIDENCE — ALLOCATION INEFFICIENCY OBSERVED, BUT NO
DEFENSIBLE PROFITABILITY HYPOTHESIS JUSTIFYING H-0010.** The three ATR
floors were not run.

**What was learned.** Equal-risk sizing allocates inversely to ATR, so
the tightest-ATR quartile receives the largest positions — 17.27% of
equity each — and returns a median of **−0.289R**. The largest size
quintile is **26% of all notional deployed ($3,050,759)** and earns
**−$306, i.e. −$0.10 per $1,000**, against $5.92–$7.93 for every other
quintile. It is worse than the rest in **3 of 3** chronological thirds
on both the size and the ATR cut — the only structural effect to
survive a time split in this whole sequence.

**Why it does not justify an experiment.** Spearman(ATR, R) = **+0.0596**
against a 2-SE band of 0.076: the surface is an inverted U with Q1 as
an outlier, not a gradient. And the Q1 trades do not *lose* money —
they earn almost nothing while consuming the most capital. Freed
capital has nowhere to go, because the 12-position cap never binds,
52.1% of sessions produce no candidate and cash blocks only 3.2%. So an
ATR floor is **exposure reduction, not redistribution**, and its best
realistic outcome is a better Sharpe with a *worse* gap to SPY.
Optimising return-per-unit-exposure would not serve the primary
objective. Production sizing and `rsi_entry = 35.0` are unchanged.

---

## B. Risk-model audit

### The exact equation, traced

From `risk.position_size` and its single caller `portfolio.py:840`:

```
loss_per_share = (entry − stop) + round_trip_cost_per_share(entry, stop)
risk_limited   = equity × 0.005 / loss_per_share
cash_limited   = equity × 0.20  / entry
quantity       = floor(min(risk_limited, cash_limited))
quantity      ×= conviction(symbol, history)            # [0.5, 1.5]
quantity       = min(quantity, equity × 0.20 / entry)   # NOTIONAL re-clamp
quantity       = cap_by_participation(quantity, entry, adv, 0.02)
if quantity <= 0: candidate DROPPED
planned_risk   = quantity × loss_per_share
```

with `stop = entry − 2.5 × ATR(14)`.

### The ten questions

Measured from the simulator's **own** `planned_risk`, recovered exactly
as `net_pnl / r_multiple`, on all 698 trades.

**1. Is 0.5% the intended maximum, or the pre-conviction base?**
**The pre-conviction base.** The effective ceiling is 0.75%.

**2. Is conviction intentionally permitted to raise risk above 0.5%?**
**Yes, by construction** — the multiplier is applied *after* the budget
and the only post-conviction clamp is on notional. The code comment at
the clamp shows the author considered the interaction and chose to
bound notional rather than risk.

**3. Why is realised mean risk ≈0.68%?**
Because **conviction is saturated**: 523 of 698 trades sit at a mean
multiplier of 1.493, pinned to the 1.5 ceiling. Mean-reversion entries
are deep pullbacks by construction, so most clear the 8%-drawdown
threshold for the full multiplier. 0.5% × 1.369 = **0.684%**.

| realised planned risk | value |
|---|---|
| min | 0.0211% |
| p10 | 0.5522% |
| median | **0.7404%** |
| mean | **0.6844%** (1.369× declared) |
| p90 | 0.7490% |
| max | **0.7500%** |
| trades over the 0.75% effective ceiling | **0 (0.00%)** |
| trades over the 0.50% declared budget | **655 (93.84%)** |

**4. What does the final re-clamp constrain?** **Notional only** —
`equity × max_notional_fraction / entry`. It does not bound risk.

**5. Are transaction costs in `loss_per_share`?** **Yes** —
`round_trip_cost_per_share(entry, stop)` is added before sizing.

**6. Does rounding materially change realised risk?** `floor()` can
only reduce, so realised risk ≤ budget × conviction. It matters at the
bottom: min 0.0211% and p10 0.5522% against a 0.7404% median — a small
number of expensive names are heavily rounded down.

**7. Does the 20% notional cap bind?** **Yes** — the binding constraint
on 8.7% of trades; 35 trades sit at the cap. (Measured max reads
20.0120% because I computed notional at the cost-adjusted fill while
the clamp uses the raw close — a ~2 bps basis difference, not a
breach.)

**8. Does the participation cap bind?** **Never** — 0 of 698.

**9. Can any path exceed the intended ceiling?** **No.** Zero trades
exceed 0.75%, and the bound is algebraically guaranteed:
`floor(·) × lps ≤ equity × 0.005`, so `× conviction ≤ 0.0075 × equity`.

**10. Consistent with the production specification?** The *code* is
correct and the bound holds. The *name* is not: a field called
`risk_per_trade = 0.005` reads as a per-trade risk ceiling, and 93.84%
of trades exceed it.

### Verdict: not a defect — an under-documented contract

No numerical error, no breach, no leakage. **The contract, stated
precisely:**

> `risk_per_trade` is a **base** budget, not a ceiling. The effective
> per-trade risk ceiling is `risk_per_trade × CONVICTION_MAX` = 0.75%
> of equity at entry. Realised mean is ~0.684% because conviction
> saturates near its ceiling for ~75% of mean-reversion entries. The
> post-conviction clamp bounds **notional** at 20% of equity; there is
> no post-conviction clamp on **risk**.

**Recommended engineering item, isolated from any economic work:** add
a test pinning the 0.75% effective ceiling and a docstring stating the
base-not-ceiling contract. No behaviour change, no rerun of historical
results. I have not made that change.

---

## C. Allocation-order audit

### Where the rank is created, and where it is lost

`candidate_rank` is a `run_portfolio` parameter (`portfolio.py:190`).
It is **never created anywhere in production**: `PRODUCTION_CANDIDATE`
does not contain it, so `production_report` never passes one. With it
absent, `order = list(todays_bars.items())` (line 761), and
`todays_bars` is built by iterating `series` (line 314). Every research
loader builds `series` from a **sorted** symbol list.

So: **insertion order governs, and sorting makes it alphabetical.**

### Is it intentional, accidental, or a defect?

**None of those cleanly — it is a known, already-tested condition.**
The comment at `portfolio.py:748-759` states it outright: *"the capital
goes to whichever qualifying name is earliest in the ALPHABET… a
thousand allocation decisions a decade were being made by spelling"*,
and notes the live loop sorts by score instead, *"so the simulator and
the bot were choosing differently among the same candidates."*

And `scripts/backfill_experiments.py:83-85` records the economic sweep,
dated **2026-09-11**:

> ranking · `candidate_rank: [alphabetical, oversold, overnight,
> conviction]` · decade **and** thirty-year · *"0.58-pt spread, ordering
> flips between windows"* · **rejected**, evidence strength **none** ·
> *"noise; also found the simulator had been allocating alphabetically"*

**This corrects my framing last turn.** I presented alphabetical
allocation as a fresh discovery. It was fresh to me; it was found,
documented and economically swept eight days earlier, and four
orderings were indistinguishable. `candidate_rank` exists as the hook
precisely because that sweep was run and nothing beat anything.

### Can it alter portfolio composition? Yes — now proven

`tests/test_allocation_order.py`, 10 tests, all passing. Identical
bars, identical timestamps, identical risk, identical bucket, identical
signal output (guarded by an explicit test) — only the symbol string
differs:

- two identical candidates in one bucket → exactly one is taken;
- sorted insertion → the alphabetically first name wins;
- the raw mechanism is **dict insertion order** (unsorted, `ZZZZ` first
  wins; `AAAA` first wins) — sorting is what turns it into the alphabet;
- **renaming alone flips the selection**: `{AAAA, MMMM}` → AAAA,
  `{NNNN, MMMM}` → MMMM;
- a supplied `candidate_rank` overrides it correctly;
- production passes none — pinned by a test that will fail if that
  changes.

### Is it a correctness defect?

**For the simulator in isolation: no** — it is deterministic,
documented, and the economic sweep found no ordering superior.

**For simulator-versus-live fidelity: yes, a real and documented
divergence.** The live loop sorts by the gate's score; the simulator
sorts by the alphabet. On the 1,061 capacity-rejected candidates a
decade they can choose differently. That is a *fidelity* issue — the
backtest is not simulating the bot's allocation — and it is orthogonal
to whether either ordering is more profitable.

### What must be registered before testing a fix

Changing the ordering changes the strategy, so any economic test needs
its own registration. It would also have to clear a high bar, because
the direction has already been swept and rejected: a new registration
would need a mechanism that the 2026-09-11 sweep did **not** test, a
declared direction, and an explicit statement of why the earlier
0.58-point/window-flipping result does not already answer it. **I do
not think that bar is currently met.**

The defensible non-economic action is to align the simulator's ordering
with the live loop's *for fidelity*, which is a correctness change
requiring its own registration precisely because it moves historical
results. Not proposed here.

---

## D. Form 4 feasibility

### Step 1 — Access probe: **PASSES**

SEC's stated terms, read from `sec.gov/os/webmaster-faq`:

> *"We allow scripted access to sec.gov content"*, with a declared
> `User-Agent` of the form `Sample Company Name AdminContact@domain.com`
> and *"Our current maximum access rate is 10 requests per second."*
> **No API key or authentication.**

Two live requests from this environment to `data.sec.gov` **succeeded**
— no 403, no block. Access is real and permissible.

### Step 3 — Timestamp audit: **strong, with one gap**

`data.sec.gov/submissions/CIK{...}.json` exposes per filing:

| field | present | example |
|---|---|---|
| `acceptanceDateTime` | **yes, to the second, UTC** | `2026-09-17T22:30:24.000Z` |
| `filingDate` | yes, date only | `2026-09-17` |
| `form` | yes | `4` |
| `accessionNumber` | yes | — |
| **`reportDate`** (transaction date) | **frequently EMPTY** | blank in 8 of 12 sampled Form 4s |

**`acceptanceDateTime` is a genuine availability timestamp to the
second** — precisely the property the news archive lacked and was
marked UNVERIFIED for. This is the single strongest thing about the
source.

**But the transaction date is not in the index.** It lives inside the
Form 4 XML, so any point-in-time reconstruction must parse every
filing, not just read the index. That is a real acquisition cost, not a
blocker.

### Step 4 — Holding-period relevance: **a full session of lag, minimum**

From 12 sampled AAPL Form 4s, `acceptanceDateTime` clusters at
**20:30–22:40 Z = 16:30–18:40 ET** — nine of twelve are **after the
16:00 close**. Two are at 10:01 Z (06:01 ET, pre-market).

So the typical filing becomes public *after* the session ends, and the
earliest decision that can use it is the **next** session's 15:45 ET
entry window — roughly 21 hours later. Against a ~14-session holding
period that is survivable, unlike 13F's 45 days, but it is one full
session worse than the "2 business days" headline implies.

Where `reportDate` was populated, the transaction-to-filing lag ranged
from **same-day to 34 days** (2026-06-27 → filed 2026-07-31;
2026-03-28 → 2026-05-01). **Not every Form 4 meets the 2-business-day
deadline**, which matters for any rule keyed on transaction recency.

### Step 2 — Coverage and survivorship: **not audited, and the known weak point**

Not measured. The structural hazard is unchanged and I will not assert
figures I have not checked: CIK↔ticker mapping is published as a
*current* snapshot, so mapping a historical filing to the security that
existed at the time — across ticker changes, mergers and delistings —
is the part most likely to inject survivorship bias. Filings themselves
persist after delisting, which is genuinely better than the trader
feeds that do not exist at all.

### Steps 5 and 6 — Redundancy and integrity: **not run**

The redundancy test is the one that decides the branch, and it cannot
be run without bulk acquisition. Integrity questions (amendments,
duplicate filings, multiple transactions per filing, transaction codes,
derivative vs non-derivative, reconstructing direction and size) all
require the filing XML.

### The concrete blocker to bulk acquisition

SEC requires a declared `User-Agent` containing a **contact address**.
Bulk acquisition means thousands of requests (≈2,500 daily index files
for the decade, plus per-filing XML). **I will not put your personal
email into an outbound header to a third party without you asking me
to.** So before acquisition starts I need either a contact string you
are content to publish in request headers, or your instruction to use
the address on file.

That is a one-line decision, not a research obstacle — but it is a hard
gate and it is why Steps 2, 5 and 6 stop here.

---

## E. Next decision

### **BOTH NEED DESIGN WORK**

**Allocation order** — the mechanism is real and now proven by test, but
there is **no defensible economic hypothesis**. The direction was swept
on 2026-09-11 across the decade *and* the thirty-year window, produced a
0.58-point spread that flipped between windows, and was rejected with
evidence strength "none". Re-testing it would be rediscovering a known
failure, which the standing directive forbids. What remains is a
**simulator-versus-live fidelity** issue, which is a correctness matter
needing its own registration because it moves historical results — not
a profitability lever.

**Form 4** — the two things that killed the news branch are both absent
here: there **is** a true availability timestamp to the second, and the
filings **are** survivorship-complete. That makes it the most promising
information source identified so far. But the branch cannot be declared
justified until the redundancy test runs, and that needs bulk
acquisition, which needs the User-Agent decision and a per-filing XML
parse for the transaction date.

**Neither is registrable today, and I am not manufacturing one to keep
the count moving.**

**The bounded next step, if you want it:** resolve the User-Agent
contact string, then run Steps 2, 5 and 6 as a single feasibility piece
— coverage against the 230-name universe with point-in-time mapping,
then the redundancy test against existing RSI/momentum/ATR/volume
features. Each can close the branch on its own, and none needs a
registration. Only if Form 4 survives all three does a hypothesis get
designed.

---

## Governance

| check | result |
|---|---|
| frozen fingerprint | `da22011e…c237b` — **unchanged** |
| production source | **unchanged**; `src/` clean |
| `rsi_entry` / bucket cap / max positions | 35.0 / 1 / 12 — unchanged |
| `risk_per_trade` / notional cap | 0.005 / 0.20 — unchanged |
| learned ranker / veto | `False` / `False` |
| exit haircut / drawdown ceiling | 0.652% / 14.2806% — unchanged |
| clean OOS | **untouched** |
| registrations | 9, chain intact — **H-0010 NOT sealed** |
| promotion candidates | **none** |
| ledger | 35 experiments, 104 configurations |
| thirty-year reads | **13** |
| external requests made | 3 (SEC, public, permitted, read-only) |

## Artefacts

- `scripts/audit_sizing.py`, `docs/phase5/sizing-audit.json`
- `tests/test_allocation_order.py` (10 tests, documents current behaviour)
- H-0010 closure recorded in `docs/phase5-research.jsonl`
