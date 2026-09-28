"""Where a take-profit and a stop-loss can go, and what each placement costs.

PREPARED, NOT WIRED. The owner asked on 2026-09-27 for the bot to learn where
to set take-profits and stop-losses - "don't implement it yet just prepare it
and research it". Nothing in the trading loop imports this module. It changes
no order, stop, size or fingerprinted value. It holds the knowledge that
docs/2026-09-27-exit-placement-research.md rests on, in a form that can be run
and tested:

1. Barrier arithmetic for a price that wanders (Brownian motion with drift):
   the chance of reaching the target before the stop, how long that takes, and
   what it is worth before and after costs.
2. An assessment of any proposed target / stop pair against a stock's own
   volatility, in plain words.
3. The optimal-trading-rule search of Carr and Lopez de Prado (arXiv
   1408.1159), for a trade whose profit follows a mean-reverting
   (Ornstein-Uhlenbeck) path. Every target / stop pair on a declared grid is
   run over the same simulated paths, so the levels come from the trade's
   measured dynamics rather than from searching a backtest. Calibrating the
   process on real trades is a registered test (DRAFT H-0026 in that
   document), not something this module does.

The three facts behind every result here:

- With no edge, no target / stop pair has a positive expected value. The
  pair decides how often you win and how big the wins are, never whether you
  come out ahead (the optional-stopping theorem).
- With a steady edge, the expected gain equals edge x expected holding time
  (Wald's identity). Tight levels close the trade quickly, so they collect
  almost none of the edge - while the round-trip cost is paid in full on
  every trade.
- For a trade that is pulled back toward a fair level above its stop, the
  expected remaining gain is positive everywhere below that level. A stop
  there never adds expected profit. It is insurance against the fair level
  itself having moved. That is why this project's stop is wide (2.5 ATR):
  EXP-0022 found 2.5 a clean peak among 2.0-4.0 ATR, and H-0010 rejected
  every tighter stop it paired with a target.

And one trap: judged per trade on smoothness (Sharpe), the best target is
far tighter than the one that makes the most money. A tight target raises the
win rate and lowers the profit - what EXP-0050 measured on this strategy.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

SESSION_MINUTES = 390          # 09:30-16:00 ET
PROJECT_ROUND_TRIP_COST = 0.0012   # 0.12% all-in, the figure the daily report uses


def _check(target: float, stop: float, vol: float) -> None:
    if not (target > 0 and stop > 0):
        raise ValueError("target and stop are positive distances from entry")
    if not vol > 0:
        raise ValueError("volatility must be positive")


def target_first_probability(target: float, stop: float, drift: float = 0.0,
                             vol: float = 1.0) -> float:
    """Chance that a Brownian path reaches +target before -stop.

    `target` and `stop` are distances from entry as fractions (0.005 = 0.5%).
    `drift` is the expected return per unit of time and `vol` the standard
    deviation per square-root unit of time, in the same unit (per trading day
    here). Monitoring is continuous. With no drift the answer is
    stop / (target + stop), whatever the volatility.
    """
    _check(target, stop, vol)
    k = 2.0 * drift / vol ** 2
    if abs(k) * (target + stop) < 1e-9:
        return stop / (target + stop)
    # Two algebraically identical forms, each free of overflow on its own side.
    if k > 0:
        return math.expm1(-k * stop) / math.expm1(-k * (target + stop))
    return ((math.expm1(k * (target + stop)) - math.expm1(k * target))
            / math.expm1(k * (target + stop)))


def expected_holding_time(target: float, stop: float, drift: float = 0.0,
                          vol: float = 1.0) -> float:
    """Expected time until either level is reached, in the unit of drift and vol.

    With no drift it is target x stop / vol^2. Otherwise Wald's identity gives
    E[gain at exit] = drift x E[time], so E[time] = E[gain] / drift.
    """
    _check(target, stop, vol)
    if abs(2.0 * drift / vol ** 2) * (target + stop) < 1e-9:
        return target * stop / vol ** 2
    return expected_gross_gain(target, stop, drift, vol) / drift


def expected_gross_gain(target: float, stop: float, drift: float = 0.0,
                        vol: float = 1.0) -> float:
    """Expected gain per trade before costs, as a fraction of the position."""
    p = target_first_probability(target, stop, drift, vol)
    return target * p - stop * (1.0 - p)


def break_even_hit_rate(target: float, stop: float,
                        round_trip_cost: float = PROJECT_ROUND_TRIP_COST) -> float:
    """How often the target must come first for the pair to pay its costs.

    A win nets target - cost and a loss costs stop + cost.
    """
    if not (target > 0 and stop > 0):
        raise ValueError("target and stop are positive distances from entry")
    return (stop + round_trip_cost) / (target + stop)


@dataclass
class Assessment:
    """A proposed target / stop pair measured against one stock's volatility."""

    target: float
    stop: float
    daily_vol: float
    drift_per_day: float
    round_trip_cost: float
    chance_target_first: float      # with no edge at all
    target_first: float             # with the stated edge
    break_even: float
    expected_minutes: float
    gross_per_trade: float
    net_per_trade: float
    typical_15_minute_move: float
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        return {
            "target_pct": round(100 * self.target, 4),
            "stop_pct": round(100 * self.stop, 4),
            "daily_vol_pct": round(100 * self.daily_vol, 4),
            "edge_per_day_pct": round(100 * self.drift_per_day, 4),
            "round_trip_cost_pct": round(100 * self.round_trip_cost, 4),
            "chance_target_first_pct": round(100 * self.chance_target_first, 2),
            "target_first_pct": round(100 * self.target_first, 2),
            "break_even_pct": round(100 * self.break_even, 2),
            "expected_minutes_to_exit": round(self.expected_minutes, 1),
            "gross_per_trade_pct": round(100 * self.gross_per_trade, 4),
            "net_per_trade_pct": round(100 * self.net_per_trade, 4),
            "typical_15_minute_move_pct": round(100 * self.typical_15_minute_move, 4),
            "notes": list(self.notes),
        }


