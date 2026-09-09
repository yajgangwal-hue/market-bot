"""The switchable entry rule, and the exit that has to match it.

Mean reversion is the shipped default because it is the one that measures.
Through record.py's own verdict, one engine, two years, 120 equities:

    trend gate      138 trades  NOT_DISTINGUISHABLE_FROM_LUCK  p=0.34
    mean reversion   31 trades  POSITIVE_AND_MEASURABLE        p=0.030

The risk in a switch like this is subtler than a wrong number: trading one
rule's entries against the other's exits would measure neither, so the pairing
is pinned here as much as the entry itself.
"""
import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.autotrade import AutoTradeConfig, _mean_reversion_candidate
from event_aware_trader.risk import CostModel, RiskPolicy
from event_aware_trader.strategy import StrategyConfig
from event_aware_trader.types import Action, Bar

START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _bars(closes):
    out = []
    for i, close in enumerate(closes):
        out.append(Bar(timestamp=START + timedelta(days=i),
                       open=close, high=close * 1.005, low=close * 0.995,
                       close=close, volume=80_000_000.0))
    return out


def oversold_in_an_uptrend(dip_days=12):
    """A long rise, then a sharp dip that stays above the 200-day average.

    That is the setup the rule is built for: short-horizon weakness inside an
    intact long-term uptrend, rather than a downtrend to catch.
    """
    rise = [100.0 + i * 0.5 for i in range(230)]          # 100 -> 214
    peak = rise[-1]
    dip = [peak * (1.0 - 0.012 * (i + 1)) for i in range(dip_days)]
    return _bars(rise + dip)


def _candidate(bars):
    return _mean_reversion_candidate(
        "SPY", bars, 100_000.0, RiskPolicy(), CostModel(),
        StrategyConfig.for_interval("1d", exit_mode="trailing"))


class DefaultTests(unittest.TestCase):
    def test_the_shipped_rule_is_mean_reversion(self):
        self.assertEqual(AutoTradeConfig().entry_rule, "mean_reversion")

    def test_the_trend_gate_is_still_reachable(self):
        self.assertEqual(AutoTradeConfig(entry_rule="trend").entry_rule, "trend")


class SignalTests(unittest.TestCase):
    def test_weakness_inside_an_uptrend_is_a_buy(self):
        c = _candidate(oversold_in_an_uptrend())
        self.assertEqual(c.action, Action.PAPER_LONG, c.blockers)
        self.assertIsNotNone(c.entry)
        self.assertIsNotNone(c.stop)

    def test_a_steady_rise_with_no_weakness_is_not(self):
        """The rule buys dips, not strength - that is the whole premise."""
        c = _candidate(_bars([100.0 + i * 0.5 for i in range(240)]))
        self.assertNotEqual(c.action, Action.PAPER_LONG)

    def test_a_long_downtrend_is_refused_WHEN_THE_FILTER_IS_ON(self):
        """Oversold below the 200-day average is a falling knife, not a dip.

        The filter was switched OFF in the shipped config on 2026-09-09 by the
        account owner's explicit decision, so this no longer describes the
        default. It is kept, pinned to the filter, because the property it
        protects is real and the setting is one line from being restored - and
        because the next person should be able to see what was given up.
        """
        from dataclasses import replace
        from event_aware_trader.mean_reversion import MeanReversionConfig
        guarded = replace(MeanReversionConfig(), trend_ma_days=200)
        c = _mean_reversion_candidate(
            "SPY", _bars([200.0 - i * 0.5 for i in range(240)]), 100_000.0,
            RiskPolicy(), CostModel(),
            StrategyConfig.for_interval("1d", exit_mode="trailing"),
            rule_config=guarded)
        self.assertNotEqual(c.action, Action.PAPER_LONG)

    def test_the_shipped_config_now_BUYS_that_downtrend(self):
        """The cost of the decision, stated as a test rather than a comment.

        With the filter off the rule buys oversold weakness regardless of the
        long-term trend. Over thirty years that is worth +2.0 CAGR points and
        a maximum drawdown that more than doubles, and 2008 goes from -8.7% to
        -25.8%. If this assertion ever starts failing, the filter has been
        turned back on and the numbers in mean_reversion.py apply again.
        """
        c = _candidate(_bars([200.0 - i * 0.5 for i in range(240)]))
        self.assertEqual(c.action, Action.PAPER_LONG, c.blockers)

    def test_the_stop_sits_below_the_entry(self):
        c = _candidate(oversold_in_an_uptrend())
        self.assertLess(c.stop, c.entry)

    def test_a_target_is_supplied_only_so_the_entry_can_bracket(self):
        """Mean reversion never exits on a target; the leg is cancelled next
        cycle. It exists so an equity entry is protected on arrival."""
        c = _candidate(oversold_in_an_uptrend())
        self.assertGreater(c.target, c.entry)

    def test_deeper_oversold_ranks_first(self):
        """Score orders several oversold names; it is not the trend score."""
        shallow = _candidate(oversold_in_an_uptrend(dip_days=8))
        deep = _candidate(oversold_in_an_uptrend(dip_days=16))
        if shallow.action == Action.PAPER_LONG and deep.action == Action.PAPER_LONG:
            self.assertGreater(deep.score, shallow.score)

    def test_a_rejected_candidate_carries_its_reasons(self):
        """A steady rise has no weakness to buy, so it is refused with a reason.

        This used a downtrend until the trend filter was switched off, at
        which point a downtrend became a BUY and there was no refusal left to
        inspect. The property under test is that refusals explain themselves,
        so any refused candidate serves.
        """
        c = _candidate(_bars([100.0 + i * 0.5 for i in range(240)]))
        self.assertNotEqual(c.action, Action.PAPER_LONG)
        self.assertTrue(c.blockers, "a refusal with no reason cannot be debugged")

    def test_liquidity_is_reported_for_the_participation_cap(self):
        """cap_by_participation needs this, and silently skips without it."""
        c = _candidate(oversold_in_an_uptrend())
        self.assertIn("average_dollar_volume", c.features)
        self.assertGreater(c.features["average_dollar_volume"], 0)



