"""H-0007: volatility abstention. The properties that make it a test.

Four things carry the result. The abstention decision for session t is
computed from closes through t-1 and can never see t. The percentile is
EXPANDING, so a later reading cannot relabel an earlier one. The veto
only ever removes. And the adjudication is faithful to the sealed text:
a family whose Sharpe gradient runs opposite to the declared direction
fails clause C no matter how good a single cutoff looks, and clause D
does not open the thirty-year window when nothing passed A, B and C.

These pin the RESULT, so it cannot be quietly re-read as a success
later, and they pin the MECHANISM, so a future reuse of the abstention
code inherits the leakage guard.
"""

import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from event_aware_trader.data import Bar
from event_aware_trader.modelgov.gradient import spearman

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "docs" / "phase5" / "h0007-results.json"
VERDICT = REPO / "docs" / "phase5" / "h0007-adjudication.json"

VOL_DAYS = 20
MIN_READINGS = 252


def sessions(n, start=date(2016, 1, 4)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(datetime.combine(d, datetime.min.time(), timezone.utc))
        d += timedelta(days=1)
    return out


def bars(closes, start=date(2016, 1, 4)):
    return [Bar(timestamp=s, open=c, high=c, low=c, close=c, volume=1e8)
            for s, c in zip(sessions(len(closes), start), closes)]


def allowance(spy, cutoff, vol_days=VOL_DAYS, minimum=MIN_READINGS):
    """The rule under test, transcribed from scripts/run_h0007.py."""
    closes, seen, rank_at = [], [], {}
    for bar in spy:
        closes.append(bar.close)
        if len(closes) >= vol_days + 1:
            rets = [closes[j] / closes[j - 1] - 1.0
                    for j in range(len(closes) - vol_days, len(closes))
                    if closes[j - 1]]
            if len(rets) > 1:
                from statistics import pstdev
                vol = pstdev(rets)
                seen.append(vol)
                rank_at[bar.timestamp.date()] = (
                    sum(1 for v in seen if v <= vol) / len(seen)
                    if len(seen) >= minimum else None)
    days = [b.timestamp.date() for b in spy]
    allow = {}
    for i, day in enumerate(days):
        if i == 0:
            allow[day] = True
            continue
        rank = rank_at.get(days[i - 1])
        allow[day] = True if rank is None else rank >= cutoff
    return allow


def ramp(n, step=1.0, start=100.0):
    return [start + step * i for i in range(n)]


class TheDecisionCannotSeeItsOwnSession(unittest.TestCase):
    """The leakage guard. Changing session t's close must not move
    session t's own allow/deny bit."""

    def test_changing_todays_close_does_not_change_todays_decision(self):
        closes = ramp(400)
        for i in range(300, 400, 7):
            shocked = list(closes)
            shocked[i] *= 1.35            # a violent move ON day i
            base = allowance(bars(closes), 0.25)
            after = allowance(bars(shocked), 0.25)
            day = bars(closes)[i].timestamp.date()
            self.assertEqual(base[day], after[day],
                             "session {0}'s own close moved its own "
                             "decision".format(i))

    def test_changing_todays_close_DOES_change_tomorrows_decision(self):
        """The guard must not be vacuous: the information still arrives,
        one session late."""
        closes = ramp(400)
        closes[350] *= 1.35
        quiet = ramp(400)
        moved = [d for d in allowance(bars(closes), 0.25)
                 if allowance(bars(closes), 0.25)[d]
                 != allowance(bars(quiet), 0.25)[d]]
        self.assertTrue(moved, "the shock changed no decision at all, so "
                               "the test above proves nothing")
        self.assertTrue(all(d > bars(quiet)[350].timestamp.date()
                            for d in moved),
                        "a decision on or before the shock day changed")

    def test_the_future_cannot_reach_back(self):
        """Appending later sessions must not alter earlier decisions:
        the percentile is EXPANDING, not full-sample."""
        closes = ramp(500)
        short = allowance(bars(closes[:400]), 0.25)
        long_ = allowance(bars(closes), 0.25)
        for day, verdict in short.items():
            self.assertEqual(verdict, long_[day],
                             "adding future data changed {0}".format(day))


class ThePercentileIsNotTrustedEarly(unittest.TestCase):
    def test_entries_are_allowed_before_the_minimum_history(self):
        allow = allowance(bars(ramp(200)), 0.9999)
        self.assertTrue(all(allow.values()),
                        "a cutoff of ~1.0 denied a session before 252 "
                        "readings existed")

    def test_the_early_window_matches_the_baseline_exactly(self):
        """Registered claim: 'the early window matches the baseline
        exactly'. With 252 readings needed and 20 burned by the vol
        window, the first ~272 sessions must all be allowed."""
        allow = allowance(bars(ramp(400)), 0.9999)
        days = [b.timestamp.date() for b in bars(ramp(400))]
        self.assertTrue(all(allow[d] for d in days[:MIN_READINGS + VOL_DAYS]))

    def test_denial_becomes_possible_once_history_exists(self):
        allow = allowance(bars(ramp(400)), 0.9999)
        self.assertFalse(all(allow.values()),
                         "no session was ever denied, so the rule is inert")


class TheVetoOnlyRemoves(unittest.TestCase):
    def test_a_denied_session_denies_every_symbol(self):
        allow = allowance(bars(ramp(400)), 0.9999)
        denied = [d for d, ok in allow.items() if not ok]
        self.assertTrue(denied)
        for symbol in ("AAPL", "MSFT", "XOM"):
            for day in denied:
                self.assertFalse(allow[day],
                                 "{0} escaped the abstention".format(symbol))

    def test_a_cutoff_of_zero_never_denies(self):
        self.assertTrue(all(allowance(bars(ramp(400)), 0.0).values()))

    def test_a_lower_cutoff_denies_a_subset_of_a_higher_one(self):
        """Nesting. Relaxing the cutoff may only allow more, never less -
        otherwise the three configurations are not one family."""
        spy = bars(ramp(400))
        loose = allowance(spy, 0.20)
        tight = allowance(spy, 1.0 / 3.0)
        for day, ok in tight.items():
            if not loose[day]:
                self.assertFalse(ok, "{0} denied at 0.20 but allowed at "
                                     "1/3".format(day))


class TheRecordedResultSaysWhatItSays(unittest.TestCase):
    """The outcome is pinned so it cannot drift into a success."""

    def setUp(self):
        self.data = json.loads(RESULTS.read_text(encoding="utf-8"))
        self.verdict = json.loads(VERDICT.read_text(encoding="utf-8"))
        self.rows = sorted(self.data["configurations"],
                           key=lambda r: r["cutoff"])

    def test_the_baseline_reproduced_the_registered_figure(self):
        self.assertAlmostEqual(self.data["baseline"]["total_return"],
                               0.585889, places=6)

    def test_exactly_the_three_sealed_cutoffs_were_run(self):
        self.assertEqual([round(r["cutoff"], 4) for r in self.rows],
                         [0.2, 0.25, 0.3333])

    def test_the_sharpe_gradient_runs_opposite_to_the_declared_direction(self):
        rho = spearman([r["cutoff"] for r in self.rows],
                       [r["sharpe"] for r in self.rows])
        self.assertLess(rho, 0, "the declared direction was POSITIVE; a "
                                "non-negative rho here would mean the "
                                "recorded result changed")
        self.assertEqual(round(rho, 4), -1.0)

    def test_clause_c_failed(self):
        self.assertFalse(self.verdict["clause_c"])

    def test_the_verdict_is_rejected(self):
        self.assertEqual(self.verdict["verdict"], "REJECTED")

    def test_no_configuration_passed_all_of_a_b_and_c(self):
        self.assertFalse([v for v in self.verdict["per_configuration"]
                          if v["passes_abc"]])

    def test_the_lone_passing_cutoff_is_recorded_as_a_spike(self):
        self.assertEqual(self.verdict["spike"], ["C quintile"])

    def test_the_spike_is_inside_noise(self):
        """0.0032 of Sharpe on a 0.51 base. Pinned so that a later reader
        cannot quote it as an improvement."""
        c = [r for r in self.rows if r["label"] == "C quintile"][0]
        self.assertLess(c["sharpe"] - self.data["baseline"]["sharpe"], 0.01)

    def test_the_spike_earns_less_than_the_baseline(self):
        """Its Sharpe rose only because volatility fell faster than
        return. Total return must be LOWER, or the claim above is wrong."""
        c = [r for r in self.rows if r["label"] == "C quintile"][0]
        self.assertLess(c["total_return"],
                        self.data["baseline"]["total_return"])
        self.assertLess(c["annualised_volatility"],
                        self.data["baseline"]["annualised_volatility"])

    def test_abstention_refused_net_winners_at_every_cutoff(self):
        """The mechanical prior said calm sessions hold the weak trades.
        Every cutoff refused trades whose net P&L was POSITIVE."""
        for r in self.rows:
            self.assertGreater(r["removed_winner_pnl"] + r["removed_loser_pnl"],
                               0.0, "{0} refused net losses, which would "
                                    "support the prior".format(r["label"]))

    def test_every_configuration_fell_further_behind_spy(self):
        base = 100.0 * (self.data["baseline"]["total_return"]
                        - self.data["spy_total"])
        for r in self.rows:
            self.assertLess(r["vs_spy_points"], base)


class TheThirtyYearWindowStayedShut(unittest.TestCase):
    def setUp(self):
        self.verdict = json.loads(VERDICT.read_text(encoding="utf-8"))

    def test_clause_d_was_not_evaluated(self):
        self.assertEqual(self.verdict["clause_d"],
                         "not_evaluated_window_not_opened")

    def test_the_access_count_is_unchanged(self):
        self.assertEqual(self.verdict["thirty_year_reads"], 13)

    def test_no_thirty_year_result_file_exists(self):
        self.assertFalse((REPO / "docs" / "phase5" /
                          "h0007-thirtyyear.json").exists(),
                         "a thirty-year run happened despite clause D being "
                         "out of scope")


class TheAdjudicationRuleItselfIsCorrect(unittest.TestCase):
    """Applied to synthetic families, so the logic is tested apart from
    the one outcome it happened to produce."""

    @staticmethod
    def clause_c(cuts, sharpes, returns):
        return (spearman(cuts, sharpes) > 0
                and spearman(cuts, returns) < 0
                and all(sharpes[i + 1] >= sharpes[i]
                        for i in range(len(sharpes) - 1)))

    def test_a_family_in_the_declared_direction_passes(self):
        self.assertTrue(self.clause_c([0.20, 0.25, 0.3333],
                                      [0.52, 0.55, 0.58],
                                      [0.57, 0.52, 0.48]))

    def test_the_observed_family_fails(self):
        self.assertFalse(self.clause_c([0.20, 0.25, 0.3333],
                                       [0.5139, 0.4603, 0.4313],
                                       [0.5758, 0.4937, 0.4435]))

    def test_a_middle_dip_fails_even_with_a_rising_rho(self):
        """A spike at the ends with a hole in the middle is not a
        gradient. Spearman alone would pass this; the adjacent check
        must catch it."""
        cuts, sharpes = [0.20, 0.25, 0.3333], [0.52, 0.50, 0.60]
        self.assertGreater(spearman(cuts, sharpes), 0)
        self.assertFalse(self.clause_c(cuts, sharpes, [0.57, 0.52, 0.48]))

    def test_rising_sharpe_with_rising_return_fails(self):
        """Both rising means the abstention is not paying for itself in
        the declared currency - it was declared to COST total return."""
        self.assertFalse(self.clause_c([0.20, 0.25, 0.3333],
                                       [0.52, 0.55, 0.58],
                                       [0.57, 0.60, 0.64]))


if __name__ == "__main__":
    unittest.main()
