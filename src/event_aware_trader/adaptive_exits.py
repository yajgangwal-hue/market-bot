"""Adaptive volatility exits - owner directive, 2026-09-28, recorded as EXP-0055.

"implement so that the bot can set its own take profits and stop losses based
on the volatility and that it can get better at knowing where to set that with
time."

WHAT IT DOES

- Every new position gets a stop k_sl x ATR below its entry and a take profit
  k_tp x ATR above it. ATR is the stock's own 14-day average daily range when
  it is bought, so a jumpy stock gets wider levels than a calm one. Both start
  at 2.5 ATR: the stop where it has always been, the target at 1R.
- The stop rests at the broker as before. The take profit is checked every
  cycle against the broker's own mark; a position at or above it is sold
  through the same path as every other exit. The bounce exit (RSI >= 60) and
  the 20-session cap stay, and whichever comes first wins.
- LEARNING. After the close, at most once every 20 sessions, the bot replays
  every finished trade under the levels in force and one step either way for
  each: target +/-0.5 ATR, stop +/-0.25 ATR. A finished trade is one with 20
  sessions of daily bars after its entry in the bot's own price files. The bot
  moves one step, inside fixed bounds, only when that neighbour would have
  earned more per unit of risk, trade by trade, by clearly more than its own
  noise, in both halves of the record. That means: paired mean above 3
  standard errors and above 0.05 R, positive in the older and the newer half
  of the trades, on at least 100 of them. Every evaluation, and why it moved
  or stayed, is kept in data/adaptive-exits.json.

  WHY SO STRICT. Measured on 2026-09-28 by simulation:
  - Paired R differences between exit levels are badly skewed. A wider target
    usually wins a little and occasionally loses a lot, and 20 trades rarely
    contain the losses.
  - A 2-standard-error rule on 20 trades therefore moved on pure noise in 59%
    of evaluations. With a real edge it moved the right way in only 42%, so it
    did not learn - it chased luck.
  - This rule moves on pure noise in 7.2% of evaluations, and with a real
    +0.05 ATR/day edge moves the right way in 11.0% and the wrong way in 5.2%.
  - At about 70 trades a year, 100 finished trades is well over a year away.
    Learning here is slow because the evidence is thin, not by choice.

EXP-0057 (2026-10-04, owner's order): THE TAKE PROFIT SITS AT THE BOUNCE PRICE

- take_profit_mode "bounce", the default, replaces the fixed k_tp x ATR
  target with the bounce price: the close that would put RSI(14) at 60, from
  the closes through the last completed session (`indicators.bounce_price`).
  That is where the frozen rule's own exit fires, so it is not a new
  parameter. It moves once a day, and the broker order moves with it.
- H-0038 replayed the 698 decade trades: the bounce price earned +0.144R a
  trade against +0.115R for the 2.5-ATR target. That is +0.029R (t 1.64),
  positive in both halves and under every exit-cost assumption, but short of
  the sealed t >= 2: evidence 'weak'.
- In this mode the learner replays trades with the bounce price as the target
  and steps only the stop. The take-profit multiple stays on file, unused.
  "atr" restores EXP-0055's fixed target exactly.

WHAT IT IS NOT

- It is not backed by the research. No take profit found beats the bounce exit
  for this strategy: EXP-0050, and H-0026, where the level learned from the
  strategy's own trades was "none". This is the owner's decision, recorded
  with evidence 'contradictory'.
- The learned VALUES are not fingerprinted; the PROCEDURE is. The
  AdaptiveExitConfig on AutoTradeConfig is part of the frozen configuration,
  so changing any number below moves the fingerprint. The learner moving k_tp
  or k_sl by its own rules does not.
"""

import json
import math
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import fmean, stdev
from typing import Dict, List, Optional, Sequence, Tuple

from .indicators import bounce_price, rsi

PARAMS_FILE_NAME = "adaptive-exits.json"
TAKE_PROFIT_MODES = ("bounce", "atr")


