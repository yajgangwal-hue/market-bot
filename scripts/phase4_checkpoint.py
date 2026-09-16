"""Phase 4 §9. Produce a checkpoint report, or say why none is due.

Four checkpoints, at 1 / 20 / 60 / 120 clean sessions. A checkpoint below
its threshold is NOT produced: an early report with a thin sample is the
mechanism by which an experiment gets stopped on a favourable quarter, and
the point of this phase is that it cannot be.

Every report separates four things that ordinarily get blended:

  MEASURED        what the record actually contains
  ASSUMED         methodology chosen in advance, not derived from results
  UNCERTAIN       known and unquantified
  UNSUPPORTED     what a reader might infer and the evidence cannot carry

Checkpoint A confirms the embargo genuinely expired. B is infrastructure
and data integrity only. C adds a descriptive performance report. D
repeats it and compares stability. None of them produces a verdict.

  python scripts/phase4_checkpoint.py            # status, plus any due report
  python scripts/phase4_checkpoint.py --force A  # re-render a reached one
"""

import statistics
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.forward import (                      # noqa: E402
    FORWARD_LOG, continuity, first_clean_session, frozen_fingerprint,
    load_sessions, verify_chain)
from event_aware_trader.purge import evaluation_window        # noqa: E402
from event_aware_trader.research import load_registry         # noqa: E402

OUT = REPO / "docs" / "phase4"
PHASE3_FINGERPRINT = (
    "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b")

CHECKPOINTS = {
    "A": (1, "first clean session",
          "Confirm the embargo genuinely expired and the first observation "
          "is clean."),
    "B": (20, "twenty clean sessions",
          "Infrastructure and data-integrity review only. No performance "
          "interpretation."),
    "C": (60, "sixty clean sessions",
          "Correctness acceptance review plus a descriptive performance "
          "report."),
    "D": (120, "one hundred and twenty clean sessions",
          "Repeat the descriptive report and compare the stability of the "
          "observed behaviour. The strategy does not change."),
}

ISOLATION_SUITES = ("tests.test_forward_isolation", "tests.test_phase4_observation",
                    "tests.test_purge_embargo", "tests.test_golden_master")


def run_isolation_suites():
    """§4: the isolation tests run at each checkpoint, not once at the start."""
    import os
    # Both paths. Several suites import sibling helpers from tests/ by bare
    # name (`golden_fixture`), so src alone loads them as import errors and
    # the checkpoint would report a green suite as broken.
    path = os.pathsep.join([str(REPO / "src"), str(REPO / "tests")])
    results = {}
    for suite in ISOLATION_SUITES:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", suite],
            cwd=str(REPO), capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": path})
        tail = (proc.stderr or "").strip().splitlines()
        ran = next((l for l in tail if l.startswith("Ran ")), "")
        results[suite] = {"ok": proc.returncode == 0, "summary": ran}
    return results


def drawdown(equities):
    peak, worst = None, 0.0
    for e in equities:
        peak = e if peak is None else max(peak, e)
        if peak:
            worst = min(worst, e / peak - 1.0)
    return worst


def descriptive(sessions):
    """Raw observations. No annualisation, no ratio, no comparison claim."""
    strat = [s.strategy_return for s in sessions if s.strategy_return is not None]
    bench = [s.benchmark_return for s in sessions if s.benchmark_return is not None]
    cum_s = cum_b = 1.0
    for r in strat:
        cum_s *= (1.0 + r)
    for r in bench:
        cum_b *= (1.0 + r)
    exits = {}
    for s in sessions:
        for e in s.exits:
            exits[e.get("reason", "unknown")] = exits.get(e.get("reason", "unknown"), 0) + 1
    return {
        "sessions": len(sessions),
        "cumulative_strategy_return": cum_s - 1.0,
        "cumulative_benchmark_return": cum_b - 1.0,
        "cumulative_difference": (cum_s - 1.0) - (cum_b - 1.0),
        "max_drawdown": drawdown([s.equity for s in sessions]),
        "daily_volatility": (statistics.pstdev(strat) if len(strat) > 1 else None),
        "exits": exits,
        "mean_exposure": (sum(s.exposure for s in sessions) / len(sessions)
                          if sessions else None),
        "mean_cash_fraction": (sum(s.cash / s.equity for s in sessions if s.equity)
                               / len(sessions) if sessions else None),
    }


