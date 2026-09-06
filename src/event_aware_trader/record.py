"""Read the accumulated paper record and say whether it proves anything.

The point of running for months is to answer one question: does this work?
That question is statistical, and the honest answer for a long time will be
"there is not enough evidence yet" - which is exactly the answer a person
watching a small positive number is least likely to give themselves.

At roughly three trades per six months, a year of running produces about six
trades. Six trades cannot distinguish a real edge from luck, and this module
says so numerically rather than leaving it to judgement: it reports the
confidence interval around the win rate, a bootstrap interval around mean
return, a sign-flip p-value against the null that the mean is zero, and how
many more trades would be needed before the question is even answerable.

`stats.py` already contained all of this machinery and nothing in the trading
path used it.
"""

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .stats import (bootstrap_ci, deflated_sharpe_ratio, normal_cdf,
                    sharpe_ratio, sign_flip_pvalue, wilson_interval)

# Below this, no statistical statement is worth making.
MINIMUM_INFORMATIVE_TRADES = 30
# A rule of thumb for detecting a modest edge at conventional power.
TRADES_FOR_A_MODEST_EDGE = 200
# Below this in EACH group, a winners-versus-losers comparison is one trade
# moving the mean, not a pattern.
MINIMUM_PER_GROUP = 5
# A pure ratio has no sense of scale: winners held an hour against losers held
# two is a 2x ratio and means nothing. The rule's holding cap is counted in
# days, so a gap worth naming is measured in days too.
MINIMUM_DISPOSITION_GAP_DAYS = 1.0
# Published return predictors lose about half their edge once they are known:
# McLean and Pontiff measured portfolio returns 58% lower post-publication,
# roughly 26 points of that being data-mining bias that was never real. A
# private backtest has not been refereed, so it carries at least that much.
# Halving the measured edge before deciding is the conservative reading.
DECAY_HAIRCUT = 0.5
SESSIONS_PER_YEAR = 252.0
# A trade rate estimated from a handful of sessions is not an estimate. Three
# trades over three observed sessions annualises to 252 a year and says the
# record will be conclusive in six weeks, which is nonsense produced by a
# denominator nobody checked.
MINIMUM_SESSIONS_FOR_RATE = 20


def _parse_when(value: Any) -> Optional[datetime]:
    """Parse the several timestamp shapes this log has accumulated.

    The audit log carries "...Z" from broker backfill, "...+00:00" from the
    live loop, and bare "2026-01-01" from older rows and tests. Everything is
    normalised to naive UTC so two of them can be subtracted without raising
    "can't subtract offset-naive and offset-aware datetimes" - which would
    turn a holding-period statistic into a crash on one malformed row.
    """
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


@dataclass
class TradeRecord:
    symbol: str
    opened: str
    closed: str
    net_pnl: float
    return_fraction: float
    # Defaulted because older logs and every existing caller build this
    # positionally with five fields.
    fees: float = 0.0

    @property
    def won(self) -> bool:
        return self.net_pnl > 0

    @property
    def gross_pnl(self) -> float:
        """P&L before costs.

        `realized_pnl` in the audit log is already NET: for the XOP exit of
        2026-09-02, proceeds 19983.60 - basis 19992.96 = -9.36 gross, and the
        row records -9.86 after a 0.4959 fee. Adding the fee back recovers the
        gross figure, which is the only way to see an edge that exists and is
        being eaten.
        """
        return self.net_pnl + self.fees

    @property
    def holding_days(self) -> Optional[float]:
        opened, closed = _parse_when(self.opened), _parse_when(self.closed)
        if opened is None or closed is None or closed < opened:
            return None
        return (closed - opened).total_seconds() / 86400.0