@dataclass(frozen=True)
class AdaptiveExitConfig:
    """The frozen procedure. Every field is part of the fingerprint."""

    initial_take_profit_atr: float = 2.5
    initial_stop_atr: float = 2.5
    take_profit_bounds: Tuple[float, float] = (1.5, 6.0)
    stop_bounds: Tuple[float, float] = (2.0, 3.5)
    take_profit_step: float = 0.5
    stop_step: float = 0.25
    # See WHY SO STRICT above: every one of these was chosen by simulation to
    # keep pure noise from moving the levels, and none may be loosened
    # without re-measuring that.
    min_trades: int = 100
    min_sessions_between_evaluations: int = 20
    min_improvement_r: float = 0.05
    improvement_standard_errors: float = 3.0
    require_both_halves: bool = True
    # Entries before this date were made under the pre-freeze setup, several
    # with a stale entry reference; they would teach the learner wrong levels.
    learning_start: str = "2026-09-14"
    round_trip_cost: float = 0.0012
    # EXP-0056 (2026-10-04, owner's order). The take profit RESTS AT THE
    # BROKER as the limit half of a one-cancels-other order whose other half
    # is the protective stop, so both levels are real orders: visible on any
    # chart connected to the account, and working while this machine is off.
    # The 15-minute check stays as a backstop. False restores EXP-0055's
    # check-only take profit beside a standalone GTC stop.
    take_profit_at_broker: bool = True
    # EXP-0057 (2026-10-04, owner's order). Where the take profit sits:
    # "bounce" - the close that would put RSI(14) at the rule's exit level,
    # refreshed every session; "atr" - EXP-0055's k_tp x entry ATR, fixed.
    take_profit_mode: str = "bounce"

    def __post_init__(self):
        if self.take_profit_mode not in TAKE_PROFIT_MODES:
            raise ValueError("take_profit_mode must be one of {0}".format(TAKE_PROFIT_MODES))


def params_path(state_file) -> Path:
    """Beside the state file, so a test with its own state file has its own copy."""
    return Path(state_file).with_name(PARAMS_FILE_NAME)


def _clamp(value: float, bounds: Tuple[float, float]) -> float:
    low, high = bounds
    return min(max(float(value), low), high)


def _read(path: Path) -> Dict[str, object]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def current_levels(config: AdaptiveExitConfig, path) -> Tuple[float, float]:
    """(take_profit_atr, stop_atr) in force.

    The initial values unless a readable file says otherwise, and always
    inside the bounds - a damaged file can never produce an extreme level.
    """
    data = _read(Path(path))
    try:
        take = float(data["take_profit_atr"])
        stop = float(data["stop_atr"])
    except (KeyError, TypeError, ValueError):
        return config.initial_take_profit_atr, config.initial_stop_atr
    if not (math.isfinite(take) and math.isfinite(stop)):
        return config.initial_take_profit_atr, config.initial_stop_atr
    return _clamp(take, config.take_profit_bounds), _clamp(stop, config.stop_bounds)


def replay(after: Sequence, closes_through_entry: Sequence[float], entry: float,
           atr: float, take_profit_atr: float, stop_atr: float,
           rule, bounce: bool = False) -> Optional[Tuple[float, str]]:
    """Exit price and reason for one trade under these levels, on daily bars.

    `after` is the sessions AFTER the entry session; `closes_through_entry`
    the closes up to and including it (the RSI needs the history). The order
    within a bar is resolved against the trade: a gap through the stop fills
    at the open, a bar that reaches both levels goes to the stop. None when
    fewer than `rule.max_holding_bars` sessions are available - the trade is
    not finished yet.

    `bounce` (EXP-0057): the target is each session's bounce price, from the
    closes through the session before, instead of entry + k_tp x ATR.
    """
    horizon = int(rule.max_holding_bars)
    if len(after) < horizon or atr <= 0:
        return None
    stop = entry - stop_atr * atr
    fixed_target = entry + take_profit_atr * atr
    closes = list(closes_through_entry)
    # A rule whose exit level RSI can never reach has no bounce price either.
    bounce_reachable = bounce and 0.0 < float(rule.rsi_exit) < 100.0
    for day, bar in enumerate(after[:horizon], start=1):
        if bounce:
            target = (bounce_price(closes, rule.rsi_exit, rule.rsi_period)
                      if bounce_reachable else None)
        else:
            target = fixed_target
        if bar.open <= stop:
            return bar.open, "stop"
        if target is not None and bar.open >= target:
            return bar.open, "take_profit"
        if bar.low <= stop:
            return stop, "stop"
        if target is not None and bar.high >= target:
            return target, "take_profit"
        closes.append(bar.close)
        strength = rsi(closes, rule.rsi_period)
        if strength is not None and strength >= rule.rsi_exit:
            return bar.close, "reverted"
        if day >= horizon:
            return bar.close, "time"
    return None


