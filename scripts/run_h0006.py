"""Run H-0006. Equivalence first, then the three sealed overlays.

The baseline is run ONCE and its cash curve is reused for every overlay,
because the overlay by construction cannot change a trade. The
equivalence check is mode "none": it must reproduce the baseline curve
exactly, or the overlay is not the identity it claims to be and nothing
built on it can be trusted.

  python scripts/run_h0006.py --check-only
  python scripts/run_h0006.py
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.data import load_bars                  # noqa: E402
from event_aware_trader.mean_reversion import conviction as shipped_conviction  # noqa: E402
from event_aware_trader.modelgov import prereg                 # noqa: E402
from event_aware_trader.modelgov.adjudicate import (           # noqa: E402
    Clause, adjudicate, standard_clauses, surviving, yearly_deltas)
from event_aware_trader.phase5 import parking                  # noqa: E402
from event_aware_trader.phase5.metrics import measure          # noqa: E402
from event_aware_trader.research import (                      # noqa: E402
    load_tbill_rates, production_report)
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
EXCLUDED_YEAR = 2025
MODES = [("C1 always", "always"), ("C2 trend_cash0", "trend_cash0"),
         ("C3 trend_bills", "trend_bills")]


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
    return sum(1 for l in path.read_text(encoding="utf-8").splitlines()
               if l.strip() and json.loads(l).get("dataset") == "thirty_year")


def spy_by_year(index):
    """SPY calendar-year price returns over the identical window."""
    by = {}
    for bar in index:
        by.setdefault(bar.timestamp.year, []).append(bar.close)
    return {y: v[-1] / v[0] - 1.0 for y, v in sorted(by.items())}


def without_year(row, baseline, year):
    keep = [y for y in sorted(baseline["by_year"]) if y != year]
    c = b = 1.0
    for y in keep:
        c *= 1.0 + row["by_year"].get(y, 0.0)
        b *= 1.0 + baseline["by_year"][y]
    return 100.0 * ((c - 1.0) - (b - 1.0))


def h0006_clauses(row, baseline):
    """Registered: the standard clauses, with a 2-point return margin."""
    clauses = standard_clauses(row, baseline)
    margin = row["total_return"] > baseline["total_return"] + 0.02
    clauses[0] = Clause("beats baseline by more than 2 points", margin,
                        "{0:+.4f} vs {1:+.4f}".format(
                            row["total_return"], baseline["total_return"]))
    inc = row["total_return"] - baseline["total_return"]
    exc = without_year(row, baseline, EXCLUDED_YEAR)
    clauses.append(Clause("positive including and excluding 2025",
                          inc > 0 and exc > 0,
                          "{0:+.2f} / {1:+.2f} pts".format(100 * inc, exc)))
    return clauses


def main():
    check_only = "--check-only" in sys.argv
    sealed = [p for p in prereg.load() if p["hypothesis_id"] == "H-0006"]
    if not sealed:
        print("REFUSED: H-0006 is not registered.")
        return 2
    seal = sealed[0]
    if not prereg.verify_chain()["intact"]:
        print("REFUSED: registration chain broken.")
        return 2
    before = thirty_year_reads()
    print("H-0006 seal {0} | commit {1}".format(seal["seal"][:16],
                                               seal["code_commit"][:12]))
    print("thirty-year reads BEFORE {0}".format(before))

    series = load()
    index = series["SPY"]
    rates = load_tbill_rates()
    print("decade: {0} symbols; SPY {1} -> {2}".format(
        len(series), index[0].timestamp.date(), index[-1].timestamp.date()),
        flush=True)
    base_report = production_report(series, conviction=conviction,
                                    dataset="decade", purpose="rejection_test")
    baseline = measure(base_report, "BASELINE").as_dict()
    spy_total = index[-1].close / index[0].close - 1.0
    spy_years = spy_by_year(index)
    print("baseline {0:+.4%} | SPY price-only {1:+.4%}".format(
        baseline["total_return"], spy_total))

    print("\nEQUIVALENCE: overlay mode 'none' must be the identity")
    same = parking.with_index_parking(base_report, index, "none")
    drift = max(abs(a[1] - b[1]) for a, b in
                zip(same.equity_curve, base_report.equity_curve))
    print("  max |difference| across {0} points: {1:.10f}".format(
        len(same.equity_curve), drift))
    if drift > 1e-9:
        print("STOPPED: the overlay is not the identity. Nothing else run.")
        return 2
    print("  IDENTITY - proceeding")
    if check_only:
        return 0

    print("\nSEALED CONFIGURATIONS")
    rows = []
    for label, mode in MODES:
        lifted = parking.with_index_parking(
            base_report, index, mode,
            cash_rates=rates if mode == "trend_bills" else None)
        scored = measure(lifted, label).as_dict()
        scored["mode"] = mode
        scored["switches"] = lifted.parking_switches
        scored["vs_spy_points"] = 100.0 * (scored["total_return"] - spy_total)
        rows.append(scored)
        print("  {0:<16} total {1:+8.2%}  CAGR {2:+6.2%}  maxDD {3:7.2%}  "
              "vol {4:5.1%}  vs SPY {5:+7.1f} pts  flips {6}".format(
                  label, scored["total_return"], scored["cagr"],
                  scored["max_drawdown"], scored["annualised_volatility"],
                  scored["vs_spy_points"], lifted.parking_switches), flush=True)

    print("\nYEAR BY YEAR (return)")
    years = sorted(baseline["by_year"])
    print("  {0:<6} {1:>9} {2:>9} {3:>9} {4:>9} {5:>9}".format(
        "year", "SPY", "baseline", "C1", "C2", "C3"))
    for y in years:
        print("  {0:<6} {1:>+9.2%} {2:>+9.2%} {3:>+9.2%} {4:>+9.2%} {5:>+9.2%}".format(
            y, spy_years.get(y, 0.0), baseline["by_year"][y],
            *[r["by_year"].get(y, 0.0) for r in rows]))

    print("\nSTANDING CLAUSES (registered; C1 is a control and cannot survive)")
    verdicts = adjudicate(rows, baseline, clauses=h0006_clauses,
                          family_clause=lambda rs: Clause(
                              "trend filter reduces drawdown vs unconditional",
                              abs(rs[1]["max_drawdown"]) < abs(rs[0]["max_drawdown"]),
                              "C2 {0:.4f} vs C1 {1:.4f}".format(
                                  rs[1]["max_drawdown"], rs[0]["max_drawdown"])))
    for v in verdicts:
        tag = "control" if v.label.startswith("C1") else (
            "PASSES ALL" if v.survives else
            "fails: " + ", ".join(c.name for c in v.failures))
        print("  {0:<16} {1}".format(v.label, tag))
    candidates = [v for v in surviving(verdicts) if not v.label.startswith("C1")]
    print("\nVERDICT")
    print("  configurations passing every clause: {0}".format(
        [v.label for v in candidates] or "none"))
    print("  H-0006 accepted as research evidence: {0}".format(bool(candidates)))
    after = thirty_year_reads()
    print("  thirty-year reads AFTER {0} (must equal {1})".format(after, before))

    out = REPO / "data" / "phase5" / "h0006-results.json"
    out.write_text(json.dumps({
        "seal": seal["seal"], "baseline": baseline, "spy_total": spy_total,
        "spy_by_year": spy_years, "configurations": rows,
        "verdicts": [v.as_dict() for v in verdicts],
        "accepted": bool(candidates),
        "thirty_year_reads": {"before": before, "after": after},
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
