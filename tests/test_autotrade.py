import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.autotrade import AutoTradeConfig, run_once
from event_aware_trader.risk import RiskPolicy
from event_aware_trader.strategy import StrategyConfig
from tests.fake_broker import FakeBroker
from tests.test_strategy import trending_bars


def _config(tmp, **overrides):
    settings = dict(
        dry_run=True,
        audit_log=Path(tmp) / "audit.jsonl",
        state_file=Path(tmp) / "state.json",
        universe=("SPY", "QQQ"),
        # These tests were written against the trend gate and their fixtures
        # are trending bars, so they pin it rather than following the shipped
        # default. Mean reversion has its own tests; leaving these implicit
        # would silently stop exercising the trend path the moment the default
        # moved, which is exactly what happened when it did.
        entry_rule="trend",
        # Entries are windowed to the last 30 minutes of the session in
        # the shipped config. These tests are about what an order LOOKS like,
        # not about when it is sent, and their FakeBroker clock sits six hours
        # from the close - so they pin the window off rather than following
        # the default. test_entry_timing.py is where the window is tested.
        entry_window_minutes=None,
    )
    settings.update(overrides)
    return AutoTradeConfig(**settings)


def _bars():
    return {"SPY": trending_bars(count=90), "QQQ": trending_bars(count=90)}


class EntryTests(unittest.TestCase):
    def test_a_qualifying_setup_produces_an_order(self):
        # A funded account, matching the real paper account. Whole-share
        # sizing is required for a broker-side stop, and whole shares need
        # enough equity to afford one - see the small-account test below.
        with TemporaryDirectory() as tmp:
            broker = FakeBroker(equity=100_000.0)
            result = run_once(_config(tmp), broker=broker, bars_by_symbol=_bars())
            self.assertEqual(result["status"], "ok")
            self.assertGreater(result["entries"], 0)
            self.assertTrue(broker.submitted)

    def test_orders_are_whole_shares_so_a_resting_stop_can_be_attached(self):
        """Alpaca rejects a bracket on a fractional quantity, so a fractional
        order would reach the broker with no protection at all."""
        with TemporaryDirectory() as tmp:
            broker = FakeBroker(equity=100_000.0)
            run_once(_config(tmp), broker=broker, bars_by_symbol=_bars())
            self.assertTrue(broker.submitted)
            for _, quantity, _, _ in broker.submitted:
                self.assertEqual(quantity, round(quantity),
                                 "fractional order cannot carry a broker-side stop")

    def test_an_account_too_small_for_a_whole_share_sends_nothing(self):
        """Refusing to trade beats sending an unprotected order."""
        with TemporaryDirectory() as tmp:
            broker = FakeBroker(equity=200.0)
            result = run_once(_config(tmp), broker=broker, bars_by_symbol=_bars())
            self.assertEqual(result["entries"], 0)
            self.assertFalse(broker.submitted)

    def test_dry_run_never_submits_for_real(self):
        with TemporaryDirectory() as tmp:
            broker = FakeBroker(equity=100_000.0)
            run_once(_config(tmp), broker=broker, bars_by_symbol=_bars())
            for _, _, _, dry in broker.submitted:
                self.assertTrue(dry)

    def test_correlation_bucket_cap_blocks_a_second_tech_name(self):
        """SPY is broad_equity and QQQ is technology, so both may open; two
        technology names must not."""
        with TemporaryDirectory() as tmp:
            broker = FakeBroker(equity=100_000.0)
            bars = {"QQQ": trending_bars(count=90), "XLK": trending_bars(count=90)}
            result = run_once(
                _config(tmp, universe=("QQQ", "XLK")), broker=broker, bars_by_symbol=bars
            )
            self.assertLessEqual(result["entries"], 1)

    def test_max_orders_per_run_is_respected(self):
        with TemporaryDirectory() as tmp:
            broker = FakeBroker(equity=100_000.0)
            result = run_once(
                _config(tmp, max_orders_per_run=1), broker=broker, bars_by_symbol=_bars()
            )
            self.assertLessEqual(result["entries"], 1)

    def test_existing_position_is_not_reopened(self):
        with TemporaryDirectory() as tmp:
            broker = FakeBroker(positions=[{
                "symbol": "SPY", "quantity": 0.5, "average_entry_price": 100.0,
                "market_value": 55.0, "unrealized_pnl": 5.0,
            }])
            run_once(_config(tmp), broker=broker, bars_by_symbol=_bars())
            self.assertNotIn("SPY", [s for s, *_ in broker.submitted])