def assess(target: float, stop: float, daily_vol: float, drift_per_day: float = 0.0,
           round_trip_cost: float = PROJECT_ROUND_TRIP_COST) -> Assessment:
    """Judge a target / stop pair for a stock whose daily volatility is known.

    Approximation, stated in the notes it produces: the day's volatility is
    treated as spread evenly over the 390-minute session and prices are
    watched continuously. Real volatility is highest near the open and the
    close, and overnight gaps jump straight past both levels.
    """
    _check(target, stop, daily_vol)
    chance = target_first_probability(target, stop, 0.0, daily_vol)
    p = target_first_probability(target, stop, drift_per_day, daily_vol)
    days = expected_holding_time(target, stop, drift_per_day, daily_vol)
    gross = expected_gross_gain(target, stop, drift_per_day, daily_vol)
    net = gross - round_trip_cost
    even = break_even_hit_rate(target, stop, round_trip_cost)
    move_15 = daily_vol * math.sqrt(15.0 / SESSION_MINUTES)
    minutes = days * SESSION_MINUTES
    held = ("{0:.0f} minutes of trading".format(minutes) if minutes < SESSION_MINUTES
            else "{0:.1f} trading days".format(days))
    notes = ["By chance alone - no edge - the price reaches +{0:.2%} before "
             "-{1:.2%} {2:.0%} of the time.".format(target, stop, chance)]
    if drift_per_day != 0:
        notes.append("With the assumed edge of {0:+.3%} a day that becomes "
                     "{1:.0%}.".format(drift_per_day, p))
    notes += [
        "To pay the {0:.2%} round-trip cost it must get there first {1:.0%} of "
        "the time.".format(round_trip_cost, even),
        "Expected time until one of the two levels is hit: about {0}.".format(held),
        "A typical 15-minute move for this stock is {0:.2%}; the stop is {1:.1f} "
        "times that.".format(move_15, stop / move_15),
    ]
    if stop < 2 * move_15:
        notes.append("The stop sits inside ordinary 15-minute noise, so noise alone "
                     "will end most trades.")
    if drift_per_day == 0:
        notes.append("With no edge the expected result is minus the cost: "
                     "{0:+.3%} a trade.".format(net))
    else:
        note = ("With that edge the expected result is {0:+.4%} a trade after costs. "
                "The edge contributes {1:+.4%}: its daily rate times the {2} the "
                "trade is expected to last".format(net, gross, held))
        if minutes < SESSION_MINUTES:
            note += " - little, because the trade lasts only minutes"
        notes.append(note + ".")
    notes.append("Approximation: volatility is treated as even through the day and "
                 "gaps are ignored; real opens are more volatile and gaps jump past "
                 "both levels.")
    return Assessment(target=target, stop=stop, daily_vol=daily_vol,
                      drift_per_day=drift_per_day, round_trip_cost=round_trip_cost,
                      chance_target_first=chance, target_first=p, break_even=even,
                      expected_minutes=minutes, gross_per_trade=gross,
                      net_per_trade=net, typical_15_minute_move=move_15, notes=notes)


# ---------------------------------------------------------------------------
# The optimal trading rule for a mean-reverting trade (Carr & Lopez de Prado)
# ---------------------------------------------------------------------------

@dataclass
class RuleResult:
    profit_take: float          # math.inf = no target
    stop_loss: float            # math.inf = no stop
    mean: float
    std: float
    sharpe: float
    mean_steps: float
    target_share: float
    stop_share: float


