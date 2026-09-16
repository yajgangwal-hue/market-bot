"""P3. The exit-timing haircut: an uncertainty adjustment, not a price.

The simulator prices rule exits at the day's close. The live bot sells the
moment the rule fires, on whichever 15-minute cycle that is. Measured on 155
real exits against 5-minute bars, the close exceeded the trigger price by
0.652% / 0.289% / 0.120% for a 10:00 / 12:30 / 15:00 trigger. So every
figure this simulator has produced assumed a fill the bot does not get.

On daily bars the trigger price does not exist and cannot be reconstructed.
The haircut therefore CHARGES the measured difference rather than modelling
it. These tests pin what it may and may not touch.

A note on G7, which said "the trade list is identical; only prices move".
That was too strict, and the golden master proved it: quantity moves too.
Not because the haircut touches sizing, but because lower exit prices mean
lower equity, and the next position is 0.5% of a smaller number. The
invariant that actually matters is that the haircut changes no DECISION -
which trades, on which days, for which reason - and the tests below assert
exactly that instead.
"""

import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.data import Bar
from event_aware_trader.portfolio import run_portfolio
from event_aware_trader.research import PRODUCTION_CANDIDATE
from event_aware_trader.risk import CostModel, RiskPolicy

START = datetime(2024, 1, 2, tzinfo=timezone.utc)
HAIRCUT = 0.00652


def oversold_in_an_uptrend(rally_to=None, dip_days=6, dip_pct=0.08):
    up = [100.0 + i * 0.25 for i in range(250)]
    top = up[-1]
    closes = up + [top * (1 - dip_pct * (j + 1) / dip_days)
                   for j in range(dip_days)]
    if rally_to is not None:
        closes = closes + [rally_to]
    return [Bar(timestamp=START + timedelta(days=i), open=c, high=c,
                low=c * 0.995, close=c, volume=3_000_000)
            for i, c in enumerate(closes)]


def run(series, **kw):
    return run_portfolio(series, starting_cash=100_000.0, policy=RiskPolicy(),
                         costs=CostModel(), entry_rule="mean_reversion",
                         entry_fill="signal_close", **kw)


class WhatTheHaircutTouches(unittest.TestCase):
    def setUp(self):
        self.series = {"AAA": oversold_in_an_uptrend(rally_to=260.0)}
        self.plain = run(self.series)
        self.cut = run(self.series, rule_exit_timing_haircut=HAIRCUT)

    def test_the_default_is_inert(self):
        again = run(self.series, rule_exit_timing_haircut=0.0)
        self.assertEqual([t.exit_price for t in again.trades],
                         [t.exit_price for t in self.plain.trades])

    def test_it_changes_no_decision(self):
        """The invariant that matters: same trades, same days, same reasons."""
        decisions = lambda r: [(t.symbol, t.entry_time.date(),
                                t.exit_time.date(), t.exit_reason)
                               for t in r.trades]
        self.assertEqual(decisions(self.cut), decisions(self.plain))

    def test_it_lowers_rule_exit_prices_by_exactly_the_haircut(self):
        pairs = [(a, b) for a, b in zip(self.plain.trades, self.cut.trades)
                 if a.exit_reason in ("reverted", "time_exit")]
        self.assertTrue(pairs, "fixture must produce a rule exit")
        for plain, cut in pairs:
            self.assertAlmostEqual(cut.exit_price / plain.exit_price,
                                   1.0 - HAIRCUT, places=6)

    def test_it_never_raises_a_price(self):
        for plain, cut in zip(self.plain.trades, self.cut.trades):
            self.assertLessEqual(cut.exit_price, plain.exit_price + 1e-9)

    def test_the_result_is_worse_which_is_the_point(self):
        self.assertLess(self.cut.equity, self.plain.equity)


class WhatItMustNotTouch(unittest.TestCase):
    def test_a_stop_exit_is_untouched(self):
        """A stop's fill is not a choice - measured upside per share: 0.00."""
        series = {"AAA": oversold_in_an_uptrend(dip_pct=0.30, dip_days=10)}
        plain = run(series)
        cut = run(series, rule_exit_timing_haircut=HAIRCUT)
        stops_plain = [t.exit_price for t in plain.trades if t.exit_reason == "stop"]
        stops_cut = [t.exit_price for t in cut.trades if t.exit_reason == "stop"]
        self.assertTrue(stops_plain, "fixture must produce a stop exit")
        self.assertEqual(stops_cut, stops_plain)

    def test_a_take_profit_is_untouched(self):
        """A limit fills at its level or better; timing does not apply."""
        series = {"AAA": oversold_in_an_uptrend(rally_to=260.0)}
        plain = run(series, mr_take_profit_r=1.0)
        cut = run(series, mr_take_profit_r=1.0, rule_exit_timing_haircut=HAIRCUT)
        tp_plain = [t.exit_price for t in plain.trades if t.exit_reason == "take_profit"]
        tp_cut = [t.exit_price for t in cut.trades if t.exit_reason == "take_profit"]
        self.assertTrue(tp_plain, "fixture must produce a take profit")
        self.assertEqual(tp_cut, tp_plain)


class TheProductionCandidateCarriesIt(unittest.TestCase):
    def test_the_candidate_uses_the_worst_measured_case(self):
        self.assertAlmostEqual(
            PRODUCTION_CANDIDATE["rule_exit_timing_haircut"], 0.00652)

    def test_it_is_the_worst_of_the_three_measured_values(self):
        # 0.652 / 0.289 / 0.120 for a 10:00 / 12:30 / 15:00 trigger. The
        # live distribution is UNVERIFIED, so the conservative bound is used
        # deliberately. If someone lowers this, it must be because the
        # distribution was measured - not because the number looked better.
        self.assertEqual(
            max(0.00652, 0.00289, 0.00120),
            PRODUCTION_CANDIDATE["rule_exit_timing_haircut"])


if __name__ == "__main__":
    unittest.main()
