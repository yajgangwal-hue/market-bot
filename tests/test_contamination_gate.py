"""P1. Scoring a spent dataset requires saying why, and it is recorded.

Before this, `DATASETS` declared the decade, the thirty-year window, the ETF
control and the crypto sets contaminated - 37 and 30 recorded touches - and
then nothing at all prevented the next run. The ledger described the problem
rather than preventing it.

The gate is honest about its own limit. Someone determined to bypass it can
still pass `dataset=` a lie. What it removes is the far more likely failure:
scoring a spent set because nobody remembered it was spent.
"""

import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.data import Bar
from event_aware_trader.research import (
    ContaminatedDataError, DATASETS, PURPOSES, check_dataset_gate,
    looks_like_research_data, production_report)

START = datetime(2016, 1, 4, tzinfo=timezone.utc)


def series(symbols, bars, price=100.0):
    out = {}
    for s in symbols:
        out[s] = [Bar(timestamp=START + timedelta(days=i), open=price,
                      high=price, low=price, close=price, volume=1_000_000)
                  for i in range(bars)]
    return out


class TheTripwire(unittest.TestCase):
    """Research-scale data must declare itself."""

    def test_a_small_fixture_is_not_research_scale(self):
        self.assertFalse(looks_like_research_data(series(["AAA", "BBB"], 300)))

    def test_many_symbols_over_a_short_span_is_not(self):
        wide = series(["S%02d" % i for i in range(60)], 100)   # ~3 months
        self.assertFalse(looks_like_research_data(wide))

    def test_a_few_symbols_over_a_long_span_is_not(self):
        deep = series(["AAA", "BBB"], 2000)                    # ~5 years
        self.assertFalse(looks_like_research_data(deep))

    def test_many_symbols_over_many_years_is(self):
        big = series(["S%02d" % i for i in range(60)], 1500)   # ~4 years
        self.assertTrue(looks_like_research_data(big))

    def test_research_scale_without_a_dataset_raises(self):
        big = series(["S%02d" % i for i in range(60)], 1500)
        with self.assertRaises(ContaminatedDataError) as caught:
            check_dataset_gate(big, None, None)
        self.assertIn("no dataset= was declared", str(caught.exception))

    def test_a_unit_test_fixture_still_runs_ungated(self):
        # The golden master and every other small test must keep working.
        check_dataset_gate(series(["AAA", "BBB"], 300), None, None)

    def test_the_gate_is_actually_wired_into_production_report(self):
        # The one integration test. Without it the gate could be perfect and
        # simply never called - which is precisely the failure mode it was
        # built to fix (DATASETS declared contamination and nothing read it).
        big = series(["S%02d" % i for i in range(60)], 1500)
        with self.assertRaises(ContaminatedDataError):
            production_report(big)


class DeclaringAPurpose(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.registry = Path(self._tmp.name) / "reg.jsonl"
        self.big = series(["S%02d" % i for i in range(60)], 1500)

    def tearDown(self):
        self._tmp.cleanup()

    def _rows(self):
        if not self.registry.exists():
            return []
        return [json.loads(l) for l in self.registry.read_text().splitlines() if l.strip()]

    def test_a_contaminated_set_without_a_purpose_raises(self):
        with self.assertRaises(ContaminatedDataError) as caught:
            check_dataset_gate(self.big, "thirty_year", None, self.registry)
        self.assertIn("requires purpose=", str(caught.exception))
        self.assertEqual(self._rows(), [])

    def test_an_unknown_purpose_raises(self):
        with self.assertRaises(ContaminatedDataError):
            check_dataset_gate(self.big, "decade", "because", self.registry)

    def test_an_unknown_dataset_raises(self):
        with self.assertRaises(ContaminatedDataError) as caught:
            check_dataset_gate(self.big, "mars", "diagnostic", self.registry)
        self.assertIn("unknown dataset", str(caught.exception))

    def test_a_valid_purpose_runs_and_records_exactly_one_row(self):
        check_dataset_gate(self.big, "thirty_year",
                           "baseline_remeasurement", self.registry)
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "dataset_use")
        self.assertEqual(rows[0]["dataset"], "thirty_year")
        self.assertEqual(rows[0]["purpose"], "baseline_remeasurement")
        self.assertEqual(rows[0]["symbols"], 60)
        self.assertIn("at", rows[0])

    def test_every_run_is_recorded_not_just_the_first(self):
        for _ in range(3):
            check_dataset_gate(self.big, "decade", "diagnostic", self.registry)
        self.assertEqual(len(self._rows()), 3)


class TheForwardRecordIsSpecial(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.registry = Path(self._tmp.name) / "reg.jsonl"
        self.big = series(["S%02d" % i for i in range(60)], 1500)

    def tearDown(self):
        self._tmp.cleanup()

    def test_forward_is_declared_clean_but_still_gated(self):
        self.assertEqual(DATASETS["forward"]["status"], "clean")
        with self.assertRaises(ContaminatedDataError):
            check_dataset_gate(self.big, "forward", None, self.registry)

    def test_forward_rejects_every_purpose_but_its_own(self):
        for purpose in ("diagnostic", "rejection_test", "baseline_remeasurement"):
            with self.assertRaises(ContaminatedDataError) as caught:
                check_dataset_gate(self.big, "forward", purpose, self.registry)
            self.assertIn("forward_gate_evaluation", str(caught.exception))

    def test_the_vocabulary_encodes_the_reject_only_asymmetry(self):
        # Contaminated data can reject; it can never accept. If a purpose
        # like "acceptance_test" ever appears here, that rule has been lost.
        self.assertIn("rejection_test", PURPOSES)
        self.assertNotIn("acceptance_test", PURPOSES)
        self.assertIn("can only reject", PURPOSES["rejection_test"])


if __name__ == "__main__":
    unittest.main()