class GuardTests(unittest.TestCase):
    def test_trading_blocked_halts_everything(self):
        with TemporaryDirectory() as tmp:
            broker = FakeBroker(blocked=True)
            result = run_once(_config(tmp), broker=broker, bars_by_symbol=_bars())
            self.assertEqual(result["status"], "halted")
            self.assertFalse(broker.submitted)

    def test_daily_loss_guard_suspends_new_entries(self):
        with TemporaryDirectory() as tmp:
            config = _config(tmp)
            # Seed the session with a higher opening equity than the broker now shows.
            config.state_file.parent.mkdir(parents=True, exist_ok=True)
            config.state_file.write_text(json.dumps({
                "session": date.today().isoformat(),
                "opening_equity": 1000.0,
                "orders_today": 0,
            }), encoding="utf-8")
            broker = FakeBroker(equity=970.0)   # -3%, past the 1.5% guard
            result = run_once(config, broker=broker, bars_by_symbol=_bars())
            self.assertEqual(result["status"], "halted_for_the_day")
            self.assertEqual(result["entries"], 0)
            self.assertFalse(broker.submitted)

    def test_position_size_never_exceeds_the_risk_budget(self):
        with TemporaryDirectory() as tmp:
            broker = FakeBroker(equity=1000.0)
            run_once(_config(tmp), broker=broker, bars_by_symbol=_bars(),
                     policy=RiskPolicy())
            for symbol, quantity, stop, _ in broker.submitted:
                self.assertGreater(quantity, 0)


class ExitTests(unittest.TestCase):
    def test_a_position_below_its_stop_is_closed(self):
        with TemporaryDirectory() as tmp:
            bars = _bars()
            # entry far above the current price, so any stop sits above it
            broker = FakeBroker(positions=[{
                "symbol": "SPY", "quantity": 0.5,
                "average_entry_price": bars["SPY"][-1].close * 2.0,
                "market_value": 10.0, "unrealized_pnl": -50.0,
            }])
            result = run_once(_config(tmp), broker=broker, bars_by_symbol=bars)
            self.assertEqual(result["exits"], 1)
            self.assertEqual(broker.closed[0][0], "SPY")


class AuditTests(unittest.TestCase):
    def test_every_run_is_written_to_the_audit_log(self):
        with TemporaryDirectory() as tmp:
            config = _config(tmp)
            run_once(config, broker=FakeBroker(), bars_by_symbol=_bars())
            lines = config.audit_log.read_text(encoding="utf-8").splitlines()
            self.assertTrue(lines)
            for line in lines:
                record = json.loads(line)
                self.assertIn("event", record)
                self.assertIn("at", record)

    def test_interval_config_is_scaled_not_reshaped(self):
        daily = StrategyConfig.for_interval("1d")
        fifteen = StrategyConfig.for_interval("15m")
        self.assertLess(fifteen.score_separation_max, daily.score_separation_max)
        self.assertLess(fifteen.min_atr_fraction, daily.min_atr_fraction)
        # the shape of the rules is unchanged
        self.assertEqual(fifteen.stop_atr_multiple, daily.stop_atr_multiple)
        self.assertEqual(fifteen.minimum_score, daily.minimum_score)


if __name__ == "__main__":
    unittest.main()


class MarketClockTests(unittest.TestCase):
    """launchd coalesces runs missed while asleep and fires once on wake. A
    DAY market order sent after the close queues to the next open and fills at
    an unknown price against stale analysis."""

    def test_a_closed_market_places_nothing(self):
        with TemporaryDirectory() as tmp:
            broker = FakeBroker(equity=100_000.0, market_open=False)
            result = run_once(_config(tmp), broker=broker, bars_by_symbol=_bars())
            self.assertEqual(result["status"], "market_closed")
            self.assertFalse(broker.submitted)
            self.assertFalse(broker.closed)

    def test_an_open_market_proceeds(self):
        with TemporaryDirectory() as tmp:
            broker = FakeBroker(equity=100_000.0, market_open=True)
            result = run_once(_config(tmp), broker=broker, bars_by_symbol=_bars())
            self.assertNotEqual(result["status"], "market_closed")