def render(letter, sessions, state, chain, window, isolation, calendar_days):
    threshold, name, purpose = CHECKPOINTS[letter]
    n = len(sessions)
    lines = []
    w = lines.append
    w("# Phase 4 — Checkpoint {0}: {1}".format(letter, name))
    w("")
    w("*Generated {0}. {1}*".format(
        datetime.now(timezone.utc).date().isoformat(), purpose))
    w("")
    w("## MEASURED")
    w("")
    w("| | |")
    w("|---|---|")
    w("| research freeze | {0} (derived from the registry) |".format(window.freeze))
    w("| embargo | {0} sessions (the rule's own holding cap) |".format(
        window.embargo_sessions))
    w("| first clean session | {0} |".format(state["first_eligible"] or "not reached"))
    w("| eligible sessions | {0} |".format(state["eligible"]))
    w("| recorded sessions | {0} |".format(state["recorded"]))
    w("| missing sessions | {0} |".format(len(state["missing"]) or "none"))
    w("| chain | {0} |".format("intact" if chain["intact"]
                               else "BROKEN at " + str(chain.get("broken_at"))))
    w("| fingerprint | `{0}` |".format(frozen_fingerprint()[:24]))
    w("| fingerprint unchanged since Phase 3 | {0} |".format(
        "yes" if frozen_fingerprint() == PHASE3_FINGERPRINT else "**NO**"))
    w("")
    if state["missing"]:
        w("Sessions eligible but not recorded: {0}. These are holes, not "
          "gaps to fill — the record cannot be reconstructed after the "
          "fact.".format(", ".join(state["missing"])))
        w("")

    w("### Isolation suites re-run at this checkpoint")
    w("")
    for suite, result in isolation.items():
        w("- `{0}` — {1} {2}".format(suite, "PASS" if result["ok"] else "**FAIL**",
                                     result["summary"]))
    w("")

    protection = sum(1 for s in sessions
                     if any("no resting stop" in i for i in s.data_quality_issues))
    discrepancies = [(s.session, d) for s in sessions
                     for d in s.execution_discrepancies]
    w("### Correctness")
    w("")
    w("| check | result |")
    w("|---|---|")
    w("| loop executed every eligible session | {0} |".format(
        "yes" if not state["missing"] else "no — {0} missing".format(len(state["missing"]))))
    w("| sessions with an unprotected position | {0} |".format(protection))
    w("| execution discrepancies recorded | {0} |".format(len(discrepancies)))
    w("| sessions with a data-quality issue | {0} |".format(
        sum(1 for s in sessions if s.data_quality_issues)))
    w("")

    if letter in ("C", "D") and sessions:
        d = descriptive(sessions)
        w("### Descriptive performance — raw observations only")
        w("")
        w("| | |")
        w("|---|---|")
        w("| sessions | {0} |".format(d["sessions"]))
        w("| cumulative strategy return | {0:+.2%} |".format(d["cumulative_strategy_return"]))
        w("| cumulative benchmark return | {0:+.2%} |".format(d["cumulative_benchmark_return"]))
        w("| cumulative difference | {0:+.2f} pts |".format(100 * d["cumulative_difference"]))
        w("| maximum drawdown | {0:.2%} |".format(d["max_drawdown"]))
        w("| daily volatility | {0} |".format(
            "{0:.3%}".format(d["daily_volatility"]) if d["daily_volatility"] else "n/a"))
        w("| mean exposure | {0:.1%} |".format(d["mean_exposure"] or 0))
        w("| mean cash | {0:.1%} |".format(d["mean_cash_fraction"] or 0))
        w("| exits by reason | {0} |".format(d["exits"] or "none"))
        w("")

    w("## ASSUMED")
    w("")
    w("- The embargo equals the rule's 20-session holding cap. Chosen in "
      "Phase 2 from the information horizon, not from results.")
    w("- The freeze date is the registry's last config-changing entry.")
    w("- Benchmark methodology is Phase 2's, unmodified.")
    w("- The 0.652% exit-timing haircut is a frozen bound, not a measurement.")
    w("- Reconciliation tolerances: $1.00 or 1 basis point on equity and "
      "cash; exact on position counts.")
    w("")
    w("## UNCERTAIN")
    w("")
    w("- The haircut remains unmeasured against live fills.")
    w("- Survivorship bias in the historical universe is unquantified.")
    w("- {0} clean sessions is {1} of what would be needed to speak about "
      "profitability at this strategy's volatility.".format(
          n, "a fraction" if n < 60 else "still a fraction"))
    w("")
    w("## UNSUPPORTED BY THIS EVIDENCE")
    w("")
    w("- That the strategy is profitable.")
    w("- That it outperforms the S&P 500 on return, Sharpe, Sortino or drawdown.")
    w("- That the in-sample drawdown advantage persists out of sample.")
    w("- That the parameters chosen in sample are correct.")
    w("")
    w("At ~6–9% annual volatility the standard error of the return over 60 "
      "sessions is roughly 3%, which exceeds the entire annual edge under "
      "test. A favourable quarter and an unfavourable one are equally "
      "consistent with the same strategy.")
    return "\n".join(lines) + "\n"


def main():
    registry = load_registry()
    from event_aware_trader.data import fetch_alpaca_equity_bars
    bars = fetch_alpaca_equity_bars(["SPY"], days=400, interval="1d",
                                    include_today=True).get("SPY", [])
    calendar_days = [b.timestamp.date() for b in bars]
    window = evaluation_window(registry, calendar_days)
    chain = verify_chain(FORWARD_LOG)
    sessions = load_sessions(FORWARD_LOG) if chain["intact"] else []
    state = continuity(sessions, calendar_days, registry)
    n = len(sessions)

    print("clean sessions: {0} | eligible: {1} | first clean: {2}".format(
        n, state["eligible"], state["first_eligible"] or "not reached"))

    forced = None
    if "--force" in sys.argv:
        forced = sys.argv[sys.argv.index("--force") + 1].upper()

    due = [k for k, (threshold, _, _) in CHECKPOINTS.items() if n >= threshold]
    if forced:
        if forced not in CHECKPOINTS:
            print("unknown checkpoint {0}".format(forced))
            return 1
        if n < CHECKPOINTS[forced][0]:
            print("REFUSED: checkpoint {0} needs {1} clean sessions; {2} "
                  "recorded. An early checkpoint is how an experiment gets "
                  "stopped on a convenient sample."
                  .format(forced, CHECKPOINTS[forced][0], n))
            return 1
        due = [forced]

    if not due:
        nxt = min(CHECKPOINTS.items(), key=lambda kv: kv[1][0])
        print("no checkpoint due: {0} clean session(s) recorded, checkpoint "
              "{1} needs {2}.".format(n, nxt[0], nxt[1][0]))
        return 0

    isolation = run_isolation_suites()
    OUT.mkdir(parents=True, exist_ok=True)
    for letter in due:
        path = OUT / "checkpoint-{0}.md".format(letter.lower())
        if path.exists() and forced != letter:
            continue
        path.write_text(render(letter, sessions, state, chain, window,
                               isolation, calendar_days), encoding="utf-8")
        print("wrote {0}".format(path.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
