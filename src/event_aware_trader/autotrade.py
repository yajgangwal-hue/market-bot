"""Fully automatic trading loop: decide, size, submit, and manage exits.

No human step. One `run_once()` call fetches current bars, reconciles what
the broker actually holds, moves every trailing stop, closes anything the
rules say is out, and opens whatever qualifies - then returns a structured
record of everything it did.

Execution goes to an Alpaca **paper** account. This is not a preference:
TradingView's built-in paper trading has no public API and cannot be driven
from code, so nothing can place an order into it. TradingView remains useful
as the chart; the orders have to land somewhere that exposes an API.

Because there is no human in the loop, the guards are the only thing standing
between a bug and a drained account, so they are checked here as well as in
the strategy:

* the broker layer still refuses any endpoint but the paper host
* `max_open_positions` and one-position-per-correlation-bucket are enforced
  against what the *broker* reports, not against local belief
* the daily loss guard halts new entries for the rest of the session
* `max_orders_per_run` bounds a runaway loop
* every decision, order, and refusal is appended to an audit log
"""

import json
import os
import time
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .broker import AlpacaPaperBroker, BrokerConfig, BrokerError
from .cross_sectional import build_snapshot
from .live_model import (
    append_example,
    live_features,
    load_live_model,
    score as live_score,
)
from .trade_learning import load_model, model_vetoes
from .data import fetch_yahoo_bars, fetch_yahoo_bars_many
from .indicators import wilder_atr
from .risk import CostModel, RiskPolicy, position_size
from .strategy import CORRELATION_BUCKETS, DEFAULT_UNIVERSE, StrategyConfig, generate_candidate
from .types import Action, Bar, Event


@dataclass
class AutoTradeConfig:
    interval: str = "1d"
    period: str = "2y"
    universe: Sequence[str] = DEFAULT_UNIVERSE
    max_orders_per_run: int = 3
    dry_run: bool = True
    # Alpaca will not accept a bracket (entry + resting stop) for a fractional
    # quantity, so a fractional order arrives as a bare market buy with no
    # protection at the broker at all. The only stop would then live in this
    # process, which has several silent ways not to run: preflight failing, a
    # network error aborting the cycle, the Mac asleep, the job unloaded. That
    # is not a stop, it is an intention.
    #
    # So the automated path rounds down to whole shares in order to earn a real
    # resting stop. On a funded paper account this costs a little precision in
    # sizing and buys an order that protects itself.
    require_broker_side_stop: bool = True
    # A single 500 or dropped connection used to abort the whole cycle,
    # including the exits - so a network blip could leave positions unmanaged
    # until the next run, or longer.
    broker_retries: int = 3
    retry_backoff_seconds: float = 2.0
    # Nothing verified the market was open. launchd coalesces runs missed while
    # the Mac sleeps and fires once on wake, so a machine asleep through the
    # session produced one run afterwards that submitted DAY market orders
    # against hours-stale bars, to be filled at the next open at an unknown
    # price. The broker's own clock is the authority.
    require_market_open: bool = True
    audit_log: Path = Path("data/autotrade-audit.jsonl")
    state_file: Path = Path("data/autotrade-state.json")
    model_file: Optional[Path] = Path("data/trade-model.json")
    # The cross-sectional model - the only one that measured above chance.
    live_model_file: Optional[Path] = Path("data/live-model.json")
    # An ABSOLUTE probability floor is the wrong instrument here and was very
    # nearly a silent disaster. Filtering to the model's top third lifted
    # expectancy by 47-70% across a 120-symbol universe, so 0.45 looked like a
    # reasonable threshold - but on the 20 ETFs this bot actually trades the
    # model's output spans only 0.2334 to 0.3500. A 0.45 floor sits above the
    # MAXIMUM, so every candidate would have been vetoed, silently, forever.
    #
    # The cause is that a threshold is a property of the population it was
    # measured on. The model was fitted on 120 symbols at a 30% base rate; the
    # bot's universe has already been filtered hard by the hand-built gate, so
    # the surviving candidates sit in a different, narrower band.
    #
    # It is set to 0.0 - inert - because on the bot's own universe the filter
    # also does not help: at a 0.30 floor it cut 13 trades to 9 and the return
    # from +4.20% to +3.23%. The gate has already done the selecting, and
    # filtering an already-selected set mostly removes good trades.
    #
    # If this is ever re-enabled, use a RELATIVE threshold - a quantile of the
    # current candidates - never an absolute probability.
    live_model_floor: float = 0.0

    def __post_init__(self) -> None:
        if self.max_orders_per_run < 1:
            raise ValueError("max_orders_per_run must be at least one")


