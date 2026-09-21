"""Phase 4. The five observation gates, each asserted rather than asserted-to.

G19 clean-session integrity     fingerprint, append-only, isolation
G20 broker reconciliation       within documented tolerances, never corrected
G21 decision-time integrity     nothing later than `as_of` in the decision
G22 evaluation continuity       gaps are visible and counted, never filled
G23 no strategy modification    the frozen fingerprint is the Phase 3 one

Two habits carried from earlier phases. Every gate has at least one test
that makes it FAIL, because a gate never seen to fail has not been shown
to be a gate. And UNVERIFIED is tested as distinct from PASS: a check that
could not run must not report health.
"""

import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.data import Bar
from event_aware_trader.forward import (
    CleanObservation, ForwardDataLeak, FrozenConfigChanged, append_session,
    continuity, eligible_sessions, first_clean_session, frozen_fingerprint,
    is_eligible, is_protective, load_sessions, reconcile, unprotected_positions,
    verify_chain)
from event_aware_trader.verify_session import FAIL, PASS, UNVERIFIED, verify

# The fingerprint accepted at the end of Phase 3. G23 is the claim that this
# value does not move for the duration of the observation period, so it is
# written here as a literal: if any frozen parameter changes, this test
# fails and names the gate, instead of the evaluation silently continuing
# under a different configuration.
PHASE3_FINGERPRINT = (
    "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b")

FREEZE = date(2026, 9, 11)
REGISTRY = [{"when": "2026-09-11", "decision": "accepted"}]


def calendar(start=date(2026, 9, 1), n=60):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def observation(day, fingerprint=None, **kw):
    base = dict(
        session=day, as_of=day + "T20:05:00+00:00",
        config_fingerprint=fingerprint or frozen_fingerprint(),
        universe_size=230, signals=4, orders=2, fills=2, positions_held=2,
        exposure=0.40, cash=60_000.0, equity=100_000.0,
        transaction_costs=0.95, dividends_received=0.0,
        strategy_return=0.001, benchmark_return=0.002,
        positions=[{"symbol": "AAA", "quantity": 100, "market_value": 20_000.0},
                   {"symbol": "BBB", "quantity": 50, "market_value": 20_000.0}],
        exits=[])
    base.update(kw)
    return CleanObservation(**base)


STOP = {"type": "stop", "stop_price": 95.0, "side": "sell"}
TAKE_PROFIT = {"type": "limit", "stop_price": None, "side": "sell"}
ACCOUNT = {"equity": 100_000.0, "cash": 60_000.0}
POSITIONS = [{"symbol": "AAA", "market_value": 20_000.0},
             {"symbol": "BBB", "market_value": 20_000.0}]
PROTECTED = {"AAA": [STOP], "BBB": [STOP]}


def spy_bar(day):
    return Bar(timestamp=datetime.combine(day, datetime.min.time(),
                                          timezone.utc),
               open=500.0, high=505.0, low=499.0, close=502.0, volume=1e8)


# ---------------------------------------------------------------------------
# G19 - clean-session integrity
# ---------------------------------------------------------------------------

