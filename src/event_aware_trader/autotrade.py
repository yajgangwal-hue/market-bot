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
from math import floor
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .broker import AlpacaPaperBroker, BrokerConfig, BrokerError, round_price
from .cross_sectional import build_snapshot
from .live_model import (
    append_example,
    live_features,
    load_live_model,
    score as live_score,
)
from .trade_learning import load_model, model_vetoes
from .data import (fetch_yahoo_bars, fetch_alpaca_crypto_bars,
                   fetch_alpaca_equity_bars)
from .indicators import wilder_atr
from .risk import CostModel, RiskPolicy, cap_by_participation, position_size
from .strategy import CORRELATION_BUCKETS, DEFAULT_UNIVERSE, StrategyConfig, generate_candidate, is_crypto
from .types import Action, Bar, Event, Candidate


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
    # Which side of the account this cycle owns: "equity", "crypto", or "all".
    #
    # Crypto trades continuously and equities do not, so they run on separate
    # schedules against one account. Every position read, every exit and every
    # protective-stop reconciliation is confined to the class this cycle owns.
    # Without that confinement a 3am crypto cycle would evaluate an equity
    # position on stale bars, and worse, _reconcile_protective_stops would
    # cancel the GTC stop under a stock while the market that could replace it
    # is closed.
    # Crypto is paused, so a bare command and both schedulers should agree
    # with that rather than quietly reintroducing it. "all" remains available
    # and is what the tests use when they mean both.
    asset_class: str = "equity"
    # Which rule decides entries, and therefore which decides exits.
    #
    # "mean_reversion" is the default because it is the one that measures.
    # Over two years on this universe the shipped trend gate produced 138
    # trades that record.py calls NOT_DISTINGUISHABLE_FROM_LUCK - a mean
    # return whose 95% interval spans zero, p=0.34 - while mean reversion
    # produced 31 that it calls POSITIVE_AND_MEASURABLE, p=0.030. The same
    # ordering holds on 2017-2023, a window neither rule was fitted to.
    #
    # Set to "trend" to restore the previous behaviour exactly.
    #
    # The honest caveat, kept next to the default rather than in a commit
    # message: 31 trades is the bare minimum for any statistical statement,
    # the interval's lower bound is +0.054%, and buy-and-hold beat both rules
    # over the same window by a wide margin. Better than luck is not good.
    entry_rule: str = "mean_reversion"
    # Trade a SLICE of the account rather than all of it.
    #
    # Sizing, both loss guards and the reported numbers all key off one
    # `equity` figure. Point that at a smaller number and every one of them
    # scales together: a 20% position cap becomes 20% of the slice, and the
    # 1.5% daily guard trips on 1.5% of the slice rather than needing a move
    # a hundred times larger to bind.
    #
    # It compounds, which is the point. The slice is the base plus every
    # dollar the account has made or lost since the baseline, so profits
    # enlarge the book and losses shrink it:
    #
    #     allocated = capital_base + (broker_equity - capital_baseline_equity)
    #
    # With base 1000 and baseline 100000 against equity 100003.74 that is
    # 1003.74; earn another 50 and it is 1053.74 with no further intervention.
    #
    # Both are None by default, which trades the whole account exactly as
    # before.
    capital_base: Optional[float] = None
    capital_baseline_equity: Optional[float] = None
    # The mean-reversion parameters this cycle runs on. None means the
    # shipped equity defaults.
    #
    # It is one object rather than three because the entry, the stop
    # reconstruction and the exit each built their own MeanReversionConfig(),
    # and they MUST agree: trading one rule's entries against another's exits
    # measures neither, which is the failure test_entry_rule.py exists to
    # prevent. A single config threaded to all three sites makes disagreement
    # impossible rather than merely unlikely.
    #
    # `CRYPTO_MEAN_REVERSION` is the preset for a crypto cycle - crypto cannot
    # be seen at all through the equity floors. It does not make crypto
    # profitable; see docs/2026-09-08-crypto-rejected.md.
    mean_reversion: Optional["MeanReversionConfig"] = None
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
        if self.asset_class not in {"all", "equity", "crypto"}:
            raise ValueError("asset_class must be one of: all, equity, crypto")


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


_DAILY_CACHE: Dict[str, tuple] = {}


def daily_bars(symbol: str, data_dir: Path = Path("data")):
    """Daily bars for one symbol from the local price files, cached per mtime.

    Read from disk rather than from the cycle's bars because the loop may be
    running any interval, and a rule calibrated in days must not be handed
    fifteen-minute candles. Cached on modification time so a cycle costs one
    stat per symbol rather than a re-parse, and so a refresh mid-session is
    picked up without a restart.
    """
    from .data import load_bars, price_file

    path = price_file(data_dir, symbol)
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return []
    # Keyed by path, not by symbol: the same symbol under a different
    # data_dir is a different file, and a test pointing at a temp directory
    # would otherwise be served the live data/ bars whenever the two happened
    # to share an mtime.
    key = str(path)
    cached = _DAILY_CACHE.get(key)
    if cached and cached[0] == stamp:
        return cached[1]
    try:
        bars = load_bars(path)
    except (OSError, ValueError):
        bars = []
    _DAILY_CACHE[key] = (stamp, bars)
    return bars