def _log(config: AutoTradeConfig, event: str, detail: Dict[str, object]) -> Dict[str, object]:
    record = {
        "at": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "dry_run": config.dry_run,
        "detail": detail,
    }
    config.audit_log.parent.mkdir(parents=True, exist_ok=True)
    with config.audit_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
    return record


def _load_state(config: AutoTradeConfig) -> Dict[str, object]:
    if not config.state_file.exists():
        return {}
    try:
        return json.loads(config.state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(config: AutoTradeConfig, state: Dict[str, object]) -> None:
    """Write atomically.

    A plain write_text truncates first. A kill inside that window - machine
    sleep, logout, the job being unloaded - leaves a truncated file, and
    _load_state swallows the decode error and returns {}. The next cycle then
    treats it as a fresh session and re-baselines `opening_equity` to the
    already-drawn-down equity, silently rearming a daily loss guard that had
    correctly halted trading. Writing to a temp file and renaming makes the
    replacement atomic, so a crash leaves either the old state or the new one.
    """
    config.state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.state_file.with_suffix(config.state_file.suffix + ".tmp")
    payload = json.dumps(state, indent=2, sort_keys=True, default=str)
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, config.state_file)


def _with_retry(config: AutoTradeConfig, label: str, call):
    """Retry a broker call through transient failures.

    Credential and endpoint errors are not retried - they will not fix
    themselves, and hammering them is worse than failing fast.
    """
    last: Optional[BrokerError] = None
    for attempt in range(max(1, config.broker_retries)):
        try:
            return call()
        except BrokerError as error:
            message = str(error).lower()
            if "credential" in message or "endpoint" in message:
                raise
            last = error
            if attempt + 1 < config.broker_retries:
                time.sleep(config.retry_backoff_seconds * (2 ** attempt))
    _log(config, "broker_call_failed", {"call": label, "error": str(last)})
    raise last if last else BrokerError("broker call failed")


