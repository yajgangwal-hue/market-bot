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
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .broker import AlpacaPaperBroker, BrokerConfig, BrokerError
from .trade_learning import load_model, model_vetoes
from .data import fetch_yahoo_bars
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
    audit_log: Path = Path("data/autotrade-audit.jsonl")
    state_file: Path = Path("data/autotrade-state.json")
    model_file: Optional[Path] = Path("data/trade-model.json")

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
    config.state_file.parent.mkdir(parents=True, exist_ok=True)
    config.state_file.write_text(json.dumps(state, indent=2, sort_keys=True, default=str), encoding="utf-8")


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

    account = broker.account()
    equity = float(account["equity"])
    if account.get("trading_blocked"):
        return {"status": "halted", "reason": "broker reports trading_blocked", "account": account}

    held = {p["symbol"]: p for p in broker.positions()}
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

    # ---- market data --------------------------------------------------------
    if bars_by_symbol is None:
        bars_by_symbol = {}
        for symbol in config.universe:
            try:
                bars_by_symbol[symbol] = fetch_yahoo_bars(symbol, config.period, config.interval)
            except Exception as error:
                _log(config, "fetch_failed", {"symbol": symbol, "error": str(error)})

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
        highest = max(bar.high for bar in bars[-strategy.max_trailing_bars:])
        initial_stop = entry - strategy.stop_atr_multiple * atr
        risk_per_share = entry - initial_stop
        armed = risk_per_share > 0 and (highest - entry) / risk_per_share >= strategy.trail_activate_r
        stop = max(initial_stop, highest - strategy.trail_atr_multiple * atr) if armed else initial_stop
        last = bars[-1].close

        if last <= stop:
            result = broker.close_position(symbol, dry_run=config.dry_run)
            actions.append(_log(config, "exit", {
                "symbol": symbol, "quantity": quantity, "last": last,
                "stop": round(stop, 2), "armed": armed, "result": result,
            }))
        else:
            actions.append(_log(config, "hold", {
                "symbol": symbol, "last": last, "stop": round(stop, 2),
                "armed": armed, "unrealized": position.get("unrealized_pnl"),
            }))

    # ---- 2. open what qualifies --------------------------------------------
    submitted = 0
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
            if submitted >= config.max_orders_per_run or len(held) >= policy.max_open_positions:
                break
            bucket = candidate.correlation_bucket
            if bucket in open_buckets:
                continue
            quantity, planned_risk = position_size(
                equity, candidate.entry, candidate.stop, policy, costs
            )
            if quantity <= 0:
                continue
            result = broker.submit_reviewed_candidate(
                candidate.symbol, quantity,
                stop=candidate.stop, target=candidate.target,
                dry_run=config.dry_run,
            )
            submitted += 1
            open_buckets.add(bucket)
            held[candidate.symbol] = {"symbol": candidate.symbol}
            actions.append(_log(config, "entry", {
                "symbol": candidate.symbol, "score": round(candidate.score, 1),
                "quantity": quantity, "stop": candidate.stop,
                "planned_risk": round(planned_risk, 2), "result": result,
            }))

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