def simulate_ou_rules(profit_takes: Sequence[float], stop_losses: Sequence[float],
                      half_life: float, forecast: float, sigma: float,
                      max_steps: int, paths: int = 20000, seed: int = 0,
                      round_trip_cost: float = 0.0) -> List[RuleResult]:
    """Every (profit_take, stop_loss) pair on the grid, over the same paths.

    The trade's profit P starts at 0 and follows the discrete
    Ornstein-Uhlenbeck process of Carr & Lopez de Prado:

        P_t = (1 - phi) * forecast + phi * P_(t-1) + sigma * e_t,
        phi = 2 ** (-1 / half_life)

    so it is pulled toward `forecast` and covers half the remaining distance
    every `half_life` steps (half_life = math.inf is a pure random walk). A
    rule exits at the first step where P_t >= profit_take or
    P_t <= -stop_loss, and otherwise at `max_steps`, booking P at that step.
    Levels are in the units of P; use math.inf for "no target" or "no stop".
    Every rule sees the same shocks, so differences between rules are not
    sampling noise.
    """
    phi = 1.0 if math.isinf(half_life) else 2.0 ** (-1.0 / half_life)
    profit = ar1_profit_paths((1.0 - phi) * forecast, phi, sigma, max_steps,
                              paths, seed)
    return evaluate_rules(profit, profit_takes, stop_losses, round_trip_cost)


def ar1_profit_paths(intercept: float, phi: float, sigma: float, max_steps: int,
                     paths: int, seed: int):
    """Simulated profit paths: P_0 = 0, P_t = intercept + phi x P_(t-1) + sigma x e_t.

    This is the discrete Ornstein-Uhlenbeck process above written as the
    AR(1) a pooled regression estimates directly: phi < 1 pulls toward
    intercept / (1 - phi); phi >= 1 is a walk with drift `intercept`, and is
    simulated as it stands rather than refused. Returns a (paths, max_steps)
    array; column t - 1 is P_t.
    """
    import numpy as np

    if max_steps < 1 or paths < 2:
        raise ValueError("need at least one step and two paths")
    rng = np.random.default_rng(seed)
    shocks = rng.standard_normal((paths, max_steps))
    profit = np.empty((paths, max_steps))
    level = np.zeros(paths)
    for step in range(max_steps):
        level = intercept + phi * level + sigma * shocks[:, step]
        profit[:, step] = level
    return profit


def evaluate_rules(profit, profit_takes: Sequence[float], stop_losses: Sequence[float],
                   round_trip_cost: float = 0.0) -> List[RuleResult]:
    """Every (profit_take, stop_loss) pair over one (paths, steps) array of profits.

    A rule exits at the first step with P >= profit_take or P <= -stop_loss,
    otherwise at the last step, and books P at that step minus the cost.
    """
    import numpy as np

    paths, max_steps = profit.shape
    rows = np.arange(paths)
    results: List[RuleResult] = []
    for take in profit_takes:
        for stop in stop_losses:
            hit_take = profit >= take
            hit_stop = profit <= -stop
            hit = hit_take | hit_stop
            any_hit = hit.any(axis=1)
            first = np.where(any_hit, hit.argmax(axis=1), max_steps - 1)
            booked = profit[rows, first] - round_trip_cost
            took = any_hit & hit_take[rows, first]
            stopped = any_hit & hit_stop[rows, first]
            std = float(booked.std(ddof=1))
            mean = float(booked.mean())
            results.append(RuleResult(
                profit_take=float(take), stop_loss=float(stop), mean=mean, std=std,
                sharpe=(mean / std) if std > 0 else 0.0,
                mean_steps=float(first.mean() + 1), target_share=float(took.mean()),
                stop_share=float(stopped.mean())))
    return results


def optimal_rule(results: Sequence[RuleResult], objective: str = "mean") -> RuleResult:
    """The grid member that maximises the declared objective ('mean' or 'sharpe').

    The objective must be fixed before any result is looked at. Choosing it
    afterwards is the very overfitting this method exists to avoid.
    """
    if objective not in ("mean", "sharpe"):
        raise ValueError("objective is 'mean' or 'sharpe'")
    if not results:
        raise ValueError("no results to choose from")
    return max(results, key=lambda r: (getattr(r, objective), -r.mean_steps))


def expected_ou_profit(forecast: float, half_life: float, steps: int) -> float:
    """E[P_steps] with no target and no stop: forecast x (1 - phi^steps)."""
    phi = 1.0 if math.isinf(half_life) else 2.0 ** (-1.0 / half_life)
    return forecast * (1.0 - phi ** steps)


def continuation_value(profit_now: float, forecast: float, half_life: float,
                       steps_left: int) -> float:
    """Expected further profit from holding `steps_left` more steps.

    E[P_T | P_t] - P_t = (forecast - P_t) x (1 - phi^(T - t)). It is positive
    whenever the trade sits below its fair level, so selling there gives up
    expected gain. For a mean-reverting trade judged on expected profit, a
    stop placed below the fair level therefore never helps.
    """
    phi = 1.0 if math.isinf(half_life) else 2.0 ** (-1.0 / half_life)
    return (forecast - profit_now) * (1.0 - phi ** max(0, steps_left))
