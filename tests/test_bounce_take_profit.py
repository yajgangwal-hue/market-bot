"""EXP-0057: the take profit sits at the bounce price, and entries are stamped
with the moment they were made.

The bounce price is the close that would put RSI(14) at 60 - where the frozen
rule's own exit fires - computed from the COMPLETED sessions and rested at the
broker as the limit half of the OCO. Pinned here:

- an open position rests at the session's bounce price, remembered for the
  chart, from completed sessions only (today's forming bar is not used);
- the next session moves the order exactly once, and a second cycle in the
  same session leaves it alone (no churn);
- a fixed EXP-0055 target already on file is replaced, never kept;
- at or above the bounce price the position is SOLD, and no sell limit is
  ever rested at or below the market;
- a new entry carries no fixed target, logs its stop multiple, and is
  stamped with the broker's clock, not yesterday's bar;
- the holding cap fires on the 20th session after the entry date (C-16);
- the learner replays trades with the bounce price as the target and steps
  only the stop.

Driven through run_once wherever the money path is involved.
"""

import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import event_aware_trader.autotrade as autotrade
from event_aware_trader.adaptive_exits import (
    AdaptiveExitConfig, _neighbours, replay)
from event_aware_trader.autotrade import AutoTradeConfig, _broker_take_profit, _entry_stamp
from event_aware_trader.broker import round_price
from event_aware_trader.indicators import bounce_price, rsi
from event_aware_trader.types import Bar
from fake_broker import FakeBroker
from tests.test_adaptive_exits_live import (
    ENTRY, STOP, SYMBOL, Harness, _bars, _quiet)
from tests.test_broker_take_profit import _position
from tests.test_take_profit import oversold_in_an_uptrend

BOUNCE = AdaptiveExitConfig()          # the shipped default


def _closes(series):
    return [b.close for b in series]


class BouncePrice(unittest.TestCase):
    def test_it_is_exactly_where_rsi_reaches_the_threshold(self):
        closes = _closes(_quiet())
        level = bounce_price(closes)
        self.assertAlmostEqual(rsi(closes + [level]), 60.0, places=9)
        self.assertGreaterEqual(rsi(closes + [level + 0.01]), 60.0)
        self.assertLess(rsi(closes + [level - 0.01]), 60.0)

    def test_short_history_and_bad_thresholds(self):
        self.assertIsNone(bounce_price([100.0] * 14))
        with self.assertRaises(ValueError):
            bounce_price([100.0] * 30, threshold=100.0)

    def test_the_mode_is_validated(self):
        with self.assertRaises(ValueError):
            AdaptiveExitConfig(take_profit_mode="somewhere")
        self.assertEqual(BOUNCE.take_profit_mode, "bounce")


