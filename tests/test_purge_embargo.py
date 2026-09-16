"""P7/P8. The four properties the brief requires, each asserted directly.

  1. contaminated observations cannot enter the evaluation set
  2. embargoed observations cannot enter the evaluation set
  3. changing future observations cannot alter historical decisions
  4. the evaluation dataset is reproducible from the documented rules

Plus the two that stop this being tuned: the embargo length comes from the
strategy's own holding cap, and the freeze date comes from the registry.
Both would otherwise be knobs, and a knob set by looking at the answer is
exactly what purging is supposed to prevent.
"""

import unittest
from datetime import date, datetime, timedelta, timezone

from event_aware_trader.mean_reversion import MeanReversionConfig
from event_aware_trader.purge import (
    CONFIG_CHANGING, embargo_sessions, evaluation_window, freeze_date,
    is_straddling, purge, summarise)

FREEZE = date(2026, 9, 11)


def sessions(start=date(2026, 9, 1), n=80):
    """Weekday-only calendar, which is what 'session' means here."""
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


class Trade:
    def __init__(self, entry, exit_):
        self.entry_time = datetime.combine(entry, datetime.min.time(), timezone.utc)
        self.exit_time = datetime.combine(exit_, datetime.min.time(), timezone.utc)


REGISTRY = [
    {"when": "2026-09-08", "decision": "measured"},
    {"when": "2026-09-09", "decision": "reverted"},
    {"when": "2026-09-10", "decision": "accepted"},
    {"when": "2026-09-11", "decision": "reverted"},
    {"when": "2026-09-15", "decision": "rejected"},      # later, but no change
    {"when": "2026-09-16", "decision": "measured"},      # later, but no change
]


class TheBoundaryIsDerivedNotChosen(unittest.TestCase):
    def test_the_freeze_is_the_last_config_CHANGING_entry(self):
        # 09-15 and 09-16 are later but changed nothing, so they must not
        # move the boundary - otherwise merely running more experiments
        # would buy a longer "clean" period.
        self.assertEqual(freeze_date(REGISTRY), FREEZE)

    def test_only_accepted_and_reverted_count(self):
        self.assertEqual(set(CONFIG_CHANGING), {"accepted", "reverted"})
        measured_only = [{"when": "2026-09-20", "decision": "measured"},
                         {"when": "2026-09-21", "decision": "rejected"}]
        self.assertIsNone(freeze_date(measured_only))

    def test_an_empty_registry_has_no_freeze(self):
        self.assertIsNone(freeze_date([]))

    def test_the_embargo_is_the_strategys_own_holding_cap(self):
        self.assertEqual(embargo_sessions(), MeanReversionConfig().max_holding_bars)
        self.assertEqual(embargo_sessions(), 20)

    def test_the_embargo_tracks_the_config_and_is_not_a_free_number(self):
        from dataclasses import replace
        self.assertEqual(
            embargo_sessions(replace(MeanReversionConfig(), max_holding_bars=7)), 7)


class TheWindow(unittest.TestCase):
    def setUp(self):
        self.window = evaluation_window(REGISTRY, sessions())

    def test_it_embargoes_exactly_the_holding_cap_in_sessions(self):
        self.assertEqual(self.window.sessions_embargoed, 20)
        self.assertEqual(self.window.freeze, FREEZE)

    def test_clean_evaluation_starts_after_the_embargo(self):
        after = [d for d in sessions() if d > FREEZE]
        self.assertEqual(self.window.clean_from, after[20])
        self.assertGreater(self.window.clean_from, FREEZE)

    def test_too_few_sessions_means_no_clean_period_yet(self):
        # Today's real situation: a handful of sessions since the freeze.
        short = evaluation_window(REGISTRY, sessions(n=14))
        self.assertIsNone(short.clean_from)
        self.assertLess(short.sessions_embargoed, 20)


class ContaminatedObservationsCannotEnter(unittest.TestCase):
    """Property 1."""

    def setUp(self):
        self.window = evaluation_window(REGISTRY, sessions())

    def test_a_straddling_trade_is_never_clean(self):
        straddle = Trade(date(2026, 9, 9), date(2026, 9, 25))
        self.assertTrue(is_straddling(date(2026, 9, 9), date(2026, 9, 25), FREEZE))
        buckets = purge([straddle], self.window)
        self.assertEqual(summarise(buckets)["clean"], 0)
        self.assertEqual(summarise(buckets)["straddling"], 1)

    def test_a_trade_closed_before_the_freeze_is_pre_freeze(self):
        old = Trade(date(2026, 9, 2), date(2026, 9, 8))
        self.assertEqual(summarise(purge([old], self.window))["pre_freeze"], 1)

    def test_a_trade_closing_exactly_on_the_freeze_is_not_straddling(self):
        edge = Trade(date(2026, 9, 5), FREEZE)
        self.assertFalse(is_straddling(date(2026, 9, 5), FREEZE, FREEZE))
        self.assertEqual(summarise(purge([edge], self.window))["pre_freeze"], 1)


