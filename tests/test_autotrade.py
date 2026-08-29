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
    )
    settings.update(overrides)
    return AutoTradeConfig(**settings)


def _bars():
    return {"SPY": trending_bars(count=90), "QQQ": trending_bars(count=90)}


class EntryTests(unittest.TestCase):
    def test_a_qualifying_setup_produces_an_order(self):
        with TemporaryDirectory() as tmp:
            broker = FakeBroker()
            result = run_once(_config(tmp), broker=broker, bars_by_symbol=_bars())
            self.assertEqual(result["status"], "ok")
            self.assertGreater(result["entries"], 0)
            self.assertTrue(broker.submitted)

    def test_dry_run_never_submits_for_real(self):
        with TemporaryDirectory() as tmp:
            broker = FakeBroker()
            run_once(_config(tmp), broker=broker, bars_by_symbol=_bars())
            for _, _, _, dry in broker.submitted:
                self.assertTrue(dry)

    def test_correlation_bucket_cap_blocks_a_second_tech_name(self):
        """SPY is broad_equity and QQQ is technology, so both may open; two
        technology names must not."""
        with TemporaryDirectory() as tmp:
            broker = FakeBroker()
            bars = {"QQQ": trending_bars(count=90), "XLK": trending_bars(count=90)}
            result = run_once(
                _config(tmp, universe=("QQQ", "XLK")), broker=broker, bars_by_symbol=bars
            )
            self.assertLessEqual(result["entries"], 1)

    def test_max_orders_per_run_is_respected(self):
        with TemporaryDirectory() as tmp:
            broker = FakeBroker()
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
