"""Does spelling decide who gets scarce bucket capacity?

THIS TEST DOCUMENTS CURRENT BEHAVIOUR. IT DOES NOT FIX IT.

`run_portfolio` iterates candidates in the order `series` was built
unless a `candidate_rank` is supplied. `production_report` supplies
none, and every research loader in this repository builds `series` by
iterating a SORTED symbol list. So when the correlation-bucket cap of 1
forces a choice between two otherwise identical candidates, the slot
goes to whichever name sorts first.

This was found and swept on 2026-09-11: four orderings - alphabetical,
oversold, overnight, conviction - were measured across the decade and
the thirty-year window and produced a 0.58-point spread that flipped
between windows, so the sweep was REJECTED as noise and no ordering was
adopted. The behaviour therefore stands as a deterministic default with
`candidate_rank` left as the hook.

What no test pinned until now is the MECHANISM: that the choice is
decided by the symbol string and by nothing economic. These tests hold
the economics exactly constant and vary only the name.
"""

import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.data import Bar
from event_aware_trader.mean_reversion import MeanReversionConfig, evaluate
from event_aware_trader.portfolio import run_portfolio
from event_aware_trader.risk import CostModel, RiskPolicy
from event_aware_trader.strategy import CORRELATION_BUCKETS


def ramp(n=260, peak=240, start=100.0):
    """A long uptrend then a mild pullback: RSI low, close above the
    200-day average, ATR inside the ceiling. Produces a clean BUY."""
    out, day, px = [], datetime(2024, 1, 1, tzinfo=timezone.utc), start
    for i in range(n):
        px *= 1.0035 if i < peak else 0.9905
        while day.weekday() >= 5:
            day += timedelta(days=1)
        out.append(Bar(timestamp=day, open=px * 0.999, high=px * 1.004,
                       low=px * 0.996, close=px, volume=4_000_000))
        day += timedelta(days=1)
    return out


def policy():
    return RiskPolicy(allow_fractional_shares=False, max_per_bucket=1,
                      max_open_positions=12)


def build(symbols):
    """Identical bars under each name, so only the spelling differs."""
    bars = ramp()
    return {s: [Bar(timestamp=b.timestamp, open=b.open, high=b.high,
                    low=b.low, close=b.close, volume=b.volume)
                for b in bars] for s in symbols}


def go(series):
    return run_portfolio(series, starting_cash=100_000.0, policy=policy(),
                         costs=CostModel(), entry_rule="mean_reversion",
                         entry_fill="signal_close", max_entries_per_day=3)


def run(symbols):
    """SORTED, because every research loader in this repository builds
    `series` by iterating a sorted symbol list. That is what makes the
    insertion order alphabetical in practice."""
    return go(build(sorted(symbols)))


def chosen(report):
    return ({t.symbol for t in report.trades}
            | {p.symbol for p in report.open_positions})


class TheFixtureIsValid(unittest.TestCase):
    """If the synthetic names do not both qualify, the ordering tests
    below prove nothing."""

    def test_the_fixture_produces_a_buy(self):
        sig = evaluate("AAAA", ramp(), MeanReversionConfig())
        self.assertEqual(sig.action, "BUY", sig.reasons)
        self.assertIsNotNone(sig.stop)

    def test_both_names_share_one_bucket(self):
        a = CORRELATION_BUCKETS.get("AAAA", "other")
        z = CORRELATION_BUCKETS.get("ZZZZ", "other")
        self.assertEqual(a, z)

    def test_the_bucket_cap_permits_only_one(self):
        self.assertEqual(policy().max_per_bucket, 1)


class SpellingDecidesWhoGetsTheSlot(unittest.TestCase):
    """Identical economics, identical timestamps, identical risk,
    identical bucket. Only the name differs."""

    def test_only_one_of_two_identical_candidates_is_taken(self):
        report = run(["AAAA", "ZZZZ"])
        self.assertEqual(len(chosen(report)), 1,
                         "the bucket cap should admit exactly one")

    def test_the_first_name_alphabetically_wins(self):
        self.assertEqual(chosen(run(["ZZZZ", "AAAA"])), {"AAAA"},
                         "sorted insertion makes the alphabet decide")

    def test_the_raw_mechanism_is_dict_insertion_order(self):
        """Underneath the alphabet it is INSERTION order that governs -
        `todays_bars` is built by iterating `series`. Build the dict
        with ZZZZ first, without sorting, and ZZZZ wins. Research
        loaders sort, which is what turns this into the alphabet."""
        self.assertEqual(chosen(go(build(["ZZZZ", "AAAA"]))), {"ZZZZ"})
        self.assertEqual(chosen(go(build(["AAAA", "ZZZZ"]))), {"AAAA"})

    def test_renaming_alone_flips_the_selection(self):
        """THE DEMONSTRATION. Same bars, same bucket, same risk, same
        day. Rename one candidate and a different one is bought."""
        a = chosen(run(["AAAA", "MMMM"]))   # sorted -> AAAA first
        b = chosen(run(["NNNN", "MMMM"]))   # sorted -> MMMM first
        self.assertEqual(a, {"AAAA"})
        self.assertEqual(b, {"MMMM"})
        self.assertNotEqual(a, b)

    def test_the_economics_really_were_identical(self):
        """Guards the demonstration: if the two candidates differed on
        any economic input, the flip would prove nothing."""
        bars = ramp()
        one = evaluate("AAAA", bars, MeanReversionConfig())
        two = evaluate("MMMM", bars, MeanReversionConfig())
        self.assertEqual(one.action, two.action)
        self.assertEqual(one.close, two.close)
        self.assertEqual(one.stop, two.stop)
        self.assertEqual(one.rsi, two.rsi)
        self.assertEqual(one.atr_fraction, two.atr_fraction)


class ACandidateRankOverridesTheSpelling(unittest.TestCase):
    """The hook exists and works; production simply does not pass one."""

    def test_a_rank_can_select_the_later_name(self):
        bars = ramp()
        series = {s: [Bar(timestamp=b.timestamp, open=b.open, high=b.high,
                          low=b.low, close=b.close, volume=b.volume)
                      for b in bars] for s in ("AAAA", "ZZZZ")}
        report = run_portfolio(
            series, starting_cash=100_000.0, policy=policy(),
            costs=CostModel(), entry_rule="mean_reversion",
            entry_fill="signal_close", max_entries_per_day=3,
            candidate_rank=lambda symbol, history: 1.0 if symbol == "ZZZZ"
            else 0.0)
        self.assertEqual(chosen(report), {"ZZZZ"},
                         "candidate_rank should override alphabetical order")

    def test_production_passes_no_candidate_rank(self):
        """The condition this file documents. If production ever starts
        supplying a rank, this test should fail and be updated as part
        of that registered change."""
        from event_aware_trader.research import PRODUCTION_CANDIDATE
        self.assertNotIn("candidate_rank", PRODUCTION_CANDIDATE)


if __name__ == "__main__":
    unittest.main()
