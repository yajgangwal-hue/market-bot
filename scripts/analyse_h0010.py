"""Adjudicate H-0010 against the five sealed clauses. Nothing chosen here.

Clause E is the one this experiment was built around: a take profit is
a resting limit and pays no 0.652% rule-exit haircut, so the gain must
survive attributing that advantage separately.
"""

import json
import sys
from pathlib import Path
from statistics import fmean

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.modelgov import prereg                  # noqa: E402
from forensics_regime import load                                # noqa: E402

CACHE = REPO / "docs" / "phase5" / "h0010-cache.json"
PENALTY = 0.02
CEILING = 0.142806
DOMINANCE = 2.5
START = 100_000.0
ORDER = [("A stop0.917", 0.917), ("B stop1.25", 1.25), ("C stop1.75", 1.75)]


def main():
    store = json.loads(CACHE.read_text(encoding="utf-8"))
    seal = [p for p in prereg.load() if p["hypothesis_id"] == "H-0010"][0]
    b = store["BASELINE"]["metrics"]
    series = load()
    spy = series["SPY"]
    spy_total = spy[-1].close / spy[0].close - 1.0

    print("H-0010 seal {0}".format(seal["seal"][:16]))
    print("baseline  total {0:+.4%}  maxDD {1:.4%}  trades {2}".format(
        b["total_return"], b["max_drawdown"], b["trades"]))
    print("clause A needs > {0:+.4%} | clause B ceiling {1:.4%}".format(
        b["total_return"] + PENALTY, CEILING))
    print("SPY price-only {0:+.4%}\n".format(spy_total))

    labels = ["BASELINE"] + [x for x, _m in ORDER]
    print("=" * 84)
    print("1. ECONOMIC PERFORMANCE")
    print("=" * 84)
    rows = [("total return", "total_return", "{0:+.2%}"),
            ("CAGR", "cagr", "{0:+.2%}"),
            ("annualised volatility", "annualised_volatility", "{0:.2%}"),
            ("Sharpe", "sharpe", "{0:.4f}"),
            ("Sortino", "sortino", "{0:.4f}"),
            ("max drawdown", "max_drawdown", "{0:.4%}"),
            ("Calmar", "calmar", "{0:.4f}"),
            ("trades", "trades", "{0}"),
            ("win rate", "win_rate", "{0:.2%}"),
            ("profit factor", "profit_factor", "{0:.3f}"),
            ("avg hold (days)", "average_hold_days", "{0:.2f}"),
            ("stop rate", "stop_rate", "{0:.2%}"),
            ("turnover", "turnover", "{0:.2f}"),
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
    print("  {0:<24}".format("take-profit exits") + "".join(
        "{0:>15}".format(store[L].get("take_profit_exits", 0))
        for L in labels))

    print("\n  exit-reason mix")
    for L in labels:
        print("    {0:<14} {1}".format(L, store[L]["exit_reasons"]))

    print("\n  year by year")
    years = sorted(b["by_year"])
    print("  {0:>6}".format("year") + "".join("{0:>15}".format(x[:15])
                                              for x in labels))
    for y in years:
        print("  {0:>6}".format(y) + "".join(
            "{0:>15}".format("{0:.2%}".format(
                store[L]["metrics"]["by_year"].get(y, 0.0)))
            for L in labels))

    # ---- clause E --------------------------------------------------------
    print("\n" + "=" * 84)
    print("2. CLAUSE E - IS THE GAIN JUST AVOIDED HAIRCUT?")
    print("=" * 84)
    print("  A take profit is a resting LIMIT and pays no 0.652% rule-exit")
    print("  haircut; 'reverted' and 'time_exit' do. For each configuration:")
    print("  what those take-profit exits would have paid as rule exits,")
    print("  against the actual dollar gain over the baseline.\n")
    base_final = START * (1.0 + b["total_return"])
    print("  {0:<14} {1:>14} {2:>16} {3:>16} {4:>10}".format(
        "config", "gain vs base", "haircut avoided", "gain NET of it",
        "ratio"))
    clause_e = {}
    for L, _m in ORDER:
        m = store[L]["metrics"]
        gain = START * (1.0 + m["total_return"]) - base_final
        avoided = store[L]["haircut_avoided_dollars"]
        net = gain - avoided
        clause_e[L] = {"gain": gain, "avoided": avoided, "net": net,
                       "passes": net > PENALTY * START}
        print("  {0:<14} {1:>14,.0f} {2:>16,.0f} {3:>16,.0f} {4:>10}".format(
            L, gain, avoided, net,
            "{0:.2f}x".format(avoided / gain) if gain > 0 else "n/a"))
    print("\n  clause E needs the NET column above {0:,.0f} "
          "(the 2-point penalty)".format(PENALTY * START))

    # ---- adjudication ----------------------------------------------------
    print("\n" + "=" * 84)
    print("3. ADJUDICATION")
    print("=" * 84)
    deltas = [store[L]["metrics"]["total_return"] - b["total_return"]
              for L, _m in ORDER]
    positive = sorted([d for d in deltas if d > 0], reverse=True)
    if len(positive) >= 2:
        clause_c = positive[0] <= DOMINANCE * positive[1]
        c_note = "largest {0:+.2f} vs second {1:+.2f} pts".format(
            100 * positive[0], 100 * positive[1])
    elif len(positive) == 1:
        clause_c = False
        c_note = "only ONE positive delta - a spike by definition"
    else:
        clause_c = False
        c_note = "no positive delta"

    print("  {0:<14} {1:>11} {2:>12} {3:>7} {4:>7} {5:>7} {6:>7} {7:>7} "
          "{8:>8}".format("config", "delta pts", "maxDD", "A", "B", "C",
                          "D", "E", "verdict"))
    results = []
    for (L, mult), d in zip(ORDER, deltas):
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
        results.append({"label": L, "stop_multiple": mult, "delta": d,
                        "max_drawdown": m["max_drawdown"], "A": a, "B": bb,
                        "C": clause_c, "D": dd, "E": ee, "passes": ok,
                        "years_beaten": beat, "best_year": best,
                        "ex_best_year_self": cw - 1, "ex_best_year_base": bw - 1})
        print("  {0:<14} {1:>+11.2f} {2:>12.4%} {3:>7} {4:>7} {5:>7} {6:>7} "
              "{7:>7} {8:>8}".format(
                  L, 100 * d, m["max_drawdown"],
                  "pass" if a else "FAIL", "pass" if bb else "FAIL",
                  "pass" if clause_c else "FAIL", "pass" if dd else "FAIL",
                  "pass" if ee else "FAIL", "pass" if ok else "FAIL"))
    print("\n  CLAUSE C (gradient, not spike): {0}  [{1}]".format(
        "PASS" if clause_c else "FAIL", c_note))
    print("  deltas across the gradient: {0}".format(
        ["{0:+.2f}".format(100 * x) for x in deltas]))
    print("\n  CLAUSE B: every configuration's drawdown against the "
          "{0:.4%} ceiling".format(CEILING))
    for r in results:
        print("    {0:<14} {1:.4%} -> {2}".format(
            r["label"], abs(r["max_drawdown"]),
            "within" if r["B"] else "BREACH by {0:.2f} pts".format(
                100 * (abs(r["max_drawdown"]) - CEILING))))

    survivors = [r for r in results if r["passes"]]
    verdict = "ACCEPTED" if survivors else "REJECTED"
    print("\n  VERDICT: H-0010 {0}".format(verdict))
    if not survivors:
        print("  The frozen stop (2.5 x ATR) and the absence of a take")
        print("  profit BOTH STAND, UNCHANGED.")

    out = REPO / "docs" / "phase5" / "h0010-adjudication.json"
    out.write_text(json.dumps({
        "FORENSIC_NON_PROMOTIONAL": True,
        "seal": seal["seal"], "verdict": verdict,
        "baseline": b, "spy_total": spy_total, "ceiling": CEILING,
        "penalty": PENALTY,
        "configurations": {L: store[L]["metrics"] for L, _m in ORDER},
        "exit_reasons": {L: store[L]["exit_reasons"] for L in labels},
        "clause_e": clause_e, "clause_c": clause_c, "clause_c_note": c_note,
        "deltas_points": [100 * d for d in deltas],
        "per_configuration": results,
        "thirty_year_reads": 13,
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
