"""Evidence-bound model training for reviewed paper-trading scenarios.

The model predicts only whether a *human-defined directional scenario* aligned
with a later, cost-adjusted paper outcome in the historical data.  It never
sets a direction, opens a position, or authorises a trade.  Chronological
out-of-sample testing and calibration are mandatory because fitting the past is
not evidence of predictive skill.
"""

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


FEATURE_NAMES = (
    "intercept",
    "trust_score",
    "freshness",
    "text_length_log",
    "entity_count",
    "platform_bluesky",
    "platform_x",
    "platform_rss",
    "direction_up",
    "direction_down",
    "claim_policy",
    "claim_company",
    "claim_macro",
)
VALID_DIRECTIONS = {"up", "down"}
VALID_CLAIM_TYPES = {"policy", "company", "macro", "other"}


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("published_at must include a timezone")
    return parsed


@dataclass(frozen=True)
class LabeledExample:
    example_id: str
    published_at: datetime
    platform: str
    trust_score: float
    age_minutes: float
    text_length: int
    entity_count: int
    direction: str
    claim_type: str
    outcome_return_bps: float
    friction_bps: float
    horizon_minutes: int
    label: int

    def as_dict(self) -> Dict[str, object]:
        result = asdict(self)
        result["published_at"] = self.published_at.isoformat()
        return result


@dataclass(frozen=True)
class TrainedModel:
    version: int
    feature_names: Tuple[str, ...]
    means: Tuple[float, ...]
    scales: Tuple[float, ...]
    weights: Tuple[float, ...]
    status: str
    report: Dict[str, object]

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


def example_from_mapping(raw: Dict[str, object]) -> LabeledExample:
    example_id = str(raw.get("example_id", "")).strip()
    if not example_id:
        raise ValueError("Each training example needs example_id")
    direction = str(raw.get("direction", "")).lower().strip()
    claim_type = str(raw.get("claim_type", "other")).lower().strip()
    if direction not in VALID_DIRECTIONS:
        raise ValueError("direction must be one of: {0}".format(", ".join(sorted(VALID_DIRECTIONS))))
    if claim_type not in VALID_CLAIM_TYPES:
        raise ValueError("claim_type must be one of: {0}".format(", ".join(sorted(VALID_CLAIM_TYPES))))
    platform = str(raw.get("platform", "")).lower().strip()
    if platform not in {"bluesky", "x", "rss"}:
        raise ValueError("platform must be bluesky, x, or rss")
    trust_score = float(raw.get("trust_score", 0.0))
    age_minutes = float(raw.get("age_minutes", -1.0))
    text_length = int(raw.get("text_length", 0))
    entity_count = int(raw.get("entity_count", 0))
    outcome_return_bps = float(raw.get("outcome_return_bps"))
    friction_bps = float(raw.get("friction_bps", 6.0))
    horizon_minutes = int(raw.get("horizon_minutes", 0))
    if not 0.0 <= trust_score <= 100.0:
        raise ValueError("trust_score must be between 0 and 100")
    if age_minutes < 0 or text_length < 0 or entity_count < 1 or friction_bps < 0 or horizon_minutes <= 0:
        raise ValueError("age, text length, entity count, friction, and horizon must be non-negative; horizon must be positive")
    if direction == "up":
        label = int(outcome_return_bps > friction_bps)
    else:
        label = int(outcome_return_bps < -friction_bps)
    return LabeledExample(
        example_id=example_id,
        published_at=_parse_datetime(str(raw.get("published_at", ""))),
        platform=platform,
        trust_score=trust_score,
        age_minutes=age_minutes,
        text_length=text_length,
        entity_count=entity_count,
        direction=direction,
        claim_type=claim_type,
        outcome_return_bps=outcome_return_bps,
        friction_bps=friction_bps,
        horizon_minutes=horizon_minutes,
        label=label,
    )


def load_examples(path: Path) -> List[LabeledExample]:
    examples = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            cleaned = line.strip()
            if not cleaned or cleaned.startswith("#"):
                continue
            try:
                raw = json.loads(cleaned)
                examples.append(example_from_mapping(raw))
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                raise ValueError("Invalid training example on line {0}: {1}".format(line_number, error)) from error
    if not examples:
        raise ValueError("No training examples found")
    ids = [example.example_id for example in examples]
    if len(ids) != len(set(ids)):
        raise ValueError("Training examples must have unique example_id values")
    return sorted(examples, key=lambda example: example.published_at)