class EmbargoedObservationsCannotEnter(unittest.TestCase):
    """Property 2."""

    def setUp(self):
        self.window = evaluation_window(REGISTRY, sessions())

    def test_a_trade_opened_inside_the_embargo_is_excluded(self):
        after = [d for d in sessions() if d > FREEZE]
        inside = Trade(after[3], after[10])
        self.assertEqual(summarise(purge([inside], self.window))["embargoed"], 1)

    def test_a_trade_opened_after_the_embargo_is_clean(self):
        after = [d for d in sessions() if d > FREEZE]
        outside = Trade(after[25], after[30])
        self.assertEqual(summarise(purge([outside], self.window))["clean"], 1)

    def test_the_first_admissible_session_is_the_boundary(self):
        after = [d for d in sessions() if d > FREEZE]
        just_before = Trade(after[19], after[24])
        just_after = Trade(after[20], after[25])
        self.assertEqual(summarise(purge([just_before], self.window))["embargoed"], 1)
        self.assertEqual(summarise(purge([just_after], self.window))["clean"], 1)

    def test_with_no_clean_period_nothing_is_clean(self):
        short = evaluation_window(REGISTRY, sessions(n=14))
        after = [d for d in sessions() if d > FREEZE]
        t = Trade(after[2], after[5])
        self.assertEqual(summarise(purge([t], short))["clean"], 0)


class FutureCannotAlterThePast(unittest.TestCase):
    """Property 3."""

    def test_adding_later_sessions_does_not_reclassify_earlier_trades(self):
        trades = [Trade(date(2026, 9, 2), date(2026, 9, 8)),
                  Trade(date(2026, 9, 9), date(2026, 9, 25))]
        short = purge(trades, evaluation_window(REGISTRY, sessions(n=40)))
        longer = purge(trades, evaluation_window(REGISTRY, sessions(n=200)))
        self.assertEqual(summarise(short)["pre_freeze"], summarise(longer)["pre_freeze"])
        self.assertEqual(summarise(short)["straddling"], summarise(longer)["straddling"])

    def test_adding_later_EXPERIMENTS_that_change_nothing_moves_no_boundary(self):
        extended = REGISTRY + [{"when": "2026-12-01", "decision": "measured"},
                               {"when": "2026-12-02", "decision": "rejected"}]
        self.assertEqual(freeze_date(extended), freeze_date(REGISTRY))

    def test_a_later_CONFIG_CHANGE_does_move_it_and_must(self):
        # The honest converse: changing the strategy again restarts the
        # clock. That is the cost of a change, and it should be visible.
        extended = REGISTRY + [{"when": "2026-12-01", "decision": "accepted"}]
        self.assertEqual(freeze_date(extended), date(2026, 12, 1))


class Reproducible(unittest.TestCase):
    """Property 4."""

    def test_the_same_inputs_give_the_same_window(self):
        a = evaluation_window(REGISTRY, sessions())
        b = evaluation_window(list(REGISTRY), list(sessions()))
        self.assertEqual(a.as_dict(), b.as_dict())

    def test_the_window_serialises_every_rule_it_applied(self):
        d = evaluation_window(REGISTRY, sessions()).as_dict()
        self.assertEqual(set(d), {"freeze", "embargo_sessions", "clean_from",
                                  "sessions_embargoed"})

    def test_every_trade_lands_in_exactly_one_bucket(self):
        after = [d for d in sessions() if d > FREEZE]
        trades = [Trade(date(2026, 9, 2), date(2026, 9, 8)),
                  Trade(date(2026, 9, 9), date(2026, 9, 25)),
                  Trade(after[3], after[10]),
                  Trade(after[25], after[30])]
        buckets = purge(trades, evaluation_window(REGISTRY, sessions()))
        self.assertEqual(sum(summarise(buckets).values()), len(trades))
        self.assertEqual(summarise(buckets),
                         {"clean": 1, "embargoed": 1, "pre_freeze": 1,
                          "straddling": 1})


if __name__ == "__main__":
    unittest.main()
