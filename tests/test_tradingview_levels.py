"""The generated TradingView indicator must state the truth about exits.

The request was to see "take profits and stop losses" on the chart. Stop
losses are real and fixed at entry. Take profits DO NOT EXIST in this bot,
and that is deliberate: the entry order carries a take-profit leg only so
Alpaca will accept it as a bracket, and `_reconcile_protective_stops` cancels
that leg on the next cycle, because the simulator never exits on a target
under the shipped exit mode. Drawing a take-profit line would put a level on
the chart that the bot will never act on - worse than drawing nothing.

So the property under test is not "does it draw lines". It is: does it draw
the exits the bot ACTUALLY has - the stop, the RSI recovery, the holding cap -
and does it decline to invent the one it does not.
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from tradingview_levels import pine_for, positions_and_stops


ROWS = [{"symbol": "RTX", "entry": 199.28, "stop": 198.3111,
         "opened_at": "2026-09-08T19:30:00+00:00"}]


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.pine = pine_for(ROWS, 60.0, 14, 20)

    def test_the_stop_price_is_present_and_exact(self):
        self.assertIn("stopPrice  := 198.3111", self.pine)

    def test_the_entry_price_is_present(self):
        self.assertIn("entryPrice := 199.2800", self.pine)

    def test_it_says_plainly_that_there_is_no_take_profit(self):
        self.assertIn("does not have one", self.pine)
        self.assertIn("none by design", self.pine)

    def test_it_draws_no_take_profit_line(self):
        """The failure this test exists to prevent."""
        lowered = self.pine.lower()
        self.assertNotIn("takeprofit :=", lowered)
        self.assertNotIn("targetprice :=", lowered)

    def test_the_rsi_exit_is_computed_live_rather_than_baked(self):
        """It is a condition, not a price, so Pine must evaluate it itself."""
        self.assertIn("ta.rsi(close, rsiLen)", self.pine)
        self.assertIn("strength >= rsiExit", self.pine)

    def test_the_holding_cap_is_represented(self):
        self.assertIn("holdBars", self.pine)
        self.assertIn("entryMs", self.pine)

    def test_the_entry_timestamp_becomes_pine_milliseconds(self):
        """Pine's `time` is epoch milliseconds, so the stamp must convert.

        The expected value is derived rather than written down: a hand-typed
        epoch is exactly the kind of constant that is wrong by hours and never
        noticed, and the first version of this test was wrong by 17 hours.
        """
        from datetime import datetime
        expected = int(datetime.fromisoformat(
            "2026-09-08T19:30:00+00:00").timestamp() * 1000)
        self.assertIn("entryMs    := {0}".format(expected), self.pine)

    def test_a_naive_timestamp_is_read_as_utc_rather_than_local(self):
        """Price files carry both conventions; the wrong one shifts the
        holding-cap line by hours."""
        from datetime import datetime, timezone
        rows = [{"symbol": "AAA", "entry": 10.0, "stop": 9.0,
                 "opened_at": "2026-09-08T19:30:00"}]
        expected = int(datetime(2026, 9, 8, 19, 30,
                                tzinfo=timezone.utc).timestamp() * 1000)
        self.assertIn("entryMs    := {0}".format(expected),
                      pine_for(rows, 60.0, 14, 20))

    def test_an_unparseable_timestamp_degrades_to_no_cap_line(self):
        rows = [{"symbol": "AAA", "entry": 10.0, "stop": 9.0,
                 "opened_at": "not a date"}]
        self.assertIn("entryMs    := 0", pine_for(rows, 60.0, 14, 20))

    def test_the_rule_constants_come_from_the_shipped_config(self):
        """A chart showing 55 while the bot exits at 60 is a lie."""
        from event_aware_trader.mean_reversion import MeanReversionConfig
        config = MeanReversionConfig()
        generated = pine_for(ROWS, config.rsi_exit, config.rsi_period,
                             config.max_holding_bars)
        self.assertIn('input.float({0}'.format(config.rsi_exit), generated)
        self.assertIn('input.int({0},'.format(config.max_holding_bars), generated)


class SymbolSpellingTests(unittest.TestCase):
    def test_a_share_class_is_spelled_the_tradingview_way(self):
        """This project says BRK-B; TradingView says BRK.B."""
        rows = [{"symbol": "BRK-B", "entry": 100.0, "stop": 95.0, "opened_at": ""}]
        self.assertIn('sym == "BRK.B"', pine_for(rows, 60.0, 14, 20))

    def test_a_crypto_pair_loses_its_slash(self):
        rows = [{"symbol": "BTC/USD", "entry": 100.0, "stop": 95.0, "opened_at": ""}]
        self.assertIn('sym == "BTCUSD"', pine_for(rows, 60.0, 14, 20))


class EmptyStateTests(unittest.TestCase):
    def test_holding_nothing_still_produces_a_valid_script(self):
        pine = pine_for([], 60.0, 14, 20)
        self.assertIn("holds nothing right now", pine)
        self.assertIn("indicator(", pine)

    def test_a_position_with_no_recorded_stop_is_skipped(self):
        """Better absent than drawn at a level nobody chose."""
        with TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            state.write_text(json.dumps({"stops": {}}), encoding="utf-8")
            self.assertEqual(positions_and_stops(state, use_broker=False), [])

    def test_a_missing_state_file_is_not_an_error(self):
        with TemporaryDirectory() as tmp:
            rows = positions_and_stops(Path(tmp) / "absent.json", use_broker=False)
            self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
