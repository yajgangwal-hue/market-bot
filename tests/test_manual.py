import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.manual import (
    HeldPosition,
    advance_stop,
    apply_stop_update,
    daily_brief,
    load_positions,
    save_positions,
)
from tests.test_strategy import trending_bars


def position(**overrides):
    base = dict(
        symbol="SPY", quantity=0.5, entry_price=100.0, entry_date="2026-01-01",
        initial_stop=95.0, current_stop=95.0, highest_high=100.0,
    )
    base.update(overrides)
    return HeldPosition(**base)


class StopRatchetTests(unittest.TestCase):
    def setUp(self):
        self.bars = trending_bars(count=120)

    def test_stop_never_moves_down(self):
        """A stop that can loosen is not a stop."""
        pos = position(entry_price=self.bars[60].close, entry_date=self.bars[60].timestamp.date().isoformat())
        pos.initial_stop = pos.entry_price * 0.95
        pos.current_stop = pos.initial_stop
        previous = pos.current_stop
        for end in range(61, len(self.bars)):
            update = advance_stop(pos, self.bars[:end])
            self.assertGreaterEqual(update["new_stop"], previous - 1e-9)
            previous = update["new_stop"]
            apply_stop_update(pos, update)

    def test_trail_does_not_arm_before_the_activation_threshold(self):
        pos = position(entry_price=self.bars[-1].close * 1.10,
                       entry_date=self.bars[-2].timestamp.date().isoformat())
        pos.initial_stop = pos.entry_price * 0.95
        pos.current_stop = pos.initial_stop
        update = advance_stop(pos, self.bars)
        self.assertFalse(update["trailing_armed"])
        self.assertEqual(update["new_stop"], round(pos.initial_stop, 2))

    def test_breached_stop_produces_an_exit_instruction(self):
        pos = position(entry_price=self.bars[-1].close,
                       entry_date=self.bars[-1].timestamp.date().isoformat())
        pos.initial_stop = self.bars[-1].high * 1.5   # already far above the bar
        pos.current_stop = pos.initial_stop
        update = advance_stop(pos, self.bars)
        self.assertEqual(update["action"], "EXIT")
        self.assertIn("SELL", update["instruction"])

    def test_missing_price_data_is_reported_not_guessed(self):
        pos = position(entry_date="2099-01-01")
        self.assertEqual(advance_stop(pos, self.bars)["action"], "no_data")


class BriefTests(unittest.TestCase):
    def setUp(self):
        self.series = {"SPY": trending_bars(count=140), "QQQ": trending_bars(count=140)}

    def test_empty_book_gives_a_do_nothing_summary(self):
        brief = daily_brief(self.series, [], 1_000.0)
        self.assertEqual(brief["open_position_count"], 0)
        self.assertIsInstance(brief["summary"], str)

    def test_a_held_symbol_is_not_offered_as_a_new_candidate(self):
        held = position(symbol="SPY", entry_date=self.series["SPY"][100].timestamp.date().isoformat())
        brief = daily_brief(self.series, [held], 1_000.0)
        self.assertNotIn("SPY", [c["symbol"] for c in brief["new_candidates"]])

    def test_candidate_quantity_respects_the_risk_budget(self):
        brief = daily_brief(self.series, [], 1_000.0)
        for candidate in brief["new_candidates"]:
            self.assertLessEqual(candidate["planned_risk"], 1_000.0 * 0.005 + 0.01)
            self.assertGreater(candidate["suggested_quantity"], 0)

    def test_brief_states_that_it_places_no_orders(self):
        brief = daily_brief(self.series, [], 1_000.0)
        self.assertIn("nothing here places an order", brief["note"].lower())


class PositionBookTests(unittest.TestCase):
    def test_round_trip_through_disk(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "positions.json"
            save_positions(path, [position(), position(symbol="GLD")])
            loaded = load_positions(path)
            self.assertEqual([p.symbol for p in loaded], ["SPY", "GLD"])
            self.assertEqual(loaded[0].current_stop, 95.0)

    def test_missing_file_is_an_empty_book_not_an_error(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(load_positions(Path(tmp) / "nope.json"), [])

    def test_correlation_bucket_is_derived_from_the_symbol(self):
        self.assertEqual(position(symbol="XLK").bucket, "technology")
        self.assertEqual(position(symbol="GLD").bucket, "precious_metals")

    def test_near_duplicate_exposures_share_one_bucket(self):
        """Holding GLD and SLV at once is one trade twice, not diversification."""
        for left, right in (("GLD", "SLV"), ("QQQ", "XLK"), ("XLE", "USO"), ("SPY", "DIA")):
            self.assertEqual(position(symbol=left).bucket, position(symbol=right).bucket)


if __name__ == "__main__":
    unittest.main()
