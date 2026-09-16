"""Phase 5. The research track cannot reach the frozen experiment.

The dangerous coupling is not obvious. Track A derives its freeze date
from the production registry as the last row whose decision was
`accepted` or `reverted`. A Phase 5 experiment written into that file with
either decision would move the freeze, reset the 20-session embargo, and
invalidate the clean forward record. The first class below exists to make
that impossible to do by accident.

The rest asserts the properties the research itself depends on: that the
as-of engine uses the exchange clock rather than the calendar date, that
features cannot see past their own bar, and that a candidate which earns
more by risking more is flagged rather than ranked first.
"""

import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.data import Bar
from event_aware_trader.phase5 import asof, ledger
from event_aware_trader.phase5.features import (
    MarketContext, TradeAnatomy, anatomise, bucket, market_context, split_by)
from event_aware_trader.phase5.metrics import (
    annualised_volatility, compare, measure, modelled_costs, turnover,
    yearly_returns)
from event_aware_trader.purge import freeze_date
from event_aware_trader.risk import CostModel

FREEZE = date(2026, 9, 11)
PRODUCTION_ROWS = [
    {"when": "2026-09-10", "decision": "measured"},
    {"when": "2026-09-11", "decision": "accepted"},
    {"when": "2026-09-14", "decision": "rejected"},
]


def experiment(**kw):
    base = dict(
        hypothesis="a filter helps", configuration={"filter": "news"},
        dataset="decade", date_range="2016-2026", universe="230 US equities",
        costs="2bps half spread + 4bps slippage", execution_assumptions="market on close",
        information_sources=["alpaca/benzinga"], trials=1,
        metrics={"cagr": 0.05, "max_drawdown": -0.11},
        baseline_metrics={"cagr": 0.04, "max_drawdown": -0.11},
        validation_methodology="none yet", leakage_risks=["vendor revisions"],
        conclusion="promising", verdict="research_evidence",
        suitable_for_further_testing=True)
    base.update(kw)
    return ledger.Experiment(**base)


# ---------------------------------------------------------------------------
# The coupling that would matter
# ---------------------------------------------------------------------------

