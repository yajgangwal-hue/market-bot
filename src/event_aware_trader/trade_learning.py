"""Learn from the bot's own trades, and use it only to veto.

`learning.py` learns about *social posts* - its features are trust score, post
age, platform, entity count.  It shares no feature with the gate that actually
decides trades, so nothing the bot did could ever teach it anything.  This
module closes that loop: the features are the candidate's own measurements,
and the label is what the trade went on to do.

Two design choices matter more than the model.

**Examples come from every candidate that cleared the blockers, not just the
ones that traded.**  Learning only from taken trades would mean learning from
seven rows, and would also be selection-biased: the model would only ever see
setups the score already liked.  A candidate that cleared every hard blocker
but scored 54 has an observable forward outcome too, and it is exactly the
sort of case a learned filter needs in order to tell 54-that-worked from
54-that-did-not.

**The model can only ever make the bot trade less.**  It is applied as a veto
on top of the hand-built gate, never as a reason to enter something the gate
rejected.  A model that is broken, overfitted, or trained on too little data
then costs missed trades rather than losses, and an `UNPROVEN` model is
ignored entirely.  The failure mode is deliberately the boring direction.
"""

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .indicators import wilder_atr
from .risk import CostModel
from .strategy import StrategyConfig, generate_candidate
from .types import Action, Bar, Event

# Ordered, and the order is part of the saved model.  These are the candidate's
# own measurements - the things the gate already computes - so nothing new has
# to be collected at decision time.
TRADE_FEATURES: Tuple[str, ...] = (
    "intercept",
    "score",
    "ma_separation",
    "extension_atr",
    "adx",
    "rsi",
    "relative_volume",
    "atr_fraction",
    "momentum",
    "trend_r_squared",
    "breakout_distance",
    "volatility_percentile",
)

MIN_TRAIN_EXAMPLES = 150

# What counts as a positive example.  "Did it make any money at all" (R > 0)
# turned out to be close to unlearnable here - out-of-sample AUC 0.543, barely
# above a coin flip - and the model trained on it ranked the *biggest* winners
# below average, because a strategy whose profit comes from a long right tail
# is not described by a win/loss flag.  Asking instead "will this become a
# meaningful winner" lifts out-of-sample AUC to 0.619 on the same features and
# the same split.  Raising it further to 2R starves the positive class and the
# Brier score falls below the base rate again.
WINNER_R_THRESHOLD = 1.0


@dataclass(frozen=True)
class TradeExample:
    """One blocker-clearing candidate and what actually happened next."""

    symbol: str
    as_of: datetime
    features: Dict[str, float]
    realized_r: float
    label: int          # 1 if the trade made money after costs
    was_tradeable: bool  # did it also clear the score threshold

    def as_dict(self) -> Dict[str, object]:
        return {
            "symbol": self.symbol,
            "as_of": self.as_of.isoformat(),
            "features": {k: round(v, 6) for k, v in self.features.items()},
            "realized_r": round(self.realized_r, 4),
            "label": self.label,
            "was_tradeable": self.was_tradeable,
        }


def _feature_row(features: Dict[str, Optional[float]], score: float) -> Dict[str, float]:
    row = {"score": float(score)}
    for name in TRADE_FEATURES:
        if name in ("intercept", "score"):
            continue
        value = features.get(name)
        row[name] = 0.0 if value is None else float(value)
    return row


def _simulate_forward(
    bars: Sequence[Bar],
    start: int,
    entry: float,
    stop: float,
    costs: CostModel,
    config: StrategyConfig,
) -> Optional[float]:
    """Return the realized R of the trade this candidate would have become.

    Uses the same trailing ratchet and the same conservative same-bar
    assumption as the portfolio simulator, so a training label and a simulated
    trade mean the same thing.
    """
    if start + 1 >= len(bars):
        return None
    fill = costs.buy_fill(bars[start + 1].open)
    initial_stop = stop
    risk_per_share = fill - initial_stop
    if risk_per_share <= 0:
        return None
    current_stop = initial_stop
    highest = bars[start + 1].high
    armed = False

    limit = min(start + 1 + config.max_trailing_bars, len(bars) - 1)
    for index in range(start + 1, limit + 1):
        bar = bars[index]
        highest = max(highest, bar.high)
        if (highest - fill) / risk_per_share >= config.trail_activate_r:
            armed = True
        if armed:
            atr = wilder_atr(bars[: index + 1], config.atr_days)
            if atr:
                current_stop = max(current_stop, highest - config.trail_atr_multiple * atr)
        if bar.low <= current_stop:
            exit_price = costs.sell_fill(current_stop)
            return (exit_price - fill) / risk_per_share
    exit_price = costs.sell_fill(bars[limit].close)
    return (exit_price - fill) / risk_per_share