@dataclass
class RecordReport:
    trades: List[TradeRecord] = field(default_factory=list)
    starting_equity: float = 1_000.0
    ending_equity: float = 1_000.0
    benchmark_return: Optional[float] = None
    sessions_observed: int = 0
    # Whether `starting_equity` is the account's real capital base or the
    # module's 1,000.0 placeholder. The buy-and-hold comparison divides the
    # record's P&L by this figure, so a placeholder does not make the
    # comparison approximate - it makes it wrong by whatever factor separates
    # the placeholder from the truth, and wrong in the flattering direction.
    equity_base_is_real: bool = False
    # How many strategy variants were tried before this one was chosen. Test
    # twenty and the best looks excellent by chance; the deflated Sharpe
    # raises the bar to what the luckiest of that many no-edge trials reaches.
    # Left at 1 it corrects nothing, which understates the bar rather than
    # inventing a number this module cannot know.
    trials_tested: int = 1

    @property
    def wins(self) -> int:
        return sum(1 for t in self.trades if t.won)

    @property
    def returns(self) -> List[float]:
        return [t.return_fraction for t in self.trades]

    def friction(self) -> Optional[Dict[str, object]]:
        """Gross edge against what it cost to collect it.

        This is the largest single term in the day-trading literature and the
        one a net-only record hides completely. A strategy whose gross edge is
        real and whose fees are larger looks identical, in net P&L, to one
        with no edge at all - and the two call for opposite responses: trade
        less versus stop trading.

        Measured in this project: the intraday rule showed +$6.19 of gross
        edge per trade against -$14.99 of round-trip friction.
        """
        if not self.trades:
            return None
        gross = sum(t.gross_pnl for t in self.trades)
        fees = sum(t.fees for t in self.trades)
        priced = sum(1 for t in self.trades if t.fees)
        out: Dict[str, object] = {
            "gross_pnl": round(gross, 2),
            "fees_paid": round(fees, 2),
            "net_pnl": round(gross - fees, 2),
            "fees_per_trade": round(fees / len(self.trades), 4),
            "trades_with_fee_data": priced,
        }
        if priced < len(self.trades):
            # Only broker-backfilled exits carry a fee. Saying so beats
            # reporting a confidently understated cost.
            out["warning"] = (
                "{0} of {1} trades carry no fee data, so the cost above is a "
                "floor, not the total.".format(len(self.trades) - priced, len(self.trades))
            )
        if gross > 0:
            share = fees / gross
            out["fees_as_share_of_gross_edge"] = round(share, 4)
            if share >= 1.0:
                out["reading"] = (
                    "Costs exceed the gross edge. The rule finds something real "
                    "and gives back more than it finds; trading it less often is "
                    "the only version of this that can work."
                )
            elif share >= 0.5:
                out["reading"] = (
                    "Costs consume more than half the gross edge. Frequency, not "
                    "signal quality, is the binding constraint."
                )
        elif gross < 0:
            out["reading"] = (
                "The gross edge is negative, so costs are not the problem - the "
                "rule is. Cheaper execution would not fix this."
            )
        return out

    def disposition(self) -> Optional[Dict[str, object]]:
        """Are losers held longer than winners?

        The disposition effect is the best-documented behavioural failure in
        the retail literature, and it is measurable rather than introspective:
        compare how long winners were held against losers. A rule with a fixed
        stop and a holding cap is structurally protected from it, so this is
        mostly a check that the protection is working - if it ever shows up
        here, something is overriding the exits.
        """
        winners = [t.holding_days for t in self.trades if t.won]
        losers = [t.holding_days for t in self.trades if not t.won]
        winners = [d for d in winners if d is not None]
        losers = [d for d in losers if d is not None]
        if len(winners) < MINIMUM_PER_GROUP or len(losers) < MINIMUM_PER_GROUP:
            # Run live on 3 trades this flagged "disposition effect present"
            # off a single winner and two losers. A module whose whole purpose
            # is refusing to read signal into small samples must not do it
            # here either.
            return {
                "note": (
                    "Needs {0} winners and {0} losers before a holding-period "
                    "comparison means anything; have {1} and {2}."
                ).format(MINIMUM_PER_GROUP, len(winners), len(losers))
            }
        held_w = sum(winners) / len(winners)
        held_l = sum(losers) / len(losers)
        # BOTH tests: proportionally longer AND longer by an amount that
        # matters. The ratio alone flagged a one-hour difference between
        # same-session trades as "something is overriding the exits".
        present = (held_l > held_w * 1.25
                   and (held_l - held_w) >= MINIMUM_DISPOSITION_GAP_DAYS)
        return {
            "mean_holding_days_winners": round(held_w, 2),
            "mean_holding_days_losers": round(held_l, 2),
            "losers_held_longer_by_days": round(held_l - held_w, 2),
            "disposition_effect_present": bool(present),
            "reading": (
                "Losers are being held materially longer than winners, which is "
                "the classic pattern. With a fixed stop and a holding cap in "
                "force, that points at something overriding the exits."
                if present else
                "Losers are not being held longer than winners."
            ),
        }

    def consistency(self) -> Optional[Dict[str, object]]:
        """Sharpe, the Grinold decomposition, and what a normal bad run looks like.

        The record could previously report a win rate and a p-value but had no
        measure of CONSISTENCY, which is what actually decides whether a
        strategy is worth running. `stats.py` has carried the machinery for
        this since the beginning and nothing used it.

        Three things come out of it:

        Sharpe, annualised from the observed trade rate. This is the number
        professionals actually judge by, because a return can be manufactured
        with leverage and says nothing about repeatability.

        The Grinold decomposition. IR = IC x sqrt(breadth), so an information
        ratio and a trade rate imply a skill level. It is worth seeing because
        the implied IC is usually far higher than any real forecaster sustains
        - a world-class equity manager runs about 0.05 - and an implied IC of
        0.3 is a statement that the sample is too small, not that the rule is
        extraordinary.

        Expected losing months. A Sharpe 1.0 strategy loses money in 4.6 months
        of an average year. Knowing that in advance is what stops a normal run
        being mistaken for a broken system.
        """
        n = len(self.trades)
        if n < 5:
            return {"note": "Needs at least 5 closed trades before a Sharpe "
                            "ratio means anything; have {0}.".format(n)}
        if self.sessions_observed < MINIMUM_SESSIONS_FOR_RATE:
            return {"note": (
                "Annualising needs a trade rate, and {0} observed session(s) "
                "cannot supply one. At least {1} are needed before the rate - "
                "and every figure built on it - means anything."
            ).format(self.sessions_observed, MINIMUM_SESSIONS_FOR_RATE)}

        breadth = n / float(self.sessions_observed) * SESSIONS_PER_YEAR
        if breadth <= 0:
            return {"note": "No trades observed per session."}
        sharpe = sharpe_ratio(self.returns, periods_per_year=breadth)
        if sharpe is None:
            return {"note": "Every trade returned the same amount, so there is "
                            "no dispersion to measure consistency against."}

        # P(a month loses) = Phi(-S/sqrt(12)) for an annual Sharpe S.
        losing_months = 12.0 * normal_cdf(-sharpe / math.sqrt(12.0))
        implied_ic = sharpe / math.sqrt(breadth)
        mean_return = sum(self.returns) / n

        out: Dict[str, object] = {
            "annualised_sharpe": round(sharpe, 3),
            "breadth_trades_per_year": round(breadth, 1),
            "implied_information_coefficient": round(implied_ic, 4),
            "expected_losing_months_per_year": round(losing_months, 1),
            "mean_return_per_trade": round(mean_return, 6),
            "decay_adjusted_sharpe": round(sharpe * DECAY_HAIRCUT, 3),
            "decay_adjusted_mean_return": round(mean_return * DECAY_HAIRCUT, 6),
        }

        # The search has to be paid for. `trials_tested` is a fact about how
        # the strategy was arrived at, not about the data, so it cannot be
        # inferred here - it is supplied, and left at 1 it corrects nothing.
        if self.trials_tested > 1:
            deflated = deflated_sharpe_ratio(
                self.returns, self.trials_tested, periods_per_year=breadth)
            out["trials_tested"] = self.trials_tested
            out["deflated_sharpe_probability"] = (
                None if deflated is None else round(deflated, 4))
            out["deflated_note"] = (
                "Probability the true Sharpe beats what the luckiest of {0} "
                "no-edge trials would have reached.".format(self.trials_tested)
            )

        if implied_ic > 0.15:
            out["reading"] = (
                "An implied IC of {0:.2f} is far above what world-class "
                "forecasters sustain (~0.05). On {1} trades this says the "
                "sample is too small to trust, not that the rule is "
                "exceptional.".format(implied_ic, n)
            )
        elif sharpe >= 1.0:
            out["reading"] = (
                "Sharpe {0:.2f} is professional-grade if it survives more "
                "trades. Expect {1:.1f} losing months a year even so."
            ).format(sharpe, losing_months)
        return out

    def verdict(self) -> Dict[str, object]:
        n = len(self.trades)
        if n == 0:
            return {
                "status": "NO_TRADES_YET",
                "explanation": (
                    "Nothing has traded. At about one trade per 51 sessions this is "
                    "the expected state for weeks at a time, not a malfunction."
                ),
                "trades_needed": MINIMUM_INFORMATIVE_TRADES,
            }

        interval = wilson_interval(self.wins, n)
        mean_return = sum(self.returns) / n
        boot = bootstrap_ci(self.returns) if n >= 5 else None
        pvalue = sign_flip_pvalue(self.returns) if n >= 5 else None

        # A confidence interval that still contains a coin flip means the
        # record is consistent with having no skill at all.
        spans_chance = bool(interval and interval[0] <= 0.5 <= interval[1])
        spans_zero = bool(boot and boot[0] <= 0.0 <= boot[1])

        if n < MINIMUM_INFORMATIVE_TRADES:
            status = "INSUFFICIENT_EVIDENCE"
            explanation = (
                "{0} trades is too few to distinguish skill from luck. Keep running; "
                "no conclusion either way is justified yet."
            ).format(n)
        elif spans_zero or spans_chance:
            status = "NOT_DISTINGUISHABLE_FROM_LUCK"
            explanation = (
                "With {0} trades the interval around the result still includes "
                "'no edge'. That is not proof it fails - it is the absence of proof "
                "that it works."
            ).format(n)
        elif mean_return > 0:
            status = "POSITIVE_AND_MEASURABLE"
            explanation = (
                "Over {0} trades the result is positive and its interval excludes "
                "zero. Compare it against buy-and-hold before concluding it is worth "
                "the effort."
            ).format(n)
        else:
            status = "NEGATIVE_AND_MEASURABLE"
            explanation = "Over {0} trades the result is reliably negative.".format(n)

        # The comparison that decides whether any of this was worth doing.
        # Not "did it make money" - "did it beat the thing available for one
        # trade and no attention". This module used to TELL the reader to make
        # that comparison and then not make it, which is the same as not
        # making it. Every configuration measured in this project lost to SPY
        # until the last one.
        realized = (
            (self.ending_equity / self.starting_equity - 1.0)
            if self.starting_equity else 0.0
        )
        excess: Optional[float] = None
        base_note: Optional[str] = None
        if self.benchmark_return is not None and not self.equity_base_is_real:
            # $3.76 of profit is +0.376% against the 1,000.0 placeholder and
            # +0.004% against the real 100,000 account. The first comfortably
            # "beats" a 0.44% index; the second loses to it badly. Refusing the
            # comparison is the only honest option when the denominator is a
            # guess.
            base_note = (
                "No comparison shown: the capital base is a placeholder "
                "({0:,.2f}), not the account's real equity. Pass the account "
                "size, or run where the audit log records equity."
            ).format(self.starting_equity)
        elif self.benchmark_return is not None:
            excess = realized - self.benchmark_return
            if status == "POSITIVE_AND_MEASURABLE":
                if excess <= 0:
                    status = "POSITIVE_BUT_BEATEN_BY_BUY_AND_HOLD"
                    explanation = (
                        "Over {0} trades the per-trade edge is real and its interval "
                        "excludes zero - but the account returned {1:+.2f}% against "
                        "buy-and-hold's {2:+.2f}% over the same window. An edge that "
                        "trails the index is still a worse outcome than one trade and "
                        "no attention."
                    ).format(n, 100 * realized, 100 * self.benchmark_return)
                else:
                    explanation = (
                        "Over {0} trades the result is positive, its interval excludes "
                        "zero, and it beat buy-and-hold by {1:.2f} points over the same "
                        "window ({2:+.2f}% against {3:+.2f}%)."
                    ).format(n, 100 * excess, 100 * realized, 100 * self.benchmark_return)

        return {
            "status": status,
            "explanation": explanation,
            "trades": n,
            "wins": self.wins,
            "win_rate": round(self.wins / n, 4),
            "win_rate_95_interval": [round(v, 4) for v in interval] if interval else None,
            "win_rate_interval_includes_a_coin_flip": spans_chance,
            "mean_return_per_trade": round(mean_return, 6),
            "mean_return_95_interval": [round(v, 6) for v in boot] if boot else None,
            "mean_return_interval_includes_zero": spans_zero,
            "sign_flip_pvalue": None if pvalue is None else round(pvalue, 4),
            "trades_still_needed_for_a_first_read": max(0, MINIMUM_INFORMATIVE_TRADES - n),
            "trades_for_confidence_in_a_modest_edge": max(0, TRADES_FOR_A_MODEST_EDGE - n),
            "time_to_evidence": self._time_to_evidence(n),
            "vs_buy_and_hold": (
                {"note": base_note} if base_note else
                None if excess is None else {
                    "strategy_return_pct": round(100 * realized, 3),
                    "buy_and_hold_return_pct": round(100 * self.benchmark_return, 3),
                    "excess_return_pct": round(100 * excess, 3),
                    "beat_buy_and_hold": bool(excess > 0),
                }
            ),
            "friction": self.friction(),
            "disposition": self.disposition(),
            "consistency": self.consistency(),
        }

    def _time_to_evidence(self, n: int) -> Dict[str, object]:
        """How long the observed trade rate takes to reach an answerable sample.

        This is the number that decides whether "run it and see" is a plan or
        a wish. A rule that trades rarely enough can be *unfalsifiable in
        practice*: correct, careful, and still unanswerable within any horizon
        a person will actually wait.
        """
        if not n:
            return {"note": "No trades yet, so there is no rate to estimate."}
        if self.sessions_observed < MINIMUM_SESSIONS_FOR_RATE:
            return {"note": (
                "{0} observed session(s) is too short a window to estimate a "
                "trade rate; {1} are needed. Annualising from it would report "
                "a horizon the record cannot support."
            ).format(self.sessions_observed, MINIMUM_SESSIONS_FOR_RATE),
                "sessions_observed": self.sessions_observed}
        per_session = n / self.sessions_observed
        if per_session <= 0:
            return {"note": "No trades observed."}
        sessions_per_year = 252.0

        def years_for(target: int) -> float:
            return max(0.0, (target - n) / per_session / sessions_per_year)

        return {
            "trades_per_year_at_this_rate": round(per_session * sessions_per_year, 2),
            "years_to_a_first_read": round(years_for(MINIMUM_INFORMATIVE_TRADES), 1),
            "years_to_confidence_in_a_modest_edge": round(
                years_for(TRADES_FOR_A_MODEST_EDGE), 1
            ),
        }

    def as_dict(self) -> Dict[str, object]:
        total = (
            (self.ending_equity / self.starting_equity - 1.0) if self.starting_equity else 0.0
        )
        payload: Dict[str, object] = {
            "starting_equity": round(self.starting_equity, 2),
            "ending_equity": round(self.ending_equity, 2),
            "total_return_pct": round(100 * total, 3),
            "closed_trades": [
                {
                    "symbol": t.symbol, "opened": t.opened, "closed": t.closed,
                    "net_pnl": round(t.net_pnl, 2),
                    "return_pct": round(100 * t.return_fraction, 3),
                }
                for t in self.trades
            ],
            "assessment": self.verdict(),
        }
        if self.benchmark_return is not None:
            payload["benchmark_return_pct"] = round(100 * self.benchmark_return, 3)
            payload["beat_benchmark"] = bool(total > self.benchmark_return)
        return payload


