"""H-0006: idle capital in the index. The overlay must be honest first.

Three properties carry the whole result and each is pinned: the overlay
with nothing applied is the identity; the decision for day t is taken
from day t-1's close and never from day t's; and friction is charged on
every dollar that moves and on the whole balance at a regime flip.
"""

import unittest
from datetime import date, datetime, timedelta, timezone

from event_aware_trader.data import Bar
from event_aware_trader.phase5 import parking


class Report:
    def __init__(self, curve, cash):
        self.equity_curve = curve
        self.cash_curve = cash
        self.equity = curve[-1][1]
        self.trades = []
        self.starting_cash = curve[0][1]


def days(n, start=date(2020, 1, 1)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(datetime.combine(d, datetime.min.time(), timezone.utc))
        d += timedelta(days=1)
    return out


def index(closes, start=date(2020, 1, 1)):
    return [Bar(timestamp=s, open=c, high=c, low=c, close=c, volume=1e8)
            for s, c in zip(days(len(closes), start), closes)]


def flat_report(n, equity=100_000.0, cash=60_000.0):
    stamps = days(n)
    return Report([(s, equity) for s in stamps], [(s, cash) for s in stamps])


class TheOverlayIsAnIdentityWhenNothingIsApplied(unittest.TestCase):
    def test_mode_none_reproduces_the_curve_exactly(self):
        report = flat_report(300)
        out = parking.with_index_parking(report, index([100.0] * 300), "none")
        self.assertEqual([v for _, v in out.equity_curve],
                         [v for _, v in report.equity_curve])
        self.assertEqual(out.equity, report.equity)

    def test_an_unknown_mode_is_refused(self):
        with self.assertRaises(ValueError):
            parking.with_index_parking(flat_report(5), index([1] * 5), "moon")


class TheDecisionUsesYesterdaysClose(unittest.TestCase):
    """The look-ahead that would flatter this experiment, closed."""

    def test_a_crash_day_is_not_dodged_by_its_own_close(self):
        # 250 flat sessions well above the average, then one -20% day.
        # The day-before close was above the 200-day, so the balance IS in
        # the index for the crash. A version deciding on the crash day's
        # own close would step aside and show no loss.
        ramp = [100.0 + 0.01 * i for i in range(250)]
        closes = ramp + [ramp[-1] * 0.80]
        report = flat_report(251, cash=60_000.0)
        out = parking.with_index_parking(report, index(closes), "trend_cash0",
                                         cost=0.0)
        # The balance entered the index on the first strictly-above close
        # and then EARNED the ramp for fifty sessions, so it was larger
        # than the raw parked amount going into the crash. Assert the
        # property, not a hand-computed number: the crash-day loss is
        # exactly 20% of whatever stood in the index the day before.
        parked = 60_000.0 - 2_000.0 - 0.05 * 100_000.0
        before = out.equity_curve[-2][1]
        after = out.equity_curve[-1][1]
        balance_in_index = parked + (before - 100_000.0)
        self.assertGreater(balance_in_index, parked)   # it did earn the ramp
        self.assertAlmostEqual(before - after, 0.20 * balance_in_index,
                               places=2)

    def test_the_next_day_after_a_break_is_out_of_the_index(self):
        # After the crash the close sits below the 200-day, so the NEXT
        # session earns nothing even though the index rallies 10%.
        ramp = [100.0 + 0.01 * i for i in range(250)]
        closes = ramp + [ramp[-1] * 0.80, ramp[-1] * 0.88]
        report = flat_report(252, cash=60_000.0)
        out = parking.with_index_parking(report, index(closes), "trend_cash0",
                                         cost=0.0)
        before_rally = out.equity_curve[-2][1]
        after_rally = out.equity_curve[-1][1]
        self.assertAlmostEqual(after_rally, before_rally, places=2)

    def test_always_mode_stays_in_through_the_break(self):
        ramp = [100.0 + 0.01 * i for i in range(250)]
        closes = ramp + [ramp[-1] * 0.80, ramp[-1] * 0.88]
        report = flat_report(252, cash=60_000.0)
        out = parking.with_index_parking(report, index(closes), "always",
                                         cost=0.0)
        self.assertGreater(out.equity_curve[-1][1], out.equity_curve[-2][1])


class FrictionIsCharged(unittest.TestCase):
    def test_a_regime_flip_charges_the_whole_balance(self):
        ramp = [100.0 + 0.01 * i for i in range(250)]
        closes = ramp + [ramp[-1] * 0.80]
        report = flat_report(251, cash=60_000.0)
        free = parking.with_index_parking(report, index(closes), "trend_cash0",
                                          cost=0.0)
        paid = parking.with_index_parking(report, index(closes), "trend_cash0",
                                          cost=parking.INDEX_COST)
        self.assertLess(paid.equity_curve[-1][1], free.equity_curve[-1][1])
        self.assertEqual(paid.parking_switches, 2)   # into, then out

    def test_the_index_leg_is_charged_more_than_the_bill_leg(self):
        from event_aware_trader.research import PARKING_COST
        self.assertGreater(parking.INDEX_COST, PARKING_COST)

    def test_moving_cash_costs_money_even_without_a_flip(self):
        stamps = days(260)
        cash = [(s, 60_000.0 if i % 2 else 30_000.0)
                for i, s in enumerate(stamps)]
        report = Report([(s, 100_000.0) for s in stamps], cash)
        out = parking.with_index_parking(report, index([100.0] * 260), "always",
                                         cost=parking.INDEX_COST)
        self.assertLess(out.equity_curve[-1][1], 100_000.0)


class TheStrategyLegIsUntouched(unittest.TestCase):
    def test_trades_are_not_modified(self):
        report = flat_report(300)
        report.trades = ["a", "b"]
        out = parking.with_index_parking(report, index([100.0] * 300), "always")
        self.assertIs(out.trades, report.trades)

    def test_the_two_hundred_day_constant_is_the_strategys_own(self):
        from event_aware_trader.mean_reversion import MeanReversionConfig
        self.assertEqual(parking.TREND_DAYS, MeanReversionConfig().trend_ma_days)


class TheRegistrationSaysWhatItMustSay(unittest.TestCase):
    def setUp(self):
        from event_aware_trader.modelgov import prereg
        rows = [p for p in prereg.load() if p["hypothesis_id"] == "H-0006"]
        if not rows:
            self.skipTest("H-0006 not registered yet")
        self.h = rows[0]

    def test_three_configurations_one_family_with_a_control(self):
        self.assertEqual(self.h["max_configurations"], 3)
        self.assertIn("ONE family", self.h["parameters"]["family_rule"])
        self.assertIn("control", self.h["parameters"]["family_rule"].lower())

    def test_the_author_declared_the_expected_failure(self):
        self.assertIn("drawdown clause", self.h["statement"])
        self.assertIn("fail", self.h["statement"])

    def test_spy_comparison_is_required(self):
        self.assertIn("against SPY", self.h["primary_metric"])

    def test_the_thirty_year_window_is_not_touched(self):
        self.assertIn("not touched", self.h["required_oos_test"])

    def test_promotion_is_named_as_a_production_change(self):
        self.assertTrue(any("PRODUCTION change" in p
                            for p in self.h["promotion_requirements"]))


if __name__ == "__main__":
    unittest.main()
