"""Shared value objects for the research pipeline."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple


class Action(str, Enum):
    REJECT = "REJECT"
    WATCH = "WATCH"
    PAPER_LONG = "PAPER_LONG"


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Event:
    title: str
    category: str
    stance: str = "neutral"
    confidence: float = 0.5
    published_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    source: str = ""
    url: str = ""
    notes: str = ""
    matched_terms: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        result = asdict(self)
        for key in ("published_at", "scheduled_at"):
            if result[key] is not None:
                result[key] = result[key].isoformat()
        return result


@dataclass(frozen=True)
class ScoreComponent:
    """One named, bounded contribution to the evidence score.

    Keeping the components separate is what makes the score auditable: a reader
    can see which piece of evidence carried a candidate over the gate, and a
    component that never varies is visible as dead weight rather than hidden
    inside a single number.
    """

    name: str
    value: float
    contribution: float
    maximum: float
    detail: str = ""

    def as_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "value": round(self.value, 6),
            "contribution": round(self.contribution, 3),
            "maximum": round(self.maximum, 3),
            "share_of_maximum": round(self.contribution / self.maximum, 4) if self.maximum else 0.0,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class Candidate:
    symbol: str
    action: Action
    as_of: datetime
    score: float
    entry: Optional[float]
    stop: Optional[float]
    target: Optional[float]
    quantity: int
    planned_risk: float
    modeled_round_trip_cost: float
    event_impact: float
    reasons: List[str]
    blockers: List[str]
    correlation_bucket: str
    score_breakdown: List[ScoreComponent] = field(default_factory=list)
    features: Dict[str, Optional[float]] = field(default_factory=dict)
    regime: Dict[str, object] = field(default_factory=dict)
    net_reward_to_risk: Optional[float] = None
    breakeven_win_rate: Optional[float] = None
    cost_to_edge_ratio: Optional[float] = None

    def as_dict(self) -> Dict[str, object]:
        result = asdict(self)
        result["action"] = self.action.value
        result["as_of"] = self.as_of.isoformat()
        result["score_breakdown"] = [component.as_dict() for component in self.score_breakdown]
        result["features"] = {
            key: (None if value is None else round(value, 6)) for key, value in self.features.items()
        }
        return result


@dataclass(frozen=True)
class Trade:
    symbol: str
    signal_time: datetime
    entry_time: datetime
    exit_time: datetime
    quantity: int
    entry_price: float
    exit_price: float
    stop: float
    target: float
    gross_pnl: float
    costs: float
    net_pnl: float
    r_multiple: float
    exit_reason: str
    bars_held: int = 0
    max_adverse_excursion_r: float = 0.0
    max_favorable_excursion_r: float = 0.0
    entry_score: float = 0.0
    return_fraction: float = 0.0

    def as_dict(self) -> Dict[str, object]:
        result = asdict(self)
        for key in ("signal_time", "entry_time", "exit_time"):
            result[key] = result[key].isoformat()
        for key in (
            "entry_price", "exit_price", "stop", "target", "gross_pnl",
            "costs", "net_pnl", "r_multiple", "max_adverse_excursion_r",
            "max_favorable_excursion_r", "entry_score", "return_fraction",
        ):
            result[key] = round(result[key], 6)
        return result
