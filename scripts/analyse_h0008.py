"""Adjudicate H-0008 against the sealed clauses. Nothing is chosen here.

The clauses are read off the registration and applied in order. Two
outcomes were registered in advance as legitimate rather than as
failures of the research: the measurement may CONFIRM 0.652%, or it may
prove too unstable to replace it. Both keep the existing haircut.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov import prereg                 # noqa: E402

MIN_SAMPLE = 100
STABILITY = 0.0025
SYMBOL_CAP, YEAR_CAP = 0.15, 0.50


def main():
    seal = [p for p in prereg.load() if p["hypothesis_id"] == "H-0008"][0]
    d = json.loads((REPO / "docs" / "phase5" / "h0008-drift.json")
                   .read_text(encoding="utf-8"))
    current = d["current_haircut"]
    n = d["reconstructed"]

    print("H-0008 seal {0}".format(seal["seal"][:16]))
    print("currently charged: {0:.4%} per rule exit".format(current))
    print("reconstructed observations: {0} of {1} rule exits\n".format(
        n, d["rule_exits_in_run"]))

    a = n >= MIN_SAMPLE
    c1 = d["top_symbol"]["share"] <= SYMBOL_CAP
    c2 = d["top_year"]["share"] <= YEAR_CAP
    print("CLAUSE A  sample >= {0}          {1} -> {2}".format(
        MIN_SAMPLE, n, "pass" if a else "FAIL"))
    print("CLAUSE C  largest symbol <= {0:.0%}   {1} {2:.1%} -> {3}".format(
        SYMBOL_CAP, d["top_symbol"]["symbol"], d["top_symbol"]["share"],
        "pass" if c1 else "FAIL"))
    print("          largest year <= {0:.0%}     {1} {2:.1%} -> {3}".format(
        YEAR_CAP, d["top_year"]["year"], d["top_year"]["share"],
        "pass" if c2 else "FAIL"))

    print("\nCLAUSE B  first half vs second half within {0:.2%}".format(
        STABILITY))
    print("CLAUSE D  the percentile is strictly BELOW {0:.4%}".format(current))
    print("\n  {0:<8} {1:>10} {2:>10} {3:>9} {4:>7} {5:>7} {6:>9}".format(
        "config", "value", "vs charged", "half gap", "B", "D", "verdict"))
    rows, survivors = [], []
    for cfg in d["configurations"]:
        b = cfg["half_gap"] <= STABILITY
        dd = cfg["value"] < current
        ok = a and c1 and c2 and b and dd
        rows.append({"label": cfg["label"], "percentile": cfg["percentile"],
                     "value": cfg["value"], "A": a, "B": b, "C": c1 and c2,
                     "D": dd, "passes": ok})
        if ok:
            survivors.append(cfg["label"])
        print("  {0:<8} {1:>10.4%} {2:>+10.2f}x {3:>9.4%} {4:>7} {5:>7} "
              "{6:>9}".format(cfg["label"], cfg["value"],
                              cfg["value"] / current, cfg["half_gap"],
                              "pass" if b else "FAIL",
                              "pass" if dd else "FAIL",
                              "pass" if ok else "FAIL"))

    verdict = "ACCEPTED" if survivors else "REJECTED"
    print("\nVERDICT: H-0008 {0}".format(verdict))
    if not survivors:
        print("  THE EXISTING 0.652% HAIRCUT STANDS, UNCHANGED.")
        if all(c["value"] >= current for c in d["configurations"]):
            print("  Every registered percentile sits ABOVE what is charged.")
            print("  The registered direction was that they would sit below.")
            print("  This CONFIRMS the current haircut and, at the bounding")
            print("  percentiles, suggests it is if anything too LOW.")

    print("\n  RECORDED, NOT ADOPTED: the MEAN drift is {0:+.4%}, which is "
          "below".format(d["mean"]))
    print("  the {0:.4%} charged. H-0008 registered a PERCENTILE of the "
          "adverse".format(current))
    print("  tail, not the mean, because portfolio.py calls the haircut 'a")
    print("  conservative bound, not a best guess'. Switching to the mean")
    print("  now, having seen that it is favourable, is exactly the move the")
    print("  registration exists to prevent. Whether the haircut should BOUND")
    print("  a cost or ESTIMATE one is a real question and a legitimate")
    print("  future registration. It is not a conclusion of H-0008.")

    u = d["unmodellable"]
    print("\n  CEILING ON THE WHOLE EXERCISE: on {0} held sessions inside "
          "the".format(u["held_sessions"]))
    print("  intraday window, {0} closed below RSI 60 yet {1} ({2:.1%}) "
          "crossed".format(u["closed_below_60"], u["crossed_intraday"],
                           u["crossed_intraday"] / u["closed_below_60"]))
    print("  60 INTRADAY. The live bot exits on those days and the simulator")
    print("  holds. No haircut at any value represents that divergence.")

    out = REPO / "docs" / "phase5" / "h0008-adjudication.json"
    out.write_text(json.dumps({
        "seal": seal["seal"], "verdict": verdict,
        "current_haircut": current, "haircut_unchanged": True,
        "sample": n, "clause_a": a, "clause_c": c1 and c2,
        "per_configuration": rows, "survivors": survivors,
        "mean_drift_recorded_not_adopted": d["mean"],
        "unmodellable": u,
        "thirty_year_reads": 13,
    }, indent=1, sort_keys=True), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