def from_audit_log(path: Path, starting_equity: float = 1_000.0) -> RecordReport:
    """Rebuild the record from what autotrade actually did.

    Reads only `entry`/`exit` events, so a log full of `hold` and
    `run_complete` lines still produces a clean record.

    `ending_equity` is the starting figure plus the realized P&L of every
    closed trade. It used to be left equal to `starting_equity`, which made
    `total_return_pct` structurally 0.000 in every report this ever wrote -
    including WEEKLY-RECORD.json and FINAL-RECORD.json, the two files the
    whole experiment exists to produce. A constant zero is worse than a wrong
    number because it never looks wrong.
    """
    report = RecordReport(starting_equity=starting_equity, ending_equity=starting_equity)
    if not path.exists():
        return report

    opened: Dict[str, Dict[str, object]] = {}
    # Distinct dates on which the loop actually ran. Without this
    # `sessions_observed` stayed 0 for every live record, so the trade rate was
    # unknown and every annualised figure - time to evidence, breadth, Sharpe -
    # silently declined to compute.
    sessions: set = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        event, detail = row.get("event"), row.get("detail", {})
        if event == "run_complete":
            when = _parse_when(row.get("at"))
            if when is not None:
                sessions.add(when.date())
        symbol = str(detail.get("symbol", ""))
        if not symbol:
            continue
        if event == "entry":
            opened[symbol] = {"at": row.get("at"), "quantity": detail.get("quantity")}
        elif event == "exit" and symbol in opened:
            entry = opened.pop(symbol)
            # An audit log records intent, not fills; P&L is only known when
            # the broker reports it, so this is left explicit rather than guessed.
            report.trades.append(
                TradeRecord(
                    symbol=symbol,
                    opened=str(entry.get("at")),
                    closed=str(row.get("at")),
                    net_pnl=float(detail.get("realized_pnl", 0.0) or 0.0),
                    return_fraction=float(detail.get("return_fraction", 0.0) or 0.0),
                    fees=abs(float(detail.get("fees", 0.0) or 0.0)),
                )
            )
    report.ending_equity = starting_equity + sum(t.net_pnl for t in report.trades)
    report.sessions_observed = len(sessions)
    return report


