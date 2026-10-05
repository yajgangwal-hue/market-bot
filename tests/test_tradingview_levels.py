"""The generated TradingView indicator must draw the exits the bot ACTUALLY has.

Since EXP-0055 (sessions from 2026-09-29) that includes a take profit. The
properties under test:

- every level on the chart is the level the bot acts on: the stop it
  recorded, and the take profit its own `_take_profit_for` sets - read from
  state when remembered, computed by that same function on a copy of state
  when not, and never written back by this script;
- the take profit is labelled for what it is: a level the bot checks every
  cycle, NOT an order resting at the broker;
- the holding count uses the entry day the bot recorded, as the bot does;
- expected returns appear only for the exit levels they were measured for;
- an entry price is never invented: without the broker or a snapshot of it,
  a position is not drawn (the old offline mode drew every entry at 0.0).
"""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import tradingview_levels as tv                                    # noqa: E402
from tradingview_levels import (entry_day, expected_for, pine_for,  # noqa: E402
                                positions_and_stops, snapshot_holdings,
                                write_snapshot)

ROWS = [{"symbol": "RTX", "entry": 199.28, "stop": 198.3111, "take_profit": 200.2489,
         "shares": 66.0, "opened_at": "2026-09-08T19:30:00+00:00"}]

EXPECTED = {"take_profit_first": 0.431, "stop_first": 0.317, "other_exit": 0.252,
            "mean_r_conservative": 0.0129, "mean_r_simulated": 0.0786,
            "account_cagr_conservative_pct": 3.2, "account_cagr_simulated_pct": 5.54,
            "spy_total_return_cagr_pct": 15.0}


def pine(rows=ROWS, expected=EXPECTED, take_atr=2.5):
    return pine_for(rows, 60.0, 14, 20, expected=expected, take_atr=take_atr,
                    generated="2026-09-28 20:00")


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.pine = pine()

    def test_the_stop_price_is_present_and_exact(self):
        self.assertIn("stopPrice  := 198.3111", self.pine)

    def test_the_entry_price_is_present(self):
        self.assertIn("entryPrice := 199.2800", self.pine)

    def test_the_take_profit_is_present_and_exact(self):
        self.assertIn("takePrice  := 200.2489", self.pine)

    def test_the_share_count_is_present_for_the_money_at_stake(self):
        self.assertIn("shares     := 66.0", self.pine)

    def test_it_says_where_the_take_profit_lives(self):
        """EXP-0056 rests it at the broker beside the stop (one OCO order);
        without that, a broker panel shows the stop and never this level, and
        a reader must be told why it is absent."""
        self.assertIn("NOT an order at the broker", self.pine)
        self.assertIn("every 15 minutes", self.pine)
        at_broker = pine_for(ROWS, 60.0, 14, 20, expected=EXPECTED, take_atr=2.5,
                             generated="2026-10-04 20:00", take_at_broker=True)
        self.assertIn("RESTS AT THE BROKER", at_broker)
        self.assertNotIn("NOT an order at the broker", at_broker)
        self.assertNotIn("{", at_broker)

    def test_the_live_generator_reads_the_switch_from_the_bots_own_config(self):
        self.assertTrue(tv.live_adaptive_config().take_profit_at_broker)

    def test_the_zones_span_the_real_levels(self):
        self.assertIn("box.new(left, entryPrice, right, stopPrice", self.pine)
        self.assertIn("box.new(left, takePrice, right, entryPrice", self.pine)

    def test_a_take_profit_line_and_label_are_drawn(self):
        self.assertIn("takeLine := line.new(left, takePrice, right, takePrice", self.pine)
        self.assertIn('"TAKE PROFIT  "', self.pine)

    def test_the_rsi_is_the_daily_one_whatever_the_chart(self):
        self.assertIn('request.security(syminfo.tickerid, "D", ta.rsi(close, rsiLen))',
                      self.pine)

    def test_the_holding_count_uses_the_recorded_entry_day(self):
        self.assertIn("entryDay   := 20260908", self.pine)
        self.assertIn("dateKey[i] > entryDay", self.pine)

    def test_the_table_does_not_collide_with_the_box_namespace(self):
        self.assertIn("var table panel = table.new(", self.pine)
        self.assertNotIn("table.cell(box,", self.pine)

    def test_no_template_brace_survives_into_the_pine(self):
        """A Python format field left unfilled is a Pine compile error."""
        self.assertNotIn("{", self.pine)
        self.assertNotIn("}", self.pine)

    def test_brackets_balance(self):
        self.assertEqual(self.pine.count("("), self.pine.count(")"))
        self.assertEqual(self.pine.count("["), self.pine.count("]"))
        self.assertEqual(self.pine.count('"') % 2, 0)

    def test_the_rule_constants_come_from_the_shipped_config(self):
        """A chart showing 55 while the bot exits at 60 is a lie."""
        from event_aware_trader.mean_reversion import MeanReversionConfig
        config = MeanReversionConfig()
        generated = pine_for(ROWS, config.rsi_exit, config.rsi_period,
                             config.max_holding_bars)
        self.assertIn('input.float({0}'.format(config.rsi_exit), generated)
        self.assertIn('input.int({0},'.format(config.max_holding_bars), generated)

    def test_the_expected_figures_are_baked_in_when_known(self):
        self.assertIn("EXP_KNOWN  = true", self.pine)
        self.assertIn("EXP_TP     = 0.4310", self.pine)
        self.assertIn("EXP_R_SIM  = 0.0786", self.pine)
        self.assertIn("SPY_TR     = 15.00", self.pine)

    def test_unknown_expected_figures_say_so(self):
        text = pine(expected=None)
        self.assertIn("EXP_KNOWN  = false", text)
        self.assertIn('"not measured"', text)

    def test_the_conservative_figure_is_derived_per_position(self):
        """The take-profit sale is charged the rule-exit haircut in dollars,
        so a narrow stop pays more of its R than a wide one."""
        self.assertIn("EXP_TP * HAIRCUT * takePrice * shares", self.pine)

    def test_with_adaptive_exits_off_no_take_profit_is_drawn(self):
        rows = [dict(ROWS[0], take_profit=None)]
        text = pine(rows=rows, take_atr=None)
        self.assertIn("takePrice  := 0.0000", text)
        self.assertIn("none - adaptive exits are switched off", text)


