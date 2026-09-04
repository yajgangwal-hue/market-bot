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


def _bars_from_history(history, interval: str, symbol: str) -> List[Bar]:
    """Turn one yfinance frame into Bars, applying the same screens either path."""
    bars: List[Bar] = []
    for timestamp, row in history.iterrows():
        try:
            candidate_values = (
                float(row["Open"]), float(row["High"]),
                float(row["Low"]), float(row["Close"]), float(row["Volume"]),
            )
        except (TypeError, ValueError, KeyError):
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
                open=candidate_values[0],
                high=candidate_values[1],
                low=candidate_values[2],
                close=candidate_values[3],
                volume=candidate_values[4],
            )
        )
    if not bars:
        raise ValueError("No valid bars returned for {0}".format(symbol))
    return bars


def fetch_alpaca_crypto_bars(symbol: str, days: int = 760) -> List[Bar]:
    """Daily bars for one crypto pair from Alpaca's own market data API.

    Uses the slashed symbol ("BTC/USD"), which is what every Alpaca endpoint
    speaks. Credentials come from the environment exactly as the broker's do,
    so nothing new needs configuring.
    """
    import json
    import os
    import urllib.parse
    import urllib.request
    from datetime import datetime, timedelta, timezone

    key = os.environ.get("APCA_API_KEY_ID", "").strip()
    secret = os.environ.get("APCA_API_SECRET_KEY", "").strip()
    if not key or not secret:
        raise RuntimeError(
            "Crypto bars need APCA_API_KEY_ID and APCA_API_SECRET_KEY in the "
            "environment, the same keys the broker uses."
        )
    start = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

    rows, token = [], None
    while True:
        url = ("https://data.alpaca.markets/v1beta3/crypto/us/bars"
               "?symbols={0}&timeframe=1Day&start={1}&limit=10000".format(
                   urllib.parse.quote(symbol), start))
        if token:
            url += "&page_token=" + urllib.parse.quote(token)
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
        rows.extend(payload.get("bars", {}).get(symbol, []))
        token = payload.get("next_page_token")
        if not token:
            break
    if not rows:
        raise ValueError("No Alpaca crypto bars returned for {0}".format(symbol))

    out: List[Bar] = []
    for row in rows:
        out.append(Bar(
            timestamp=_parse_timestamp(row["t"]),
            open=float(row["o"]), high=float(row["h"]), low=float(row["l"]),
            close=float(row["c"]), volume=float(row["v"]),
        ))
    return out


def price_file_name(symbol: str) -> str:
    """Filesystem-safe stem for a symbol's price file.

    Crypto pairs are slashed ("BTC/USD") because that is what Alpaca returns
    everywhere, and a slash in a path is a directory separator. Mapping to
    "BTC-USD" keeps one canonical symbol in memory and one safe name on disk.
    """
    return str(symbol).replace("/", "-")


def price_file(data_dir, symbol: str):
    """The path a symbol's daily bars live at, under `data_dir`."""
    from pathlib import Path as _Path
    return _Path(data_dir) / "{0}.csv".format(price_file_name(symbol))


def fetch_yahoo_bars(symbol: str, period: str = "2y", interval: str = "1d") -> List[Bar]:
    """Download data only.  yfinance is optional until this function is used."""
    try:
        import yfinance as yf
    except ImportError as error:
        raise RuntimeError("Install yfinance with `python -m pip install -e .` to download market data") from error
    history = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=False, actions=False)
    if history.empty:
        raise ValueError("No Yahoo Finance data returned for {0}".format(symbol))
    return _bars_from_history(history, interval, symbol)


def fetch_yahoo_bars_many(
    symbols: Sequence[str],
    period: str = "2y",
    interval: str = "1d",
    chunk_size: int = 25,
    retries: int = 2,
    pause_seconds: float = 1.5,
    timeout_seconds: float = 20.0,
    budget_seconds: float = 240.0,
):
    """Fetch many symbols in a few batched requests instead of one apiece.

    One request per symbol does not scale. At 120 symbols every 15 minutes that
    is ~3,100 requests a session, and Yahoo starts refusing them: on 2026-08-31
    live cycles silently lost 6-18 symbols each - including QQQ - and a
    rate-limited symbol is indistinguishable from one with no signal. Cycles
    also stretched past the 15-minute cadence, so scheduled slots were missed.

    Batching turns 120 requests into ~5. Anything still missing is retried
    individually, because a symbol dropped from a batch is usually transient
    and silently trading on a partial universe is the failure being fixed.

    Returns ``(bars_by_symbol, failures)`` where failures maps symbol -> reason.
    Callers must treat a non-empty ``failures`` as a real problem, not noise.

    Bounded on the wall clock, because an unbounded fetch is what broke the
    schedule. On 2026-08-31 a single symbol hung for 375 seconds inside one
    request; the straggler path calls ``Ticker().history()``, which accepts no
    timeout at all, up to ``retries`` times per symbol. Eighteen stragglers
    could therefore occupy hours, and a cycle that outlives its 15-minute slot
    makes launchd skip the next one - the bot slept through 15 of 26 decision
    points that day. ``budget_seconds`` is a hard ceiling on the whole call:
    once spent, whatever is still missing is returned as a failure rather than
    waited on. Late data is worth less than a cycle that runs on time.
    """
    try:
        import yfinance as yf
    except ImportError as error:
        raise RuntimeError("Install yfinance with `python -m pip install -e .` to download market data") from error

    import time

    deadline = time.monotonic() + max(0.0, budget_seconds)
    wanted = [s for s in dict.fromkeys(symbols)]     # de-dup, keep order
    collected: dict = {}
    failures: dict = {}

    for start in range(0, len(wanted), max(1, chunk_size)):
        chunk = wanted[start:start + max(1, chunk_size)]
        if time.monotonic() >= deadline:
            for symbol in chunk:
                failures[symbol] = "fetch budget exhausted before request"
            continue
        try:
            frame = yf.download(
                tickers=" ".join(chunk), period=period, interval=interval,
                group_by="ticker", auto_adjust=False, actions=False,
                progress=False, threads=False, timeout=timeout_seconds,
            )
        except Exception as error:                    # whole chunk failed
            for symbol in chunk:
                failures[symbol] = "batch request failed: {0}".format(error)[:120]
            continue
        for symbol in chunk:
            try:
                # One ticker comes back without the ticker column level.
                sub = frame[symbol] if len(chunk) > 1 else frame
                if sub is None or sub.empty:
                    failures[symbol] = "empty in batch response"
                    continue
                collected[symbol] = _bars_from_history(sub, interval, symbol)
            except Exception as error:
                failures[symbol] = str(error)[:120]
        if start + chunk_size < len(wanted):
            time.sleep(pause_seconds)

    # Retry the stragglers one at a time; a batch drop is usually transient.
    for _ in range(max(0, retries)):
        if not failures or time.monotonic() >= deadline:
            break
        for symbol in list(failures):
            if time.monotonic() >= deadline:
                break
            try:
                collected[symbol] = fetch_yahoo_bars(symbol, period, interval)
                failures.pop(symbol, None)
            except Exception as error:
                failures[symbol] = str(error)[:120]
            time.sleep(pause_seconds / 3.0)

    return collected, failures
