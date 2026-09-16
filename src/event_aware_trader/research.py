"""The research firewall: what the bot runs, what data is spent, what was tried.

WHY THIS EXISTS. Between 2026-09-08 and 2026-09-13 roughly forty
configurations were evaluated on the decade (2016-2026) and roughly twenty
decisions were taken on the thirty-year window (1996-2026) - the window this
project called "the test that decides". Both halves of both windows were seen
for every one of them. There was no registry of what had been tried, no count
of related attempts, and no correction for the fact that the best of forty
tries is expected to look good by luck.

By the project's own rule - once a holdout is used to make a decision it is
contaminated and the boundary moves forward - every historical dataset here is
spent for the CURRENT production candidate. The only clean data for it is what
the account has produced since it went live, and every new idea from here on
has to be judged by a distribution across periods, recorded, and counted.

This module is that discipline, in code:

  PRODUCTION_CANDIDATE   the exact simulator configuration that mirrors what
                         the bot actually runs. Every comparison starts here.
  DATASETS / FORWARD     the contamination ledger, and the date after which
                         data is genuinely unseen by the current candidate.
  walk_forward_years     the per-period out-of-sample distribution - a
                         median, a worst year, a share of positive years - not
                         one number.
  record_experiment      the append-only registry with the fields the research
                         standard requires, including how many related
                         experiments preceded this one.
  deflated_sharpe        the multiple-comparison correction: the Sharpe a
                         lucky no-edge trial would reach after N tries, which
                         the reported Sharpe must clear.

Nothing here is a strategy. It only decides how strategies are judged.
"""

import csv
import json
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean, median, variance
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .portfolio import PortfolioReport, run_portfolio
from .risk import CostModel, RiskPolicy
from .stats import deflated_sharpe_ratio

# The append-only experiment registry (see the section below).
REGISTRY = Path("docs/experiments.jsonl")


# ---------------------------------------------------------------------------
# The production candidate
# ---------------------------------------------------------------------------

# Every live constraint the simulator can mirror, switched ON. A comparison run
# without one of these is a comparison against something the bot does not do.
#
#   entry_fill signal_close      entries in the closing window (live: 15:45)
#   realistic_stop_fills         a gapped stop fills at the open, not the stop
#   max_entries_per_day 3        max_orders_per_run x the one closing cycle
#   mark_to_market_guard         the live daily guard halts on unrealised loss
#   whole shares (policy)        Alpaca refuses a GTC stop on a fraction
#
# One live behaviour the simulator cannot take as a parameter: idle cash is
# parked in SGOV. That is applied afterwards by `with_parked_cash`, and the
# candidate is not fully mirrored until it has been.
PRODUCTION_CANDIDATE: Dict[str, object] = {
    "entry_rule": "mean_reversion",
    "entry_fill": "signal_close",
    "realistic_stop_fills": True,
    "max_entries_per_day": 3,
    "mark_to_market_guard": True,
    # The exit-timing haircut. See portfolio.py for why this is an
    # uncertainty adjustment and not an observed price: the simulator prices
    # rule exits at the close, live sells at the trigger, and on daily bars
    # the trigger price does not exist. 0.652% is the WORST of three measured
    # cases (155 real exits, 5-minute bars) and is used because the live
    # trigger-time distribution is UNVERIFIED and Phase 1's risk is
    # overstating. It lowers reported return on purpose.
    "rule_exit_timing_haircut": 0.00652,
}


def production_policy() -> RiskPolicy:
    return replace(RiskPolicy(), allow_fractional_shares=False)


# What a contaminated dataset may still be used FOR. The asymmetry is the
# point: data this candidate was tuned on can still REJECT an idea - a change
# that loses money on its own training data will not win elsewhere - but it
# can never ACCEPT one. Anything else is re-reading a spent holdout.
PURPOSES = {
    "baseline_remeasurement": "re-establishing the frozen baseline after a correctness fix",
    "rejection_test": "can only reject; a positive result here means nothing",
    "diagnostic": "understanding behaviour, no accept/reject attached",
    "forward_gate_evaluation": "the forward record, once it is long enough",
}

# A tripwire, not a proof. Anything with this many symbols over this long a
# span is one of the research sets rather than a unit-test fixture, and must
# declare itself. Someone determined to bypass the gate still can - by
# passing dataset= a lie - but they can no longer do it by forgetting.
RESEARCH_SCALE_SYMBOLS = 50
RESEARCH_SCALE_YEARS = 3.0


