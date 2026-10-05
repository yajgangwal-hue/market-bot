"""The short-sleeve research engine: money arithmetic for a SHORT, checked on
fixtures small enough to verify by hand.

A short inverts every sign the long engine relies on - the stop is above, the
loss is a rise, a gap UP is the danger, the cover is a buy - so each of those
is pinned here before any research number is trusted.
"""

import random
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import short_sleeve_research as sr                                    # noqa: E402
from event_aware_trader.indicators import rsi, wilder_atr             # noqa: E402
from event_aware_trader.types import Bar                              # noqa: E402

D0 = date(2024, 1, 1)
NO_COST = sr.Costs(one_way_bps=0.0, rule_exit_haircut=0.0, borrow_annual=0.0,
                   dividend_annual=0.0, sec_fee_bps=0.0)


def series(rows, symbol="AAA", start=D0):
    """rows of (open, high, low, close); one session per calendar day."""
    bars = [Bar(datetime(start.year, start.month, start.day, tzinfo=timezone.utc) + timedelta(days=k),
                o, h, l, c, 10_000_000) for k, (o, h, l, c) in enumerate(rows)]
    return sr.Series.from_bars(symbol, bars)


def flat(n, price=100.0):
    return [(price, price, price, price)] * n


class IndicatorParity(unittest.TestCase):
    def test_rsi_and_atr_match_the_bots_own_functions(self):
        rng = random.Random(7)
        price, rows = 100.0, []
        for _ in range(260):
            o = price * (1 + rng.uniform(-0.01, 0.01))
            c = o * (1 + rng.uniform(-0.02, 0.02))
            rows.append((o, max(o, c) * 1.01, min(o, c) * 0.99, c))
            price = c
        s = series(rows)
        bars = [Bar(datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=k), *r, 1)
                for k, r in enumerate(rows)]
        for i in (14, 15, 60, 259):
            self.assertAlmostEqual(s.rsi[i], rsi(s.closes[:i + 1], 14), places=9)
            self.assertAlmostEqual(s.atr[i], wilder_atr(bars[:i + 1], 14), places=9)


class StepShort(unittest.TestCase):
    def trade(self, rows, costs=NO_COST, exits=sr.ShortExits(), stop=105.0, target=None):
        s = series(rows)
        t = sr.ShortTrade(symbol="AAA", entry_date=s.dates[0], exit_date=None, entry_ref=100.0,
                          entry_fill=100.0, stop=stop, target=target, quantity=10.0)
        for i in range(1, len(rows)):
            if sr.step_short(t, s, i, exits, costs):
                return t
        return t

    def test_a_falling_price_is_a_profit(self):
        t = self.trade([(100, 100, 100, 100), (99, 99, 90, 90)],
                       exits=sr.ShortExits(rsi_cover=None, max_bars=1))
        self.assertEqual(t.reason, "time_exit")
        self.assertAlmostEqual(t.gross, 100.0)           # (100 - 90) x 10

    def test_a_gap_up_through_the_stop_covers_at_the_open(self):
        costs = sr.Costs(one_way_bps=6.0, rule_exit_haircut=0.0, borrow_annual=0.0,
                         dividend_annual=0.0, sec_fee_bps=0.0)
        t = self.trade([(100, 100, 100, 100), (110, 112, 109, 111)], costs=costs)
        self.assertEqual(t.reason, "stop")
        self.assertTrue(t.gap_through)
        self.assertAlmostEqual(t.exit_fill, 110 * 1.0006)
        self.assertAlmostEqual(t.net_pct, (100 - 110 * 1.0006) / 100)

    def test_an_intraday_touch_covers_at_the_stop(self):
        t = self.trade([(100, 100, 100, 100), (101, 106, 100, 102)])
        self.assertEqual((t.reason, t.exit_fill, t.gap_through), ("stop", 105.0, False))
        self.assertAlmostEqual(t.mae, 0.05)

    def test_a_bar_spanning_stop_and_target_is_given_to_the_stop(self):
        t = self.trade([(100, 100, 100, 100), (100, 106, 98, 100)], target=99.0)
        self.assertEqual(t.reason, "stop")

    def test_a_gap_down_through_the_target_fills_at_the_open(self):
        t = self.trade([(100, 100, 100, 100), (97, 98, 96, 97)], target=99.0)
        self.assertEqual((t.reason, t.exit_fill), ("take_profit", 97))

    def test_the_target_needs_price_to_trade_through_it(self):
        t = self.trade([(100, 100, 100, 100), (100, 100.5, 98.98, 99.5)], target=99.0,
                       exits=sr.ShortExits(rsi_cover=None, max_bars=1))
        self.assertEqual(t.reason, "time_exit")           # 98.98 is not 5 bp through 99
        t = self.trade([(100, 100, 100, 100), (100, 100.5, 98.9, 99.5)], target=99.0)
        self.assertEqual((t.reason, t.exit_fill), ("take_profit", 99.0))

    def test_rule_exits_pay_the_spread_and_the_haircut_upward(self):
        costs = sr.Costs(one_way_bps=6.0, rule_exit_haircut=0.00652, borrow_annual=0.0,
                         dividend_annual=0.0, sec_fee_bps=0.0)
        t = self.trade([(100, 100, 100, 100), (99, 99.5, 98, 99)], costs=costs,
                       exits=sr.ShortExits(rsi_cover=None, max_bars=1))
        self.assertAlmostEqual(t.exit_fill, 99 * (1 + 0.0006 + 0.00652))

    def test_borrow_dividends_and_fees_are_charged_on_entry_notional_per_day(self):
        costs = sr.Costs(one_way_bps=0.0, rule_exit_haircut=0.0, borrow_annual=0.0365,
                         dividend_annual=0.073, sec_fee_bps=1.0)
        t = self.trade(flat(11), costs=costs, exits=sr.ShortExits(rsi_cover=None, max_bars=10))
        self.assertEqual(t.bars_held, 10)
        self.assertAlmostEqual(t.borrow, 1000 * 0.0365 * 10 / 365)
        self.assertAlmostEqual(t.dividends, 1000 * 0.073 * 10 / 365)
        self.assertAlmostEqual(t.fees, 1000 * 1.0 / 10_000)
        self.assertAlmostEqual(t.net, -(t.borrow + t.dividends + t.fees))


