"""Command-line interface.  All commands are research or paper-trading only."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Sequence

from .backtest import walk_forward_backtest
from .data import fetch_yahoo_bars, load_bars, save_bars
from .events import fetch_rss_events, load_events, save_events
from .journal import append_candidate
from .learning import forecast_scenario, load_examples, load_model, save_model, train_model
from .risk import CostModel, RiskPolicy
from .strategy import DEFAULT_UNIVERSE, generate_candidate
from .social import entities_from_file, sources_from_file, watch
from .types import Action, Candidate, Event


def _events(path: str) -> List[Event]:
    return load_events(Path(path)) if path else []


def _emit(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _policy(args: argparse.Namespace) -> RiskPolicy:
    return RiskPolicy(risk_per_trade=args.risk_per_trade, max_daily_loss=args.max_daily_loss, max_weekly_loss=args.max_weekly_loss)


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
