"""Idle cash earns nothing, and that is the largest measurable loss here.

Median 56% of equity sits at zero yield at any moment, mean 55%, measured
across the decade with the shipped configuration. At 4% that is worth +1.49
CAGR points - 7.82% to 9.31% - net of the trading cost of moving in and out,
with the drawdown completely unchanged because interest cannot lose money.
That is larger than every parameter change tested this week put together.

The danger is not the return, it is the plumbing. A parked holding that leaked
into the rest of the loop would be counted as an open position, occupy a
correlation bucket, be handed a protective stop, be evaluated by the exit
rules, or be cancelled as an orphan sell - and any one of those would do more
damage than the interest is worth.

So the design puts all of that behind ONE gate: `owns()` returns False for the
parking symbol, and every consumer already filters on `owns()`. These tests
pin that gate and the two operations around it, because this is the order
path, where every serious bug in this project has lived.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.autotrade import (
    AutoTradeConfig, _parked, _raise_cash, _sweep_cash, owns)
from fake_broker import FakeBroker


def _config(**overrides):
    settings = dict(cash_parking_symbol="SGOV", dry_run=False,
                    universe=("SPY",), asset_class="equity")
    settings.update(overrides)
    return AutoTradeConfig(**settings)


def _broker(cash, sgov_shares=0.0, sgov_price=100.0):
    positions = []
    if sgov_shares:
        positions.append({"symbol": "SGOV", "quantity": sgov_shares,
                          "average_entry_price": sgov_price,
                          "market_value": sgov_shares * sgov_price,
                          "unrealized_pnl": 0.0})
    broker = FakeBroker(equity=cash, positions=positions)
    broker._init_stops()
    return broker


class OwnershipGateTests(unittest.TestCase):
    """One exclusion, inherited by every consumer. The whole safety design."""

    def test_the_parking_symbol_is_not_owned(self):
        self.assertFalse(owns(_config(), "SGOV"))

    def test_a_traded_symbol_still_is(self):
        self.assertTrue(owns(_config(), "RTX"))

    def test_with_parking_off_it_is_just_another_equity(self):
        """Nothing is special about SGOV itself - only the configured role."""
        self.assertTrue(owns(AutoTradeConfig(), "SGOV"))

    def test_the_match_is_case_insensitive(self):
        self.assertFalse(owns(_config(cash_parking_symbol="sgov"), "SGOV"))

    def test_crypto_confinement_still_applies(self):
        self.assertFalse(owns(_config(asset_class="crypto"), "RTX"))


class SweepTests(unittest.TestCase):
    def test_idle_cash_above_the_floor_is_parked(self):
        broker = _broker(cash=50_000.0)
        _sweep_cash(_config(cash_parking_floor=2_000.0), broker, [])
        self.assertEqual(len(broker.parked_buys), 1)
        symbol, notional, dry = broker.parked_buys[0]
        self.assertEqual(symbol, "SGOV")
        self.assertAlmostEqual(notional, 48_000.0)
        self.assertFalse(dry)

    def test_the_floor_is_left_behind(self):
        """So an ordinary entry next cycle does not need a sale first."""
        broker = _broker(cash=10_000.0)
        _sweep_cash(_config(cash_parking_floor=2_000.0), broker, [])
        self.assertAlmostEqual(broker.parked_buys[0][1], 8_000.0)

    def test_nothing_is_parked_below_the_floor(self):
        broker = _broker(cash=1_500.0)
        _sweep_cash(_config(cash_parking_floor=2_000.0), broker, [])
        self.assertEqual(broker.parked_buys, [])

    def test_a_trivial_remainder_is_left_alone(self):
        """Parking $50 costs a commission to earn a few cents."""
        broker = _broker(cash=2_050.0)
        _sweep_cash(_config(cash_parking_floor=2_000.0), broker, [])
        self.assertEqual(broker.parked_buys, [])

    def test_parking_off_does_nothing_at_all(self):
        broker = _broker(cash=50_000.0)
        _sweep_cash(AutoTradeConfig(), broker, [])
        self.assertEqual(broker.parked_buys, [])

    def test_a_dry_run_submits_nothing_real(self):
        broker = _broker(cash=50_000.0)
        _sweep_cash(_config(dry_run=True), broker, [])
        self.assertTrue(broker.parked_buys[0][2], "should be flagged dry")


class RaiseCashTests(unittest.TestCase):
    def test_only_the_shortfall_is_sold(self):
        """Not the whole holding - that would be pointless turnover."""
        broker = _broker(cash=1_000.0, sgov_shares=500.0, sgov_price=100.0)
        raised = _raise_cash(_config(), broker, shortfall=9_000.0, actions=[])
        self.assertEqual(len(broker.parked_sells), 1)
        symbol, quantity, _dry = broker.parked_sells[0]
        self.assertEqual(symbol, "SGOV")
        # 9,000 plus a 1% margin, at $100 a share.
        self.assertAlmostEqual(quantity, 90.9, places=1)
        self.assertGreater(raised, 9_000.0)
        self.assertLess(quantity, 500.0, "must not liquidate the position")

    def test_it_cannot_sell_more_than_is_held(self):
        broker = _broker(cash=0.0, sgov_shares=10.0, sgov_price=100.0)
        _raise_cash(_config(), broker, shortfall=50_000.0, actions=[])
        self.assertAlmostEqual(broker.parked_sells[0][1], 10.0)

    def test_nothing_parked_means_nothing_to_sell(self):
        broker = _broker(cash=0.0)
        self.assertEqual(_raise_cash(_config(), broker, 5_000.0, []), 0.0)
        self.assertEqual(broker.parked_sells, [])

    def test_a_non_positive_shortfall_does_nothing(self):
        broker = _broker(cash=0.0, sgov_shares=500.0)
        self.assertEqual(_raise_cash(_config(), broker, -1.0, []), 0.0)
        self.assertEqual(broker.parked_sells, [])

    def test_parking_off_never_sells(self):
        broker = _broker(cash=0.0, sgov_shares=500.0)
        self.assertEqual(_raise_cash(AutoTradeConfig(), broker, 5_000.0, []), 0.0)
        self.assertEqual(broker.parked_sells, [])


class ParkedValueTests(unittest.TestCase):
    def test_it_reads_the_holding(self):
        broker = _broker(cash=0.0, sgov_shares=250.0, sgov_price=100.4)
        shares, value = _parked(_config(), broker)
        self.assertAlmostEqual(shares, 250.0)
        self.assertAlmostEqual(value, 25_100.0)

    def test_absent_means_zero_rather_than_an_error(self):
        self.assertEqual(_parked(_config(), _broker(cash=0.0)), (0.0, 0.0))


class ReconcilerIsolationTests(unittest.TestCase):
    """The parked holding must never be handed a protective stop.

    It is a cash equivalent whose widest intraday range over 62 sessions was
    0.020%. A stop on it would be noise that occasionally sells the buffer at
    a random moment - and worse, the reconciler would see a position with no
    remembered stop and invent one from an ATR.
    """

    def test_no_stop_is_placed_on_the_parked_holding(self):
        from event_aware_trader.autotrade import _reconcile_protective_stops
        broker = _broker(cash=1_000.0, sgov_shares=500.0, sgov_price=100.0)
        with TemporaryDirectory() as tmp:
            _reconcile_protective_stops(
                _config(audit_log=Path(tmp) / "a.jsonl",
                        state_file=Path(tmp) / "s.json"),
                broker, {"stops": {}}, [])
        self.assertEqual(broker.protective, [])
        self.assertEqual(broker.canceled, [])

    def test_it_would_be_protected_if_parking_were_off(self):
        """Proves the isolation comes from the gate, not from luck."""
        from event_aware_trader.autotrade import _reconcile_protective_stops
        broker = _broker(cash=1_000.0, sgov_shares=500.0, sgov_price=100.0)
        with TemporaryDirectory() as tmp:
            _reconcile_protective_stops(
                AutoTradeConfig(dry_run=False, universe=("SGOV",),
                                audit_log=Path(tmp) / "a.jsonl",
                                state_file=Path(tmp) / "s.json"),
                broker, {"stops": {"SGOV": {"initial": 95.0, "current": 95.0}}},
                [])
        self.assertEqual(len(broker.protective), 1)


class DefaultTests(unittest.TestCase):
    def test_parking_is_off_by_default(self):
        """It buys an instrument the account has never held, so it is switched
        on deliberately rather than inherited."""
        self.assertIsNone(AutoTradeConfig().cash_parking_symbol)
