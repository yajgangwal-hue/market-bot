"""Purged, embargoed, walk-forward evaluation. The only admissible kind here.

WHAT THE EXISTING TRAINER DOES, AND WHY IT IS NOT ENOUGH.
`live_model.train_live_model` sorts by time - which is right - then cuts at
75%, fits on the first part, scores on the second, and then **refits on
everything** and ships that model carrying the earlier score. Three separate
problems, and they compound:

  NO PURGE      a mean-reversion trade is held up to 20 sessions. An example
                entered just before the cut resolves *after* it, so its label
                is written by prices that sit inside the test period. Train
                and test share outcomes.

  SCORE BELONGS TO A DIFFERENT MODEL  the number reported is for the model
                fit on 75% of the data. That model is then thrown away. The
                artifact that gets deployed was fit on 100%, including every
                row it was scored against, and no out-of-sample number
                describes it at all.

  ONE SPLIT     a single cut means one regime in test. It cannot distinguish
                "works" from "worked once".

This module fixes all three by construction. Folds walk forward, training
always ends before testing begins, the overlap window is purged, an embargo
follows it, and `evaluate` scores the model fit on that fold's training rows
only - never a refit on everything.

THE HORIZON IS NOT A FREE PARAMETER. It is the strategy's own holding cap,
`MeanReversionConfig.max_holding_bars`, for the same reason the forward
evaluation's embargo is: that is how long an example's outcome takes to
resolve, so that is how far contamination reaches.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional, Sequence, Tuple


def horizon_sessions() -> int:
    """The information horizon, read from the rule rather than chosen."""
    from ..mean_reversion import MeanReversionConfig
    return MeanReversionConfig().max_holding_bars


def example_date(row: Dict) -> Optional[date]:
    """The decision date of one training row, from whichever field carries it."""
    raw = row.get("at") or row.get("d") or ""
    text = str(raw)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


@dataclass
class Fold:
    """One walk-forward step. Every boundary is a date, not an index."""
    index: int
    train_start: date
    train_end: date        # exclusive
    test_start: date       # exclusive of the embargo already applied
    test_end: date         # exclusive
    train: List[Dict] = field(default_factory=list)
    test: List[Dict] = field(default_factory=list)
    purged: int = 0
    embargoed: int = 0

    def as_dict(self) -> Dict[str, object]:
        return {
            "fold": self.index,
            "train": "{0}..{1}".format(self.train_start, self.train_end),
            "test": "{0}..{1}".format(self.test_start, self.test_end),
            "n_train": len(self.train), "n_test": len(self.test),
            "purged": self.purged, "embargoed": self.embargoed,
        }


def make_folds(rows: Sequence[Dict],
               n_folds: int = 5,
               horizon_days: Optional[int] = None,
               expanding: bool = True,
               minimum_train: int = 200,
               minimum_test: int = 40) -> List[Fold]:
    """Split a dated corpus into purged, embargoed, forward-walking folds.

    `horizon_days` is the calendar gap that stands for the strategy's
    session horizon. Sessions are not calendar days, so the conversion is
    deliberately generous - 20 sessions is about 28 calendar days, and
    erring long costs training rows while erring short leaks outcomes.

    `expanding` grows the training set from the start of the record;
    False makes it a rolling window of the previous fold's length. Both
    are offered because the brief asks for both to be TESTED, not because
    one is assumed better.
    """
    horizon = timedelta(days=horizon_days if horizon_days is not None
                        else int(round(horizon_sessions() * 1.4)))
    dated = sorted(((example_date(r), r) for r in rows if example_date(r)),
                   key=lambda pair: pair[0])
    if len(dated) < minimum_train + minimum_test:
        return []

    days = [d for d, _ in dated]
    first, last = days[0], days[-1]
    # Cut the TEST period into equal spans of time, not equal counts of
    # examples: equal counts would make a busy year and a quiet year the
    # same size and hide the regime difference the folds exist to expose.
    start_testing = days[max(minimum_train - 1, int(len(days) * 0.4))]
    span = (last - start_testing) / max(1, n_folds)

    folds: List[Fold] = []
    for i in range(n_folds):
        test_from = start_testing + span * i
        test_to = start_testing + span * (i + 1) if i < n_folds - 1 else \
            last + timedelta(days=1)
        train_end = test_from - horizon          # PURGE: the overlap window
        train_start = first if expanding else max(
            first, train_end - (test_from - first) / 2)

        train = [r for d, r in dated if train_start <= d < train_end]
        purged = sum(1 for d, _ in dated if train_end <= d < test_from)
        # EMBARGO: the first horizon of the test period is discarded too,
        # because an example there was decided while the last training
        # example was still resolving.
        embargo_until = test_from + horizon
        test = [r for d, r in dated if embargo_until <= d < test_to]
        embargoed = sum(1 for d, _ in dated if test_from <= d < embargo_until)

        if len(train) < minimum_train or len(test) < minimum_test:
            continue
        folds.append(Fold(index=len(folds), train_start=train_start,
                          train_end=train_end, test_start=embargo_until,
                          test_end=test_to, train=train, test=test,
                          purged=purged, embargoed=embargoed))
    return folds


def check_no_overlap(fold: Fold) -> List[str]:
    """Assert the properties the split claims. Returns violations, not a bool.

    Called by the tests and by `evaluate`, because a split that silently
    stopped purging would produce exactly the optimistic numbers this
    module exists to prevent.
    """
    problems = []
    train_days = [example_date(r) for r in fold.train]
    test_days = [example_date(r) for r in fold.test]
    if train_days and test_days:
        if max(train_days) >= min(test_days):
            problems.append("a training example is dated on or after the "
                            "first test example")
        gap = (min(test_days) - max(train_days)).days
        if gap < 1:
            problems.append("train and test touch: gap {0} days".format(gap))
    ids = {id(r) for r in fold.train}
    if any(id(r) in ids for r in fold.test):
        problems.append("the same row object appears in train and test")
    return problems


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

@dataclass
class FoldResult:
    fold: int
    n_train: int
    n_test: int
    train_auc: Optional[float]
    test_auc: Optional[float]
    test_brier: Optional[float]
    base_rate: float
    test_start: str
    test_end: str

    @property
    def gap(self) -> Optional[float]:
        if self.train_auc is None or self.test_auc is None:
            return None
        return self.train_auc - self.test_auc

    def as_dict(self) -> Dict[str, object]:
        out = dict(self.__dict__)
        out["gap"] = self.gap
        return {k: (round(v, 6) if isinstance(v, float) else v)
                for k, v in out.items()}


def _auc(y_true, y_score) -> Optional[float]:
    from sklearn.metrics import roc_auc_score
    if len(set(int(v) for v in y_true)) < 2:
        return None
    return float(roc_auc_score(y_true, y_score))


def default_fit(features: Sequence[str]):
    """The estimator the live trainer uses, so the audit describes IT.

    Deliberately not a better model. The question here is whether the
    SHIPPED configuration has out-of-sample value; swapping in a stronger
    learner would answer a different question and quietly become the
    parameter search the governance plan forbids.
    """
    def fit(train_rows):
        import numpy as np
        from sklearn.ensemble import HistGradientBoostingClassifier
        X = np.nan_to_num(np.array(
            [[float(r["f"].get(k, 0.0)) for k in features] for r in train_rows],
            float))
        y = np.array([int(r["label"]) for r in train_rows], int)
        if len(set(y.tolist())) < 2:
            return None
        model = HistGradientBoostingClassifier(
            max_iter=300, max_depth=4, learning_rate=0.05, random_state=0)
        model.fit(X, y)
        return model
    return fit


def _matrix(rows, features):
    import numpy as np
    return np.nan_to_num(np.array(
        [[float(r["f"].get(k, 0.0)) for k in features] for r in rows], float))


def evaluate(rows: Sequence[Dict],
             features: Sequence[str],
             n_folds: int = 5,
             expanding: bool = True,
             fit: Optional[Callable] = None,
             shuffle_labels: bool = False,
             seed: int = 0) -> Dict[str, object]:
    """Walk forward and report each fold honestly.

    `shuffle_labels` is the control, not an option to use in anger: with
    labels permuted WITHIN the training fold only, a sound pipeline must
    score about 0.5 out of sample. Anything materially above that is
    evidence of leakage in the split rather than skill in the model.
    """
    import numpy as np
    fit = fit or default_fit(features)
    folds = make_folds(rows, n_folds=n_folds, expanding=expanding)
    results: List[FoldResult] = []
    violations: List[str] = []
    rng = np.random.default_rng(seed)

    for fold in folds:
        violations.extend("fold {0}: {1}".format(fold.index, p)
                          for p in check_no_overlap(fold))
        train_rows = list(fold.train)
        if shuffle_labels:
            labels = [int(r["label"]) for r in train_rows]
            rng.shuffle(labels)
            train_rows = [dict(r, label=l) for r, l in zip(train_rows, labels)]

        model = fit(train_rows)
        if model is None:
            continue
        x_train, x_test = _matrix(train_rows, features), _matrix(fold.test, features)
        y_train = [int(r["label"]) for r in train_rows]
        y_test = [int(r["label"]) for r in fold.test]
        p_train = model.predict_proba(x_train)[:, 1]
        p_test = model.predict_proba(x_test)[:, 1]
        brier = (float(np.mean((p_test - np.array(y_test, float)) ** 2))
                 if y_test else None)
        results.append(FoldResult(
            fold=fold.index, n_train=len(train_rows), n_test=len(fold.test),
            train_auc=_auc(y_train, p_train), test_auc=_auc(y_test, p_test),
            test_brier=brier,
            base_rate=(sum(y_test) / len(y_test)) if y_test else 0.0,
            test_start=fold.test_start.isoformat(),
            test_end=fold.test_end.isoformat()))

    scored = [r for r in results if r.test_auc is not None]
    mean_test = (sum(r.test_auc for r in scored) / len(scored)) if scored else None
    mean_train = (sum(r.train_auc for r in scored if r.train_auc is not None)
                  / len(scored)) if scored else None
    return {
        "folds": [f.as_dict() for f in folds],
        "results": [r.as_dict() for r in results],
        "n_folds_scored": len(scored),
        "mean_train_auc": mean_train,
        "mean_test_auc": mean_test,
        "mean_gap": (mean_train - mean_test)
                    if (mean_train is not None and mean_test is not None) else None,
        "worst_test_auc": min((r.test_auc for r in scored), default=None),
        "best_test_auc": max((r.test_auc for r in scored), default=None),
        "folds_above_half": sum(1 for r in scored if r.test_auc > 0.5),
        "shuffled_control": shuffle_labels,
        "split_violations": violations,
        "horizon_sessions": horizon_sessions(),
    }
