"""Command-line interface.  All commands are research or paper-trading only."""

import argparse
import json
from datetime import date
import os
import sys
from pathlib import Path
from typing import List, Sequence

from .backfill import allocate_fees, merge_into_log, round_trips_from_fills
from .backtest import walk_forward_backtest
from .autotrade import AutoTradeConfig, run_once
from .trade_learning import (
    examples_from_audit_log,
    export_pine,
    generate_examples,
    save_examples,
    save_model as save_trade_model,
    train_trade_model,
)
from .broker import AlpacaPaperBroker, BrokerConfig, BrokerError
from .data import fetch_yahoo_bars, load_bars, save_bars
from .events import fetch_rss_events, load_events, save_events
from .journal import append_candidate
from .ledger import load_ledger, reset_ledger, save_ledger
from .preflight import run_preflight, strategy_expectation
from .daily_report import render as render_day
from .live_model import load_training, train_live_model
from .record import from_audit_log, from_portfolio
from .manual import (
    HeldPosition,
    advance_stop,
    apply_stop_update,
    daily_brief,
    load_positions,
    save_positions,
)
from .learning import forecast_scenario, load_examples, load_model, save_model, train_model
from .risk import RISK_PROFILES, CostModel, RiskPolicy, policy_for_profile
from .strategy import DEFAULT_UNIVERSE, StrategyConfig, generate_candidate
from .social import entities_from_file, sources_from_file, watch
from .types import Action, Candidate, Event


def _events(path: str) -> List[Event]:
    return load_events(Path(path)) if path else []


