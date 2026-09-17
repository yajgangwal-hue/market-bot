"""H-0008: exit-timing calibration. The properties that make it a test.

The danger in this experiment is not complexity, it is OPTIMISM: a lower
haircut raises backtest return mechanically, so anything that lets a
favourable number in through the side door is the bug. These tests pin
three things.

The MECHANISM: the trigger is found by walking a session forward and
halting at the first RSI crossing, so no later bar can move it, and the
holding cap - which has no intraday component - triggers at the bell.

The RESULT: every registered percentile measured ABOVE the 0.652%
charged, so the haircut stands. Pinned so it cannot later be read as a
licence to lower it.

The RULE ITSELF: the adjudication rejects on direction even when a
configuration is stable, and accepts only when a percentile is genuinely
below what is charged.
"""

import json
import unittest
from datetime import time
from pathlib import Path

from event_aware_trader.mean_reversion import rsi

REPO = Path(__file__).resolve().parents[1]
DRIFT = REPO / "docs" / "phase5" / "h0008-drift.json"
VERDICT = REPO / "docs" / "phase5" / "h0008-adjudication.json"

CURRENT_HAIRCUT = 0.00652
RSI_PERIOD, RSI_EXIT = 14, 60.0


def percentile(values, p):
    """The runner's percentile, transcribed."""
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def find_trigger(reason, session, prior):
    """The runner's trigger search, transcribed."""
    if not session:
        return None
    if reason != "reverted":
        return session[0]
    for hhmm, price in session:
        strength = rsi(prior + [price], RSI_PERIOD)
        if strength is not None and strength >= RSI_EXIT:
            return hhmm, price
    return None


