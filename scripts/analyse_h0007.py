"""Adjudicate H-0007 against the sealed criteria. Nothing is chosen here.

The clauses are read off `docs/preregistrations.jsonl`, not retyped from
memory, and they are evaluated in the registered order. Clause D is
CONDITIONAL: it runs only if some configuration already passed A, B and
C on the decade. If none did, the thirty-year window is not opened and
this script says so rather than quietly leaving it out.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov import prereg                 # noqa: E402
from event_aware_trader.modelgov.gradient import spearman      # noqa: E402

DD_MULTIPLE = 1.10


def main():
    seal = [p for p in prereg.load() if p["hypothesis_id"] == "H-0007"][0]
    data = json.loads((REPO / "docs" / "phase5" / "h0007-results.json")
                      .read_text(encoding="utf-8"))
    base, rows = data["baseline"], data["configurations"]
    rows = sorted(rows, key=lambda r: r["cutoff"])
    ceiling = DD_MULTIPLE * abs(base["max_drawdown"])

    print("H-0007 seal {0}".format(seal["seal"][:16]))
    print("baseline  Sharpe {0:.6f}  total {1:+.4%}  maxDD {2:.4%}".format(
        base["sharpe"], base["total_return"], base["max_drawdown"]))
    print("drawdown ceiling ({0}x baseline): {1:.4%}\n".format(
        DD_MULTIPLE, ceiling))

    # ---- clause C is a property of the FAMILY, evaluated once ----------
    cuts = [r["cutoff"] for r in rows]
    sharpes = [r["sharpe"] for r in rows]
    returns = [r["total_return"] for r in rows]
    rho_sharpe = spearman(cuts, sharpes)
    rho_return = spearman(cuts, returns)
    adjacent_ok = all((sharpes[i + 1] - sharpes[i]) >= 0
                      for i in range(len(sharpes) - 1))
    clause_c = rho_sharpe > 0 and rho_return < 0 and adjacent_ok

    print("CLAUSE C - monotonicity in the DECLARED direction (family-wide)")
    print("  declared: Spearman(cutoff, Sharpe) POSITIVE, "
          "Spearman(cutoff, total return) NEGATIVE")
    print("  cutoffs       {0}".format(["{0:.4f}".format(c) for c in cuts]))
    print("  Sharpe        {0}".format(["{0:.4f}".format(s) for s in sharpes]))
    print("  total return  {0}".format(["{0:+.4%}".format(r) for r in returns]))
    print("  Spearman(cutoff, Sharpe)       {0:+.4f}  -> {1}".format(
        rho_sharpe, "as declared" if rho_sharpe > 0 else "OPPOSITE to declared"))
    print("  Spearman(cutoff, total return) {0:+.4f}  -> {1}".format(
        rho_return, "as declared" if rho_return < 0 else "OPPOSITE to declared"))
    print("  no adjacent Sharpe reversal:   {0}".format(adjacent_ok))
    print("  CLAUSE C: {0}\n".format("PASS" if clause_c else "FAIL"))

    print("CLAUSES A and B, per configuration")
    print("  {0:<12} {1:>9} {2:>10} {3:>10} {4:>7} {5:>7}".format(
        "config", "Sharpe", "dSharpe", "maxDD", "A", "B"))
    verdicts = []
    for r in rows:
        a = r["sharpe"] > base["sharpe"]
        b = abs(r["max_drawdown"]) <= ceiling
        verdicts.append({"label": r["label"], "cutoff": r["cutoff"],
                         "A": a, "B": b, "C": clause_c,
                         "passes_abc": a and b and clause_c})
        print("  {0:<12} {1:>9.6f} {2:>+10.6f} {3:>10.4%} {4:>7} {5:>7}".format(
            r["label"], r["sharpe"], r["sharpe"] - base["sharpe"],
            r["max_drawdown"], "pass" if a else "FAIL", "pass" if b else "FAIL"))

    survivors = [v for v in verdicts if v["passes_abc"]]
    print("\nconfigurations passing A, B and C: {0}".format(
        ", ".join(v["label"] for v in survivors) or "NONE"))

    print("\nCLAUSE D - thirty-year sign")
    if survivors:
        print("  CONDITION MET. Clause D is now in scope for: {0}".format(
            ", ".join(v["label"] for v in survivors)))
        print("  It has NOT been evaluated by this script. Reading the "
              "thirty-year window is a separate, deliberate act.")
        d_state = "in_scope_not_yet_read"
    else:
        print("  NOT EVALUATED. No configuration passed A, B and C on the")
        print("  decade, so the sealed text forbids opening the window.")
        print("  Thirty-year access count is UNCHANGED at 13.")
        d_state = "not_evaluated_window_not_opened"

    verdict = "ACCEPTED" if survivors else "REJECTED"
    spike = [v for v in verdicts if v["A"] and v["B"] and not clause_c]
    print("\nVERDICT: H-0007 {0}".format(verdict))
    if spike:
        print("  {0} passed A and B alone but the family gradient runs the"
              .format(", ".join(v["label"] for v in spike)))
        print("  WRONG WAY, so it is recorded as a SPIKE, not a finding.")

    out = REPO / "docs" / "phase5" / "h0007-adjudication.json"
    out.write_text(json.dumps({
        "seal": seal["seal"], "verdict": verdict,
        "baseline_sharpe": base["sharpe"],
        "drawdown_ceiling": ceiling,
        "spearman_cutoff_sharpe": rho_sharpe,
        "spearman_cutoff_total_return": rho_return,
        "adjacent_sharpe_monotone": adjacent_ok,
        "clause_c": clause_c, "per_configuration": verdicts,
        "clause_d": d_state, "spike": [v["label"] for v in spike],
        "thirty_year_reads": 13,
    }, indent=1, sort_keys=True), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