def _raw_features(example: LabeledExample) -> List[float]:
    freshness = max(0.0, min(1.0, 1.0 - example.age_minutes / 60.0))
    return [
        1.0,
        example.trust_score / 100.0,
        freshness,
        math.log1p(example.text_length),
        float(example.entity_count),
        float(example.platform == "bluesky"),
        float(example.platform == "x"),
        float(example.platform == "rss"),
        float(example.direction == "up"),
        float(example.direction == "down"),
        float(example.claim_type == "policy"),
        float(example.claim_type == "company"),
        float(example.claim_type == "macro"),
    ]


def _normalizer(rows: Sequence[Sequence[float]]) -> Tuple[List[float], List[float]]:
    width = len(FEATURE_NAMES)
    means = [0.0] * width
    scales = [1.0] * width
    for column in range(1, width):  # Intercept stays fixed at one.
        values = [row[column] for row in rows]
        average = sum(values) / len(values)
        variance = sum((value - average) ** 2 for value in values) / len(values)
        means[column] = average
        scales[column] = max(math.sqrt(variance), 1e-8)
    return means, scales


def _standardize(row: Sequence[float], means: Sequence[float], scales: Sequence[float]) -> List[float]:
    result = [1.0]
    for index in range(1, len(row)):
        result.append((row[index] - means[index]) / scales[index])
    return result


def _sigmoid(value: float) -> float:
    clipped = max(-35.0, min(35.0, value))
    return 1.0 / (1.0 + math.exp(-clipped))


def _probability(row: Sequence[float], weights: Sequence[float]) -> float:
    return _sigmoid(sum(value * weight for value, weight in zip(row, weights)))


def _metrics(labels: Sequence[int], probabilities: Sequence[float]) -> Dict[str, object]:
    if not labels:
        return {"sample_count": 0, "accuracy": None, "brier_score": None, "base_rate_brier_score": None, "calibration_error": None, "calibration_bins": []}
    base_rate = sum(labels) / len(labels)
    brier = sum((probability - label) ** 2 for label, probability in zip(labels, probabilities)) / len(labels)
    base_brier = sum((base_rate - label) ** 2 for label in labels) / len(labels)
    accuracy = sum(int((probability >= 0.5) == bool(label)) for label, probability in zip(labels, probabilities)) / len(labels)
    bins = []
    calibration_error = 0.0
    for index in range(5):
        lower = index / 5.0
        upper = (index + 1) / 5.0
        bucket = [(label, probability) for label, probability in zip(labels, probabilities) if lower <= probability < upper or (index == 4 and probability == 1.0)]
        if not bucket:
            continue
        observed = sum(label for label, _ in bucket) / len(bucket)
        predicted = sum(probability for _, probability in bucket) / len(bucket)
        gap = abs(predicted - observed)
        calibration_error += len(bucket) / len(labels) * gap
        bins.append({"range": "{0:.1f}-{1:.1f}".format(lower, upper), "count": len(bucket), "mean_predicted": round(predicted, 6), "observed_rate": round(observed, 6)})
    return {
        "sample_count": len(labels),
        "base_rate": round(base_rate, 6),
        "accuracy": round(accuracy, 6),
        "brier_score": round(brier, 6),
        "base_rate_brier_score": round(base_brier, 6),
        "calibration_error": round(calibration_error, 6),
        "calibration_bins": bins,
    }