def owns(config, symbol: str) -> bool:
    """Is this symbol the responsibility of this cycle?"""
    if config.asset_class == "crypto":
        return is_crypto(symbol)
    if config.asset_class == "equity":
        return not is_crypto(symbol)
    return True


def _mean_reversion_candidate(symbol, series, equity, policy, costs, strategy,
                              rule_config=None):
    """A mean-reversion signal, shaped as the Candidate the rest of the loop reads.

    `series` must be DAILY bars. The rule counts in days - rsi_period 14,
    trend_ma_days 200, max_holding_bars 10 - and the loop may be running any
    interval, so the caller loads the daily file rather than passing the
    cycle's candles. Taking the series as an argument rather than reading it
    here keeps this function pure and testable against a fixture.

    Buy short-horizon weakness inside an intact long-term uptrend, rather than
    joining a move already underway. The score is not comparable to the trend
    gate's 0-100 evidence score; it exists only to rank several oversold names
    against each other, and deeper oversold ranks first.

    A target is supplied purely so the entry can carry a bracket, which is
    what protects an equity position in the seconds before the standalone GTC
    stop replaces it. Mean reversion does not exit on a target - it exits when
    the oversold condition resolves - and the take-profit leg is cancelled by
    _reconcile_protective_stops on the very next cycle, so it never fires.
    """
    from .mean_reversion import MeanReversionConfig, evaluate

    mr_config = rule_config or MeanReversionConfig()
    as_of = series[-1].timestamp if series else datetime.now(timezone.utc)
    if len(series) < mr_config.minimum_history:
        return Candidate(
            symbol=symbol, action=Action.REJECT, as_of=as_of, score=0.0,
            entry=None, stop=None, target=None, quantity=0.0, planned_risk=0.0,
            modeled_round_trip_cost=0.0, event_impact=0.0,
            reasons=[], correlation_bucket=CORRELATION_BUCKETS.get(symbol, "other"),
            blockers=["Fewer than {0} daily bars on file for {1}".format(
                mr_config.minimum_history, symbol)],
        )
    signal = evaluate(symbol, series, mr_config)
    bucket = CORRELATION_BUCKETS.get(symbol, "other")
    if not signal.is_buy or signal.stop is None or signal.close <= signal.stop:
        return Candidate(
            symbol=symbol, action=Action.REJECT, as_of=as_of, score=0.0,
            entry=None, stop=None, target=None, quantity=0.0, planned_risk=0.0,
            modeled_round_trip_cost=0.0, event_impact=0.0,
            reasons=list(signal.reasons), blockers=list(signal.reasons),
            correlation_bucket=bucket,
        )

    entry = float(signal.close)
    stop = float(signal.stop)
    target = entry + strategy.reward_to_risk * (entry - stop)
    return Candidate(
        symbol=symbol, action=Action.PAPER_LONG, as_of=as_of,
        score=100.0 - float(signal.rsi or 0.0),
        entry=entry, stop=stop, target=target, quantity=0.0, planned_risk=0.0,
        modeled_round_trip_cost=costs.round_trip_cost_per_share(entry, stop),
        event_impact=0.0, reasons=list(signal.reasons), blockers=[],
        correlation_bucket=bucket,
        features={
            "rsi": signal.rsi, "trend_ma": signal.trend_ma,
            "atr_fraction": signal.atr_fraction,
            "average_dollar_volume": sum(
                b.close * b.volume for b in series[-20:]) / max(1, len(series[-20:])),
        },
    )


def _mr(config: "AutoTradeConfig"):
    """The rule parameters for this cycle. One source, three call sites."""
    from .mean_reversion import MeanReversionConfig
    return config.mean_reversion or MeanReversionConfig()


def _parse_stamp(value: str) -> datetime:
    """An ISO timestamp from state, tolerant of both conventions on file.

    Price files arrive from two sources: 120 naive at 16:00 local and 110
    tz-aware at 04:00+00:00. Only the DATE is ever compared downstream, so the
    zone is normalised away rather than trusted.
    """
    text = str(value).strip().replace("Z", "+00:00")
    stamp = datetime.fromisoformat(text)
    if stamp.tzinfo is not None:
        stamp = stamp.astimezone(timezone.utc).replace(tzinfo=None)
    return stamp