def looks_like_research_data(series) -> bool:
    if len(series) < RESEARCH_SCALE_SYMBOLS:
        return False
    spans = []
    for bars in series.values():
        if len(bars) >= 2:
            spans.append((bars[-1].timestamp - bars[0].timestamp).days / 365.25)
    return bool(spans) and max(spans) >= RESEARCH_SCALE_YEARS


class ContaminatedDataError(RuntimeError):
    """Raised when a spent dataset is scored without declaring why."""


def check_dataset_gate(series, dataset: Optional[str], purpose: Optional[str],
                       registry: Path = REGISTRY) -> None:
    """Refuse to score a spent dataset without saying why, and record it.

    Separated from `production_report` so it can be tested in milliseconds.
    Folded into the caller, every gate assertion had to run a full
    simulation over a research-scale fixture to reach the check - 126
    seconds for fourteen tests, which is the kind of cost that gets a test
    file quietly excluded from the suite later.
    """
    if dataset is None:
        if looks_like_research_data(series):
            raise ContaminatedDataError(
                "This series is research-scale ({0} symbols, multi-year) but "
                "no dataset= was declared. Every historical set is "
                "contaminated for the current candidate; name it and give a "
                "purpose from {1}.".format(len(series), sorted(PURPOSES)))
        return

    if dataset not in DATASETS:
        raise ContaminatedDataError(
            "unknown dataset {0!r}; add it to DATASETS".format(dataset))

    spent = DATASETS[dataset]["status"] != "clean"
    if not spent and dataset != "forward":
        return

    if purpose not in PURPOSES:
        raise ContaminatedDataError(
            "dataset {0!r} is {1}; scoring it requires purpose= one of {2}"
            .format(dataset, DATASETS[dataset]["status"], sorted(PURPOSES)))
    if dataset == "forward" and purpose != "forward_gate_evaluation":
        raise ContaminatedDataError(
            "the forward record may only be scored with "
            "purpose='forward_gate_evaluation'")
    _record_gate_use(dataset, purpose, len(series), registry)


def production_report(series, starting_cash: float = 100_000.0,
                      conviction=None, dataset: Optional[str] = None,
                      purpose: Optional[str] = None,
                      registry: Path = REGISTRY, **overrides) -> PortfolioReport:
    """Run the production candidate. `overrides` is how an experiment differs.

    An experiment that changes the candidate passes only the keys it changes,
    so the diff between candidate and experiment is exactly the override dict
    - which is what goes in the registry.

    THE GATE. Every historical dataset here is contaminated for this
    candidate - 37 recorded touches on the decade, 30 on the thirty-year
    window - and until now `DATASETS` merely SAID so while nothing stopped
    another run. Scoring a contaminated set now requires naming a `purpose`
    from PURPOSES, and the run is recorded.

    `dataset=None` with a small series is the unit-test path and is
    ungated. A series at research scale without a declared dataset raises:
    that is the case where someone forgot, which is the case worth catching.
    """
    check_dataset_gate(series, dataset, purpose, registry)

    kwargs = dict(PRODUCTION_CANDIDATE)
    kwargs.update(overrides)
    return run_portfolio(series, starting_cash=starting_cash,
                         policy=production_policy(), costs=CostModel(),
                         conviction=conviction, **kwargs)


def _record_gate_use(dataset: str, purpose: str, symbols: int,
                     registry: Path) -> None:
    """Append one line recording that a spent dataset was read, and why."""
    registry.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "at": datetime.now(timezone.utc).isoformat(),
        "kind": "dataset_use",
        "dataset": dataset,
        "purpose": purpose,
        "note": PURPOSES[purpose],
        "symbols": symbols,
    }
    with registry.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + chr(10))


# ---------------------------------------------------------------------------
# Idle cash, as live holds it
# ---------------------------------------------------------------------------

# 3-month Treasury bill yield, daily, 1970 on. What SGOV pays, to a few bps.
TBILL = Path("data/tbill.csv")

# Mirrors autotrade: cash_parking_floor, reserved_fraction, and the 2bps
# charged each way that every parking measurement has used.
PARKING_FLOOR = 2_000.0
RESERVED_FRACTION = 0.05
PARKING_COST = 0.0002


