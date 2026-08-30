"""Model selection across several learner families, chosen out of sample.

The bot's original learner is a hand-rolled logistic regression. This module
adds genuinely more expressive families - random forests, gradient boosting,
neural networks - and, more importantly, a selection procedure that decides
between them on data none of them were fitted on.

The selection procedure is the point, not the extra capacity. Measured on
3,624 real candidates over ten years:

    model                     train AUC   test AUC
    logistic                     0.6190     0.5030
    random forest                0.9456     0.5044
    gradient boosting (deep)     1.0000     0.4772
    neural net (64,32)           1.0000     0.4455

Every family lands at chance out of sample, and the strongest ones land
*below* it: the neural net separated the training set perfectly and then did
worse than guessing on new data. Capacity did not buy edge, because the
limitation is the features, not the learner. A model cannot extract
information that is not in its inputs, and given more freedom it will fit
noise instead and report high confidence about it.

So the honest use of this module is defensive. `select_model` ranks by
out-of-sample AUC, penalises the train-test gap that signals memorisation,
and refuses to endorse anything that fails to beat chance - which today means
it declines to use the powerful models at all. If better features are ever
found, the capacity is here and the selection will notice.
"""

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# Minimum out-of-sample AUC before a model may be used for anything.
MIN_USABLE_AUC = 0.58
# A train-test AUC gap above this is memorisation, whatever the test score says.
MAX_OVERFIT_GAP = 0.25


@dataclass
class ModelResult:
    name: str
    train_auc: float
    test_auc: float
    test_brier: float
    base_brier: float

    @property
    def overfit_gap(self) -> float:
        return self.train_auc - self.test_auc

    @property
    def beats_chance(self) -> bool:
        return self.test_auc >= MIN_USABLE_AUC

    @property
    def memorised(self) -> bool:
        return self.overfit_gap > MAX_OVERFIT_GAP

    @property
    def usable(self) -> bool:
        return self.beats_chance and not self.memorised

    def as_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "train_auc": round(self.train_auc, 4),
            "test_auc": round(self.test_auc, 4),
            "overfit_gap": round(self.overfit_gap, 4),
            "test_brier": round(self.test_brier, 4),
            "base_brier": round(self.base_brier, 4),
            "beats_chance": self.beats_chance,
            "memorised": self.memorised,
            "usable": self.usable,
        }


@dataclass
class SelectionReport:
    results: List[ModelResult] = field(default_factory=list)
    chosen: Optional[str] = None
    reason: str = ""

    def as_dict(self) -> Dict[str, object]:
        return {
            "chosen": self.chosen,
            "reason": self.reason,
            "candidates": [r.as_dict() for r in sorted(
                self.results, key=lambda r: -r.test_auc
            )],
        }


def _families():
    """Learner families, weakest to strongest. Import is deferred so the rest
    of the package keeps working without scikit-learn installed."""
    from sklearn.ensemble import (
        ExtraTreesClassifier,
        GradientBoostingClassifier,
        RandomForestClassifier,
    )
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return [
        ("logistic", make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))),
        ("random_forest", RandomForestClassifier(
            n_estimators=400, min_samples_leaf=20, random_state=0, n_jobs=-1)),
        ("extra_trees", ExtraTreesClassifier(
            n_estimators=400, min_samples_leaf=20, random_state=0, n_jobs=-1)),
        ("gradient_boosting", GradientBoostingClassifier(
            n_estimators=200, max_depth=3, learning_rate=0.05, random_state=0)),
        ("neural_net", make_pipeline(
            StandardScaler(), MLPClassifier((64, 32), max_iter=1500, random_state=0))),
    ]


