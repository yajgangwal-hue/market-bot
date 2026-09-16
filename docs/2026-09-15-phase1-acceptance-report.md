# Phase 1 acceptance report

*2026-09-16. Commits `1b7603d` → `68a1eba`. Both hard gates pass. The
headline fell from 5.75% to 3.18%.*

---

## 1. EVERY CHANGE MADE

| # | change | classification |
|---|---|---|
| **P0** | golden master: a committed trade-by-trade fingerprint of simulator behaviour, captured before anything else | measurement |
| **P1** | contamination gate: scoring a spent dataset now requires a declared `purpose` and is logged | process |
| **P2** | simulator honours `max_volume_participation`, via the **same** `cap_by_participation` live uses | **correctness bug** |
| **P3** | `rule_exit_timing_haircut` (0.652%) charged on `reverted` and `time_exit` | **correctness (reporting)** |
| **P5** | baseline re-measured once, under the gate | measurement |
| fix | dataset-use records moved out of the experiment registry into their own file | defect introduced by P1, caught by an existing test |

Not done, deliberately: P4 (scope statement — documentation, no code), P6
(benchmark basis), P7/P8 (purge/embargo). Those remain open.

## 2. FILES CHANGED

**Production path — UNCHANGED, verified mechanically:**
`autotrade.py`, `broker.py`, `crypto_sleeve.py`, `mean_reversion.py`,
`risk.py`, `session-run.ps1`, `session-run-crypto.ps1`,
`crypto-loop-worker.ps1` — all zero-diff across the whole of Phase 1.

**Changed:**
- `src/event_aware_trader/portfolio.py` — participation cap; exit haircut;
  import of `cap_by_participation`
- `src/event_aware_trader/research.py` — `PURPOSES`,
  `check_dataset_gate`, `looks_like_research_data`,
  `ContaminatedDataError`, `_record_gate_use`, `DATASET_USES`;
  `PRODUCTION_CANDIDATE` gains `rule_exit_timing_haircut: 0.00652`

**Added:**
- `tests/golden_fixture.py`, `tests/fixtures/golden_baseline.json`
- `tests/test_golden_master.py`, `tests/test_contamination_gate.py`,
  `tests/test_participation_cap.py`, `tests/test_exit_timing_haircut.py`
- `docs/dataset-uses.jsonl`

## 3. TESTS ADDED

| file | tests | what they prove |
|---|---|---|
| `test_golden_master.py` | 5 | the full trade list is pinned; the master **can fail** (0.01 on the stop multiple moves it); the fixture actually exercises all three exit reasons |
| `test_contamination_gate.py` | 17 | research-scale data without a declaration raises; each purpose is honoured and logged; `forward` accepts only its own purpose; **no `acceptance_test` purpose exists**; the gate is actually *called*; the two record types stay in separate files |
| `test_participation_cap.py` | 7 | the cap binds on a large account; it is **inert at $100k** (pinned); disabling restores size; both paths use the same helper; **future volume cannot change position size** |
| `test_exit_timing_haircut.py` | 9 | inert at default; changes **no decision**; lowers rule exits by exactly the haircut; **stops and take-profits untouched**; the candidate uses the worst of three measured values |

## 4. TEST RESULTS

**813 tests, all green.** Was 795 at Phase 1 start.

Three failures occurred during development, each a real defect:
1. Contamination-gate tests took **126s** because every assertion ran a full
   simulation to reach the check → gate extracted into its own function →
   **1.0s**.
