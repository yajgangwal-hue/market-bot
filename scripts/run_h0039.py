"""H-0039 runner: trend following on futures-tracking funds, sealed.

Refuses unless H-0039's registration matches this code and configuration
(`prereg.verify`) and the dataset verifies byte for byte
(`research_gate.verify_dataset`); loads bars only from the path that returns.
Writes docs/phase5/h0039-results.json, appends one dataset-use row, and
prints the verdict.

`evaluate()` is pure and is exercised end to end on synthetic data by
tests/test_h0039_trend.py, so the verdict step has run before the sealed run.

Usage:  python scripts/run_h0039.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import h0039_trend as engine  # noqa: E402

RESULTS = REPO / "docs" / "phase5" / "h0039-results.json"
DATASET_USES = REPO / "docs" / "dataset-uses.jsonl"


def blocks(r, rf, dates, split):
    first, second = engine.split_rows(dates, split)
    take = lambda rows: engine.metrics(r[rows], rf[rows], [dates[i] for i in rows])
    return {"full": engine.metrics(r, rf, dates), "half1": take(first), "half2": take(second)}


def evaluate(dates, symbols, returns, rf, split, resamples, seed):
    """Every number the registration names, then the sealed verdict."""
    primary = engine.run(dates, symbols, returns, rf)
    days, rf_eval = primary["dates"], primary["rf"]
    first_exec = len(dates) - len(days)
    spy = returns[first_exec:, symbols.index(engine.BENCHMARK)]
    years = len(days) / engine.TRADING_DAYS

    results = {"window": {"first_decision": dates[first_exec - 1].isoformat(),
                          "first_execution": days[0].isoformat(), "last": days[-1].isoformat(),
                          "sessions": len(days), "split": split.isoformat()}}
    results["primary"] = blocks(primary["account"], rf_eval, days, split)
    results["primary"]["bootstrap_p"] = engine.stationary_bootstrap_p(
        primary["account"] - rf_eval, resamples=resamples, seed=seed)
    double = engine.run(dates, symbols, returns, rf, cost_multiplier=2.0)
    results["double_cost"] = blocks(double["account"], rf_eval, days, split)
    results["overlay"] = blocks(engine.overlay(spy, rf_eval, primary["futures_pnl"]), rf_eval,
                                days, split)
    results["spy"] = blocks(spy, rf_eval, days, split)

    # Secondary: reported, cannot overturn the primary.
    twelve = engine.run(dates, symbols, returns, rf, lookbacks=(252,))
    weekly = engine.run(dates, symbols, returns, rf, frequency="weekly")
    results["secondary"] = {
        "twelve_month_only": blocks(twelve["account"], rf_eval, days, split),
        "weekly_rebalance": blocks(weekly["account"], rf_eval, days, split),
        "overlay_100_spy": blocks(engine.overlay(spy, rf_eval, primary["futures_pnl"], 1.0),
                                  rf_eval, days, split),
        "bills": blocks(rf_eval, rf_eval, days, split),
    }
    classes = {}
    for j, symbol in enumerate(symbols):
        cls = engine.MARKETS[symbol][0]
        classes[cls] = classes.get(cls, 0.0) + float(primary["contribution"][:, j].sum())
    results["descriptive"] = {
        "correlation_with_spy": float(np.corrcoef(primary["account"], spy)[0, 1]),
        "pnl_by_class_per_year": {k: v / years for k, v in sorted(classes.items())},
        "gross_leverage": {"mean": float(primary["gross"].mean()),
                           "max": float(primary["gross"].max())},
        "turnover_per_year": float(primary["turnover"].sum() / years),
        "costs_per_year": float(primary["costs"].sum() / years),
        "decisions": primary["decisions"],
        "decisions_where_the_gross_cap_bound": primary["decisions_capped"],
    }
    # Reported, never edited: the data are used exactly as received.
    moves = {}
    for j, symbol in enumerate(symbols):
        column = returns[:, j]
        k = int(np.argmax(np.abs(column)))
        moves[symbol] = {"largest_move": float(column[k]), "on": dates[k].isoformat(),
                         "moves_over_20pct": int((np.abs(column) > 0.20).sum())}
    results["data_quality"] = {"calendar_first": dates[0].isoformat(),
                               "calendar_last": dates[-1].isoformat(),
                               "sessions": len(dates), "by_symbol": moves}
    results["decision"] = engine.decide(results)
    return results


def main():
    from event_aware_trader.modelgov import prereg
    import research_gate
    import h0039_spec as spec

    try:
        sealed = prereg.verify(spec.HYPOTHESIS_ID, spec.hypothesis())
    except prereg.RegistrationError as error:
        print("REFUSED: " + str(error))
        return 2
    problems = research_gate.check_registration(sealed)
    if problems:
        print("REFUSED: dataset gate: " + "; ".join(problems))
        return 2
    directory = research_gate.verify_dataset(spec.DATASET["id"], spec.DATASET["sha256"])
    closes, irx = engine.load(directory)
    dates, symbols, returns, rf = engine.build_panel(closes, irx, spec.END)
    results = evaluate(dates, symbols, returns, rf, spec.SPLIT, spec.BOOTSTRAP["resamples"],
                       spec.BOOTSTRAP["seed"])
    results["registration"] = {"hypothesis": spec.HYPOTHESIS_ID, "seal": sealed["seal"],
                               "registered_at": sealed["registered_at"]}
    results["dataset"] = spec.DATASET
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(results, indent=1, sort_keys=True), encoding="utf-8")
    with DATASET_USES.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "at": datetime.now(timezone.utc).isoformat(), "dataset": spec.DATASET["id"],
            "kind": "dataset_use", "note": "H-0039 sealed run", "purpose": "rejection_test",
            "symbols": len(symbols) + 1}) + "\n")

    p, o, s = results["primary"], results["overlay"], results["spy"]
    print("window {first_execution} .. {last} ({sessions} sessions)".format(**results["window"]))
    for label, block in (("trend (stand-alone)", p), ("80% SPY + trend", o), ("SPY", s),
                         ("trend, double costs", results["double_cost"])):
        f = block["full"]
        print("{0:22} CAGR {1:+7.2%}  Sharpe {2:5.2f}  vol {3:6.2%}  worst drawdown {4:+7.2%}"
              "  halves {5:+6.2%} / {6:+6.2%}".format(
                  label, f["cagr"], f["sharpe"], f["volatility"], f["max_drawdown"],
                  block["half1"]["cagr"], block["half2"]["cagr"]))
    print("bootstrap p {0:.4f}".format(p["bootstrap_p"]))
    print("gates", results["decision"]["gates"])
    print("VERDICT:", results["decision"]["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
