"""Decide which configurations survive, by the registered criteria only.

THE BUG THIS EXISTS TO PREVENT. The Phase 6 recorder chose each family's
representative with `max(rows, key=lambda r: r["total_return"])` and then
wrote a conclusion describing a DIFFERENT configuration - the one that
actually passed. For H-0002 the highest return was 1.5R, whose entire
gain is a single year and which fails the registered best-year clause;
the passing configuration was 2.0R. Selecting by raw return is exactly
the habit pre-registration exists to stop, and it had migrated out of the
experiment and into the bookkeeping, where nobody was looking.

So selection is no longer something a caller does. `adjudicate` applies
the criteria to every configuration and returns a verdict for each;
`surviving` returns those that passed. There is no function here that
takes a metric name and returns the best row, and `best_by_return` exists
only to raise if someone reaches for it.

THE ORDER IS FIXED: metrics for all configurations, then criteria, then
robustness, then survivors, then record. Never return first.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence


class SelectionError(RuntimeError):
    """Raised when a caller tries to pick a configuration by performance."""


@dataclass
class Clause:
    """One registered criterion, and whether this configuration met it."""
    name: str
    passed: bool
    detail: str = ""

    def as_dict(self) -> Dict[str, object]:
        return dict(self.__dict__)


@dataclass
class Verdict:
    label: str
    clauses: List[Clause] = field(default_factory=list)
    family_clauses: List[Clause] = field(default_factory=list)

    @property
    def failures(self) -> List[Clause]:
        return [c for c in self.clauses + self.family_clauses if not c.passed]

    @property
    def survives(self) -> bool:
        return not self.failures

    def as_dict(self) -> Dict[str, object]:
        return {"label": self.label, "survives": self.survives,
                "failed": [c.name for c in self.failures],
                "clauses": [c.as_dict() for c in
                            self.clauses + self.family_clauses]}


def yearly_deltas(row: Dict, baseline: Dict) -> Dict[int, float]:
    years = sorted(baseline.get("by_year") or {})
    return {y: (row.get("by_year") or {}).get(y, 0.0)
               - (baseline.get("by_year") or {})[y] for y in years}


def leave_one_best_year_out(deltas: Dict[int, float]) -> float:
    """Sum of yearly differences with the single best year removed.

    Defined here, once, and applied identically to every configuration.
    The procedure was fixed at registration; it is not chosen per result.
    """
    if not deltas:
        return 0.0
    best = max(deltas, key=lambda y: deltas[y])
    return sum(deltas.values()) - deltas[best]


def standard_clauses(row: Dict, baseline: Dict,
                     max_risk_increase: float = 0.10,
                     min_years_better: int = 7) -> List[Clause]:
    """The registered per-configuration criteria for the exit hypotheses."""
    deltas = yearly_deltas(row, baseline)
    wins = sum(1 for v in deltas.values() if v > 0)
    ex_best = leave_one_best_year_out(deltas)

    base_vol = baseline.get("annualised_volatility")
    vol = row.get("annualised_volatility")
    vol_ok = (vol is None or base_vol is None
              or vol <= base_vol * (1.0 + max_risk_increase))
    dd_ok = (abs(row.get("max_drawdown", 0.0))
             <= abs(baseline.get("max_drawdown", 0.0)) * (1.0 + max_risk_increase))

    return [
        Clause("beats baseline on total return",
               row.get("total_return", 0.0) > baseline.get("total_return", 0.0),
               "{0:+.4f} vs {1:+.4f}".format(row.get("total_return", 0.0),
                                             baseline.get("total_return", 0.0))),
        Clause("volatility within {0:.0%} of baseline".format(
            1 + max_risk_increase), vol_ok,
            "{0} vs {1}".format(vol, base_vol)),
        Clause("drawdown within {0:.0%} of baseline".format(
            1 + max_risk_increase), dd_ok,
            "{0:.4f} vs {1:.4f}".format(row.get("max_drawdown", 0.0),
                                        baseline.get("max_drawdown", 0.0))),
        Clause("positive with its best year removed", ex_best > 0,
               "{0:+.4f}".format(ex_best)),
        Clause("better in at least {0} years".format(min_years_better),
               wins >= min_years_better,
               "{0} of {1}".format(wins, len(deltas))),
    ]


def family_monotonicity(rows: Sequence[Dict]) -> Clause:
    """Monotone or flat across adjacent parameter values, as registered."""
    values = [r.get("total_return", 0.0) for r in rows]
    monotone = (all(a <= b for a, b in zip(values, values[1:]))
                or all(a >= b for a, b in zip(values, values[1:])))
    return Clause("family monotone or flat across adjacent values", monotone,
                  ", ".join("{0:+.4f}".format(v) for v in values))


def adjudicate(rows: Sequence[Dict], baseline: Dict,
               clauses: Optional[Callable] = None,
               family_clause: Optional[Callable] = None) -> List[Verdict]:
    """Every configuration gets a verdict. None is discarded or ranked.

    Returned in the order given, which is the registered grid order, NOT
    sorted by any metric - sorting is how a reader's eye is drawn to the
    best number before the criteria have been read.
    """
    clauses = clauses or standard_clauses
    family = (family_clause or family_monotonicity)(rows)
    return [Verdict(label=str(r.get("label", "?")),
                    clauses=clauses(r, baseline),
                    family_clauses=[family])
            for r in rows]


def surviving(verdicts: Sequence[Verdict]) -> List[Verdict]:
    """Those that met every criterion. May be empty, and often should be."""
    return [v for v in verdicts if v.survives]


def best_by_return(*_args, **_kwargs):
    """Deliberately not implemented.

    Reaching for this is the mistake. If a representative configuration is
    needed, take it from `surviving`; if nothing survives, the honest
    answer is that nothing survived, not the best of the failures.
    """
    raise SelectionError(
        "Configurations may not be selected by return. Apply the registered "
        "criteria with `adjudicate` and take the result from `surviving`. "
        "If that list is empty, the family produced no surviving "
        "configuration and must be recorded as such.")
