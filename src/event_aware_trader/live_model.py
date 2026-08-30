"""Train, persist, and serve the cross-sectional model for live decisions.

This is the strongest model the project found: out-of-sample AUC 0.5665 with
cross-sectional and market-context features, against 0.50 for everything that
came before it. It is wired here into the path the bot actually trades on,
rather than living only in offline analysis.

It learns continuously. `update_from_trades` folds every closed trade into
the training set, so the record the bot builds becomes the data it is next
fitted on, and `train_live_model` refits from scratch each time so a bad run
of trades cannot permanently poison a weight.
"""

import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .cross_sectional import CROSS_SECTIONAL_FEATURES, build_snapshot, cross_sectional_features
from .types import Bar

LIVE_FEATURES: Tuple[str, ...] = (
    "above_ma200", "ma20_over_ma50", "mom21", "mom63", "mom126",
    "vol21", "pos52",
) + CROSS_SECTIONAL_FEATURES

MODEL_PATH = Path("data/live-model.json")
TRAINING_PATH = Path("data/live-training.jsonl")


@dataclass
class LiveModel:
    """A gradient-boosted model plus everything needed to reproduce it."""

    trained_at: str
    n_examples: int
    test_auc: float
    feature_names: Tuple[str, ...]
    payload: Dict[str, object] = field(default_factory=dict)
    status: str = "UNPROVEN"

    @property
    def usable(self) -> bool:
        return self.status == "USABLE" and self.test_auc >= 0.53

    def as_dict(self) -> Dict[str, object]:
        return {
            "trained_at": self.trained_at,
            "n_examples": self.n_examples,
            "test_auc": round(self.test_auc, 4),
            "feature_names": list(self.feature_names),
            "status": self.status,
            "payload": self.payload,
        }


def live_features(symbol: str, bars: Sequence[Bar], snapshot) -> Dict[str, float]:
    """The feature vector for one symbol, matching what the model was fitted on."""
    closes = [b.close for b in bars]
    out = {name: 0.0 for name in LIVE_FEATURES}
    if len(closes) < 210 or closes[-1] <= 0:
        out.update({k: 0.5 for k in ("rank_mom21", "rank_mom63", "rank_mom126",
                                     "rank_vol", "rank_pos52", "pos52")})
        return out

    def change(window):
        return closes[-1] / closes[-1 - window] - 1.0 if len(closes) > window and closes[-1 - window] > 0 else 0.0

    ma20 = sum(closes[-20:]) / 20.0
    ma50 = sum(closes[-50:]) / 50.0
    ma200 = sum(closes[-200:]) / 200.0
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(len(closes) - 21, len(closes)) if closes[i - 1] > 0]
    mean = sum(rets) / len(rets) if rets else 0.0
    vol21 = math.sqrt(sum((r - mean) ** 2 for r in rets) / max(1, len(rets) - 1)) if len(rets) > 1 else 0.0
    window = bars[-252:] if len(bars) >= 252 else bars
    high, low = max(b.high for b in window), min(b.low for b in window)

    out.update({
        "above_ma200": 1.0 if closes[-1] > ma200 else 0.0,
        "ma20_over_ma50": (ma20 / ma50 - 1.0) if ma50 > 0 else 0.0,
        "mom21": change(21), "mom63": change(63), "mom126": change(126),
        "vol21": vol21,
        "pos52": ((closes[-1] - low) / (high - low)) if high > low else 0.5,
    })
    out.update(cross_sectional_features(symbol, snapshot))
    return out


def append_example(features: Dict[str, float], realized_r: float, symbol: str,
                   path: Path = TRAINING_PATH) -> None:
    """Record one completed trade as a training row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "at": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "f": {k: float(features.get(k, 0.0)) for k in LIVE_FEATURES},
        "r": float(realized_r),
        "label": 1 if realized_r >= 1.0 else 0,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def load_training(path: Path = TRAINING_PATH) -> List[Dict[str, object]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def train_live_model(
    rows: Sequence[Dict[str, object]],
    model_path: Path = MODEL_PATH,
    min_examples: int = 500,
) -> Optional[LiveModel]:
    """Refit from scratch on every example available.

    Refitting rather than updating means a bad stretch of trades cannot leave
    a permanent mark on a weight - the model is always the best explanation of
    the whole record, not the accumulated residue of its worst week.
    """
    try:
        import numpy as np
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.metrics import roc_auc_score
        import pickle, base64
    except ImportError:
        return None

    if len(rows) < min_examples:
        return None
    rows = sorted(rows, key=lambda r: r.get("at", r.get("d", "")))
    X = np.nan_to_num(np.array([[float(r["f"].get(k, 0.0)) for k in LIVE_FEATURES] for r in rows], float))
    y = np.array([int(r["label"]) for r in rows], int)
    if len(set(y.tolist())) < 2:
        return None

    cut = int(len(y) * 0.75)
    model = HistGradientBoostingClassifier(
        max_iter=300, max_depth=4, learning_rate=0.05, random_state=0)
    model.fit(X[:cut], y[:cut])
    try:
        auc = float(roc_auc_score(y[cut:], model.predict_proba(X[cut:])[:, 1]))
    except ValueError:
        auc = 0.5

    # Refit on everything for the model actually used, having measured on the
    # holdout for the score that is reported.
    model.fit(X, y)
    blob = base64.b64encode(pickle.dumps(model)).decode("ascii")
    live = LiveModel(
        trained_at=datetime.now(timezone.utc).isoformat(),
        n_examples=len(rows),
        test_auc=auc,
        feature_names=LIVE_FEATURES,
        payload={"sklearn_pickle_b64": blob},
        status="USABLE" if auc >= 0.53 else "UNPROVEN",
    )
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text(json.dumps(live.as_dict(), indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
    return live


def load_live_model(path: Path = MODEL_PATH):
    """Return (LiveModel, estimator) or (None, None)."""
    if not path.exists():
        return None, None
    try:
        import base64, pickle
        raw = json.loads(path.read_text(encoding="utf-8"))
        blob = raw.get("payload", {}).get("sklearn_pickle_b64")
        if not blob:
            return None, None
        estimator = pickle.loads(base64.b64decode(blob))
        live = LiveModel(
            trained_at=raw["trained_at"], n_examples=int(raw["n_examples"]),
            test_auc=float(raw["test_auc"]), feature_names=tuple(raw["feature_names"]),
            status=raw.get("status", "UNPROVEN"),
        )
        return live, estimator
    except Exception:
        return None, None


def score(estimator, features: Dict[str, float]) -> float:
    """Probability this candidate becomes a meaningful winner."""
    try:
        import numpy as np
        row = np.nan_to_num(np.array([[float(features.get(k, 0.0)) for k in LIVE_FEATURES]], float))
        return float(estimator.predict_proba(row)[0, 1])
    except Exception:
        return 0.5