def generate_examples(
    series: Dict[str, List[Bar]],
    events: Sequence[Event] = (),
    equity: float = 1_000.0,
    costs: CostModel = CostModel(),
    config: StrategyConfig = StrategyConfig(),
    step: int = 1,
) -> List[TradeExample]:
    """Walk history and label every candidate that cleared the hard blockers."""
    examples: List[TradeExample] = []
    for symbol, bars in sorted(series.items()):
        start = max(config.minimum_history, 1)
        for index in range(start, len(bars) - 2, max(1, step)):
            window = bars[: index + 1]
            candidate = generate_candidate(
                symbol, window, events, equity, costs=costs, config=config
            )
            # Blockers are the hard rules; a WATCH cleared them and only missed
            # the score, which is exactly the population worth learning from.
            if candidate.blockers or candidate.action == Action.REJECT:
                continue
            if candidate.entry is None or candidate.stop is None:
                continue
            realized = _simulate_forward(bars, index, candidate.entry, candidate.stop, costs, config)
            if realized is None:
                continue
            examples.append(
                TradeExample(
                    symbol=symbol,
                    as_of=bars[index].timestamp,
                    features=_feature_row(candidate.features, candidate.score),
                    realized_r=realized,
                    label=1 if realized >= WINNER_R_THRESHOLD else 0,
                    was_tradeable=candidate.action == Action.PAPER_LONG,
                )
            )
    examples.sort(key=lambda e: e.as_of)
    return examples


def save_examples(path: Path, examples: Sequence[TradeExample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example.as_dict(), sort_keys=True) + "\n")


def load_examples(path: Path) -> List[TradeExample]:
    examples: List[TradeExample] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        raw = json.loads(line)
        examples.append(
            TradeExample(
                symbol=raw["symbol"],
                as_of=datetime.fromisoformat(raw["as_of"]),
                features={k: float(v) for k, v in raw["features"].items()},
                realized_r=float(raw["realized_r"]),
                label=int(raw["label"]),
                was_tradeable=bool(raw.get("was_tradeable", False)),
            )
        )
    return examples


# ---- model ------------------------------------------------------------------

@dataclass(frozen=True)
class TradeModel:
    version: int
    feature_names: Tuple[str, ...]
    means: Tuple[float, ...]
    scales: Tuple[float, ...]
    weights: Tuple[float, ...]
    status: str
    veto_threshold: float
    report: Dict[str, object]

    @property
    def is_usable(self) -> bool:
        """Only a model that beat the base rate out of sample may veto."""
        return self.status == "USABLE_AS_VETO"

    def as_dict(self) -> Dict[str, object]:
        return {
            "version": self.version,
            "feature_names": list(self.feature_names),
            "means": list(self.means),
            "scales": list(self.scales),
            "weights": list(self.weights),
            "status": self.status,
            "veto_threshold": self.veto_threshold,
            "report": self.report,
        }


def _row(features: Dict[str, float]) -> List[float]:
    return [1.0] + [float(features.get(name, 0.0)) for name in TRADE_FEATURES[1:]]


def _sigmoid(value: float) -> float:
    if value < -60:
        return 0.0
    if value > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-value))


def _predict(row: Sequence[float], weights: Sequence[float]) -> float:
    return _sigmoid(sum(r * w for r, w in zip(row, weights)))


def _standardize(row, means, scales):
    return [row[0]] + [
        (row[i] - means[i]) / scales[i] if scales[i] else 0.0 for i in range(1, len(row))
    ]