class EntryDayTests(unittest.TestCase):
    def test_the_date_the_stamp_carries(self):
        self.assertEqual(entry_day("2026-09-21T04:00:00+00:00"), 20260921)
        self.assertEqual(entry_day("2026-09-21T19:30:00Z"), 20260921)

    def test_unreadable_or_missing_is_zero(self):
        self.assertEqual(entry_day(""), 0)
        self.assertEqual(entry_day("not a date"), 0)


class SymbolSpellingTests(unittest.TestCase):
    def test_a_share_class_is_spelled_the_tradingview_way(self):
        """This project says BRK-B; TradingView says BRK.B."""
        rows = [{"symbol": "BRK-B", "entry": 100.0, "stop": 95.0, "opened_at": ""}]
        self.assertIn('sym == "BRK.B"', pine(rows=rows))

    def test_a_crypto_pair_loses_its_slash(self):
        rows = [{"symbol": "BTC/USD", "entry": 100.0, "stop": 95.0, "opened_at": ""}]
        self.assertIn('sym == "BTCUSD"', pine(rows=rows))


class AtrMode:
    """EXP-0055/56's fixed 2.5-ATR target, which take_profit_mode='atr' keeps.
    The bounce price (EXP-0057, the default) is pinned in BounceLevels below."""

    def setUp(self):
        self._mode = tv.live_take_profit_mode
        tv.live_take_profit_mode = lambda: "atr"
        super().setUp()

    def tearDown(self):
        tv.live_take_profit_mode = self._mode
        super().tearDown()


