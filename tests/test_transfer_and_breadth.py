"""The fundamental law's other two terms, and honest cost headroom.

IR = TC x IC x sqrt(breadth). The record measured IC and breadth once
`consistency()` landed, but nothing measured the transfer coefficient - how
much of a forecast survives the constraints between deciding and holding -
and nothing checked whether the breadth was real or ten bets on one theme.

The cost tests exist because the first version of the headroom figure was
reassuring and wrong: the audit log itemises only the explicit fee line, and
spread and slippage sit inside the fill price where nothing can see them.
Measured against fees alone the edge looked to cover costs 3.9x; against
realistic all-in friction it covers 0.08x.
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.record import (
    DECAY_HAIRCUT,
    REALISTIC_EQUITY_ROUND_TRIP,
    RecordReport,
    TradeRecord,
    from_audit_log,
)


def log_with(rows):
    """Write rows to a temp audit log and return the rebuilt record.

    `from_audit_log` reads the whole file eagerly, so the directory can be
    cleaned as soon as it returns.
    """
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "audit.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        return from_audit_log(path)


class TransferTests(unittest.TestCase):
    def test_no_constraint_events_means_nothing_to_report(self):
        self.assertIsNone(RecordReport().transfer())

    def test_entries_that_reached_the_portfolio_are_counted(self):
        report = log_with([
            {"at": "2026-01-01", "event": "entry", "detail": {"symbol": "SPY"}},
            {"at": "2026-01-01", "event": "entry", "detail": {"symbol": "QQQ"}},
            {"at": "2026-01-01", "event": "skipped_no_cash", "detail": {"symbol": "IWM"}},
            {"at": "2026-01-01", "event": "skipped_no_cash", "detail": {"symbol": "EFA"}},
        ])
        transfer = report.transfer()
        self.assertEqual(transfer["entries_made"], 2)
        self.assertEqual(transfer["entries_blocked"], 2)
        self.assertEqual(transfer["signal_reaching_the_portfolio"], 0.5)

    def test_the_binding_constraint_is_named(self):
        rows = [{"at": "2026-01-01", "event": "entry", "detail": {"symbol": "SPY"}}]
        rows += [{"at": "2026-01-01", "event": "model_veto",
                  "detail": {"symbol": "X{0}".format(i)}} for i in range(5)]
        rows += [{"at": "2026-01-01", "event": "skipped_no_cash",
                  "detail": {"symbol": "Y"}}]
        transfer = log_with(rows).transfer()
        self.assertEqual(transfer["binding_constraint"], "model_veto")
        self.assertIn("tax on an edge you already have", transfer["reading"])

    def test_a_cap_that_shrank_an_order_is_counted_separately(self):
        """A clipped order still reached the portfolio; a blocked one did not."""
        report = log_with([
            {"at": "2026-01-01", "event": "entry", "detail": {"symbol": "SPY"}},
            {"at": "2026-01-01", "event": "size_capped_by_liquidity",
             "detail": {"symbol": "SPY"}},
        ])
        transfer = report.transfer()
        self.assertEqual(transfer["orders_shrunk_by_a_cap"], 1)
        self.assertEqual(transfer["entries_blocked"], 0)
        self.assertEqual(transfer["signal_reaching_the_portfolio"], 1.0)


class BreadthQualityTests(unittest.TestCase):
    def _report(self, symbols):
        report = RecordReport()
        for symbol in symbols:
            report.trades.append(
                TradeRecord(symbol, "2026-01-01", "2026-01-05", 1.0, 0.01))
        return report

    def test_one_trade_is_not_a_distribution(self):
        self.assertIsNone(self._report(["SPY"]).breadth_quality())

    def test_spread_across_buckets_scores_near_the_bucket_count(self):
        got = self._report(["SPY", "TLT", "GLD", "XLE"]).breadth_quality()
        self.assertEqual(got["distinct_buckets"], got["effective_buckets"])

    def test_concentration_collapses_the_effective_count(self):
        """Ten bets on one theme is one bet, and the square root makes it cost."""
        got = self._report(["SPY"] * 9 + ["TLT"]).breadth_quality()
        self.assertEqual(got["distinct_buckets"], 2)
        self.assertLess(got["effective_buckets"], 1.3)
        self.assertIn("concentrated", got["reading"])

    def test_the_largest_bucket_is_named_with_its_share(self):
        got = self._report(["SPY"] * 3 + ["TLT"]).breadth_quality()
        self.assertAlmostEqual(got["largest_bucket_share"], 0.75)


class CostHeadroomTests(unittest.TestCase):
    def _report(self, gross_return, fee_fraction, n=10):
        report = RecordReport()
        basis = 10_000.0
        fees = fee_fraction * basis
        for _ in range(n):
            net = gross_return - fee_fraction
            report.trades.append(TradeRecord(
                "SPY", "2026-01-01", "2026-01-05", net * basis, net,
                fees=fees, cost_basis=basis))
        return report

    def test_gross_return_adds_the_fee_fraction_back(self):
        trade = TradeRecord("SPY", "2026-01-01", "2026-01-05", 90.0, 0.009,
                            fees=10.0, cost_basis=10_000.0)
        self.assertAlmostEqual(trade.fee_fraction, 0.001)
        self.assertAlmostEqual(trade.gross_return_fraction, 0.010)

    def test_a_trade_without_a_basis_has_no_fee_fraction(self):
        self.assertIsNone(
            TradeRecord("SPY", "a", "b", 1.0, 0.01, fees=5.0).fee_fraction)

    def test_headroom_is_reported_against_realistic_friction_not_fees(self):
        """Fees alone flattered the edge by roughly fifty times."""
        friction = self._report(gross_return=0.01, fee_fraction=0.0001).friction()
        self.assertAlmostEqual(friction["headroom_vs_fees_only"], 100.0, places=0)
        self.assertAlmostEqual(friction["headroom_vs_realistic_friction"],
                               round(0.01 / REALISTIC_EQUITY_ROUND_TRIP, 2), places=2)
        self.assertIn("spread and slippage", friction["cost_note"])

    def test_an_edge_that_fails_after_decay_is_called_out(self):
        friction = self._report(gross_return=0.0015, fee_fraction=0.0001).friction()
        self.assertLess(0.0015 * DECAY_HAIRCUT, REALISTIC_EQUITY_ROUND_TRIP)
        self.assertIn("does not clear realistic friction", friction["cost_reading"])

    def test_a_comfortable_edge_is_not_flagged(self):
        friction = self._report(gross_return=0.02, fee_fraction=0.0001).friction()
        self.assertNotIn("cost_reading", friction)

    def test_a_negative_gross_edge_is_not_a_cost_problem(self):
        friction = self._report(gross_return=-0.005, fee_fraction=0.0001).friction()
        self.assertIn("no reduction in costs", friction["cost_note"])

    def test_cost_basis_is_read_from_the_audit_log(self):
        report = log_with([
            {"at": "2026-01-01", "event": "entry", "detail": {"symbol": "XOP"}},
            {"at": "2026-01-05", "event": "exit", "detail": {
                "symbol": "XOP", "realized_pnl": -9.86, "return_fraction": -0.000493,
                "fees": 0.4959, "cost_basis": 19992.96}},
        ])
        trade = report.trades[0]
        self.assertAlmostEqual(trade.cost_basis, 19992.96)
        self.assertAlmostEqual(trade.fee_fraction, 0.4959 / 19992.96)


if __name__ == "__main__":
    unittest.main()