def _reconcile_protective_stops(config, broker, state, actions) -> None:
    """Every open position must rest on a GTC stop, and nothing else may.

    THE PROBLEM. The bracket sent with an entry does not survive the session.
    Its legs are time_in_force=day: the take-profit limit expires at the bell
    and OCO cancels the sibling stop with it. Measured 2026-09-01, both legs
    were gone at 16:01:38 ET - ninety seconds after the close - and two
    positions sat overnight with nothing behind them. `require_broker_side_stop`
    is True precisely because a stop needing this machine awake "is not a stop,
    it is an intention", and after the first close every position had exactly
    that.

    WHY IT CANNOT SIMPLY BE ADDED ALONGSIDE. Alpaca reserves position shares
    against any resting sell order, so a bracket leg covering 100 shares holds
    all 100 and a second sell stop for the same shares is rejected with
    "insufficient qty available". A GTC stop can only exist where the bracket
    legs do not. Both legs must go - the take-profit reserves shares exactly as
    the stop does.

    WHAT THAT CHANGES, STATED PLAINLY. After the first cycle following an entry
    the position no longer has a broker-side take-profit. This is a behaviour
    change and it is deliberate: under exit_mode="trailing" - the shipped
    default - the simulator never exits on target (portfolio.py evaluates
    target_hit only in the non-trailing branch), yet autotrade was sending a
    take-profit leg to the broker anyway. So live could be closed by a target
    the backtest never modelled. Removing it makes live match what was actually
    tested.

    The entry keeps its bracket, so a fill is protected within seconds. The
    swap happens on the next cycle, and once swapped it is permanent - which is
    why this does not depend on any particular cycle running. An approach that
    swapped only on the last cycle before the close would fail exactly when the
    machine is unreliable, which is the case the fix exists for.

    Each cycle re-asserts the truth at the broker:

      position, no GTC stop      -> cancel any legs, place one  (the repair)
      position, wrong quantity   -> replace          (partial fill, manual trim)
      position, stop too low     -> replace          (the trail ratcheted up)
      sell order, no position    -> cancel           (closed by hand elsewhere)

    Cancel-before-submit, deliberately, for two reasons. It frees the reserved
    shares so the submit can succeed at all. And two live stops on one position
    could both trigger and sell twice, turning a flat exit into an accidental
    short. The cost is a window with no stop if the submit is then rejected;
    that window is bounded by the cycle interval, and a failure is logged
    loudly rather than swallowed.

    Positions are read from the BROKER, never from local state, so a position
    closed by hand elsewhere is seen and quantities match what is really held.

    TWO HONEST COSTS, so they are not mistaken later for something worse.

    First, this is not purely an improvement. On the first cycle after an entry
    the day bracket IS protecting the position; cancelling it and then having
    the submit rejected leaves the position naked mid-session until the next
    cycle. Before this change it would have kept that bracket until the bell.
    The window is bounded by the cycle interval and logged, and it buys a stop
    that survives every night thereafter - but that specific window is a
    regression, not a win.

    Second, if price crosses `planned` between section 1 reading the bar and
    this submitting, Alpaca rejects a sell stop at or above the market and
    protective_stop_FAILED appears. The window is narrow - section 1 would
    normally have exited the position in the same cycle - and it resolves
    itself on the next cycle.
    """
    try:
        positions = {str(p["symbol"]): p for p in broker.positions()
                     if owns(config, p["symbol"])}
        # The orphan branch cancels any resting sell with no position behind
        # it. Unfiltered, a crypto cycle would see an equity's GTC stop, find
        # no equity position in its own view, and cancel the protection off a
        # stock overnight. Filter both sides, not just one.
        sells = {symbol: orders
                 for symbol, orders in broker.open_sell_orders().items()
                 if owns(config, symbol)}
    except BrokerError as error:
        actions.append(_log(config, "stop_reconcile_failed", {"error": str(error)}))
        return

    remembered = state.setdefault("stops", {})

    # Alpaca's position delete is asynchronous, so a position sold seconds ago
    # in section 1 can still be listed here. Its remembered stop was popped on
    # exit, so it would look like an unprotected position with no planned stop
    # and log stop_unknown on the ordinary happy path of an exit. A warning
    # that fires routinely is a warning nobody reads, which would blunt the
    # exact signal this function exists to raise.
    exited_this_cycle = {
        str(a.get("detail", {}).get("symbol"))
        for a in actions
        if a.get("event") == "exit" and a.get("detail", {}).get("symbol")
    }

    def cancel(symbol, order, why):
        result = _with_retry(
            config, "cancel-{0}:{1}".format(why, symbol),
            lambda oid=order["id"]: broker.cancel_order(oid, dry_run=config.dry_run),
        )
        actions.append(_log(config, "sell_order_canceled", {
            "symbol": symbol, "order_id": order["id"], "why": why,
            "type": order["type"], "stop_price": order["stop_price"],
            "result": result,
        }))

    # Orphans first: a sell order with no position behind it can only go short.
    for symbol in sorted(sells):
        if symbol not in positions:
            for order in sells[symbol]:
                cancel(symbol, order, "orphan")

    for symbol in sorted(positions):
        quantity = float(positions[symbol]["quantity"])
        # Protect the whole-share PART of a fractional equity position rather
        # than protecting none of it.
        #
        # Alpaca cannot rest a GTC stop on a fraction, so a 76.5-share holding
        # used to fail outright and log protective_stop_FAILED every cycle
        # forever - the position stayed completely naked over an unprotected
        # remainder of half a share. A 76-share stop covers 99.3% of it.
        #
        # Sizing now floors before the order is sent, so new positions arrive
        # whole and this branch is for what a partial fill, a corporate action
        # or an older position leaves behind.
        #
        # `protectable` and not `quantity` is then used by the comparison
        # below as well, deliberately: comparing a 76-share stop against a
        # 76.5-share position would call it wrong on every cycle and churn a
        # cancel-and-resubmit pair forever.
        protectable = quantity
        if config.require_broker_side_stop and not is_crypto(symbol):
            protectable = float(floor(quantity + 1e-9))
        if symbol in exited_this_cycle:
            continue
        if protectable <= 0:
            # A sub-share equity remainder can never be protected, so close it.
            #
            # This is what a filled stop leaves behind. On 2026-09-09 the stop
            # on RTX covered 76 of 76.5 shares, filled, and left 0.5 shares -
            # $99 that no GTC stop can rest on, logging the same warning every
            # fifteen minutes indefinitely. Unprotected and unmanaged is the
            # one state this whole module exists to prevent, and a warning
            # that repeats forever is a warning nobody reads.
            #
            # EQUITIES ONLY, and the distinction matters: 0.5 BTC is a
            # deliberate position worth tens of thousands, not a remainder.
            # Crypto is fractional by nature and can rest a stop_limit, so it
            # must never reach this branch.
            #
            # Sizing now floors before the order goes out, so new positions
            # arrive whole and this is for what a filled partial stop, a
            # corporate action, or a pre-fix position leaves behind.
            if is_crypto(symbol):
                continue
            actions.append(_log(config, "too_small_to_protect", {
                "symbol": symbol, "quantity": quantity,
                "note": ("under one whole share, so no GTC stop can rest on "
                         "it; closing the remainder"),
            }))
            if not config.dry_run:
                try:
                    for order in sells.get(symbol, []):
                        cancel(symbol, order, "closing-sub-share-remainder")
                    result = _with_retry(
                        config, "close-remainder:" + symbol,
                        lambda s=symbol: broker.close_position(s, dry_run=False),
                    )
                    actions.append(_log(config, "sub_share_remainder_closed", {
                        "symbol": symbol, "quantity": quantity,
                        "result": result,
                    }))
                    remembered.pop(symbol, None)
                except BrokerError as error:
                    actions.append(_log(config, "sub_share_close_FAILED", {
                        "symbol": symbol, "quantity": quantity,
                        "error": str(error),
                        "note": "retried next cycle; the amount is under one share",
                    }))
            continue
        planned = remembered.get(symbol, {}).get("current")
        if planned is None:
            # Section 1 sets this from the entry stop; it is absent only when
            # the symbol had no bars this cycle. Say so - an unprotected
            # position is the exact thing this function exists to surface.
            actions.append(_log(config, "stop_unknown", {
                "symbol": symbol, "quantity": quantity,
                "note": "no planned stop this cycle, so none could be asserted",
            }))
            continue
        # Same tick-aware rounding the order will use, or the comparison
        # below is against a price the broker never saw.
        planned = round_price(float(planned))

        correct, must_go = None, []
        for order in sells.get(symbol, []):
            price = order["stop_price"]
            is_right_stop = (
                order["type"] == "stop"
                and order["time_in_force"] == "gtc"
                and price is not None
                # Tolerance scaled to the price: half a cent is the right
                # window for a $200 stock and larger than the entire price of
                # a sub-dollar asset, where it would call every stop "correct".
                and abs(float(price) - planned) < max(0.005, planned * 1e-4)
                and abs(float(order["quantity"]) - protectable) < 1e-9
            )
            if is_right_stop and correct is None:
                correct = order
            else:
                must_go.append(order)      # incl. bracket legs holding shares

        if correct is not None and not must_go:
            continue

        for order in must_go:
            cancel(symbol, order, "stale-or-reserving")

        if correct is None:
            try:
                result = _with_retry(
                    config, "protect:" + symbol,
                    lambda s=symbol, q=protectable, sp=planned: broker.submit_protective_stop(
                        s, q, sp, dry_run=config.dry_run),
                )
                actions.append(_log(config, "protective_stop_placed", {
                    "symbol": symbol, "quantity": protectable, "stop_price": planned,
                    "position_quantity": quantity,
                    "unprotected_remainder": round(quantity - protectable, 9),
                    "replaced": len(must_go), "result": result,
                }))
            except BrokerError as error:
                actions.append(_log(config, "protective_stop_FAILED", {
                    "symbol": symbol, "quantity": protectable, "stop_price": planned,
                    "error": str(error),
                    "note": "position has NO resting stop until the next cycle repairs it",
                }))


