"""Append-only paper-trade journal; no broker or order-routing code exists."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from .types import Candidate


def append_candidate(path: Path, candidate: Candidate, edge: str, thesis: str) -> None:
    if candidate.action.value != "PAPER_LONG":
        raise ValueError("Only a cleared PAPER_LONG candidate can be journaled")
    if not edge.strip() or not thesis.strip():
        raise ValueError("A named edge and falsifiable thesis are both required")
    record: Dict[str, object] = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "kind": "paper_trade_plan",
        "candidate": candidate.as_dict(),
        "named_edge": edge.strip(),
        "thesis": thesis.strip(),
        "followed_plan": None,
        "outcome_r": None,
        "note": "Paper only. This record did not submit an order.",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
