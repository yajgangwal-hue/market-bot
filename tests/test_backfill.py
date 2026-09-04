import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.backfill import (
    allocate_fees,
    audit_rows_for,
    merge_into_log,
    round_trips_from_fills,
)
from event_aware_trader.record import from_audit_log


def fill(symbol, side, qty, price, when):
    return {"symbol": symbol, "side": side, "qty": qty, "price": price,
            "transaction_time": when}


# The first three trades this account ever made, exactly as Alpaca reports
# them. Kept as real data rather than round numbers because the point of the
# reconciliation test below is that it agrees with a real balance.
REAL_FILLS = [
    fill("WMT", "buy", "125", "105.49", "2026-09-01T13:51:32.464Z"),
    fill("WMT", "buy", "38", "105.49", "2026-09-01T13:51:32.627Z"),
    fill("WMT", "buy", "19", "105.49", "2026-09-01T13:51:33.567Z"),
    fill("WMT", "buy", "7", "105.49", "2026-09-01T13:51:33.957Z"),
    fill("WMT", "sell", "108", "106.16", "2026-09-01T16:08:21.290Z"),
    fill("WMT", "sell", "81", "106.17", "2026-09-01T16:08:22.085Z"),
    fill("XOP", "buy", "104", "192.24", "2026-09-01T17:45:52.641Z"),
    fill("DBC", "buy", "114", "31.93", "2026-09-01T19:40:33.025Z"),
    fill("DBC", "buy", "218", "31.93", "2026-09-01T19:40:33.550Z"),
    fill("DBC", "buy", "108", "31.93", "2026-09-01T19:40:33.972Z"),
    fill("DBC", "buy", "187", "31.93", "2026-09-01T19:40:34.722Z"),
    fill("XOP", "sell", "104", "192.15", "2026-09-02T14:04:45.016Z"),
    fill("DBC", "sell", "578", "31.75", "2026-09-02T14:05:10.899Z"),
    fill("DBC", "sell", "42", "31.75", "2026-09-02T14:05:12.383Z"),
    fill("DBC", "sell", "7", "31.75", "2026-09-02T14:05:13.460Z"),
]

REAL_FEES = [
    {"date": "2026-09-02", "net_amount": "-0.83", "sub_type": "REG"},
    {"date": "2026-09-02", "net_amount": "-0.01", "sub_type": "CAT"},
    {"date": "2026-09-02", "net_amount": "-0.15", "sub_type": "TAF"},
    {"date": "2026-09-01", "net_amount": "-0.01", "sub_type": "CAT"},
    {"date": "2026-09-01", "net_amount": "-0.42", "sub_type": "REG"},
    {"date": "2026-09-01", "net_amount": "-0.04", "sub_type": "TAF"},
]


class RoundTripTests(unittest.TestCase):
    def test_partial_fills_on_one_order_are_a_single_trade(self):
        """Four buy fills and two sell fills are one round trip, not six."""
        trips = round_trips_from_fills(REAL_FILLS)
        self.assertEqual([t["symbol"] for t in trips], ["WMT", "XOP", "DBC"])
        wmt = trips[0]
        self.assertEqual(wmt["quantity"], 189.0)
        self.assertAlmostEqual(wmt["cost"], 19937.61, places=2)
        self.assertAlmostEqual(wmt["proceeds"], 20065.05, places=2)

    def test_a_trip_spans_from_first_buy_to_the_fill_that_flattens_it(self):
        trips = round_trips_from_fills(REAL_FILLS)
        dbc = trips[2]
        self.assertEqual(dbc["opened"], "2026-09-01T19:40:33.025Z")
        self.assertEqual(dbc["closed"], "2026-09-02T14:05:13.460Z")

    def test_a_position_still_open_is_not_a_trade(self):
        """An unrealized number is not a result and must not be counted."""
        trips = round_trips_from_fills([
            fill("SPY", "buy", "10", "500.00", "2026-09-01T14:00:00Z"),
            fill("SPY", "sell", "4", "505.00", "2026-09-01T15:00:00Z"),
        ])
        self.assertEqual(trips, [])

    def test_a_second_cycle_in_the_same_symbol_is_a_second_trade(self):
        trips = round_trips_from_fills([
            fill("SPY", "buy", "10", "500.00", "2026-09-01T14:00:00Z"),
            fill("SPY", "sell", "10", "505.00", "2026-09-01T15:00:00Z"),
            fill("SPY", "buy", "10", "501.00", "2026-09-02T14:00:00Z"),
            fill("SPY", "sell", "10", "499.00", "2026-09-02T15:00:00Z"),
        ])
        self.assertEqual(len(trips), 2)
        self.assertAlmostEqual(trips[0]["proceeds"] - trips[0]["cost"], 50.0, places=6)
        self.assertAlmostEqual(trips[1]["proceeds"] - trips[1]["cost"], -20.0, places=6)

    def test_unrecognised_sides_are_ignored_rather_than_corrupting_a_trip(self):
        trips = round_trips_from_fills([
            fill("SPY", "buy", "10", "500.00", "2026-09-01T14:00:00Z"),
            fill("SPY", "dividend", "1", "1.00", "2026-09-01T14:30:00Z"),
            fill("SPY", "sell", "10", "505.00", "2026-09-01T15:00:00Z"),
        ])
        self.assertEqual(len(trips), 1)
        self.assertEqual(trips[0]["quantity"], 10.0)


