"""Pre-deployment checks: is this safe to let run unattended?

Deployment readiness and profitability are separate questions. Everything
here answers the first one - will it run, will it stay inside its risk
limits, will it fail loudly rather than silently. None of it is evidence
that the strategy makes money, and `strategy_expectation` deliberately
reports the measured history so that is visible at the point of launch
rather than buried in a document.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .broker import LIVE_ENDPOINT, PAPER_ENDPOINT, AlpacaPaperBroker, BrokerConfig, BrokerError
from .data import load_bars, price_file
from .risk import CostModel, RiskPolicy, position_size
from .strategy import DEFAULT_UNIVERSE, StrategyConfig, generate_candidate


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    blocking: bool = True


@dataclass
class PreflightReport:
    checks: List[Check] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str, blocking: bool = True) -> None:
        self.checks.append(Check(name, passed, detail, blocking))

    @property
    def blocking_failures(self) -> List[Check]:
        return [c for c in self.checks if c.blocking and not c.passed]

    @property
    def warnings(self) -> List[Check]:
        return [c for c in self.checks if not c.blocking and not c.passed]

    @property
    def ready(self) -> bool:
        return not self.blocking_failures

    def as_dict(self) -> Dict[str, object]:
        return {
            "ready_to_run": self.ready,
            "blocking_failures": [c.name for c in self.blocking_failures],
            "warnings": [c.name for c in self.warnings],
            "checks": [
                {"name": c.name, "passed": c.passed, "blocking": c.blocking, "detail": c.detail}
                for c in self.checks
            ],
        }


def _check_credentials(report: PreflightReport) -> Optional[AlpacaPaperBroker]:
    try:
        config = BrokerConfig.from_environment()
    except BrokerError as error:
        report.add("broker credentials", False, str(error))
        return None
    report.add("broker credentials", True, "APCA key and secret are present in the environment")

    if config.endpoint == LIVE_ENDPOINT:
        report.add("paper endpoint", False, "APCA_API_BASE_URL points at the LIVE endpoint")
        return None
    if config.endpoint != PAPER_ENDPOINT:
        report.add("paper endpoint", False, "Unrecognised endpoint {0!r}".format(config.endpoint))
        return None
    report.add("paper endpoint", True, "Pointed at {0}".format(PAPER_ENDPOINT))

    try:
        broker = AlpacaPaperBroker(config)
        account = broker.account()
    except BrokerError as error:
        report.add("broker reachable", False, str(error))
        return None
    report.add(
        "broker reachable", True,
        "account {0}, equity ${1:,.2f}, status {2}".format(
            account.get("account_number"), account.get("equity", 0.0), account.get("status")
        ),
    )
    report.add(
        "trading not blocked", not account.get("trading_blocked", False),
        "broker reports trading_blocked={0}".format(account.get("trading_blocked")),
    )
    return broker


def _check_data(report: PreflightReport, data_dir: Path, max_age_days: int) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    missing: List[str] = []
    stale: List[str] = []
    now = datetime.now(timezone.utc)
    for symbol in DEFAULT_UNIVERSE:
        path = price_file(data_dir, symbol)
        if not path.exists():
            missing.append(symbol)
            continue
        try:
            bars = load_bars(path)
        except (OSError, ValueError) as error:
            missing.append("{0} ({1})".format(symbol, error))
            continue
        counts[symbol] = len(bars)
        last = bars[-1].timestamp
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if now - last > timedelta(days=max_age_days):
            stale.append("{0}@{1}".format(symbol, last.date()))

    report.add(
        "price files present", not missing,
        "missing: {0}".format(", ".join(missing)) if missing else
        "{0} of {1} symbols present".format(len(counts), len(DEFAULT_UNIVERSE)),
    )
    report.add(
        "price data fresh", not stale,
        "stale (older than {0}d): {1}".format(max_age_days, ", ".join(stale)) if stale
        else "newest bars are within {0} days".format(max_age_days),
        blocking=False,
    )
    thin = [s for s, n in counts.items() if n < StrategyConfig().minimum_history]
    report.add(
        "enough history to decide", not thin,
        "too short: {0}".format(", ".join(thin)) if thin else
        "every file clears the {0}-bar warmup".format(StrategyConfig().minimum_history),
    )
    return counts


def _check_risk(report: PreflightReport, equity: float, policy: RiskPolicy) -> None:
    report.add(
        "no leverage", policy.max_notional_fraction <= 1.0,
        "max notional per position is {0:.0%} of equity".format(policy.max_notional_fraction),
    )
    report.add(
        "loss guards set",
        0 < policy.max_daily_loss < 1 and 0 < policy.max_weekly_loss < 1,
        "daily {0:.1%}, weekly {1:.1%}".format(policy.max_daily_loss, policy.max_weekly_loss),
    )
    budget = equity * policy.risk_per_trade
    quantity, planned = position_size(equity, 100.0, 98.0, policy, CostModel())
    report.add(
        "sizing respects the risk cap", planned <= budget + 1e-9,
        "on ${0:,.0f}, one position risks at most ${1:,.2f} ({2:.2%})".format(
            equity, planned, policy.risk_per_trade
        ),
    )
    report.add(
        "position cap set", policy.max_open_positions >= 1,
        "at most {0} open positions".format(policy.max_open_positions),
    )


def _check_strategy(report: PreflightReport, data_dir: Path, equity: float,
                    policy: RiskPolicy, config: StrategyConfig) -> None:
    decided = 0
    errors: List[str] = []
    for symbol in DEFAULT_UNIVERSE:
        path = price_file(data_dir, symbol)
        if not path.exists():
            continue
        try:
            candidate = generate_candidate(
                symbol, load_bars(path), [], equity, policy, CostModel(), config
            )
            decided += 1
            if candidate.action.value == "PAPER_LONG":
                if candidate.entry is None or candidate.stop is None:
                    errors.append("{0}: PAPER_LONG without a price plan".format(symbol))
                elif candidate.stop >= candidate.entry:
                    errors.append("{0}: stop is not below entry".format(symbol))
        except Exception as error:  # a live loop must not die on one symbol
            errors.append("{0}: {1}".format(symbol, type(error).__name__))
    report.add(
        "strategy evaluates cleanly", not errors and decided > 0,
        "; ".join(errors) if errors else "{0} symbols evaluated, no malformed plans".format(decided),
    )


def strategy_expectation() -> Dict[str, object]:
    """Measured history, stated at launch rather than buried in a document."""
    return {
        "trend_gate_2017_2023_held_out": "-3.46%",
        "mean_reversion_2017_2023_held_out": "+2.28%",
        "spy_buy_and_hold_same_period": "far higher",
        "profitable_years": "1 of 8 tested for the trend gate",
        "verdict": (
            "These checks confirm the system will run safely and stay inside its "
            "risk limits. They are not evidence that it makes money, and the "
            "measured history says it does not. Run it on paper."
        ),
    }


def run_preflight(
    data_dir: Path = Path("data"),
    equity: float = 1_000.0,
    policy: RiskPolicy = RiskPolicy(),
    config: StrategyConfig = StrategyConfig(),
    max_age_days: int = 5,
    check_broker: bool = True,
) -> PreflightReport:
    report = PreflightReport()
    if check_broker:
        _check_credentials(report)
    else:
        report.add("broker credentials", True, "skipped", blocking=False)
    _check_data(report, data_dir, max_age_days)
    _check_risk(report, equity, policy)
    _check_strategy(report, data_dir, equity, policy, config)
    return report