2. Participation-cap tests used thin-volume fixtures that produce **zero
   trades** (the rule's own $50M ADV floor rejects them), so they passed
   while proving nothing → rebuilt at the scale where the cap binds.
3. The gate wrote `dataset_use` rows into `docs/experiments.jsonl`, breaking
   the well-formedness test on the **first** sanctioned run → separate file.

## 5. BEFORE / AFTER HEADLINE

Thirty years, 229 symbols, parked, every live constraint:

| | before | after | change |
|---|---|---|---|
| **headline CAGR (parked)** | **5.75%** | **3.18%** | **−2.57 pts** |
| strategy alone | 5.17% | 2.19% | −2.98 pts |
| Sharpe (rf 2.30%) | 0.53 | 0.17 | −0.36 |
| Sortino | 0.75 | 0.23 | −0.52 |
| Calmar | 0.51 | 0.29 | −0.22 |
| max drawdown | −11.2% | −11.0% | +0.2 |
| years positive | 83.3% | 76.7% | −6.6 pp |
| trades | 1,522 | 1,501 | −21 |

## 6. EFFECT OF THE 0.652% HAIRCUT

**It is the entire move.** P2 contributed exactly zero.

The magnitude was far larger than the −0.7 to −1.3 points I projected, so it
was checked before being believed:

- 980 rule exits over 30.7 years = **31.9 per year**
- at a ~15% position, 0.652% costs **0.0978% of equity** per exit
- 31.9 × 0.0978% = **3.12 points predicted** vs **2.98 observed**

It also reconciles with EXP-0048, where close-to-high was worth +1.33 points
as an explicit **lower bound** (terminal cash, no compounding). Compounding
through thirty years roughly doubles it. **Not a bug.**

**What this means, stated plainly:** the exit-timing gap is worth about as
much as the entire strategy edge. This is not a new cost — the bot has
always sold at the trigger. The simulator credited it a close it never
received, and **every figure published before today was overstated by
roughly 2.6 points.**

## 7. `cap_by_participation` IS SHARED — CONFIRMED

One implementation, `risk.py:365`. Called by `autotrade.py:1849` (live) and
now by `portfolio.run_portfolio` (simulator). A test asserts both call sites
reference it by name, so a future divergence must be deliberate.

**But its measured effect is zero, and that is the honest finding.** The
rule requires $50,000,000 ADV; 2% of that is $1,000,000; a 20% position on
$100k is $20,000. The cap cannot bind until equity exceeds roughly ADV/10 —
about **$5,000,000**. A test pins this inertness so that if it ever fails,
the account has outgrown the assumption and the baseline needs re-measuring.

## 8. NO PROHIBITED OPTIMISATION

- No parameter tuned. `MeanReversionConfig` and `RiskPolicy` diffs are empty.
- No configuration selected after seeing results. The haircut value was
  fixed at the worst of three **pre-existing** measurements before the
  baseline was run.
- No trades or periods removed. Trade count moved 1,522 → 1,501 purely
  through the equity path, and no decision changed (symbol, entry date, exit
  date, exit reason identical across the golden fixture's 23).
- No assumption changed to reduce performance for its own sake — both
  changes correct a **documented** sim/live divergence.
- No look-ahead introduced. Two explicit tests: future volume cannot change
  position size; the haircut adds no data dependency.
- Nothing optimised against the gates. G13 required the number to fall; it
  fell because the correction is real, and the arithmetic was verified
  independently.

## 9. G13 — PASS

Headline **3.18% < 5.75%**. Required direction, and the mechanism was
independently confirmed before acceptance.

## 10. G14 — PASS

Zero diff across all eight frozen files for the entire phase:
`autotrade.py`, `broker.py`, `crypto_sleeve.py`, `mean_reversion.py`,
`risk.py`, `session-run.ps1`, `session-run-crypto.ps1`,
`crypto-loop-worker.ps1`. No scheduled task, broker setting or live
parameter was touched. The bot is trading today exactly as it traded
yesterday.

## 11. REMAINING UNCERTAINTY — WHY 3.18% IS NOT PROOF OF ANYTHING

1. **The haircut is a bound, not a measurement.** 0.652% is the worst of
   three cases. The live trigger-time distribution is **UNVERIFIED** — three
   rule exits have ever been logged, all pre-instrumentation. The true drag
   lies somewhere between the 0.120% case and this. **3.18% is therefore a
   conservative floor, not a point estimate.**
2. **Still in-sample.** Every parameter was chosen on this data. 186
   configurations across two windows.
3. **Survivorship remains.** The honest range is the ETF-control floor
   (2.24% pre-remediation, **not yet re-measured** under P2/P3) to the
   survivor ceiling.
4. **Dividends still absent** from the simulator — conservative, but the bot
   and SPY are not yet on the same basis (P6 outstanding).
5. **The backtest still describes an equity-only book.** No sleeve, no 5%
   reserve (P4 outstanding).
6. **No purge or embargo yet** (P7/P8 outstanding).
7. **The forward record is 3 sessions** against a 60-session floor, and 60
   sessions cannot resolve profitability regardless.

**I am not claiming this strategy is profitable, and I am not claiming it
beats the S&P 500.** On these corrected figures it trails SPY's price return
(8.55%) by more than five points a year, and its risk-adjusted advantage has
narrowed substantially — Sharpe 0.17 against SPY's 0.40 on price return.
The drawdown advantage survives (−11.0% vs −56.5%); almost nothing else does.

Phase 1 did not make the system better. It made the reported result harder
to overstate — which was the objective, and the 2.57-point drop is the
measure of how overstated it was.
