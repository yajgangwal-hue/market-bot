"""The Phase 5 research ledger. Separate file, separate schema, separate risk.

WHY NOT THE PRODUCTION REGISTRY. `purge.freeze_date()` derives Track A's
freeze from the production registry as the date of the last row whose
decision was `accepted` or `reverted`. A Phase 5 row carrying either of
those decisions would move that date, reset the 20-session embargo, and
silently invalidate the clean forward record the whole of Phase 4 exists
to protect. Nothing about the research track is worth that, so research
rows go somewhere else entirely and a test asserts the freeze cannot move.

Two more properties the brief requires and this file enforces:

  NEGATIVE RESULTS SURVIVE. The ledger is append-only. A later experiment
  cannot overwrite an earlier one, and `record` refuses a duplicate id
  rather than replacing it. An experiment that failed is the most
  reusable thing in here.

  THE TRIAL COUNT IS CARRIED. Every row states how many configurations it
  stands for, so "the best of N tries" can be discounted honestly rather
  than quoted as though it were the only try.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

LEDGER = Path("docs/phase5-research.jsonl")

#: Research verdicts. Deliberately NOT the production registry's vocabulary:
#: nothing here can "accept" anything, because acceptance is a later phase's
#: decision made against data this track is not allowed to spend.
VERDICTS = (
    "rejected",            # measured, and worse or no different
    "inconclusive",        # the measurement could not separate the outcomes
    "research_evidence",   # promising, on contaminated data, proves nothing
    "promotion_candidate",  # survived validation AND an untouched test period
)

#: How far a result may travel. The gap between the third and fourth verdict
#: is the whole discipline of this phase.
PROMOTION_REQUIREMENTS = (
    "improvement during research",
    "survives validation",
    "survives an untouched test period",
    "no unresolved data leakage",
    "realistic transaction costs",
    "realistic execution assumptions",
    "parameter stability demonstrated",
    "research history documented",
)


@dataclass
class Experiment:
    """One recorded experiment. Every field the brief asks for, or None."""
    hypothesis: str
    configuration: Dict[str, object]
    dataset: str
    date_range: str
    universe: str
    costs: str
    execution_assumptions: str
    information_sources: List[str]
    trials: int
    metrics: Dict[str, object]
    baseline_metrics: Dict[str, object]
    validation_methodology: str
    leakage_risks: List[str]
    conclusion: str
    verdict: str
    suitable_for_further_testing: bool
    id: str = ""
    when: str = ""
    difference_from_baseline: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if self.verdict not in VERDICTS:
            raise ValueError("verdict must be one of {0}".format(VERDICTS))
        if self.trials < 1:
            raise ValueError("an experiment evaluates at least one configuration")
        if not self.difference_from_baseline:
            self.difference_from_baseline = difference(self.metrics,
                                                       self.baseline_metrics)


def difference(metrics: Dict[str, object],
               baseline: Dict[str, object]) -> Dict[str, object]:
    """Candidate minus baseline, for every numeric both of them report.

    Computed rather than typed, because a difference quoted by hand is a
    difference that can be quoted selectively.
    """
    out: Dict[str, object] = {}
    for key, value in metrics.items():
        other = baseline.get(key)
        if isinstance(value, (int, float)) and isinstance(other, (int, float)) \
                and not isinstance(value, bool) and not isinstance(other, bool):
            out[key] = round(float(value) - float(other), 6)
    return out


def load(path: Path = LEDGER) -> List[Dict[str, object]]:
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def record(experiment: Experiment, path: Path = LEDGER) -> Dict[str, object]:
    """Append one experiment. Refuses to overwrite, refuses a duplicate id."""
    path = Path(path)
    rows = load(path)
    row = asdict(experiment)
    row["id"] = experiment.id or "P5-{0:04d}".format(len(rows) + 1)
    row["when"] = experiment.when or datetime.now(timezone.utc).isoformat()
    if any(r.get("id") == row["id"] for r in rows):
        raise ValueError(
            "{0} is already recorded. The research ledger is append-only: a "
            "failed experiment must not be overwritten by a later one."
            .format(row["id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def total_trials(path: Path = LEDGER) -> int:
    """Every configuration this track has evaluated, for deflation."""
    return sum(int(r.get("trials") or 1) for r in load(path))


def summary(path: Path = LEDGER) -> Dict[str, object]:
    rows = load(path)
    by_verdict: Dict[str, int] = {}
    for r in rows:
        by_verdict[r.get("verdict", "?")] = by_verdict.get(r.get("verdict", "?"), 0) + 1
    return {
        "experiments": len(rows),
        "configurations": total_trials(path),
        "by_verdict": by_verdict,
        "promotion_candidates": [r["id"] for r in rows
                                 if r.get("verdict") == "promotion_candidate"],
    }


def touches_frozen_registry(path: Path = LEDGER) -> bool:
    """True if the research ledger was pointed at the production registry.

    The one mistake that would matter. Called by a test rather than by the
    writer, because a writer that checks its own destination has already
    been told where to write.
    """
    from ..research import REGISTRY
    return Path(path).resolve() == Path(REGISTRY).resolve()