def load_tbill_rates(path: Path = TBILL) -> Dict[date, float]:
    """Yield by date as a fraction (5.00 in the file -> 0.05)."""
    rates: Dict[date, float] = {}
    with Path(path).open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rates[date.fromisoformat(row["date"])] = float(row["yield"]) / 100.0
    return rates


def _rate_on(rates: Dict[date, float], day: date, last: float) -> float:
    for back in range(8):
        probe = date.fromordinal(day.toordinal() - back)
        if probe in rates:
            return rates[probe]
    return last


def with_parked_cash(report: PortfolioReport, rates: Dict[date, float],
                     floor: float = PARKING_FLOOR,
                     reserved_fraction: float = RESERVED_FRACTION,
                     cost: float = PARKING_COST) -> PortfolioReport:
    """The candidate's curve with idle cash earning what live earns.

    run_portfolio holds idle cash at zero. Live parks everything above
    `floor`, less `reserved_fraction` of equity held back for the crypto
    sleeve, in SGOV - and pays `cost` each time the parked balance moves.
    This is an overlay on cash_curve rather than a simulator parameter
    because the simulator's money path should not change for a component
    that cannot lose money. The strategy's own Sharpe is the un-parked curve
    (its excess return over cash); the account's P&L is this one.
    """
    if len(report.cash_curve) != len(report.equity_curve):
        raise ValueError("cash_curve and equity_curve differ in length")
    sleeve = 0.0
    current = 0.0
    previous_stamp: Optional[datetime] = None
    previous_parked = 0.0
    lifted: List[Tuple[datetime, float]] = []
    for (stamp, equity), (_, cash) in zip(report.equity_curve, report.cash_curve):
        current = _rate_on(rates, stamp.date(), current)
        parked = max(0.0, cash - floor - reserved_fraction * equity)
        if previous_stamp is not None:
            years = max(0.0, (stamp - previous_stamp).days / 365.25)
            growth = (1.0 + current) ** years - 1.0
            sleeve += (sleeve + previous_parked) * growth
            moved = abs(parked - previous_parked)
            if moved > 1.0:
                sleeve -= moved * cost
        lifted.append((stamp, equity + sleeve))
        previous_stamp, previous_parked = stamp, parked
    return replace(report, equity_curve=lifted, equity=report.equity + sleeve)


# ---------------------------------------------------------------------------
# The contamination ledger
# ---------------------------------------------------------------------------

# The first session the current candidate traded live. Everything the account
# records from here on is the only data no experiment has seen.
FORWARD_START = date(2026, 9, 11)

DATASETS: Dict[str, Dict[str, object]] = {
    "decade": {
        "window": "2016-2026, 230 names",
        "status": "contaminated",
        "note": "development set; ~40 configurations evaluated 09-08..09-13",
    },
    "thirty_year": {
        "window": "1996-2026, 229 names",
        "status": "contaminated",
        "note": ("was the deciding holdout; ~20 accept/reject decisions taken "
                 "on it. No longer a holdout for the current candidate."),
    },
    "etf_subset": {
        "window": "46 broad ETFs, both windows",
        "status": "contaminated as a control",
        "note": ("survivorship control, used twice. Not tuned on, but seen."),
    },
    "crypto": {
        "window": "BTC 2014-, ETH 2017-, SOL 2020-, meme pairs 2021-",
        "status": "contaminated",
        "note": "sleeve allocation, window, trail and meme tests",
    },
    "forward": {
        "window": "paper account from {0}".format(FORWARD_START.isoformat()),
        "status": "clean",
        "note": "the only unseen data for the current candidate",
    },
}


# ---------------------------------------------------------------------------
# Per-period distribution
# ---------------------------------------------------------------------------

@dataclass
class PeriodResult:
    label: str
    days: int
    total_return: float
    max_drawdown: float
    trades: int


