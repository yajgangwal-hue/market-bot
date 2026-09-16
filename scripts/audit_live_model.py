"""Re-measure the deployed live model under a split that does not leak.

The shipped trainer reports an AUC measured on a single 75/25 cut with no
purge, and then refits on ALL the data and ships that model carrying the
earlier number. This runs the same estimator and the same corpus through
purged, embargoed, walk-forward folds, scores only the model that would
actually have been deployed at each point, and runs a shuffled-label
control that must stay near chance.

Read-only with respect to production: it trains models in memory, writes
no model file, and changes nothing the live loop reads. The lineage row it
appends is a record, not a deployable artifact.

  python scripts/audit_live_model.py
  python scripts/audit_live_model.py --rolling   # rolling instead of expanding
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.modelgov import lineage, trust, walkforward  # noqa: E402
from event_aware_trader.live_model import (                          # noqa: E402
    LIVE_FEATURES, load_live_model, load_training)


def main():
    expanding = "--rolling" not in sys.argv
    rows = load_training()
    if not rows:
        print("no training rows on file")
        return 1

    dated = [r for r in rows if walkforward.example_date(r)]
    print("corpus: {0} rows, {1} dated, {2} .. {3}".format(
        len(rows), len(dated),
        min(walkforward.example_date(r) for r in dated),
        max(walkforward.example_date(r) for r in dated)))
    print("window: {0}".format("expanding" if expanding else "rolling"))
    print("horizon: {0} sessions, purged and embargoed at every boundary"
          .format(walkforward.horizon_sessions()))

    from event_aware_trader.autotrade import AutoTradeConfig
    live, _est = load_live_model(AutoTradeConfig().live_model_file)
    if live is not None:
        print("\nSHIPPED MODEL CLAIMS: status={0} test_auc={1} n={2}".format(
            live.status, live.test_auc, live.n_examples))
        print("  measured on one 75/25 cut, no purge, and the deployed "
              "artifact was then refit on 100% of that data.")

    print("\nWALK-FORWARD (purged, embargoed, no refit on test)")
    walk = walkforward.evaluate(rows, LIVE_FEATURES, n_folds=5,
                                expanding=expanding)
    print("  {0:<5} {1:>7} {2:>7} {3:>10} {4:>10} {5:>8} {6:>8}  {7}".format(
        "fold", "train", "test", "train AUC", "test AUC", "gap", "brier",
        "test period"))
    for r in walk["results"]:
        print("  {0:<5} {1:>7} {2:>7} {3:>10} {4:>10} {5:>8} {6:>8}  {7}..{8}"
              .format(r["fold"], r["n_train"], r["n_test"],
                      _f(r["train_auc"]), _f(r["test_auc"]), _f(r["gap"]),
                      _f(r["test_brier"]), r["test_start"], r["test_end"]))
    print("  purged/embargoed per fold: {0}".format(
        [(f["purged"], f["embargoed"]) for f in walk["folds"]]))
    print("  mean train {0} | mean test {1} | mean gap {2}".format(
        _f(walk["mean_train_auc"]), _f(walk["mean_test_auc"]),
        _f(walk["mean_gap"])))

    print("\nSHUFFLED-LABEL CONTROL (must stay near 0.5)")
    control = walkforward.evaluate(rows, LIVE_FEATURES, n_folds=5,
                                   expanding=expanding, shuffle_labels=True)
    print("  mean test AUC on permuted labels: {0}".format(
        _f(control["mean_test_auc"])))

    report = trust.assess(walk, shuffled=control)
    print("\n" + report.explain())

    print("\nABSTENTION - can the model decline?")
    curve = _abstention(rows, walk)
    if curve:
        print("  {0:>6} {1:>10} {2:>7} {3:>10} {4:>10}".format(
            "band", "coverage", "n", "accuracy", "lift"))
        for row in curve:
            print("  {0:>6} {1:>10} {2:>7} {3:>10} {4:>10}".format(
                row["band"],
                "{0:.1%}".format(row["coverage"]),
                row["n"],
                "-" if row["accuracy"] is None else "{0:.3f}".format(row["accuracy"]),
                "-" if row.get("lift_over_majority") is None
                else "{0:+.3f}".format(row["lift_over_majority"])))

    entry = lineage.ModelRecord(
        trained_at=lineage.datetime.now(lineage.timezone.utc).isoformat(),
        information_cutoff=max(walkforward.example_date(r)
                               for r in dated).isoformat(),
        train_interval=walk["folds"][0]["train"] if walk["folds"] else "n/a",
        validate_interval="none - folds serve as validation",
        test_interval="; ".join(f["test"] for f in walk["folds"]),
        dataset_fingerprint=lineage.dataset_fingerprint(rows),
        dataset_rows=len(rows),
        feature_version=lineage.FEATURE_VERSION,
        features=list(LIVE_FEATURES),
        code_commit=lineage.git_commit(),
        hyperparameters={"estimator": "HistGradientBoostingClassifier",
                         "max_iter": 300, "max_depth": 4,
                         "learning_rate": 0.05, "random_state": 0,
                         "window": "expanding" if expanding else "rolling"},
        evaluation={"walk_forward": {k: walk[k] for k in
                                     ("mean_train_auc", "mean_test_auc",
                                      "mean_gap", "worst_test_auc",
                                      "best_test_auc", "n_folds_scored",
                                      "folds_above_half")},
                    "shuffled_control_auc": control["mean_test_auc"],
                    "conditions_failed": [c.name for c in report.failures]},
        trust_status=report.status,
        notes=("Re-audit of the SHIPPED live model configuration under a "
               "purged, embargoed walk-forward. Not a new model and not a "
               "deployable artifact."))
    try:
        row = lineage.record(entry)
        print("\nlineage: recorded {0} ({1})".format(
            row["payload"]["model_id"], row["payload"]["trust_status"]))
    except ValueError as error:
        print("\nlineage: {0}".format(error))

    print("\nVERDICT: the learned component is {0}.".format(report.status))
    if report.status != trust.TRUSTED:
        print("  The verified baseline stands. No model change is proposed.")
    return 0


def _abstention(rows, walk):
    """Probabilities from the last fold only, which is the most recent OOS."""
    import numpy as np
    folds = walkforward.make_folds(rows, n_folds=5)
    if not folds:
        return []
    fold = folds[-1]
    model = walkforward.default_fit(LIVE_FEATURES)(fold.train)
    if model is None:
        return []
    x = walkforward._matrix(fold.test, LIVE_FEATURES)
    p = model.predict_proba(x)[:, 1]
    y = [int(r["label"]) for r in fold.test]
    return trust.abstention_curve(list(p), y)


def _f(value):
    return "-" if value is None else "{0:.4f}".format(value)


if __name__ == "__main__":
    raise SystemExit(main())