class LevelsTheBotUses(AtrMode, unittest.TestCase):
    """Offline, through a snapshot, so nothing reaches a broker."""

    def setUp(self):
        super().setUp()
        self.tmp = TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.state = self.dir / "autotrade-state.json"
        self.snapshot = self.dir / "tradingview-levels.json"
        write_snapshot([{"symbol": "TJX", "entry": 100.0, "shares": 151.0}],
                       self.snapshot, "2026-09-28 20:00")

    def tearDown(self):
        self.tmp.cleanup()
        super().tearDown()

    def remember(self, **extra):
        stop = {"initial": 92.0, "current": 92.0,
                "opened_at_ts": "2026-09-21T04:00:00+00:00"}
        stop.update(extra)
        self.state.write_text(json.dumps({"stops": {"TJX": stop}}), encoding="utf-8")

    def rows(self):
        return positions_and_stops(self.state, use_broker=False, snapshot=self.snapshot)

    def test_a_position_without_a_remembered_level_gets_the_bots_own(self):
        """Entry 100 behind a stop at 92: ATR (100 - 92) / 2.5 = 3.2, so the
        2.5-ATR take profit sits at 108.0 - what _take_profit_for sets."""
        self.remember()
        [row] = self.rows()
        self.assertAlmostEqual(row["take_profit"], 108.0)
        self.assertEqual(row["shares"], 151.0)

    def test_a_remembered_level_is_used_as_it_is(self):
        self.remember(take_profit=105.0)
        [row] = self.rows()
        self.assertAlmostEqual(row["take_profit"], 105.0)

    def test_a_learned_multiple_is_used(self):
        self.remember()
        (self.dir / "adaptive-exits.json").write_text(
            json.dumps({"take_profit_atr": 3.0, "stop_atr": 2.5}), encoding="utf-8")
        [row] = self.rows()
        self.assertAlmostEqual(row["take_profit"], 100.0 + 3.0 * 3.2)

    def test_the_state_file_is_never_written(self):
        self.remember()
        before = self.state.read_bytes()
        self.rows()
        self.assertEqual(self.state.read_bytes(), before)

    def test_a_snapshot_symbol_the_bot_no_longer_remembers_is_not_drawn(self):
        self.state.write_text(json.dumps({"stops": {}}), encoding="utf-8")
        self.assertEqual(self.rows(), [])

    def test_with_adaptive_exits_off_there_is_no_take_profit(self):
        self.remember()
        original = tv.live_adaptive_config
        tv.live_adaptive_config = lambda: None
        try:
            [row] = self.rows()
        finally:
            tv.live_adaptive_config = original
        self.assertIsNone(row["take_profit"])

    def test_the_broker_path_reads_fills_from_the_broker(self):
        self.remember()
        original = tv.broker_holdings
        tv.broker_holdings = lambda: {"TJX": (101.0, 10.0)}
        try:
            [row] = positions_and_stops(self.state, use_broker=True, snapshot=self.snapshot)
        finally:
            tv.broker_holdings = original
        self.assertEqual((row["entry"], row["shares"]), (101.0, 10.0))
        self.assertAlmostEqual(row["take_profit"], 101.0 + 2.5 * (101.0 - 92.0) / 2.5)


