import math
import sys
import time
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from event_aware_trader.data import fetch_yahoo_bars_many, load_bars

HEADER = "timestamp,open,high,low,close,volume\n"
GOOD = "2026-01-02T16:00:00+00:00,100,101,99,100.5,1000000\n"


class DataTests(unittest.TestCase):
    def _load(self, body):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.csv"
            path.write_text(HEADER + body, encoding="utf-8")
            return load_bars(path)

    def test_nan_close_row_is_skipped(self):
        """Yahoo reports the still-open session with a NaN close, not a null."""
        bars = self._load(GOOD + "2026-01-03T16:00:00+00:00,101,102,100,nan,900000\n")
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].close, 100.5)

    def test_infinite_and_non_positive_prices_are_skipped(self):
        bars = self._load(
            GOOD
            + "2026-01-03T16:00:00+00:00,101,inf,100,101.5,900000\n"
            + "2026-01-04T16:00:00+00:00,101,102,100,0,900000\n"
            + "2026-01-05T16:00:00+00:00,101,102,100,-5,900000\n"
        )
        self.assertEqual(len(bars), 1)

    def test_a_file_of_only_bad_rows_raises(self):
        with self.assertRaises(ValueError):
            self._load("2026-01-03T16:00:00+00:00,101,102,100,nan,900000\n")


if __name__ == "__main__":
    unittest.main()


class BatchHistoryParsingTests(unittest.TestCase):
    """The batched path must screen exactly what the per-symbol path screens.

    Batching was added because 120 requests a cycle got rate-limited and lost
    6-18 symbols silently. It would be a poor trade to fix that by letting a
    NaN or a still-open bar through on the new path.
    """

    def _frame(self):
        import pandas as pd
        index = pd.to_datetime(["2026-08-27", "2026-08-28", "2026-08-31"])
        return pd.DataFrame(
            {
                "Open": [100.0, 101.0, 102.0],
                "High": [101.0, 102.0, 103.0],
                "Low": [99.0, 100.0, 101.0],
                # The last row is the session still in progress.
                "Close": [100.5, 101.5, float("nan")],
                "Volume": [1000.0, 1100.0, 1200.0],
            },
            index=index,
        )

    def test_a_still_open_bar_with_a_nan_close_is_dropped(self):
        from event_aware_trader.data import _bars_from_history
        bars = _bars_from_history(self._frame(), "1d", "TEST")
        self.assertEqual(len(bars), 2)
        for bar in bars:
            self.assertFalse(math.isnan(bar.close))

    def test_a_daily_bar_is_stamped_at_the_close_not_midnight(self):
        from event_aware_trader.data import _bars_from_history
        bars = _bars_from_history(self._frame(), "1d", "TEST")
        # Midnight would make a same-day signal look knowable before it was.
        for bar in bars:
            self.assertEqual(bar.timestamp.hour, 16)

    def test_an_intraday_bar_keeps_its_own_timestamp(self):
        from event_aware_trader.data import _bars_from_history
        bars = _bars_from_history(self._frame(), "15m", "TEST")
        self.assertEqual(bars[0].timestamp.hour, 0)

    def test_a_frame_with_nothing_usable_raises_rather_than_returning_empty(self):
        from event_aware_trader.data import _bars_from_history
        frame = self._frame()
        frame["Close"] = [float("nan")] * 3
        # Silently returning [] would read downstream as "no signal".
        with self.assertRaises(ValueError):
            _bars_from_history(frame, "1d", "TEST")


class FetchBudgetTests(unittest.TestCase):
    """A fetch that outlives its slot makes launchd skip the next cycle.

    On 2026-08-31 one symbol hung for 375s inside a single request and the
    session ran 11 of its 26 scheduled cycles. These pin the ceiling.
    """

    def _fake_yfinance(self, on_download):
        module = types.ModuleType("yfinance")
        module.download = on_download

        class _Ticker:                      # the straggler path uses this
            def __init__(self, symbol):
                self.symbol = symbol

            def history(self, **kwargs):
                raise AssertionError("straggler retry ran past the budget")

        module.Ticker = _Ticker
        return module

    def test_an_exhausted_budget_reports_failures_without_requesting(self):
        calls = []

        def download(**kwargs):
            calls.append(kwargs)
            raise AssertionError("no request may be made with no budget")

        with mock.patch.dict(sys.modules, {"yfinance": self._fake_yfinance(download)}):
            bars, failures = fetch_yahoo_bars_many(
                ["SPY", "QQQ"], budget_seconds=0.0)

        self.assertEqual(bars, {})
        self.assertEqual(sorted(failures), ["QQQ", "SPY"])
        self.assertIn("budget", failures["SPY"])
        self.assertEqual(calls, [], "budget was exhausted; nothing should be requested")

    def test_a_slow_source_cannot_outlive_the_budget(self):
        def download(**kwargs):
            time.sleep(0.2)
            raise RuntimeError("upstream is slow, then fails")

        symbols = ["S{0}".format(i) for i in range(60)]
        start = time.monotonic()
        with mock.patch.dict(sys.modules, {"yfinance": self._fake_yfinance(download)}):
            bars, failures = fetch_yahoo_bars_many(
                symbols, chunk_size=10, retries=2,
                pause_seconds=0.0, budget_seconds=0.5)
        elapsed = time.monotonic() - start

        # Six chunks at 0.2s each would be 1.2s with no budget, and the
        # straggler retries would then run 120 more requests on top.
        self.assertLess(elapsed, 2.0)
        self.assertEqual(len(failures), 60)
        self.assertEqual(bars, {})

    def test_the_download_is_given_an_explicit_timeout(self):
        seen = {}

        def download(**kwargs):
            seen.update(kwargs)
            raise RuntimeError("stop here; the timeout is what matters")

        with mock.patch.dict(sys.modules, {"yfinance": self._fake_yfinance(download)}):
            fetch_yahoo_bars_many(["SPY"], timeout_seconds=7.0, retries=0)

        # yfinance defaults this to 10s, but the observed hang was 375s, so it
        # must be passed explicitly rather than relied upon.
        self.assertEqual(seen.get("timeout"), 7.0)