class BounceTakeProfitInTheLiveLoop(Harness, unittest.TestCase):
    def cycle(self, broker, series=None, **overrides):
        overrides.setdefault("retry_backoff_seconds", 0.0)
        overrides.setdefault("adaptive_exits", BOUNCE)
        return self.run_cycle(self.config(**overrides), broker, series or _quiet())

    def test_an_open_position_rests_at_the_sessions_bounce_price(self):
        broker = _position()
        self.cycle(broker)
        level = bounce_price(_closes(_quiet()))
        [(symbol, quantity, stop, take, dry)] = broker.protective_oco
        self.assertEqual((symbol, quantity, dry), (SYMBOL, 151.0, False))
        self.assertAlmostEqual(stop, STOP)
        self.assertAlmostEqual(take, round_price(level))
        remembered = self.state()["stops"][SYMBOL]
        self.assertAlmostEqual(remembered["take_profit"], level)
        self.assertEqual(remembered["take_profit_mode"], "bounce")
        [hold] = self.audit("hold")
        self.assertAlmostEqual(hold["take_profit"], round(level, 4))

    def test_the_level_uses_completed_sessions_only(self):
        series = _quiet()
        last = series[-1]
        today = Bar(timestamp=last.timestamp + timedelta(days=1), open=last.close,
                    high=last.close * 1.004, low=last.close * 0.999,
                    close=last.close * 1.003, volume=5_000_000)
        autotrade._todays_bars = lambda config, symbols: {SYMBOL: today}
        broker = _position()
        self.cycle(broker, series)
        self.assertAlmostEqual(self.state()["stops"][SYMBOL]["take_profit"],
                               bounce_price(_closes(series)))

    def test_the_next_session_moves_the_order_once_and_only_once(self):
        series = _quiet()
        broker = _position()
        self.cycle(broker, series)
        first = broker.protective_oco[-1][3]
        nxt = series + [Bar(timestamp=series[-1].timestamp + timedelta(days=1),
                            open=series[-1].close, high=series[-1].close * 1.002,
                            low=series[-1].close * 0.996, close=series[-1].close * 0.997,
                            volume=5_000_000)]
        self.cycle(broker, nxt)
        second = broker.protective_oco[-1][3]
        self.assertEqual(len(broker.protective_oco), 2)
        self.assertNotAlmostEqual(first, second)
        self.assertAlmostEqual(second, round_price(bounce_price(_closes(nxt))))
        submitted, canceled = len(broker.protective_oco), len(broker.canceled)
        self.cycle(broker, nxt)                       # same session again
        self.assertEqual((len(broker.protective_oco), len(broker.canceled)),
                         (submitted, canceled))

    def test_a_fixed_target_on_file_is_replaced(self):
        broker = _position()
        self.cycle(broker, stop_state={"take_profit": 108.0, "take_profit_atr": 2.5})
        remembered = self.state()["stops"][SYMBOL]
        self.assertAlmostEqual(remembered["take_profit"], bounce_price(_closes(_quiet())))
        self.assertNotAlmostEqual(broker.protective_oco[-1][3], 108.0)

    def test_at_or_above_the_bounce_price_it_is_sold_not_given_a_marketable_limit(self):
        level = bounce_price(_closes(_quiet()))
        broker = _position(mark=level + 0.5)
        self.cycle(broker)
        self.assertIn((SYMBOL, False), broker.closed)
        [exit_] = self.audit("exit")
        self.assertEqual(exit_["exit_reason"], "take_profit")
        self.assertEqual(getattr(broker, "protective_oco", []), [])   # none was ever sent

    def test_the_broker_never_gets_a_limit_at_or_below_the_mark(self):
        config = AutoTradeConfig(entry_rule="mean_reversion", adaptive_exits=BOUNCE)
        remembered = {"take_profit": 105.0}
        self.assertEqual(_broker_take_profit(config, {}, remembered, SYMBOL, 92.0, 101.0), 105.0)
        self.assertIsNone(_broker_take_profit(config, {}, remembered, SYMBOL, 92.0, 105.0))
        self.assertIsNone(_broker_take_profit(config, {}, remembered, SYMBOL, 92.0, 106.0))
        self.assertIsNone(_broker_take_profit(config, {}, remembered, SYMBOL, 106.0, 101.0))

    def test_the_holding_cap_fires_on_the_twentieth_session_after_the_entry_date(self):
        series = _quiet()
        on_day = lambda i: series[i].timestamp.date().isoformat() + "T19:45:00+00:00"
        broker = _position()
        self.cycle(broker, series, stop_state={"opened_at_ts": on_day(len(series) - 20)})
        self.assertEqual(self.audit("exit"), [])            # 19 sessions after
        self.tearDown(); self.setUp()
        broker = _position()
        self.cycle(broker, series, stop_state={"opened_at_ts": on_day(len(series) - 21)})
        [exit_] = self.audit("exit")                         # the 20th
        self.assertEqual(exit_["exit_reason"], "time")


class ANewEntryInBounceMode(Harness, unittest.TestCase):
    def enter(self):
        state = self.dir / "state.json"
        state.write_text("{}", encoding="utf-8")
        config = AutoTradeConfig(dry_run=True, universe=(SYMBOL,), asset_class="equity",
                                 adaptive_exits=BOUNCE, entry_rule="mean_reversion",
                                 cash_parking_symbol=None, reserved_fraction=0.0,
                                 require_market_open=True, entry_window_minutes=None,
                                 model_file=None, live_model_file=None,
                                 audit_log=self.dir / "audit.jsonl", state_file=state)
        broker = FakeBroker(equity=100_000.0, market_open=True)
        self.run_cycle(config, broker, oversold_in_an_uptrend())
        [entry] = self.audit("entry")
        return entry, self.state()["stops"][SYMBOL], broker

    def test_no_fixed_target_and_the_stop_multiple_is_logged(self):
        entry, remembered, broker = self.enter()
        self.assertTrue(broker.submitted)
        self.assertIsNone(entry["take_profit"])
        self.assertEqual(entry["take_profit_mode"], "bounce")
        self.assertEqual(entry["stop_atr"], 2.5)
        self.assertNotIn("take_profit", remembered)
        self.assertEqual(remembered["take_profit_mode"], "bounce")

    def test_the_entry_is_stamped_with_the_brokers_clock_not_yesterdays_bar(self):
        entry, remembered, _ = self.enter()
        self.assertEqual(remembered["opened_at_ts"], "2026-09-01T14:00:00+00:00")
        last_bar = oversold_in_an_uptrend()[-1].timestamp.isoformat()
        self.assertNotEqual(remembered["opened_at_ts"], last_bar)


