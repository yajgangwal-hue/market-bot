"""The research firewall: the candidate mirrors live, the registry counts, the
distribution is per period.

If PRODUCTION_CANDIDATE silently drops a live constraint, every future
comparison is against something the bot does not do. If the registry stops
counting related experiments, the deflated-Sharpe correction is fed a lie.
"""

import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.portfolio import ClosedTrade, PortfolioReport
from event_aware_trader.research import (
    DATASETS, PRODUCTION_CANDIDATE, contamination_summary, deflated_sharpe,
    load_registry, period_table, production_policy, record_experiment,
    related_before, summarize_periods, walk_forward_years)

START = datetime(2020, 1, 1, tzinfo=timezone.utc)


class TheCandidateMirrorsLive(unittest.TestCase):
    def test_every_live_constraint_is_on(self):
        self.assertEqual(PRODUCTION_CANDIDATE["entry_fill"], "signal_close")
        self.assertTrue(PRODUCTION_CANDIDATE["realistic_stop_fills"])
        self.assertEqual(PRODUCTION_CANDIDATE["max_entries_per_day"], 3)
        self.assertTrue(PRODUCTION_CANDIDATE["mark_to_market_guard"])
        self.assertFalse(production_policy().allow_fractional_shares)

    def test_it_matches_the_live_config_where_the_two_overlap(self):
        # max_entries_per_day mirrors max_orders_per_run x one closing cycle.
        from event_aware_trader.autotrade import AutoTradeConfig
        live = AutoTradeConfig()
        self.assertEqual(PRODUCTION_CANDIDATE["max_entries_per_day"],
                         live.max_orders_per_run)
        self.assertIsNotNone(live.entry_window_minutes,
                             "live has no entry window but the candidate assumes one")


class PerPeriodDistribution(unittest.TestCase):
    def _report(self, values_by_year):
        report = PortfolioReport(starting_cash=100.0, cash=0.0, invested=0.0,
                                 equity=100.0)
        day = START
        for values in values_by_year:
            for v in values:
                report.equity_curve.append((day, v))
                day += timedelta(days=1)
            day = datetime(day.year + 1, 1, 1, tzinfo=timezone.utc)
        return report

    def test_one_row_per_year_measured_from_the_prior_close(self):
        # Year 1 flat at 100; year 2 rises to 110; year 3 falls to 99.
        report = self._report([[100.0] * 250, [105.0] * 125 + [110.0] * 125,
                               [99.0] * 250])
        periods = walk_forward_years(report)
        self.assertEqual([p.label for p in periods], ["2020", "2021", "2022"])
        self.assertAlmostEqual(periods[0].total_return, 0.0)
        self.assertAlmostEqual(periods[1].total_return, 0.10)
        self.assertAlmostEqual(periods[2].total_return, 99.0 / 110.0 - 1.0)
        self.assertAlmostEqual(periods[2].max_drawdown, 99.0 / 110.0 - 1.0)

    def test_the_summary_is_a_distribution_not_an_average(self):
        report = self._report([[100.0] * 250, [120.0] * 250, [90.0] * 250,
                               [95.0] * 250])
        summary = summarize_periods(walk_forward_years(report))
        self.assertEqual(summary["periods"], 4)
        self.assertIn("worst_return", summary)
        self.assertIn("share_positive", summary)
        self.assertEqual(summary["worst_period"], "2022")
        self.assertAlmostEqual(summary["share_positive"], 0.5)

    def test_partial_years_are_flagged_and_excluded_from_the_summary(self):
        report = self._report([[100.0] * 250, [110.0] * 30])
        periods = walk_forward_years(report)
        self.assertIn("(partial)", period_table(periods))
        self.assertEqual(summarize_periods(periods)["periods"], 1)

    def test_refit_is_refused_rather_than_faked(self):
        with self.assertRaises(NotImplementedError):
            walk_forward_years(self._report([[100.0] * 10]), refit=lambda d: None)


class TheRegistry(unittest.TestCase):
    def test_related_before_counts_the_family(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "reg.jsonl"
            a = record_experiment("exits", "h1", {}, ["decade"], "r", "rejected",
                                  "why", path=path)
            b = record_experiment("exits", "h2", {}, ["decade"], "r", "rejected",
                                  "why", path=path)
            c = record_experiment("entries", "h3", {}, ["decade"], "r", "accepted",
                                  "why", evidence="strong", path=path)
            self.assertEqual((a["related_before"], b["related_before"],
                              c["related_before"]), (0, 1, 0))
            self.assertEqual(related_before("exits", path), 2)
            self.assertEqual([r["id"] for r in load_registry(path)],
                             ["EXP-0001", "EXP-0002", "EXP-0003"])

    def test_contamination_is_recorded_per_dataset(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "reg.jsonl"
            record_experiment("x", "h", {}, ["decade", "thirty_year"], "r",
                              "rejected", "why", path=path)
            record_experiment("y", "h", {}, ["decade"], "r", "rejected", "why",
                              path=path)
            counts = contamination_summary(path)
            self.assertEqual(counts["decade"], 2)
            self.assertEqual(counts["thirty_year"], 1)
            self.assertEqual(counts["forward"], 0)

    def test_it_refuses_unknown_datasets_and_bad_decisions(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "reg.jsonl"
            with self.assertRaises(ValueError):
                record_experiment("x", "h", {}, ["mars"], "r", "rejected", "why",
                                  path=path)
            with self.assertRaises(ValueError):
                record_experiment("x", "h", {}, ["decade"], "r", "shipped-ish",
                                  "why", path=path)

    def test_the_committed_registry_is_well_formed_and_forward_is_clean(self):
        rows = load_registry()
        self.assertGreater(len(rows), 30, "the back-fill has not been run")
        for row in rows:
            for key in ("id", "family", "related_before", "decision", "evidence",
                        "contaminated"):
                self.assertIn(key, row)
        self.assertEqual(contamination_summary()["forward"], 0,
                         "an experiment claims to have used forward data")
        self.assertEqual(DATASETS["forward"]["status"], "clean")


class DeflatedSharpe(unittest.TestCase):
    def test_more_trials_lower_the_probability(self):
        report = PortfolioReport(starting_cash=100.0, cash=0.0, invested=0.0,
                                 equity=100.0)
        value = 100.0
        for i in range(600):
            value *= 1.0 + (0.0012 if i % 5 else -0.0025)
            report.equity_curve.append((START + timedelta(days=i), value))
        one = deflated_sharpe(report, trials=1)
        forty = deflated_sharpe(report, trials=40)
        self.assertIsNotNone(one)
        self.assertIsNotNone(forty)
        self.assertLess(forty, one)


if __name__ == "__main__":
    unittest.main()