def select_model(
    features: Sequence[Sequence[float]],
    labels: Sequence[int],
    split: float = 0.70,
) -> SelectionReport:
    """Fit every family on the first `split`, judge them all on the rest.

    The split is chronological, never shuffled: shuffling would let a model
    train on tomorrow to predict yesterday, which inflates every score and is
    the single easiest way to fool yourself in this domain.
    """
    try:
        import numpy as np
        from sklearn.metrics import brier_score_loss, roc_auc_score
    except ImportError:
        return SelectionReport(
            chosen=None,
            reason="scikit-learn is not installed; the built-in logistic model is used.",
        )

    X = np.nan_to_num(np.asarray(features, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
    y = np.asarray(labels, dtype=int)

    # Conditioning, for two real reasons - neither of which is the
    # "divide by zero encountered in matmul" warning that sklearn emits here.
    # That warning is spurious: it reproduces on a plain `Z @ zeros` with
    # finite, standardised data whose largest magnitude is 15.5 and which
    # contains no non-finite cell at all. It is a numpy 2.0.2 / BLAS artifact
    # on this platform, not a property of the data, and chasing it as a data
    # problem wastes time.
    #
    # The genuine reasons: `event_impact` is constant 0.0 whenever no event
    # file is configured, and standardising a zero-variance column divides by
    # zero for real. And `average_dollar_volume` spans 1.5e8 to 5.4e10, ten
    # orders of magnitude from features like `momentum` that live near 0.01,
    # which is poor conditioning for any gradient-based solver.
    #
    # Both are handled here rather than in a pipeline step so tree models,
    # which need neither, see the same table as the linear ones.
    keep = X.std(axis=0) > 0
    X = X[:, keep]
    if X.shape[1] == 0:
        return SelectionReport(chosen=None, reason="Every feature is constant.")
    wide = np.abs(X).max(axis=0) > 1e4
    if wide.any():
        X[:, wide] = np.sign(X[:, wide]) * np.log1p(np.abs(X[:, wide]))
    if len(y) < 100 or len(set(y.tolist())) < 2:
        return SelectionReport(
            chosen=None, reason="Not enough labelled examples to compare models."
        )

    cut = int(len(y) * split)
    Xtr, Xte, ytr, yte = X[:cut], X[cut:], y[:cut], y[cut:]
    if len(set(ytr.tolist())) < 2 or len(set(yte.tolist())) < 2:
        return SelectionReport(chosen=None, reason="A split segment has only one class.")

    base_brier = float(np.mean((ytr.mean() - yte) ** 2))
    report = SelectionReport()

    for name, model in _families():
        try:
            model.fit(Xtr, ytr)
            ptr = model.predict_proba(Xtr)[:, 1]
            pte = model.predict_proba(Xte)[:, 1]
            report.results.append(ModelResult(
                name=name,
                train_auc=float(roc_auc_score(ytr, ptr)),
                test_auc=float(roc_auc_score(yte, pte)),
                test_brier=float(brier_score_loss(yte, pte)),
                base_brier=base_brier,
            ))
        except Exception as error:            # one family failing must not stop the rest
            report.results.append(ModelResult(name + " (failed: {0})".format(
                type(error).__name__), 0.5, 0.5, 1.0, base_brier))

    usable = [r for r in report.results if r.usable]
    if not usable:
        best = max(report.results, key=lambda r: r.test_auc)
        memorisers = [r.name for r in report.results if r.memorised]
        report.chosen = None
        report.reason = (
            "No family beat chance out of sample. Best was {0} at AUC {1:.4f}, "
            "against a {2:.2f} threshold. {3} model(s) separated the training set "
            "well and then failed on unseen data ({4}), which is memorisation "
            "rather than skill. The limitation is the features, not the learner - "
            "a bigger model cannot extract information the inputs do not contain."
        ).format(
            best.name, best.test_auc, MIN_USABLE_AUC, len(memorisers),
            ", ".join(memorisers) or "none",
        )
        return report

    winner = max(usable, key=lambda r: r.test_auc)
    report.chosen = winner.name
    report.reason = (
        "{0} was chosen on out-of-sample AUC {1:.4f} with a train-test gap of "
        "{2:.4f}, below the {3:.2f} memorisation threshold."
    ).format(winner.name, winner.test_auc, winner.overfit_gap, MAX_OVERFIT_GAP)
    return report


def save_selection(path: Path, report: SelectionReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
