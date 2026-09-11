"""Local CSV storage and optional Yahoo Finance retrieval."""

import csv
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

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


def _bars_from_history(
    history, interval: str, symbol: str, as_of: Optional[datetime] = None
) -> List[Bar]:
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
        # A provider is not required to mark an in-progress daily candle with
        # NaN. Treating its current price as the day's close lets a live loop
        # act on an RSI that did not exist at the previous close, while a
        # historical backtest sees a completed candle - lookahead in practice,
        # even though the timestamp is legitimately today's date. The NaN check
        # above catches Yahoo's usual behaviour, not a guarantee.
        #
        # Daily rules therefore only receive bars strictly before the local
        # current date; the completed candle becomes eligible the next day.
        # `as_of` exists for deterministic tests and should normally be left
        # unset.
        if interval == "1d":
            reference = as_of
            if reference is None:
                reference = (datetime.now(time_value.tzinfo) if time_value.tzinfo
                             else datetime.now())
            if time_value.date() >= reference.date():
                continue
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
    today_utc = datetime.now(timezone.utc).date()
    for row in rows:
        timestamp = _parse_timestamp(row["t"])
        # Crypto trades continuously, so a 1Day candle stays in progress until
        # UTC midnight. Feeding that partial bar to a daily rule prices its RSI
        # and 200-day average off a few hours of today rather than a completed
        # session. Measured 2026-09-05: every crypto file on disk carried one.
        if timestamp.astimezone(timezone.utc).date() >= today_utc:
            continue
        out.append(Bar(
            timestamp=timestamp,
            open=float(row["o"]), high=float(row["h"]), low=float(row["l"]),
            close=float(row["c"]), volume=float(row["v"]),
        ))
    if not out:
        raise ValueError(
            "No completed Alpaca crypto bars returned for {0}".format(symbol))
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


ALPACA_TIMEFRAMES = {
    "1d": "1Day", "1h": "1Hour", "30m": "30Min", "15m": "15Min", "5m": "5Min",
}


def fetch_alpaca_equity_bars(
    symbols: Sequence[str], days: int = 760, batch: int = 100,
    interval: str = "1d", include_today: bool = False,
) -> dict:
    """Daily bars for many US equities from Alpaca's own market data API.

    The same credentials the broker uses, so nothing new needs configuring.
    Returns {symbol: [Bar]} and simply omits anything the API has no data for.

    Preferred over the Yahoo path for two measured reasons. It returns the
    full consolidated session rather than a partial one - on 2026-09-06 all 59
    price files carrying an incoherent final bar were Yahoo-sourced and all
    110 Alpaca-sourced files were clean. And it takes many symbols per
    request, so a universe screen is a few hundred calls rather than one per
    name into a rate limit.
    """
    import json
    import os
    import time
    import urllib.parse
    import urllib.request
    from datetime import datetime, timedelta, timezone

    key = os.environ.get("APCA_API_KEY_ID", "").strip()
    secret = os.environ.get("APCA_API_SECRET_KEY", "").strip()
    if not key or not secret:
        raise RuntimeError(
            "Alpaca bars need APCA_API_KEY_ID and APCA_API_SECRET_KEY in the "
            "environment, the same keys the broker uses."
        )
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    start = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    today_utc = datetime.now(timezone.utc).date()

    # Share classes are spelled differently on either side of the same broker:
    # the trading API and this project's universe say "BRK-B", the market data
    # API says "BRK.B" and answers a hyphen with HTTP 400 - which fails the
    # whole batch, not just that symbol. Translate on the way out and map back
    # on the way in so callers keep using one spelling.
    timeframe = ALPACA_TIMEFRAMES.get(interval)
    if timeframe is None:
        raise ValueError("Unsupported interval {0!r}; expected one of {1}".format(
            interval, ", ".join(sorted(ALPACA_TIMEFRAMES))))

    wanted = [s.strip().upper() for s in symbols if s and s.strip()]
    as_api = {symbol: symbol.replace("-", ".") for symbol in wanted}
    back = {api: symbol for symbol, api in as_api.items()}

    out: dict = {}
    for index in range(0, len(wanted), batch):
        chunk = [as_api[symbol] for symbol in wanted[index:index + batch]]
        collected: dict = {}
        token = None
        while True:
            # adjustment=split, deliberately, and not "all".
            #
            # Splits MUST be adjusted or the series is broken: AVGO's 10-for-1
            # on 2024-07-15 shows as a 9.92x close-to-close ratio in raw data,
            # so a 200-day average and an RSI computed over it are measured
            # across a fake 90% crash. Split-adjusted the worst ratio in the
            # same two years is 1.24.
            #
            # Dividends are deliberately NOT adjusted. Back-adjusting them
            # rewrites historical prices below what actually traded, and the
            # rule compares prices against absolute thresholds - a $20 minimum,
            # a stop stored from a real fill - which only make sense against
            # prices the market really printed.
            url = ("https://data.alpaca.markets/v2/stocks/bars?symbols={0}"
                   "&timeframe={1}&start={2}&limit=10000&adjustment=split".format(
                       urllib.parse.quote(",".join(chunk)), timeframe, start))
            if token:
                url += "&page_token=" + urllib.parse.quote(token)
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.loads(response.read().decode("utf-8"))
            for symbol, rows in (payload.get("bars") or {}).items():
                collected.setdefault(symbol, []).extend(rows)
            token = payload.get("next_page_token")
            if not token:
                break
        for symbol, rows in collected.items():
            bars: List[Bar] = []
            for row in rows:
                timestamp = _parse_timestamp(row["t"])
                # Today's DAILY bar is partial until the session closes -
                # the defect that reached ten crypto files and 59 equity ones.
                # Intraday bars are a different matter: a 15-minute bar from
                # this morning is complete and is exactly what a live loop
                # needs, so the filter applies only to daily data.
                #
                # `include_today` asks for that partial bar ON PURPOSE, and
                # exactly one caller does: the close-window entry path, which
                # has to read the session it is about to close in. A partial
                # bar is legitimate to DECIDE on and never legitimate to SAVE
                # - it would freeze a half-formed session into the history and
                # every average computed from it afterwards. Anything that
                # writes to disk must leave this False, which is why it is
                # False by default and why `save_bars` is never reached from
                # the path that sets it.
                if (interval == "1d" and not include_today
                        and timestamp.astimezone(timezone.utc).date() >= today_utc):
                    continue
                bars.append(Bar(
                    timestamp=timestamp,
                    open=float(row["o"]), high=float(row["h"]),
                    low=float(row["l"]), close=float(row["c"]),
                    volume=float(row["v"]),
                ))
            if bars:
                out[back.get(symbol, symbol)] = sorted(
                    bars, key=lambda b: b.timestamp)
        time.sleep(0.35)
    return out


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