def train_model(
    examples: Sequence[LabeledExample],
    min_examples: int = 200,
    learning_rate: float = 0.08,
    epochs: int = 600,
    l2: float = 0.02,
) -> TrainedModel:
    """Train chronologically and report only untouched final-period performance."""
    if min_examples < 20:
        raise ValueError("min_examples must be at least 20")
    if len(examples) < 20:
        raise ValueError("At least 20 labeled examples are required to train any diagnostic model")
    if learning_rate <= 0 or epochs < 1 or l2 < 0:
        raise ValueError("learning_rate and epochs must be positive; l2 must be non-negative")
    ordered = sorted(examples, key=lambda example: example.published_at)
    split_index = max(1, int(len(ordered) * 0.70))
    train_examples = ordered[:split_index]
    test_examples = ordered[split_index:]
    if len(test_examples) < 5:
        raise ValueError("Need at least five chronological out-of-sample examples")
    train_raw = [_raw_features(example) for example in train_examples]
    means, scales = _normalizer(train_raw)
    train_rows = [_standardize(row, means, scales) for row in train_raw]
    train_labels = [example.label for example in train_examples]
    weights = [0.0] * len(FEATURE_NAMES)
    for _ in range(epochs):
        gradient = [0.0] * len(FEATURE_NAMES)
        for row, label in zip(train_rows, train_labels):
            error = _probability(row, weights) - label
            for index, value in enumerate(row):
                gradient[index] += error * value
        for index in range(1, len(weights)):
            gradient[index] += l2 * weights[index] * len(train_rows)
        for index in range(len(weights)):
            weights[index] -= learning_rate * gradient[index] / len(train_rows)
    test_rows = [_standardize(_raw_features(example), means, scales) for example in test_examples]
    test_labels = [example.label for example in test_examples]
    metrics = _metrics(test_labels, [_probability(row, weights) for row in test_rows])
    sample_ready = len(ordered) >= min_examples and len(test_examples) >= max(50, min_examples // 4)
    improves_on_base = bool(metrics["brier_score"] is not None and metrics["brier_score"] < metrics["base_rate_brier_score"] * 0.98)
    calibrated = bool(metrics["calibration_error"] is not None and metrics["calibration_error"] <= 0.10)
    status = "RESEARCH_ONLY_CANDIDATE" if sample_ready and improves_on_base and calibrated else "UNPROVEN"
    report: Dict[str, object] = {
        "method": "Chronological 70/30 split. No order execution or parameter optimisation on the final segment.",
        "training_count": len(train_examples),
        "out_of_sample_count": len(test_examples),
        "minimum_examples": min_examples,
        "out_of_sample": metrics,
        "sample_ready": sample_ready,
        "improves_on_base_rate": improves_on_base,
        "calibration_passed": calibrated,
        "status_explanation": "A candidate status is still research-only and is never an authorisation to trade.",
    }
    return TrainedModel(
        version=1,
        feature_names=FEATURE_NAMES,
        means=tuple(means),
        scales=tuple(scales),
        weights=tuple(weights),
        status=status,
        report=report,
    )


def save_model(path: Path, model: TrainedModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_model(path: Path) -> TrainedModel:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if tuple(raw.get("feature_names", [])) != FEATURE_NAMES:
        raise ValueError("Model features do not match this version of the research pipeline")
    values = (raw.get("means", []), raw.get("scales", []), raw.get("weights", []))
    if any(len(value) != len(FEATURE_NAMES) for value in values):
        raise ValueError("Model is incomplete or corrupt")
    return TrainedModel(
        version=int(raw.get("version", 0)),
        feature_names=tuple(raw["feature_names"]),
        means=tuple(float(value) for value in raw["means"]),
        scales=tuple(float(value) for value in raw["scales"]),
        weights=tuple(float(value) for value in raw["weights"]),
        status=str(raw.get("status", "UNPROVEN")),
        report=dict(raw.get("report", {})),
    )


def forecast_scenario(model: TrainedModel, raw: Dict[str, object]) -> Dict[str, object]:
    """Score a reviewed direction only; no direction is generated automatically."""
    template = dict(raw)
    template.setdefault("example_id", "forecast")
    template.setdefault("published_at", "2000-01-01T00:00:00+00:00")
    template.setdefault("outcome_return_bps", 0.0)
    template.setdefault("friction_bps", 6.0)
    template.setdefault("horizon_minutes", 60)
    scenario = example_from_mapping(template)
    row = _standardize(_raw_features(scenario), model.means, model.scales)
    probability = _probability(row, model.weights)
    return {
        "model_status": model.status,
        "historical_alignment_probability": round(probability, 6),
        "scenario": {
            "platform": scenario.platform,
            "trust_score": scenario.trust_score,
            "age_minutes": scenario.age_minutes,
            "direction": scenario.direction,
            "claim_type": scenario.claim_type,
            "horizon_minutes": scenario.horizon_minutes,
        },
        "decision": "HOLD_FOR_HUMAN_REVIEW",
        "note": "This is a model estimate from reviewed historical paper outcomes. It is not a market forecast, trade instruction, or brokerage order.",
    }
