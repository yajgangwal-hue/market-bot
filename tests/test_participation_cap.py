"""P2. The simulator now honours the participation cap it was always handed.

`RiskPolicy.max_volume_participation` (0.02) was passed into `run_portfolio`
and read ZERO times, while `autotrade.py` enforced it on every live order. A
declared risk control that is silently unapplied is worse than an absent one:
the backtest could take positions the live bot would refuse, and nothing
distinguished the two.

These tests have to work harder than usual, and the first attempt at them
failed in an instructive way. Thin-volume fixtures cannot be used: the
rule's own liquidity gate (min_average_dollar_volume = $50,000,000) rejects
such a name before sizing is ever reached, so the fixture produced zero
trades and proved nothing.

The two constraints are arithmetically incompatible at this account size.
The cap allows 2% of ADV; the position wants 20% of equity; so it binds only
once equity exceeds ADV/10 - about $5,000,000 against the $50M liquidity
floor. ON THE LIVE $100k ACCOUNT THE CAP CANNOT BIND AT ALL. That is a real
finding, not a testing inconvenience, and it is why P2's measured effect on
the baseline is expected to be exactly zero.

So these tests use a large account, which is the scale the cap exists for,
and one test pins the inertness at $100k so that fact stays visible.
"""

import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.data import Bar
from event_aware_trader.portfolio import run_portfolio
from event_aware_trader.risk import CostModel, RiskPolicy, cap_by_participation

START = datetime(2024, 1, 2, tzinfo=timezone.utc)


def oversold_in_an_uptrend(volume, dip_days=6, dip_pct=0.08):
    """A name the rule will buy, with volume under the caller's control."""
    up = [100.0 + i * 0.25 for i in range(250)]
    top = up[-1]
    closes = up + [top * (1 - dip_pct * (j + 1) / dip_days)
                   for j in range(dip_days)]
    return [Bar(timestamp=START + timedelta(days=i), open=c, high=c,
                low=c * 0.995, close=c, volume=volume)
            for i, c in enumerate(closes)]


# ADV here is ~3,000,000 shares x ~$150 = ~$450M, comfortably over the
# rule's $50M floor. 2% of that is $9M, so the cap binds once a 20% position
# exceeds it - i.e. above roughly $45M of equity.
LIQUID = 3_000_000
BIG_ACCOUNT = 200_000_000.0
SMALL_ACCOUNT = 100_000.0


def run(series, cash=BIG_ACCOUNT, participation=0.02, **kw):
    policy = RiskPolicy() if participation == 0.02 else RiskPolicy(
        max_volume_participation=participation)
    return run_portfolio(series, starting_cash=cash, policy=policy,
                         costs=CostModel(), entry_rule="mean_reversion",
                         entry_fill="signal_close", **kw)


def held_notional(report):
    return sum(p.quantity * p.raw_entry for p in report.open_positions)


class TheCapEngages(unittest.TestCase):
    def test_the_cap_binds_on_a_large_account(self):
        series = {"AAA": oversold_in_an_uptrend(volume=LIQUID)}
        report = run(series)
        self.assertTrue(report.open_positions or report.trades,
                        "fixture must actually trade or it proves nothing")
        # ADV must be taken at the ENTRY bar, not at the end of the series.
        # Measuring it over the last 20 bars overstated it by 0.2% here,
        # because the entry lands mid-dip where prices are lower - and the
        # first version of this test failed on exactly that arithmetic.
        bars = series["AAA"]
        entry_day = (report.open_positions or report.trades)[0]
        entry_date = getattr(entry_day, "entry_time").date()
        idx = next(i for i, b in enumerate(bars) if b.timestamp.date() == entry_date)
        window = bars[max(0, idx - 19):idx + 1]
        adv = sum(b.close * b.volume for b in window) / len(window)
        notional = held_notional(report) or sum(
            t.quantity * t.entry_price for t in report.trades)
        self.assertLessEqual(notional, adv * 0.02 * 1.001,
                             "notional {0:,.0f} exceeds 2% of ADV {1:,.0f}"
                             .format(notional, adv * 0.02))

    def test_it_cannot_bind_on_the_live_hundred_thousand_account(self):
        """Pinned because it is the honest answer to "what did P2 change?".

        2% of a $50M-floor ADV is $1,000,000; a 20% position on $100k is
        $20,000. The cap is inert at the live account size, so P2 must not
        move the baseline. If this ever fails, the account has grown past
        the point where that was true and the baseline needs re-measuring.
        """
        series = {"AAA": oversold_in_an_uptrend(volume=LIQUID)}
        capped = run(series, cash=SMALL_ACCOUNT)
        uncapped = run(series, cash=SMALL_ACCOUNT, participation=None)
        self.assertEqual(
            [(t.symbol, t.quantity) for t in capped.trades],
            [(t.symbol, t.quantity) for t in uncapped.trades])

    def test_disabling_the_cap_restores_the_larger_position(self):
        series = {"AAA": oversold_in_an_uptrend(volume=LIQUID)}
        with_cap = run(series)
        without = run(series, participation=None)
        a = held_notional(with_cap) or sum(t.quantity * t.entry_price for t in with_cap.trades)
        b = held_notional(without) or sum(t.quantity * t.entry_price for t in without.trades)
        self.assertLess(a, b, "the cap must reduce size on a large account")


class ItMatchesLive(unittest.TestCase):
    """Same function, same inputs, same answer - that is the whole point."""

    def test_the_simulator_uses_the_same_helper_as_autotrade(self):
        import inspect
        from event_aware_trader import autotrade, portfolio
        self.assertIn("cap_by_participation", inspect.getsource(portfolio.run_portfolio))
        self.assertIn("cap_by_participation", inspect.getsource(autotrade.run_once))

    def test_the_helper_gives_the_same_answer_both_sides(self):
        # There is one implementation; this pins its behaviour so a future
        # divergence has to be deliberate.
        for qty, price, adv in ((1000, 50.0, 1_000_000.0),
                                (10, 500.0, 250_000.0),
                                (1, 20.0, 10_000_000.0)):
            allowed = cap_by_participation(qty, price, adv, 0.02)
            self.assertLessEqual(allowed * price, adv * 0.02 + 1e-6)

    def test_no_cap_and_no_liquidity_figure_both_mean_unchanged(self):
        self.assertEqual(cap_by_participation(100, 10.0, 1_000_000.0, None), 100)
        self.assertEqual(cap_by_participation(100, 10.0, None, 0.02), 100)


class NoLookAhead(unittest.TestCase):
    def test_future_volume_cannot_change_the_size(self):
        """ADV must come from bars up to the entry, never beyond it."""
        thin = oversold_in_an_uptrend(volume=LIQUID)
        base = run({"AAA": thin})

        # Append a year of enormous volume AFTER the decision window. If the
        # cap were reading forward, the position would grow.
        future = list(thin) + [
            Bar(timestamp=thin[-1].timestamp + timedelta(days=i + 1),
                open=150.0, high=151.0, low=149.0, close=150.0,
                volume=5_000_000_000)
            for i in range(250)]
        extended = run({"AAA": future})

        first_base = base.trades[0] if base.trades else base.open_positions[0]
        first_ext = extended.trades[0] if extended.trades else extended.open_positions[0]
        self.assertAlmostEqual(float(first_base.quantity),
                               float(first_ext.quantity), places=6,
                               msg="future volume changed the position size")


if __name__ == "__main__":
    unittest.main()