class Rule201(unittest.TestCase):
    def test_a_ten_percent_drop_blocks_that_session_and_the_next(self):
        s = series([(100, 100, 100, 100), (90, 90, 90, 90), (91, 91, 91, 91), (92, 92, 92, 92)])
        self.assertTrue(sr.rule_201_blocks(s, 1))
        self.assertTrue(sr.rule_201_blocks(s, 2))
        self.assertFalse(sr.rule_201_blocks(s, 3))


def rally_then_fall(n_warm=230):
    """Below a high 200-day average, a rally that takes RSI over 70, then a fall.
    Bars span +/-1.5%, so ATR is ~3% of price and the stop sits ~7.5% above."""
    rows = []
    for k in range(n_warm):                                           # long decline to ~81
        c = 150.0 - 0.3 * k
        rows.append((c, c * 1.015, c * 0.985, c))
    p = rows[-1][3]
    for k in range(5):                                                # rally, +2.5% a day
        p *= 1.025
        rows.append((p, p * 1.015, p * 0.985, p))
    for k in range(25):                                               # fall, -1% a day
        p *= 0.99
        rows.append((p, p * 1.015, p * 0.985, p))
    return rows


class SleeveOverlay(unittest.TestCase):
    def ctx(self, s):
        return sr.Context(s, {})

    def run_sleeve(self, s, long_value=lambda d: 0.0, signal=sr.mirror_signal, costs=NO_COST):
        spy = series(flat(len(s.closes)), symbol="SPY")
        rules = sr.SleeveRules(signal=signal, costs=costs)
        return sr.run_sleeve({"AAA": s}, sr.Context(spy, {}), rules,
                             base_equity=lambda d: 100_000.0, long_value=long_value,
                             long_holds=lambda sym, d: False, buckets={})

    def test_a_flat_market_trades_nothing_and_drifts_nowhere(self):
        result = self.run_sleeve(series(flat(300)))
        self.assertEqual(result.trades, [])
        self.assertTrue(all(v == 0.0 for _, v in result.pnl_curve))

    def test_a_failed_rally_is_shorted_and_the_fall_is_profit(self):
        result = self.run_sleeve(series(rally_then_fall()))
        self.assertTrue(result.trades)
        first = result.trades[0]
        self.assertGreater(first.net, 0)
        self.assertLessEqual(first.notional, 0.05 * 100_000 + 1e-6)

    def test_no_short_opens_when_the_long_book_uses_all_the_equity(self):
        result = self.run_sleeve(series(rally_then_fall()), long_value=lambda d: 100_000.0)
        self.assertEqual(result.trades, [])
        self.assertGreater(result.skipped_capacity, 0)

    def test_the_long_books_growth_forces_the_youngest_short_out(self):
        s = series(rally_then_fall())
        first = self.run_sleeve(s).trades[0]
        squeeze = lambda d: 100_000.0 if d > first.entry_date else 0.0
        result = self.run_sleeve(s, long_value=squeeze)
        self.assertEqual(result.trades[0].reason, "forced")
        self.assertEqual(result.forced, 1)


class LongOutcome(unittest.TestCase):
    def test_a_gap_below_the_stop_fills_at_the_open(self):
        rows = flat(230) + [(80.0, 81.0, 79.0, 80.0)]
        s = series(rows)
        s.atr[229] = 4.0                               # stop at 100 - 10 = 90
        out = sr.long_outcome(s, 229, NO_COST)
        self.assertEqual((out.reason, out.gap), ("stop", True))
        self.assertAlmostEqual(out.net_pct, -0.20)

    def test_a_tight_pair_is_stopped_first_on_an_ambiguous_bar(self):
        rows = flat(230) + [(100.0, 100.6, 99.7, 100.0)]
        s = series(rows)
        out = sr.long_outcome(s, 229, NO_COST, target_pct=0.005, stop_pct=0.002)
        self.assertEqual(out.reason, "stop")
        out = sr.long_outcome(s, 229, NO_COST, target_pct=0.005, stop_pct=0.002,
                              ambiguous_target_first=True)
        self.assertEqual(out.reason, "take_profit")


class Statistics(unittest.TestCase):
    def test_distribution_reports_what_was_asked(self):
        d = sr.distribution([0.01, -0.02, 0.03, -0.01, 0.0])
        self.assertEqual(d["n"], 5)
        self.assertAlmostEqual(d["win_rate"], 0.4)
        self.assertAlmostEqual(d["profit_factor"], 0.04 / 0.03)
        self.assertAlmostEqual(d["median"], 0.0)

    def test_account_metrics_on_a_known_curve(self):
        curve = [(date(2020, 1, 1), 100.0), (date(2020, 6, 1), 120.0),
                 (date(2020, 9, 1), 90.0), (date(2021, 1, 1), 110.0)]
        m = sr.account_metrics(curve)
        self.assertAlmostEqual(m["max_drawdown"], -0.25)
        self.assertAlmostEqual(m["total_return"], 0.10)
        self.assertAlmostEqual(m["by_year"][2020], -0.10)


if __name__ == "__main__":
    unittest.main()