def _emit(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _policy(args: argparse.Namespace) -> RiskPolicy:
    """Build the risk policy, letting --risk-profile set the baseline."""
    profile = getattr(args, "risk_profile", None)
    if profile:
        overrides = {}
        # An explicit --risk-per-trade still wins over the profile's value.
        if getattr(args, "risk_per_trade", None) not in (None, 0.005):
            overrides["risk_per_trade"] = args.risk_per_trade
        return policy_for_profile(profile, **overrides)
    return RiskPolicy(
        risk_per_trade=args.risk_per_trade,
        max_daily_loss=args.max_daily_loss,
        max_weekly_loss=args.max_weekly_loss,
    )


def _candidate(symbol: str, price_file: Path, events: Sequence[Event], args: argparse.Namespace) -> Candidate:
    return generate_candidate(symbol, load_bars(price_file), events, args.account, _policy(args), CostModel())


def command_fetch(args: argparse.Namespace) -> int:
    bars = fetch_yahoo_bars(args.symbol, args.period, args.interval)
    destination = Path(args.out)
    save_bars(destination, bars)
    _emit({"status": "downloaded", "symbol": args.symbol.upper(), "bars": len(bars), "out": str(destination), "note": "Market data only; no broker connection or order was created."})
    return 0


def command_analyze(args: argparse.Namespace) -> int:
    candidate = _candidate(args.symbol, Path(args.prices), _events(args.events), args)
    payload = candidate.as_dict()
    payload["disclaimer"] = "Evidence score is not a calibrated probability or a recommendation. PAPER_LONG remains paper-only."
    _emit(payload)
    if args.journal:
        if candidate.action != Action.PAPER_LONG:
            raise ValueError("The candidate was not cleared; nothing was journaled")
        append_candidate(Path(args.journal), candidate, args.edge, args.thesis)
        print("Paper plan appended to {0}; no order was submitted.".format(args.journal))
    return 0


def command_screen(args: argparse.Namespace) -> int:
    events = _events(args.events)
    output_dir = Path(args.out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    results = []
    selected_buckets = []
    for symbol in symbols:
        if symbol not in DEFAULT_UNIVERSE:
            raise ValueError("{0} is not in the conservative default universe".format(symbol))
        bars = fetch_yahoo_bars(symbol, args.period, "1d")
        price_file = output_dir / (symbol + ".csv")
        save_bars(price_file, bars)
        candidate = generate_candidate(
            symbol,
            bars,
            events,
            args.account,
            _policy(args),
            CostModel(),
            open_positions=len(selected_buckets),
            open_buckets=selected_buckets,
        )
        results.append(candidate.as_dict())
        if candidate.action == Action.PAPER_LONG:
            selected_buckets.append(candidate.correlation_bucket)
    _emit({"mode": "paper_research_screen", "results": results, "note": "No orders were created. Rejections are expected and desirable when conditions are weak."})
    return 0


def command_backtest(args: argparse.Namespace) -> int:
    bars = load_bars(Path(args.prices))
    report = walk_forward_backtest(args.symbol, bars, _events(args.events), args.account, args.out_of_sample_fraction, _policy(args), CostModel())
    payload = report.as_dict()
    payload["disclaimer"] = "Historical simulation, not evidence of future profitability. Costs, data quality, regimes, and execution can invalidate a backtest."
    _emit(payload)
    return 0


def command_rss(args: argparse.Namespace) -> int:
    events = fetch_rss_events(args.feed, args.max_items)
    save_events(Path(args.out), events)
    _emit({"status": "review_queue_written", "count": len(events), "out": args.out, "note": "These are low-confidence keyword labels. Verify each against a primary source before use."})
    return 0


def command_social(args: argparse.Namespace) -> int:
    """Poll trusted sources into an auditable review queue; never place an order."""
    sources, settings = sources_from_file(Path(args.sources))
    entities = entities_from_file(Path(args.entities))
    enabled_sources = [source for source in sources if source.enabled]
    if not enabled_sources:
        raise ValueError("No social sources are enabled. Verify a source, then set enabled to true in the source file.")
    configured_poll_seconds = int(settings.get("poll_seconds", 30))
    configured_max_age = int(settings.get("max_post_age_minutes", 10))
    poll_seconds = args.poll_seconds if args.poll_seconds is not None else configured_poll_seconds
    max_age = args.max_post_age_minutes if args.max_post_age_minutes is not None else configured_max_age
    token = os.environ.get(args.x_token_env, "")
    alerts = watch(
        enabled_sources,
        entities,
        Path(args.state),
        Path(args.journal),
        x_bearer_token=token,
        max_post_age_minutes=max_age,
        poll_seconds=poll_seconds,
        iterations=args.iterations,
    )
    _emit(
        {
            "mode": "verified_social_paper_monitor",
            "enabled_sources": [source.name for source in enabled_sources],
            "alerts": [alert.as_dict() for alert in alerts],
            "note": "REVIEW_REQUIRED means an exact, pinned-source post mentioned an entity. It is not a buy/sell signal and cannot submit an order.",
        }
    )
    return 0


def command_train(args: argparse.Namespace) -> int:
    examples = load_examples(Path(args.examples))
    model = train_model(
        examples,
        min_examples=args.min_examples,
        learning_rate=args.learning_rate,
        epochs=args.epochs,
        l2=args.l2,
    )
    save_model(Path(args.model), model)
    _emit(
        {
            "status": model.status,
            "model": args.model,
            "report": model.report,
            "note": "Training uses completed, reviewed paper outcomes only. This model cannot execute orders.",
        }
    )
    return 0


def command_forecast(args: argparse.Namespace) -> int:
    raw_scenario = json.loads(Path(args.scenario).read_text(encoding="utf-8"))
    if not isinstance(raw_scenario, dict):
        raise ValueError("Scenario must be one JSON object")
    _emit(forecast_scenario(load_model(Path(args.model)), raw_scenario))
    return 0


def _shared_risk_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--account", type=float, default=10_000.0, help="Paper account equity; default: 10000")
    parser.add_argument("--risk-per-trade", type=float, default=0.005, help="Fraction of equity at risk; default: 0.005")
    parser.add_argument("--max-daily-loss", type=float, default=0.015, help="Fractional daily loss guard; default: 0.015")
    parser.add_argument("--max-weekly-loss", type=float, default=0.06, help="Fractional weekly loss guard; default: 0.06")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Event-aware, long-only paper-trading research tool. Never sends orders.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch = subparsers.add_parser("fetch", help="Download OHLCV data from Yahoo Finance")
    fetch.add_argument("--symbol", required=True)
    fetch.add_argument("--period", default="2y")
    fetch.add_argument("--interval", default="1d", choices=("1d", "1h", "30m", "15m", "5m"))
    fetch.add_argument("--out", required=True)
    fetch.set_defaults(handler=command_fetch)

    analyze = subparsers.add_parser("analyze", help="Evaluate one local price file as a paper candidate")
    analyze.add_argument("--symbol", required=True)
    analyze.add_argument("--prices", required=True)
    analyze.add_argument("--events", default="")
    analyze.add_argument("--journal", default="", help="Optional JSONL paper journal; requires a cleared candidate")
    analyze.add_argument("--edge", default="", help="Named source of edge required when journaling")
    analyze.add_argument("--thesis", default="", help="Falsifiable thesis required when journaling")
    _shared_risk_options(analyze)
    analyze.set_defaults(handler=command_analyze)

    screen = subparsers.add_parser("screen", help="Download and screen the liquid default ETF universe")
    screen.add_argument("--symbols", default=",".join(DEFAULT_UNIVERSE))
    screen.add_argument("--events", default="")
    screen.add_argument("--period", default="2y")
    screen.add_argument("--out-dir", default="data")
    _shared_risk_options(screen)
    screen.set_defaults(handler=command_screen)

    backtest = subparsers.add_parser("backtest", help="Run a fixed-rule chronological split backtest")
    backtest.add_argument("--symbol", required=True)
    backtest.add_argument("--prices", required=True)
    backtest.add_argument("--events", default="")
    backtest.add_argument("--out-of-sample-fraction", type=float, default=0.30)
    _shared_risk_options(backtest)
    backtest.set_defaults(handler=command_backtest)

    rss = subparsers.add_parser("rss", help="Make a review queue from an RSS or Atom feed")
    rss.add_argument("--feed", required=True)
    rss.add_argument("--out", required=True)
    rss.add_argument("--max-items", type=int, default=20)
    rss.set_defaults(handler=command_rss)

    social = subparsers.add_parser("social", help="Monitor configured, pinned social sources and write paper-only review alerts")
    social.add_argument("--sources", required=True, help="Verified social-source JSON configuration")
    social.add_argument("--entities", required=True, help="Reviewed company/ticker alias JSON configuration")
    social.add_argument("--state", default="data/social-state.json", help="Deduplication state file")
    social.add_argument("--journal", default="data/social-alerts.jsonl", help="Append-only social alert journal")
    social.add_argument("--x-token-env", default="X_BEARER_TOKEN", help="Environment-variable name for the X bearer token")
    social.add_argument("--poll-seconds", type=int, default=None, help="Polling interval; uses config if omitted, minimum 5 seconds")
    social.add_argument("--max-post-age-minutes", type=int, default=None, help="Stale-post threshold; uses config if omitted")
    social.add_argument("--iterations", type=int, default=1, help="Number of polls; use 0 only when deliberately running as a monitor")
    social.set_defaults(handler=command_social)

    brief = subparsers.add_parser(
        "brief", help="Morning instruction list for trading the rules by hand"
    )
    brief.add_argument("--account", type=float, default=1000.0, help="Account equity for sizing")
    brief.add_argument("--data-dir", default="data")
    brief.add_argument("--positions", default="data/positions.json")
    brief.add_argument("--events", default="")
    brief.add_argument("--refresh", action="store_true", help="Download fresh daily bars first")
    brief.add_argument("--period", default="2y")
    brief.add_argument("--apply-stops", action="store_true", help="Persist the new stop levels")
    brief.add_argument(
        "--risk-profile", choices=sorted(RISK_PROFILES),
        help="Named position-sizing profile; see docs for measured results",
    )
    brief.add_argument("--risk-per-trade", type=float, default=0.005)
    brief.add_argument("--max-daily-loss", type=float, default=0.015)
    brief.add_argument("--max-weekly-loss", type=float, default=0.06)
    brief.set_defaults(handler=command_brief)

    log_fill = subparsers.add_parser(
        "log-fill", help="Record a fill you made by hand (manual trading)"
    )
    log_fill.add_argument("--symbol", required=True)
    log_fill.add_argument("--quantity", type=float, required=True)
    log_fill.add_argument("--price", type=float, required=True, help="Your actual fill price")
    log_fill.add_argument("--stop", type=float, required=True, help="The stop you placed")
    log_fill.add_argument("--date", required=True, help="Fill date, YYYY-MM-DD")
    log_fill.add_argument("--note", default="")
    log_fill.add_argument("--positions", default="data/positions.json")
    log_fill.set_defaults(handler=command_log_fill)

    close = subparsers.add_parser("close", help="Remove a position after you have sold it")
    close.add_argument("--symbol", required=True)
    close.add_argument("--positions", default="data/positions.json")
    close.set_defaults(handler=command_close)

    autotrade = subparsers.add_parser(
        "autotrade",
        help="Run one fully automatic cycle against the Alpaca PAPER account",
    )
    autotrade.add_argument("--interval", default="1d", choices=("1d", "1h", "30m", "15m", "5m"))
    autotrade.add_argument("--period", default="2y")
    autotrade.add_argument("--exit-mode", default="trailing", choices=("trailing", "fixed_time"))
    autotrade.add_argument("--max-orders", type=int, default=3)
    autotrade.add_argument(
        "--live", action="store_true",
        help="Actually submit to the paper account. Without this it is a dry run.",
    )
    autotrade.add_argument("--audit-log", default="data/autotrade-audit.jsonl")
    autotrade.add_argument("--state-file", default="data/autotrade-state.json")
    autotrade.add_argument(
        "--risk-profile", choices=sorted(RISK_PROFILES),
        help="Named position-sizing profile; see docs for measured results",
    )
    autotrade.add_argument("--risk-per-trade", type=float, default=0.005)
    autotrade.add_argument("--max-daily-loss", type=float, default=0.015)
    autotrade.add_argument("--max-weekly-loss", type=float, default=0.06)
    autotrade.set_defaults(handler=command_autotrade)

    learn = subparsers.add_parser(
        "learn", help="Regenerate labeled examples from history and retrain the trade model"
    )
    learn.add_argument("--data-dir", default="data")
    learn.add_argument("--interval", default="1d", choices=("1d", "1h", "30m", "15m", "5m"))
    learn.add_argument("--account", type=float, default=1000.0)
    learn.add_argument("--events", default="")
    learn.add_argument("--examples", default="data/trade-examples.jsonl")
    learn.add_argument(
        "--audit-log", default="data/autotrade-audit.jsonl",
        help="Executed trades to fold into training alongside the simulated set",
    )
    learn.add_argument("--model", default="data/trade-model.json")
    learn.add_argument(
        "--pine", default="", help="Also export the fitted model as Pine Script to this path"
    )
    learn.set_defaults(handler=command_learn)

    ledger = subparsers.add_parser(
        "ledger", help="Show or reset the simulated balance carried between runs"
    )
    ledger.add_argument("--path", default="data/ledger.json")
    ledger.add_argument("--starting-equity", type=float, default=1000.0)
    ledger.add_argument("--reset", action="store_true")
    ledger.set_defaults(handler=command_ledger)

    preflight = subparsers.add_parser(
        "preflight", help="Check whether the bot is safe to let run unattended"
    )
    preflight.add_argument("--data-dir", default="data")
    preflight.add_argument("--account", type=float, default=1000.0)
    preflight.add_argument("--interval", default="1d", choices=("1d", "1h", "30m", "15m", "5m"))
    preflight.add_argument("--max-age-days", type=int, default=5)
    preflight.add_argument("--skip-broker", action="store_true")
    preflight.add_argument("--risk-profile", choices=sorted(RISK_PROFILES))
    preflight.add_argument("--risk-per-trade", type=float, default=0.005)
    preflight.add_argument("--max-daily-loss", type=float, default=0.015)
    preflight.add_argument("--max-weekly-loss", type=float, default=0.06)
    preflight.set_defaults(handler=command_preflight)

    record = subparsers.add_parser(
        "record", help="Assess the accumulated paper record: does it prove anything yet?"
    )
    record.add_argument("--audit-log", default="data/autotrade-audit.jsonl")
    record.add_argument("--account", type=float, default=1000.0)
    record.set_defaults(handler=command_record)

    backfill = subparsers.add_parser(
        "backfill-audit",
        help="Recover closed trades the broker has but this machine's audit log does not",
    )
    backfill.add_argument("--audit-log", default="data/autotrade-audit.jsonl")
    backfill.add_argument(
        "--dry-run", action="store_true",
        help="Report what would be added without writing the log",
    )
    backfill.set_defaults(handler=command_backfill_audit)

    daily = subparsers.add_parser(
        "daily-report", help="End-of-session report: what traded and what it earned"
    )
    daily.add_argument("--audit-log", default="data/autotrade-audit.jsonl")
    daily.add_argument("--session", default="", help="YYYY-MM-DD; defaults to today")
    daily.add_argument("--account", type=float, default=None)
    daily.add_argument("--out", default="", help="Also write the report here")
    daily.set_defaults(handler=command_daily_report)

    retrain = subparsers.add_parser(
        "retrain", help="Refit the live model, including every trade closed so far"
    )
    retrain.add_argument("--training", default="data/live-training.jsonl")
    retrain.add_argument("--seed", default="data/big-dataset.jsonl",
                         help="Historical examples to train alongside live trades")
    retrain.add_argument("--model", default="data/live-model.json")
    retrain.set_defaults(handler=command_retrain)

    account = subparsers.add_parser(
        "account",
        help="Show the connected Alpaca PAPER account, positions, and recent orders",
    )
    account.add_argument(
        "--positions", action="store_true", help="Include open positions and recent orders"
    )
    account.set_defaults(handler=command_account)

    train = subparsers.add_parser("train", help="Train and evaluate a paper-outcome model using a chronological holdout")
    train.add_argument("--examples", required=True, help="JSONL of reviewed, completed paper scenarios")
    train.add_argument("--model", default="data/research-model.json", help="Destination model JSON")
    train.add_argument("--min-examples", type=int, default=200, help="Minimum examples before a model can be a research candidate")
    train.add_argument("--learning-rate", type=float, default=0.08)
    train.add_argument("--epochs", type=int, default=600)
    train.add_argument("--l2", type=float, default=0.02)
    train.set_defaults(handler=command_train)

    forecast = subparsers.add_parser("forecast", help="Score a human-defined paper scenario with a trained research model")
    forecast.add_argument("--model", required=True)
    forecast.add_argument("--scenario", required=True, help="One reviewed scenario JSON; direction is mandatory")
    forecast.set_defaults(handler=command_forecast)
    return parser


def _load_universe(data_dir: Path):
    """Load whatever local price files exist for the default universe."""
    series = {}
    for symbol in DEFAULT_UNIVERSE:
        path = data_dir / "{0}.csv".format(symbol)
        if path.exists():
            series[symbol] = load_bars(path)
    return series


def command_brief(args: argparse.Namespace) -> int:
    """The morning instruction list for trading the rules by hand."""
    data_dir = Path(args.data_dir)
    if args.refresh:
        for symbol in DEFAULT_UNIVERSE:
            try:
                save_bars(data_dir / "{0}.csv".format(symbol), fetch_yahoo_bars(symbol, args.period, "1d"))
            except Exception as error:  # a stale file beats a half-written one
                _emit({"status": "fetch_failed", "symbol": symbol, "error": str(error)})
                return 1
    series = _load_universe(data_dir)
    if not series:
        _emit({"status": "no_data", "hint": "Run with --refresh, or use the fetch command first."})
        return 1
    positions_path = Path(args.positions)
    positions = load_positions(positions_path)
    brief = daily_brief(series, positions, args.account, _events(args.events), _policy(args), CostModel())
    if args.apply_stops:
        for position in positions:
            bars = series.get(position.symbol.upper())
            if bars:
                apply_stop_update(position, advance_stop(position, bars))
        save_positions(positions_path, positions)
        brief["stops_persisted_to"] = str(positions_path)
    _emit(brief)
    return 0


def command_log_fill(args: argparse.Namespace) -> int:
    """Record a fill you made yourself, so the brief can manage its stop.

    Renamed from command_record: a second function of that name later in this
    module shadowed it, and a second subparser named "record" shadowed its
    subcommand, so both were unreachable.
    """
    positions_path = Path(args.positions)
    positions = load_positions(positions_path)
    symbol = args.symbol.upper()
    if any(p.symbol.upper() == symbol for p in positions):
        _emit({"status": "already_held", "symbol": symbol})
        return 1
    if args.stop >= args.price:
        _emit({"status": "invalid", "error": "stop must be below the entry price"})
        return 1
    positions.append(
        HeldPosition(
            symbol=symbol,
            quantity=args.quantity,
            entry_price=args.price,
            entry_date=args.date,
            initial_stop=args.stop,
            current_stop=args.stop,
            highest_high=args.price,
            note=args.note,
        )
    )
    save_positions(positions_path, positions)
    _emit({"status": "recorded", "symbol": symbol, "positions_now": len(positions)})
    return 0


def command_close(args: argparse.Namespace) -> int:
    """Drop a position from the book after you have sold it."""
    positions_path = Path(args.positions)
    positions = load_positions(positions_path)
    symbol = args.symbol.upper()
    remaining = [p for p in positions if p.symbol.upper() != symbol]
    if len(remaining) == len(positions):
        _emit({"status": "not_held", "symbol": symbol})
        return 1
    save_positions(positions_path, remaining)
    _emit({"status": "closed", "symbol": symbol, "positions_now": len(remaining)})
    return 0


def command_autotrade(args: argparse.Namespace) -> int:
    """One fully automatic cycle: manage stops, exit, and enter. No human step."""
    config = AutoTradeConfig(
        interval=args.interval,
        period=args.period,
        max_orders_per_run=args.max_orders,
        dry_run=not args.live,
        audit_log=Path(args.audit_log),
        state_file=Path(args.state_file),
    )
    strategy = StrategyConfig.for_interval(args.interval, exit_mode=args.exit_mode)
    try:
        result = run_once(config, strategy=strategy, policy=_policy(args), costs=CostModel())
    except BrokerError as error:
        _emit({"status": "not_connected", "error": str(error)})
        return 1
    _emit(result)
    return 0


def command_learn(args: argparse.Namespace) -> int:
    """Regenerate labeled examples from history and retrain the trade model."""
    data_dir = Path(args.data_dir)
    series = {}
    for symbol in DEFAULT_UNIVERSE:
        path = data_dir / "{0}.csv".format(symbol)
        if path.exists():
            series[symbol] = load_bars(path)
    if not series:
        _emit({"status": "no_data", "hint": "Fetch price history first."})
        return 1
    config = StrategyConfig.for_interval(args.interval, exit_mode="trailing")
    simulated = generate_examples(series, _events(args.events), args.account, CostModel(), config)

    # Trades the bot actually placed are the better evidence - real fills, real
    # slippage, real timing - but there are very few of them for a long time,
    # so they supplement the simulated set rather than replacing it. Without
    # this, a weekly retrain re-reads the same price history and barely moves.
    executed = examples_from_audit_log(Path(args.audit_log))
    examples = sorted(simulated + executed, key=lambda e: e.as_of)

    if len(examples) < 30:
        _emit({"status": "insufficient_examples", "count": len(examples)})
        return 1
    save_examples(Path(args.examples), examples)
    model = train_trade_model(examples)
    save_trade_model(Path(args.model), model)
    if args.pine:
        Path(args.pine).parent.mkdir(parents=True, exist_ok=True)
        Path(args.pine).write_text(export_pine(model), encoding="utf-8")
    _emit({
        "status": "trained",
        "examples": len(examples),
        "from_simulation": len(simulated),
        "from_executed_trades": len(executed),
        "positives": sum(e.label for e in examples),
        "model_status": model.status,
        "examples_file": args.examples,
        "model_file": args.model,
        "pine_file": args.pine if args.pine else None,
        "report": model.report,
    })
    return 0


def command_ledger(args: argparse.Namespace) -> int:
    """Show or reset the balance that carries between runs."""
    path = Path(args.path)
    if args.reset:
        ledger = reset_ledger(path, args.starting_equity)
        _emit({"status": "reset", "current_equity": ledger.current_equity})
        return 0
    _emit(load_ledger(path, args.starting_equity).as_dict())
    return 0


def command_preflight(args: argparse.Namespace) -> int:
    """Is this safe to let run unattended? Exit code 0 only if yes."""
    report = run_preflight(
        data_dir=Path(args.data_dir),
        equity=args.account,
        policy=_policy(args),
        config=StrategyConfig.for_interval(args.interval, exit_mode="trailing"),
        max_age_days=args.max_age_days,
        check_broker=not args.skip_broker,
    )
    payload = report.as_dict()
    payload["strategy_expectation"] = strategy_expectation()
    _emit(payload)
    return 0 if report.ready else 1


def command_record(args: argparse.Namespace) -> int:
    """What the accumulated paper record proves, if anything."""
    report = from_audit_log(Path(args.audit_log), args.account)
    payload = report.as_dict()
    payload["source"] = args.audit_log
    payload["note"] = (
        "Rebuilt from the autotrade audit log. Realized P&L appears only for "
        "exits the broker has reported, so a fresh log shows trades with zero "
        "P&L rather than invented numbers."
    )
    _emit(payload)
    return 0


def command_backfill_audit(args: argparse.Namespace) -> int:
    """Recover trades the broker recorded but this machine's log never saw.

    The case this exists for is moving the bot to another computer. The
    account keeps its history; the new machine starts with an empty log, and
    every statistic is then computed from whatever happened after the move.
    """
    try:
        broker = AlpacaPaperBroker(BrokerConfig.from_environment())
        fills = broker.fill_activities()
        fees = broker.fee_activities()
    except BrokerError as error:
        _emit({"status": "not_connected", "error": str(error)})
        return 1

    trips = round_trips_from_fills(fills)
    per_trip, unallocated = allocate_fees(trips, fees)
    path = Path(args.audit_log)

    if args.dry_run:
        _emit({
            "status": "DRY_RUN_NOTHING_WRITTEN",
            "fills_seen": len(fills),
            "closed_round_trips": len(trips),
            "unallocated_fees": unallocated,
            "trips": [
                {
                    "symbol": t["symbol"], "opened": t["opened"], "closed": t["closed"],
                    "quantity": round(float(t["quantity"]), 6),
                    "realized_pnl": round(
                        float(t["proceeds"]) - float(t["cost"]) - f, 2
                    ),
                }
                for t, f in zip(trips, per_trip)
            ],
        })
        return 0

    summary = merge_into_log(path, trips, per_trip)
    summary["status"] = "ok"
    summary["audit_log"] = str(path)
    summary["unallocated_fees"] = unallocated
    summary["note"] = (
        "Rebuilt from the broker's own fill activities. Re-running this is "
        "safe: a trip the log already covers is skipped, not duplicated."
    )
    _emit(summary)
    return 0


def command_daily_report(args: argparse.Namespace) -> int:
    """What today's session did, and what the record proves so far."""
    session = date.fromisoformat(args.session) if args.session else None
    payload = render_day(Path(args.audit_log), session, args.account)
    _emit(payload)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                                  encoding="utf-8")
    return 0


def command_retrain(args: argparse.Namespace) -> int:
    """Refit the live model on everything, including trades just closed."""
    rows = load_training(Path(args.training))
    if args.seed and Path(args.seed).exists():
        for line in Path(args.seed).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows.append({"at": raw.get("d", ""), "symbol": raw.get("s", ""),
                         "f": raw.get("f", {}), "r": raw.get("r", 0.0),
                         "label": raw.get("label", 0)})
    model = train_live_model(rows, Path(args.model))
    if model is None:
        _emit({"status": "not_enough_examples", "have": len(rows)})
        return 1
    _emit({
        "status": "retrained",
        "examples": model.n_examples,
        "from_live_trades": len(load_training(Path(args.training))),
        "holdout_auc": round(model.test_auc, 4),
        "model_status": model.status,
        "usable": model.usable,
    })
    return 0


def command_account(args: argparse.Namespace) -> int:
    """Read-only view of the real paper account. Submits nothing."""
    try:
        broker = AlpacaPaperBroker(BrokerConfig.from_environment())
        payload = {"account": broker.account()}
        if args.positions:
            payload["positions"] = broker.positions()
            payload["recent_orders"] = broker.recent_orders(limit=25)
    except BrokerError as error:
        _emit({"status": "not_connected", "error": str(error)})
        return 1
    _emit(payload)
    return 0


def main(argv: Sequence[str] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))
        return 2


if __name__ == "__main__":
    sys.exit(main())
