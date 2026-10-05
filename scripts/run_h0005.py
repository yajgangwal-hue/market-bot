"""Run H-0005. Equivalence check first, then the three sealed thresholds.

ORDER IS NOT NEGOTIABLE. G=1.00R is re-run first and must reproduce the
recorded +13.7125 points. That is an implementation-integrity check, not
a new experiment: if the simulator no longer produces what it produced
before, every earlier number is suspect and the run stops rather than
carrying a silent drift into three new configurations.

The frozen prior points are then used AS RECORDED to complete the
six-point family. The equivalence re-run confirms them; it does not
replace them.

  python scripts/run_h0005.py --check-only
  python scripts/run_h0005.py
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.data import load_bars                  # noqa: E402
from event_aware_trader.mean_reversion import conviction as shipped_conviction  # noqa: E402
from event_aware_trader.modelgov import gradient, prereg       # noqa: E402
from event_aware_trader.modelgov.adjudicate import (           # noqa: E402
    adjudicate, leave_one_best_year_out, surviving, yearly_deltas)
from event_aware_trader.phase5.metrics import measure          # noqa: E402
from event_aware_trader.research import production_report      # noqa: E402
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto  # noqa: E402

# Decade price data comes only through the research dataset gate: verified
# before a bar is read, fail-closed, no scratchpad fallback. It replaced a
# first-match glob over session scratchpads on 2026-09-24
# (docs/2026-09-24-governed-research-dataset-migration.md).
if str(REPO / "scripts") not in sys.path:
    sys.path.append(str(REPO / "scripts"))
from research_gate import dataset_file, price_dir              # noqa: E402
WINDOW = 400
_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-WINDOW:], c)
_conv = {}

NEW_THRESHOLDS = [0.25, 0.50, 0.75]
FROZEN = {1.00: +13.7125, 1.50: -1.3647, 2.00: 0.0000}
EXPECTED_DIRECTION = -1
EXCLUDED_YEAR = 2025


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def load():
    base = price_dir("deep")        # verified before any bar is read
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        bars = load_bars(dataset_file(base, symbol + ".csv"))
        if len(bars) >= 500:
            out[symbol] = bars
    return out


def thirty_year_reads():
    path = REPO / "docs" / "dataset-uses.jsonl"
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip()
               and json.loads(line).get("dataset") == "thirty_year")


def without_year(row, baseline, year):
    """Total-return delta with one calendar year's contribution removed.

    Compounds the remaining years rather than subtracting a percentage,
    so the excluded-year figure is a real return and not an arithmetic
    convenience.
    """
    keep = [y for y in sorted(baseline.get("by_year") or {}) if y != year]
    cand = base = 1.0
    for y in keep:
        cand *= 1.0 + (row.get("by_year") or {}).get(y, 0.0)
        base *= 1.0 + (baseline.get("by_year") or {})[y]
    return 100.0 * ((cand - 1.0) - (base - 1.0))


def main():
    check_only = "--check-only" in sys.argv
    sealed = [p for p in prereg.load() if p["hypothesis_id"] == "H-0005"]
    if not sealed:
        print("REFUSED: H-0005 is not registered.")
        return 2
    seal = sealed[0]
    chain = prereg.verify_chain()
    if not chain["intact"]:
        print("REFUSED: registration chain broken -> {0}".format(chain))
        return 2
    if sorted(seal["parameters"]["new_thresholds_R"]) != sorted(NEW_THRESHOLDS):
        print("REFUSED: this runner's grid is not the sealed grid.")
        return 2

    before = thirty_year_reads()
    print("H-0005 seal {0}".format(seal["seal"][:16]))
    print("  commit at registration {0}".format(seal["code_commit"][:12]))
    print("  sealed grid            {0}".format(NEW_THRESHOLDS))
    print("  frozen prior points    {0}".format(FROZEN))
    print("  expected rho direction {0}".format(EXPECTED_DIRECTION))
    print("  thirty-year reads BEFORE {0}".format(before))

    series = load()
    print("\ndecade: {0} symbols".format(len(series)), flush=True)
    base_report = production_report(series, conviction=conviction,
                                    dataset="decade", purpose="rejection_test")
    baseline = measure(base_report, "BASELINE").as_dict()
    print("baseline total return {0:+.4%}".format(baseline["total_return"]))

    # ---- implementation equivalence, before anything new ------------------
    print("\nIMPLEMENTATION EQUIVALENCE at G=1.00R (not a new experiment)")
    check = measure(production_report(series, conviction=conviction,
                                      dataset="decade",
                                      purpose="rejection_test",
                                      mr_lock_at_r=1.00),
                    "equivalence 1.00R").as_dict()
    observed = 100.0 * (check["total_return"] - baseline["total_return"])
    print("  recorded  {0:+.4f} points".format(FROZEN[1.00]))
    print("  reproduces{0:+.4f} points".format(observed))
    try:
        gradient.check_frozen({1.00: observed}, FROZEN)
    except gradient.FrozenObservationChanged as error:
        print("\nSTOPPED: {0}".format(error))
        print("Every earlier number is suspect until this is understood. "
              "No new configuration was run.")
        return 2
    print("  MATCHES - proceeding")
    if check_only:
        print("\n--check-only: stopping before the new configurations.")
        return 0

    # ---- the three sealed configurations ----------------------------------
    print("\nSEALED CONFIGURATIONS")
    rows = []
    for g in NEW_THRESHOLDS:
        scored = measure(production_report(series, conviction=conviction,
                                           dataset="decade",
                                           purpose="rejection_test",
                                           mr_lock_at_r=g),
                         "lock at {0}R".format(g)).as_dict()
        scored["threshold"] = g
        rows.append(scored)
        print("  G={0:<5} total {1:+.4%}  delta {2:+.4f} pts  trades {3}"
              .format(g, scored["total_return"],
                      100.0 * (scored["total_return"] - baseline["total_return"]),
                      scored["trades"]), flush=True)

    # ---- the six-point family ---------------------------------------------
    thresholds = NEW_THRESHOLDS + sorted(FROZEN)
    deltas = [100.0 * (r["total_return"] - baseline["total_return"])
              for r in rows] + [FROZEN[t] for t in sorted(FROZEN)]
    family = gradient.classify_family(thresholds, deltas, EXPECTED_DIRECTION)

    print("\nSIX-POINT FAMILY")
    print("  thresholds {0}".format(thresholds))
    print("  deltas     {0}".format([round(d, 4) for d in deltas]))
    print("  adjacent   {0}".format(
        [round(d, 4) for d in family.adjacent_differences]))
    print("  spearman   {0}".format(
        "n/a" if family.spearman is None else round(family.spearman, 4)))
    print("\n" + family.explain())
    print("\n  detail: {0}".format(json.dumps(family.detail)))

    # ---- standing clauses, per configuration ------------------------------
    print("\nSTANDING CLAUSES (no configuration pre-selected)")
    verdicts = adjudicate(rows, baseline)
    for row, verdict in zip(rows, verdicts):
        inc = 100.0 * (row["total_return"] - baseline["total_return"])
        exc = without_year(row, baseline, EXCLUDED_YEAR)
        both = inc > 0 and exc > 0
        print("  {0:<16} 2025-in {1:+8.4f}  2025-out {2:+8.4f}  "
              "both positive {3:<5}  {4}".format(
                  verdict.label, inc, exc, str(both),
                  "PASSES" if verdict.survives and both
                  else "fails: " + ", ".join(
                      c.name.split()[0] for c in verdict.failures)
                  or "fails: 2025 basis"))

    passing = [v for v, r in zip(verdicts, rows)
               if v.survives
               and 100.0 * (r["total_return"] - baseline["total_return"]) > 0
               and without_year(r, baseline, EXCLUDED_YEAR) > 0]
    accepted = family.is_gradient and bool(passing)
    print("\nVERDICT")
    print("  family classification : {0}".format(family.verdict.upper()))
    print("  configurations passing every standing clause: {0}".format(
        [v.label for v in passing] or "none"))
    print("  H-0005 accepted as research evidence: {0}".format(accepted))
    if not accepted:
        print("  The registered hypothesis - that this is a threshold "
              "artefact - is therefore NOT refuted.")

    after = thirty_year_reads()
    print("\n  thirty-year reads AFTER {0} (must equal {1})".format(
        after, before))
    if after != before:
        print("  *** THIRTY-YEAR WINDOW WAS READ. This violates the seal. ***")

    out = REPO / "data" / "phase5" / "h0005-results.json"
    out.write_text(json.dumps({
        "seal": seal["seal"], "baseline": baseline, "configurations": rows,
        "family": family.as_dict(),
        "verdicts": [v.as_dict() for v in verdicts],
        "2025_excluded": {r["label"]: without_year(r, baseline, EXCLUDED_YEAR)
                          for r in rows},
        "accepted": accepted,
        "thirty_year_reads": {"before": before, "after": after},
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
