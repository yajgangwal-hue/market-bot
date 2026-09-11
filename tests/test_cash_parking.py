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


# Every config here writes to a throwaway directory.
#
# The first version of this file left audit_log and state_file at their
# defaults, which are data/autotrade-audit.jsonl and data/autotrade-state.json
# - the REAL ones. The tests submitted nothing (they use FakeBroker) but they
# logged, and 49 synthetic "parked $48,000" entries landed in the production
# audit log on an account whose cash was $702 all day. record.py reads that
# log to report performance, so the fabricated rows would have shown up as
# fact in every later report.
#
# Module-scoped rather than per-test so it cannot be forgotten in a new test.
_TMP = TemporaryDirectory()


def _config(**overrides):
    settings = dict(cash_parking_symbol="SGOV", dry_run=False,
                    universe=("SPY",), asset_class="equity",
                    audit_log=Path(_TMP.name) / "audit.jsonl",
                    state_file=Path(_TMP.name) / "state.json")
    settings.update(overrides)
    return AutoTradeConfig(**settings)


def _broker(cash, sgov_shares=0.0, sgov_price=100.0, equity=None):
    positions = []
    if sgov_shares:
        positions.append({"symbol": "SGOV", "quantity": sgov_shares,
                          "average_entry_price": sgov_price,
                          "market_value": sgov_shares * sgov_price,
                          "unrealized_pnl": 0.0})
    broker = FakeBroker(equity=cash if equity is None else equity,
                        cash=cash, positions=positions)
    broker._init_stops()
    return broker


class OwnershipGateTests(unittest.TestCase):
    """One exclusion, inherited by every consumer. The whole safety design."""

    def test_the_parking_symbol_is_not_owned(self):
        self.assertFalse(owns(_config(), "SGOV"))

    def test_a_traded_symbol_still_is(self):
        self.assertTrue(owns(_config(), "RTX"))

    def test_with_parking_off_it_is_just_another_equity(self):
        """Nothing is special about SGOV itself - only the configured role.

        Says `cash_parking_symbol=None` explicitly rather than leaning on the
        default, which now IS SGOV. A test that encodes "off" as "whatever the
        default happens to be" silently changes meaning when the default does.
        """
        self.assertTrue(owns(_config(cash_parking_symbol=None), "SGOV"))

    def test_the_match_is_case_insensitive(self):
        self.assertFalse(owns(_config(cash_parking_symbol="sgov"), "SGOV"))

    def test_crypto_confinement_still_applies(self):
        self.assertFalse(owns(_config(asset_class="crypto"), "RTX"))


class SweepTests(unittest.TestCase):
    def test_idle_cash_above_the_floor_is_parked(self):
        broker = _broker(cash=50_000.0)
        _sweep_cash(_config(cash_parking_floor=2_000.0, reserved_fraction=0.0),
                    broker, [])
        self.assertEqual(len(broker.parked_buys), 1)
        symbol, notional, dry = broker.parked_buys[0]
        self.assertEqual(symbol, "SGOV")
        self.assertAlmostEqual(notional, 48_000.0)
        self.assertFalse(dry)

    def test_the_floor_is_left_behind(self):
        """So an ordinary entry next cycle does not need a sale first.

        States reserved_fraction=0.0 explicitly rather than leaning on the
        default, which is now 0.05 for the crypto sleeve. A test that encodes
        "none" as "whatever the default happens to be" changes meaning
        silently when the default does.
        """
        broker = _broker(cash=10_000.0)
        _sweep_cash(_config(cash_parking_floor=2_000.0, reserved_fraction=0.0),
                    broker, [])
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
        _sweep_cash(_config(cash_parking_symbol=None), broker, [])
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
        off = _config(cash_parking_symbol=None)
        self.assertEqual(_raise_cash(off, broker, 5_000.0, []), 0.0)
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
                _config(cash_parking_symbol=None, universe=("SGOV",),
                        audit_log=Path(tmp) / "a.jsonl",
                        state_file=Path(tmp) / "s.json"),
                broker, {"stops": {"SGOV": {"initial": 95.0, "current": 95.0}}},
                [])
        self.assertEqual(len(broker.protective), 1)