def walk_forward_years(report: PortfolioReport,
                       refit: Optional[Callable[[date], None]] = None
                       ) -> List[PeriodResult]:
    """One result per calendar year, from a single run of a FIXED rule.

    For a rule with fixed parameters nothing is re-estimated per fold, so a
    single pass over the data and a per-year slice of its equity curve IS the
    per-period out-of-sample record - each year's trades used only bars that
    had printed. What it is NOT is out-of-sample for the parameters, which
    were chosen on this same data; that is what the ledger above is for.

    `refit` is the hook for a component that IS re-estimated: a callable that
    re-fits on data before the fold's first date. It is deliberately not
    implemented here - a real refit changes which trades happen and needs a
    fresh run per fold. Naming the hook keeps the two cases from being
    confused when someone adds a tuned model.
    """
    if refit is not None:
        raise NotImplementedError(
            "per-fold refitting needs one run per fold; slicing a single run "
            "would leak later folds' fits into earlier ones")
    curve = list(report.equity_curve)
    if not curve:
        return []
    by_year: Dict[int, List[float]] = {}
    for stamp, value in curve:
        by_year.setdefault(stamp.year, []).append(value)
    closed: Dict[int, int] = {}
    for trade in report.trades:
        closed[trade.exit_time.year] = closed.get(trade.exit_time.year, 0) + 1
    out = []
    previous_close: Optional[float] = None
    for year in sorted(by_year):
        values = by_year[year]
        start = previous_close if previous_close is not None else values[0]
        peak, worst = start, 0.0
        for value in values:
            peak = max(peak, value)
            if peak > 0:
                worst = min(worst, value / peak - 1.0)
        out.append(PeriodResult(
            label=str(year), days=len(values),
            total_return=(values[-1] / start - 1.0) if start > 0 else 0.0,
            max_drawdown=worst, trades=closed.get(year, 0)))
        previous_close = values[-1]
    return out


def summarize_periods(periods: Sequence[PeriodResult]) -> Dict[str, object]:
    """The distribution, not the average."""
    full = [p for p in periods if p.days >= 200]        # drop partial years
    if not full:
        return {"periods": 0}
    returns = sorted(p.total_return for p in full)
    drawdowns = [p.max_drawdown for p in full]
    q = lambda f: returns[min(len(returns) - 1, int(len(returns) * f))]
    return {
        "periods": len(full),
        "median_return": median(returns),
        "mean_return": mean(returns),
        "worst_return": returns[0],
        "best_return": returns[-1],
        "p25_return": q(0.25),
        "p75_return": q(0.75),
        "share_positive": sum(1 for r in returns if r > 0) / len(returns),
        "worst_drawdown": min(drawdowns),
        "median_drawdown": median(drawdowns),
        "worst_period": min(full, key=lambda p: p.total_return).label,
    }


def period_table(periods: Sequence[PeriodResult]) -> str:
    lines = ["{0:<8}{1:>10}{2:>10}{3:>8}".format("year", "return", "maxDD",
                                                 "trades"), "-" * 36]
    for p in periods:
        flag = "" if p.days >= 200 else "  (partial)"
        lines.append("{0:<8}{1:>10.1%}{2:>10.1%}{3:>8}{4}".format(
            p.label, p.total_return, p.max_drawdown, p.trades, flag))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Multiple comparisons
# ---------------------------------------------------------------------------

def daily_returns(report: PortfolioReport) -> List[float]:
    curve = list(report.equity_curve)
    return [curve[i][1] / curve[i - 1][1] - 1.0 for i in range(1, len(curve))
            if curve[i - 1][1] > 0]


EQUITY_WINDOWS = ("decade", "thirty_year", "etf_subset")


@dataclass
class Deflation:
    probability: Optional[float]   # PSR against the expected best of N no-edge trials
    trials: int                    # configurations evaluated on these windows
    variance: float                # spread of Sharpe across those trials, annualised
    variance_source: str           # "observed" from the registry, "unit default", "given"

    def __str__(self) -> str:
        p = "-" if self.probability is None else "{0:.3f}".format(self.probability)
        return "DSR {0} after {1} configurations (trial Sharpe sd {2:.3f}, {3})".format(
            p, self.trials, self.variance ** 0.5, self.variance_source)


def deflated_sharpe(report: PortfolioReport, trials: Optional[int] = None,
                    variance: Optional[float] = None,
                    datasets: Sequence[str] = EQUITY_WINDOWS,
                    path: Path = REGISTRY) -> Deflation:
    """Probability the candidate's Sharpe beats what the search would reach by luck.

    Below 0.95 the reported Sharpe has not paid for the search that produced
    it. Both inputs default to the registry: `trials` is every configuration
    evaluated on `datasets`, and `variance` is the spread of the Sharpes those
    configurations recorded. When no Sharpes were recorded the spread falls
    back to 1.0 - conservative to the point of failing anything - which is the
    reason every experiment should record its trial Sharpes.
    """
    n = search_size(datasets, path) if trials is None else trials
    source = "given"
    if variance is None:
        variance = trial_sharpe_variance(datasets, path)
        source = "observed"
        if variance is None:
            variance, source = 1.0, "unit default"
    probability = deflated_sharpe_ratio(daily_returns(report), trials=max(1, n),
                                        trial_sharpe_variance=variance)
    return Deflation(probability, max(1, n), variance, source)


