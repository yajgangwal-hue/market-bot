"""Local CSV storage and optional Yahoo Finance retrieval."""

import csv
import math
from datetime import datetime
from pathlib import Path
from typing import List, Sequence

from .types import Bar


REQUIRED_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}


def _is_usable(*values: float) -> bool:
    """Reject a bar containing NaN, infinity, or a non-positive price.

    Yahoo returns a placeholder row for the session that is still open, and its
    close arrives as NaN rather than as a missing field.  ``value is None`` does
    not catch that, because NaN is a perfectly good float.  An unscreened NaN
    propagates silently through every moving average, ATR, and RSI, and only
    surfaces much later as ``cannot convert float NaN to integer`` inside
    position sizing - or, worse, as a NaN P&L that quietly poisons an equity
    curve.  Screening at the boundary keeps the failure local and visible.
    """
    for value in values:
        if value is None or math.isnan(value) or math.isinf(value):
            return False
    return True


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_bars(path: Path) -> List[Bar]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Price CSV has no header")
        names = {name.strip().lower() for name in reader.fieldnames}
        missing = REQUIRED_COLUMNS - names
        if missing:
            raise ValueError("Price CSV is missing: {0}".format(", ".join(sorted(missing))))
        bars = []
        skipped = 0
        for row in reader:
            normalised = {key.strip().lower(): value for key, value in row.items() if key is not None}
            try:
                values = tuple(
                    float(normalised[name]) for name in ("open", "high", "low", "close", "volume")
                )
            except (TypeError, ValueError):
                skipped += 1
                continue
            if not _is_usable(*values) or min(values[:4]) <= 0:
                skipped += 1
                continue
            open_, high, low, close, volume = values
            bars.append(
                Bar(
                    timestamp=_parse_timestamp(normalised["timestamp"]),
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )
    if not bars:
        raise ValueError("Price CSV contains no bars")
    return sorted(bars, key=lambda bar: bar.timestamp)


def save_bars(path: Path, bars: Sequence[Bar]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        for bar in bars:
            writer.writerow(
                {
                    "timestamp": bar.timestamp.isoformat(),
                    "open": "{0:.8f}".format(bar.open),
                    "high": "{0:.8f}".format(bar.high),
                    "low": "{0:.8f}".format(bar.low),
                    "close": "{0:.8f}".format(bar.close),
                    "volume": "{0:.0f}".format(bar.volume),
                }
            )


def fetch_yahoo_bars(symbol: str, period: str = "2y", interval: str = "1d") -> List[Bar]:
    """Download data only.  yfinance is optional until this function is used."""
    try:
        import yfinance as yf
    except ImportError as error:
        raise RuntimeError("Install yfinance with `python -m pip install -e .` to download market data") from error
    history = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=False, actions=False)
    if history.empty:
        raise ValueError("No Yahoo Finance data returned for {0}".format(symbol))
    bars: List[Bar] = []
    for timestamp, row in history.iterrows():
        try:
            candidate_values = (
                float(row["Open"]), float(row["High"]),
                float(row["Low"]), float(row["Close"]), float(row["Volume"]),
            )
        except (TypeError, ValueError):
            continue
        # Skips the still-open session, whose close Yahoo reports as NaN.
        if not _is_usable(*candidate_values) or min(candidate_values[:4]) <= 0:
            continue
        time_value = timestamp.to_pydatetime() if hasattr(timestamp, "to_pydatetime") else timestamp
        # Yahoo labels a daily OHLCV bar at midnight. A daily signal is only
        # knowable after that session closes, so store it at 16:00 local market
        # time. This prevents an 08:30 release from being incorrectly treated
        # as future information on the same trading date.
        if interval == "1d" and time_value.hour == 0 and time_value.minute == 0:
            time_value = time_value.replace(hour=16)
        bars.append(
            Bar(
                timestamp=time_value,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
            )
        )
    if not bars:
        raise ValueError("No valid bars returned for {0}".format(symbol))
    return bars