class DefaultTests(unittest.TestCase):
    def test_parking_is_enabled_and_points_at_SGOV(self):
        """Switched on 2026-09-10 by the account owner, after the measurement
        and after being told it buys an instrument never previously held."""
        self.assertEqual(AutoTradeConfig().cash_parking_symbol, "SGOV")

    def test_a_floor_is_left_so_entries_do_not_need_a_sale_first(self):
        self.assertGreater(AutoTradeConfig().cash_parking_floor, 0.0)


class CryptoCycleTests(unittest.TestCase):
    """A crypto cycle must never touch the parking instrument.

    The parked holding is an equity ETF and its order is time_in_force=day. An
    equity cycle cannot reach the sweep with the market shut, because run_once
    returns early on a closed clock. A crypto cycle deliberately SKIPS that
    check - crypto trades continuously - so without this guard it would try to
    buy an ETF at three in the morning, every night.
    """

    def test_a_crypto_cycle_parks_nothing(self):
        broker = _broker(cash=50_000.0)
        _sweep_cash(_config(asset_class="crypto"), broker, [])
        self.assertEqual(broker.parked_buys, [])

    def test_a_crypto_cycle_unparks_nothing(self):
        broker = _broker(cash=0.0, sgov_shares=500.0, sgov_price=100.0)
        raised = _raise_cash(_config(asset_class="crypto"), broker, 9_000.0, [])
        self.assertEqual(raised, 0.0)
        self.assertEqual(broker.parked_sells, [])

    def test_an_equity_cycle_still_does_both(self):
        """So the guard is shown to be about the asset class, not a mistake."""
        broker = _broker(cash=50_000.0)
        _sweep_cash(_config(asset_class="equity"), broker, [])
        self.assertEqual(len(broker.parked_buys), 1)


class ReservationTests(unittest.TestCase):
    """Two books share one account, and without a reservation the faster wins.

    Measured live on 2026-09-10: the equity book held six positions and $702.87
    of cash, so a 5% crypto sleeve could never have been funded - every dollar
    that freed up would have gone into the next equity entry before the
    sleeve's daily cycle ran.

    The reservation is withheld from entry sizing AND from the parking sweep.
    Missing the second would be the subtle failure: parking would move the
    sleeve's cash into SGOV and the sleeve would still starve, while every log
    line looked correct.
    """

    def test_the_sweep_leaves_the_reservation_behind(self):
        broker = _broker(cash=50_000.0, equity=50_000.0)
        _sweep_cash(_config(cash_parking_floor=2_000.0, reserved_fraction=0.05),
                    broker, [])
        # 50,000 cash - 2,000 floor - 2,500 reserved
        self.assertAlmostEqual(broker.parked_buys[0][1], 45_500.0)

    def test_with_no_reservation_only_the_floor_is_left(self):
        broker = _broker(cash=50_000.0, equity=50_000.0)
        _sweep_cash(_config(cash_parking_floor=2_000.0, reserved_fraction=0.0),
                    broker, [])
        self.assertAlmostEqual(broker.parked_buys[0][1], 48_000.0)

    def test_a_reservation_larger_than_the_cash_parks_nothing(self):
        # The realistic shape: a mostly-invested account. $3,000 cash
        # against $100,000 equity reserves $5,000, which exceeds the cash.
        broker = _broker(cash=3_000.0, equity=100_000.0)
        _sweep_cash(_config(cash_parking_floor=2_000.0, reserved_fraction=0.05),
                    broker, [])
        self.assertEqual(broker.parked_buys, [])

    def test_the_default_reserves_the_crypto_sleeve(self):
        """5% is withheld from the equity book for the BTC sleeve, enabled
        2026-09-10. Set to 0.0 to hand the cash back."""
        self.assertAlmostEqual(AutoTradeConfig().reserved_fraction, 0.05)

    def test_the_reservation_matches_the_sleeve_weight(self):
        """The two numbers must agree or the sleeve is under- or over-funded
        and the mismatch would show up only as trades that quietly fail."""
        from event_aware_trader.crypto_sleeve import SleeveConfig
        self.assertAlmostEqual(AutoTradeConfig().reserved_fraction,
                               SleeveConfig().fraction)
