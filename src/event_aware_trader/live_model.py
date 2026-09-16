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

# ---------------------------------------------------------------------------
# DISABLED 2026-09-16. The learned ranking may not influence any trade.
# ---------------------------------------------------------------------------
#
# WHY. `train_live_model` reports an AUC from a single 75/25 time cut with no
# purge, and then refits on ALL the data and ships THAT model carrying the
# earlier number. Re-measured under purged, embargoed walk-forward folds
# scoring only the model that would actually have been deployed:
#
#     train AUC 0.9983      out-of-sample AUC 0.4839      gap 0.5144
#     worst fold 0.3309     0 of 5 folds beat a constant base-rate forecast
#     shuffled-label control 0.5113, so the pipeline is sound and the 0.4839
#     is a real measurement rather than an artifact of the new split
#
# It memorises almost perfectly and is worse than a coin out of sample. The
# 0.5424 that marked it USABLE is not evidence of predictive ability and must
# never be cited as such again. Full audit: scripts/audit_live_model.py,
# lineage row M-f2ba8495dc75f8cf, status OBSERVE_ONLY.
#
# WHY A CONSTANT AND NOT JUST THE STATUS FIELD. Editing data/live-model.json
# to UNPROVEN works until the next retrain, which runs every time a trade
# closes and re-derives the status from the same leaky 0.53 rule. A flag the
# trainer cannot clear is the only disable that survives its own retraining.
#
# TO RE-ENABLE: a model must first pass `modelgov.trust.assess` with status
# TRUSTED - purged walk-forward, no memorisation gap, calibration beating the
# base rate, and a shuffled control that stays near chance - and then be
# promoted deliberately. Flipping this back without that is the exact failure
# it was added to stop.
LEARNED_RANKING_ENABLED = False


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
        # THE KILL SWITCH COMES FIRST, and it is checked here rather than at
        # the call sites because `usable` is the single gate the live loop
        # consults before letting a score touch candidate ordering.
        if not LEARNED_RANKING_ENABLED:
            return False
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


#: The corpus schema version. v2 separates the two timestamps below; v1
#: rows carry only `at`, whose meaning depends on how they were produced.
SCHEMA_VERSION = 2


def append_example(features: Dict[str, float], realized_r: float, symbol: str,
                   path: Optional[Path] = None,
                   decision_at: Optional[str] = None) -> None:
    """Record one completed trade, dated by WHEN ITS FEATURES WERE KNOWABLE.

    THE DEFECT THIS FIXES. `at` used to be `datetime.now()` at the moment
    the row was written, which is when the trade CLOSED. The features in
    that same row describe the ENTRY. A mean-reversion trade is held up to
    20 sessions, so the stamp could sit up to 20 sessions after the
    information it claims to date.

    That is not merely untidy. Every purge and embargo in the validation
    engine is computed from this field. A row stamped at its exit looks
    newer than it is, so it can be placed on the training side of a
    boundary its FEATURES predate comfortably while its OUTCOME resolved
    inside the validation window - which is precisely the overlap purging
    exists to remove. With 5 live rows in 1,531 it changed nothing; it
    would have grown with every closed trade.

    The convention, stated once: **the timestamp of an observation is the
    moment its features were knowable.** The outcome is allowed to become
    known later, and is recorded separately rather than being allowed to
    move the observation.

    `at` keeps its name and now carries the decision timestamp, so every
    existing reader - the trainer's sort, the walk-forward splitter, the
    lineage fingerprint - gets the corrected meaning without a change.
    `outcome_at` preserves what `at` used to hold.
    """
    # Resolved at CALL time, not bound at import. Binding the default to
    # the module constant meant a caller redirecting TRAINING_PATH was
    # ignored, and the only way to redirect it was to patch
    # `__defaults__` - which silently rebinds the WRONG parameter the
    # moment another one is added. That is exactly what happened when
    # `decision_at` was introduced: a one-element __defaults__ landed on
    # it, `path` lost its default, and every append raised into a
    # swallowing except-clause. Reading the constant here removes the
    # footgun instead of documenting it.
    path = Path(path) if path is not None else TRAINING_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    outcome_at = datetime.now(timezone.utc).isoformat()
    # Fall back to the outcome time only when the caller genuinely has no
    # entry timestamp, and SAY SO in the row rather than letting a
    # fallback masquerade as a decision date.
    known = decision_at or outcome_at
    row = {
        "at": known,
        "decision_at": known,
        "outcome_at": outcome_at,
        "timestamp_convention": ("decision" if decision_at
                                 else "outcome_used_as_fallback"),
        "schema": SCHEMA_VERSION,
        "symbol": symbol,
        "f": {k: float(features.get(k, 0.0)) for k in LIVE_FEATURES},
        "r": float(realized_r),
        "label": 1 if realized_r >= 1.0 else 0,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def load_training(path: Optional[Path] = None) -> List[Dict[str, object]]:
    # Call-time, matching append_example. These two must agree about
    # where the corpus lives, and a default bound at import cannot
    # follow a caller that redirects TRAINING_PATH.
    path = Path(path) if path is not None else TRAINING_PATH
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
        # The written status must agree with the kill switch, or the file
        # keeps re-labelling itself USABLE on every retrain and anyone
        # reading it is misled. Measured on 2026-09-16: the file was set to
        # UNPROVEN by hand at 18:05:43 and a retrain rewrote it to USABLE at
        # 18:08:01, two and a half minutes later. `usable` was already False
        # throughout because the switch is checked first, so no trade was
        # affected - but the file said the opposite of the truth.
        status=("USABLE" if (auc >= 0.53 and LEARNED_RANKING_ENABLED)
                else "UNPROVEN"),
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