def run_once(
    config: AutoTradeConfig = AutoTradeConfig(),
    strategy: Optional[StrategyConfig] = None,
    policy: RiskPolicy = RiskPolicy(),
    costs: CostModel = CostModel(),
    events: Sequence[Event] = (),
    broker: Optional[AlpacaPaperBroker] = None,
    bars_by_symbol: Optional[Dict[str, List[Bar]]] = None,
) -> Dict[str, object]:
    """One complete cycle. Safe to call repeatedly; it reconciles each time."""
    strategy = strategy or StrategyConfig.for_interval(config.interval, exit_mode="trailing")
    actions: List[Dict[str, object]] = []

    if broker is None:
        broker = AlpacaPaperBroker(
            BrokerConfig.from_environment(allow_order_submission=not config.dry_run)
        )

    if config.require_market_open:
        try:
            clock = _with_retry(config, "clock", broker.clock)
        except BrokerError as error:
            return {"status": "halted", "reason": "clock unavailable: {0}".format(error)}
        if not clock.get("is_open"):
            _log(config, "market_closed", clock)
            return {
                "status": "market_closed",
                "reason": "The broker reports the market is closed.",
                "next_open": clock.get("next_open"),
                "note": (
                    "No order is placed outside the session. A DAY market order "
                    "sent after the close queues to the next open and fills at an "
                    "unknown price against stale analysis."
                ),
            }

    account = _with_retry(config, "account", broker.account)
    equity = float(account["equity"])
    if account.get("trading_blocked"):
        return {"status": "halted", "reason": "broker reports trading_blocked", "account": account}

    held = {p["symbol"]: p for p in _with_retry(config, "positions", broker.positions)}
    open_buckets = {CORRELATION_BUCKETS.get(s, "other") for s in held}

    # ---- daily loss guard, measured against the session's opening equity ----
    state = _load_state(config)
    today = date.today().isoformat()
    if state.get("session") != today:
        state = {"session": today, "opening_equity": equity, "orders_today": 0}
        _save_state(config, state)
    opening = float(state.get("opening_equity", equity))
    drawdown = (equity - opening) / opening if opening > 0 else 0.0
    halted = drawdown <= -policy.max_daily_loss
    if halted:
        _log(config, "daily_guard_halt", {"opening": opening, "equity": equity, "drawdown": drawdown})

    # The weekly guard was exposed as --max-weekly-loss, reported as "set" by
    # preflight, and enforced nowhere: run_once only ever consulted the daily
    # limit, and that limit re-baselines every calendar day, so nothing
    # accumulated across a losing week. Anchored to the equity at the start of
    # the ISO week, it now does what its name says.
    week_key = date.today().isocalendar()[:2]
    week_tag = "{0}-W{1}".format(*week_key)
    if state.get("week") != week_tag:
        state["week"] = week_tag
        state["week_opening_equity"] = equity
    week_opening = float(state.get("week_opening_equity", equity))
    week_drawdown = (equity - week_opening) / week_opening if week_opening > 0 else 0.0
    if week_drawdown <= -policy.max_weekly_loss:
        halted = True
        _log(config, "weekly_guard_halt", {
            "week": week_tag, "opening": week_opening,
            "equity": equity, "drawdown": week_drawdown,
        })

    # ---- market data --------------------------------------------------------
    if bars_by_symbol is None:
        # Batched, not one request per symbol. See fetch_yahoo_bars_many: at
        # 120 symbols the per-symbol loop was rate-limited by Yahoo and lost
        # 6-18 instruments a cycle, silently, because a throttled symbol looks
        # exactly like a symbol with no signal.
        bars_by_symbol, fetch_failures = fetch_yahoo_bars_many(
            list(config.universe), config.period, config.interval)
        for symbol, error in sorted(fetch_failures.items()):
            _log(config, "fetch_failed", {"symbol": symbol, "error": error})
        # An incomplete universe changes what the gate can even consider, and
        # cross-sectional features are ranks ACROSS peers - so missing symbols
        # quietly move every surviving symbol's rank. Say so at cycle level
        # rather than leaving it to be reconstructed from per-symbol lines.
        missing = len(fetch_failures)
        if missing:
            _log(config, "universe_incomplete", {
                "missing": missing,
                "of": len(config.universe),
                "symbols": sorted(fetch_failures)[:20],
                "note": ("Ranks are computed across peers, so absent symbols "
                         "shift every remaining symbol's percentile."),
                "degraded": missing > len(config.universe) * 0.05,
            })

    # ---- 1. manage what is already open ------------------------------------
    for symbol, position in sorted(held.items()):
        bars = bars_by_symbol.get(symbol)
        if not bars:
            continue
        entry = float(position["average_entry_price"])
        quantity = float(position["quantity"])
        atr = wilder_atr(bars, strategy.atr_days)
        if not atr:
            continue

        # The stop planned at entry is authoritative. Recomputing it from the
        # CURRENT ATR every cycle - as this did - means a widening ATR walks the
        # stop away from price and the position's real risk grows past the
        # budget it was sized against, with no ceiling. So the entry stop is
        # persisted and only ever ratchets up.
        stops = state.setdefault("stops", {})
        remembered = stops.get(symbol)
        if remembered is None:
            initial_stop = entry - strategy.stop_atr_multiple * atr
            stops[symbol] = {"initial": initial_stop, "current": initial_stop,
                             "opened_bars": len(bars)}
            remembered = stops[symbol]
        initial_stop = float(remembered["initial"])
        risk_per_share = entry - initial_stop

        # Only price action since the position opened may arm the trail. Taking
        # the high over a fixed 250-bar window armed it on pre-entry history, so
        # a minutes-old position could inherit a ten-day high and trail from it.
        opened_at = int(remembered.get("opened_bars", len(bars)))
        since_entry = bars[-max(1, len(bars) - opened_at + 1):]
        highest = max(bar.high for bar in since_entry)

        armed = risk_per_share > 0 and (highest - entry) / risk_per_share >= strategy.trail_activate_r
        candidate_stop = highest - strategy.trail_atr_multiple * atr if armed else initial_stop
        stop = max(float(remembered["current"]), candidate_stop)   # ratchet only
        remembered["current"] = stop
        last = bars[-1].close

        if last <= stop:
            result = _with_retry(
                config, "close:" + symbol,
                lambda s=symbol: broker.close_position(s, dry_run=config.dry_run),
            )
            # Taken from what the broker reports it holds, not from a local
            # guess, so the label a model later trains on is the real outcome.
            realized = float(position.get("unrealized_pnl", 0.0) or 0.0)
            cost_basis = entry * quantity
            return_fraction = (last / entry - 1.0) if entry > 0 else 0.0
            r_multiple = (realized / (risk_per_share * quantity)) if (
                risk_per_share > 0 and quantity > 0
            ) else 0.0
            state.get("stops", {}).pop(symbol, None)
            # Learn from this trade immediately: the features it was entered
            # on, paired with what it actually returned.
            opened_features = state.get("open_features", {}).pop(symbol, None)
            if opened_features:
                try:
                    append_example(opened_features, r_multiple, symbol)
                except Exception as error:
                    _log(config, "learning_append_failed", {"symbol": symbol, "error": str(error)})
            actions.append(_log(config, "exit", {
                "symbol": symbol, "quantity": quantity, "last": last,
                "stop": round(stop, 2), "armed": armed, "result": result,
                "entry_price": round(entry, 6),
                "cost_basis": round(cost_basis, 2),
                "realized_pnl": round(realized, 2),
                "return_fraction": round(return_fraction, 6),
                "r_multiple": round(r_multiple, 4),
            }))
        else:
            actions.append(_log(config, "hold", {
                "symbol": symbol, "last": last, "stop": round(stop, 2),
                "armed": armed, "unrealized": position.get("unrealized_pnl"),
            }))

    # ---- 2. open what qualifies --------------------------------------------
    submitted = 0
    near_misses: List[tuple] = []
    if halted:
        actions.append(_log(config, "entries_suspended", {"reason": "daily loss guard"}))
    else:
        candidates = []
        for symbol in sorted(config.universe):
            bars = bars_by_symbol.get(symbol)
            if symbol in held or not bars or len(bars) < strategy.minimum_history:
                continue
            bucket = CORRELATION_BUCKETS.get(symbol, "other")
            if bucket in open_buckets or len(held) >= policy.max_open_positions:
                continue
            candidate = generate_candidate(
                symbol, bars, events, equity, policy, costs, strategy,
                open_positions=len(held), open_buckets=open_buckets,
            )
            if candidate.action == Action.PAPER_LONG and candidate.entry and candidate.stop:
                candidates.append(candidate)
            elif candidate.action == Action.WATCH:
                # Cleared every hard blocker; only the evidence score fell
                # short. Worth recording: "no trades" is otherwise silent and
                # indistinguishable from a broken cycle - which is exactly how
                # a whole dead trading day went unnoticed on 2026-08-31.
                near_misses.append((candidate.score, symbol))
        # Rank by the cross-sectional model where it is available. It scored
        # 0.55-0.57 out of sample against 0.50 for the hand-built score, so it
        # is the better ordering - but it only ever REORDERS and filters what
        # the hand-built gate already approved. It cannot introduce a trade the
        # gate rejected.
        live, estimator = load_live_model(config.live_model_file) if config.live_model_file else (None, None)
        snapshot = build_snapshot(bars_by_symbol) if estimator is not None else None
        live_scores: Dict[str, float] = {}
        if estimator is not None and live is not None and live.usable:
            for candidate in candidates:
                feats = live_features(candidate.symbol, bars_by_symbol.get(candidate.symbol, []), snapshot)
                live_scores[candidate.symbol] = live_score(estimator, feats)
            before = len(candidates)
            candidates = [c for c in candidates
                          if live_scores.get(c.symbol, 1.0) >= config.live_model_floor]
            candidates.sort(key=lambda c: live_scores.get(c.symbol, 0.0), reverse=True)
            _log(config, "live_model_ranking", {
                "model_auc": live.test_auc, "trained_on": live.n_examples,
                "considered": before, "kept": len(candidates),
                "scores": {k: round(v, 4) for k, v in sorted(
                    live_scores.items(), key=lambda kv: -kv[1])[:5]},
            })
        else:
            candidates.sort(key=lambda c: c.score, reverse=True)

        # The learned model may only remove a candidate the gate accepted.
        model = None
        if config.model_file and config.model_file.exists():
            try:
                model = load_model(config.model_file)
            except (OSError, ValueError, KeyError) as error:
                _log(config, "model_load_failed", {"error": str(error)})
        if model is not None:
            kept = []
            for candidate in candidates:
                vetoed, probability = model_vetoes(model, candidate.features, candidate.score)
                if vetoed:
                    actions.append(_log(config, "model_veto", {
                        "symbol": candidate.symbol,
                        "probability": round(probability, 4),
                        "threshold": model.veto_threshold,
                        "model_status": model.status,
                    }))
                else:
                    kept.append(candidate)
            candidates = kept

        for candidate in candidates:
            bars = bars_by_symbol.get(candidate.symbol) or []
            if not bars:
                continue
            if submitted >= config.max_orders_per_run or len(held) >= policy.max_open_positions:
                break
            bucket = candidate.correlation_bucket
            if bucket in open_buckets:
                continue
            # Same guard the simulator applies: the stop came from the last
            # closed bar, and price may already have moved through it. Entering
            # a position that is beyond its own stop is incoherent, and a fill
            # only just above it produces a maximum-sized position on a setup
            # whose premise has broken. The last trade price is the freshest
            # read available here.
            latest = bars[-1].close
            planned_risk_per_share = candidate.entry - candidate.stop
            actual_risk_per_share = latest - candidate.stop
            if actual_risk_per_share <= 0 or (
                planned_risk_per_share > 0
                and actual_risk_per_share < 0.5 * planned_risk_per_share
            ):
                actions.append(_log(config, "gapped_through_stop", {
                    "symbol": candidate.symbol,
                    "planned_entry": round(candidate.entry, 4),
                    "stop": round(candidate.stop, 4),
                    "latest": round(latest, 4),
                }))
                continue

            sizing_policy = policy
            if config.require_broker_side_stop:
                sizing_policy = replace(policy, allow_fractional_shares=False)
            quantity, planned_risk = position_size(
                equity, candidate.entry, candidate.stop, sizing_policy, costs
            )
            if quantity <= 0:
                actions.append(_log(config, "too_small_for_a_protected_order", {
                    "symbol": candidate.symbol,
                    "reason": (
                        "Whole-share sizing yields zero at this equity and stop "
                        "distance. A fractional order cannot carry a resting stop, "
                        "so no order is sent."
                    ),
                }))
                continue
            result = broker.submit_reviewed_candidate(
                candidate.symbol, quantity,
                stop=candidate.stop, target=candidate.target,
                dry_run=config.dry_run,
            )
            submitted += 1
            open_buckets.add(bucket)
            held[candidate.symbol] = {"symbol": candidate.symbol}
            # The feature vector is written down at entry because that is the
            # only moment it exists. Without it a completed trade cannot become
            # a training example later, and the retraining loop would only ever
            # re-read price history - learning from hypotheticals rather than
            # from what the bot actually did.
            actions.append(_log(config, "entry", {
                "symbol": candidate.symbol, "score": round(candidate.score, 1),
                "quantity": quantity, "stop": candidate.stop,
                "entry_reference": candidate.entry,
                "planned_risk": round(planned_risk, 2), "result": result,
                "features": {
                    k: (None if v is None else round(float(v), 6))
                    for k, v in candidate.features.items()
                },
                # The cross-sectional vector is what the live model was fitted
                # on, so it is what a completed trade has to carry back.
                "live_features": live_features(
                    candidate.symbol, bars_by_symbol.get(candidate.symbol, []), snapshot
                ),
                "live_score": round(live_scores.get(candidate.symbol, 0.0), 4),
            }))
            state.setdefault("open_features", {})[candidate.symbol] = live_features(
                candidate.symbol, bars_by_symbol.get(candidate.symbol, []), snapshot
            )

    if submitted == 0 and near_misses:
        near_misses.sort(reverse=True)
        _log(config, "no_entries_closest_candidates", {
            "gate": strategy.minimum_score,
            "closest": [{"symbol": sym, "score": round(sc, 1),
                         "short_by": round(strategy.minimum_score - sc, 1)}
                        for sc, sym in near_misses[:5]],
            "cleared_all_hard_blockers": len(near_misses),
            "note": ("These passed every hard filter and fell short only on the "
                     "evidence score. Do NOT lower the gate to convert them - "
                     "the threshold is what separates a rule from a guess."),
        })

    state["orders_today"] = int(state.get("orders_today", 0)) + submitted
    _save_state(config, state)

    # A run that did nothing is still evidence the loop ran, which is exactly
    # what you need when asking later why no trade appeared on some day.
    _log(config, "run_complete", {
        "equity": equity, "entries": submitted,
        "exits": len([a for a in actions if a["event"] == "exit"]),
        "held": len(held), "halted": halted,
    })

    return {
        "status": "halted_for_the_day" if halted else "ok",
        "at": datetime.now(timezone.utc).isoformat(),
        "dry_run": config.dry_run,
        "interval": config.interval,
        "equity": equity,
        "opening_equity": opening,
        "session_change": round(100 * drawdown, 3),
        "positions_held": len([a for a in actions if a["event"] == "hold"]),
        "exits": len([a for a in actions if a["event"] == "exit"]),
        "entries": submitted,
        "actions": actions,
        "note": (
            "Alpaca paper account. TradingView paper trading exposes no API and "
            "cannot receive these orders."
        ),
    }
