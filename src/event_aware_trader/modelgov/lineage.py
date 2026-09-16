"""Model lineage. "What did the model know when it made this decision?"

Every trained model gets a row here before it is allowed anywhere near a
decision, and the row carries enough to answer that question years later:
the intervals it trained, validated and tested on, the information cutoff
past which it saw nothing, the dataset and feature versions, the code
commit, the hyperparameters, and the trust status it earned.

APPEND-ONLY AND HASH-CHAINED, for the same reason the forward record is: a
model that turned out badly must not be quietly edited into one that
turned out well. `verify_chain` recomputes every link.

THE ID IS A DIGEST, NOT A COUNTER. It is computed over the training data
fingerprint, the feature list, the hyperparameters and the cutoff, so two
models with the same id really are the same model, and a model retrained
on one extra example is visibly a different one.
"""

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

LINEAGE = Path("docs/model-lineage.jsonl")
GENESIS = "0" * 64

#: Bump when the meaning of a feature changes. A model trained under one
#: feature version must never be compared with one trained under another
#: as though the numbers were interchangeable.
FEATURE_VERSION = "live_v1"


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def dataset_fingerprint(rows: Sequence[Dict]) -> str:
    """A digest over the training corpus as it stood at training time."""
    body = json.dumps(
        [[str(r.get("at") or r.get("d") or ""), str(r.get("symbol") or ""),
          int(r.get("label", 0))] for r in rows],
        sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass
class ModelRecord:
    trained_at: str
    information_cutoff: str          # nothing after this was visible
    train_interval: str
    validate_interval: str
    test_interval: str
    dataset_fingerprint: str
    dataset_rows: int
    feature_version: str
    features: List[str]
    code_commit: str
    hyperparameters: Dict[str, object]
    evaluation: Dict[str, object]
    trust_status: str
    notes: str = ""
    model_id: str = ""

    def compute_id(self) -> str:
        body = json.dumps({
            "data": self.dataset_fingerprint,
            "features": sorted(self.features),
            "feature_version": self.feature_version,
            "hyperparameters": dict(sorted(self.hyperparameters.items())),
            "cutoff": self.information_cutoff,
        }, sort_keys=True, separators=(",", ":"), default=str)
        return "M-" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def _digest(payload: Dict, previous: str) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256((previous + body).encode("utf-8")).hexdigest()


def _raw(path: Path) -> List[Dict]:
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def record(model: ModelRecord, path: Path = LINEAGE) -> Dict[str, object]:
    """Append one model. Refuses to re-record the same id."""
    path = Path(path)
    rows = _raw(path)
    payload = asdict(model)
    payload["model_id"] = model.model_id or model.compute_id()
    if any(r["payload"]["model_id"] == payload["model_id"] for r in rows):
        raise ValueError(
            "{0} is already recorded. Lineage is append-only: retrain on "
            "different data or a different configuration rather than "
            "overwriting a model's history.".format(payload["model_id"]))
    previous = rows[-1]["digest"] if rows else GENESIS
    row = {"payload": payload, "previous": previous,
           "digest": _digest(payload, previous),
           "recorded_at": datetime.now(timezone.utc).isoformat()}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def verify_chain(path: Path = LINEAGE) -> Dict[str, object]:
    rows = _raw(path)
    previous = GENESIS
    for i, row in enumerate(rows):
        if row.get("previous") != previous:
            return {"intact": False, "models": len(rows), "broken_at": i,
                    "reason": "record {0} does not follow its predecessor".format(i)}
        if _digest(row["payload"], previous) != row.get("digest"):
            return {"intact": False, "models": len(rows), "broken_at": i,
                    "reason": "record {0} was edited after it was written".format(i)}
        previous = row["digest"]
    return {"intact": True, "models": len(rows), "broken_at": None,
            "reason": "every link recomputes"}


def load(path: Path = LINEAGE) -> List[Dict[str, object]]:
    check = verify_chain(path)
    if not check["intact"]:
        raise ValueError("model lineage is broken: " + str(check["reason"]))
    return [r["payload"] for r in _raw(path)]


def latest_trusted(path: Path = LINEAGE) -> Optional[Dict[str, object]]:
    """The most recent model that earned TRUSTED, or None. None means the
    baseline stands, which is the correct default."""
    trusted = [p for p in load(path) if p.get("trust_status") == "TRUSTED"]
    return trusted[-1] if trusted else None
