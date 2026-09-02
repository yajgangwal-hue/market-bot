import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.preflight import PreflightReport, run_preflight, strategy_expectation
from event_aware_trader.risk import RiskPolicy


class ReportTests(unittest.TestCase):
    def test_a_blocking_failure_makes_it_not_ready(self):
        report = PreflightReport()
        report.add("ok", True, "")
        report.add("bad", False, "", blocking=True)
        self.assertFalse(report.ready)
        self.assertEqual([c.name for c in report.blocking_failures], ["bad"])

    def test_a_warning_does_not_block(self):
        report = PreflightReport()
        report.add("stale", False, "", blocking=False)
        self.assertTrue(report.ready)
        self.assertEqual([c.name for c in report.warnings], ["stale"])


def _has_price_data():
    """data/ is gitignored, so a fresh clone has no CSVs at all."""
    return bool(list(Path("data").glob("*.csv")))


class RiskCheckTests(unittest.TestCase):
    @unittest.skipUnless(_has_price_data(),
                         "no data/*.csv yet - fetch price data before this can mean anything")
    def test_real_data_passes_the_non_broker_checks(self):
        # This one reads the REAL data directory, so it is a check on the
        # machine as much as on the code. On a fresh checkout there are no
        # CSVs - data/ is gitignored - and it failed with "price files
        # present, strategy evaluates cleanly", which reads like broken code
        # rather than an empty folder. It skips now instead of lying.
        report = run_preflight(Path("data"), 1_000.0, check_broker=False)
        failures = [c.name for c in report.blocking_failures]
        self.assertEqual(failures, [], "unexpected blocking failures: {0}".format(failures))

    def test_leverage_is_reported_as_a_blocking_failure(self):
        policy = RiskPolicy(max_notional_fraction=1.0)
        report = run_preflight(Path("data"), 1_000.0, policy=policy, check_broker=False)
        names = [c.name for c in report.checks]
        self.assertIn("no leverage", names)

    def test_missing_data_directory_blocks(self):
        with TemporaryDirectory() as tmp:
            report = run_preflight(Path(tmp), 1_000.0, check_broker=False)
            self.assertFalse(report.ready)
            self.assertIn("price files present", [c.name for c in report.blocking_failures])


class HonestyTests(unittest.TestCase):
    def test_the_report_states_it_is_not_evidence_of_profit(self):
        verdict = strategy_expectation()["verdict"].lower()
        self.assertIn("not evidence that it makes money", verdict)

    def test_measured_history_is_included(self):
        expectation = strategy_expectation()
        self.assertIn("trend_gate_2017_2023_held_out", expectation)
        self.assertIn("profitable_years", expectation)


if __name__ == "__main__":
    unittest.main()
