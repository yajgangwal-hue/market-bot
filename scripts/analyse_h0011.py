"""Adjudicate H-0011 against the five sealed clauses.

Clause E is the one this experiment exists for, and it has three
parts, all required by the seal:

  1. FILLED and LAPSED priced separately against the baseline's own
     market exit on the same (symbol, entry date).
  2. The queue-position assumption DISCLOSED, not netted out. On daily
     bars a bar whose high touches the level is assumed to fill. A
     touch is not a fill: you are in a queue, and a level that is
     touched and rejected is precisely where you do not get filled.
  3. A pass by a margin smaller than that disclosed uncertainty is
     INCONCLUSIVE, not a pass.

So this computes the BREAK-EVEN FILL RATE: how many of the assumed
fills have to be fictional before the gain is gone. If that number is
close to the modelled fill rate, the result is an artefact of the
fill assumption and the seal says to call it inconclusive.

It also re-prices the result at the two SMALLER haircuts that were
actually measured, because the 0.652% the baseline is charged is the
WORST of three observations and was chosen as a deliberate
over-statement correction, not as an estimate.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.modelgov import prereg                  # noqa: E402
from forensics_regime import load                                # noqa: E402

CACHE = REPO / "docs" / "phase5" / "h0011-cache.json"
PENALTY = 0.02
CEILING = 0.142806
DOMINANCE = 2.5
START = 100_000.0
HAIRCUT = 0.00652
MEASURED_HAIRCUTS = {"10:00 ET (charged)": 0.00652,
                     "12:30 ET": 0.00289,
                     "15:00 ET": 0.00120}
ORDER = [("A patience1", 1), ("B patience2", 2), ("C patience3", 3)]


def main():
    store = json.loads(CACHE.read_text(encoding="utf-8"))
    seal = [p for p in prereg.load() if p["hypothesis_id"] == "H-0011"][0]
    b = store["BASELINE"]["metrics"]
    spy = load()["SPY"]
    spy_total = spy[-1].close / spy[0].close - 1.0
    base_final = START * (1.0 + b["total_return"])
    labels = ["BASELINE"] + [x for x, _p in ORDER]

    print("H-0011 seal {0} | commit {1}".format(seal["seal"][:16],
                                                seal["code_commit"][:12]))
    print("baseline  total {0:+.4%}  maxDD {1:.4%}  trades {2}".format(
        b["total_return"], b["max_drawdown"], b["trades"]))
    print("clause A needs > {0:+.4%} | clause B ceiling {1:.4%}".format(
        b["total_return"] + PENALTY, CEILING))
    print("SPY price-only {0:+.4%}\n".format(spy_total))

    print("=" * 86)
    print("1. ECONOMIC PERFORMANCE")
    print("=" * 86)
    rows = [("total return", "total_return", "{0:+.2%}"),
            ("CAGR", "cagr", "{0:+.2%}"),
            ("Sharpe", "sharpe", "{0:.4f}"),
            ("Sortino", "sortino", "{0:.4f}"),
            ("max drawdown", "max_drawdown", "{0:.4%}"),
            ("Calmar", "calmar", "{0:.4f}"),
            ("trades", "trades", "{0}"),
            ("win rate", "win_rate", "{0:.2%}"),
            ("profit factor", "profit_factor", "{0:.3f}"),
            ("avg hold (days)", "average_hold_days", "{0:.2f}"),
            ("stop rate", "stop_rate", "{0:.2%}"),
            ("transaction costs", "transaction_costs", "${0:,.0f}"),
            ("exposure", "exposure", "{0:.2%}")]
    print("  {0:<24}".format("") + "".join("{0:>15}".format(x[:15])
                                           for x in labels))
    for name, key, fmt in rows:
        cells = []
        for L in labels:
            v = store[L]["metrics"].get(key)
            cells.append(fmt.format(v) if v is not None else "-")
        print("  {0:<24}".format(name) + "".join("{0:>15}".format(c)
                                                 for c in cells))
    print("  {0:<24}".format("vs SPY (points)") + "".join(
        "{0:>15}".format("{0:+.1f}".format(
            100 * (store[L]["metrics"]["total_return"] - spy_total)))
        for L in labels))
    for nm, k in (("limit filled", "limit_filled"),
                  ("limit lapsed", "limit_lapsed"),
                  ("max bars held", "max_bars_held")):
        print("  {0:<24}".format(nm) + "".join(
            "{0:>15}".format(store[L].get(k, 0)) for L in labels))
    print("  {0:<24}".format("fill rate") + "".join(
        "{0:>15}".format("{0:.1%}".format(store[L]["fill_rate"])
                         if store[L].get("fill_rate") else "-")
        for L in labels))

    print("\n  exit-reason mix")
    for L in labels:
        print("    {0:<14} {1}".format(L, store[L]["exit_reasons"]))

    cap_ok = all(store[L]["max_bars_held"] <= 20 for L in labels)
    print("\n  20-bar holding cap respected everywhere: {0}".format(
        "YES" if cap_ok else "NO - CAP BREACHED"))

    print("\n  year by year")
    years = sorted(b["by_year"])
    print("  {0:>6}".format("year") + "".join("{0:>15}".format(x[:15])
                                              for x in labels))
    for y in years:
        print("  {0:>6}".format(y) + "".join(
            "{0:>15}".format("{0:.2%}".format(
                store[L]["metrics"]["by_year"].get(y, 0.0)))
            for L in labels))

    # ---- clause E -------------------------------------------------------
    print("\n" + "=" * 86)
    print("2. CLAUSE E - IS THE GAIN NET OF ADVERSE SELECTION?")
    print("=" * 86)
    print("  Each configuration trade matched to the BASELINE trade with the")
    print("  same (symbol, entry date). The baseline exited that trade at the")
    print("  trigger close as a market order with the haircut charged, so it")
    print("  IS the counterfactual - measured, not modelled.\n")
    print("  {0:<14} {1:>18} {2:>18} {3:>14} {4:>12}".format(
        "config", "FILLED delta", "LAPSED delta", "net", "unmatched"))
    clause_e = {}
    for L, _p in ORDER:
        e = store[L]["clause_e"]
        gain = START * (1.0 + store[L]["metrics"]["total_return"]) - base_final
        clause_e[L] = {"filled": e["filled"], "lapsed": e["lapsed"],
                       "other": e["other"], "net": e["total_delta"],
                       "headline_gain": gain,
                       "passes": e["total_delta"] > PENALTY * START}
        print("  {0:<14} {1:>+13,.0f} /{2:<4} {3:>+13,.0f} /{4:<4} "
              "{5:>+14,.0f} {6:>12}".format(
                  L, e["filled"]["delta"], e["filled"]["n"],
                  e["lapsed"]["delta"], e["lapsed"]["n"], e["total_delta"],
                  "{0}/{1}".format(e["unmatched_cfg"], e["unmatched_base"])))
    print("\n  clause E needs the net above {0:,.0f} (the 2-point penalty)"
          .format(PENALTY * START))
    print("  LAPSED is negative in every configuration, as registered: the")
    print("  orders that did not fill are the ones you wanted out of.")

    # ---- the disclosure the seal demands --------------------------------
    print("\n" + "=" * 86)
    print("3. CLAUSE E, PART 2 - THE QUEUE-POSITION DISCLOSURE")
    print("=" * 86)
    print("  A daily bar whose HIGH touches the level is assumed to fill a")
    print("  resting order at that level. That is an UPPER BOUND, and the")
    print("  seal forbids netting it out. A touch is not a fill: you are in")
    print("  a queue behind every order already resting there, and a level")
    print("  that is touched once and rejected is exactly where the queue")
    print("  does not clear. The true fill rate is lower by an unknown")
    print("  amount.\n")
    print("  So: HOW MANY ASSUMED FILLS MUST BE FICTIONAL BEFORE THE GAIN IS")
    print("  GONE? Each fill converted to a lapse loses its own gain and")
    print("  takes the average lapse loss instead.\n")
    print("  {0:<14} {1:>12} {2:>12} {3:>14} {4:>16} {5:>14}".format(
        "config", "per fill", "per lapse", "swing/convert", "converts to zero",
        "break-even FR"))
    for L, _p in ORDER:
        e = store[L]["clause_e"]
        nf, nl = e["filled"]["n"], e["lapsed"]["n"]
        if not nf:
            continue
        per_fill = e["filled"]["delta"] / nf
        per_lapse = e["lapsed"]["delta"] / nl if nl else 0.0
        swing = per_fill - per_lapse
        surplus = e["total_delta"] - PENALTY * START
        converts = surplus / swing if swing > 0 else float("inf")
        be_fr = max(0.0, (nf - converts)) / (nf + nl)
        print("  {0:<14} {1:>+12,.0f} {2:>+12,.0f} {3:>14,.0f} {4:>16.1f} "
              "{5:>13.1%}".format(L, per_fill, per_lapse, swing, converts,
                                  be_fr))
        clause_e[L]["break_even_fill_rate"] = be_fr
        clause_e[L]["modelled_fill_rate"] = store[L]["fill_rate"]
    print("\n  Read the last two columns together with the modelled fill")
    print("  rate above. If break-even is FAR below modelled, the result")
    print("  tolerates a lot of fill-assumption error. If it is close, the")
    print("  seal says INCONCLUSIVE.")

    # ---- haircut sensitivity --------------------------------------------
    print("\n" + "=" * 86)
    print("4. CLAUSE E, PART 3 - THE HAIRCUT IS ITSELF A CONSERVATIVE GUESS")
    print("=" * 86)
    print("  The 0.652% charged on rule exits is the WORST of three")
    print("  measurements (155 real exits, 5-minute bars), chosen")
    print("  deliberately because overstating risk was the safer error. The")
    print("  live trigger-time distribution is UNVERIFIED - three rule exits")
    print("  have ever been logged. This experiment's gain comes largely")
    print("  from not paying that charge, so it must be re-priced at the")
    print("  smaller measurements.\n")
    print("  {0:<14}".format("config") + "".join(
        "{0:>22}".format(k) for k in MEASURED_HAIRCUTS))
    for L, _p in ORDER:
        cells = []
        for _k, h in MEASURED_HAIRCUTS.items():
            scaled = store[L]["haircut_avoided_dollars"] * (h / HAIRCUT)
            adj = store[L]["clause_e"]["total_delta"] - (
                store[L]["haircut_avoided_dollars"] - scaled)
            cells.append("{0:>+16,.0f} {1:<5}".format(
                adj, "PASS" if adj > PENALTY * START else "FAIL"))
        print("  {0:<14}".format(L) + "".join(cells))
        clause_e[L]["haircut_sensitivity"] = {
            k: store[L]["clause_e"]["total_delta"]
            - (store[L]["haircut_avoided_dollars"]
               * (1 - h / HAIRCUT))
            for k, h in MEASURED_HAIRCUTS.items()}

    # ---- adjudication ----------------------------------------------------
    print("\n" + "=" * 86)
    print("5. ADJUDICATION")
    print("=" * 86)
    deltas = [store[L]["metrics"]["total_return"] - b["total_return"]
              for L, _p in ORDER]
    positive = sorted([d for d in deltas if d > 0], reverse=True)
    if len(positive) >= 2:
        clause_c = positive[0] <= DOMINANCE * positive[1]
        c_note = "largest {0:+.2f} vs second {1:+.2f} pts -> ratio {2:.2f}x".format(
            100 * positive[0], 100 * positive[1], positive[0] / positive[1])
    elif len(positive) == 1:
        clause_c, c_note = False, "only ONE positive delta - a spike"
    else:
        clause_c, c_note = False, "no positive delta"

    print("  {0:<14} {1:>11} {2:>12} {3:>7} {4:>7} {5:>7} {6:>7} {7:>7} "
          "{8:>9}".format("config", "delta pts", "maxDD", "A", "B", "C", "D",
                          "E", "verdict"))
    results = []
    for (L, patience), d in zip(ORDER, deltas):
        m = store[L]["metrics"]
        a = d > PENALTY
        bb = abs(m["max_drawdown"]) <= CEILING
        by = m["by_year"]
        beat = sum(1 for y in years if by.get(y, 0.0) > b["by_year"][y])
        best = max(years, key=lambda y: by.get(y, 0.0) - b["by_year"][y])
        cw = bw = 1.0
        for y in years:
            if y != best:
                cw *= (1 + by.get(y, 0.0))
                bw *= (1 + b["by_year"][y])
        dd = beat >= 7 and cw > bw
        ee = clause_e[L]["passes"]
        ok = a and bb and clause_c and dd and ee
        results.append({"label": L, "patience": patience, "delta": d,
                        "max_drawdown": m["max_drawdown"], "A": a, "B": bb,
                        "C": clause_c, "D": dd, "E": ee, "passes": ok,
                        "years_beaten": beat, "best_year": best,
                        "ex_best_year_self": cw - 1,
                        "ex_best_year_base": bw - 1})
        print("  {0:<14} {1:>+11.2f} {2:>12.4%} {3:>7} {4:>7} {5:>7} {6:>7} "
              "{7:>7} {8:>9}".format(
                  L, 100 * d, m["max_drawdown"],
                  "pass" if a else "FAIL", "pass" if bb else "FAIL",
                  "pass" if clause_c else "FAIL", "pass" if dd else "FAIL",
                  "pass" if ee else "FAIL", "pass" if ok else "FAIL"))
    print("\n  CLAUSE C: {0}  [{1}]".format("PASS" if clause_c else "FAIL",
                                            c_note))
    print("  deltas: {0}".format(["{0:+.2f}".format(100 * x) for x in deltas]))
    print("  CLAUSE D detail:")
    for r in results:
        print("    {0:<14} beats baseline in {1}/11 years | ex-best-year "
              "{2:+.2%} vs baseline {3:+.2%}".format(
                  r["label"], r["years_beaten"], r["ex_best_year_self"],
                  r["ex_best_year_base"]))

    survivors = [r for r in results if r["passes"]]
    print("\n  passing configurations: {0}".format(
        ", ".join(r["label"] for r in survivors) if survivors else "NONE"))

    # the seal's inconclusive test
    inconclusive = []
    for r in survivors:
        ce = clause_e[r["label"]]
        if ce.get("break_even_fill_rate", 0) > 0.55 * ce["modelled_fill_rate"]:
            inconclusive.append(r["label"])
        if any(v <= PENALTY * START
               for v in ce["haircut_sensitivity"].values()):
            if r["label"] not in inconclusive:
                inconclusive.append(r["label"])
    verdict = ("REJECTED" if not survivors
               else "INCONCLUSIVE" if len(inconclusive) == len(survivors)
               else "ACCEPTED (research_evidence)")
    print("\n  VERDICT: H-0011 {0}".format(verdict))
    if inconclusive:
        print("  INCONCLUSIVE on: {0}".format(", ".join(inconclusive)))
        print("  Reason: the pass does not survive the disclosed fill-rate")
        print("  and/or haircut uncertainty the seal required to be priced.")
    print("\n  NOTHING IS PROMOTED. Routing real exits as resting limits is")
    print("  a production change requiring its own registration, a new")
    print("  fingerprint and a restarted forward evaluation.")

    out = REPO / "docs" / "phase5" / "h0011-adjudication.json"
    out.write_text(json.dumps({
        "FORENSIC_NON_PROMOTIONAL": True,
        "seal": seal["seal"], "verdict": verdict,
        "inconclusive_on": inconclusive,
        "baseline": b, "spy_total": spy_total, "ceiling": CEILING,
        "penalty": PENALTY,
        "configurations": {L: store[L]["metrics"] for L, _p in ORDER},
        "exit_reasons": {L: store[L]["exit_reasons"] for L in labels},
        "fill_rates": {L: store[L]["fill_rate"] for L, _p in ORDER},
        "clause_e": clause_e, "clause_c": clause_c, "clause_c_note": c_note,
        "holding_cap_respected": cap_ok,
        "deltas_points": [100 * d for d in deltas],
        "per_configuration": results,
        "thirty_year_reads": 13,
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