def r_multiple(exit_price: float, entry: float, atr: float, stop_atr: float,
               round_trip_cost: float) -> float:
    """Profit per unit of the risk this stop would have sized the trade at."""
    return (exit_price - entry - round_trip_cost * entry) / (stop_atr * atr)


@dataclass
class Entry:
    symbol: str
    day: date
    price: float
    atr: float


def logged_entries(audit_log, config: AdaptiveExitConfig,
                   default_stop_atr: float) -> List[Entry]:
    """The bot's own entries since `learning_start`, with the ATR each was sized from.

    ATR is recovered exactly from the logged stop: the stop was entry minus
    stop_atr x ATR. Entries logged before this feature carry no `stop_atr`
    and used the frozen multiple, `default_stop_atr`.
    """
    out, seen = [], set()
    path = Path(audit_log)
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("event") != "entry":
            continue
        at = str(row.get("at", ""))
        detail = row.get("detail") or {}
        if at[:10] < config.learning_start or not isinstance(detail, dict):
            continue
        try:
            symbol = str(detail["symbol"])
            price = float(detail["entry_reference"])
            stop = float(detail["stop"])
            multiple = float(detail.get("stop_atr") or default_stop_atr)
            day = date.fromisoformat(at[:10])
        except (KeyError, TypeError, ValueError):
            continue
        atr = (price - stop) / multiple if multiple > 0 else 0.0
        if atr <= 0 or (symbol, day) in seen:
            continue
        seen.add((symbol, day))
        out.append(Entry(symbol, day, price, atr))
    return out


def _neighbours(take: float, stop: float, config: AdaptiveExitConfig
                ) -> List[Tuple[float, float]]:
    out = []
    # In bounce mode the target is the bounce price, not a multiple, so only
    # the stop has neighbours.
    steps = (() if config.take_profit_mode == "bounce"
             else (-config.take_profit_step, config.take_profit_step))
    for dt in steps:
        t = round(take + dt, 6)
        low, high = config.take_profit_bounds
        if low - 1e-9 <= t <= high + 1e-9:
            out.append((t, stop))
    for ds in (-config.stop_step, config.stop_step):
        s = round(stop + ds, 6)
        low, high = config.stop_bounds
        if low - 1e-9 <= s <= high + 1e-9:
            out.append((take, s))
    return out


def _sessions_since(last: str, today: date, calendar: Sequence[date]) -> int:
    start = date.fromisoformat(last)
    if calendar:
        return sum(1 for d in calendar if start < d <= today)
    return sum(1 for k in range(1, (today - start).days + 1)
               if date.fromordinal(start.toordinal() + k).weekday() < 5)