class G19CleanSessionIntegrity(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "forward.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_session_before_the_embargo_expires_is_not_eligible(self):
        days = calendar(n=10)                       # only a few after freeze
        self.assertIsNone(first_clean_session(days, REGISTRY))
        self.assertFalse(is_eligible(days[-1], days, REGISTRY))

    def test_eligibility_starts_after_exactly_the_embargo_length(self):
        days = calendar(n=60)
        after = [d for d in days if d > FREEZE]
        start = first_clean_session(days, REGISTRY)
        self.assertEqual(start, after[20])          # 20 embargoed, then clean
        self.assertFalse(is_eligible(after[19], days, REGISTRY))
        self.assertTrue(is_eligible(after[20], days, REGISTRY))

    def test_the_start_date_moves_with_the_calendar_not_with_a_constant(self):
        """Derived, not hard-coded: a holiday shifts the first clean day."""
        days = calendar(n=60)
        holiday = [d for d in days if d > FREEZE][5]
        without = [d for d in days if d != holiday]
        self.assertNotEqual(first_clean_session(days, REGISTRY),
                            first_clean_session(without, REGISTRY))

    def test_a_foreign_fingerprint_is_refused(self):
        with self.assertRaises(FrozenConfigChanged):
            append_session(observation("2026-10-09", "beef" * 16), self.path)

    def test_a_session_cannot_be_recorded_twice(self):
        append_session(observation("2026-10-09"), self.path)
        with self.assertRaises(ForwardDataLeak):
            append_session(observation("2026-10-09", equity=1.0), self.path)

    def test_an_edited_record_breaks_the_chain(self):
        for day in ("2026-10-09", "2026-10-12", "2026-10-13"):
            append_session(observation(day), self.path)
        rows = [json.loads(l) for l in self.path.read_text().splitlines()]
        rows[1]["payload"]["equity"] = 250_000.0
        self.path.write_text("".join(json.dumps(r, sort_keys=True) + "\n"
                                     for r in rows))
        check = verify_chain(self.path)
        self.assertFalse(check["intact"])
        self.assertEqual(check["broken_at"], 1)

    def test_clean_observations_still_cannot_reach_research(self):
        """Re-asserted here so it runs at every checkpoint, not once."""
        from event_aware_trader.research import production_report
        with self.assertRaises(ForwardDataLeak):
            production_report({"AAA": [observation("2026-10-09")]})


# ---------------------------------------------------------------------------
# G20 - broker reconciliation
# ---------------------------------------------------------------------------

class G20BrokerReconciliation(unittest.TestCase):
    def test_a_penny_of_rounding_is_within_tolerance(self):
        r = reconcile({"equity": 100_000.00, "cash": 60_000.00,
                       "positions_held": 2},
                      {"equity": 100_000.01, "cash": 60_000.00,
                       "positions_held": 2})
        self.assertTrue(r.ok)

    def test_a_real_gap_fails_and_names_the_field(self):
        r = reconcile({"equity": 100_000.0, "cash": 60_000.0,
                       "positions_held": 2},
                      {"equity": 98_500.0, "cash": 60_000.0,
                       "positions_held": 3})
        self.assertFalse(r.ok)
        self.assertEqual(sorted(c["check"] for c in r.failures),
                         ["equity", "positions_held"])

    def test_position_counts_have_no_tolerance(self):
        r = reconcile({"equity": 100_000.0, "cash": 60_000.0,
                       "positions_held": 5},
                      {"equity": 100_000.0, "cash": 60_000.0,
                       "positions_held": 6})
        self.assertFalse(r.ok)

    def test_reconciliation_reports_and_does_not_correct(self):
        recorded = {"equity": 100_000.0, "cash": 60_000.0, "positions_held": 2}
        reconcile(recorded, {"equity": 98_000.0, "cash": 59_000.0,
                             "positions_held": 2})
        self.assertEqual(recorded["equity"], 100_000.0)
        self.assertEqual(recorded["cash"], 60_000.0)

    def test_a_take_profit_leg_is_not_protection(self):
        """It reserves the shares and stops nothing on the way down."""
        self.assertFalse(is_protective(TAKE_PROFIT))
        self.assertTrue(is_protective(STOP))
        self.assertEqual(
            unprotected_positions(POSITIONS, {"AAA": [STOP],
                                              "BBB": [TAKE_PROFIT]}),
            ["BBB"])

    def test_crypto_and_the_parking_etf_are_exempt(self):
        positions = POSITIONS + [{"symbol": "BTC/USD"}, {"symbol": "SGOV"}]
        self.assertEqual(unprotected_positions(positions, PROTECTED), [])

    def test_a_naked_position_fails_the_session_verification(self):
        v = verify(observation("2026-10-09"), POSITIONS,
                   {"AAA": [STOP]}, [], ACCOUNT, [], [])
        self.assertFalse(v.ok)
        self.assertIn("every position protected", [c.name for c in v.failures])

    def test_unrecorded_broker_fees_fail_the_session(self):
        fees = [{"date": "2026-10-09", "net_amount": "-4.20"}]
        v = verify(observation("2026-10-09"), POSITIONS, PROTECTED, [],
                   ACCOUNT, fees, [])
        self.assertIn("transaction costs recorded",
                      [c.name for c in v.failures])

    def test_a_dividend_that_was_paid_must_be_recorded(self):
        divs = [{"date": "2026-10-09", "net_amount": "31.40"}]
        v = verify(observation("2026-10-09"), POSITIONS, PROTECTED, [],
                   ACCOUNT, [{"date": "2026-10-09", "net_amount": "-0.95"}],
                   divs)
        self.assertIn("dividends recorded", [c.name for c in v.failures])


# ---------------------------------------------------------------------------
# G21 - decision-time integrity
# ---------------------------------------------------------------------------

class G21DecisionTimeIntegrity(unittest.TestCase):
    def good(self, **kw):
        return verify(observation("2026-10-09", **kw), POSITIONS, PROTECTED,
                      [], ACCOUNT, [{"date": "2026-10-09",
                                     "net_amount": "-0.95"}], [],
                      benchmark_bar=spy_bar(date(2026, 10, 9)),
                      universe=["AAA", "BBB"],
                      now=datetime(2026, 10, 9, 21, tzinfo=timezone.utc))

    def test_a_coherent_session_passes_every_runnable_check(self):
        v = self.good()
        self.assertTrue(v.ok, v.as_dict()["failed"])
        self.assertEqual(v.unverified, [])

    def test_a_decision_stamped_in_the_future_fails(self):
        v = self.good(as_of="2026-10-10T20:05:00+00:00")
        self.assertIn("decision timestamp coherent",
                      [c.name for c in v.failures])

    def test_a_decision_stamped_before_its_session_fails(self):
        v = self.good(as_of="2026-10-08T20:05:00+00:00")
        self.assertIn("decision timestamp coherent",
                      [c.name for c in v.failures])

    def test_a_benchmark_from_another_day_fails(self):
        v = verify(observation("2026-10-09"), POSITIONS, PROTECTED, [],
                   ACCOUNT, [{"date": "2026-10-09", "net_amount": "-0.95"}],
                   [], benchmark_bar=spy_bar(date(2026, 10, 8)))
        self.assertIn("benchmark matches the session date",
                      [c.name for c in v.failures])

    def test_an_unsupplied_benchmark_is_unverified_not_passed(self):
        v = verify(observation("2026-10-09"), POSITIONS, PROTECTED, [],
                   ACCOUNT, [{"date": "2026-10-09", "net_amount": "-0.95"}],
                   [], now=datetime(2026, 10, 9, 21, tzinfo=timezone.utc))
        names = [c.name for c in v.unverified]
        self.assertIn("benchmark matches the session date", names)
        self.assertIn("orders within the frozen universe", names)
        self.assertTrue(v.ok)          # unverified is not a failure

    def test_an_off_universe_order_fails(self):
        orders = [{"symbol": "MEME", "submitted_at": "2026-10-09T19:45:00Z",
                   "quantity": 10}]
        v = verify(observation("2026-10-09"), POSITIONS, PROTECTED, orders,
                   ACCOUNT, [{"date": "2026-10-09", "net_amount": "-0.95"}],
                   [], universe=["AAA", "BBB"])
        self.assertIn("orders within the frozen universe",
                      [c.name for c in v.failures])

    def test_an_oversized_position_fails_the_concentration_cap(self):
        v = verify(observation("2026-10-09", positions=[
                       {"symbol": "AAA", "market_value": 35_000.0}]),
                   POSITIONS, PROTECTED, [], ACCOUNT,
                   [{"date": "2026-10-09", "net_amount": "-0.95"}], [])
        self.assertIn("concentration within the frozen cap",
                      [c.name for c in v.failures])

    def test_a_participation_breach_fails_when_volume_is_known(self):
        orders = [{"symbol": "AAA", "submitted_at": "2026-10-09T19:45:00Z",
                   "quantity": 1000, "filled_quantity": 1000,
                   "filled_avg_price": 100.0}]
        v = verify(observation("2026-10-09"), POSITIONS, PROTECTED, orders,
                   ACCOUNT, [{"date": "2026-10-09", "net_amount": "-0.95"}],
                   [], universe=["AAA", "BBB"],
                   adv_by_symbol={"AAA": 1_000_000.0})   # 10% of ADV
        self.assertIn("participation limit respected",
                      [c.name for c in v.failures])

    def test_an_unknown_exit_reason_fails(self):
        v = verify(observation("2026-10-09",
                               exits=[{"symbol": "AAA", "reason": "hunch"}]),
                   POSITIONS, PROTECTED, [], ACCOUNT,
                   [{"date": "2026-10-09", "net_amount": "-0.95"}], [])
        self.assertIn("exit reasons recognised", [c.name for c in v.failures])


# ---------------------------------------------------------------------------
# G22 - evaluation continuity
# ---------------------------------------------------------------------------

class G22EvaluationContinuity(unittest.TestCase):
    def setUp(self):
        self.days = calendar(n=60)
        self.eligible = eligible_sessions(self.days, REGISTRY)

    def test_no_session_is_eligible_before_the_embargo_expires(self):
        self.assertEqual(eligible_sessions(calendar(n=10), REGISTRY), [])

    def test_a_complete_record_reports_complete(self):
        recorded = [observation(d.isoformat()) for d in self.eligible]
        state = continuity(recorded, self.days, REGISTRY)
        self.assertTrue(state["complete"])
        self.assertEqual(state["missing"], [])
        self.assertEqual(state["eligible"], len(self.eligible))

    def test_a_missed_session_is_named_not_filled(self):
        recorded = [observation(d.isoformat()) for d in self.eligible
                    if d != self.eligible[3]]
        state = continuity(recorded, self.days, REGISTRY)
        self.assertFalse(state["complete"])
        self.assertEqual(state["missing"],
                         [self.eligible[3].isoformat()])
        self.assertEqual(state["recorded"], len(self.eligible) - 1)

    def test_a_session_recorded_before_eligibility_is_flagged(self):
        early = [d for d in self.days if d > FREEZE][2]
        recorded = ([observation(early.isoformat())] +
                    [observation(d.isoformat()) for d in self.eligible])
        state = continuity(recorded, self.days, REGISTRY)
        self.assertFalse(state["complete"])
        self.assertEqual(state["recorded_before_eligibility"],
                         [early.isoformat()])

    def test_an_empty_record_before_eligibility_is_not_an_error(self):
        state = continuity([], calendar(n=10), REGISTRY)
        self.assertEqual(state["eligible"], 0)
        self.assertTrue(state["complete"])
        self.assertIsNone(state["first_eligible"])


# ---------------------------------------------------------------------------
# G23 - no strategy modification
# ---------------------------------------------------------------------------

class G23NoStrategyModification(unittest.TestCase):
    def test_the_frozen_fingerprint_is_still_the_one_phase_3_accepted(self):
        self.assertEqual(
            frozen_fingerprint(), PHASE3_FINGERPRINT,
            "the frozen configuration has changed during the observation "
            "period. G23 fails: stop, investigate, and restart the "
            "evaluation rather than continuing under a new configuration.")

    def test_the_embargo_still_comes_from_the_strategys_holding_cap(self):
        from event_aware_trader.mean_reversion import MeanReversionConfig
        from event_aware_trader.purge import embargo_sessions
        self.assertEqual(embargo_sessions(),
                         MeanReversionConfig().max_holding_bars)

    def test_changing_a_frozen_parameter_is_visible_immediately(self):
        from unittest import mock
        from event_aware_trader import research
        moved = dict(research.PRODUCTION_CANDIDATE)
        moved["rule_exit_timing_haircut"] = 0.02
        with mock.patch.object(research, "PRODUCTION_CANDIDATE", moved):
            self.assertNotEqual(frozen_fingerprint(), PHASE3_FINGERPRINT)


# ---------------------------------------------------------------------------
# The recorder refuses rather than inventing
# ---------------------------------------------------------------------------

class TheRecorderRefusesRatherThanInventing(unittest.TestCase):
    def setUp(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import record_clean_session as rec
        self.rec = rec

    def test_a_session_with_no_completed_run_is_refused(self):
        rows = [{"at": "2026-10-09T13:31:00+00:00", "event": "hold",
                 "detail": {}}]
        with self.assertRaises(self.rec.NoSessionRecorded):
            self.rec.audit_facts(rows, date(2026, 10, 9))

    def test_signals_and_exits_come_from_the_audit_log(self):
        rows = [
            {"at": "2026-10-09T19:45:00+00:00", "event": "entry_window_open",
             "detail": {"symbols_with_todays_bar": 228}},
            {"at": "2026-10-09T19:46:00+00:00", "event": "live_model_ranking",
             "detail": {"considered": 6, "kept": 6}},
            {"at": "2026-10-09T19:47:00+00:00", "event": "entry",
             "detail": {"symbol": "AAA"}},
            {"at": "2026-10-09T19:48:00+00:00", "event": "exit",
             "detail": {"symbol": "BBB", "realized_pnl": 12.0,
                        "return_fraction": 0.001}},
            {"at": "2026-10-09T19:49:00+00:00",
             "event": "learned_from_external_exit",
             "detail": {"symbol": "CCC", "realized_pnl": -30.0,
                        "r_multiple": -0.4}},
            {"at": "2026-10-09T20:00:00+00:00", "event": "run_complete",
             "detail": {"entries": 1, "exits": 1, "held": 5, "halted": False,
                        "config_fingerprint": "a" * 64}},
        ]
        facts = self.rec.audit_facts(rows, date(2026, 10, 9))
        self.assertEqual(facts["effective_fingerprint"], "a" * 64)
        self.assertEqual(facts["signals"], 6)
        self.assertEqual(facts["universe_size"], 228)
        self.assertEqual([e["reason"] for e in facts["exits"]],
                         ["rule", "external"])
        self.assertEqual(facts["data_quality_issues"], [])

    def test_loop_failures_become_recorded_data_quality_issues(self):
        rows = [
            {"at": "2026-10-09T19:45:00+00:00", "event": "unpark_FAILED",
             "detail": {"error": "insufficient qty"}},
            {"at": "2026-10-09T20:00:00+00:00", "event": "run_complete",
             "detail": {"entries": 0, "exits": 0, "held": 5, "halted": True,
                        "config_fingerprint": "a" * 64}},
        ]
        facts = self.rec.audit_facts(rows, date(2026, 10, 9))
        self.assertEqual(len(facts["data_quality_issues"]), 2)
        self.assertTrue(any("halted" in i
                            for i in facts["data_quality_issues"]))

    def _run_complete(self, detail):
        return [{"at": "2026-10-09T20:00:00+00:00", "event": "run_complete",
                 "detail": detail}]

    def test_a_cycle_with_no_effective_fingerprint_is_flagged(self):
        """The stamp must come from the run, never from source defaults."""
        facts = self.rec.audit_facts(
            self._run_complete({"entries": 0, "held": 0, "halted": False}),
            date(2026, 10, 9))
        self.assertIsNone(facts["effective_fingerprint"])
        self.assertTrue(any("effective config_fingerprint" in i
                            for i in facts["data_quality_issues"]))

    def test_two_configurations_in_one_session_are_flagged(self):
        """A session that ran under two configs is not one observation."""
        rows = (self._run_complete({"halted": False,
                                    "config_fingerprint": "a" * 64})
                + [{"at": "2026-10-09T20:05:00+00:00", "event": "run_complete",
                    "detail": {"halted": False, "config_fingerprint": "b" * 64}}])
        facts = self.rec.audit_facts(rows, date(2026, 10, 9))
        self.assertTrue(any("more than one configuration" in i
                            for i in facts["data_quality_issues"]))

    def test_another_days_rows_are_not_counted(self):
        rows = [
            {"at": "2026-10-08T20:00:00+00:00", "event": "run_complete",
             "detail": {"halted": False}},
            {"at": "2026-10-09T19:46:00+00:00", "event": "live_model_ranking",
             "detail": {"considered": 3}},
            {"at": "2026-10-09T20:00:00+00:00", "event": "run_complete",
             "detail": {"halted": False}},
        ]
        self.assertEqual(self.rec.audit_facts(rows, date(2026, 10, 9))["runs"], 1)

    def test_counts_and_costs_come_from_the_brokers_own_feeds(self):
        got = self.rec.broker_facts(
            orders=[{"submitted_at": "2026-10-09T19:45:00Z"},
                    {"submitted_at": "2026-10-08T19:45:00Z"}],
            fills=[{"transaction_time": "2026-10-09T19:45:03Z"}],
            fees=[{"date": "2026-10-09", "net_amount": "-0.4959"}],
            dividends=[{"date": "2026-10-09", "net_amount": "31.40"}],
            session=date(2026, 10, 9))
        self.assertEqual(got["orders"], 1)
        self.assertEqual(got["fills"], 1)
        self.assertAlmostEqual(got["transaction_costs"], 0.4959)
        self.assertAlmostEqual(got["dividends_received"], 31.40)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# The checkpoint machinery itself
# ---------------------------------------------------------------------------

class CheckpointsRefuseBelowTheirThreshold(unittest.TestCase):
    def setUp(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import phase4_checkpoint as cp
        self.cp = cp

    def test_the_four_checkpoints_are_the_ones_the_protocol_names(self):
        self.assertEqual(
            {k: v[0] for k, v in self.cp.CHECKPOINTS.items()},
            {"A": 1, "B": 20, "C": 60, "D": 120})

    def test_descriptive_statistics_compound_rather_than_sum(self):
        days = ["2026-10-{0:02d}".format(9 + i) for i in range(3)]
        sessions = [observation(d, strategy_return=0.10, benchmark_return=0.05,
                                equity=100_000.0 * (1.1 ** (i + 1)))
                    for i, d in enumerate(days)]
        d = self.cp.descriptive(sessions)
        self.assertAlmostEqual(d["cumulative_strategy_return"], 0.331, places=6)
        self.assertAlmostEqual(d["cumulative_benchmark_return"], 0.157625,
                               places=6)

    def test_drawdown_is_measured_from_the_running_peak(self):
        self.assertAlmostEqual(
            self.cp.drawdown([100.0, 120.0, 90.0, 110.0]), -0.25, places=6)

    def test_a_report_never_contains_a_profitability_verdict(self):
        from event_aware_trader.purge import evaluation_window
        days = calendar(n=60)
        sessions = [observation(d.isoformat())
                    for d in eligible_sessions(days, REGISTRY)]
        text = self.cp.render(
            "C", sessions, continuity(sessions, days, REGISTRY),
            {"intact": True}, evaluation_window(REGISTRY, days),
            {"tests.test_forward_isolation": {"ok": True, "summary": "Ran 23"}},
            days)
        # The phrases appear only in the section that DENIES them, so the
        # assertion is about where they appear, not whether.
        self.assertIn("UNSUPPORTED BY THIS EVIDENCE", text)
        body, denied = text.split("## UNSUPPORTED BY THIS EVIDENCE", 1)
        for forbidden in ("is profitable", "beats the S&P", "outperforms the",
                          "superior", "annualised", "Sharpe ratio of"):
            self.assertNotIn(forbidden, body)
        self.assertIn("That the strategy is profitable.", denied)


# ---------------------------------------------------------------------------
# Haircut collection (Phase 4 §7) - collect now, report at ~30
# ---------------------------------------------------------------------------

class HaircutObservations(unittest.TestCase):
    def setUp(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import haircut_observations as hc
        self.hc = hc

    def rows(self, reason="reverted", last=100.0, order_id="o1"):
        return [{"at": "2026-10-09T19:50:00+00:00", "event": "exit",
                 "detail": {"symbol": "AAA", "exit_reason": reason,
                            "last": last, "quantity": 100,
                            "result": {"order_id": order_id}}}]

    def test_stop_exits_are_excluded(self):
        self.assertEqual(self.hc.triggers(self.rows(reason="stop")), [])

    def test_both_rule_exits_are_eligible(self):
        for reason in ("reverted", "time"):
            self.assertEqual(len(self.hc.triggers(self.rows(reason=reason))), 1)

    def test_an_exit_without_a_trigger_price_is_skipped_not_guessed(self):
        self.assertEqual(self.hc.triggers(self.rows(last=None)), [])

    def test_a_worse_fill_is_positive_slippage(self):
        self.assertAlmostEqual(self.hc.slippage(100.0, 99.0), 0.01)

    def test_a_better_fill_is_kept_as_negative_rather_than_clipped(self):
        self.assertAlmostEqual(self.hc.slippage(100.0, 100.5), -0.005)

    def test_partial_fills_are_volume_weighted(self):
        fills = [{"order_id": "o1", "qty": "25", "price": "99.00"},
                 {"order_id": "o1", "qty": "75", "price": "99.80"}]
        paired = self.hc.match_fills(self.hc.triggers(self.rows()), fills)
        self.assertEqual(len(paired), 1)
        self.assertAlmostEqual(paired[0]["fill_price"], 99.6, places=6)
        self.assertAlmostEqual(paired[0]["slippage"], 0.004, places=6)

    def test_an_unmatched_trigger_is_dropped_rather_than_assumed_clean(self):
        self.assertEqual(self.hc.match_fills(self.hc.triggers(self.rows()),
                                             []), [])

    def test_the_frozen_bound_is_the_phase_one_value(self):
        from event_aware_trader.research import PRODUCTION_CANDIDATE
        self.assertEqual(self.hc.FROZEN_HAIRCUT,
                         PRODUCTION_CANDIDATE["rule_exit_timing_haircut"])


# ---------------------------------------------------------------------------
# Exemptions found by running the verifier against a real session
# ---------------------------------------------------------------------------

class TheVerifierKnowsWhatIsNotAnEquityEntry(unittest.TestCase):
    """Both of these fired as false FAILs on the live 2026-09-15 account.

    A checker that fails every single session teaches the reader to skip
    its output, which is worse than not checking at all.
    """

    def base(self, orders):
        return verify(observation("2026-10-09"), POSITIONS, PROTECTED, orders,
                      ACCOUNT, [{"date": "2026-10-09", "net_amount": "-0.95"}],
                      [], universe=["AAA", "BBB"],
                      now=datetime(2026, 10, 9, 21, tzinfo=timezone.utc))

    def test_the_cash_parking_etf_is_not_an_off_universe_order(self):
        v = self.base([{"symbol": "SGOV", "submitted_at": "2026-10-09T19:45:00Z",
                        "quantity": 174.027637}])
        self.assertTrue(v.ok, v.as_dict()["failed"])

    def test_a_fractional_crypto_order_is_not_a_whole_share_breach(self):
        v = self.base([{"symbol": "BTC/USD", "submitted_at": "2026-10-09T19:45:00Z",
                        "quantity": 0.0183}])
        self.assertNotIn("whole-share equity orders",
                         [c.name for c in v.failures])

    def test_a_fractional_equity_order_is_still_a_breach(self):
        v = self.base([{"symbol": "AAA", "submitted_at": "2026-10-09T19:45:00Z",
                        "quantity": 10.5}])
        self.assertIn("whole-share equity orders", [c.name for c in v.failures])


class ParticipationUsesOnlyPriorVolume(unittest.TestCase):
    def setUp(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import record_clean_session as rec
        self.rec = rec

    def bars(self, volumes, start=date(2026, 9, 1)):
        out, d = [], start
        for v in volumes:
            while d.weekday() >= 5:
                d += timedelta(days=1)
            out.append(Bar(timestamp=datetime.combine(d, datetime.min.time(),
                                                      timezone.utc),
                           open=100.0, high=101.0, low=99.0, close=100.0,
                           volume=v))
            d += timedelta(days=1)
        return out

    def test_the_sessions_own_volume_is_excluded(self):
        """Its volume is not known when the order is sized."""
        bars = self.bars([1_000_000] * 20 + [500_000_000])
        session = bars[-1].timestamp.date()
        adv = self.rec.average_dollar_volume(bars, session)
        self.assertAlmostEqual(adv, 100.0 * 1_000_000, places=2)

    def test_no_prior_bars_yields_no_average_rather_than_zero(self):
        bars = self.bars([1_000_000])
        self.assertIsNone(
            self.rec.average_dollar_volume(bars, bars[0].timestamp.date()))

    def test_only_filled_equities_are_looked_up(self):
        orders = [
            {"symbol": "AAA", "submitted_at": "2026-10-09T19:45:00Z",
             "filled_quantity": "10"},
            {"symbol": "BBB", "submitted_at": "2026-10-09T19:45:00Z",
             "filled_quantity": "0"},          # never filled
            {"symbol": "BTC/USD", "submitted_at": "2026-10-09T19:45:00Z",
             "filled_quantity": "0.01"},       # not an equity
            {"symbol": "CCC", "submitted_at": "2026-10-08T19:45:00Z",
             "filled_quantity": "10"},         # another session
        ]
        asked = {}
        def fake_fetch(symbols, **kw):
            asked["symbols"] = list(symbols)
            return {}
        self.rec.traded_adv(orders, date(2026, 10, 9), fetch=fake_fetch)
        self.assertEqual(asked["symbols"], ["AAA"])

    def test_no_fills_means_no_lookup_at_all(self):
        def explode(*a, **k):
            raise AssertionError("should not fetch when nothing was filled")
        self.assertEqual(self.rec.traded_adv([], date(2026, 10, 9),
                                             fetch=explode), {})
