"""Rebuilding a trade the rule did not close.

The case that matters most is the stop: 35% of all trades in simulation and
every one of the large losses. If these are the trades that go unrecorded,
the learner is trained on a record with its worst outcomes deleted.
"""

import unittest

from event_aware_trader.trade_reconcile import (
    latest_round_trip, orphaned_symbols, r_multiple)


def fill(symbol, side, qty, price, t):
    return {"symbol": symbol, "side": side, "qty": str(qty),
            "price": str(price), "transaction_time": t}


class RebuildingARoundTrip(unittest.TestCase):
    def test_a_simple_buy_and_sell(self):
        trip = latest_round_trip([
            fill("RTX", "buy", 66, 198.93, "2026-09-09T15:30:00"),
            fill("RTX", "sell", 66, 195.20, "2026-09-14T19:40:27"),
        ], "RTX")
        self.assertAlmostEqual(trip.entry_price, 198.93)
        self.assertAlmostEqual(trip.exit_price, 195.20)
        self.assertAlmostEqual(trip.quantity, 66)
        self.assertEqual(trip.closed_at, "2026-09-14T19:40:27")
        self.assertAlmostEqual(trip.realized, (195.20 - 198.93) * 66)

    def test_partial_fills_are_volume_weighted_not_averaged(self):
        # 1 share at 200 and 3 at 100 is 125, not 150.
        trip = latest_round_trip([
            fill("X", "buy", 4, 100.0, "T1"),
            fill("X", "sell", 1, 200.0, "T2"),
            fill("X", "sell", 3, 100.0, "T3"),
        ], "X")
        self.assertAlmostEqual(trip.exit_price, 125.0)
        self.assertAlmostEqual(trip.quantity, 4)
        self.assertEqual(trip.fills, 3)

    def test_only_the_latest_trip_is_returned(self):
        trip = latest_round_trip([
            fill("X", "buy", 10, 50.0, "T1"), fill("X", "sell", 10, 55.0, "T2"),
            fill("X", "buy", 10, 60.0, "T3"), fill("X", "sell", 10, 70.0, "T4"),
        ], "X")
        self.assertAlmostEqual(trip.entry_price, 60.0)
        self.assertAlmostEqual(trip.exit_price, 70.0)

    def test_a_position_still_open_is_not_a_trip(self):
        self.assertIsNone(latest_round_trip([
            fill("X", "buy", 10, 50.0, "T1"),
            fill("X", "sell", 4, 55.0, "T2"),      # partially closed only
        ], "X"))

    def test_a_sell_with_no_buy_in_the_window_is_not_guessed_at(self):
        # The entry is older than the fills feed reaches. Returning a trip
        # here would invent an entry price of zero.
        self.assertIsNone(latest_round_trip([
            fill("X", "sell", 10, 55.0, "T2")], "X"))

    def test_other_symbols_are_ignored(self):
        trip = latest_round_trip([
            fill("SGOV", "sell", 120, 100.52, "T1"),
            fill("LIN", "buy", 31, 464.97, "T2"),
            fill("SGOV", "sell", 23, 100.52, "T3"),
            fill("LIN", "sell", 31, 463.61, "T4"),
        ], "LIN")
        self.assertAlmostEqual(trip.entry_price, 464.97)
        self.assertAlmostEqual(trip.quantity, 31)

    def test_fills_are_sorted_not_trusted_in_feed_order(self):
        # The activities feed returns newest first.
        trip = latest_round_trip([
            fill("X", "sell", 10, 55.0, "2026-09-14T19:00:00"),
            fill("X", "buy", 10, 50.0, "2026-09-09T15:00:00"),
        ], "X")
        self.assertAlmostEqual(trip.entry_price, 50.0)
        self.assertAlmostEqual(trip.exit_price, 55.0)

    def test_fractional_quantities_close_cleanly(self):
        trip = latest_round_trip([
            fill("BTC/USD", "buy", 0.008801732, 77696.63, "T1"),
            fill("BTC/USD", "sell", 0.008801732, 78000.0, "T2"),
        ], "BTC/USD")
        self.assertIsNotNone(trip)
        self.assertAlmostEqual(trip.quantity, 0.008801732)

    def test_junk_rows_do_not_break_the_walk(self):
        trip = latest_round_trip([
            {"symbol": "X", "side": "buy", "qty": None, "price": "50"},
            {"symbol": "X", "side": "buy", "qty": "10", "price": "bad"},
            fill("X", "buy", 10, 50.0, "T1"),
            fill("X", "sell", 10, 55.0, "T2"),
        ], "X")
        self.assertAlmostEqual(trip.entry_price, 50.0)


class TheLabel(unittest.TestCase):
    def test_r_is_the_move_divided_by_the_risk_taken(self):
        # entry 100, stop 90 -> 10 of risk. Exiting at 115 is +1.5R.
        self.assertAlmostEqual(r_multiple(100.0, 115.0, 90.0), 1.5)
        self.assertAlmostEqual(r_multiple(100.0, 90.0, 90.0), -1.0)

    def test_a_stop_at_or_above_entry_yields_no_label(self):
        self.assertIsNone(r_multiple(100.0, 115.0, 100.0))
        self.assertIsNone(r_multiple(100.0, 115.0, 105.0))
        self.assertIsNone(r_multiple(0.0, 115.0, 90.0))

    def test_the_real_rtx_trade(self):
        # entry 198.93, initial stop 187.896, exited at 195.20
        r = r_multiple(198.93, 195.20, 187.89629030651562)
        self.assertAlmostEqual(r, (195.20 - 198.93) / (198.93 - 187.89629030651562))
        self.assertLess(r, 0)


class FindingTheOrphans(unittest.TestCase):
    def test_features_with_no_position_behind_them(self):
        self.assertEqual(
            orphaned_symbols({"RTX": {}, "LIN": {}, "COST": {}, "XHB": {}},
                             ["COST", "XHB", "BTC/USD", "SGOV"]),
            ["LIN", "RTX"])

    def test_case_is_not_a_reason_to_think_a_position_vanished(self):
        self.assertEqual(orphaned_symbols({"cost": {}}, ["COST"]), [])

    def test_nothing_held_means_everything_is_an_orphan(self):
        self.assertEqual(orphaned_symbols({"A": {}, "B": {}}, []), ["A", "B"])


if __name__ == "__main__":
    unittest.main()
