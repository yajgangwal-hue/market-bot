"""P7/P8. Keep the research process out of the evaluation period.

Two separate leaks, two separate remedies, and they are often conflated:

  PURGE     a trade that OPENED before the configuration froze but closed
            after it belongs to neither period cleanly. Its entry decision
            used a rule chosen with knowledge of the historical data; its
            outcome lands in the evaluation window. Straddling observations
            are removed from the evaluation set.

  EMBARGO   even a trade opened entirely after the freeze can be tainted,
            because the researcher saw market conditions up to the freeze
            date and those conditions persist. The persistence horizon for
            this strategy is its own holding cap - a position is resolved
            within 20 sessions - so 20 sessions after the freeze are set
            aside before the evaluation period begins.

THE EMBARGO LENGTH IS NOT A CHOICE. It is `MeanReversionConfig.max_holding_bars`,
the number of sessions after which every position is closed by the rule. It
must never be tuned: an embargo picked because it improved the result would
be the precise failure this module exists to prevent, so `embargo_sessions`
reads the strategy config rather than taking a parameter.

THE FREEZE DATE IS NOT A CHOICE EITHER. It is derived from the experiment
registry - the date of the last entry that accepted or reverted a change to
the shipped configuration. On 2026-09-16 that is EXP-0017, 2026-09-11, which
independently coincides with `research.FORWARD_START`.
"""

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Sequence

# Decisions that changed what the bot actually runs. A "measured" or
# "rejected" experiment consumed data but altered no parameter, so it does
# not move the freeze date - only a change to the shipped configuration does.
CONFIG_CHANGING = ("accepted", "reverted")


@dataclass
class EvaluationWindow:
    freeze: date                  # last change to the shipped configuration
    embargo_sessions: int         # the strategy's own information horizon
    clean_from: Optional[date]    # first session admissible as evidence
    sessions_embargoed: int

    def as_dict(self) -> Dict[str, object]:
        return {
            "freeze": self.freeze.isoformat(),
            "embargo_sessions": self.embargo_sessions,
            "clean_from": self.clean_from.isoformat() if self.clean_from else None,
            "sessions_embargoed": self.sessions_embargoed,
        }


def freeze_date(registry_rows: Sequence[Dict]) -> Optional[date]:
    """The last date any experiment changed the shipped configuration.

    Reads the registry rather than accepting an argument, so the boundary
    cannot be moved by whoever wants a longer clean period.
    """
    dates = [row["when"] for row in registry_rows
             if row.get("decision") in CONFIG_CHANGING and row.get("when")]
    if not dates:
        return None
    return date.fromisoformat(max(dates))


def embargo_sessions(config=None) -> int:
    """The strategy's information horizon, in sessions. Not a free parameter."""
    if config is None:
        from .mean_reversion import MeanReversionConfig
        config = MeanReversionConfig()
    return int(config.max_holding_bars)


def evaluation_window(registry_rows: Sequence[Dict],
                      sessions: Sequence[date],
                      config=None) -> EvaluationWindow:
    """Where clean evaluation may begin, given the registry and the calendar.

    `sessions` is the ordered list of trading days that actually occurred -
    the embargo is counted in SESSIONS, not calendar days, because the
    holding cap is counted in sessions.
    """
    freeze = freeze_date(registry_rows)
    horizon = embargo_sessions(config)
    if freeze is None:
        return EvaluationWindow(date.min, horizon, None, 0)
    after = [d for d in sorted(sessions) if d > freeze]
    embargoed = after[:horizon]
    clean = after[horizon] if len(after) > horizon else None
    return EvaluationWindow(freeze, horizon, clean, len(embargoed))


def is_straddling(entry: date, exit_: date, boundary: date) -> bool:
    """True when a trade spans the freeze: opened before, closed after."""
    return entry <= boundary < exit_


def purge(trades: Sequence, window: EvaluationWindow) -> Dict[str, List]:
    """Split trades into clean / straddling / embargoed / pre-freeze.

    Nothing is deleted. Every trade lands in exactly one bucket and the
    counts are reported, because a purge that silently drops observations is
    indistinguishable from one that drops the inconvenient ones.
    """
    out = {"clean": [], "straddling": [], "embargoed": [], "pre_freeze": []}
    for t in trades:
        entry = t.entry_time.date() if hasattr(t.entry_time, "date") else t.entry_time
        exit_ = t.exit_time.date() if hasattr(t.exit_time, "date") else t.exit_time
        if is_straddling(entry, exit_, window.freeze):
            out["straddling"].append(t)
        elif exit_ <= window.freeze:
            out["pre_freeze"].append(t)
        elif window.clean_from is None or entry < window.clean_from:
            out["embargoed"].append(t)
        else:
            out["clean"].append(t)
    return out


def summarise(buckets: Dict[str, List]) -> Dict[str, int]:
    return {name: len(items) for name, items in sorted(buckets.items())}
