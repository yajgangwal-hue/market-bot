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

import json
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Callable, Dict, List, Optional, Sequence

from .portfolio import PortfolioReport, run_portfolio
from .risk import CostModel, RiskPolicy
from .stats import deflated_sharpe_ratio

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
PRODUCTION_CANDIDATE: Dict[str, object] = {
    "entry_rule": "mean_reversion",
    "entry_fill": "signal_close",
    "realistic_stop_fills": True,
    "max_entries_per_day": 3,
    "mark_to_market_guard": True,
}


def production_policy() -> RiskPolicy:
    return replace(RiskPolicy(), allow_fractional_shares=False)


def production_report(series, starting_cash: float = 100_000.0,
                      conviction=None, **overrides) -> PortfolioReport:
    """Run the production candidate. `overrides` is how an experiment differs.

    An experiment that changes the candidate passes only the keys it changes,
    so the diff between candidate and experiment is exactly the override dict
    - which is what goes in the registry.
    """
    kwargs = dict(PRODUCTION_CANDIDATE)
    kwargs.update(overrides)
    return run_portfolio(series, starting_cash=starting_cash,
                         policy=production_policy(), costs=CostModel(),
                         conviction=conviction, **kwargs)


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


def deflated_sharpe(report: PortfolioReport, trials: int) -> Optional[float]:
    """Probability the candidate's Sharpe beats what `trials` lucky tries reach.

    Below 0.95 the reported Sharpe has not paid for the search that produced
    it. `trials` must be honest: the number of related configurations that
    were evaluated on this data, which the registry counts.
    """
    return deflated_sharpe_ratio(daily_returns(report), trials=max(1, trials))


# ---------------------------------------------------------------------------
# The experiment registry
# ---------------------------------------------------------------------------

REGISTRY = Path("docs/experiments.jsonl")

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
                      when: Optional[str] = None,
                      path: Path = REGISTRY) -> Dict[str, object]:
    """Append one experiment. Failed ones too - especially failed ones.

    `related_before` is computed here, from the registry, so nobody has to
    remember how many times this family has been tried. It is what
    `deflated_sharpe` needs and what the promotion gate reads.
    """
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
