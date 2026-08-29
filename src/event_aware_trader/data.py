"""Local CSV storage and optional Yahoo Finance retrieval."""

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Sequence

from .types import Bar


REQUIRED_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}


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
        for row in reader:
            normalised = {key.strip().lower(): value for key, value in row.items() if key is not None}
            bars.append(
                Bar(
                    timestamp=_parse_timestamp(normalised["timestamp"]),
                    open=float(normalised["open"]),
                    high=float(normalised["high"]),
                    low=float(normalised["low"]),
                    close=float(normalised["close"]),
                    volume=float(normalised["volume"]),
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
        if any(value is None for value in (row["Open"], row["High"], row["Low"], row["Close"], row["Volume"])):
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
