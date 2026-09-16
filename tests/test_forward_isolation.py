"""Phase 3. The clean forward record cannot be edited, and cannot flow back.

The brief names six properties. Each has its own test below, and the
look-ahead ones are the important half: they assert that nothing arriving
later can reach backwards and change a decision already made.

A note on what these prove and what they do not. The hash chain makes
tampering DETECTABLE, not impossible - nothing in a local file can be made
impossible. The type-level refusal stops a clean observation reaching
research through the front door, not through someone deliberately
converting it to a dict first. Both raise the cost of the mistake from
"silent" to "loud", which is the achievable goal.
"""

import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.data import Bar
from event_aware_trader.forward import (
    CleanObservation, ForwardDataLeak, FrozenConfigChanged,
    MINIMUM_SESSIONS_FOR_ANY_VERDICT, append_session, evaluate_forward,
    frozen_fingerprint, load_sessions, reject_forward_data, verify_chain)
from event_aware_trader.portfolio import run_portfolio
from event_aware_trader.risk import CostModel, RiskPolicy

START = datetime(2024, 1, 2, tzinfo=timezone.utc)


def observation(day, fingerprint, equity=100_000.0, ret=0.001):
    return CleanObservation(
        session=day, as_of=day + "T20:00:00+00:00",
        config_fingerprint=fingerprint, universe_size=230, signals=4,
        orders=1, fills=1, positions_held=5, exposure=0.72, cash=7_000.0,
        equity=equity, transaction_costs=12.0, dividends_received=0.0,
        strategy_return=ret, benchmark_return=0.002)


def series(closes, volumes=None, highs=None):
    volumes = volumes or [3_000_000] * len(closes)
    highs = highs or closes
    return [Bar(timestamp=START + timedelta(days=i), open=c, high=h,
                low=c * 0.995, close=c, volume=v)
            for i, (c, h, v) in enumerate(zip(closes, highs, volumes))]


def oversold_in_an_uptrend(extra=None, volume=3_000_000):
    up = [100.0 + i * 0.25 for i in range(250)]
    top = up[-1]
    closes = up + [top * (1 - 0.08 * (j + 1) / 6) for j in range(6)]
    if extra:
        closes = closes + list(extra)
    return series(closes, [volume] * len(closes))


def run(data, **kw):
    return run_portfolio(data, starting_cash=100_000.0, policy=RiskPolicy(),
                         costs=CostModel(), entry_rule="mean_reversion",
                         entry_fill="signal_close", **kw)


def decisions(report):
    """What was decided, stripped of what it earned."""
    return [(t.symbol, t.entry_time.date(), t.exit_time.date(),
             round(float(t.quantity), 6), round(float(t.entry_price), 6))
            for t in report.trades]


# ---------------------------------------------------------------------------
# Property: the future cannot reach backwards
# ---------------------------------------------------------------------------