class DailyTimescaleTests(unittest.TestCase):
    """The rule counts in DAYS, and the loop may be running any interval.

    MeanReversionConfig's numbers - rsi_period 14, trend_ma_days 200,
    max_holding_bars 10 - were all chosen on daily data, and the +1.571%/trade
    result was produced there. The live loop runs --interval 15m, where 26 bars
    is one session. Hand it the cycle's candles and max_holding_bars 10 becomes
    a two-and-a-half hour timer nobody set, on a strategy nobody measured.
    """

    def test_too_few_daily_bars_is_refused_with_a_reason(self):
        """Rather than evaluating a 200-day average over three days of candles."""
        c = _candidate(_bars([100.0 + i * 0.5 for i in range(50)]))
        self.assertNotEqual(c.action, Action.PAPER_LONG)
        self.assertTrue(any("daily bars" in b for b in c.blockers), c.blockers)

    def test_an_empty_series_does_not_raise(self):
        c = _mean_reversion_candidate(
            "SPY", [], 100_000.0, RiskPolicy(), CostModel(),
            StrategyConfig.for_interval("1d", exit_mode="trailing"))
        self.assertNotEqual(c.action, Action.PAPER_LONG)

    def test_the_windows_are_counted_in_days(self):
        """Pins the SCALE, not the tuning.

        An earlier version asserted max_holding_bars == 10 and failed when the
        window was retuned to 20 - catching a deliberate change while proving
        nothing about the thing it existed to protect. What must stay true is
        that these are day counts: a holding window of a few days to a few
        months, and a trend filter of 200 days. Feed the rule 15-minute candles
        and the same numbers mean hours, which is a different strategy wearing
        this one's parameters.
        """
        from event_aware_trader.mean_reversion import MeanReversionConfig
        cfg = MeanReversionConfig()
        # This asserted trend_ma_days == 200 until that filter was switched
        # off on 2026-09-09. The SCALE is now carried by warmup_days, which is
        # exactly why it is a separate field: turning the filter off must not
        # be able to collapse the history requirement from 215 bars to 15 and
        # start the rule trading on an RSI computed from fifteen prices.
        self.assertGreaterEqual(cfg.warmup_days, 200)
        self.assertGreaterEqual(cfg.minimum_history, 215)
        self.assertGreaterEqual(cfg.max_holding_bars, 5)
        self.assertLessEqual(cfg.max_holding_bars, 90)
        # Warmup must cover the trend filter, or the 200-day average is
        # computed over whatever happens to be on file.
        self.assertGreaterEqual(cfg.minimum_history, cfg.trend_ma_days)

    def test_missing_price_file_yields_no_bars_rather_than_raising(self):
        from event_aware_trader.autotrade import daily_bars
        from pathlib import Path
        self.assertEqual(daily_bars("NOTAREALSYMBOL", Path("no-such-dir")), [])


class CashGuardTests(unittest.TestCase):
    """Entries are limited by cash, not by margin buying power.

    Sizing is a fraction of EQUITY, so several positions can total more than
    the account holds. At the old 20% cap and six positions that was 120% - an
    overshoot margin absorbed quietly. At 50% it is 300%, which is leverage,
    and the sizing sweep that justified 50% skipped any signal whose cost
    exceeded available cash. Borrowing would make the live record describe a
    strategy nobody measured.
    """

    def _run(self, cash, equity=100_000.0):
        import tempfile
        from pathlib import Path as _Path
        from event_aware_trader.autotrade import run_once
        from tests.fake_broker import FakeBroker

        class Broker(FakeBroker):
            def account(self):
                base = super().account()
                base["cash"] = cash
                return base

        tmp = _Path(tempfile.mkdtemp())
        cfg = AutoTradeConfig(
            dry_run=True, require_market_open=False, entry_rule="trend",
            audit_log=tmp / "a.jsonl", state_file=tmp / "s.json",
            universe=("SPY",))
        broker = Broker(equity=equity)
        result = run_once(cfg, broker=broker, bars_by_symbol={"SPY": oversold_in_an_uptrend()})
        return result, tmp / "a.jsonl"

    def test_an_account_with_no_cash_opens_nothing(self):
        import json
        result, log = self._run(cash=0.0)
        self.assertEqual(result.get("entries", 0), 0)
        rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()
                if l.strip()]
        self.assertFalse([r for r in rows if r["event"] == "entry"],
                         "opened a position with no cash to pay for it")

if __name__ == "__main__":
    unittest.main()