class FeeAllocationTests(unittest.TestCase):
    def test_fees_split_across_same_day_exits_in_proportion_to_proceeds(self):
        trips = round_trips_from_fills(REAL_FILLS)
        per_trip, unallocated = allocate_fees(trips, REAL_FEES)
        self.assertEqual(unallocated, 0.0)
        # 09-01 has one exit, so it takes that day's fees whole.
        self.assertAlmostEqual(per_trip[0], 0.47, places=4)
        # 09-02 has two, splitting 0.99 by proceeds; Alpaca's own REG fee
        # description names the same $39,890.85 basis.
        self.assertAlmostEqual(per_trip[1] + per_trip[2], 0.99, places=4)
        self.assertGreater(per_trip[1], per_trip[2])

    def test_a_fee_on_a_day_with_no_exit_is_reported_not_absorbed(self):
        trips = round_trips_from_fills(REAL_FILLS)
        _, unallocated = allocate_fees(
            trips, REAL_FEES + [{"date": "2026-08-15", "net_amount": "-2.50"}]
        )
        self.assertAlmostEqual(unallocated, 2.50, places=4)

    def test_no_trips_leaves_every_fee_unallocated(self):
        per_trip, unallocated = allocate_fees([], REAL_FEES)
        self.assertEqual(per_trip, [])
        self.assertAlmostEqual(unallocated, 1.46, places=4)


class ReconciliationTests(unittest.TestCase):
    def test_the_rebuilt_record_matches_the_real_account_balance(self):
        """The whole point: rebuilt P&L must equal what the broker says.

        The account was funded with exactly $100,000 and stood at $100,003.76
        once these three trades had closed. Gross P&L is $5.22; the missing
        $1.46 is Alpaca's REG/TAF/CAT fees. A rebuild that ignores fees is
        about a dollar and a half optimistic and never reconciles.
        """
        trips = round_trips_from_fills(REAL_FILLS)
        per_trip, _ = allocate_fees(trips, REAL_FEES)
        rows = audit_rows_for(trips, per_trip)

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            path.write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
            )
            report = from_audit_log(path, starting_equity=100_000.0)

        self.assertEqual(len(report.trades), 3)
        self.assertAlmostEqual(report.ending_equity, 100_003.76, places=2)
        self.assertEqual(report.wins, 1)


class MergeTests(unittest.TestCase):
    def _write(self, path, rows):
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    def test_backfilling_an_empty_log_adds_every_trip(self):
        trips = round_trips_from_fills(REAL_FILLS)
        per_trip, _ = allocate_fees(trips, REAL_FEES)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            summary = merge_into_log(path, trips, per_trip)
            self.assertEqual(summary["trips_added"], 3)
            self.assertEqual(summary["rows_added"], 6)
            self.assertAlmostEqual(summary["realized_pnl_added"], 3.76, places=2)

    def test_running_it_twice_changes_nothing(self):
        """Idempotence matters: this is a command people re-run when unsure."""
        trips = round_trips_from_fills(REAL_FILLS)
        per_trip, _ = allocate_fees(trips, REAL_FEES)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            merge_into_log(path, trips, per_trip)
            first = path.read_text(encoding="utf-8")
            summary = merge_into_log(path, trips, per_trip)
            self.assertEqual(summary["trips_added"], 0)
            self.assertEqual(summary["trips_already_present"], 3)
            self.assertEqual(path.read_text(encoding="utf-8"), first)

    def test_a_trade_the_local_log_already_recorded_is_not_duplicated(self):
        trips = round_trips_from_fills(REAL_FILLS)
        per_trip, _ = allocate_fees(trips, REAL_FEES)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            self._write(path, [
                {"at": "2026-09-01T13:51:32.464Z", "event": "entry",
                 "detail": {"symbol": "WMT", "quantity": 189}},
                {"at": "2026-09-01T16:08:22.085Z", "event": "exit",
                 "detail": {"symbol": "WMT", "realized_pnl": 126.97,
                            "return_fraction": 0.006369}},
            ])
            summary = merge_into_log(path, trips, per_trip)
            self.assertEqual(summary["trips_added"], 2)
            self.assertEqual(sorted(summary["symbols_added"]), ["DBC", "XOP"])
            self.assertEqual(len(from_audit_log(path).trades), 3)

    def test_existing_rows_survive_and_the_file_stays_in_time_order(self):
        trips = round_trips_from_fills(REAL_FILLS)
        per_trip, _ = allocate_fees(trips, REAL_FEES)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            self._write(path, [
                {"at": "2026-09-02T04:42:25.491Z", "event": "run_complete", "detail": {}},
                {"at": "2026-09-03T20:00:03.272Z", "event": "run_complete", "detail": {}},
            ])
            merge_into_log(path, trips, per_trip)
            rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
            stamps = [r["at"] for r in rows]
            self.assertEqual(stamps, sorted(stamps))
            self.assertEqual(sum(1 for r in rows if r["event"] == "run_complete"), 2)
            self.assertEqual(len(rows), 8)

    def test_a_log_written_with_a_bom_is_still_read(self):
        """A PowerShell redirect writes a BOM; json.loads rejects it."""
        trips = round_trips_from_fills(REAL_FILLS)
        per_trip, _ = allocate_fees(trips, REAL_FEES)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            path.write_text(
                json.dumps({"at": "2026-09-01T13:51:32.464Z", "event": "entry",
                            "detail": {"symbol": "WMT"}}) + "\n",
                encoding="utf-8-sig",
            )
            summary = merge_into_log(path, trips, per_trip)
            self.assertEqual(sorted(summary["symbols_added"]), ["DBC", "XOP"])


if __name__ == "__main__":
    unittest.main()
