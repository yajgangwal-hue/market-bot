"""Detect manufactured accuracy before anyone trades on it.

An unusually good score in this domain is nearly always a bug, not a
discovery. Published equity-return models live around 0.52-0.58 AUC, and the
most successful quantitative fund on record is reported to be right barely
over half the time. So a 0.90 is not an achievement to celebrate; it is a
symptom to diagnose.

Measured on this project's own 266,954-example dataset, here is how easy the
impressive numbers are to produce:

    honest chronological split + embargo      0.5588
    reporting the TRAIN score as the result   0.7353
    a SHUFFLED split, so it trains on future  0.6885
    one noisy feature built from the outcome  0.8070
    the outcome included directly             1.0000

Only the first is real. The last has a 100% win rate on the held-out set and
is worth exactly nothing, because the feature carrying it is the answer, and
on the morning you would actually trade, that column is empty.

`audit_for_leakage` runs the checks that separate these cases. It is meant to
be run on any model before it is believed, including one's own.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# Above this, an out-of-sample score in this domain is evidence of a bug.
IMPLAUSIBLE_AUC = 0.75
# A single feature that alone separates outcomes this well is the outcome.
SINGLE_FEATURE_ALARM = 0.80
# Train minus test beyond this is memorisation.
OVERFIT_GAP_ALARM = 0.25
# Chronological worse than shuffled by this much means order carries meaning
# the shuffle destroyed - i.e. the shuffled score was borrowing the future.
SHUFFLE_ADVANTAGE_ALARM = 0.05


@dataclass
class LeakageFinding:
    check: str
    triggered: bool
    detail: str
    severity: str = "high"


@dataclass
class LeakageReport:
    findings: List[LeakageFinding] = field(default_factory=list)
    test_auc: float = 0.5

    @property
    def triggered(self) -> List[LeakageFinding]:
        return [f for f in self.findings if f.triggered]

    @property
    def trustworthy(self) -> bool:
        return not self.triggered

    def as_dict(self) -> Dict[str, object]:
        return {
            "test_auc": round(self.test_auc, 4),
            "trustworthy": self.trustworthy,
            "alarms": [f.check for f in self.triggered],
            "checks": [
                {"check": f.check, "triggered": f.triggered,
                 "severity": f.severity, "detail": f.detail}
                for f in self.findings
            ],
            "note": (
                "A high score here is a reason to look for a bug, not a reason to "
                "trade. Honest models in this domain sit near 0.55."
            ),
        }


def audit_for_leakage(
    features: Sequence[Sequence[float]],
    labels: Sequence[int],
    dates: Sequence,
    feature_names: Optional[Sequence[str]] = None,
    split: float = 0.70,
    embargo_days: int = 30,
) -> LeakageReport:
    """Run every check that distinguishes a real score from a manufactured one."""
    try:
        import numpy as np
        from datetime import timedelta
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.metrics import roc_auc_score
        from sklearn.model_selection import train_test_split
    except ImportError:
        return LeakageReport(findings=[LeakageFinding(
            "dependencies", False, "scikit-learn not installed; audit skipped.", "low")])

    X = np.nan_to_num(np.asarray(features, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
    y = np.asarray(labels, dtype=int)
    D = np.asarray(dates)
    names = list(feature_names) if feature_names else ["f%d" % i for i in range(X.shape[1])]
    report = LeakageReport()

    if len(set(y.tolist())) < 2 or len(y) < 200:
        report.findings.append(LeakageFinding(
            "sample", False, "Too few examples or only one class to audit.", "low"))
        return report

    unique_dates = sorted(set(D.tolist()))
    cut = unique_dates[int(len(unique_dates) * split)]
    tr = D < cut
    te = D >= (cut + timedelta(days=embargo_days)) if hasattr(cut, "toordinal") else D >= cut
    if tr.sum() < 100 or te.sum() < 100:
        report.findings.append(LeakageFinding("sample", False, "Split leaves too little data.", "low"))
        return report

    def fit_auc(Xa, ya, Xb, yb):
        m = HistGradientBoostingClassifier(
            max_iter=200, max_depth=4, learning_rate=0.05, random_state=0)
        m.fit(Xa, ya)
        return roc_auc_score(yb, m.predict_proba(Xb)[:, 1]), m

    test_auc, model = fit_auc(X[tr], y[tr], X[te], y[te])
    report.test_auc = float(test_auc)
    train_auc = float(roc_auc_score(y[tr], model.predict_proba(X[tr])[:, 1]))

    # 1. an implausible headline score
    report.findings.append(LeakageFinding(
        "implausible_score", test_auc > IMPLAUSIBLE_AUC,
        "Out-of-sample AUC {0:.4f}. Above {1:.2f} in this domain is evidence of a "
        "bug, not of skill - honest models sit near 0.55.".format(test_auc, IMPLAUSIBLE_AUC),
    ))

    # 2. memorisation
    report.findings.append(LeakageFinding(
        "memorisation", (train_auc - test_auc) > OVERFIT_GAP_ALARM,
        "Train {0:.4f} against test {1:.4f}, a gap of {2:.4f}.".format(
            train_auc, test_auc, train_auc - test_auc),
        severity="medium",
    ))

    # 3. any single feature that alone separates the outcome IS the outcome
    worst: Tuple[str, float] = ("", 0.5)
    for i, name in enumerate(names):
        column = X[:, i]
        if len(set(column.tolist())) < 2:
            continue
        try:
            alone = roc_auc_score(y, column)
        except ValueError:
            continue
        alone = max(alone, 1.0 - alone)          # direction does not matter
        if alone > worst[1]:
            worst = (name, float(alone))
    report.findings.append(LeakageFinding(
        "single_feature_knows_the_answer", worst[1] > SINGLE_FEATURE_ALARM,
        "Strongest single feature is {0!r} at AUC {1:.4f} on its own. A lone column "
        "that separates outcomes this well is usually derived from them.".format(
            worst[0] or "none", worst[1]),
    ))

    # 4. shuffled beating chronological means the shuffle borrowed the future
    Xa, Xb, ya, yb = train_test_split(X, y, test_size=0.3, random_state=0, shuffle=True)
    shuffled_auc, _ = fit_auc(Xa, ya, Xb, yb)
    report.findings.append(LeakageFinding(
        "shuffled_split_flatters", (shuffled_auc - test_auc) > SHUFFLE_ADVANTAGE_ALARM,
        "Shuffled split scores {0:.4f} against {1:.4f} chronological. A shuffle lets "
        "the model train on dates after the ones it is scored on; the difference is "
        "the size of that advantage.".format(shuffled_auc, test_auc),
        severity="medium",
    ))

    return report