class FutureCannotAlterThePast(unittest.TestCase):
    def test_a_future_price_cannot_change_an_earlier_signal(self):
        base = oversold_in_an_uptrend()
        with_future = oversold_in_an_uptrend(extra=[500.0] * 60)
        self.assertEqual(decisions(run({"AAA": base}))[:1],
                         decisions(run({"AAA": with_future}))[:1])

    def test_a_future_collapse_cannot_change_an_earlier_signal(self):
        base = oversold_in_an_uptrend()
        crash = oversold_in_an_uptrend(extra=[5.0] * 60)
        self.assertEqual(decisions(run({"AAA": base}))[:1],
                         decisions(run({"AAA": crash}))[:1])

    def test_a_future_volume_spike_cannot_change_an_earlier_position_size(self):
        base = oversold_in_an_uptrend(volume=3_000_000)
        later = list(base) + [
            Bar(timestamp=base[-1].timestamp + timedelta(days=i + 1),
                open=150.0, high=151.0, low=149.0, close=150.0,
                volume=9_000_000_000) for i in range(60)]
        a = run({"AAA": base}, )
        b = run({"AAA": later})
        first_a = (a.trades or a.open_positions)[0]
        first_b = (b.trades or b.open_positions)[0]
        self.assertAlmostEqual(float(first_a.quantity), float(first_b.quantity),
                               places=6)

    def test_a_future_dividend_cannot_change_an_earlier_signal(self):
        """Signals run on as-traded prices, never on dividend-adjusted ones.

        adjustment="all" restates HISTORY using dividends paid afterwards.
        This asserts the property that makes that safe: the decision depends
        only on the bars up to it, so a payment later in the series - which
        would alter an adjusted close - cannot move it.
        """
        base = oversold_in_an_uptrend()
        # A dividend shows up as a downward step in an as-traded series.
        after_div = oversold_in_an_uptrend(
            extra=[base[-1].close * 0.97] + [base[-1].close] * 40)
        self.assertEqual(decisions(run({"AAA": base}))[:1],
                         decisions(run({"AAA": after_div}))[:1])

    def test_a_future_trade_cannot_change_an_earlier_portfolio_decision(self):
        one = {"AAA": oversold_in_an_uptrend()}
        two = dict(one)
        # A second name whose setup occurs only much later.
        late = [100.0] * 250 + [100.0 - i for i in range(30)]
        two["ZZZ"] = series(late)
        self.assertEqual(decisions(run(one))[:1], decisions(run(two))[:1])


# ---------------------------------------------------------------------------
# Property: clean data cannot flow into research
# ---------------------------------------------------------------------------

class CleanDataCannotReachResearch(unittest.TestCase):
    def setUp(self):
        self.obs = observation("2026-10-09", frozen_fingerprint())

    def test_the_guard_refuses_a_single_observation(self):
        with self.assertRaises(ForwardDataLeak):
            reject_forward_data(self.obs)

    def test_the_guard_refuses_a_sequence_of_them(self):
        with self.assertRaises(ForwardDataLeak):
            reject_forward_data([self.obs, self.obs])

    def test_it_lets_ordinary_research_inputs_through(self):
        reject_forward_data({"AAA": oversold_in_an_uptrend()}, [1, 2, 3], None)

    def test_production_report_refuses_clean_observations(self):
        from event_aware_trader.research import production_report
        with self.assertRaises(ForwardDataLeak):
            production_report({"AAA": [self.obs]})

    def test_record_experiment_refuses_clean_observations(self):
        from event_aware_trader.research import record_experiment
        with self.assertRaises(ForwardDataLeak):
            record_experiment("x", "h", {"smuggled": self.obs}, ["decade"],
                              "r", "rejected", "why")


# ---------------------------------------------------------------------------
# Property: the record is append-only and tamper-evident
# ---------------------------------------------------------------------------