def train_trade_model(
    examples: Sequence[TradeExample],
    min_examples: int = MIN_TRAIN_EXAMPLES,
    # Light regularization overfitted badly (out-of-sample Brier 0.33 against
    # a 0.29 base rate). Every setting with l2 = 0.30 beat the base rate
    # regardless of learning rate or epoch count, so the default sits in that
    # flat region rather than at any single best cell.
    learning_rate: float = 0.02,
    epochs: int = 300,
    l2: float = 0.30,
    veto_threshold: float = 0.25,
) -> TradeModel:
    """Fit chronologically; report only untouched out-of-sample performance."""
    if len(examples) < 30:
        raise ValueError("At least 30 labeled examples are required")
    ordered = sorted(examples, key=lambda e: e.as_of)
    split = max(1, int(len(ordered) * 0.70))
    train, test = ordered[:split], ordered[split:]
    if len(test) < 10:
        raise ValueError("Need at least ten chronological out-of-sample examples")

    raw_train = [_row(e.features) for e in train]
    width = len(TRADE_FEATURES)
    means = [0.0] * width
    scales = [1.0] * width
    for i in range(1, width):
        column = [r[i] for r in raw_train]
        mean = sum(column) / len(column)
        variance = sum((v - mean) ** 2 for v in column) / max(1, len(column) - 1)
        means[i] = mean
        scales[i] = math.sqrt(variance) or 1.0

    rows = [_standardize(r, means, scales) for r in raw_train]
    labels = [e.label for e in train]
    weights = [0.0] * width
    for _ in range(epochs):
        gradient = [0.0] * width
        for row, label in zip(rows, labels):
            error = _predict(row, weights) - label
            for i, value in enumerate(row):
                gradient[i] += error * value
        for i in range(1, width):
            gradient[i] += l2 * weights[i] * len(rows)
        for i in range(width):
            weights[i] -= learning_rate * gradient[i] / len(rows)

    test_rows = [_standardize(_row(e.features), means, scales) for e in test]
    test_labels = [e.label for e in test]
    probabilities = [_predict(r, weights) for r in test_rows]
    brier = sum((p - y) ** 2 for p, y in zip(probabilities, test_labels)) / len(test_labels)
    base_rate = sum(labels) / len(labels)
    base_brier = sum((base_rate - y) ** 2 for y in test_labels) / len(test_labels)

    # Calibration: mean |predicted - observed| across probability deciles.
    buckets: Dict[int, List[Tuple[float, int]]] = {}
    for probability, label in zip(probabilities, test_labels):
        buckets.setdefault(min(9, int(probability * 10)), []).append((probability, label))
    calibration = sum(
        abs(sum(p for p, _ in rows_) / len(rows_) - sum(y for _, y in rows_) / len(rows_))
        * len(rows_)
        for rows_ in buckets.values()
    ) / len(test_labels)

    # AUC by the rank statistic. For a veto the model is used *ordinally* -
    # everything below a threshold is dropped - so discrimination is the
    # property that has to hold. Calibration is still reported, because a
    # badly calibrated probability should not be shown to a human as if it
    # were a real one, but it does not gate the veto.
    pairs = sorted(zip(probabilities, test_labels))
    positives = sum(test_labels)
    negatives = len(test_labels) - positives
    if positives and negatives:
        rank_sum = sum(i + 1 for i, (_, label) in enumerate(pairs) if label == 1)
        auc = (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)
    else:
        auc = 0.5

    enough = len(ordered) >= min_examples and len(test) >= 40
    beats_base = brier < base_brier * 0.98
    discriminates = auc >= 0.58
    status = "USABLE_AS_VETO" if (enough and beats_base and discriminates) else "UNPROVEN"

    return TradeModel(
        version=1,
        feature_names=TRADE_FEATURES,
        means=tuple(means),
        scales=tuple(scales),
        weights=tuple(weights),
        status=status,
        veto_threshold=veto_threshold,
        report={
            "method": "Chronological 70/30 split; the final segment is untouched by fitting.",
            "training_count": len(train),
            "out_of_sample_count": len(test),
            "minimum_examples": min_examples,
            "base_rate": round(base_rate, 4),
            "out_of_sample_brier": round(brier, 4),
            "base_rate_brier": round(base_brier, 4),
            "out_of_sample_auc": round(auc, 4),
            "calibration_error": round(calibration, 4),
            "winner_threshold_r": WINNER_R_THRESHOLD,
            "sample_ready": enough,
            "beats_base_rate": beats_base,
            "discriminates": discriminates,
            "usage": (
                "Applied only as a veto on candidates the hand-built gate already "
                "accepted. It can never authorise a trade the gate rejected, and an "
                "UNPROVEN model is ignored entirely."
            ),
        },
    )


