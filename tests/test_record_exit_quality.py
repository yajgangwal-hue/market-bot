"""record.py reports exit quality on real trades, and survives logs without it.

The live loop writes `captured` and `gave_back` on every exit since
2026-09-13. Older logs have neither, and several callers build TradeRecord
positionally with five fields - so the new fields must be optional, absent
must be tolerated, and the report must say how many trades it actually
scored rather than silently averaging over a subset.
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.record import TradeRecord, from_audit_log


def _write(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n",
                    encoding="utf-8")


def _entry(sym, at):
    return {"at": at, "event": "entry", "dry_run": False,
            "detail": {"symbol": sym, "quantity": 10, "entry_price": 100.0}}


def _exit(sym, at, pnl, captured=None, gave_back=None):
    detail = {"symbol": sym, "realized_pnl": pnl, "return_fraction": pnl / 1000,
              "fees": 0.5, "cost_basis": 1000.0, "entry_price": 100.0}
    if captured is not None:
        detail["captured"] = captured
        detail["gave_back"] = gave_back
    return {"at": at, "event": "exit", "dry_run": False, "detail": detail}


class ExitQualityInTheRecord(unittest.TestCase):
    def test_scored_exits_are_summarised_and_the_winner_turned_loser_is_counted(self):
        with TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            _write(log, [
                _entry("AAA", "2026-09-01T14:00:00+00:00"),
                _exit("AAA", "2026-09-05T14:00:00+00:00", 80.0,
                      captured=0.8, gave_back=0.02),
                _entry("BBB", "2026-09-02T14:00:00+00:00"),
                # was up, closed below entry: captured negative
                _exit("BBB", "2026-09-08T14:00:00+00:00", -30.0,
                      captured=-0.5, gave_back=0.09),
            ])
            report = from_audit_log(log, starting_equity=100_000.0)
        quality = report.exit_quality()
        self.assertIsNotNone(quality)
        self.assertEqual(quality["trades_scored"], 2)
        self.assertAlmostEqual(quality["mean_captured"], 0.15)
        self.assertAlmostEqual(quality["mean_gave_back_pct"], 5.5)
        self.assertEqual(quality["winners_that_became_losers"], 1)
        self.assertIn("exit_quality", report.as_dict())

    def test_an_old_log_without_the_fields_reports_none_not_garbage(self):
        with TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            _write(log, [_entry("AAA", "2026-09-01T14:00:00+00:00"),
                         _exit("AAA", "2026-09-05T14:00:00+00:00", 80.0)])
            report = from_audit_log(log, starting_equity=100_000.0)
        self.assertIsNone(report.exit_quality())
        self.assertIsNone(report.as_dict()["exit_quality"])

    def test_positional_construction_still_works(self):
        # Existing callers build the record with five positional fields.
        t = TradeRecord("AAA", "2026-09-01", "2026-09-05", 80.0, 0.08)
        self.assertIsNone(t.captured)
        self.assertIsNone(t.gave_back)
        self.assertTrue(t.won)


if __name__ == "__main__":
    unittest.main()
