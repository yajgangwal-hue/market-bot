import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.ledger import Ledger, load_ledger, reset_ledger, save_ledger


class LedgerTests(unittest.TestCase):
    def test_a_fresh_ledger_opens_at_the_starting_equity(self):
        with TemporaryDirectory() as tmp:
            ledger = load_ledger(Path(tmp) / "l.json", 1_000.0)
            self.assertEqual(ledger.current_equity, 1_000.0)
            self.assertEqual(ledger.runs, [])

    def test_balance_carries_from_one_run_to_the_next(self):
        """A run that ends at $1,035 is the run the next one begins with."""
        ledger = Ledger(starting_equity=1_000.0, current_equity=1_000.0)
        ledger.record("test 1", 1_035.0, trades=7, wins=5)
        self.assertEqual(ledger.current_equity, 1_035.0)
        second = ledger.record("test 2", 1_012.5, trades=4, wins=2)
        self.assertEqual(second.opening_equity, 1_035.0)
        self.assertAlmostEqual(second.pnl, -22.5)

    def test_totals_are_measured_against_the_original_stake(self):
        ledger = Ledger(starting_equity=1_000.0, current_equity=1_000.0)
        ledger.record("a", 1_100.0, 1, 1)
        ledger.record("b", 1_210.0, 1, 1)
        self.assertAlmostEqual(ledger.total_pnl, 210.0)
        self.assertAlmostEqual(ledger.total_return, 0.21)

    def test_a_losing_sequence_compounds_downward_too(self):
        ledger = Ledger(starting_equity=1_000.0, current_equity=1_000.0)
        for closing in (900.0, 810.0, 729.0):
            ledger.record("down", closing, 1, 0)
        self.assertAlmostEqual(ledger.current_equity, 729.0)
        self.assertLess(ledger.total_return, -0.27)

    def test_negative_closing_equity_is_refused(self):
        ledger = Ledger()
        with self.assertRaises(ValueError):
            ledger.record("impossible", -1.0, 0, 0)

    def test_round_trip_through_disk_preserves_history(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "l.json"
            ledger = load_ledger(path)
            ledger.record("test 1", 1_035.0, 7, 5)
            ledger.record("test 2", 1_012.5, 4, 2)
            save_ledger(path, ledger)
            reloaded = load_ledger(path)
            self.assertEqual(reloaded.current_equity, 1_012.5)
            self.assertEqual(len(reloaded.runs), 2)
            self.assertEqual(reloaded.runs[0].label, "test 1")

    def test_reset_clears_history_and_balance(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "l.json"
            ledger = load_ledger(path)
            ledger.record("test 1", 2_000.0, 1, 1)
            save_ledger(path, ledger)
            fresh = reset_ledger(path, 1_000.0)
            self.assertEqual(fresh.current_equity, 1_000.0)
            self.assertEqual(load_ledger(path).runs, [])

    def test_saved_file_says_it_is_not_a_brokerage_statement(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "l.json"
            save_ledger(path, load_ledger(path))
            self.assertIn("Not a brokerage statement", json.loads(path.read_text())["note"])


class TradeWindowTests(unittest.TestCase):
    def test_entries_are_withheld_until_the_window_opens(self):
        from datetime import timedelta
        from event_aware_trader.portfolio import run_portfolio
        from event_aware_trader.strategy import StrategyConfig
        from tests.test_strategy import trending_bars

        bars = trending_bars(count=200)
        cutoff = bars[150].timestamp.date()
        report = run_portfolio(
            {"SPY": bars}, starting_cash=1_000.0,
            config=StrategyConfig(exit_mode="trailing"), trade_from=cutoff,
        )
        for trade in report.trades:
            self.assertGreaterEqual(trade.entry_time.date(), cutoff)
        for position in report.open_positions:
            self.assertGreaterEqual(position.entry_time.date(), cutoff)


if __name__ == "__main__":
    unittest.main()