def _allocated_equity(config: AutoTradeConfig, broker_equity: float) -> float:
    """The slice of the account this bot may trade, or all of it.

    Returns broker equity untouched unless both capital settings are present.
    Never returns more than the account actually holds: a slice larger than
    the account would size positions the broker cannot fill, and the rejection
    would arrive as an opaque buying-power error rather than as the
    configuration mistake it is.
    """
    if config.capital_base is None or config.capital_baseline_equity is None:
        return broker_equity
    allocated = config.capital_base + (broker_equity - config.capital_baseline_equity)
    return max(0.0, min(allocated, broker_equity))


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

    # The equity clock does not govern crypto, which trades continuously. A
    # crypto cycle that consulted it would sleep through every weekend and
    # every night, which is the whole reason for a second schedule.
    if config.require_market_open and config.asset_class != "crypto":
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
    broker_equity = float(account["equity"])
    if account.get("trading_blocked"):
        return {"status": "halted", "reason": "broker reports trading_blocked", "account": account}

    # Everything downstream - sizing, both guards, the reported figures - keys
    # off this one number, so capping here caps all of them consistently.
    equity = _allocated_equity(config, broker_equity)
    # Cash, not buying power. Alpaca reports 4x buying power on a margin
    # account, and spending it is borrowing - which is neither what the sizing
    # sweep measured nor something to start doing by accident.
    cash_available = float(account.get("cash", 0.0) or 0.0)
    if config.capital_base is not None and config.capital_baseline_equity is not None:
        _log(config, "capital_allocation", {
            "broker_equity": round(broker_equity, 2),
            "allocated": round(equity, 2),
            "base": config.capital_base,
            "baseline_equity": config.capital_baseline_equity,
            "note": "Sizing and loss guards use the allocated figure, not the account.",
        })
        if equity <= 0:
            return {
                "status": "halted",
                "reason": "allocated capital has been exhausted",
                "broker_equity": round(broker_equity, 2),
                "allocated": round(equity, 2),
            }

    held = {p["symbol"]: p
            for p in _with_retry(config, "positions", broker.positions)
            if owns(config, p["symbol"])}
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
        # Only this cycle's own class. A crypto run at 3am has no business
        # pulling 120 equities, and it could not anyway: Yahoo does not carry
        # Alpaca's pairs, so crypto comes from Alpaca's own bars.
        wanted = [sym for sym in config.universe if owns(config, sym)]
        equities = [sym for sym in wanted if not is_crypto(sym)]
        crypto = [sym for sym in wanted if is_crypto(sym)]
        bars_by_symbol, fetch_failures = ({}, {})
        if equities:
            # Alpaca, not Yahoo. On 2026-09-08 every Yahoo request from this
            # machine failed certificate verification - "unable to get local
            # issuer certificate" - so the loop had no bars and traded nothing
            # for four consecutive cycles on the first session after a
            # configuration change. Pointing certifi's bundle at it did not
            # help, and the daily refresh had already been moved to Alpaca for
            # separate reasons: partial sessions and unadjusted splits.
            # Keeping one source for both removes the last dependency on a
            # feed that has now broken twice in two days.
            months = {"1mo": 35, "2mo": 65, "3mo": 95, "6mo": 190,
                      "1y": 370, "2y": 760}.get(config.period, 95)
            try:
                bars_by_symbol = fetch_alpaca_equity_bars(
                    equities, days=months, interval=config.interval)
            except Exception as error:
                bars_by_symbol = {}
                _log(config, "fetch_failed", {"symbol": "*", "error": str(error)})
            fetch_failures = {
                symbol: "no bars returned" for symbol in equities
                if symbol not in bars_by_symbol
            }
        for symbol in crypto:
            try:
                bars_by_symbol[symbol] = fetch_alpaca_crypto_bars(symbol)
            except Exception as error:
                fetch_failures[symbol] = str(error)
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
                "of": len(wanted),
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
        # Only the TREND path needs the cycle's ATR - to widen a trailing stop.
        # Mean reversion holds a fixed stop and exits on RSI, so skipping the
        # whole position for a missing ATR would leave it unmanaged for a
        # reason that has nothing to do with the rule managing it. A position
        # nobody looks at is precisely what this loop exists to prevent.
        if not atr and config.entry_rule != "mean_reversion":
            continue

        # The stop planned at entry is authoritative. Recomputing it from the
        # CURRENT ATR every cycle - as this did - means a widening ATR walks the
        # stop away from price and the position's real risk grows past the
        # budget it was sized against, with no ceiling. So the entry stop is
        # persisted and only ever ratchets up.
        stops = state.setdefault("stops", {})
        remembered = stops.get(symbol)
        if remembered is None:
            # Reached only for a position this process did not open - the entry
            # path now records the exact submitted stop. Falling back to an ATR
            # multiple needs an ATR; without one there is nothing to reconstruct
            # from, so leave it for a cycle that has the data.
            if not atr:
                actions.append(_log(config, "stop_unreconstructable", {
                    "symbol": symbol,
                    "note": ("No remembered stop and no ATR this cycle, so none "
                             "could be reconstructed. The resting broker stop "
                             "still protects the position."),
                }))
                continue
            # The multiple has to come from the rule that is running. The
            # trend config says 2.0 and mean reversion says 3.0, and this used
            # `strategy` either way - so a recovered mean-reversion position
            # was rebuilt with a stop a third tighter than the rule places,
            # and _reconcile_protective_stops then rested that tighter level
            # at the broker. Buying weakness behind a stop meant for breakouts
            # converts winners into stop-outs.
            if config.entry_rule == "mean_reversion":
                from .mean_reversion import MeanReversionConfig
                multiple = _mr(config).stop_atr_multiple
            else:
                multiple = strategy.stop_atr_multiple
            initial_stop = entry - multiple * atr
            stops[symbol] = {"initial": initial_stop, "current": initial_stop,
                             "opened_bars": len(bars),
                             "opened_at_ts": bars[-1].timestamp.isoformat()}
            remembered = stops[symbol]
        initial_stop = float(remembered["initial"])
        risk_per_share = entry - initial_stop

        # Only price action since the position opened may arm the trail. Taking
        # the high over a fixed 250-bar window armed it on pre-entry history, so
        # a minutes-old position could inherit a ten-day high and trail from it.
        # By TIMESTAMP, not by an index into a rolling window. `opened_bars`
        # recorded len(bars) at entry, but `bars` is a rolling 1-month window
        # of 15-minute candles whose length barely changes - so len(bars) minus
        # opened_at collapses to about 1 and `since_entry` became the last bar
        # alone. The trail then measured its high over a single candle and
        # could never arm, silently, for the life of every trend position.
        opened_ts = remembered.get("opened_at_ts")
        if opened_ts:
            since_entry = [b for b in bars if b.timestamp.isoformat() >= opened_ts] or bars[-1:]
        else:
            opened_at = int(remembered.get("opened_bars", len(bars)))
            since_entry = bars[-max(1, len(bars) - opened_at + 1):]
        highest = max(bar.high for bar in since_entry)

        last = bars[-1].close
        if config.entry_rule == "mean_reversion":
            # The exit belongs to the rule that made the entry. Mean reversion
            # leaves the stop where it was placed and closes when the oversold
            # condition resolves, when the stop is hit, or when the holding
            # window runs out. Trailing it would be a different strategy from
            # the one measured, and measuring one thing while trading another
            # is how a record stops meaning anything.
            from .mean_reversion import MeanReversionConfig, should_exit
            armed = False
            stop = initial_stop
            remembered["current"] = stop
            # Daily bars here for the same reason as the entry, and the held
            # count is in DAYS: opened_days is stamped from the daily series at
            # entry, so a position opened on Friday is one day old on Tuesday
            # rather than a hundred fifteen-minute candles old.
            series = daily_bars(symbol)
            # Age is counted from the entry DATE, not from how long the
            # price file happened to be at entry.
            #
            # This used `len(series) - opened_days`, where `opened_days` was
            # the file's length when the position opened. That is an absolute
            # index into a file whose length is a configuration choice: the
            # refresh asks for `days=800` and gets about 548 bars. Change that
            # number - which is exactly what "give the bot more history" means
            # - and len(series) jumps to 2,684 while `opened_days` stays 548,
            # so bars_held becomes 2,136 against a 20-bar limit and EVERY open
            # position time-exits on the next cycle. Nothing about the market
            # would have changed; only the depth of a CSV.
            #
            # `opened_at_ts` is already recorded and is immune to that, so it
            # is preferred and the old arithmetic is kept only for positions
            # opened before this was written. Compared by DATE rather than by
            # ISO string, because the series carries two timestamp conventions
            # - naive 16:00 local and tz-aware 04:00+00:00 - and "16:00" sorts
            # after "04:00+00:00" for the same session.
            opened_at = remembered.get("opened_at_ts")
            entry_day = None
            if opened_at:
                try:
                    entry_day = _parse_stamp(opened_at).date()
                except (TypeError, ValueError):
                    entry_day = None
            if entry_day is not None:
                bars_held = sum(1 for bar in series
                                if bar.timestamp.date() > entry_day)
            else:
                opened_days = remembered.get("opened_days")
                if opened_days is None:
                    opened_days = len(series)
                    remembered["opened_days"] = opened_days
                bars_held = max(0, len(series) - int(opened_days))
            exit_reason = should_exit(
                series, entry, stop, bars_held, _mr(config),
                entry_time=remembered.get("opened_at_ts"),
            ) if series else None
            closing = exit_reason is not None
        else:
            armed = risk_per_share > 0 and (highest - entry) / risk_per_share >= strategy.trail_activate_r
            candidate_stop = highest - strategy.trail_atr_multiple * atr if armed else initial_stop
            stop = max(float(remembered["current"]), candidate_stop)   # ratchet only
            remembered["current"] = stop
            exit_reason = "stop" if last <= stop else None
            closing = last <= stop

        if closing:
            # Free the shares before asking to sell them. Alpaca reserves a
            # position's quantity against any resting sell order, so the
            # protective GTC stop this loop places holds all 106 shares of a
            # 106-share position and the close is refused:
            #
            #   HTTP 403 DELETE /v2/positions/EWY
            #   {"available":"0","existing_qty":"106","held_for_orders":"106",
            #    "message":"insufficient qty available for order"}
            #
            # _reconcile_protective_stops has always cancelled before
            # submitting for exactly this reason; the exit path never did. The
            # effect was that a position could not be closed by the RULE at
            # all once its stop was resting - only by the stop itself - which
            # silently disables every RSI-recovery and holding-cap exit. It
            # surfaced on 2026-09-08 when EWY became the first position to
            # reach an RSI exit while protected.
            if not config.dry_run:
                try:
                    resting = broker.open_sell_orders().get(symbol, [])
                except BrokerError as error:
                    resting = []
                    actions.append(_log(config, "exit_cancel_lookup_failed", {
                        "symbol": symbol, "error": str(error)}))
                for order in resting:
                    cancelled = _with_retry(
                        config, "cancel-for-exit:" + symbol,
                        lambda oid=order["id"]: broker.cancel_order(oid),
                    )
                    actions.append(_log(config, "sell_order_canceled", {
                        "symbol": symbol, "order_id": order["id"],
                        "why": "closing the position", "type": order["type"],
                        "stop_price": order["stop_price"], "result": cancelled,
                    }))
                if resting:
                    # Alpaca frees the reserved shares ASYNCHRONOUSLY. The
                    # first version of this fix cancelled and then closed
                    # seven seconds later, and the close still came back
                    # "insufficient qty available" - the cancel had been
                    # accepted but not yet applied. The exit only landed on a
                    # later cycle, fifteen minutes on.
                    #
                    # So wait for the broker to actually report the orders
                    # gone. Bounded, and it proceeds anyway on timeout: a
                    # close that fails is retried next cycle, while blocking
                    # the loop would hold up every other symbol.
                    for attempt in range(10):
                        time.sleep(1.0)
                        try:
                            if not broker.open_sell_orders().get(symbol):
                                break
                        except BrokerError:
                            break
                    else:
                        actions.append(_log(config, "cancel_did_not_settle", {
                            "symbol": symbol,
                            "note": ("Shares still reserved after 10s. The close "
                                     "is attempted anyway and retried next cycle."),
                        }))
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
                "exit_reason": exit_reason,
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

    # ---- 1b. make sure every position actually has a resting stop ----------
    _reconcile_protective_stops(config, broker, state, actions)

    # ---- 2. open what qualifies --------------------------------------------
    submitted = 0
    near_misses: List[tuple] = []
    if halted:
        actions.append(_log(config, "entries_suspended", {"reason": "daily loss guard"}))
    else:
        candidates = []
        for symbol in sorted(config.universe):
            if not owns(config, symbol):
                continue
            bars = bars_by_symbol.get(symbol)
            if symbol in held or not bars or len(bars) < strategy.minimum_history:
                continue
            bucket = CORRELATION_BUCKETS.get(symbol, "other")
            if bucket in open_buckets or len(held) >= policy.max_open_positions:
                continue
            if config.entry_rule == "mean_reversion":
                candidate = _mean_reversion_candidate(
                    symbol, daily_bars(symbol), equity, policy, costs, strategy,
                    rule_config=_mr(config))
            else:
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

            crypto = is_crypto(candidate.symbol)
            sizing_policy = policy
            if config.require_broker_side_stop and not crypto:
                sizing_policy = replace(policy, allow_fractional_shares=False)
            # Crypto keeps fractional sizing. Whole units are meaningless there
            # - one BTC is most of this account - and unlike equities a
            # fractional crypto position CAN carry a resting stop, because
            # Alpaca accepts stop_limit on it. Probed on the live account
            # 2026-09-04: type "stop" is refused for crypto, "stop_limit" rests.
            # Size against the executable reference, not the signal's close.
            # The stop is a fixed price; if the market gapped up overnight the
            # distance from the fill to that stop is wider than the candidate
            # assumed, so the old quantity would carry MORE than the risk
            # budget - and it would do so exactly when the setup has become
            # less attractive, which is the wrong direction to be wrong in.
            quantity, planned_risk = position_size(
                equity, latest, candidate.stop, sizing_policy, costs
            )
            # Conviction weighting: the same risk appetite, concentrated on the
            # setups that measure better. Validated against a random control -
            # see mean_reversion.conviction for the tables. Applied only under
            # the rule it was measured on.
            if config.entry_rule == "mean_reversion" and quantity > 0:
                from .mean_reversion import conviction
                scale = conviction(daily_bars(candidate.symbol))
                quantity *= scale
                planned_risk *= scale
                # The concentration cap must survive the multiplier. Sizing
                # trimmed this to max_notional_fraction of equity and
                # conviction then scaled it by up to 1.5x, so a stated 20%
                # limit was really admitting 30%. Clamping here rather than
                # lowering the cap touches only positions that would breach,
                # leaving conviction free to size the rest.
                ceiling = equity * policy.max_notional_fraction
                if latest > 0 and quantity * latest > ceiling:
                    trimmed = ceiling / latest
                    planned_risk *= trimmed / quantity
                    quantity = trimmed
                    actions.append(_log(config, "size_capped_by_concentration", {
                        "symbol": candidate.symbol,
                        "ceiling": round(ceiling, 2),
                        "fraction": policy.max_notional_fraction,
                    }))

            # Then cap against the instrument's own liquidity, not the
            # account's size. Admitting crypto meant lowering a $50,000,000
            # liquidity floor to $1,000, and that floor was the only thing
            # stopping the bot sending an order larger than the venue. Alpaca
            # prints about $103,000 a day on BTC and $1,320 on DOT, against a
            # 20%-of-equity position of $20,000. For the liquid equities in the
            # universe this never binds - 2% of GDX's volume is $36,000,000.
            adv = (candidate.features or {}).get("average_dollar_volume")
            capped = cap_by_participation(
                quantity, latest, adv, policy.max_volume_participation)
            if capped < quantity:
                actions.append(_log(config, "size_capped_by_liquidity", {
                    "symbol": candidate.symbol,
                    "wanted": round(quantity, 9), "allowed": round(capped, 9),
                    "average_dollar_volume": adv,
                    "participation": policy.max_volume_participation,
                }))
                quantity = capped

            # Whole shares LAST, not first.
            #
            # `sizing_policy` above sets allow_fractional_shares=False so the
            # position can carry a resting GTC stop - Alpaca refuses one on a
            # fractional quantity. But conviction then multiplies by 0.5-1.5x
            # and the liquidity cap scales again, and either turns 51 whole
            # shares back into 76.5. The guard was established and then
            # silently undone two lines later.
            #
            # This is not theoretical. Both RTX entries on 2026-09-08 were
            # 51 x 1.5 = 76.5 and 53 x 1.5 = 79.5 shares, and every cycle
            # afterwards logged protective_stop_FAILED: "Alpaca cannot rest a
            # GTC stop on a fractional quantity". The position sat unprotected
            # all session. Because conviction returns a non-integer for any
            # setup that is not exactly at the top or bottom of its range,
            # essentially EVERY equity position was affected.
            #
            # Flooring costs at most one share - 0.65% of a 77-share position -
            # and buys the stop that require_broker_side_stop exists to
            # guarantee. Risk is rescaled to the shares actually bought so the
            # recorded planned_risk stays true to the order.
            if not sizing_policy.allow_fractional_shares and quantity > 0:
                whole = float(floor(quantity + 1e-9))
                if whole > 0:
                    planned_risk *= whole / quantity
                quantity = whole

            if quantity <= 0:
                actions.append(_log(config, "too_small_for_a_protected_order", {
                    "symbol": candidate.symbol,
                    "reason": (
                        "Sizing yields zero at this equity, stop distance and "
                        "liquidity cap, so no order is sent."
                    ),
                }))
                continue

            # Sizing is a fraction of EQUITY, so several positions can add up
            # past what is actually in the account. Skipping here rather than
            # shrinking: a position sized to something other than the rule is
            # not the rule, and a smaller one would carry the friction of a
            # trade without the exposure it was sized for.
            cost = quantity * float(latest)
            if cost > cash_available:
                actions.append(_log(config, "skipped_no_cash", {
                    "symbol": candidate.symbol,
                    "cost": round(cost, 2),
                    "cash_available": round(cash_available, 2),
                    "note": (
                        "Buying power would cover this on margin. Cash is used "
                        "deliberately: the sizing that justified this cap was "
                        "measured without borrowing."
                    ),
                }))
                continue
            cash_available -= cost
            result = broker.submit_reviewed_candidate(
                candidate.symbol, quantity,
                stop=candidate.stop, target=candidate.target,
                dry_run=config.dry_run,
            )
            submitted += 1
            open_buckets.add(bucket)
            held[candidate.symbol] = {"symbol": candidate.symbol}
            # Record the exact stop submitted with this entry. Without it the
            # next cycle rebuilds one from the CURRENT ATR - a different number
            # from the one the order carries, and under mean reversion a
            # different rule entirely, since that stop comes from evaluate()
            # rather than from an ATR multiple. The reconciler then rests that
            # invented level at the broker. A stop is an entry-time fact.
            stop_state = {
                "initial": float(candidate.stop),
                "current": float(candidate.stop),
                "opened_bars": len(bars),
                # The timestamp is what survives a rolling window; the length
                # does not. See the trail computation in section 1.
                "opened_at_ts": bars[-1].timestamp.isoformat(),
            }
            if config.entry_rule == "mean_reversion":
                stop_state["opened_days"] = len(daily_bars(candidate.symbol))
            state.setdefault("stops", {})[candidate.symbol] = stop_state
            # The feature vector is written down at entry because that is the
            # only moment it exists. Without it a completed trade cannot become
            # a training example later, and the retraining loop would only ever
            # re-read price history - learning from hypotheticals rather than
            # from what the bot actually did.
            actions.append(_log(config, "entry", {
                "symbol": candidate.symbol, "score": round(candidate.score, 1),
                "quantity": quantity, "stop": candidate.stop,
                "entry_reference": candidate.entry,
                "sizing_reference": latest,
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
        "asset_class": config.asset_class,
        "broker_equity": round(broker_equity, 2),
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
