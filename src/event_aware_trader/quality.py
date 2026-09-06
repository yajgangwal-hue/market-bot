"""Input validation for price series.

A rule tested on broken data produces a confident, meaningless number.  Yahoo
and other free sources routinely serve duplicated sessions, unadjusted splits,
zero-volume holidays, and bars where the high is below the close.  This module
finds those before a backtest turns them into an apparent edge.

Severities:

``error``    the series should not be used as-is.
``warning``  usable, but the result carries an asterisk.
``note``     worth knowing; not a threat to the conclusion.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence

from .types import Bar


SEVERITY_ORDER = {"note": 0, "warning": 1, "error": 2}

# Ratios that a real ETF close rarely produces overnight but a missed split
# reproduces exactly.  Checked with a tolerance because prices are rounded.
COMMON_SPLIT_RATIOS = (2.0, 3.0, 4.0, 5.0, 10.0, 1.5, 2.5)


@dataclass(frozen=True)
class QualityIssue:
    severity: str
    code: str
    message: str
    count: int = 1
    examples: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "count": self.count,
            "examples": self.examples[:5],
        }


@dataclass(frozen=True)
class QualityReport:
    symbol: str
    bar_count: int
    first_timestamp: Optional[str]
    last_timestamp: Optional[str]
    issues: List[QualityIssue]

    @property
    def worst_severity(self) -> str:
        if not self.issues:
            return "note"
        return max((issue.severity for issue in self.issues), key=lambda value: SEVERITY_ORDER[value])

    @property
    def is_usable(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def as_dict(self) -> Dict[str, object]:
        return {
            "symbol": self.symbol,
            "bar_count": self.bar_count,
            "first_timestamp": self.first_timestamp,
            "last_timestamp": self.last_timestamp,
            "worst_severity": self.worst_severity,
            "usable": self.is_usable,
            "issue_count": len(self.issues),
            "issues": [issue.as_dict() for issue in self.issues],
            "note": "Clean data is a precondition for a meaningful backtest, not a sign of one.",
        }


def _near_ratio(value: float, target: float, tolerance: float = 0.04) -> bool:
    return abs(value - target) / target <= tolerance


def validate_bars(
    bars: Sequence[Bar],
    symbol: str = "",
    max_gap_days: int = 5,
    jump_threshold: float = 0.20,
    min_bars: int = 60,
    as_of: Optional[date] = None,
) -> QualityReport:
    """Inspect a price series for the defects that quietly corrupt a backtest.

    `as_of` marks the first date whose bar has NOT finished forming. Pass
    today's date for a daily series and any bar on or after it is reported as
    unclosed. Leave it None for intraday data, where a bar stamped today is
    ordinary.
    """
    issues: List[QualityIssue] = []
    if not bars:
        return QualityReport(symbol.upper(), 0, None, None, [QualityIssue("error", "empty_series", "The price series contains no bars")])

    # An in-progress candle is the defect this project actually shipped: ten
    # crypto files carried a bar dated the current day, a candle that does not
    # close until UTC midnight. A daily rule reading it prices its RSI and its
    # 200-day average off a few hours of an unfinished session, while a
    # backtest over the same code sees a completed bar. The timestamp is
    # legitimately today's date, so nothing else here catches it.
    unclosed: List[str] = []
    if as_of is not None:
        for bar in bars:
            if bar.timestamp.date() >= as_of:
                unclosed.append(str(bar.timestamp))

    ordered = sorted(bars, key=lambda bar: bar.timestamp)
    if [bar.timestamp for bar in ordered] != [bar.timestamp for bar in bars]:
        issues.append(QualityIssue("warning", "unsorted", "Bars were not in chronological order and had to be sorted"))

    if len(ordered) < min_bars:
        issues.append(
            QualityIssue(
                "error",
                "insufficient_history",
                "Only {0} bars supplied; at least {1} are needed for warm-up plus a testable sample".format(len(ordered), min_bars),
            )
        )

    duplicates: List[str] = []
    incoherent: List[str] = []
    non_positive: List[str] = []
    negative_volume: List[str] = []
    zero_volume: List[str] = []
    gaps: List[str] = []
    jumps: List[str] = []
    suspected_splits: List[str] = []
    frozen: List[str] = []
    naive_timestamps = 0
    aware_timestamps = 0

    previous: Optional[Bar] = None
    repeat_run = 0
    for bar in ordered:
        stamp = bar.timestamp.isoformat()
        if bar.timestamp.tzinfo is None:
            naive_timestamps += 1
        else:
            aware_timestamps += 1
        if min(bar.open, bar.high, bar.low, bar.close) <= 0:
            non_positive.append(stamp)
        elif bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close) or bar.high < bar.low:
            incoherent.append(stamp)
        if bar.volume < 0:
            negative_volume.append(stamp)
        elif bar.volume == 0:
            zero_volume.append(stamp)
        if previous is not None:
            if bar.timestamp == previous.timestamp:
                duplicates.append(stamp)
            else:
                calendar_gap = (bar.timestamp.date() - previous.timestamp.date()).days
                if calendar_gap > max_gap_days + 2:
                    gaps.append("{0} -> {1} ({2} calendar days)".format(previous.timestamp.date(), bar.timestamp.date(), calendar_gap))
            if previous.close > 0 and bar.close > 0:
                change = bar.close / previous.close - 1.0
                if abs(change) >= jump_threshold:
                    jumps.append("{0}: {1:+.1%}".format(stamp, change))
                    ratio = previous.close / bar.close if bar.close < previous.close else bar.close / previous.close
                    if any(_near_ratio(ratio, target) for target in COMMON_SPLIT_RATIOS):
                        suspected_splits.append("{0}: close ratio {1:.2f}".format(stamp, ratio))
            if bar.close == previous.close and bar.high == previous.high and bar.low == previous.low:
                repeat_run += 1
                if repeat_run >= 2:
                    frozen.append(stamp)
            else:
                repeat_run = 0
        previous = bar

    if unclosed:
        issues.append(QualityIssue(
            "error", "unclosed_bar",
            "Bars dated on or after {0} have not finished forming; a daily rule "
            "reading them is acting on a partial session".format(as_of),
            len(unclosed), unclosed[:5]))
    if duplicates:
        issues.append(QualityIssue("error", "duplicate_timestamps", "Repeated timestamps double-count a session", len(duplicates), duplicates))
    if non_positive:
        issues.append(QualityIssue("error", "non_positive_price", "Bars contain a zero or negative price", len(non_positive), non_positive))
    if incoherent:
        issues.append(QualityIssue("error", "ohlc_incoherent", "High/low do not bracket open/close, so stop and target fills cannot be simulated", len(incoherent), incoherent))
    if negative_volume:
        issues.append(QualityIssue("error", "negative_volume", "Negative volume is impossible and corrupts the liquidity gate", len(negative_volume), negative_volume))
    if suspected_splits:
        issues.append(QualityIssue("error", "suspected_unadjusted_split", "A close-to-close ratio matches a common split; an unadjusted series invents a huge fake loss", len(suspected_splits), suspected_splits))
    if naive_timestamps and aware_timestamps:
        issues.append(QualityIssue("error", "mixed_timezone_awareness", "The series mixes naive and timezone-aware timestamps, which makes event availability checks unreliable"))
    if zero_volume:
        issues.append(QualityIssue("warning", "zero_volume", "Zero-volume sessions are usually holidays or stale rows; relative volume is undefined there", len(zero_volume), zero_volume))
    if gaps:
        issues.append(QualityIssue("warning", "calendar_gap", "Sessions are missing; indicator windows silently span the hole", len(gaps), gaps))
    if frozen:
        issues.append(QualityIssue("warning", "repeated_bar", "Consecutive identical high/low/close values suggest a stale feed", len(frozen), frozen))
    if jumps and not suspected_splits:
        issues.append(QualityIssue("note", "large_move", "Large single-session moves are present; confirm they are real events, not data errors", len(jumps), jumps))
    if naive_timestamps and not aware_timestamps:
        issues.append(QualityIssue("note", "naive_timestamps", "Timestamps carry no timezone; they are treated as UTC when compared with event times"))

    return QualityReport(
        symbol=symbol.upper(),
        bar_count=len(ordered),
        first_timestamp=ordered[0].timestamp.isoformat(),
        last_timestamp=ordered[-1].timestamp.isoformat(),
        issues=issues,
    )


def assert_usable(report: QualityReport) -> None:
    """Raise when a series carries an error-severity defect."""
    if report.is_usable:
        return
    blocking = [issue for issue in report.issues if issue.severity == "error"]
    raise ValueError(
        "Price data for {0} failed validation: {1}".format(
            report.symbol or "the series", "; ".join(issue.message for issue in blocking)
        )
    )


def staleness_days(bars: Sequence[Bar], reference) -> Optional[float]:
    """Age of the newest bar in days, for spotting a stale local CSV."""
    if not bars:
        return None
    last = max(bar.timestamp for bar in bars)
    if last.tzinfo is None and reference.tzinfo is not None:
        reference = reference.replace(tzinfo=None)
    elif last.tzinfo is not None and reference.tzinfo is None:
        last = last.replace(tzinfo=None)
    return max(0.0, (reference - last).total_seconds() / 86400.0)
