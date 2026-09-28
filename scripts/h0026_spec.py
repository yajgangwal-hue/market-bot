"""H-0026 - the registration, in one place, for register_h0026.py and run_h0026.py.

Both scripts build the Hypothesis from this module, so the runner cannot drift
from what was sealed: prereg.verify() recomputes the seal from these fields
and refuses a mismatch. Owner approval to run: 2026-09-28 ("yes", in answer to
"Want me to run H-0026 on history now?"). Drafted and published as DRAFT
H-0026 in docs/2026-09-27-exit-placement-research.md; the changes made before
sealing are listed in `CHANGES_FROM_DRAFT`.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov.prereg import CONFIRMATORY, Hypothesis  # noqa: E402

HYPOTHESIS_ID = "H-0026"
DATASET_ID = "decade-2016-2026-split-adjusted-230"
DATASET_SHA256 = "935fed79de9803f1da2a380c6f3f76ab525b27c5d14830bbea4744a7bf73d4a7"

GRID_ATR = [x / 2.0 for x in range(1, 21)]      # 0.5, 1.0, ..., 10.0 - plus "none"
STOP_ATR = 2.5
TIME_BARRIER = 20
SYNTHETIC_PATHS = 100_000
FIRST_YEAR = 2018
PURGE_SESSIONS = 20
TRADE_THROUGH = 0.0005
HAIRCUT = 0.00652
PENALTY = 0.02
CEILING = 0.142806
BINDING_MIN = 0.05
DSR_TRIALS = 235          # 170 experiments.jsonl + 64 registered before H-0026 + H-0026
DSR_MIN = 0.95
START = 100_000.0

# The code the registered commit must contain, unchanged, when the runner runs.
CODE_FILES = ["scripts/h0026_spec.py", "scripts/run_h0026.py",
              "scripts/register_h0026.py", "scripts/research_gate.py",
              "scripts/forensics_regime.py", "src/event_aware_trader/portfolio.py",
              "src/event_aware_trader/exit_placement.py",
              "src/event_aware_trader/research.py"]

CHANGES_FROM_DRAFT = [
    "The process is stated and fitted as the AR(1) P_t = a + phi x P_(t-1) + sigma x e_t "
    "(the discrete O-U form whenever phi < 1), so a fit with no reversion is simulated as "
    "it stands instead of being undefined.",
    "The synthetic objective is GROSS mean profit in ATRs - no cost and no haircut - so the "
    "chosen level cannot be driven by avoiding the rule-exit haircut (H-0010's trap).",
    "Ties resolve to the larger target, 'none' counting as largest, so a level that never "
    "binds on synthetic paths is not added.",
    "The deflated Sharpe ratio uses every configuration this project has evaluated "
    "(N = 235), not only the exit family (N = 78): stricter.",
    "The chronological-thirds clause is defined on equal-session thirds of the daily "
    "equity curves.",
    "H-0010's clause E - the gain must survive once the avoided rule-exit haircut is "
    "counted - was added on 2026-09-27, before sealing.",
]


def hypothesis() -> Hypothesis:
    return Hypothesis(
        hypothesis_id=HYPOTHESIS_ID,
        kind=CONFIRMATORY,
        statement=(
            "A profit-take level derived from the frozen strategy's OWN reversion "
            "dynamics - an AR(1) / discrete Ornstein-Uhlenbeck process fitted walk-forward "
            "to past baseline trades' post-entry paths in ATR units, with the level chosen "
            "on synthetic paths to maximise expected profit per trade (Carr & Lopez de "
            "Prado, arXiv 1408.1159) - raises decade total return above the frozen baseline "
            "when added as a resting limit to the unchanged frozen exits, and the gain "
            "survives the sealed clauses. If the calibrated process chooses 'no target' in "
            "every year the rule IS the baseline and the outcome is C."),
        rationale=(
            "Every take profit this project tested was a hand-picked multiple of risk "
            "(EXP-0049/0050, H-0002, H-0010, EXP-0051/0052). The literature's method is "
            "different in kind: estimate the trade's reversion process, then derive the "
            "level on synthetic data so it is never searched on the backtest (Carr & Lopez "
            "de Prado; Lipton & Lopez de Prado 2020; Bertram 2010; Leung & Li 2015). The "
            "frozen 2.5-ATR stop is kept as insurance the model cannot value (post-stop "
            "forensics: 22.2% of stopped names traded 5% or more below the fill within 10 "
            "sessions). Expected outcome, stated before any number: likely NO improvement - "
            "EXP-0050 measured return falling as fixed targets tighten and H-0021 found "
            "81.2% of +2% crossers went on higher. H-0010 showed a take profit can look "
            "+19.25 points better purely by avoiding the rule-exit haircut, so clause E "
            "attributes that separately. Owner approved the run on 2026-09-28."),
        rule=(
            "Keep every frozen exit unchanged: the 2.5 x ATR(14) resting stop, RSI(14) >= 60 "
            "and the 20-session cap. ADD one resting sell limit at raw_entry + k*(Y) x "
            "entry_atr for every position ENTERED in calendar year Y >= 2018 "
            "(run_portfolio's mr_take_profit_atr_by_year); positions entered before 2018, or "
            "in a year whose k* is 'none', carry no target. CALIBRATION for year Y: take "
            "every frozen-baseline decade trade; its path is P_t = (close_(i+t) - close_i) / "
            "entry_atr for t = 0..20 on its symbol's verified decade bars, i the entry "
            "session, entry_atr = (close_i - initial_stop) / 2.5; paths continue past the "
            "trade's actual exit; paths with fewer than 20 sessions of data are excluded. A "
            "path qualifies for Y if its 20th session is on or before the SPY session 20 "
            "sessions before Y's first SPY session. Fit P_t = a + phi x P_(t-1) + sigma x e_t "
            "by pooled OLS over t = 1..20 of every qualifying path (sigma = residual standard "
            "deviation, n - 2). Simulate 100,000 paths of that AR(1) with seed Y, the stop at "
            "-2.5 and a 20-step time barrier, booking P at the step a level is crossed "
            "(exit_placement.ar1_profit_paths and evaluate_rules). k*(Y) is the grid point - "
            "0.5 to 10.0 ATR in steps of 0.5, plus 'none' - with the highest GROSS mean P at "
            "exit; means equal within 1e-12 resolve to the larger target, 'none' largest. "
            "No trimming, no per-symbol parameters, no other process."),
        parameters={
            "dataset": {"id": DATASET_ID, "sha256": DATASET_SHA256},
            "population": ("the frozen baseline's own decade trades (698) for calibration "
                           "paths; the frozen emulator's candidate stream, unchanged, for "
                           "evaluation"),
            "benchmark": ("the frozen baseline on the same emulator and data (+58.5889% / "
                          "698 trades must reproduce first); SPY price return reported "
                          "alongside"),
            "grid_atr": GRID_ATR,
            "grid_includes_none": True,
            "stop_atr": STOP_ATR,
            "time_barrier_sessions": TIME_BARRIER,
            "synthetic_paths": SYNTHETIC_PATHS,
            "seed": "calendar year Y",
            "first_year": FIRST_YEAR,
            "purge_sessions": PURGE_SESSIONS,
            "objective": "gross mean profit at exit, in ATRs; no cost, no haircut",
            "tie_rule": "equal within 1e-12 -> larger target; 'none' is largest",
            "trade_through": TRADE_THROUGH,
            "haircut": HAIRCUT,
            "penalty": PENALTY,
            "drawdown_ceiling": CEILING,
            "binding_min_share": BINDING_MIN,
            "dsr_trials": DSR_TRIALS,
            "dsr_min": DSR_MIN,
            "dsr_variance": "the registry's observed trial-Sharpe variance "
                            "(research.trial_sharpe_variance), as research.deflated_sharpe "
                            "reads it by default",
            "changes_from_draft": CHANGES_FROM_DRAFT,
        },
        search_procedure=(
            "One configuration. The grid is traversed only on synthetic paths, never on the "
            "backtest. The process, objective, grid, calibration, purge, seeds, tie rule, "
            "fill rule and every clause are fixed here and may not change after any result "
            "is seen. A second emulator run with trade-through 0 (touch fills) is a SECONDARY "
            "optimistic bound: it is reported, labelled unexecutable, and can neither pass "
            "nor fail anything."),
        max_configurations=1,
        datasets=["decade (development) via research_gate.verify_dataset; the frozen "
                  "baseline's 698 trades",
                  "thirty_year: LOST - not used", "clean OOS: NOT USED",
                  "live audit log: NOT USED"],
        information_boundary=(
            "k*(Y) uses only paths whose 20th session is at least 20 sessions before Y's first "
            "session; entry_atr is the ATR the stop was sized from at the entry bar; the limit "
            "is placed at entry. No bar after a decision sets a level. A bar that reaches both "
            "the stop and the limit is given to the stop (the emulator checks the stop first)."),
        execution_assumptions=(
            "research.production_report (the frozen PRODUCTION_CANDIDATE: entry at the signal "
            "close; rule exits at close x (1 - 0.652%); stops as the candidate prices them) "
            "with mr_take_profit_atr_by_year = {Y: k*(Y)} and mr_take_profit_trade_through = "
            "0.0005: the limit fills at the open when the open is at or above it, else at the "
            "level only when the high exceeds it by 5 basis points. Daily bars cannot see the "
            "queue (H-0017, H-0018), so touch fills are only the secondary bound."),
        primary_metric=(
            "variant total return minus baseline total return on the decade, same emulator, "
            "same candidate stream"),
        secondary_metrics=[
            "the rule-exit haircut avoided by take-profit exits, in dollars (H-0010's formula)",
            "max drawdown against the 14.2806% ceiling",
            "share of the variant's trades exiting at the limit",
            "equal-session thirds and year-by-year deltas",
            "k*(Y), a, phi, sigma, half-life and fair level per year",
            "the touch-fill bound, labelled unexecutable",
            "stop exits on a bar that also reached the limit",
            "deflated Sharpe with N = 78 (exit family + 1), secondary only",
            "SPY price return over the same window",
        ],
        acceptance_criteria=(
            "Outcome A (PASS, research_evidence only) requires ALL of: (A) primary metric >= "
            "+2.0 points; (E) variant final equity minus baseline final equity, minus the "
            "rule-exit haircut avoided by take-profit exits (sum of |quantity| x exit_price x "
            "0.652%), >= $2,000 on $100,000; (B) |max drawdown| <= 14.2806%; (D) variant "
            "growth above baseline growth in at least 2 of 3 consecutive equal-session thirds "
            "of the daily equity curves; (F) take-profit exits >= 5% of the variant's trades; "
            "(G) research.deflated_sharpe(variant, trials=235) >= 0.95. Outcome B: REJECTED, "
            "naming every failed clause. Outcome C: NO TARGET - k*(Y) is 'none' in every "
            "year, the rule is the baseline, and nothing is evaluated. STOPPED if the baseline "
            "does not reproduce +58.5889% / 698 or the registration does not verify."),
        rejection_criteria=(
            "Explicitly NOT successes: a gain explained by the avoided rule-exit haircut "
            "(H-0010: +19.25 points that were -$39,611 net of it); a gain that appears only "
            "under touch fills; a gain concentrated in one third or one year; a k*(Y) that "
            "moves erratically across years, which is reported and not smoothed; any use of "
            "Sharpe as the objective after the fact; any baseline other than the frozen one. "
            "A PASS is research_evidence on survivorship-affected data (H-0023) and is never "
            "by itself a production rule."),
        robustness_requirements=[
            "baseline +58.5889% / 698 reproduced first",
            "survivorship: H-0023 - the decade baseline is not validated; ceiling research_evidence",
            "every prior exit configuration named in the report (77 = 54 + 23)",
            "CONF-1 stated, and not resolved silently",
        ],
        complexity_penalty="The standing two percentage points.",
        required_oos_test=(
            "None available: the thirty-year dataset is lost and Clean OOS is reserved for the "
            "frozen strategy. A pass is research_evidence only; promotion would need a "
            "separately governed forward evaluation."),
        promotion_requirements=[
            "owner approval",
            "money-path review (SPEC-0001 C-27)",
            "new fingerprint and a restarted evaluation clock",
            "Clean OOS remains uncontaminated",
        ],
    )