class EntryStamp(unittest.TestCase):
    def test_the_brokers_clock_in_utc(self):
        self.assertEqual(_entry_stamp({"timestamp": "2026-10-05T15:45:12.123-04:00"}),
                         "2026-10-05T19:45:12+00:00")

    def test_without_a_clock_this_machines_time(self):
        before = datetime.now(timezone.utc).date().isoformat()
        stamp = _entry_stamp(None)
        self.assertTrue(stamp.startswith(before) or stamp > before)
        self.assertTrue(stamp.endswith("+00:00"))

    def test_an_unreadable_clock_falls_back(self):
        self.assertTrue(_entry_stamp({"timestamp": "not a time"}).endswith("+00:00"))


class LearnerInBounceMode(unittest.TestCase):
    RULE = SimpleNamespace(max_holding_bars=20, rsi_period=14, rsi_exit=60.0,
                           stop_atr_multiple=2.5)

    def test_only_the_stop_has_neighbours(self):
        self.assertEqual(_neighbours(2.5, 2.5, BOUNCE), [(2.5, 2.25), (2.5, 2.75)])
        self.assertEqual(len(_neighbours(2.5, 2.5, AdaptiveExitConfig(take_profit_mode="atr"))), 4)

    def test_replay_sells_at_the_sessions_bounce_price(self):
        history = _closes(_quiet())
        level = bounce_price(history)
        entry, atr = history[-1], 1.0
        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        after = [Bar(timestamp=start, open=entry, high=level + 1.0, low=entry - 0.2,
                     close=entry, volume=1.0)]
        after += [Bar(timestamp=start + timedelta(days=d), open=entry, high=entry,
                      low=entry, close=entry, volume=1.0) for d in range(1, 20)]
        price, reason = replay(after, history, entry, atr, 2.5, 2.5, self.RULE, bounce=True)
        self.assertEqual(reason, "take_profit")
        self.assertAlmostEqual(price, level)
        fixed, why = replay(after, history, entry, atr, 2.5, 2.5, self.RULE, bounce=False)
        self.assertAlmostEqual(fixed, entry + 2.5 * atr)
        self.assertEqual(why, "take_profit")


if __name__ == "__main__":
    unittest.main()


class TheEmulatorSwitch(unittest.TestCase):
    """portfolio.run_portfolio(mr_take_profit_bounce=True): RESEARCH ONLY, off by default."""

    def run_(self, series, **kw):
        from event_aware_trader.portfolio import run_portfolio
        from event_aware_trader.risk import CostModel, RiskPolicy
        return run_portfolio({"AAA": series}, starting_cash=100_000.0, policy=RiskPolicy(),
                             costs=CostModel(), entry_rule="mean_reversion",
                             entry_fill="signal_close", **kw)

    def test_off_by_default(self):
        series = oversold_in_an_uptrend(rally_to=260.0, peak=260.0, gap_open=150.0)
        plain = self.run_(series)
        off = self.run_(series, mr_take_profit_bounce=False)
        self.assertEqual([(t.exit_reason, t.exit_price) for t in plain.trades],
                         [(t.exit_reason, t.exit_price) for t in off.trades])

    def test_it_sells_at_the_bounce_price_of_the_session(self):
        from event_aware_trader.risk import CostModel
        series = oversold_in_an_uptrend(rally_to=260.0, peak=260.0, gap_open=150.0)
        report = self.run_(series, mr_take_profit_bounce=True)
        [trade] = [t for t in report.trades if t.exit_reason == "take_profit"]
        index = next(i for i, b in enumerate(series) if b.timestamp == trade.exit_time)
        level = bounce_price([b.close for b in series[:index]])
        bar = series[index]
        raw = bar.open if bar.open >= level else level
        self.assertAlmostEqual(trade.exit_price, CostModel().sell_fill(raw))

    def test_it_replaces_every_other_take_profit(self):
        series = oversold_in_an_uptrend(rally_to=260.0, peak=260.0)
        with self.assertRaises(ValueError):
            self.run_(series, mr_take_profit_bounce=True, mr_take_profit_r=1.0)
        with self.assertRaises(ValueError):
            self.run_(series, mr_take_profit_bounce=True, mr_take_profit_atr_by_year={2024: 2.5})
