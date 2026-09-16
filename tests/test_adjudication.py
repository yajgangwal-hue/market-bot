"""A configuration may not be chosen by its return. The H-0002 mistake.

WHAT HAPPENED. The Phase 6 recorder picked each family's representative
with `max(..., key=total_return)`. For H-0002 that is 1.5R, whose entire
gain is one calendar year and which FAILS the registered best-year
clause. The conclusion text described 2.0R, which passes. Metrics and
prose disagreed, and the error was not in the experiment - it was in the
bookkeeping underneath it, where pre-registration was not looking.

The synthetic family below is built to reproduce exactly that shape: A
has the highest raw return and fails a criterion, B is lower and passes.
Any selection step that reaches for the return will pick A and fail
these tests.
"""

import unittest

from event_aware_trader.modelgov.adjudicate import (
    SelectionError, adjudicate, best_by_return, family_monotonicity,
    leave_one_best_year_out, standard_clauses, surviving, yearly_deltas)

YEARS = list(range(2016, 2027))


def row(label, total, by_year, drawdown=-0.13, vol=0.093):
    return {"label": label, "total_return": total, "max_drawdown": drawdown,
            "annualised_volatility": vol, "by_year": dict(by_year)}


BASELINE = row("baseline", 0.586, {y: 0.03 for y in YEARS})


def concentrated(total):
    """All the gain in one year, negative in most others. Like 1.5R."""
    by = {y: 0.03 - 0.002 for y in YEARS}
    by[2017] = 0.03 + 0.05
    return row("A concentrated", total, by)


def broad(total):
    """A small edge in most years. Like 2.0R."""
    by = {y: 0.03 + 0.004 for y in YEARS}
    by[2018] = 0.03 - 0.001
    by[2025] = 0.03 - 0.001
    return row("B broad", total, by)


class TheHighestReturnDoesNotWin(unittest.TestCase):
    def setUp(self):
        # A genuinely has the higher raw return. That is the trap.
        self.a = concentrated(0.616)
        self.b = broad(0.613)
        self.rows = [self.a, self.b]
        self.verdicts = adjudicate(self.rows, BASELINE)

    def test_the_trap_is_real_a_really_does_return_more(self):
        self.assertGreater(self.a["total_return"], self.b["total_return"])

    def test_the_concentrated_configuration_fails(self):
        a = [v for v in self.verdicts if v.label == "A concentrated"][0]
        self.assertFalse(a.survives)
        self.assertIn("positive with its best year removed",
                      [c.name for c in a.failures])

    def test_the_broad_configuration_survives(self):
        b = [v for v in self.verdicts if v.label == "B broad"][0]
        self.assertTrue(b.survives, [c.name for c in b.failures])

    def test_only_the_passing_configuration_is_returned(self):
        self.assertEqual([v.label for v in surviving(self.verdicts)],
                         ["B broad"])

    def test_every_configuration_gets_a_verdict_none_is_dropped(self):
        self.assertEqual(len(self.verdicts), len(self.rows))

    def test_verdicts_keep_the_registered_grid_order_not_a_ranking(self):
        self.assertEqual([v.label for v in self.verdicts],
                         [r["label"] for r in self.rows])

    def test_reaching_for_the_best_return_raises(self):
        with self.assertRaises(SelectionError):
            best_by_return(self.rows)

    def test_an_empty_survivor_list_is_a_legitimate_outcome(self):
        both_fail = [concentrated(0.60), concentrated(0.59)]
        self.assertEqual(surviving(adjudicate(both_fail, BASELINE)), [])


class TheLeaveOneBestYearProcedureIsFixed(unittest.TestCase):
    def test_it_removes_the_single_best_year(self):
        deltas = {2020: 0.05, 2021: 0.01, 2022: -0.02}
        self.assertAlmostEqual(leave_one_best_year_out(deltas), -0.01)

    def test_it_is_the_same_procedure_for_every_configuration(self):
        """Not re-chosen per result: one function, one definition."""
        a = yearly_deltas(concentrated(0.6), BASELINE)
        b = yearly_deltas(broad(0.6), BASELINE)
        self.assertLess(leave_one_best_year_out(a), 0)
        self.assertGreater(leave_one_best_year_out(b), 0)

    def test_removing_the_worst_year_is_not_offered(self):
        """A favourable variant must not be reachable by accident."""
        import event_aware_trader.modelgov.adjudicate as module
        self.assertFalse(any("worst" in name for name in dir(module)))

    def test_an_empty_delta_set_is_zero_not_an_error(self):
        self.assertEqual(leave_one_best_year_out({}), 0.0)


class RiskClausesBiteInBothDirections(unittest.TestCase):
    def test_a_higher_return_bought_with_drawdown_fails(self):
        risky = broad(0.80)
        risky["max_drawdown"] = -0.20
        verdict = adjudicate([risky], BASELINE)[0]
        self.assertFalse(verdict.survives)
        self.assertTrue(any("drawdown" in c.name for c in verdict.failures))

    def test_a_higher_return_bought_with_volatility_fails(self):
        risky = broad(0.80)
        risky["annualised_volatility"] = 0.15
        verdict = adjudicate([risky], BASELINE)[0]
        self.assertTrue(any("volatility" in c.name for c in verdict.failures))

    def test_not_beating_the_baseline_fails_first(self):
        worse = broad(0.40)
        verdict = adjudicate([worse], BASELINE)[0]
        self.assertIn("beats baseline on total return",
                      [c.name for c in verdict.failures])


class FamilyMonotonicityIsAFamilyProperty(unittest.TestCase):
    def test_a_monotone_family_passes(self):
        rows = [broad(0.62), broad(0.61), broad(0.58)]
        self.assertTrue(family_monotonicity(rows).passed)

    def test_a_spike_in_the_middle_fails(self):
        rows = [broad(0.58), broad(0.72), broad(0.59)]
        self.assertFalse(family_monotonicity(rows).passed)

    def test_the_family_clause_sinks_every_member(self):
        """H-0003's actual shape: one strong value, neighbours inert."""
        rows = [broad(0.723), broad(0.572), broad(0.586)]
        verdicts = adjudicate(rows, BASELINE)
        self.assertEqual(surviving(verdicts), [])
        for v in verdicts:
            self.assertIn("family monotone or flat across adjacent values",
                          [c.name for c in v.failures])


class TheRealPhase6DataReproducesTheFinding(unittest.TestCase):
    """Guards the conclusion itself against a silent change in the data."""

    def rows(self):
        import json
        from pathlib import Path
        path = Path("data/phase5/sealed-exits-deep.json")
        if not path.exists():
            self.skipTest("Phase 6 results not on disk")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_h0002_survivor_is_the_2R_configuration_not_the_1_5R(self):
        rows = self.rows()
        base = rows[0]
        family = [r for r in rows[1:] if r.get("hypothesis") == "H-0002"]
        verdicts = adjudicate(family, base)
        survivors = [v.label for v in surviving(verdicts)]
        self.assertEqual(survivors, ["take profit 2.0R"])
        highest = max(family, key=lambda r: r["total_return"])["label"]
        self.assertEqual(highest, "take profit 1.5R")
        self.assertNotIn(highest, survivors,
                         "the highest-return configuration must not survive")

    def test_h0003_has_no_survivor_because_the_family_is_not_monotone(self):
        rows = self.rows()
        base = rows[0]
        family = [r for r in rows[1:] if r.get("hypothesis") == "H-0003"]
        self.assertEqual(surviving(adjudicate(family, base)), [])


if __name__ == "__main__":
    unittest.main()