class TheRecordIsAppendOnly(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "forward.jsonl"
        self.fp = frozen_fingerprint()

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_session_cannot_be_recorded_twice(self):
        append_session(observation("2026-10-09", self.fp), self.path)
        with self.assertRaises(ForwardDataLeak):
            append_session(observation("2026-10-09", self.fp, ret=0.05),
                           self.path)

    def test_the_chain_is_intact_when_appended_normally(self):
        for i in range(5):
            append_session(observation("2026-10-%02d" % (9 + i), self.fp),
                           self.path)
        check = verify_chain(self.path)
        self.assertTrue(check["intact"])
        self.assertEqual(check["sessions"], 5)

    def test_editing_a_recorded_result_breaks_the_chain(self):
        for i in range(4):
            append_session(observation("2026-10-%02d" % (9 + i), self.fp),
                           self.path)
        rows = [json.loads(l) for l in self.path.read_text().splitlines()]
        rows[1]["payload"]["strategy_return"] = 0.99      # flatter day two
        self.path.write_text("".join(json.dumps(r, sort_keys=True) + "\n"
                                     for r in rows))
        check = verify_chain(self.path)
        self.assertFalse(check["intact"])
        self.assertEqual(check["broken_at"], 1)
        self.assertIn("edited", check["reason"])

    def test_deleting_a_record_breaks_the_chain(self):
        for i in range(4):
            append_session(observation("2026-10-%02d" % (9 + i), self.fp),
                           self.path)
        rows = [json.loads(l) for l in self.path.read_text().splitlines()]
        del rows[2]
        self.path.write_text("".join(json.dumps(r, sort_keys=True) + "\n"
                                     for r in rows))
        self.assertFalse(verify_chain(self.path)["intact"])

    def test_loading_a_tampered_record_refuses_rather_than_returning_data(self):
        append_session(observation("2026-10-09", self.fp), self.path)
        rows = [json.loads(l) for l in self.path.read_text().splitlines()]
        rows[0]["payload"]["equity"] = 999_999.0
        self.path.write_text(json.dumps(rows[0], sort_keys=True) + "\n")
        with self.assertRaises(ForwardDataLeak):
            load_sessions(self.path)


# ---------------------------------------------------------------------------
# Property: the freeze is enforced, not promised
# ---------------------------------------------------------------------------

class TheFreezeIsEnforced(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "forward.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_fingerprint_is_stable_across_calls(self):
        self.assertEqual(frozen_fingerprint(), frozen_fingerprint())

    def test_a_session_from_a_different_configuration_is_refused(self):
        stale = observation("2026-10-09", "deadbeef" * 8)
        with self.assertRaises(FrozenConfigChanged):
            append_session(stale, self.path)

    def test_the_fingerprint_moves_when_a_frozen_parameter_moves(self):
        from unittest import mock
        from event_aware_trader import research
        before = frozen_fingerprint()
        moved = dict(research.PRODUCTION_CANDIDATE)
        moved["rule_exit_timing_haircut"] = 0.001
        with mock.patch.object(research, "PRODUCTION_CANDIDATE", moved):
            after = frozen_fingerprint()
        self.assertNotEqual(before, after,
                            "changing the haircut must move the fingerprint")


# ---------------------------------------------------------------------------
# Property: no conclusion from an insufficient sample
# ---------------------------------------------------------------------------

class NoPrematureConclusion(unittest.TestCase):
    def test_an_empty_record_yields_insufficient_evidence(self):
        v = evaluate_forward([])
        self.assertEqual(v.verdict, "INSUFFICIENT_EVIDENCE")
        self.assertFalse(v.may_conclude)

    def test_a_short_favourable_run_still_yields_insufficient_evidence(self):
        fp = frozen_fingerprint()
        great = [observation("2026-10-%02d" % (9 + i), fp, ret=0.03)
                 for i in range(10)]
        v = evaluate_forward(great)
        self.assertEqual(v.verdict, "INSUFFICIENT_EVIDENCE")
        self.assertGreater(v.measured["cumulative_return"], 0.3)
        self.assertFalse(v.may_conclude)

    def test_even_a_full_sample_cannot_conclude(self):
        fp = frozen_fingerprint()
        many = [observation("2026-%02d-%02d" % (10 + i // 28, 1 + i % 28), fp)
                for i in range(MINIMUM_SESSIONS_FOR_ANY_VERDICT + 5)]
        v = evaluate_forward(many)
        self.assertEqual(v.verdict, "MEASURED_NO_CONCLUSION")
        self.assertFalse(v.may_conclude)

    def test_the_verdict_type_cannot_express_profitability(self):
        v = evaluate_forward([])
        for forbidden in ("profitable", "beats_benchmark", "superior",
                          "outperforms"):
            self.assertNotIn(forbidden, v.as_dict())
        self.assertIn("whether the strategy is profitable", v.not_testable_yet)

    def test_annualised_statistics_are_withheld_on_a_short_sample(self):
        fp = frozen_fingerprint()
        v = evaluate_forward([observation("2026-10-%02d" % (9 + i), fp)
                              for i in range(5)])
        self.assertNotIn("cagr", v.measured)
        self.assertNotIn("sharpe", v.measured)
        self.assertTrue(any("annualised" in u for u in v.uncertain))


if __name__ == "__main__":
    unittest.main()