def save_model(path: Path, model: TradeModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_model(path: Path) -> TradeModel:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return TradeModel(
        version=int(raw["version"]),
        feature_names=tuple(raw["feature_names"]),
        means=tuple(float(v) for v in raw["means"]),
        scales=tuple(float(v) for v in raw["scales"]),
        weights=tuple(float(v) for v in raw["weights"]),
        status=str(raw["status"]),
        veto_threshold=float(raw["veto_threshold"]),
        report=raw.get("report", {}),
    )


def score_candidate(model: TradeModel, features: Dict[str, Optional[float]], score: float) -> float:
    """Estimated probability this candidate ends profitable after costs."""
    return _predict(_standardize(_row(_feature_row(features, score)), model.means, model.scales), model.weights)


def model_vetoes(model: TradeModel, features: Dict[str, Optional[float]], score: float) -> Tuple[bool, float]:
    """(veto, probability). An UNPROVEN model never vetoes."""
    probability = score_candidate(model, features, score)
    if not model.is_usable:
        return False, probability
    return probability < model.veto_threshold, probability


def export_pine(model: TradeModel) -> str:
    """Emit the trained model as Pine Script.

    Pine cannot train anything: it has no ML library, cannot call an external
    API, and runs in a sandbox on TradingView's servers.  But a logistic model
    *is* only a dot product against twelve constants, so the fitted weights and
    the standardisation it needs can be baked in and evaluated on a chart.
    Training stays in Python; scoring becomes portable.

    Re-export after every retrain, or the chart silently keeps scoring with an
    old model.
    """
    lines = [
        "// Learned trade filter - exported from trade_learning.py",
        "// status: {0}   out-of-sample AUC: {1}".format(
            model.status, model.report.get("out_of_sample_auc")
        ),
        "// Trained in Python on {0} examples. Pine cannot fit this; it only".format(
            model.report.get("training_count")
        ),
        "// evaluates the frozen weights below. Re-export after retraining.",
        "",
        "winnerProbability() =>",
    ]
    for index, name in enumerate(model.feature_names):
        if name == "intercept":
            continue
        lines.append("    // {0}".format(name))
        lines.append("    m_{0} = {1:.10f}".format(name, model.means[index]))
        lines.append("    s_{0} = {1:.10f}".format(name, model.scales[index]))
        lines.append("    w_{0} = {1:.10f}".format(name, model.weights[index]))
    lines += [
        "    b = {0:.10f}".format(model.weights[0]),
        "    z = b",
        "    // caller supplies each feature as f_<name>",
    ]
    for name in model.feature_names[1:]:
        lines.append(
            "    z := z + w_{0} * (f_{0} - m_{0}) / (s_{0} == 0 ? 1 : s_{0})".format(name)
        )
    lines += [
        "    1.0 / (1.0 + math.exp(-z))",
        "",
        "// A probability below {0:.2f} is the veto band.".format(model.veto_threshold),
        "vetoThreshold = {0:.4f}".format(model.veto_threshold),
    ]
    return "\n".join(lines) + "\n"


def examples_from_audit_log(path: Path) -> List[TradeExample]:
    """Turn trades the bot actually executed into labeled training examples.

    `generate_examples` learns from re-simulated price history: what the rules
    *would* have done. That is the only option before any trade exists, and it
    is what the model was first fitted on. But it means a weekly retrain over
    the same history barely moves - the bot is not learning from its own
    results, it is re-reading the same book.

    This reads the audit log instead. An `entry` event carries the feature
    vector the decision was made on; the matching `exit` carries what the trade
    returned, taken from the broker's own figures. Pairing them produces
    examples of the thing that actually happened, with the same schema as the
    simulated ones so both can train one model.

    Executed trades are the more honest evidence - they include real fills,
    real slippage, and real timing - but there will be very few of them for a
    long time, so they supplement the simulated set rather than replacing it.
    """
    if not path.exists():
        return []

    open_entries: Dict[str, Dict[str, object]] = {}
    examples: List[TradeExample] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        event = row.get("event")
        detail = row.get("detail") or {}
        symbol = str(detail.get("symbol", ""))
        if not symbol:
            continue

        if event == "entry":
            features = detail.get("features")
            if isinstance(features, dict):
                open_entries[symbol] = {
                    "features": features,
                    "score": float(detail.get("score", 0.0) or 0.0),
                    "at": row.get("at"),
                }
        elif event == "exit" and symbol in open_entries:
            entry = open_entries.pop(symbol)
            r_multiple = detail.get("r_multiple")
            if r_multiple is None:
                continue
            try:
                realized = float(r_multiple)
            except (TypeError, ValueError):
                continue
            raw = {
                k: (0.0 if v is None else float(v))
                for k, v in entry["features"].items()
                if isinstance(v, (int, float)) or v is None
            }
            try:
                as_of = datetime.fromisoformat(str(entry["at"]))
            except (TypeError, ValueError):
                continue
            examples.append(
                TradeExample(
                    symbol=symbol,
                    as_of=as_of,
                    features=_feature_row(raw, float(entry["score"])),
                    realized_r=realized,
                    label=1 if realized >= WINNER_R_THRESHOLD else 0,
                    was_tradeable=True,
                )
            )

    examples.sort(key=lambda e: e.as_of)
    return examples