class SnapshotTests(unittest.TestCase):
    def test_no_snapshot_means_no_rows_rather_than_an_entry_of_zero(self):
        with TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            state.write_text(json.dumps({"stops": {"TJX": {"initial": 92.0}}}),
                             encoding="utf-8")
            self.assertEqual(positions_and_stops(state, use_broker=False,
                                                 snapshot=Path(tmp) / "absent.json"), [])

    def test_a_snapshot_round_trips(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "snap.json"
            write_snapshot([{"symbol": "TJX", "entry": 100.5, "shares": 3.0}], path,
                           "2026-09-28 20:00")
            held, taken = snapshot_holdings(path)
            self.assertEqual(held, {"TJX": (100.5, 3.0)})
            self.assertEqual(taken, "2026-09-28 20:00")


class ExpectedForTests(AtrMode, unittest.TestCase):
    RECORD = {"take_profit_atr": 2.5, "stop_atr": 2.5, "chart": EXPECTED}

    def test_the_bounce_exit_shows_no_figures_measured_for_the_fixed_target(self):
        tv.live_take_profit_mode = lambda: "bounce"
        self.assertIsNone(expected_for(self.RECORD, 2.5, 2.5))
        self.assertIsNone(expected_for(tv.load_expected(), 2.5, 2.5))

    def test_matching_multiples_give_the_figures(self):
        self.assertEqual(expected_for(self.RECORD, 2.5, 2.5)["take_profit_first"], 0.431)

    def test_other_multiples_give_nothing(self):
        self.assertIsNone(expected_for(self.RECORD, 3.0, 2.5))
        self.assertIsNone(expected_for(self.RECORD, 2.5, 2.75))

    def test_no_record_or_no_take_profit_gives_nothing(self):
        self.assertIsNone(expected_for(None, 2.5, 2.5))
        self.assertIsNone(expected_for(self.RECORD, None, None))

    def test_the_shipped_record_matches_the_shipped_multiples(self):
        """The record committed beside the generator describes the exits the
        bot starts with; if it did not, the chart would say 'not measured'."""
        from event_aware_trader.adaptive_exits import AdaptiveExitConfig
        config = AdaptiveExitConfig()
        record = tv.load_expected()
        self.assertIsNotNone(expected_for(record, config.initial_take_profit_atr,
                                          config.initial_stop_atr))


class EmptyStateTests(unittest.TestCase):
    def test_holding_nothing_still_produces_a_valid_script(self):
        text = pine(rows=[])
        self.assertIn("holds nothing right now", text)
        self.assertIn("indicator(", text)

    def test_a_position_with_no_recorded_stop_is_skipped(self):
        """Better absent than drawn at a level nobody chose."""
        with TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            state.write_text(json.dumps({"stops": {}}), encoding="utf-8")
            self.assertEqual(positions_and_stops(state, use_broker=False,
                                                 snapshot=Path(tmp) / "none.json"), [])

    def test_a_missing_state_file_is_not_an_error(self):
        with TemporaryDirectory() as tmp:
            rows = positions_and_stops(Path(tmp) / "absent.json", use_broker=False,
                                       snapshot=Path(tmp) / "none.json")
            self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()


class BounceLevels(unittest.TestCase):
    """EXP-0057: the chart draws the session's bounce price, from the same local
    price file the bot reads, even for a position the bot has not yet looked at."""

    def setUp(self):
        import event_aware_trader.autotrade as autotrade
        from event_aware_trader.types import Bar
        from datetime import datetime, timedelta, timezone
        self.autotrade = autotrade
        self._daily = autotrade.daily_bars
        self._mode = tv.live_take_profit_mode
        tv.live_take_profit_mode = lambda: "bounce"
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.closes = [100.0 + (i % 7) - 0.15 * i for i in range(60)]
        bars = [Bar(timestamp=start + timedelta(days=i), open=c, high=c, low=c, close=c,
                    volume=1.0) for i, c in enumerate(self.closes)]
        autotrade.daily_bars = lambda symbol, *a, **k: bars
        self.tmp = TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.state = self.dir / "autotrade-state.json"
        self.snapshot = self.dir / "tradingview-levels.json"
        write_snapshot([{"symbol": "TJX", "entry": 100.0, "shares": 151.0}],
                       self.snapshot, "2026-10-04 20:00")

    def tearDown(self):
        self.autotrade.daily_bars = self._daily
        tv.live_take_profit_mode = self._mode
        self.tmp.cleanup()

    def test_a_new_position_is_drawn_at_the_bounce_price(self):
        from event_aware_trader.indicators import bounce_price, rsi
        self.state.write_text(json.dumps({"stops": {"TJX": {
            "initial": 92.0, "current": 92.0, "opened_at_ts": "2026-09-21T19:45:00+00:00"}}}),
            encoding="utf-8")
        [row] = positions_and_stops(self.state, use_broker=False, snapshot=self.snapshot)
        self.assertAlmostEqual(row["take_profit"], bounce_price(self.closes))
        self.assertAlmostEqual(rsi(self.closes + [row["take_profit"]]), 60.0, places=9)

    def test_a_stale_fixed_target_on_file_is_not_drawn(self):
        self.state.write_text(json.dumps({"stops": {"TJX": {
            "initial": 92.0, "current": 92.0, "take_profit": 108.0,
            "opened_at_ts": "2026-09-21T19:45:00+00:00"}}}), encoding="utf-8")
        [row] = positions_and_stops(self.state, use_broker=False, snapshot=self.snapshot)
        self.assertNotAlmostEqual(row["take_profit"], 108.0)

    def test_the_chart_says_where_the_level_comes_from(self):
        text = pine_for([], 60.0, 14, 20, take_atr=2.5, generated="2026-10-04 20:00")
        self.assertIn("bounce price", text)
        self.assertIn("EXP-0057", text)