def search_size(datasets: Sequence[str] = EQUITY_WINDOWS,
                path: Path = REGISTRY) -> int:
    """Configurations evaluated on any of `datasets` - the N the deflation pays for."""
    wanted = set(datasets)
    return sum(int(r.get("configurations", 1)) for r in load_registry(path)
               if wanted & set(r.get("contaminated", [])))


def trial_sharpe_variance(datasets: Sequence[str] = EQUITY_WINDOWS,
                          path: Path = REGISTRY) -> Optional[float]:
    """Sample variance of every recorded configuration Sharpe on `datasets`."""
    wanted = set(datasets)
    values = [float(v) for r in load_registry(path)
              if wanted & set(r.get("contaminated", []))
              for v in r.get("trial_sharpes", [])]
    return variance(values) if len(values) >= 3 else None


# ---------------------------------------------------------------------------
# The experiment registry
# ---------------------------------------------------------------------------

DECISIONS = ("accepted", "rejected", "inconclusive", "measured", "reverted")
EVIDENCE = ("strong", "weak", "none", "contradictory", "artifact", "inconclusive")


def load_registry(path: Path = REGISTRY) -> List[Dict[str, object]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def related_before(family: str, path: Path = REGISTRY) -> int:
    return sum(1 for r in load_registry(path) if r.get("family") == family)


def record_experiment(family: str, hypothesis: str, config: Dict[str, object],
                      data_periods: Sequence[str], result: str, decision: str,
                      reason: str, evidence: str = "inconclusive",
                      features: Optional[Sequence[str]] = None,
                      parameters: Optional[Dict[str, object]] = None,
                      validation_result: Optional[str] = None,
                      holdout_result: Optional[str] = None,
                      contaminated: Optional[Sequence[str]] = None,
                      configurations: int = 1,
                      trial_sharpes: Optional[Sequence[float]] = None,
                      when: Optional[str] = None,
                      path: Path = REGISTRY) -> Dict[str, object]:
    """Append one experiment. Failed ones too - especially failed ones.

    `related_before` is computed here, from the registry, so nobody has to
    remember how many times this family has been tried. `configurations` is
    how many distinct settings the row stands for (a sweep of five stops is
    one experiment, five configurations) and `trial_sharpes` their Sharpes:
    together they are what `deflated_sharpe` pays for.
    """
    if configurations < 1:
        raise ValueError("an experiment evaluates at least one configuration")
    sharpes = [float(v) for v in (trial_sharpes or [])]
    if len(sharpes) > configurations:
        raise ValueError("more trial Sharpes than configurations")
    if decision not in DECISIONS:
        raise ValueError("decision must be one of {0}".format(DECISIONS))
    if evidence not in EVIDENCE:
        raise ValueError("evidence must be one of {0}".format(EVIDENCE))
    touched = list(contaminated) if contaminated is not None else list(data_periods)
    unknown = sorted(set(d for d in list(data_periods) + touched if d not in DATASETS))
    if unknown:
        raise ValueError("unknown dataset(s) {0}; add them to DATASETS".format(unknown))
    rows = load_registry(path)
    row = {
        "id": "EXP-{0:04d}".format(len(rows) + 1),
        "when": when or datetime.now(timezone.utc).date().isoformat(),
        "family": family,
        "related_before": sum(1 for r in rows if r.get("family") == family),
        "hypothesis": hypothesis,
        "config": config,
        "features": list(features or []),
        "parameters": parameters or {},
        "data_periods": list(data_periods),
        "result": result,
        "validation_result": validation_result,
        "holdout_result": holdout_result,
        "decision": decision,
        "evidence": evidence,
        "reason": reason,
        "contaminated": touched,
        "configurations": int(configurations),
        "trial_sharpes": sharpes,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def contamination_summary(path: Path = REGISTRY) -> Dict[str, int]:
    """How many recorded experiments touched each dataset."""
    counts: Dict[str, int] = {name: 0 for name in DATASETS}
    for row in load_registry(path):
        for name in row.get("contaminated", []):
            counts[name] = counts.get(name, 0) + 1
    return counts