class RetryTests(unittest.TestCase):
    def test_a_transient_broker_error_is_retried_not_fatal(self):
        """One 500 used to abort the cycle including exits."""
        with TemporaryDirectory() as tmp:
            config = _config(tmp)
            config.retry_backoff_seconds = 0.0
            broker = FakeBroker(equity=100_000.0, fail_times=2)
            result = run_once(config, broker=broker, bars_by_symbol=_bars())
            self.assertNotEqual(result["status"], "halted")
            self.assertGreaterEqual(broker.calls, 3)

    def test_persistent_failure_still_surfaces(self):
        from event_aware_trader.broker import BrokerError

        with TemporaryDirectory() as tmp:
            config = _config(tmp)
            config.retry_backoff_seconds = 0.0
            broker = FakeBroker(equity=100_000.0, fail_times=99)
            with self.assertRaises(BrokerError):
                run_once(config, broker=broker, bars_by_symbol=_bars())


class WeeklyGuardTests(unittest.TestCase):
    def test_the_weekly_guard_halts_entries(self):
        """--max-weekly-loss was accepted, reported as set, and enforced nowhere."""
        import datetime as _dt

        with TemporaryDirectory() as tmp:
            config = _config(tmp)
            week = "{0}-W{1}".format(*_dt.date.today().isocalendar()[:2])
            config.state_file.parent.mkdir(parents=True, exist_ok=True)
            config.state_file.write_text(json.dumps({
                "session": date.today().isoformat(),
                "opening_equity": 100_000.0,
                "week": week,
                "week_opening_equity": 100_000.0,
                "orders_today": 0,
            }), encoding="utf-8")
            broker = FakeBroker(equity=90_000.0)          # -10%, past the 6% weekly cap
            result = run_once(config, broker=broker, bars_by_symbol=_bars())
            self.assertEqual(result["entries"], 0)
            self.assertFalse(broker.submitted)


class AtomicStateTests(unittest.TestCase):
    def test_a_truncated_state_file_cannot_silently_rearm_the_guard(self):
        """The old write truncated first; a kill mid-write left {} and
        re-baselined opening_equity to the drawn-down value."""
        with TemporaryDirectory() as tmp:
            config = _config(tmp)
            run_once(config, broker=FakeBroker(equity=100_000.0), bars_by_symbol=_bars())
            written = json.loads(config.state_file.read_text())
            self.assertIn("opening_equity", written)
            self.assertFalse(
                list(config.state_file.parent.glob("*.tmp")),
                "temp file left behind; the rename did not complete",
            )


class NoEntryReportingTests(unittest.TestCase):
    """A cycle that buys nothing must still say what it nearly bought.

    On 2026-08-31 the bot placed no trades for a whole session and the logs
    could not distinguish "nothing qualified" from "never ran". Entries of
    zero is the normal case for this strategy, so it is exactly the case that
    has to stay legible.
    """

    def test_a_cycle_that_opens_nothing_reports_its_closest_candidates(self):
        from dataclasses import replace
        with TemporaryDirectory() as tmp:
            config = _config(tmp)
            # Clears every hard blocker, cannot reach an impossible score gate:
            # the WATCH path, which is distinct from a hard REJECT.
            strategy = replace(StrategyConfig.for_interval("1d"), minimum_score=99.0)
            # Funded, so the ONLY reason for zero entries is the score gate.
            # An underfunded account also yields zero and would let this test
            # pass without exercising the WATCH path at all.
            result = run_once(config, broker=FakeBroker(equity=100_000.0),
                              bars_by_symbol=_bars(), strategy=strategy)
            self.assertEqual(result["entries"], 0)

            events = [json.loads(line) for line
                      in config.audit_log.read_text(encoding="utf-8").splitlines()]
            reports = [e for e in events if e["event"] == "no_entries_closest_candidates"]
            self.assertEqual(len(reports), 1)

            detail = reports[0]["detail"]
            self.assertEqual(detail["gate"], 99.0)
            self.assertTrue(detail["closest"])
            best = detail["closest"][0]
            self.assertIn(best["symbol"], {"SPY", "QQQ"})
            self.assertGreater(best["short_by"], 0)
            # Ranked best-first, so the report names the real nearest miss.
            scores = [c["score"] for c in detail["closest"]]
            self.assertEqual(scores, sorted(scores, reverse=True))

    def test_a_cycle_that_does_trade_files_no_near_miss_report(self):
        with TemporaryDirectory() as tmp:
            config = _config(tmp)
            result = run_once(config, broker=FakeBroker(equity=100_000.0),
                              bars_by_symbol=_bars())
            self.assertGreater(result["entries"], 0)
            events = [json.loads(line) for line
                      in config.audit_log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(
                [e for e in events if e["event"] == "no_entries_closest_candidates"], [])