def learn(audit_log, data_dir, path, config: AdaptiveExitConfig, rule,
          today: Optional[date] = None) -> Dict[str, object]:
    """One evaluation, by the frozen rule. Returns what it decided and why."""
    from .data import load_bars, price_file

    today = today or datetime.now(timezone.utc).date()
    path = Path(path)
    record = _read(path)
    take, stop = current_levels(config, path)

    spy_file = price_file(Path(data_dir), "SPY")
    calendar = ([b.timestamp.date() for b in load_bars(spy_file)]
                if spy_file.exists() else [])
    last = record.get("last_evaluated")
    if isinstance(last, str):
        waited = _sessions_since(last, today, calendar)
        if waited < config.min_sessions_between_evaluations:
            return {"action": "wait", "take_profit_atr": take, "stop_atr": stop,
                    "reason": "evaluated {0} session(s) ago; the rule waits {1}".format(
                        waited, config.min_sessions_between_evaluations)}

    bars_cache: Dict[str, list] = {}
    candidates = [(take, stop)] + _neighbours(take, stop, config)
    results: List[List[float]] = []
    for entry in logged_entries(audit_log, config, rule.stop_atr_multiple):
        if entry.symbol not in bars_cache:
            file = price_file(Path(data_dir), entry.symbol)
            bars_cache[entry.symbol] = load_bars(file) if file.exists() else []
        bars = bars_cache[entry.symbol]
        index = next((i for i, b in enumerate(bars) if b.timestamp.date() == entry.day), None)
        if index is None:
            continue
        after = bars[index + 1:index + 1 + int(rule.max_holding_bars)]
        closes = [b.close for b in bars[:index + 1]]
        row = []
        for t, s in candidates:
            outcome = replay(after, closes, entry.price, entry.atr, t, s, rule,
                             bounce=config.take_profit_mode == "bounce")
            if outcome is None:
                break
            row.append(r_multiple(outcome[0], entry.price, entry.atr, s,
                                  config.round_trip_cost))
        if len(row) == len(candidates):
            results.append(row)

    n = len(results)
    evidence = {}
    choice = (take, stop)
    if n >= config.min_trades:
        best = None
        for j, (t, s) in enumerate(candidates[1:], start=1):
            diffs = [row[j] - row[0] for row in results]
            mean = fmean(diffs)
            error = stdev(diffs) / math.sqrt(n) if n > 1 else float("inf")
            half = n // 2
            older, newer = fmean(diffs[:half]), fmean(diffs[half:])
            clears = mean > max(config.min_improvement_r,
                                config.improvement_standard_errors * error)
            if config.require_both_halves:
                clears = clears and older > 0 and newer > 0
            evidence["{0} / stop {1}".format(
                "bounce" if config.take_profit_mode == "bounce" else "take {0}".format(t), s)] = {
                "mean_r_gain": round(mean, 4), "standard_error": round(error, 4),
                "older_half": round(older, 4), "newer_half": round(newer, 4),
                "clears_the_bar": clears}
            if clears and (best is None or mean > best[0]):
                best = (mean, (t, s))
        if best is not None:
            choice = best[1]
    moved = choice != (take, stop)
    if n < config.min_trades:
        reason = "{0} finished trade(s); the rule needs {1} before it may move".format(
            n, config.min_trades)
    elif moved:
        reason = "moved one step: {0}".format(
            "take profit {0} -> {1} ATR".format(take, choice[0]) if choice[0] != take
            else "stop {0} -> {1} ATR".format(stop, choice[1]))
    else:
        reason = "no neighbour beat the levels in force by more than its noise"

    history = list(record.get("history") or [])
    history.append({"evaluated": today.isoformat(), "finished_trades": n,
                    "from": {"take_profit_atr": take, "stop_atr": stop},
                    "to": {"take_profit_atr": choice[0], "stop_atr": choice[1]},
                    "neighbours": evidence, "decision": reason})
    new_record = {
        "take_profit_atr": choice[0], "stop_atr": choice[1],
        "last_evaluated": today.isoformat(),
        "updated_at": today.isoformat() if moved else record.get("updated_at"),
        "procedure": asdict(config),
        "history": history,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(new_record, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return {"action": "moved" if moved else "stayed", "take_profit_atr": choice[0],
            "stop_atr": choice[1], "finished_trades": n, "reason": reason,
            "neighbours": evidence}