class TheResearchLedgerCannotMoveTheFreeze(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "phase5.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_ledger_is_not_the_production_registry(self):
        from event_aware_trader.research import REGISTRY
        self.assertNotEqual(Path(ledger.LEDGER).resolve(),
                            Path(REGISTRY).resolve())
        self.assertFalse(ledger.touches_frozen_registry(ledger.LEDGER))

    def test_recording_research_leaves_the_frozen_freeze_date_alone(self):
        before = freeze_date(PRODUCTION_ROWS)
        for i in range(5):
            ledger.record(experiment(hypothesis="try {0}".format(i)), self.path)
        self.assertEqual(freeze_date(PRODUCTION_ROWS), before)
        self.assertEqual(before, FREEZE)

    def test_research_rows_are_not_shaped_like_registry_rows(self):
        """A research row must not be readable as a config-changing decision."""
        row = ledger.record(experiment(), self.path)
        self.assertNotIn("decision", row)
        self.assertEqual(freeze_date([row]), None)

    def test_no_research_verdict_can_accept_anything(self):
        from event_aware_trader.purge import CONFIG_CHANGING
        self.assertEqual(set(ledger.VERDICTS) & set(CONFIG_CHANGING), set())

    def test_an_unknown_verdict_is_refused(self):
        with self.assertRaises(ValueError):
            experiment(verdict="accepted")


class TheLedgerKeepsFailures(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "phase5.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_duplicate_id_is_refused_rather_than_overwriting(self):
        ledger.record(experiment(id="P5-0001"), self.path)
        with self.assertRaises(ValueError):
            ledger.record(experiment(id="P5-0001", conclusion="better!"),
                          self.path)

    def test_a_failed_experiment_survives_a_later_success(self):
        ledger.record(experiment(verdict="rejected", conclusion="no effect"),
                      self.path)
        ledger.record(experiment(verdict="research_evidence"), self.path)
        rows = ledger.load(self.path)
        self.assertEqual([r["verdict"] for r in rows],
                         ["rejected", "research_evidence"])

    def test_the_difference_from_baseline_is_computed_not_typed(self):
        row = ledger.record(experiment(), self.path)
        self.assertAlmostEqual(row["difference_from_baseline"]["cagr"], 0.01)
        self.assertAlmostEqual(row["difference_from_baseline"]["max_drawdown"],
                               0.0)

    def test_the_trial_count_accumulates_across_experiments(self):
        ledger.record(experiment(trials=12), self.path)
        ledger.record(experiment(trials=7), self.path)
        self.assertEqual(ledger.total_trials(self.path), 19)

    def test_an_experiment_evaluates_at_least_one_configuration(self):
        with self.assertRaises(ValueError):
            experiment(trials=0)


# ---------------------------------------------------------------------------
# The clock. Same date is not the same thing as available.
# ---------------------------------------------------------------------------

class TheDecisionClock(unittest.TestCase):
    def test_summer_decisions_are_at_1945_utc(self):
        self.assertEqual(asof.decision_timestamp(date(2024, 7, 10)),
                         datetime(2024, 7, 10, 19, 45, tzinfo=timezone.utc))

    def test_winter_decisions_are_at_2045_utc(self):
        self.assertEqual(asof.decision_timestamp(date(2024, 1, 10)),
                         datetime(2024, 1, 10, 20, 45, tzinfo=timezone.utc))

    def test_the_pre_2007_daylight_saving_rule_is_used_for_old_sessions(self):
        """In 2000, March was still standard time; today's rule says summer."""
        self.assertEqual(asof.decision_timestamp(date(2000, 3, 20)).hour, 20)
        self.assertEqual(asof.decision_timestamp(date(2000, 5, 20)).hour, 19)

    def test_a_story_published_after_the_close_is_not_available_that_day(self):
        day = date(2024, 7, 10)
        after_close = datetime(2024, 7, 10, 21, 30, tzinfo=timezone.utc)
        archive = asof.Archive([item("1", after_close, ["AAA"])])
        snap = archive.snapshot(asof.decision_timestamp(day), ["AAA"])
        self.assertEqual(snap.items, [])

    def test_a_story_published_before_the_decision_is_available(self):
        day = date(2024, 7, 10)
        before = datetime(2024, 7, 10, 13, 40, tzinfo=timezone.utc)
        archive = asof.Archive([item("1", before, ["AAA"])])
        snap = archive.snapshot(asof.decision_timestamp(day), ["AAA"])
        self.assertEqual(len(snap.items), 1)

    def test_an_item_exactly_at_the_decision_instant_is_excluded(self):
        moment = asof.decision_timestamp(date(2024, 7, 10))
        archive = asof.Archive([item("1", moment, ["AAA"])])
        self.assertEqual(archive.snapshot(moment, ["AAA"]).items, [])

    def test_items_older_than_the_lookback_are_excluded(self):
        moment = asof.decision_timestamp(date(2024, 7, 10))
        old = moment - timedelta(days=10)
        archive = asof.Archive([item("1", old, ["AAA"])])
        self.assertEqual(
            archive.snapshot(moment, ["AAA"], lookback_hours=72).items, [])


def item(ident, published, symbols, source="benzinga", revised=False,
         usable=True):
    return asof.NewsItem(
        item_id=ident, source=source, tier=asof.tier_for(source),
        published_at=published.isoformat(), retrieved_at=None,
        symbols=[s.upper() for s in symbols], headline="h " + ident,
        revised=revised, usable=usable)


class TheInformationHierarchy(unittest.TestCase):
    def test_primary_sources_outrank_news_which_outranks_commentary(self):
        self.assertEqual(asof.tier_for("sec"), asof.TIER1)
        self.assertEqual(asof.tier_for("reuters"), asof.TIER2)
        self.assertEqual(asof.tier_for("seekingalpha"), asof.TIER3)
        self.assertEqual(asof.tier_for("reddit"), asof.TIER4)

    def test_an_unrecognised_vendor_is_not_assumed_reputable(self):
        self.assertEqual(asof.tier_for("some-blog"), asof.TIER3)

    def test_a_blank_vendor_takes_the_aggregators_tier_and_is_marked(self):
        parsed = asof.from_alpaca({"id": 1, "source": "", "symbols": ["AAA"],
                                   "created_at": "2024-07-10T13:00:00Z",
                                   "updated_at": "2024-07-10T13:00:00Z"})
        self.assertEqual(parsed.source, asof.UNATTRIBUTED)
        self.assertEqual(parsed.tier, asof.TIER2)

    def test_filtering_by_tier_keeps_only_what_is_good_enough(self):
        snap = asof.Snapshot(as_of=datetime.now(timezone.utc), items=[
            item("1", datetime.now(timezone.utc), ["AAA"], source="sec"),
            item("2", datetime.now(timezone.utc), ["AAA"], source="reddit")])
        self.assertEqual(len(snap.by_tier(asof.TIER2)), 1)


class VendorRevisionsAreTreatedAsALeakChannel(unittest.TestCase):
    def test_a_later_update_marks_the_item_revised(self):
        parsed = asof.from_alpaca({
            "id": 9, "source": "benzinga", "symbols": ["AAA"],
            "created_at": "2024-07-10T13:00:00Z",
            "updated_at": "2024-07-10T17:00:00Z"})
        self.assertTrue(parsed.revised)

    def test_a_second_of_jitter_is_not_a_revision(self):
        parsed = asof.from_alpaca({
            "id": 9, "source": "benzinga", "symbols": ["AAA"],
            "created_at": "2024-07-10T13:00:00Z",
            "updated_at": "2024-07-10T13:00:01Z"})
        self.assertFalse(parsed.revised)

    def test_an_item_with_no_timestamp_is_stored_unusable_not_dropped(self):
        parsed = asof.from_alpaca({"id": 9, "source": "benzinga",
                                   "symbols": ["AAA"], "created_at": None})
        self.assertFalse(parsed.usable)
        self.assertIn("timestamp", parsed.unusable_reason)

    def test_an_unusable_item_never_reaches_a_snapshot(self):
        moment = datetime(2024, 7, 10, 19, 45, tzinfo=timezone.utc)
        archive = asof.Archive([item("1", moment - timedelta(hours=2), ["AAA"],
                                     usable=False)])
        self.assertEqual(archive.snapshot(moment, ["AAA"]).items, [])

    def test_revised_items_can_be_excluded_from_a_count(self):
        moment = datetime(2024, 7, 10, 19, 45, tzinfo=timezone.utc)
        archive = asof.Archive([
            item("1", moment - timedelta(hours=2), ["AAA"]),
            item("2", moment - timedelta(hours=1), ["AAA"], revised=True)])
        snap = archive.snapshot(moment, ["AAA"])
        self.assertEqual(snap.count(), 2)
        self.assertEqual(snap.count(exclude_revised=True), 1)

    def test_a_story_tagged_with_many_symbols_can_be_excluded(self):
        moment = datetime(2024, 7, 10, 19, 45, tzinfo=timezone.utc)
        archive = asof.Archive([
            item("1", moment - timedelta(hours=2), ["AAA"]),
            item("2", moment - timedelta(hours=1),
                 ["AAA", "B", "C", "D", "E", "F", "G"])])
        snap = archive.snapshot(moment, ["AAA"])
        self.assertEqual(snap.count(max_symbols=5), 1)


class TheQualityReportSaysUnknownWhenItDoesNotKnow(unittest.TestCase):
    def test_every_question_is_answered_or_marked_unknown(self):
        archive = asof.Archive([item("1", datetime(2024, 7, 10, 12,
                                                   tzinfo=timezone.utc), ["AAA"])])
        report = asof.quality_report(archive)
        self.assertEqual(sorted(report), sorted(asof.QUESTIONS))
        for question in ("already reflected in the price",
                         "survives out-of-sample testing",
                         "improves results after costs"):
            self.assertEqual(report[question]["answer"], "UNKNOWN")


# ---------------------------------------------------------------------------
# Features cannot see past their own bar
# ---------------------------------------------------------------------------

def bars(closes, start=date(2020, 1, 1), volume=1_000_000):
    out, day = [], start
    for close in closes:
        while day.weekday() >= 5:
            day += timedelta(days=1)
        out.append(Bar(timestamp=datetime.combine(day, datetime.min.time(),
                                                  timezone.utc),
                       open=close, high=close * 1.01, low=close * 0.99,
                       close=close, volume=volume))
        day += timedelta(days=1)
    return out


class MarketContextCannotSeeTheFuture(unittest.TestCase):
    def test_appending_later_bars_does_not_change_an_earlier_context(self):
        base = bars([100.0 + i for i in range(260)])
        extended = base + bars([500.0] * 40, start=date(2021, 3, 1))
        a = market_context(base)
        b = market_context(extended)
        day = base[-1].timestamp.date()
        self.assertEqual(a[day].drawdown, b[day].drawdown)
        self.assertEqual(a[day].above_ma200, b[day].above_ma200)
        self.assertEqual(a[day].volatility_20, b[day].volatility_20)

    def test_the_running_high_is_cumulative_not_the_whole_series_high(self):
        rising = bars([100.0 + i for i in range(250)])
        ctx = market_context(rising)
        # On a monotonically rising series every day IS the high.
        self.assertAlmostEqual(ctx[rising[100].timestamp.date()].drawdown, 0.0)

    def test_a_later_crash_does_not_retroactively_create_a_drawdown(self):
        rising = bars([100.0 + i for i in range(250)])
        crashed = rising + bars([50.0] * 20, start=date(2021, 3, 1))
        day = rising[200].timestamp.date()
        self.assertAlmostEqual(market_context(rising)[day].drawdown,
                               market_context(crashed)[day].drawdown)


class Trade:
    def __init__(self, symbol, entry, exit_, r=0.5, pnl=100.0,
                 reason="reverted", held=9):
        self.symbol = symbol
        self.entry_time = datetime.combine(entry, datetime.min.time(),
                                           timezone.utc)
        self.exit_time = datetime.combine(exit_, datetime.min.time(),
                                          timezone.utc)
        self.r_multiple = r
        self.net_pnl = pnl
        self.exit_reason = reason
        self.bars_held = held
        self.quantity = 10.0
        self.entry_price = 100.0
        self.exit_price = 101.0


class AnatomyUsesOnlyPriorBars(unittest.TestCase):
    def setUp(self):
        self.series = {"AAA": bars([100.0 + i * 0.1 for i in range(260)]),
                       "SPY": bars([400.0 + i * 0.2 for i in range(260)])}
        self.market = market_context(self.series["SPY"])

    def test_a_future_price_cannot_change_a_recorded_feature(self):
        day = self.series["AAA"][250].timestamp.date()
        trade = Trade("AAA", day, day + timedelta(days=9))
        before = anatomise([trade], self.series, self.market, {})[0]
        longer = dict(self.series)
        longer["AAA"] = self.series["AAA"] + bars([9999.0] * 5,
                                                  start=date(2021, 3, 1))
        after = anatomise([trade], longer, self.market, {})[0]
        self.assertEqual(before.features(), after.features())

    def test_outcomes_are_not_returned_as_features(self):
        day = self.series["AAA"][250].timestamp.date()
        trade = Trade("AAA", day, day + timedelta(days=9))
        row = anatomise([trade], self.series, self.market, {})[0]
        for outcome in ("r_multiple", "net_pnl", "exit_reason", "bars_held"):
            self.assertNotIn(outcome, row.features())

    def test_the_stop_rate_is_reported_on_every_bucket(self):
        rows = [TradeAnatomy("A", "2024-01-02", "2024-01-09", "tech",
                             exit_reason="stop"),
                TradeAnatomy("B", "2024-01-02", "2024-01-09", "tech",
                             exit_reason="reverted", net_pnl=10.0)]
        self.assertAlmostEqual(bucket(rows, "x").stop_rate, 0.5)

    def test_rows_missing_an_attribute_are_counted_not_dropped(self):
        rows = [TradeAnatomy("A", "2024-01-02", "2024-01-09", "t",
                             atr_fraction=0.01),
                TradeAnatomy("B", "2024-01-02", "2024-01-09", "t",
                             atr_fraction=None)]
        buckets = split_by(rows, "atr_fraction", [0.02])
        self.assertEqual(sum(b.trades for b in buckets), 2)
        self.assertTrue(any("unavailable" in b.label for b in buckets))


# ---------------------------------------------------------------------------
# Metrics that spoil a story
# ---------------------------------------------------------------------------

class Report:
    def __init__(self, curve, trades=(), cash=None, starting_cash=100_000.0):
        self.equity_curve = curve
        self.cash_curve = cash if cash is not None else [(s, v * 0.5)
                                                         for s, v in curve]
        self.trades = list(trades)
        self.starting_cash = starting_cash
        self.cash = curve[-1][1] if curve else starting_cash
        self.invested = 0.0
        self.equity = curve[-1][1] if curve else starting_cash
        self.open_positions = []
        self.days_simulated = len(curve)


def curve(values, start=date(2020, 1, 1)):
    out, day = [], start
    for v in values:
        out.append((datetime.combine(day, datetime.min.time(), timezone.utc), v))
        day += timedelta(days=1)
    return out


class TheMetricsRefuseToFlatter(unittest.TestCase):
    def test_a_candidate_that_buys_return_with_risk_is_flagged(self):
        from event_aware_trader.phase5.metrics import FullMetrics
        baseline = FullMetrics("base", cagr=0.05, annualised_volatility=0.08,
                               max_drawdown=-0.10)
        risky = FullMetrics("risky", cagr=0.09, annualised_volatility=0.20,
                            max_drawdown=-0.30)
        result = compare(risky, baseline)
        self.assertTrue(result["return_bought_with_risk"])
        self.assertEqual(len(result["higher_risk"]), 2)

    def test_a_genuinely_better_candidate_is_not_flagged(self):
        from event_aware_trader.phase5.metrics import FullMetrics
        baseline = FullMetrics("base", cagr=0.05, annualised_volatility=0.08,
                               max_drawdown=-0.10)
        better = FullMetrics("better", cagr=0.07, annualised_volatility=0.075,
                             max_drawdown=-0.09)
        result = compare(better, baseline)
        self.assertEqual(result["higher_risk"], [])
        self.assertFalse(result["return_bought_with_risk"])

    def test_a_partial_final_year_is_kept_rather_than_dropped(self):
        values = curve([100.0] * 400)
        years = yearly_returns(values)
        self.assertIn(2021, years)

    def test_volatility_is_annualised_from_daily_returns(self):
        import math
        values = curve([100.0 * (1.01 ** i) for i in range(300)])
        vol = annualised_volatility(values)
        self.assertLess(vol, 1e-6)          # constant growth has no variance

    def test_costs_are_reconstructed_from_round_trip_notional(self):
        trade = Trade("A", date(2024, 1, 2), date(2024, 1, 9))
        trade.quantity, trade.entry_price, trade.exit_price = 100.0, 50.0, 55.0
        # 6 bps total on (50 + 55) * 100 = 10500 -> 6.30
        self.assertAlmostEqual(modelled_costs([trade], CostModel()), 6.30,
                               places=6)

    def test_turnover_scales_with_the_length_of_the_run(self):
        trade = Trade("A", date(2024, 1, 2), date(2024, 1, 9))
        trade.quantity, trade.entry_price, trade.exit_price = 100.0, 50.0, 50.0
        one_year = Report(curve([100_000.0] * 252), [trade])
        two_years = Report(curve([100_000.0] * 504), [trade])
        self.assertAlmostEqual(turnover(one_year), 0.10, places=6)
        self.assertAlmostEqual(turnover(two_years), 0.05, places=6)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# The headline matcher, and what it admits it cannot do
# ---------------------------------------------------------------------------

class TheHeadlineMatcherIsHonestAboutBeingAMatcher(unittest.TestCase):
    def setUp(self):
        from event_aware_trader.phase5 import headline
        self.h = headline

    def test_the_macro_classifier_cannot_answer_a_single_stock_question(self):
        """The reason this module exists, asserted rather than asserted-to."""
        from event_aware_trader.events import classify_headline
        macro = classify_headline("Apple beats earnings estimates, raises guidance")
        self.assertEqual(macro.stance, "neutral")
        self.assertEqual(self.h.label(
            "Apple beats earnings estimates, raises guidance").direction,
            "favourable")

    def test_adverse_and_favourable_headlines_separate(self):
        self.assertTrue(self.h.label("Shares plunge after SEC probe").adverse)
        self.assertTrue(self.h.label("FDA approval granted").favourable)

    def test_a_headline_with_both_is_mixed_not_silently_resolved(self):
        got = self.h.label("Analyst upgrade but revenue misses")
        self.assertEqual(got.direction, "mixed")
        self.assertTrue(got.conflicted)

    def test_an_ordinary_headline_matches_nothing(self):
        self.assertEqual(self.h.label("Company to present at conference"
                                      ).direction, "none")

    def test_simple_negation_is_handled(self):
        self.assertEqual(self.h.label("Drug not approved").direction, "none")

    def test_negation_only_guards_the_term_it_precedes(self):
        """A documented limit. The matcher is a matcher, not a parser."""
        got = self.h.label("Company not approved for merger")
        self.assertEqual(got.direction, "favourable")
        self.assertEqual(got.bullish_hits, ["merger"])

    def test_summarise_reports_the_net_and_how_many_matched(self):
        counts = self.h.summarise(["Shares plunge", "FDA approval",
                                   "Company to present at conference"])
        self.assertEqual(counts["adverse"], 1)
        self.assertEqual(counts["favourable"], 1)
        self.assertEqual(counts["none"], 1)
        self.assertEqual(counts["net"], 0)
        self.assertEqual(counts["matched"], 2)
