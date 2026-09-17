"""Is a parameter family a gradient, a spike, or inert? Decided in advance.

WHY THIS IS A MODULE AND NOT A JUDGEMENT. H-0003's breakeven lock moved
+13.71 points at a trigger of 1.0R, -1.36 at 1.5R and exactly 0.00 at
2.0R. Looking at that and deciding by eye whether it is "a threshold
effect, which is mechanically sensible" or "one fitted point" is the
whole problem: both readings are available, and the one a researcher
reaches for is the one that suits them. So the rule is arithmetic,
written before the sub-1.0R points exist, and it returns a verdict
whether or not the verdict is welcome.

G1  at least 3 of the thresholds move the result at all
G2  the largest move is at most 2.5x the second-largest positive move
G3  the maximum is not isolated - its neighbours also moved the right way
G4  |Spearman rho| >= 0.6, so the family has a consistent direction
DIRECTION  the sign of rho agrees with the direction registered in advance

G2 is the one that bites hardest and is meant to. On the three known
points alone the largest move is +13.71 and the second-largest positive
is 0.00, so the ratio is unbounded and the family is a spike unless a
sub-1.0R threshold also moves substantially.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

GRADIENT = "gradient"
SPIKE = "spike"
INERT = "inert"

#: Registered constants. Chosen before the sub-1.0R results existed.
MAX_DOMINANCE_RATIO = 2.5
MIN_ABS_SPEARMAN = 0.6
MIN_MOVING_POINTS = 3
INERT_BAND_POINTS = 1.0          # |delta| at or below this is "did not move"


def _rank(values: Sequence[float]) -> List[float]:
    """Average ranks, so ties do not fabricate a direction."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        shared = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = shared
        i = j + 1
    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    rx, ry = _rank(xs), _rank(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


@dataclass
class Classification:
    verdict: str
    thresholds: List[float]
    deltas: List[float]                  # in POINTS of total return
    adjacent_differences: List[float] = field(default_factory=list)
    spearman: Optional[float] = None
    checks: Dict[str, bool] = field(default_factory=dict)
    detail: Dict[str, object] = field(default_factory=dict)

    @property
    def is_gradient(self) -> bool:
        return self.verdict == GRADIENT

    def as_dict(self) -> Dict[str, object]:
        return {"verdict": self.verdict,
                "thresholds": self.thresholds,
                "deltas_points": [round(d, 4) for d in self.deltas],
                "adjacent_differences": [round(d, 4)
                                         for d in self.adjacent_differences],
                "spearman": (None if self.spearman is None
                             else round(self.spearman, 4)),
                "checks": self.checks, "detail": self.detail}

    def explain(self) -> str:
        lines = ["family verdict: {0}".format(self.verdict.upper())]
        for name, passed in self.checks.items():
            lines.append("  [{0}] {1}".format("PASS" if passed else "FAIL",
                                              name))
        return "\n".join(lines)


def classify_family(thresholds: Sequence[float],
                    deltas_points: Sequence[float],
                    expected_direction: int) -> Classification:
    """Apply G1-G4 plus the direction condition. Order is fixed.

    `expected_direction` is -1 when the registration predicts the effect
    STRENGTHENS as the threshold falls, +1 when it strengthens as the
    threshold rises. It is part of the registration, not chosen here.
    """
    if expected_direction not in (-1, 1):
        raise ValueError("expected_direction must be -1 or +1")
    thresholds = list(thresholds)
    deltas = list(deltas_points)
    adjacent = [deltas[i + 1] - deltas[i] for i in range(len(deltas) - 1)]
    rho = spearman(thresholds, deltas)

    moved = [d for d in deltas if abs(d) > INERT_BAND_POINTS]
    if not moved:
        return Classification(INERT, thresholds, deltas, adjacent, rho,
                              {"inert: nothing moved beyond the band": True},
                              {"inert_band_points": INERT_BAND_POINTS})

    positives = sorted((d for d in deltas if d > 0), reverse=True)
    largest = max(deltas)
    second = positives[1] if len(positives) > 1 else 0.0
    peak = deltas.index(largest)
    neighbours = []
    if peak > 0:
        neighbours.append(deltas[peak - 1])
    if peak < len(deltas) - 1:
        neighbours.append(deltas[peak + 1])

    checks = {
        "G1 at least {0} thresholds move the result".format(MIN_MOVING_POINTS):
            sum(1 for d in deltas if d > 0) >= MIN_MOVING_POINTS,
        "G2 largest move <= {0}x the second-largest positive".format(
            MAX_DOMINANCE_RATIO):
            bool(second > 0 and largest <= MAX_DOMINANCE_RATIO * second),
        "G3 the maximum is not isolated":
            bool(neighbours) and all(d > 0 for d in neighbours),
        "G4 |spearman| >= {0}".format(MIN_ABS_SPEARMAN):
            rho is not None and abs(rho) >= MIN_ABS_SPEARMAN,
        "direction agrees with the registration":
            rho is not None and (rho < 0) == (expected_direction < 0)
            and rho != 0,
    }
    verdict = GRADIENT if all(checks.values()) else SPIKE
    return Classification(
        verdict, thresholds, deltas, adjacent, rho, checks,
        {"largest": round(largest, 4), "second_largest_positive": round(second, 4),
         "dominance_ratio": (None if second <= 0
                             else round(largest / second, 4)),
         "peak_threshold": thresholds[peak],
         "neighbours_of_peak": [round(d, 4) for d in neighbours],
         "expected_direction": expected_direction})


# ---------------------------------------------------------------------------
# Frozen prior observations
# ---------------------------------------------------------------------------

class FrozenObservationChanged(RuntimeError):
    """Raised when a previously recorded result no longer reproduces."""


def check_frozen(observed: Dict[float, float], frozen: Dict[float, float],
                 tolerance_points: float = 0.01) -> None:
    """Implementation-equivalence. A recorded result must still reproduce.

    Not a new experiment: it re-runs one ALREADY-RECORDED configuration
    and asserts the simulator still produces what it produced before. A
    drift here would mean every earlier number is suspect, so it stops
    rather than continuing into new configurations.
    """
    problems = []
    for threshold, expected in sorted(frozen.items()):
        if threshold not in observed:
            continue
        got = observed[threshold]
        if abs(got - expected) > tolerance_points:
            problems.append(
                "G={0}: recorded {1:+.4f} points, reproduces as {2:+.4f}"
                .format(threshold, expected, got))
    if problems:
        raise FrozenObservationChanged(
            "the simulator no longer reproduces a recorded result: "
            + "; ".join(problems))
