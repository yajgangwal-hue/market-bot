"""A learning observation is dated by when its FEATURES were knowable.

THE DEFECT. `append_example` stamped rows with `datetime.now()`, which is
when the trade CLOSED, while the features in the same row describe the
ENTRY. A mean-reversion trade is held up to 20 sessions, so the stamp
could sit up to 20 sessions after the information it claimed to date.
Every purge and embargo boundary is computed from that field, so a row
could be placed on the training side of a boundary its features predate
comfortably while its OUTCOME resolved inside the validation window.

The tests below drive the exact boundary cases the audit called for: a
trade entered immediately before a split and exiting 1, 5 and 20 sessions
later, exactly on the boundary, and past the embargo.
"""

import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader import live_model
from event_aware_trader.modelgov import walkforward


def row(decision, outcome=None, label=1, symbol="AAA", **extra):
    """One observation, dated explicitly on both axes."""
    body = {"at": decision.isoformat(), "decision_at": decision.isoformat(),
            "outcome_at": (outcome or decision).isoformat(),
            "timestamp_convention": "decision", "schema": 2,
            "symbol": symbol, "label": label,
            "f": {k: 0.0 for k in live_model.LIVE_FEATURES}}
    body.update(extra)
    return body


class TheConventionIsDeclaredNotGuessed(unittest.TestCase):
    def test_a_schema_2_row_is_decision_stamped(self):
        self.assertEqual(
            walkforward.timestamp_convention(row(date(2024, 1, 2))), "decision")

    def test_a_seed_row_is_decision_stamped(self):
        legacy = {"at": "1996-12-05", "source": "seed_replay", "label": 0,
                  "f": {}}
        self.assertEqual(walkforward.timestamp_convention(legacy), "decision")
        self.assertEqual(walkforward.example_date(legacy), date(1996, 12, 5))

    def test_a_legacy_live_row_is_outcome_stamped_and_has_no_usable_date(self):
        """The five rows already on disk. Excluded, not guessed at."""
        legacy = {"at": "2026-09-15T17:17:57+00:00", "source": "live",
                  "label": 0, "f": {}}
        self.assertEqual(walkforward.timestamp_convention(legacy), "outcome")
        self.assertIsNone(walkforward.example_date(legacy))

    def test_an_unmarked_row_of_unknown_origin_is_excluded(self):
        self.assertEqual(
            walkforward.timestamp_convention({"at": "2024-01-02", "f": {}}),
            "unknown")
        self.assertIsNone(walkforward.example_date({"at": "2024-01-02", "f": {}}))

    def test_the_census_counts_what_was_excluded(self):
        rows = [row(date(2024, 1, 2)),
                {"at": "1996-12-05", "source": "seed_replay", "f": {}},
                {"at": "2026-09-15T17:00:00+00:00", "source": "live", "f": {}}]
        census = walkforward.census(rows)
        self.assertEqual(census["usable"], 2)
        self.assertEqual(census["excluded"], 1)
        self.assertEqual(census["outcome"], 1)


class TheOutcomeWindowDecidesInclusion(unittest.TestCase):
    """Entry just before a split; exit at various distances past it."""

    def setUp(self):
        self.split = date(2024, 6, 3)
        self.fold = walkforward.Fold(
            index=0, train_start=date(2023, 1, 2),
            train_end=self.split, test_start=self.split + timedelta(days=28),
            test_end=date(2025, 1, 1))

    def place(self, exit_offset_days):
        """A trade entered the session before the split."""
        entry = self.split - timedelta(days=1)
        return row(entry, outcome=entry + timedelta(days=exit_offset_days))

    def straddles(self):
        return any("resolve on or after" in p
                   for p in walkforward.check_no_overlap(self.fold))

    # The embargo is 28 calendar days here, standing for 20 sessions. A
    # trade entered one day before the split and held for 1, 5 or 20
    # sessions resolves INSIDE the embargo and therefore before any test
    # row exists. Those must be KEPT - purging them would throw away
    # training data for no gain - and the tests say so explicitly rather
    # than asserting a purge that would be wrong.
    def test_exiting_one_session_later_resolves_inside_the_embargo(self):
        self.fold.train = [self.place(2)]
        self.assertFalse(self.straddles())

    def test_exiting_five_sessions_later_resolves_inside_the_embargo(self):
        self.fold.train = [self.place(7)]
        self.assertFalse(self.straddles())

    def test_exiting_twenty_sessions_later_still_just_clears_it(self):
        """27 days after the split, one day before the test period opens."""
        self.fold.train = [self.place(28)]
        self.assertFalse(self.straddles())

    def test_a_hold_longer_than_the_cap_does_straddle_and_is_purged(self):
        """The case the calendar proxy alone would miss.

        The 28-day embargo stands for a 20-session cap. A position that
        outlives the cap - a stop that failed to fill, a halted symbol -
        resolves inside the test window, and only the exact outcome-date
        check catches it.
        """
        self.fold.train = [self.place(31)]
        self.assertTrue(self.straddles())

    def test_the_calendar_proxy_is_tight_by_one_day(self):
        """Worth knowing: the margin is a day, not a week."""
        self.fold.train = [self.place(29)]
        self.assertTrue(self.straddles())
        self.fold.train = [self.place(28)]
        self.assertFalse(self.straddles())

    def test_exiting_exactly_on_the_test_start_is_purged(self):
        """The boundary case. Inclusive, deliberately."""
        entry = self.split - timedelta(days=1)
        self.fold.train = [row(entry, outcome=self.fold.test_start)]
        self.assertTrue(any("resolve on or after" in p
                            for p in walkforward.check_no_overlap(self.fold)))

    def test_a_trade_resolving_before_the_test_begins_is_kept(self):
        entry = self.split - timedelta(days=40)
        self.fold.train = [row(entry, outcome=entry + timedelta(days=5))]
        self.assertEqual(walkforward.check_no_overlap(self.fold), [])

    def test_a_test_row_dated_before_training_ended_is_flagged(self):
        self.fold.train = [row(date(2023, 2, 1),
                               outcome=date(2023, 2, 20))]
        self.fold.test = [row(date(2024, 1, 1), outcome=date(2024, 1, 20))]
        self.assertTrue(any("dated before training ended" in p
                            for p in walkforward.check_no_overlap(self.fold)))