def equity_base_from_log(path: Path) -> Optional[float]:
    """The account's equity at the earliest cycle the log recorded one.

    `run_complete` rows carry the broker's equity. That is the real capital
    base the record's P&L should be measured against; the module's 1,000.0
    default is a leftover from when this project assumed a $1,000 account and
    is wrong by two orders of magnitude for the account it now runs on.
    """
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("event") != "run_complete":
            continue
        equity = (row.get("detail") or {}).get("equity")
        if equity is None:
            continue
        try:
            value = float(equity)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def buy_and_hold_return(
    bars: Sequence[Any], start: Any, end: Any
) -> Optional[float]:
    """What holding the benchmark across exactly this window would have paid.

    The window is the record's own - first entry to last exit - rather than a
    fixed period, so the comparison is against the alternative that was
    actually available while the strategy was running. A hardcoded figure
    would go stale and quietly flatter or punish the record depending on when
    it was written.

    Returns None rather than guessing when the window cannot be covered by the
    bars supplied; a missing comparison is honest, a fabricated one is not.
    """
    first, last = _parse_when(start), _parse_when(end)
    if first is None or last is None or last < first:
        return None
    inside = []
    for bar in bars:
        when = getattr(bar, "timestamp", None)
        if when is None:
            continue
        if getattr(when, "tzinfo", None) is not None:
            when = when.astimezone(timezone.utc).replace(tzinfo=None)
        if first.date() <= when.date() <= last.date():
            inside.append(float(bar.close))
    if len(inside) < 2 or inside[0] <= 0:
        return None
    return inside[-1] / inside[0] - 1.0


