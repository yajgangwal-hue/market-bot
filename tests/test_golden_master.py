"""P0. A pinned record of what the simulator produces, so any later change
is attributable.

Before this existed, `portfolio.py` could be edited and the only signal that
behaviour had moved was an aggregate CAGR - visible solely if somebody re-ran
a six-minute job and happened to remember the previous number. Several of
this project's real defects (the conviction cache keyed on history length,
the dry-run cancel, the bracket stop expiring overnight) were invisible for
days for exactly that reason.

The master asserts the full trade list, not a summary. A change that moves
one fill by a cent while leaving CAGR unchanged to two decimals is still a
behaviour change and must be declared.

G2 requires that this test can FAIL. `test_the_master_is_sensitive_to_a_real_change`
is that proof: it perturbs a strategy parameter and asserts the fingerprint
moves. A golden master nobody has seen fail is decoration.
"""

import json
import unittest
from dataclasses import replace
from pathlib import Path

from golden_fixture import fingerprint, golden_series
from event_aware_trader.mean_reversion import MeanReversionConfig
from event_aware_trader.research import production_report

FIXTURE = Path(__file__).parent / "fixtures" / "golden_baseline.json"


class GoldenMaster(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.report = production_report(golden_series())
        cls.actual = fingerprint(cls.report)

    def test_the_trade_list_is_unchanged(self):
        expected = self.expected["trades"]
        self.assertEqual(
            len(self.actual), len(expected),
            "trade COUNT moved: {0} now vs {1} recorded. Something changed "
            "which trades happen, not merely their prices.".format(
                len(self.actual), len(expected)))
        for i, (got, want) in enumerate(zip(self.actual, expected)):
            self.assertEqual(
                got, want,
                "trade {0} differs.\n  now      : {1}\n  recorded : {2}\n"
                "If this change was intended, regenerate the fixture in the "
                "same commit and say why in the message.".format(i, got, want))

    def test_the_final_equity_is_unchanged(self):
        self.assertAlmostEqual(
            self.report.equity, self.expected["final_equity"], places=4)

    def test_the_fixture_actually_exercises_the_rule(self):
        # A master over an input that trades nothing asserts nothing.
        reasons = {t["reason"] for t in self.expected["trades"]}
        self.assertGreaterEqual(len(self.expected["trades"]), 15)
        self.assertIn("stop", reasons)
        self.assertIn("time_exit", reasons)
        self.assertIn("reverted", reasons)

    def test_it_is_deterministic_within_a_run(self):
        again = fingerprint(production_report(golden_series()))
        self.assertEqual(again, self.actual)

    def test_the_master_is_sensitive_to_a_real_change(self):
        """G2: prove the master can fail.

        A stop 0.01 ATR wider is a small, entirely plausible edit. If the
        fingerprint survives it, this file is not protecting anything.
        """
        moved = production_report(
            golden_series(),
            mr_config=replace(MeanReversionConfig(), stop_atr_multiple=2.51))
        self.assertNotEqual(
            fingerprint(moved), self.actual,
            "the golden master did NOT notice a 0.01 change to the stop "
            "multiple; it cannot detect a real regression either")


if __name__ == "__main__":
    unittest.main()