def session_of(prices, start_hour=13, start_min=30):
    out, h, m = [], start_hour, start_min
    for p in prices:
        out.append((time(h, m), p))
        m += 5
        h, m = (h + m // 60, m % 60)
    return out


class TheTriggerHaltsAtTheFirstCrossing(unittest.TestCase):
    """A forward walk that stops. Nothing after the trigger may move it."""

    def setUp(self):
        # A falling prior series leaves RSI low, so a rising session
        # carries it up through 60 at some identifiable bar.
        self.prior = [100.0 - i for i in range(40)]

    def test_later_bars_cannot_move_the_trigger(self):
        rising = [62.0 + 0.8 * i for i in range(30)]
        first = find_trigger("reverted", session_of(rising), self.prior)
        self.assertIsNotNone(first, "the fixture never crossed; test is vacuous")
        for tail in ([0.0] * 10, [999.0] * 10, [-50.0] * 10):
            longer = find_trigger(
                "reverted", session_of(rising + [max(x, 0.01) for x in tail]),
                self.prior)
            self.assertEqual(first, longer,
                             "a bar after the crossing moved the trigger")

    def test_the_trigger_is_the_first_crossing_not_the_best_price(self):
        """A dip after the crossing must not be preferred, and neither
        must a later, higher price."""
        prices = [62.0 + 0.8 * i for i in range(30)]
        found = find_trigger("reverted", session_of(prices), self.prior)
        self.assertIsNotNone(found, "fixture never crossed; test is vacuous")
        _hhmm, price = found
        crossing = [p for p in prices
                    if rsi(self.prior + [p], RSI_PERIOD) >= RSI_EXIT][0]
        self.assertEqual(price, crossing)
        self.assertLess(price, max(prices),
                        "the trigger took the session's best price")

    def test_a_session_that_never_crosses_returns_nothing(self):
        flat = [50.0] * 30
        self.assertIsNone(find_trigger("reverted", session_of(flat),
                                       self.prior))

    def test_the_holding_cap_triggers_at_the_bell(self):
        """It has no intraday component: it is already true at the open."""
        prices = [10.0 * (i + 1) for i in range(20)]
        session = session_of(prices)
        self.assertEqual(find_trigger("time_exit", session, self.prior),
                         session[0])

    def test_the_cap_trigger_ignores_rsi_entirely(self):
        session = session_of([1.0] * 12)
        self.assertEqual(find_trigger("time_exit", session, self.prior),
                         session[0])


class TheDriftSignConventionHolds(unittest.TestCase):
    """Positive drift = close above trigger = the simulator overstates,
    which is the quantity the haircut corrects. Getting this backwards
    would invert the entire conclusion."""

    def test_a_close_above_the_trigger_is_positive(self):
        self.assertGreater(110.0 / 100.0 - 1.0, 0)

    def test_the_recorded_drifts_match_their_trigger_and_close(self):
        d = json.loads(DRIFT.read_text(encoding="utf-8"))
        for row in d["observations"][:50]:
            self.assertAlmostEqual(row["drift"],
                                   row["close"] / row["trigger"] - 1.0,
                                   places=12)


class TheRecordedResultSaysWhatItSays(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(DRIFT.read_text(encoding="utf-8"))
        self.v = json.loads(VERDICT.read_text(encoding="utf-8"))

    def test_the_baseline_reproduced_before_anything_was_measured(self):
        self.assertAlmostEqual(self.d["baseline_total_return"], 0.585889,
                               places=6)

    def test_exactly_the_three_sealed_percentiles_were_run(self):
        self.assertEqual(sorted(c["percentile"]
                                for c in self.d["configurations"]),
                         [75, 90, 95])

    def test_every_registered_percentile_is_ABOVE_what_is_charged(self):
        """The finding. If this ever fails, the measurement changed and
        the conclusion must be re-derived rather than reused."""
        for cfg in self.d["configurations"]:
            self.assertGreater(cfg["value"], CURRENT_HAIRCUT,
                               "{0} fell below the charged haircut".format(
                                   cfg["label"]))

    def test_the_verdict_is_rejected(self):
        self.assertEqual(self.v["verdict"], "REJECTED")

    def test_no_configuration_survived(self):
        self.assertEqual(self.v["survivors"], [])

    def test_the_haircut_is_recorded_as_unchanged(self):
        self.assertTrue(self.v["haircut_unchanged"])
        self.assertEqual(self.v["current_haircut"], CURRENT_HAIRCUT)

    def test_production_still_charges_the_original_haircut(self):
        """The one that matters. A rejected experiment must not have
        edited the constant it was testing."""
        source = (REPO / "src" / "event_aware_trader" / "portfolio.py"
                  ).read_text(encoding="utf-8")
        self.assertIn("0.652%", source)
        self.assertIn("rule_exit_timing_haircut: float = 0.0", source)

    def test_the_favourable_mean_was_recorded_but_not_adopted(self):
        """The mean drift IS below the charged haircut. H-0008 registered
        a percentile, so the mean may not be used. It is kept visible so
        a later registration can test it honestly."""
        self.assertLess(self.v["mean_drift_recorded_not_adopted"],
                        CURRENT_HAIRCUT)
        self.assertTrue(self.v["haircut_unchanged"])

    def test_the_sample_is_the_registered_minimum_or_better(self):
        self.assertGreaterEqual(self.d["reconstructed"], 100)

    def test_coverage_is_recorded_honestly(self):
        """160 of 459. A partial reconstruction must say so."""
        self.assertLess(self.d["reconstructed"], self.d["rule_exits_in_run"])
        self.assertTrue(self.d["not_reconstructed"])

    def test_the_unmodellable_gap_is_reported(self):
        u = self.d["unmodellable"]
        self.assertGreater(u["crossed_intraday"], 0)
        self.assertGreater(u["closed_below_60"], u["crossed_intraday"])


class TheThirtyYearWindowWasNotTouched(unittest.TestCase):
    def test_the_access_count_is_unchanged(self):
        v = json.loads(VERDICT.read_text(encoding="utf-8"))
        self.assertEqual(v["thirty_year_reads"], 13)

    def test_the_use_log_still_records_thirteen(self):
        rows = [json.loads(line) for line in
                (REPO / "docs" / "dataset-uses.jsonl")
                .read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(
            sum(1 for r in rows if r.get("dataset") == "thirty_year"), 13)


class TheAdjudicationRuleItselfIsCorrect(unittest.TestCase):
    """Applied to synthetic families, so the logic is tested apart from
    the one outcome it happened to produce."""

    @staticmethod
    def passes(value, half_gap, n, sym_share, year_share):
        return (n >= 100 and sym_share <= 0.15 and year_share <= 0.50
                and half_gap <= 0.0025 and value < CURRENT_HAIRCUT)

    def test_a_low_stable_well_spread_percentile_passes(self):
        self.assertTrue(self.passes(0.0030, 0.0010, 160, 0.05, 0.30))

    def test_the_observed_family_fails(self):
        for value, gap in ((0.006712, 0.001335), (0.014362, 0.003084),
                           (0.018327, 0.004976)):
            self.assertFalse(self.passes(value, gap, 160, 0.038, 0.319))

    def test_a_low_value_that_is_unstable_fails(self):
        """Stability is not negotiable just because the number is nice."""
        self.assertFalse(self.passes(0.0030, 0.0080, 160, 0.05, 0.30))

    def test_a_low_value_on_too_small_a_sample_fails(self):
        self.assertFalse(self.passes(0.0030, 0.0010, 99, 0.05, 0.30))

    def test_a_low_value_concentrated_in_one_symbol_fails(self):
        self.assertFalse(self.passes(0.0030, 0.0010, 160, 0.40, 0.30))

    def test_a_low_value_concentrated_in_one_year_fails(self):
        self.assertFalse(self.passes(0.0030, 0.0010, 160, 0.05, 0.80))

    def test_equal_to_the_charged_haircut_is_not_below_it(self):
        self.assertFalse(self.passes(CURRENT_HAIRCUT, 0.0010, 160, 0.05, 0.30))


if __name__ == "__main__":
    unittest.main()
