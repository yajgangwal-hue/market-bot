"""Whether a learned model has earned the right to influence a trade.

THE DEFAULT IS NO. `assess` starts from UNTRUSTED and a model has to clear
every condition to move. That direction matters: a gate whose default is
"allow unless something objects" lets a model through whenever a check is
missing, which is how the current live model came to be ranking candidates
on a 0.5424 AUC measured against a split with no purge.

THE CONTROL THAT MUST FAIL. `shuffled_control_auc` is the same pipeline with
training labels permuted. If a model scores well out of sample on labels
that carry no information, the pipeline is leaking and the real score means
nothing. A control that passes is a failure of the experiment, not a
success of the model - `SHUFFLED_CONTROL_MAX` is therefore an upper bound
the control must stay BELOW.

WHAT THIS DELIBERATELY DOES NOT DO. It does not rank models, does not pick
the best of several, and does not lower a threshold that a promising model
narrowly misses. Every threshold here is a constant in this file, declared
before any model was measured against it.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

UNTRUSTED = "UNTRUSTED"
OBSERVE_ONLY = "OBSERVE_ONLY"     # may be scored and logged, never consulted
TRUSTED = "TRUSTED"               # may influence, still under hard risk limits

#: Minimum mean out-of-sample AUC across folds. 0.53 is inherited from the
#: existing trainer so the comparison is like for like; it is a low bar and
#: is not on its own sufficient - every other condition must also hold.
MIN_MEAN_TEST_AUC = 0.53

#: The worst fold may not be worse than a coin. A model that is strong on
#: average because one fold carried it is not stable.
MIN_WORST_TEST_AUC = 0.50

#: Most folds must be on the right side of chance.
MIN_FRACTION_FOLDS_ABOVE_HALF = 0.6

#: Train minus test. A large gap is memorisation whatever the test score.
MAX_TRAIN_TEST_GAP = 0.15

#: The shuffled-label control must stay below this. Above it, the split
#: leaks and every other number on the page is void.
SHUFFLED_CONTROL_MAX = 0.55

#: Calibration. Brier must beat predicting the base rate for every example;
#: a model whose probabilities are worse than a constant cannot be used to
#: size or to abstain.
REQUIRE_BRIER_BEATS_BASE_RATE = True

#: Below this many scored folds nothing is concluded at all.
MIN_FOLDS = 3

#: Below this many out-of-sample examples nothing is concluded either.
MIN_TEST_EXAMPLES = 150


@dataclass
class Condition:
    name: str
    passed: bool
    detail: str

    def as_dict(self) -> Dict[str, object]:
        return dict(self.__dict__)


@dataclass
class TrustReport:
    status: str
    conditions: List[Condition] = field(default_factory=list)
    measured: Dict[str, object] = field(default_factory=dict)

    @property
    def failures(self) -> List[Condition]:
        return [c for c in self.conditions if not c.passed]

    @property
    def may_influence_trades(self) -> bool:
        return self.status == TRUSTED

    def as_dict(self) -> Dict[str, object]:
        return {
            "status": self.status,
            "may_influence_trades": self.may_influence_trades,
            "failed": [c.name for c in self.failures],
            "conditions": [c.as_dict() for c in self.conditions],
            "measured": self.measured,
        }

    def explain(self) -> str:
        lines = ["trust status: {0}".format(self.status)]
        for c in self.conditions:
            lines.append("  [{0}] {1} - {2}".format(
                "PASS" if c.passed else "FAIL", c.name, c.detail))
        return "\n".join(lines)


def base_rate_brier(base_rate: float) -> float:
    """Brier score of always predicting the base rate. The bar to beat."""
    return base_rate * (1.0 - base_rate)


def assess(walk: Dict[str, object],
           shuffled: Optional[Dict[str, object]] = None) -> TrustReport:
    """Score a walk-forward result against every declared condition."""
    results = walk.get("results") or []
    scored = [r for r in results if r.get("test_auc") is not None]
    mean_test = walk.get("mean_test_auc")
    mean_gap = walk.get("mean_gap")
    worst = walk.get("worst_test_auc")
    n_test = sum(int(r.get("n_test") or 0) for r in scored)
    above = walk.get("folds_above_half") or 0
    fraction_above = (above / len(scored)) if scored else 0.0

    conditions: List[Condition] = []

    def add(name, passed, detail):
        conditions.append(Condition(name, bool(passed), detail))

    add("no split violations", not walk.get("split_violations"),
        "; ".join(walk.get("split_violations") or []) or
        "train ends before test begins on every fold, with the horizon purged")

    add("enough folds", len(scored) >= MIN_FOLDS,
        "{0} scored folds, minimum {1}".format(len(scored), MIN_FOLDS))

    add("enough out-of-sample examples", n_test >= MIN_TEST_EXAMPLES,
        "{0} test examples, minimum {1}".format(n_test, MIN_TEST_EXAMPLES))

    add("mean out-of-sample AUC", mean_test is not None
        and mean_test >= MIN_MEAN_TEST_AUC,
        "{0} vs minimum {1}".format(
            "n/a" if mean_test is None else round(mean_test, 4),
            MIN_MEAN_TEST_AUC))

    add("worst fold beats chance", worst is not None
        and worst >= MIN_WORST_TEST_AUC,
        "worst fold {0} vs minimum {1}".format(
            "n/a" if worst is None else round(worst, 4), MIN_WORST_TEST_AUC))

    add("most folds beat chance",
        fraction_above >= MIN_FRACTION_FOLDS_ABOVE_HALF,
        "{0} of {1} folds above 0.5, minimum {2:.0%}".format(
            above, len(scored), MIN_FRACTION_FOLDS_ABOVE_HALF))

    add("train/test gap within bound", mean_gap is not None
        and mean_gap <= MAX_TRAIN_TEST_GAP,
        "gap {0} vs maximum {1}".format(
            "n/a" if mean_gap is None else round(mean_gap, 4),
            MAX_TRAIN_TEST_GAP))

    if REQUIRE_BRIER_BEATS_BASE_RATE:
        beaten, total = 0, 0
        for r in scored:
            brier, rate = r.get("test_brier"), r.get("base_rate")
            if brier is None or rate is None:
                continue
            total += 1
            if brier < base_rate_brier(float(rate)):
                beaten += 1
        add("calibration beats the base rate",
            total > 0 and beaten == total,
            "{0} of {1} folds beat a constant base-rate forecast".format(
                beaten, total))

    if shuffled is None:
        add("shuffled-label control was run", False,
            "no control supplied; a model cannot be trusted without one")
    else:
        control = shuffled.get("mean_test_auc")
        add("shuffled-label control stays near chance",
            control is not None and control < SHUFFLED_CONTROL_MAX,
            "control AUC {0}, must be below {1} (a HIGH control means the "
            "split leaks, not that the model is good)".format(
                "n/a" if control is None else round(control, 4),
                SHUFFLED_CONTROL_MAX))

    failures = [c for c in conditions if not c.passed]
    if not failures:
        status = TRUSTED
    elif len(failures) == len(conditions):
        status = UNTRUSTED
    else:
        # Something measurable held, but not everything. The model may be
        # recorded and watched; it may not be consulted.
        status = OBSERVE_ONLY if any(c.passed for c in conditions) else UNTRUSTED
        if any(c.name in ("no split violations",
                          "shuffled-label control stays near chance")
               and not c.passed for c in conditions):
            # A leaking split or a passing control voids the whole result.
            status = UNTRUSTED

    return TrustReport(status=status, conditions=conditions, measured={
        "mean_test_auc": mean_test, "mean_train_auc": walk.get("mean_train_auc"),
        "mean_gap": mean_gap, "worst_test_auc": worst,
        "best_test_auc": walk.get("best_test_auc"),
        "folds_scored": len(scored), "test_examples": n_test,
        "shuffled_control_auc": (shuffled or {}).get("mean_test_auc"),
    })


# ---------------------------------------------------------------------------
# Abstention. The model must be allowed to say nothing.
# ---------------------------------------------------------------------------

def abstention_curve(probabilities: Sequence[float],
                     labels: Sequence[int],
                     bands: Sequence[float] = (0.0, 0.05, 0.10, 0.15, 0.20)
                     ) -> List[Dict[str, object]]:
    """Accuracy against coverage as the model is allowed to decline.

    A model that is right only when it is confident is useful even at low
    coverage; a model whose accuracy is flat as coverage falls is not
    distinguishing anything and should abstain always. `band` is the
    half-width around 0.5 within which the model declines to call.
    """
    out = []
    for band in bands:
        kept = [(p, y) for p, y in zip(probabilities, labels)
                if abs(p - 0.5) >= band]
        if not kept:
            out.append({"band": band, "coverage": 0.0, "n": 0,
                        "accuracy": None, "base_rate": None})
            continue
        correct = sum(1 for p, y in kept if (p >= 0.5) == bool(y))
        rate = sum(1 for _p, y in kept if y) / len(kept)
        out.append({
            "band": band,
            "coverage": round(len(kept) / len(probabilities), 4),
            "n": len(kept),
            "accuracy": round(correct / len(kept), 4),
            "base_rate": round(rate, 4),
            "lift_over_majority": round(
                correct / len(kept) - max(rate, 1.0 - rate), 4),
        })
    return out
