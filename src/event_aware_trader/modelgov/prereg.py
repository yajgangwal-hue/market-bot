"""Seal a hypothesis before its outcome is visible.

THE FAILURE THIS CLOSES. In Phase 5 I ran a descriptive split, read tables
that carried median R and P&L per bucket, picked the two worst buckets,
and then wrote a mechanism to explain what I had already seen. The
thresholds, the bucket edges and even the rejection rule were all chosen
after the numbers were on screen. Every one of those was reported as a
hypothesis test. None of them was.

Timestamps alone cannot stop that, because whoever writes the row also
controls the clock. Three bindings together can:

  CHAIN      each registration carries the digest of the one before, so a
             row inserted later breaks every link after it.

  COMMIT     the row records `git rev-parse HEAD`. A confirmatory claim
             whose commit is not an ancestor of the result's commit is
             detectable from git's own history, which the researcher does
             not control retroactively.

  SEAL       `seal()` returns a digest over the complete record. `verify()`
             recomputes it from the configuration actually being run and
             refuses when they differ, so a threshold edited after
             registration cannot execute under that registration.

WHAT IT DOES NOT DO. It cannot stop someone registering fifty hypotheses
and reporting the best one - only the trial count in the ledger and the
deflation that pays for it can do that. It makes the ORDER of events
auditable, which is the part that was unfalsifiable before.
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

REGISTRATIONS = Path("docs/preregistrations.jsonl")
GENESIS = "0" * 64

EXPLORATORY = "exploratory"
CONFIRMATORY = "confirmatory"


class RegistrationError(RuntimeError):
    """Raised when a run does not match what was registered."""


@dataclass
class Hypothesis:
    """Everything that must be fixed before the outcome is looked at."""
    statement: str
    rationale: str                     # economic or mechanical, not "it fits"
    rule: str                          # the exact change, in words
    parameters: Dict[str, object]      # exact values, or the declared grid
    search_procedure: str              # how the grid may be traversed
    max_configurations: int            # the trial cap, binding
    datasets: List[str]
    information_boundary: str          # what is knowable at decision time
    execution_assumptions: str
    primary_metric: str                # ONE. Secondary cannot overturn it.
    secondary_metrics: List[str]
    acceptance_criteria: str
    rejection_criteria: str
    robustness_requirements: List[str]
    complexity_penalty: str
    required_oos_test: str
    promotion_requirements: List[str]
    kind: str = CONFIRMATORY
    hypothesis_id: str = ""
    registered_at: str = ""
    code_commit: str = ""

    def __post_init__(self):
        if self.kind not in (EXPLORATORY, CONFIRMATORY):
            raise ValueError("kind must be exploratory or confirmatory")
        if self.max_configurations < 1:
            raise ValueError("a hypothesis evaluates at least one configuration")

    def sealable(self) -> Dict[str, object]:
        """The fields the seal covers. Everything that could be tuned."""
        return {
            "statement": self.statement, "rule": self.rule,
            "parameters": self.parameters,
            "search_procedure": self.search_procedure,
            "max_configurations": self.max_configurations,
            "datasets": sorted(self.datasets),
            "information_boundary": self.information_boundary,
            "execution_assumptions": self.execution_assumptions,
            "primary_metric": self.primary_metric,
            "acceptance_criteria": self.acceptance_criteria,
            "rejection_criteria": self.rejection_criteria,
            "robustness_requirements": sorted(self.robustness_requirements),
            "kind": self.kind,
        }

    def seal(self) -> str:
        body = json.dumps(self.sealable(), sort_keys=True,
                          separators=(",", ":"), default=str)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _digest(payload: Dict, previous: str) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=str)
    return hashlib.sha256((previous + body).encode("utf-8")).hexdigest()


def _raw(path: Path) -> List[Dict]:
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def register(hypothesis: Hypothesis,
             path: Path = REGISTRATIONS) -> Dict[str, object]:
    """Seal and append. Returns the row, whose `seal` is the token."""
    from .lineage import git_commit
    path = Path(path)
    rows = _raw(path)
    payload = asdict(hypothesis)
    payload["seal"] = hypothesis.seal()
    payload["hypothesis_id"] = (hypothesis.hypothesis_id or
                                "H-{0:04d}".format(len(rows) + 1))
    payload["registered_at"] = (hypothesis.registered_at or
                                datetime.now(timezone.utc).isoformat())
    payload["code_commit"] = hypothesis.code_commit or git_commit()
    if any(r["payload"]["hypothesis_id"] == payload["hypothesis_id"]
           for r in rows):
        raise RegistrationError(
            "{0} is already registered. Register a new hypothesis that cites "
            "the old one rather than editing it.".format(
                payload["hypothesis_id"]))
    previous = rows[-1]["digest"] if rows else GENESIS
    row = {"payload": payload, "previous": previous,
           "digest": _digest(payload, previous)}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def verify(hypothesis_id: str, running: Hypothesis,
           path: Path = REGISTRATIONS) -> Dict[str, object]:
    """Refuse to run anything the registration did not describe.

    Called BEFORE the experiment, with the configuration the experiment is
    about to use. A parameter changed since registration produces a
    different seal and this raises.
    """
    rows = _raw(path)
    match = [r for r in rows
             if r["payload"]["hypothesis_id"] == hypothesis_id]
    if not match:
        raise RegistrationError(
            "{0} is not registered. A confirmatory test requires a "
            "registration written before its outcome was seen.".format(
                hypothesis_id))
    registered = match[-1]["payload"]
    if registered["seal"] != running.seal():
        raise RegistrationError(
            "{0} does not match its registration. Something that was fixed "
            "in advance has changed, so this run is EXPLORATORY and may not "
            "be reported as confirmatory.".format(hypothesis_id))
    return registered


def verify_chain(path: Path = REGISTRATIONS) -> Dict[str, object]:
    rows = _raw(path)
    previous = GENESIS
    for i, row in enumerate(rows):
        if row.get("previous") != previous:
            return {"intact": False, "registrations": len(rows),
                    "broken_at": i,
                    "reason": "row {0} does not follow its predecessor".format(i)}
        if _digest(row["payload"], previous) != row.get("digest"):
            return {"intact": False, "registrations": len(rows),
                    "broken_at": i,
                    "reason": "row {0} was edited after registration".format(i)}
        previous = row["digest"]
    return {"intact": True, "registrations": len(rows), "broken_at": None,
            "reason": "every link recomputes"}


def load(path: Path = REGISTRATIONS) -> List[Dict[str, object]]:
    check = verify_chain(path)
    if not check["intact"]:
        raise RegistrationError("registration chain broken: " +
                                str(check["reason"]))
    return [r["payload"] for r in _raw(path)]


def declared_trials(path: Path = REGISTRATIONS) -> int:
    """Every configuration the track has committed to evaluating."""
    return sum(int(p.get("max_configurations") or 1) for p in load(path))