def window_of(report: RecordReport) -> Optional[Sequence[str]]:
    """First entry and last exit in the record, for pricing the benchmark."""
    if not report.trades:
        return None
    opened = [t.opened for t in report.trades if _parse_when(t.opened)]
    closed = [t.closed for t in report.trades if _parse_when(t.closed)]
    if not opened or not closed:
        return None
    return (min(opened, key=lambda v: _parse_when(v)),
            max(closed, key=lambda v: _parse_when(v)))


def from_portfolio(report_obj, benchmark_return: Optional[float] = None) -> RecordReport:
    """Build the same assessment from a simulated portfolio run."""
    out = RecordReport(
        starting_equity=report_obj.starting_cash,
        ending_equity=report_obj.equity,
        benchmark_return=benchmark_return,
        sessions_observed=getattr(report_obj, "days_simulated", 0),
        # A simulated run knows exactly what it started with.
        equity_base_is_real=True,
    )
    for t in report_obj.trades:
        out.trades.append(
            TradeRecord(
                symbol=t.symbol,
                opened=t.entry_time.isoformat(),
                closed=t.exit_time.isoformat(),
                net_pnl=t.net_pnl,
                return_fraction=(t.exit_price / t.entry_price - 1.0) if t.entry_price else 0.0,
            )
        )
    return out