class MakeFoldsAppliesTheExactPurge(unittest.TestCase):
    def corpus(self, n=500, hold_days=28):
        """Every trade held `hold_days`, so straddlers exist at every split."""
        rows, day = [], date(2015, 1, 5)
        for i in range(n):
            rows.append(row(day, outcome=day + timedelta(days=hold_days),
                            label=i % 3 == 0, symbol="S%d" % (i % 15)))
            day += timedelta(days=3)
        return rows

    def test_no_training_row_resolves_inside_its_test_window(self):
        for fold in walkforward.make_folds(self.corpus(), n_folds=4):
            for r in fold.train:
                resolved = walkforward.outcome_date(r)
                self.assertLess(resolved, fold.test_start,
                                "fold {0}".format(fold.index))

    def test_straddlers_are_counted_in_the_purge_total(self):
        folds = walkforward.make_folds(self.corpus(), n_folds=4)
        self.assertTrue(any(f.purged > 0 for f in folds))

    def test_a_long_holding_period_purges_more_than_a_short_one(self):
        short = walkforward.make_folds(self.corpus(hold_days=2), n_folds=4)
        long = walkforward.make_folds(self.corpus(hold_days=60), n_folds=4)
        self.assertGreater(sum(f.purged for f in long),
                           sum(f.purged for f in short))

    def test_rows_without_a_usable_date_never_enter_a_fold(self):
        rows = self.corpus()
        rows += [{"at": "2019-06-0{0}T12:00:00+00:00".format(i + 1),
                  "source": "live", "label": 1,
                  "f": {k: 0.0 for k in live_model.LIVE_FEATURES}}
                 for i in range(5)]
        folds = walkforward.make_folds(rows, n_folds=4)
        placed = sum(len(f.train) + len(f.test) for f in folds)
        self.assertGreater(placed, 0)
        for fold in folds:
            for r in fold.train + fold.test:
                self.assertIsNotNone(walkforward.example_date(r))


class AppendExampleWritesBothTimestamps(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "training.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def read(self):
        import json
        return [json.loads(l) for l in
                self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_the_decision_timestamp_is_used_when_supplied(self):
        entry = "2026-09-01T19:45:00+00:00"
        live_model.append_example({}, 1.4, "AAA", path=self.path,
                                  decision_at=entry)
        got = self.read()[0]
        self.assertEqual(got["decision_at"], entry)
        self.assertEqual(got["at"], entry)
        self.assertEqual(got["timestamp_convention"], "decision")
        self.assertEqual(got["schema"], 2)

    def test_the_outcome_timestamp_is_preserved_separately(self):
        entry = "2026-09-01T19:45:00+00:00"
        live_model.append_example({}, 1.4, "AAA", path=self.path,
                                  decision_at=entry)
        got = self.read()[0]
        self.assertNotEqual(got["outcome_at"], entry)
        self.assertGreater(got["outcome_at"], entry)

    def test_a_missing_entry_timestamp_is_declared_not_disguised(self):
        live_model.append_example({}, 1.4, "AAA", path=self.path)
        got = self.read()[0]
        self.assertEqual(got["timestamp_convention"],
                         "outcome_used_as_fallback")

    def test_such_a_row_is_still_usable_but_visibly_a_fallback(self):
        """It declares a convention, so the census can count it."""
        live_model.append_example({}, 1.4, "AAA", path=self.path)
        got = self.read()[0]
        self.assertEqual(walkforward.timestamp_convention(got),
                         "outcome_used_as_fallback")
        self.assertIsNone(walkforward.example_date(got))

    def test_the_label_rule_is_unchanged(self):
        live_model.append_example({}, 0.99, "AAA", path=self.path)
        live_model.append_example({}, 1.00, "BBB", path=self.path)
        self.assertEqual([r["label"] for r in self.read()], [0, 1])


class TheShippedCorpusIsClassified(unittest.TestCase):
    def test_every_row_on_disk_gets_a_convention(self):
        rows = live_model.load_training()
        if not rows:
            self.skipTest("no corpus on disk")
        census = walkforward.census(rows)
        self.assertEqual(census["usable"] + census["excluded"], len(rows))

    def test_the_seed_majority_remains_usable(self):
        rows = live_model.load_training()
        if not rows:
            self.skipTest("no corpus on disk")
        self.assertGreater(walkforward.census(rows)["usable"], 1000)


if __name__ == "__main__":
    unittest.main()
